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
