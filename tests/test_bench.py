# Build: 2
"""Bench/active state — toggle, arena exclusion, battle_end event, save migration."""
import random


def test_default_active():
    from game.models import Fighter
    f = Fighter()
    assert f.is_active is True
    assert f.available is True


def test_toggle_bench_blocks_available():
    from game.models import Fighter
    f = Fighter()
    f.is_active = False
    assert f.available is False
    f.is_active = True
    assert f.available is True


def test_arena_skips_benched(engine):
    engine.gold = 99999
    while len(engine.fighters) < 2:
        engine.hire_gladiator("mercenary")
    engine.fighters[0].is_active = False
    engine._spawn_enemy()
    # Enemy count tracks number of *available* fighters, not roster size.
    assert len(engine.preview_enemies) == 1
    engine.start_auto_battle()
    assert engine.fighters[0] not in engine.battle_mgr.state.player_fighters
    assert engine.fighters[1] in engine.battle_mgr.state.player_fighters


def test_skipped_battle_event_fires(engine):
    engine.gold = 99999
    while len(engine.fighters) < 2:
        engine.hire_gladiator("mercenary")
    benched = engine.fighters[0]
    fighter = engine.fighters[1]
    benched.is_active = False

    received = []
    engine.subscribe_battle_end(
        lambda result, participants, skipped: received.append((result, participants, skipped))
    )

    random.seed(7)
    engine._spawn_enemy()
    engine.start_auto_battle()
    # Resolve fully — even if it takes many turns or ends in defeat.
    for _ in range(2000):
        if not engine.battle_active:
            break
        engine.battle_next_turn()

    assert len(received) == 1, f"expected 1 battle_end event, got {len(received)}"
    _result, participants, skipped = received[0]
    assert benched in skipped
    assert fighter in participants
    assert benched not in participants


def test_refresh_arena_preview_tracks_active_count(engine):
    engine.gold = 99999
    while len(engine.fighters) < 3:
        engine.hire_gladiator("mercenary")
    engine._spawn_enemy()
    assert len(engine.preview_enemies) == 3
    engine.fighters[0].is_active = False
    engine.fighters[1].is_active = False
    engine.refresh_arena_preview()
    assert len(engine.preview_enemies) == 1
    engine.fighters[0].is_active = True
    engine.refresh_arena_preview()
    assert len(engine.preview_enemies) == 2


def test_refresh_arena_preview_preserves_boss(engine):
    engine.gold = 99999
    engine.hire_gladiator("mercenary")
    engine.spawn_boss_enemy()
    boss = engine.current_enemy
    assert getattr(boss, 'is_boss', False)
    engine.fighters[0].is_active = False
    engine.refresh_arena_preview()
    # Boss preview untouched.
    assert engine.current_enemy is boss
    assert engine.preview_enemies == [boss]


def test_save_load_roundtrip(engine, tmp_save_path):
    engine.gold = 99999
    engine.hire_gladiator("mercenary")
    engine.fighters[0].is_active = False
    engine.save()

    from game.engine import GameEngine
    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.fighters[0].is_active is False
    assert eng2.fighters[0].available is False


def test_save_migration_default_true():
    """Old saves without `is_active` default to True."""
    from game.models import Fighter
    legacy = {
        "name": "Legacy", "fighter_class": "mercenary", "level": 1,
        "strength": 5, "agility": 5, "vitality": 5, "unused_points": 0,
        "alive": True, "hp": 50,
    }
    f = Fighter.from_dict(legacy)
    assert f.is_active is True
    assert f.available is True
