# Build: 1
"""The data half of a language pack, and what it may cost when it is wrong.

A pack's UI half has always been validated key by key. Its data half — the one
consumed by game/data_loader/translationmixin.py — used to reach the disk on
nothing but `isinstance(dict)`, and the overlay that reads it runs inside
engine.load(), whose blanket handler QUARANTINES the save when anything raises.
So a malformed section published once was a silent, unrecoverable loss of
progress for every player who downloaded that language.

These tests pin both ends of that path: the shape a pack must have to be
installed at all, and the guarantee that a pack which slipped through anyway
costs English game text and nothing else.
"""
import glob
import json
import os

import pytest

from game.remote_content import packs


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Point Path.home() at a scratch dir — the real home holds the save."""
    import pathlib
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


# ------------------------------------------------- the contract, as published

def _shipped_data_files():
    return sorted(glob.glob(os.path.join(packs.bundled_dir(), "data_*.json")))


def test_every_shipped_pack_survives_the_contract_unchanged():
    """The contract is derived from the overlay, so it must fit real content.

    A rule the shipped languages cannot satisfy is a rule that would silently
    strip translations, which is the failure this validation exists to avoid.
    """
    files = _shipped_data_files()
    assert files, "no data_*.json to check the contract against"
    for path in files:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        assert packs.validate_data(raw) == raw, f"{path} was altered"


def test_the_contract_covers_every_section_the_overlay_reads():
    """The section list here and the .get() calls in the overlay are one set.

    Drift either way is silent: a section missing here is stripped from every
    pack, a section the overlay stopped reading is validated for nothing.
    """
    source_path = os.path.join(os.path.dirname(packs.__file__),
                               "..", "data_loader", "translationmixin.py")
    with open(os.path.abspath(source_path), encoding="utf-8") as handle:
        source = handle.read()
    known = set(packs.DATA_FLAT_SECTIONS) | {packs.DATA_CLASSES_SECTION}
    for section in known:
        assert f'tr.get("{section}"' in source, f"{section} is not read any more"


# ------------------------------------------------------------ what is refused

@pytest.mark.parametrize("data", [
    "not a document",
    {"enemies": ["goblin"]},                       # section is not a mapping
    {"enemies": {"goblin": "Гоблін"}},             # entry is not a mapping
    {"enemies": {"goblin": {"name": 5}}},          # field is not text
    {"classes": {"merc": {"passive_ability": 7}}},  # nested block is not a mapping
    {"classes": {"merc": {"perks": {"p": 3}}}},    # perk is not a mapping
])
def test_a_malformed_data_half_is_refused(data):
    assert packs.validate_data(data) is None


def test_an_oversized_string_is_refused():
    over = "x" * (packs.MAX_DATA_TEXT_CHARS + 1)
    assert packs.validate_data({"lore": {"a": {"text": over}}}) is None
    assert packs.validate_data({"lore": {"a": {"text": over[:-1]}}}) is not None


def test_sections_this_build_does_not_read_are_dropped_not_refused():
    """Forward compatibility: a pack built for a newer game still installs."""
    clean = packs.validate_data({"quests": {"q1": {"name": "Q"}},
                                 "lore": {"a": {"text": "текст"}}})
    assert clean == {"lore": {"a": {"text": "текст"}}}


def test_fields_outside_the_contract_are_dropped():
    clean = packs.validate_data({"lore": {"a": {"text": "текст", "notes": 7}}})
    assert clean == {"lore": {"a": {"text": "текст"}}}


def test_validate_pack_refuses_the_whole_pack_over_its_data_half():
    from tests.test_remote_content import _pack_payload
    payload = _pack_payload()
    payload["data"] = {"enemies": ["goblin"]}
    assert packs.validate_pack(payload, "uk") == (None, None)


def test_install_writes_only_contract_shaped_data(isolated_home):
    from tests.test_remote_content import _pack_payload
    payload = _pack_payload()
    payload["data"] = {"enchantments": {"burn": {"name": "Опік", "extra": 1}},
                       "quests": {"q1": {"name": "Q"}}}
    assert packs.install("uk", payload, revision=1)
    written = isolated_home / packs.PACKS_DIRNAME / "data_uk.json"
    with open(written, encoding="utf-8") as handle:
        assert json.load(handle) == {"enchantments": {"burn": {"name": "Опік"}}}


# -------------------------------------------- a bad pack must not cost a save

def test_a_raising_overlay_does_not_quarantine_the_save(tmp_save_path, monkeypatch):
    """The whole point: engine.load() survives an overlay that blows up.

    A pack installed before the validation above existed can still be sitting
    on a player's disk, so the guard is the thing that has to hold.
    """
    from game.data_loader import data_loader
    from game.engine import GameEngine
    from game.localization import get_language, set_language

    def boom(_lang_code):
        raise AttributeError("'list' object has no attribute 'get'")

    original_language = get_language()
    monkeypatch.setattr(data_loader, "apply_translations", boom)
    try:
        engine = GameEngine(save_path=tmp_save_path)
        engine.gold = 4242
        engine.save()
        reloaded = GameEngine(save_path=tmp_save_path)
        reloaded.load({"gold": 4242, "language": "ru", "fighters": []})
    finally:
        set_language(original_language)

    assert reloaded.gold == 4242, "the save was thrown away over a translation"
    assert not os.path.exists(tmp_save_path + ".corrupt")
    assert not reloaded._load_failed


# ------------------------------------------------------- client-side plumbing

def test_a_font_download_in_flight_is_not_collected(isolated_home):
    """_collect_garbage shares its directory with a concurrent writer."""
    in_flight = packs.fonts_dir() / ("deadbeef.ttf" + packs.TMP_SUFFIX)
    stale = packs.fonts_dir() / "0badc0de.ttf"
    in_flight.write_bytes(b"partial")
    stale.write_bytes(b"unreferenced")
    packs._collect_garbage({})
    assert in_flight.exists()
    assert not stale.exists()


def test_state_files_are_written_atomically(isolated_home, monkeypatch):
    """A force-kill mid-write must leave the previous mapping readable."""
    packs._record_font("uk", "abc.ttf", "0" * 64)

    def die(*_args, **_kwargs):
        raise OSError("device went away")

    monkeypatch.setattr(packs.shutil, "move", die)
    packs._record_font("uk", "def.ttf", "1" * 64)
    assert packs._fonts_state() == {"uk": {"file": "abc.ttf", "sha256": "0" * 64}}


def test_an_unusable_manifest_does_not_evict_a_good_one(isolated_home, monkeypatch):
    """One bad publish must not blank the picker on every installed client."""
    import game.remote_content as rc
    from game.remote_content import _cache
    good = {"schema": _manifest_schema(),
            "entries": {"pack.uk": {"path": "packs/uk.v1.json", "revision": 1}}}
    _cache.write(rc.MANIFEST_CACHE, good)
    monkeypatch.setattr(rc._net, "is_online", lambda: True)
    monkeypatch.setattr(rc._http, "fetch_json",
                        lambda *a, **k: {"schema": 999, "entries": {}})
    assert rc.refresh_manifest(force=True) is True
    assert _cache.read(rc.MANIFEST_CACHE) == good


def _manifest_schema():
    from game.remote_content import _manifest
    return _manifest.SCHEMA


# ------------------------------------------- unbalanced braces at publish time

@pytest.mark.parametrize("text", [
    "Золото: {n} монет {",       # lone brace beside a valid placeholder
    "Просто текст {",            # lone brace in a string with no placeholders
])
def test_a_string_that_cannot_be_formatted_is_rejected(text):
    from game.remote_content.languages import _reject_reason
    base = {"a": "Gold: {n} coins", "b": "Plain text"}
    key = "a" if "{n}" in text else "b"
    assert _reject_reason(key, text, base) is not None


def test_a_formattable_translation_is_still_accepted():
    from game.remote_content.languages import _reject_reason
    base = {"a": "Gold: {n} coins"}
    assert _reject_reason("a", "Золото: {n} монет", base) is None
