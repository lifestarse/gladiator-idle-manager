# Build: 1
"""Save / load roundtrip tests — most critical because bad migration
destroyed a real save once (see feedback_never_touch_real_save memory).
"""
import json
import os


def test_empty_save_loads_clean(engine):
    """A freshly-constructed engine saves and the file is valid JSON."""
    engine.save()
    assert os.path.exists(engine.SAVE_PATH)
    with open(engine.SAVE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema_version"] == 1


def test_roundtrip_preserves_scalars(engine, tmp_save_path):
    """gold/wins/tier/diamonds survive a save → new engine → load cycle."""
    from game.engine import GameEngine
    engine.gold = 54321
    engine.wins = 42
    engine.arena_tier = 5
    engine.diamonds = 7
    engine.save()

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.gold == 54321
    assert eng2.wins == 42
    assert eng2.arena_tier == 5
    assert eng2.diamonds == 7


def test_multiple_roundtrips_stable(engine, tmp_save_path):
    """3 save/load cycles don't drift any value (prevents silent corruption)."""
    from game.engine import GameEngine
    engine.gold = 99999
    engine.wins = 17
    for _ in range(3):
        engine.save()
        engine = GameEngine(save_path=tmp_save_path)
        engine.load()
    assert engine.gold == 99999
    assert engine.wins == 17


def test_fighters_roundtrip(engine, tmp_save_path):
    """Hiring a fighter, saving, loading preserves the fighter."""
    from game.engine import GameEngine
    engine.gold = 100000  # ensure hire_cost is covered
    initial_count = len(engine.fighters)
    engine.hire_gladiator("mercenary")
    assert len(engine.fighters) == initial_count + 1
    new_fighter_name = engine.fighters[-1].name

    engine.save()
    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert len(eng2.fighters) == initial_count + 1
    assert eng2.fighters[-1].name == new_fighter_name


def test_save_creates_backup(engine):
    """Second save should produce a .bak of the prior save."""
    engine.gold = 100
    engine.save()
    engine.gold = 200
    engine.save()
    assert os.path.exists(engine.SAVE_PATH + ".bak")
    with open(engine.SAVE_PATH + ".bak", "r", encoding="utf-8") as f:
        bak = json.load(f)
    assert bak["gold"] == 100


def test_load_survives_utf8_save_written_externally(tmp_save_path):
    """Regression: an external editor (or a Python script using the templates
    factory) that writes the save file with ``ensure_ascii=False`` and real
    UTF-8 bytes must not make the next engine.load() silently fall back to .bak.

    Before the encoding='utf-8' fix in persistencereadmixin.py, on Windows
    open() defaulted to cp1252, and any byte outside Latin-1 (0x81, 0x8D,
    0x8F, 0x90, 0x9D — which the byte sequence for the Russian letter 'я'
    contains as 0x8F) would raise UnicodeDecodeError, get caught by the
    "corrupt save" handler, and the engine would load the .bak instead —
    silently losing every program with a non-ASCII name.
    """
    from game.engine import GameEngine
    from game.scripting.ast_nodes import (
        Program, Trigger, ForEach, Action, BinOp, Const,
        FighterField, LocalVar,
    )

    # 1) Build a save dict with a Russian program name + run it through the
    #    real AST serializer so the structure matches what the engine expects.
    prog = Program(
        name="активация готовых",   # contains 'я' → byte 0x8F in UTF-8
        trigger=Trigger.ON_BATTLE_END,
        body=[
            ForEach(
                var_name="f", source="fighters",
                where=BinOp(">=", FighterField(LocalVar("f"), "stamina"), Const(100)),
                body=[Action("activate", [LocalVar("f")])],
            ),
        ],
    )
    raw_save = {
        "schema_version": 1,
        "gold": 0, "diamonds": 0, "wins": 0, "arena_tier": 1,
        "fighters": [],
        "inventory": [],
        "shards": {},
        "scripts": {
            "programs": [prog.to_dict()],
            "g_vars": {"_examples_seeded": True},
        },
    }

    # 2) Write it EXTERNALLY with ensure_ascii=False (real UTF-8 bytes, like
    #    a hand-edited file or a third-party tool would produce).
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        json.dump(raw_save, f, ensure_ascii=False, indent=2)

    # 3) Engine must read it back without falling through to .bak (which
    #    doesn't even exist here — if the fix regressed, the test would fail
    #    with "no fighters" because the missing-file branch would fire).
    eng = GameEngine(save_path=tmp_save_path)
    eng.load()
    assert len(eng.scripts.programs) == 1, (
        "engine.load() lost the program — likely fell back to .bak because "
        "UTF-8 save couldn't be decoded under the platform's default locale"
    )
    assert eng.scripts.programs[0].name == "активация готовых"
    # AST must be intact too, not just the name
    body = eng.scripts.programs[0].body
    assert len(body) == 1
    assert isinstance(body[0], ForEach)
    assert body[0].body[0].name == "activate"
