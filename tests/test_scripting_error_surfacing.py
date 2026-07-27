# Build: 1
"""Guard: a failing engine call inside a script action must reach the player.

`Interpreter._exec_Action` wraps every action and re-raises as ScriptError
naming the action; `ScriptManager._run_program` stores that in `last_errors`
and `RunStats.error`, which the Scripts screen renders. That pipeline exists
and works — but every action in `builtins.py` used to wrap its engine call in
`except Exception: pass`, killing the exception one layer *below* it.

The result was indistinguishable from a legitimate no-op: `actions_fired` kept
climbing, `last_errors` stayed empty, and a farm program that failed on every
single iteration looked like one that had simply found nothing to do. The
docstrings in `builtins.py` record two shipped bugs of exactly that shape.

These tests fail if anyone re-adds a swallow.
"""
from __future__ import annotations
import ast as pyast
import pathlib

import pytest

from game.scripting import builtins as builtins_mod
from game.scripting.ast_nodes import Program, Trigger, Action, Const, LocalVar, ForEach
from game.scripting.interpreter import Interpreter, ScriptError
from game.scripting.manager import ScriptManager


class _Boom(RuntimeError):
    """Distinct type so we can assert the *original* error survives the trip."""


class _Fighter:
    def __init__(self):
        self.name = "Vorn"
        self.hp = 100
        self.max_hp = 100
        self.level = 1
        self.alive = True
        self.is_active = True
        self.is_exhausted = False
        self.on_expedition = False
        self.equipment = {"weapon": {"id": "w1"}, "armor": None,
                          "accessory": None, "relic": None}


class _ExplodingEngine:
    """Engine whose every scripted entry point raises.

    Only the methods the actions actually route through are defined — the
    getattr/callable guards in `builtins.py` must still see a callable, so a
    missing attribute would test the wrong thing (guard skip, not propagation).
    """

    def __init__(self):
        self.fighters = [_Fighter()]
        self.gold = 10_000
        self.diamonds = 0
        self.battle_active = False
        self.inventory = [{"id": "inv1", "slot": "weapon", "cost": 10,
                           "upgrade_level": 0}]
        self.event_log = []

    def _explode(self, *_a, **_kw):
        raise _Boom("engine call failed")

    unequip_from_fighter = _explode
    start_auto_battle = _explode
    _spawn_enemy = _explode
    send_on_expedition = _explode
    stop_expedition = _explode
    buy_forge_item = _explode
    equip_from_inventory = _explode
    hire_gladiator = _explode
    upgrade_gladiator = _explode
    equip_item_on = _explode
    upgrade_item = _explode

    def get_expeditions(self):
        return [{"id": "exp1", "shard_tier": 1, "min_level": 1}]

    def get_forge_items(self):
        return [{"id": "f1", "slot": "weapon", "cost": 10, "affordable": True}]


# (action name, args after the implicit fighter) for every action that reaches
# an engine method. Actions with no engine call (bench/activate/log/spawn_boss)
# are out of scope — they have nothing to swallow.
_FIGHTER_ACTIONS = [
    ("unequip_all", []),
    ("unequip_slot", [Const("weapon")]),
    ("equip_best", [Const("weapon")]),
    ("forge_upgrade", [Const("weapon")]),
    ("train_to", [Const(5)]),
    ("give_item", [Const("sword_iron")]),
]

_PLAIN_ACTIONS = [
    ("start_arena_battle", []),
    ("start_expedition", [Const(1)]),
    ("stop_expedition", []),
    ("buy_item", [Const("weapon")]),
    ("buy_best", [Const("weapon")]),
    ("hire", [Const("mercenary")]),
]


def _const_values(args):
    return [a.value for a in args]


@pytest.mark.parametrize("name,args", _FIGHTER_ACTIONS)
def test_fighter_action_propagates_engine_error(name, args):
    """Called directly, the builtin must let the engine's exception out."""
    eng = _ExplodingEngine()
    fn = builtins_mod.BUILTIN_ACTIONS[name]["fn"]
    with pytest.raises(_Boom):
        fn(eng, eng.fighters[0], *_const_values(args))


@pytest.mark.parametrize("name,args", _PLAIN_ACTIONS)
def test_plain_action_propagates_engine_error(name, args):
    eng = _ExplodingEngine()
    fn = builtins_mod.BUILTIN_ACTIONS[name]["fn"]
    with pytest.raises(_Boom):
        fn(eng, *_const_values(args))


def test_interpreter_converts_to_scripterror_naming_the_action():
    """The wrap in _exec_Action is what turns a raw error into a labelled one."""
    eng = _ExplodingEngine()
    prog = Program(name="p", trigger=Trigger.ON_DEMAND,
                   body=[Action("hire", [Const("mercenary")])])
    with pytest.raises(ScriptError) as ei:
        Interpreter(eng, prog).run()
    msg = str(ei.value)
    assert "hire" in msg, f"ScriptError must name the failing action, got: {msg!r}"
    assert "engine call failed" in msg, (
        f"ScriptError must carry the original cause, got: {msg!r}"
    )
    assert isinstance(ei.value.__cause__, _Boom), (
        "the original exception must stay chained for the traceback"
    )


def test_manager_records_the_error_for_the_player():
    """End of the pipeline: what the Scripts screen reads must be populated."""
    eng = _ExplodingEngine()
    mgr = ScriptManager()
    prog = Program(name="farm", trigger=Trigger.ON_DEMAND,
                   body=[Action("hire", [Const("mercenary")])])
    mgr.programs.append(prog)

    returned = mgr.run_program_now(eng, prog)

    assert returned, "run_program_now must return a non-empty error message"
    assert "hire" in returned
    key = mgr._program_key(prog)
    assert mgr.last_errors.get(key), "last_errors must hold the message for the UI"
    assert mgr.last_runs[key].error, "RunStats.error drives the run-log dialog"


def test_error_inside_foreach_still_surfaces():
    """The farm-shaped case: the failure happens inside a loop over fighters."""
    eng = _ExplodingEngine()
    prog = Program(
        name="p", trigger=Trigger.ON_DEMAND,
        body=[ForEach("f", "fighters",
                      body=[Action("unequip_all", [LocalVar("f")])])],
    )
    with pytest.raises(ScriptError) as ei:
        Interpreter(eng, prog).run()
    assert "unequip_all" in str(ei.value)


def test_builtins_declares_no_broad_except():
    """Structural lock: no bare/broad handler may come back into builtins.py.

    Narrow handlers (the `except (TypeError, ValueError)` used for argument
    parsing) are fine and deliberately still allowed.
    """
    src = pathlib.Path(builtins_mod.__file__).read_text(encoding="utf-8")
    offenders = []
    for node in pyast.walk(pyast.parse(src)):
        if not isinstance(node, pyast.ExceptHandler):
            continue
        if node.type is None:
            offenders.append(f"line {node.lineno}: bare `except:`")
        elif isinstance(node.type, pyast.Name) and node.type.id in (
            "Exception", "BaseException",
        ):
            offenders.append(f"line {node.lineno}: `except {node.type.id}`")
    assert not offenders, (
        "builtins.py must not catch broadly — _exec_Action already wraps every "
        "action and ScriptManager surfaces it to the player. Found:\n  "
        + "\n  ".join(offenders)
    )
