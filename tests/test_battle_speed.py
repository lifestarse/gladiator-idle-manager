# Build: 1
"""Battle-speed preference gate — the arena x1/x2/x4 toggle persists on the
engine like sound_volume. Guards the clamp: a tampered save writing an
arbitrary multiplier would race the battle Clock (interval → ~0), so any
value outside BATTLE_SPEED_OPTIONS must snap back to 1.
"""
import json

import pytest

from game.constants import BATTLE_AUTO_INTERVAL, BATTLE_SPEED_OPTIONS
from game.models import Fighter


@pytest.fixture
def fighting_engine(engine):
    """Engine with a live fighter and a staged wave, mid-battle.

    A bare GameEngine has an empty roster and no preview enemies, so
    start_auto_battle() short-circuits on "no fighters" and never leaves
    the battle active — same setup shape as test_perk_effects.
    """
    engine.fighters.append(Fighter(fighter_class="mercenary"))
    engine._spawn_enemy()
    engine.start_auto_battle()
    assert engine.battle_active, "fixture must leave a battle running"
    return engine


def test_default_battle_speed_is_x1(engine):
    assert engine.battle_speed == 1


def test_battle_speed_roundtrip(engine, tmp_save_path):
    from game.engine import GameEngine
    engine.battle_speed = 4
    engine.save()

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.battle_speed == 4


@pytest.mark.parametrize("bad", [0, 3, -1, 999, "fast", None])
def test_battle_speed_clamps_invalid_saves(engine, tmp_save_path, bad):
    """Values outside BATTLE_SPEED_OPTIONS (or non-ints) snap back to 1."""
    from game.engine import GameEngine
    engine.save()
    with open(tmp_save_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["battle_speed"] = bad
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.battle_speed == 1, (
        f"battle_speed={bad!r} in the save must snap to 1, "
        f"got {eng2.battle_speed!r}"
    )


def test_battle_speed_missing_key_defaults_to_x1(engine, tmp_save_path):
    """Old saves (no battle_speed key) load with the x1 default."""
    from game.engine import GameEngine
    engine.save()
    with open(tmp_save_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("battle_speed", None)
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.battle_speed == 1


def test_flee_forfeits_gold_banked_during_the_battle(fighting_engine):
    """STOP must not be a risk-free exploit.

    award_gold pays out per kill as the battle runs, so before the forfeit
    a player could clear most of a wave, flee on the losing turn and keep
    the purse. Fleeing costs exactly what the fight had banked.

    gold_earned is set directly rather than fought for: which enemy dies on
    which turn is RNG, and this gate is about the forfeit arithmetic, not
    about combat resolution (that is test_battle_determinism's job).
    """
    engine = fighting_engine
    engine.gold = 1000
    engine.battle_mgr.state.gold_earned = 250

    assert engine.stop_auto_battle() is True
    assert engine.gold == 750
    assert engine.last_flee_forfeit == 250
    assert not engine.battle_active


def test_flee_with_no_kills_costs_nothing(fighting_engine):
    """Fleeing turn one — nothing banked, nothing forfeited."""
    engine = fighting_engine
    engine.gold = 500
    engine.battle_mgr.state.gold_earned = 0

    assert engine.stop_auto_battle() is True
    assert engine.gold == 500
    assert engine.last_flee_forfeit == 0


def test_flee_never_drives_gold_negative(fighting_engine):
    """A forfeit larger than the purse floors at zero, never goes negative.

    Reachable in real play: gold banked from kills can be spent mid-battle
    on the arena heal button before the player flees.
    """
    engine = fighting_engine
    engine.gold = 40
    engine.battle_mgr.state.gold_earned = 300

    engine.stop_auto_battle()
    assert engine.gold == 0
    assert engine.last_flee_forfeit == 40, (
        "reported cost must be what the player actually lost, not the "
        "uncapped forfeit"
    )


def test_speed_options_produce_sane_intervals():
    """Every allowed multiplier yields a positive, ordered turn interval."""
    intervals = [BATTLE_AUTO_INTERVAL / s for s in BATTLE_SPEED_OPTIONS]
    assert all(iv > 0 for iv in intervals)
    assert intervals == sorted(intervals, reverse=True), (
        "BATTLE_SPEED_OPTIONS must be ascending so the arena button cycle "
        "x1 -> x2 -> x4 shortens the interval each step"
    )
