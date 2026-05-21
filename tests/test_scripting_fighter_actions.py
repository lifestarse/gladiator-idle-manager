# Build: 1
"""Tests for hire / train_to / give_item script actions.

These wrap engine APIs (hire_gladiator, upgrade_gladiator, equip_item_on)
and must be no-ops when preconditions fail (invalid input, no gold,
fighter not in roster, etc).
"""
import pytest

import game.models as _m
from game.engine import GameEngine
from game.models import Fighter
from game.scripting import (
    Program, Interpreter, Action, Const, LocalVar, ForEach,
)


@pytest.fixture
def eng(tmp_save_path):
    return GameEngine(save_path=tmp_save_path)


def _run(body, engine):
    Interpreter(engine, Program(name="t", body=body)).run()


# ---------- hire ----------

def test_hire_creates_fighter_of_class(eng):
    eng.gold = 10**6
    eng.fighters = []
    _run([Action("hire", [Const("berserker")])], eng)
    assert len(eng.fighters) == 1
    assert eng.fighters[0].fighter_class == "berserker"


def test_hire_each_class(eng):
    """All six valid classes can be hired."""
    eng.gold = 10**9
    eng.fighters = []
    for cls_id in ("mercenary", "assassin", "tank", "berserker", "retiarius", "medicus"):
        _run([Action("hire", [Const(cls_id)])], eng)
    classes = {f.fighter_class for f in eng.fighters}
    assert classes == {"mercenary", "assassin", "tank", "berserker", "retiarius", "medicus"}


def test_hire_invalid_class_no_op(eng):
    eng.gold = 10**6
    eng.fighters = []
    _run([Action("hire", [Const("not_a_class")])], eng)
    assert eng.fighters == []


def test_hire_non_string_no_op(eng):
    eng.gold = 10**6
    eng.fighters = []
    _run([Action("hire", [Const(42)])], eng)
    assert eng.fighters == []


def test_hire_no_gold_no_op(eng):
    """First hire is free (cost=0 with empty roster); second needs gold."""
    eng.gold = 0
    eng.fighters = []
    _run([Action("hire", [Const("mercenary")])], eng)  # free
    n_after_free = len(eng.fighters)
    eng.gold = 0
    _run([Action("hire", [Const("mercenary")])], eng)  # should no-op
    assert len(eng.fighters) == n_after_free


# ---------- train_to ----------

def test_train_to_levels_fighter_up(eng):
    eng.gold = 10**9
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    _run([
        ForEach("f", "fighters", body=[
            Action("train_to", [LocalVar("f"), Const(10)]),
        ]),
    ], eng)
    assert f.level >= 10


def test_train_to_idempotent_when_at_or_above_target(eng):
    """Already at level 15 with target 10 — no gold spent."""
    eng.gold = 10**9
    f = Fighter(fighter_class="mercenary")
    f.level = 15
    eng.fighters = [f]
    gold_before = eng.gold
    _run([
        ForEach("f", "fighters", body=[
            Action("train_to", [LocalVar("f"), Const(10)]),
        ]),
    ], eng)
    assert f.level == 15
    assert eng.gold == gold_before


def test_train_to_stops_on_no_gold(eng):
    eng.gold = 0
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    _run([
        ForEach("f", "fighters", body=[
            Action("train_to", [LocalVar("f"), Const(50)]),
        ]),
    ], eng)
    assert f.level < 50


def test_train_to_invalid_target_no_op(eng):
    """Negative or non-numeric target — no-op, no level change."""
    eng.gold = 10**9
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    lv_before = f.level
    _run([
        ForEach("f", "fighters", body=[
            Action("train_to", [LocalVar("f"), Const(-5)]),
        ]),
    ], eng)
    assert f.level == lv_before


# ---------- give_item ----------

def test_give_item_equips_valid_id(eng):
    eng.gold = 10**9
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    item_id = next(it["id"] for it in _m.ALL_FORGE_ITEMS if it["slot"] == "weapon")
    _run([
        ForEach("f", "fighters", body=[
            Action("give_item", [LocalVar("f"), Const(item_id)]),
        ]),
    ], eng)
    assert f.equipment["weapon"] is not None
    assert f.equipment["weapon"]["id"] == item_id


def test_give_item_invalid_id_no_op(eng):
    eng.gold = 10**9
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    _run([
        ForEach("f", "fighters", body=[
            Action("give_item", [LocalVar("f"), Const("not_a_real_id")]),
        ]),
    ], eng)
    assert all(v is None for v in f.equipment.values())


def test_give_item_empty_string_no_op(eng):
    eng.gold = 10**9
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    _run([
        ForEach("f", "fighters", body=[
            Action("give_item", [LocalVar("f"), Const("")]),
        ]),
    ], eng)
    assert all(v is None for v in f.equipment.values())


def test_give_item_no_gold_no_op(eng):
    eng.gold = 0
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    item_id = next(it["id"] for it in _m.ALL_FORGE_ITEMS if it["slot"] == "weapon")
    _run([
        ForEach("f", "fighters", body=[
            Action("give_item", [LocalVar("f"), Const(item_id)]),
        ]),
    ], eng)
    assert f.equipment["weapon"] is None


def test_give_item_each_slot(eng):
    """All four slots can be filled via give_item."""
    eng.gold = 10**9
    f = Fighter(fighter_class="mercenary")
    eng.fighters = [f]
    for slot in ("weapon", "armor", "accessory", "relic"):
        item_id = next(
            (it["id"] for it in _m.ALL_FORGE_ITEMS if it["slot"] == slot),
            None,
        )
        if item_id is None:
            continue
        _run([
            ForEach("f", "fighters", body=[
                Action("give_item", [LocalVar("f"), Const(item_id)]),
            ]),
        ], eng)
        assert f.equipment[slot] is not None, f"slot {slot} not filled"


# ---------- combined / palette spec ----------

def test_actions_registered_in_builtins():
    """Palette discovery: all three new actions appear in BUILTIN_ACTIONS
    so the script editor's Add-Block menu surfaces them."""
    from game.scripting.builtins import BUILTIN_ACTIONS
    assert "hire" in BUILTIN_ACTIONS
    assert "train_to" in BUILTIN_ACTIONS
    assert "give_item" in BUILTIN_ACTIONS
