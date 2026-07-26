# Build: 1
"""Gate for the unified event log (Lore → Stats → Event Log).

Four display bugs shipped here at once and none of them were caught by a
test, because every one lives in the seam between three layers: the
engine writes an entry, a translation file names it, and the log screen
formats it. These tests hold that seam:

1. one battle == one event (a second "battle_end" event duplicated every
   fight in the log);
2. every event type the engine can write has an `evt_*` key in EVERY
   language file (a missing key renders as the raw key, e.g.
   "evt_battle_end", because localization.t() falls back to the key);
3. no formatter path leaks a raw dict into a row ("{'t': 1784943830,
   'type': ...}" was visible on screen);
4. every glyph used by an event-log string exists in PressStart2P — the
   pixel font has no box-drawing characters, so a U+2500 rule rendered
   as a row of tofu squares.
"""
import ast
import glob
import json
import os
import re

import pytest

_PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LANG_DIR = os.path.join(_PROJ_ROOT, "data", "languages")
_PIXEL_FONT = os.path.join(_PROJ_ROOT, "fonts", "PressStart2P-Regular.ttf")

# Event types written by the engine as `self._log_event("<type>", ...)`.
_LOG_EVENT_RE = re.compile(r'_log_event\(\s*["\']([a-z_]+)["\']')


def _engine_event_types():
    """Every event type the engine can append, scraped from the source.

    Scraped rather than hardcoded so a newly logged event type is caught
    by the key gate below on the commit that introduces it.
    """
    from game.scripting.builtins import SCRIPT_EVENT_TYPE
    types = {SCRIPT_EVENT_TYPE}
    for path in glob.glob(os.path.join(_PROJ_ROOT, "game", "**", "*.py"),
                          recursive=True):
        with open(path, "r", encoding="utf-8") as f:
            types.update(_LOG_EVENT_RE.findall(f.read()))
    return types


def _lang_files():
    return sorted(glob.glob(os.path.join(_LANG_DIR, "??.json")))


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class _StubEnemy:
    def __init__(self, name="Rat"):
        self.name = name


class _StubResult:
    """Minimal stand-in for BattleResult as _record_battle consumes it."""

    def __init__(self, player_fighters, gold=25):
        self.is_boss = False
        self.gold_earned = gold
        self.turn_number = 4
        self.player_fighters = list(player_fighters)
        self.enemies = [_StubEnemy()]


# ---------- 1. one battle == one event ----------

def _roster_of_two(engine):
    """Two named fighters: one fights, one sits out."""
    engine.gold = 10_000
    while len(engine.fighters) < 2:
        engine.hire_gladiator()
    engine.fighters[0].name = "Fighter_A"
    engine.fighters[1].name = "Fighter_B"
    engine.event_log.clear()
    return engine.fighters


def test_resolved_battle_logs_exactly_one_event(engine):
    fighters = _roster_of_two(engine)
    engine._record_battle(_StubResult(fighters[:1]), "V")

    assert len(engine.event_log) == 1, (
        f"expected 1 event per battle, got {[e['type'] for e in engine.event_log]}"
    )
    entry = engine.event_log[0]
    assert entry["type"] == "battle"
    assert entry["result"] == "victory"


def test_battle_event_carries_skipped_roster(engine):
    """The retired battle_end event existed only to carry `skipped`."""
    fighters = _roster_of_two(engine)
    engine._record_battle(_StubResult(fighters[:1]), "V")

    skipped = engine.event_log[0]["skipped"]
    assert skipped == ["Fighter_B"]


def test_battle_end_event_type_is_gone():
    """No engine callsite may reintroduce the duplicate event."""
    assert "battle_end" not in _engine_event_types()


# ---------- 2. every event type is translated, in every language ----------

def test_every_event_type_has_translation_key_in_every_language():
    expected = {f"evt_{etype}" for etype in _engine_event_types()}
    missing = {}
    for path in _lang_files():
        data = _load(path)
        absent = sorted(k for k in expected if k not in data)
        if absent:
            missing[os.path.basename(path)] = absent
    assert not missing, (
        "event types with no evt_* key — localization.t() renders the raw "
        f"key on screen: {missing}"
    )


def test_no_orphan_evt_keys():
    """An evt_* key with no event type behind it is dead weight (and a
    hint that the event was renamed or removed on one side only)."""
    live = {f"evt_{etype}" for etype in _engine_event_types()}
    orphans = sorted(k for k in _load(os.path.join(_LANG_DIR, "en.json"))
                     if k.startswith("evt_") and k not in live)
    assert not orphans, f"evt_* keys with no matching event type: {orphans}"


# ---------- 3. no raw dict leaks into a row ----------

def _format(entry):
    from game.screens.lore import LoreScreen
    return LoreScreen._format_event_detail(entry)


def test_known_event_types_format_without_dict_dump():
    sample_fields = {
        "result": "victory", "tier": 3, "boss": False, "gold": 50,
        "name": "Maximus", "cls": "Brute", "lv": 4, "perk": "Iron Skin",
        "item": "Rusty Blade", "fighter": "Maximus", "ench": "Flame",
        "injury": "Sprain", "exp": "Deep Woods", "n": 2, "text": "hello",
        "skipped": ["Crixus", "Spartacus"],
    }
    for etype in _engine_event_types():
        entry = {"t": 1784943830, "type": etype, **sample_fields}
        detail = _format(entry)
        assert "{" not in detail and "'t':" not in detail, (
            f"event type {etype!r} leaked a raw dict into the log row: {detail!r}"
        )


def test_unknown_event_type_formats_without_dict_dump():
    """Old saves and future events must degrade to readable fields."""
    detail = _format({"t": 1784943830, "type": "some_future_event",
                      "who": "Maximus", "amount": 7})
    assert "{" not in detail
    assert "who=Maximus" in detail
    assert "amount=7" in detail


def test_list_field_renders_names_not_a_bare_count():
    from game.screens.lore.event_logs_mixin import _fmt_event_value
    assert _fmt_event_value(["Crixus", "Spartacus"]) == "Crixus, Spartacus"
    assert _fmt_event_value([]) == "-"
    long_value = _fmt_event_value([f"Fighter{i}" for i in range(20)])
    assert long_value.endswith("…") and len(long_value) <= 48


# ---------- 4. every glyph exists in the pixel font ----------

def _pixel_font_cmap():
    fontTools = pytest.importorskip(
        "fontTools", reason="fontTools not installed — glyph gate skipped")
    from fontTools.ttLib import TTFont
    return set(TTFont(_PIXEL_FONT).getBestCmap())


def test_evt_strings_use_only_glyphs_present_in_pixel_font():
    cmap = _pixel_font_cmap()
    offenders = {}
    for path in _lang_files():
        for key, value in _load(path).items():
            if not key.startswith("evt_") or not isinstance(value, str):
                continue
            bad = {c for c in value if ord(c) not in cmap}
            if bad:
                offenders[f"{os.path.basename(path)}:{key}"] = sorted(
                    f"U+{ord(c):04X}" for c in bad)
    assert not offenders, (
        f"event-log labels use glyphs PressStart2P lacks (renders as tofu): "
        f"{offenders}"
    )


def test_event_log_screen_literals_use_only_pixel_font_glyphs():
    """Catches the U+2500 divider that shipped as a row of tofu squares."""
    cmap = _pixel_font_cmap()
    path = os.path.join(_PROJ_ROOT, "game", "screens", "lore",
                        "event_logs_mixin.py")
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    # Parse rather than grep: only string literals reach the screen, and
    # the module's comments deliberately quote the offending glyph.
    literals = [node.value for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    bad = {c for lit in literals for c in lit
           if not c.isspace() and ord(c) not in cmap}
    assert not bad, (
        "event-log screen renders glyphs PressStart2P lacks: "
        f"{sorted(f'U+{ord(c):04X}' for c in bad)}"
    )
