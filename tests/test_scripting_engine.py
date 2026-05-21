# Build: 1
"""Engine integration tests: scripts manager wired into GameEngine.

These touch the real engine (via the `engine` fixture which uses tmp_save_path),
exercising battle_end + idle_tick triggers and save/load round-trip.
"""
from game.scripting import (
    Program, Trigger, Action, Assign, BinOp, Const, GlobalVar,
    ForEach, FighterField, LocalVar, If,
)


def test_engine_has_scripts_manager(engine):
    assert hasattr(engine, "scripts")
    # Fresh engine seeds the built-in "bench tired" example program.
    assert any(p.name == "bench tired" for p in engine.scripts.programs)


def test_battle_end_fires_script(engine):
    engine.gold = 99999
    while len(engine.fighters) < 2:
        engine.hire_gladiator("mercenary")

    # Bench-tired rule: fatigue>=80 → bench.
    engine.scripts.add_program(Program(
        name="bench tired",
        trigger=Trigger.ON_BATTLE_END,
        body=[ForEach("f", "fighters",
                      where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(80)),
                      body=[Action("bench", [LocalVar("f")])])],
    ))

    f0 = engine.fighters[0]
    # Set high enough that even after the stamina/fatigue handler's
    # FATIGUE_RECOVERY_PER_REST (20) decrement on a skipped battle, it
    # still meets the threshold.
    f0.fatigue = 100
    engine.fighters[1].fatigue = 0

    # Synthetic battle_end emit
    class _R:
        player_fighters = [engine.fighters[1]]
    engine._emit_battle_end(_R())

    assert f0.is_active is False
    assert engine.fighters[1].is_active is True


def test_on_tick_via_idle_tick(engine):
    engine.scripts.add_program(Program(
        name="counter",
        trigger=Trigger.ON_TICK,
        tick_interval=2,
        body=[Assign("global", "n", BinOp("+", GlobalVar("n"), Const(1)))],
        g_var_init={"n": 0},
    ))
    engine.idle_tick(1.0)
    assert engine.scripts.g_vars.get("n", 0) == 0
    engine.idle_tick(1.5)
    assert engine.scripts.g_vars["n"] == 1
    engine.idle_tick(2.0)
    assert engine.scripts.g_vars["n"] == 2


def test_save_load_round_trip(engine, tmp_save_path):
    # Drop the seeded example so we test only the user-added program.
    engine.scripts.programs.clear()
    engine.scripts.add_program(Program(
        name="p1",
        trigger=Trigger.ON_BATTLE_END,
        body=[Action("log", [Const("hi")])],
    ))
    engine.scripts.g_vars["wins"] = 5
    engine.save()

    from game.engine import GameEngine
    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    # Seed flag is persisted, so no example reseeding on load.
    assert [p.name for p in eng2.scripts.programs] == ["p1"]
    assert eng2.scripts.g_vars.get("wins") == 5


def test_legacy_save_no_scripts_key(engine, tmp_save_path):
    """Old saves without `scripts` key must load with the seeded example
    (legacy player gets the built-in helper too on first migrated launch)."""
    engine.save()
    # Strip scripts key from disk
    import json
    with open(tmp_save_path) as f:
        data = json.load(f)
    data.pop("scripts", None)
    with open(tmp_save_path, "w") as f:
        json.dump(data, f)

    from game.engine import GameEngine
    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert any(p.name == "bench tired" for p in eng2.scripts.programs)
    assert eng2.scripts.g_vars.get("_examples_seeded") is True


def test_one_bad_program_does_not_break_others(engine):
    engine.gold = 99999
    while len(engine.fighters) < 1:
        engine.hire_gladiator("mercenary")

    engine.scripts.add_program(Program(
        name="bad", trigger=Trigger.ON_BATTLE_END,
        body=[Assign("local", "x", BinOp("/", Const(1), Const(0)))],
    ))
    engine.scripts.add_program(Program(
        name="good", trigger=Trigger.ON_BATTLE_END,
        body=[ForEach("f", "fighters", body=[Action("bench", [LocalVar("f")])])],
    ))

    f = engine.fighters[0]

    class _R:
        player_fighters = [f]
    engine._emit_battle_end(_R())

    assert f.is_active is False
    assert any("bad" in k for k in engine.scripts.last_errors)
