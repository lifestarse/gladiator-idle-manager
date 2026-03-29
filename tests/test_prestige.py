# Build: 1
"""Tests for prestige system (~10 tests)."""
import pytest

from game.prestige import PrestigeManager, PRESTIGE_ARENA_REQUIREMENT, PRESTIGE_REWARDS
from game.constants import STARTING_GOLD


# ---- 1. Cannot prestige below T15 ----

def test_cannot_prestige_below_t15(engine):
    engine.arena_tier = 14
    assert engine.prestige_manager.can_prestige() is False
    result = engine.prestige_manager.do_prestige()
    assert result.ok is False


# ---- 2. Can prestige at T15 ----

def test_can_prestige_at_t15(engine):
    engine.arena_tier = 15
    assert engine.prestige_manager.can_prestige() is True


# ---- 3. Prestige increments level ----

def test_prestige_increments_level(engine):
    engine.arena_tier = 15
    engine.gold = 10000
    before = engine.prestige_level
    engine.prestige_manager.do_prestige()
    assert engine.prestige_level == before + 1


# ---- 4. Prestige preserves diamonds ----

def test_prestige_preserves_diamonds(engine):
    engine.arena_tier = 15
    engine.diamonds = 500
    engine.prestige_manager.do_prestige()
    assert engine.diamonds == 500


# ---- 5. Stat bonus calculation ----

def test_stat_bonus_calculation(engine):
    engine.prestige_level = 0
    assert engine.prestige_manager.get_stat_bonus() == 1.0
    engine.prestige_level = 5
    assert abs(engine.prestige_manager.get_stat_bonus() - 1.10) < 0.001
    engine.prestige_level = 10
    assert abs(engine.prestige_manager.get_stat_bonus() - 1.20) < 0.001


# ---- 6. Prestige resets gold ----

def test_prestige_resets_gold(engine):
    engine.arena_tier = 15
    engine.gold = 50000
    engine.prestige_manager.do_prestige()
    assert engine.gold == STARTING_GOLD


# ---- 7. Prestige resets inventory ----

def test_prestige_resets_inventory(engine):
    engine.arena_tier = 15
    engine.inventory = [{"id": "test", "name": "Test"}]
    engine.prestige_manager.do_prestige()
    assert engine.inventory == []


# ---- 8. Prestige unlocks ----

def test_prestige_unlocks(engine):
    engine.prestige_level = 0
    assert engine.prestige_manager.is_unlocked("mutators") is False
    engine.prestige_level = 1
    assert engine.prestige_manager.is_unlocked("mutators") is True
    engine.prestige_level = 5
    assert engine.prestige_manager.is_unlocked("class_berserker") is True
    assert engine.prestige_manager.is_unlocked("mutator_slot_2") is True


# ---- 9. Prestige saves prestige_level ----

def test_prestige_saves(engine):
    engine.arena_tier = 15
    engine.prestige_manager.do_prestige()
    assert engine.prestige_level == 1
    # After reset, prestige_level should still be 1
    save_data = engine.save()
    assert save_data["prestige_level"] == 1


# ---- 10. Prestige stat bonus applied to fighters ----

def test_prestige_stat_bonus_applied(engine):
    engine.arena_tier = 15
    engine.prestige_manager.do_prestige()
    # After prestige, hire a fighter — should have prestige bonus
    engine.gold = 10000
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    expected_bonus = engine.prestige_manager.get_stat_bonus()
    assert f.prestige_bonus == expected_bonus
    assert f.prestige_bonus > 1.0
