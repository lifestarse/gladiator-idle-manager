# Build: 1
"""ScriptManager tests: trigger dispatch, persistence, error isolation."""
import pytest

from game.scripting import (
    Program, Trigger, ScriptManager,
    Action, Assign, BinOp, Const, GlobalVar, ForEach, FighterField, LocalVar, If,
)


class FakeFighter:
    def __init__(self, name, is_active=True, fatigue=0, hp=100, max_hp=100):
        self.name = name
        self.is_active = is_active
        self.fatigue = fatigue
        self.hp = hp
        self.max_hp = max_hp
        self.injuries = []
        self.alive = True
        self.level = 1
        self.strength = 5
        self.agility = 5
        self.vitality = 5
        self.stamina = 100
        self.fighter_class = "mercenary"

    @property
    def is_exhausted(self):
        return self.fatigue >= 100

    @property
    def available(self):
        return self.is_active and not self.is_exhausted and self.alive


class FakeEngine:
    def __init__(self, fighters=None):
        self.fighters = fighters or []
        self.gold = 0
        self.diamonds = 0
        self.victories = 0
        self.current_tier = 1
        self.current_floor = 1
        self.battle_active = False
        self.expedition_active = False


def test_round_trip_save_load():
    m = ScriptManager()
    m.add_program(Program(
        name="bench tired",
        body=[ForEach("f", "fighters",
                      body=[Action("bench", [LocalVar("f")])],
                      where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(80)))],
    ))
    m.g_vars["counter"] = 7
    d = m.to_dict()
    m2 = ScriptManager.from_dict(d)
    assert len(m2.programs) == 1
    assert m2.programs[0].name == "bench tired"
    assert m2.g_vars["counter"] == 7
    assert m2.to_dict() == d


def test_legacy_save_no_scripts_key():
    m = ScriptManager.from_dict(None)
    assert m.programs == []
    assert m.g_vars == {}
    m2 = ScriptManager.from_dict({})
    assert m2.programs == []


def test_corrupt_program_skipped_on_load():
    m = ScriptManager.from_dict({"programs": [
        {"name": "ok", "trigger": "on_demand", "enabled": True,
         "tick_interval": 5, "g_var_init": {}, "body": []},
        {"name": "bad", "trigger": "lol", "enabled": True},  # bad trigger
    ]})
    assert len(m.programs) == 1
    assert m.programs[0].name == "ok"


def test_on_battle_end_runs_only_battle_programs():
    m = ScriptManager()
    f = FakeFighter("a", fatigue=90)
    e = FakeEngine([f])
    m.add_program(Program("p1", trigger=Trigger.ON_BATTLE_END, body=[
        ForEach("f", "fighters",
                body=[Action("bench", [LocalVar("f")])],
                where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(80))),
    ]))
    m.add_program(Program("p2", trigger=Trigger.ON_DEMAND, body=[
        Action("activate", [LocalVar("f")])  # would crash, no f local
    ]))
    m.on_battle_end(e)
    assert f.is_active is False


def test_disabled_program_skipped():
    m = ScriptManager()
    f = FakeFighter("a", fatigue=90)
    e = FakeEngine([f])
    m.add_program(Program("p", trigger=Trigger.ON_BATTLE_END, enabled=False, body=[
        ForEach("f", "fighters", body=[Action("bench", [LocalVar("f")])]),
    ]))
    m.on_battle_end(e)
    assert f.is_active is True


def test_on_tick_respects_interval():
    m = ScriptManager()
    e = FakeEngine()
    m.add_program(Program("p", trigger=Trigger.ON_TICK, tick_interval=5, body=[
        Assign("global", "n", BinOp("+", GlobalVar("n"), Const(1))),
    ], g_var_init={"n": 0}))
    m.on_tick(e, dt=1.0)
    m.on_tick(e, dt=1.0)
    m.on_tick(e, dt=1.0)
    m.on_tick(e, dt=1.0)
    assert m.g_vars.get("n", 0) == 0  # 4s elapsed, no fire yet
    m.on_tick(e, dt=1.5)
    assert m.g_vars["n"] == 1  # 5.5s → fired
    m.on_tick(e, dt=5.5)
    assert m.g_vars["n"] == 2


def test_run_on_demand_runs_disabled():
    m = ScriptManager()
    e = FakeEngine()
    m.add_program(Program("manual", trigger=Trigger.ON_DEMAND, enabled=False, body=[
        Action("log", [Const("hi")]),
    ]))
    e.events = []
    e.log_event = lambda msg: e.events.append(msg)
    err = m.run_on_demand(e, "manual")
    assert err is None
    assert e.events == ["hi"]


def test_error_isolated_per_program():
    m = ScriptManager()
    f = FakeFighter("a", fatigue=90)
    e = FakeEngine([f])
    # First program: divide by zero (will fail)
    m.add_program(Program("bad", trigger=Trigger.ON_BATTLE_END, body=[
        Assign("local", "r", BinOp("/", Const(1), Const(0))),
    ]))
    # Second program: should still bench
    m.add_program(Program("good", trigger=Trigger.ON_BATTLE_END, body=[
        ForEach("f", "fighters",
                body=[Action("bench", [LocalVar("f")])],
                where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(80))),
    ]))
    m.on_battle_end(e)
    assert f.is_active is False
    assert "bad" in str(m.last_errors)


def test_move_program_reorders():
    m = ScriptManager()
    m.add_program(Program("a"))
    m.add_program(Program("b"))
    m.add_program(Program("c"))
    m.move_program(2, -1)
    assert [p.name for p in m.programs] == ["a", "c", "b"]
    m.move_program(0, 1)
    assert [p.name for p in m.programs] == ["c", "a", "b"]
    # out of range → no change
    m.move_program(0, -1)
    m.move_program(2, 1)
    assert [p.name for p in m.programs] == ["c", "a", "b"]


def test_remove_program():
    m = ScriptManager()
    m.add_program(Program("a"))
    m.add_program(Program("b"))
    m.remove_program(0)
    assert [p.name for p in m.programs] == ["b"]


def test_seed_examples_first_call_adds_program():
    m = ScriptManager()
    added = m.seed_examples_if_needed()
    assert added is True
    assert any(p.name == "bench tired" for p in m.programs)


def test_seed_examples_idempotent():
    m = ScriptManager()
    m.seed_examples_if_needed()
    n_before = len(m.programs)
    again = m.seed_examples_if_needed()
    assert again is False
    assert len(m.programs) == n_before


def test_seed_example_benches_tired_fighter():
    """The example program must actually bench fatigued fighters when fired."""
    m = ScriptManager()
    m.seed_examples_if_needed()

    f_tired = FakeFighter("tired", fatigue=85)
    f_fresh = FakeFighter("fresh", fatigue=10)
    e = FakeEngine([f_tired, f_fresh])
    m.on_battle_end(e)

    assert f_tired.is_active is False
    assert f_fresh.is_active is True


def test_export_then_import_single_program_roundtrip():
    m = ScriptManager()
    m.add_program(Program(
        name="x", body=[Action("log", [Const("hi")])],
    ))
    text = m.export_program_json(0)
    m2 = ScriptManager()
    err = m2.import_program_json(text)
    assert err is None
    assert len(m2.programs) == 1
    assert m2.programs[0].name == "x"


def test_import_program_rejects_garbage():
    m = ScriptManager()
    assert "invalid JSON" in m.import_program_json("not json{{{")
    assert "program payload" in m.import_program_json('{"hello": "world"}')


def test_import_program_accepts_raw_dict():
    """User pastes just the inner program dict — still valid."""
    p = Program(name="y", body=[Action("log", [Const("hi")])])
    import json
    text = json.dumps(p.to_dict())
    m = ScriptManager()
    assert m.import_program_json(text) is None
    assert m.programs[0].name == "y"


def test_export_all_then_import_replaces():
    src = ScriptManager()
    src.add_program(Program("a"))
    src.add_program(Program("b"))
    src.g_vars["counter"] = 9
    bundle = src.export_all_json()

    dst = ScriptManager()
    dst.add_program(Program("OLD"))
    dst.g_vars["counter"] = 1
    dst.g_vars["other"] = 7
    err = dst.import_all_json(bundle, replace=True)
    assert err is None
    assert [p.name for p in dst.programs] == ["a", "b"]
    assert dst.g_vars == {"counter": 9}


def test_import_all_merge_mode_keeps_existing_globals():
    src = ScriptManager()
    src.add_program(Program("imported"))
    src.g_vars["counter"] = 9  # source value
    bundle = src.export_all_json()

    dst = ScriptManager()
    dst.add_program(Program("local"))
    dst.g_vars["counter"] = 1  # existing — must NOT be overwritten in merge mode
    err = dst.import_all_json(bundle, replace=False)
    assert err is None
    assert [p.name for p in dst.programs] == ["local", "imported"]
    assert dst.g_vars["counter"] == 1


def test_import_all_rejects_wrong_kind():
    m = ScriptManager()
    err = m.import_all_json('{"kind":"something_else","programs":[]}')
    assert "bundle" in err


def test_seed_flag_survives_round_trip():
    m = ScriptManager()
    m.seed_examples_if_needed()
    # User deletes the seeded program — but the flag must persist so it
    # does not come back on next launch.
    m.programs.clear()
    d = m.to_dict()
    m2 = ScriptManager.from_dict(d)
    re_added = m2.seed_examples_if_needed()
    assert re_added is False
    assert m2.programs == []
