# Build: 2
"""Regression tests for the 2026-07-24 audit fixes.

Covers:
* IAP — no free purchase on android/ios when billing is uninitialized
  (desktop stub still auto-succeeds for local testing).
* Ads — no free rewarded-video reward on android when ads are
  uninitialized (desktop stub still simulates).
* Persistence — load() recovers a save stranded in .tmp/.bak; an
  unreadable primary is quarantined to .corrupt; _load_failed blocks
  save()/save_async() and queues a toast; backup rotation copies (the
  primary never disappears mid-save); failed external (cloud) data can't
  autosave over the local file.
* Achievements — _wire_data fills ACHIEVEMENTS in place, so references
  captured at import time (lore screen) see the JSON data.
* Scripting — interpreter engine ops serialize on engine.state_lock; a
  stub engine without the lock still works.
* Online library — oversized manifests are rejected.
"""
import json
import os
import threading
import time

import pytest


# ---------- IAP ----------

def test_iap_uninitialized_android_never_grants(monkeypatch):
    import game.iap._core as iap_core
    monkeypatch.setattr(iap_core, "platform", "android")
    mgr = iap_core.IAPManager()
    assert not mgr._initialized
    got = {"success": False, "failure": None}
    mgr.purchase(
        "gems_100",
        on_success=lambda: got.__setitem__("success", True),
        on_failure=lambda reason: got.__setitem__("failure", reason),
    )
    assert got["success"] is False
    assert got["failure"]


def test_iap_uninitialized_desktop_stub_grants(monkeypatch):
    import game.iap._core as iap_core
    monkeypatch.setattr(iap_core, "platform", "win")
    mgr = iap_core.IAPManager()
    got = {"success": False}
    mgr.purchase("gems_100", on_success=lambda: got.__setitem__("success", True))
    assert got["success"] is True


# ---------- Ads ----------

def test_rewarded_uninitialized_android_no_reward(monkeypatch):
    # game/ads is a package now — patch platform where the gating code
    # lives (game.ads._core), same as the IAP tests patch game.iap._core.
    import game.ads._core as ads_core
    monkeypatch.setattr(ads_core, "platform", "android")
    mgr = ads_core.AdManager()
    assert not mgr._initialized
    calls = []
    mgr.show_rewarded(lambda: calls.append(1))
    assert calls == []


def test_rewarded_uninitialized_desktop_stub_rewards(monkeypatch):
    import game.ads._core as ads_core
    monkeypatch.setattr(ads_core, "platform", "win")
    mgr = ads_core.AdManager()
    calls = []
    mgr.show_rewarded(lambda: calls.append(1))
    assert calls == [1]


# ---------- Persistence: recovery ----------

def _fresh_engine(save_path):
    from game.engine import GameEngine
    return GameEngine(save_path=save_path)


def test_load_recovers_from_bak_when_primary_missing(tmp_save_path):
    eng = _fresh_engine(tmp_save_path)
    eng.load()
    eng.gold = 777_777
    eng.save()
    # Old-build kill window: primary rotated away, .bak holds the progress.
    os.replace(tmp_save_path, tmp_save_path + ".bak")

    eng2 = _fresh_engine(tmp_save_path)
    eng2.load()
    assert eng2.gold == 777_777
    assert eng2._is_first_launch is False


def test_load_recovers_from_tmp_when_primary_missing(tmp_save_path):
    eng = _fresh_engine(tmp_save_path)
    eng.load()
    eng.gold = 31_337
    eng.save()
    # Kill between backup rotation and final replace: only .tmp remains.
    os.replace(tmp_save_path, tmp_save_path + ".tmp")

    eng2 = _fresh_engine(tmp_save_path)
    eng2.load()
    assert eng2.gold == 31_337
    assert eng2._is_first_launch is False


def test_load_prefers_tmp_over_bak(tmp_save_path):
    # .tmp is the newer write in every real crash sequence.
    with open(tmp_save_path + ".bak", "w", encoding="utf-8") as f:
        json.dump({"gold": 111}, f)
    with open(tmp_save_path + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"gold": 222}, f)

    eng = _fresh_engine(tmp_save_path)
    eng.load()
    assert eng.gold == 222


def test_corrupt_primary_quarantined_and_bak_used(tmp_save_path):
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        f.write("{ this is not json")
    with open(tmp_save_path + ".bak", "w", encoding="utf-8") as f:
        json.dump({"gold": 555}, f)

    eng = _fresh_engine(tmp_save_path)
    eng.load()
    assert eng.gold == 555
    # Corrupt primary moved aside so the next rotation can't clobber .bak.
    assert not os.path.exists(tmp_save_path)
    assert os.path.exists(tmp_save_path + ".corrupt")
    assert eng._load_failed is False


def test_all_unreadable_quarantines_and_allows_fresh_save(tmp_save_path):
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        f.write("garbage")
    eng = _fresh_engine(tmp_save_path)
    eng.load()
    assert eng._is_first_launch is False
    assert eng._load_failed is False
    assert os.path.exists(tmp_save_path + ".corrupt")
    eng.save()
    assert os.path.exists(tmp_save_path)


def test_fresh_install_still_detected(tmp_save_path):
    eng = _fresh_engine(tmp_save_path)
    eng.load()
    assert eng._is_first_launch is True
    assert eng._load_failed is False


# ---------- Persistence: _load_failed / notifications ----------

def test_load_failed_blocks_save_and_notifies(engine):
    engine._load_failed = True
    engine.pending_notifications.clear()
    out = engine.save()
    assert out == {}
    assert not os.path.exists(engine.SAVE_PATH)
    assert len(engine.pending_notifications) == 1
    # Anti-spam: the same issue toasts once per session.
    engine.save()
    assert len(engine.pending_notifications) == 1


def test_load_failed_blocks_save_async(engine):
    engine._load_failed = True
    engine.save_async()
    time.sleep(0.1)
    assert not os.path.exists(engine.SAVE_PATH)


def test_bad_external_data_sets_load_failed(engine):
    # Cloud handed us an unusable dict: engine must fresh-start WITHOUT
    # gaining the right to overwrite the local save file.
    engine.load(data={"fighters": "not-a-list"})
    assert engine._load_failed is True
    assert engine.save() == {}


def test_save_write_failure_surfaces_toast(engine, monkeypatch):
    def boom(data):
        raise OSError("disk full")
    monkeypatch.setattr(engine, "_write_save_to_disk", boom)
    engine.pending_notifications.clear()
    out = engine.save()
    assert "gold" in out  # snapshot still returned for cloud paths
    assert len(engine.pending_notifications) == 1


# ---------- Persistence: rotation ----------

def test_backup_rotation_copies_primary(engine):
    engine.load()
    engine.gold = 1
    engine.save()
    engine.gold = 2
    engine.save()
    # Copy-based rotation: BOTH files present, .bak = previous state.
    assert os.path.exists(engine.SAVE_PATH)
    assert os.path.exists(engine.SAVE_PATH + ".bak")
    with open(engine.SAVE_PATH, encoding="utf-8") as f:
        assert json.load(f)["gold"] == 2
    with open(engine.SAVE_PATH + ".bak", encoding="utf-8") as f:
        assert json.load(f)["gold"] == 1


# ---------- Achievements wiring ----------

def test_achievements_wired_in_place(tmp_save_path):
    import game.achievements as am
    captured = am.ACHIEVEMENTS  # simulates an import-time `from ... import`
    _fresh_engine(tmp_save_path)  # __init__ runs _wire_data
    assert captured is am.ACHIEVEMENTS
    # JSON supersedes the 29-entry hardcoded fallback; the captured
    # reference must see the full set (the "21/29" lore-screen bug).
    assert len(captured) >= 30


# ---------- Scripting: state lock ----------

def _log_program():
    from game.scripting.ast_nodes import Program, Trigger, Action, Const
    return Program(
        name="lock-test",
        trigger=Trigger.ON_DEMAND,
        enabled=True,
        body=[Action("log", [Const("locked")])],
    )


def test_interpreter_blocks_on_state_lock(engine):
    from game.scripting.interpreter import Interpreter

    def script_events():
        return [e for e in engine.event_log
                if isinstance(e, dict) and e.get("kind") == "script"]

    started = threading.Event()

    def worker():
        started.set()
        Interpreter(engine, _log_program()).run()

    th = threading.Thread(target=worker, daemon=True)
    with engine.state_lock:
        th.start()
        assert started.wait(2.0)
        time.sleep(0.15)  # give a buggy (lock-free) interpreter time to run
        assert script_events() == []
    th.join(2.0)
    assert not th.is_alive()
    assert len(script_events()) == 1


def test_interpreter_works_without_state_lock():
    from game.scripting.interpreter import Interpreter

    class StubEngine:
        fighters = []
        event_log = []

    stub = StubEngine()
    Interpreter(stub, _log_program()).run()
    assert stub.event_log and stub.event_log[0]["kind"] == "script"


# ---------- Online library ----------

def test_manifest_size_cap(monkeypatch):
    from game.scripting import online_library as ol

    class FakeResp:
        def read(self, n=-1):
            size = n if isinstance(n, int) and n > 0 else ol.MAX_MANIFEST_BYTES + 10
            return b"x" * size

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(ol.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    monkeypatch.setattr(ol, "save_cached", lambda payload: pytest.fail(
        "oversized manifest must not be cached"))
    assert ol.fetch_remote() is None


def test_manifest_normal_size_accepted(monkeypatch):
    from game.scripting import online_library as ol
    body = json.dumps({"scripts": [{"id": "a", "program": {}}]}).encode("utf-8")

    class FakeResp:
        def read(self, n=-1):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    cached = {}
    monkeypatch.setattr(ol.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    monkeypatch.setattr(ol, "save_cached", lambda payload: cached.update(payload))
    payload = ol.fetch_remote()
    assert payload and payload["scripts"][0]["id"] == "a"
    assert cached  # accepted manifests still hit the cache
