# Build: 1
"""Story quest checks — fact-of-event, not localized log text.

Regression for the 2026-08 audit: ch6_q3 "Void Walker" matched the English
substrings "Void Rift"/"returned" against engine.expedition_log, but the log
is localized (t("expedition_returned", ...)), so the quest was unreachable in
every language except English. The fix routes the quest (and the
expedition_completed_specific achievement condition) through
engine.has_completed_expedition(), backed by the persisted
completed_expedition_ids list.
"""
import json

import pytest

from game.engine import GameEngine
from game.models import Fighter
from game.story import STORY_CHAPTERS

VOID_RIFT_ID = "void_rift"
CH6_INDEX = 5  # chapter index of "Chapter VI: The Void" in STORY_CHAPTERS


def _quest(quest_id):
    for chapter in STORY_CHAPTERS:
        for quest in chapter["quests"]:
            if quest["id"] == quest_id:
                return quest
    raise AssertionError(f"quest {quest_id!r} not found")


def _return_from_void_rift(engine, monkeypatch):
    """Send a fighter to the Void Rift and bring him back alive."""
    import game.engine._expeditions as exp_mod
    # Deterministic rolls: 0.99 >= danger(0.75) → survives; >= relic_chance
    # (0.55) → no relic; no extra injury. randint (shard amount) untouched.
    monkeypatch.setattr(exp_mod.random, "random", lambda: 0.99)
    f = Fighter(fighter_class="mercenary")
    f.level = 30  # void_rift min_level is 22
    engine.fighters.append(f)
    res = engine.send_on_expedition(0, VOID_RIFT_ID)
    assert res.ok, res.message
    f.expedition_end = 0.0  # expedition already over
    results = engine.check_expeditions()
    assert results, "expedition must have resolved"
    return f


def test_ch6_q3_completes_on_non_english_locale(engine, monkeypatch):
    """The quest must close from the event itself, whatever t() returns."""
    import game.engine._expeditions as exp_mod

    def fake_t(key, **kw):
        # Russian-style template: expedition name present, the English
        # word "returned" absent — exactly the case the old substring
        # check could never match.
        return f"Боец вернулся из '{kw.get('exp', '')}'"

    monkeypatch.setattr(exp_mod, "t", fake_t)
    quest = _quest("ch6_q3")
    assert not quest["check"](engine)

    _return_from_void_rift(engine, monkeypatch)

    assert VOID_RIFT_ID in engine.completed_expedition_ids
    # The localized log genuinely lacks the old English markers...
    assert not any("returned" in log for log in engine.expedition_log)
    # ...yet the quest check passes.
    assert quest["check"](engine)

    # Full path: check_quests marks it completed once ch6 is reachable.
    engine.story_chapter = CH6_INDEX
    engine.check_quests()
    assert "ch6_q3" in engine.quests_completed


def test_ch6_q3_completes_on_english_locale(engine, monkeypatch):
    """Same event, default (English) locale — no regression."""
    quest = _quest("ch6_q3")
    _return_from_void_rift(engine, monkeypatch)
    assert quest["check"](engine)


def test_legacy_english_log_still_counts(engine):
    """Pre-field saves kept the completion only as an English log line."""
    assert VOID_RIFT_ID not in engine.completed_expedition_ids
    engine.expedition_log.append("Marcus returned from Void Rift!")
    assert engine.has_completed_expedition(VOID_RIFT_ID)
    assert _quest("ch6_q3")["check"](engine)


def test_achievement_condition_uses_same_source(engine):
    """expedition_completed_specific delegates to the engine method."""
    from game.achievements_checks import _build_check
    check = _build_check(
        {"type": "expedition_completed_specific", "value": VOID_RIFT_ID})
    assert not check(engine)
    engine.completed_expedition_ids.append(VOID_RIFT_ID)
    assert check(engine)


def test_old_save_without_completed_ids_loads(tmp_save_path):
    """Saves written before completed_expedition_ids existed load cleanly."""
    eng = GameEngine(save_path=tmp_save_path)
    eng.load()
    eng.save()
    with open(tmp_save_path, encoding="utf-8") as fh:
        data = json.load(fh)
    assert "completed_expedition_ids" in data
    del data["completed_expedition_ids"]
    with open(tmp_save_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.completed_expedition_ids == []
    assert eng2.has_completed_expedition(VOID_RIFT_ID) is False
    assert not _quest("ch6_q3")["check"](eng2)
