# Build: 3
"""Tests for GameEngine (game/engine.py) — 27 tests."""
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from game.engine import GameEngine, SAVE_PATH
from game.models import Fighter, DifficultyScaler, FORGE_WEAPONS, ENCHANTMENT_TYPES
from game.constants import STARTING_GOLD


# ---- 1. Initial state ----

def test_initial_state(engine):
    assert engine.gold == STARTING_GOLD
    assert engine.fighters == []
    assert engine.arena_tier == 1


# ---- 2. Hire fighter ----

def test_hire_fighter(engine):
    engine.gold = 500
    result = engine.hire_gladiator("mercenary")
    assert result.ok is True
    assert len(engine.fighters) == 1
    assert engine.fighters[0].fighter_class == "mercenary"
    assert engine.gold < 500  # gold was deducted


# ---- 3. Hire cost scales ----

def test_hire_cost_scales(engine):
    engine.gold = 100_000
    engine.hire_gladiator("mercenary")
    cost_1 = engine.hire_cost  # cost for 2nd hire (1 alive)
    engine.hire_gladiator("mercenary")
    cost_2 = engine.hire_cost  # cost for 3rd hire (2 alive)
    assert cost_2 > cost_1


# ---- 4. Hire insufficient gold ----

def test_hire_insufficient_gold(engine):
    engine.gold = 0
    result = engine.hire_gladiator("mercenary")
    assert result.ok is False
    assert result.code == "not_enough_gold"
    assert len(engine.fighters) == 0


# ---- 5. Upgrade fighter ----

def test_upgrade_fighter(engine):
    engine.gold = 100_000
    engine.hire_gladiator("mercenary")
    gold_before = engine.gold
    result = engine.upgrade_gladiator(0)
    assert result.ok is True
    assert engine.fighters[0].level == 2
    assert engine.gold < gold_before


# ---- 6. Distribute stat: strength ----

def test_distribute_stat_strength(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.unused_points = 1
    old_str = f.strength
    result = engine.distribute_stat(0, "strength")
    assert result.ok is True
    assert f.strength == old_str + 1


# ---- 7. Distribute stat: agility ----

def test_distribute_stat_agility(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.unused_points = 1
    old_agi = f.agility
    result = engine.distribute_stat(0, "agility")
    assert result.ok is True
    assert f.agility == old_agi + 1


# ---- 8. Distribute stat: vitality (heals HP gain) ----

def test_distribute_stat_vitality(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.unused_points = 1
    old_hp = f.hp
    old_max = f.max_hp
    result = engine.distribute_stat(0, "vitality")
    assert result.ok is True
    # VIT +1 -> max_hp increases by 8 * hp_mult; hp heals by the gain
    assert f.max_hp > old_max
    assert f.hp >= old_hp


# ---- 9. Distribute stat: no points ----

def test_distribute_no_points(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.unused_points = 0
    result = engine.distribute_stat(0, "strength")
    assert result.ok is False
    assert result.code == "no_points"


# ---- 10. Equip item ----

def test_equip_item(engine, sample_weapon):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    engine.inventory.append(dict(sample_weapon))
    result = engine.equip_from_inventory(0, 0)
    assert result.ok is True
    assert engine.fighters[0].equipment["weapon"] is not None
    assert len(engine.inventory) == 0  # item moved to fighter


# ---- 11. Unequip item ----

def test_unequip_item(engine, sample_weapon):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    engine.inventory.append(dict(sample_weapon))
    engine.equip_from_inventory(0, 0)
    result = engine.unequip_from_fighter(0, "weapon")
    assert result.ok is True
    assert engine.fighters[0].equipment["weapon"] is None
    assert len(engine.inventory) == 1


# ---- 12. Heal fighter ----

def test_heal_fighter(engine):
    engine.gold = 100_000
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.hp = 1  # damage the fighter
    healed, spent = engine.heal_all_hp()
    assert f.hp == f.max_hp
    assert spent > 0


# ---- 13. Heal injury ----

def test_heal_injury(engine):
    engine.gold = 100_000
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.injuries = [{"id": "split_lip"}, {"id": "bruised_ribs"}]
    gold_before = engine.gold
    result = engine.heal_fighter_injury(0)
    assert result.ok is True
    assert f.injury_count == 1
    assert engine.gold < gold_before


# ---- 14. Award gold ----

def test_award_gold(engine):
    engine.gold = 50
    engine.total_gold_earned = 0
    engine.award_gold(200)
    assert engine.gold == 250
    assert engine.total_gold_earned == 200


# ---- 15. Roguelike reset ----

def test_roguelike_reset(engine):
    engine.gold = 5000
    engine.arena_tier = 10
    diamonds_before_setup = engine.diamonds
    engine.achievements_unlocked = ["first_blood"]
    engine.best_record_tier = 5
    engine.hire_gladiator("mercenary")
    engine.inventory.append({"id": "test", "name": "x"})
    diamonds_before = engine.diamonds
    engine.roguelike_reset()
    # Run state wiped
    assert engine.gold == STARTING_GOLD
    assert engine.fighters == []
    assert engine.arena_tier == 1
    assert engine.inventory == []
    # Persistent data kept
    assert engine.diamonds >= diamonds_before  # may gain from achievements
    assert "first_blood" in engine.achievements_unlocked
    assert engine.best_record_tier == 10  # updated to max


# ---- 16. Save/load roundtrip ----

def test_save_load_roundtrip(engine):
    tmp = tempfile.mktemp(suffix=".json")
    try:
        engine.SAVE_PATH = tmp
        # Hire first, then set gold so deduction doesn't affect assertion
        engine.hire_gladiator("assassin")
        engine.gold = 777
        engine.diamonds = 42
        engine.arena_tier = 5
        engine.save()

        engine2 = GameEngine()
        engine2.SAVE_PATH = tmp
        engine2.load()
        assert engine2.gold == 777
        assert engine2.diamonds == 42
        assert engine2.arena_tier == 5
        assert len(engine2.fighters) == 1
        assert engine2.fighters[0].fighter_class == "assassin"
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ---- 17. Handle fighter death: permadeath triggers ----

def test_handle_fighter_death_permadeath(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    with patch("random.random", return_value=0.01):
        # death_chance at 0 injuries = 0.05, random=0.01 < 0.05 => dies
        died, injury_id = engine.handle_fighter_death(f)
    assert died is True
    assert injury_id is None
    assert f.alive is False
    assert engine.total_deaths == 1
    assert len(engine.graveyard) == 1


# ---- 18. Handle fighter death: injury instead ----

def test_handle_fighter_death_injury(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    old_count = f.injury_count
    with patch("random.random", return_value=0.99):
        # death_chance=0.05, random=0.99 > 0.05 => survives, gets injury
        died, injury_id = engine.handle_fighter_death(f)
    assert died is False
    assert injury_id is not None
    assert f.alive is True
    assert f.injury_count == old_count + 1


# ---- 19. Check achievements ----

def test_check_achievements(engine):
    engine.wins = 1  # triggers "first_blood" achievement
    engine.achievements_unlocked = []
    newly = engine.check_achievements()
    ids = [a["id"] for a in newly]
    assert "first_blood" in ids
    assert "first_blood" in engine.achievements_unlocked
    assert engine.diamonds > 0  # diamonds awarded


# ---- 20. Dismiss dead fighter ----

def test_dismiss_dead(engine, sample_weapon):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    # Equip a weapon
    f.equip_item(dict(sample_weapon))
    f.alive = False
    engine.dismiss_dead(0)
    assert len(engine.fighters) == 0
    # Equipment returned to inventory
    assert len(engine.inventory) == 1
    assert engine.inventory[0]["id"] == sample_weapon["id"]


# ---- 21. Enchant weapon success ----

def test_enchant_weapon_success(engine, sample_weapon):
    engine.gold = 200000
    engine.shards = {5: 500}
    weapon = dict(sample_weapon)
    result = engine.enchant_weapon(weapon, "bleeding")
    assert result.ok is True
    assert weapon["enchantment"] == "bleeding"


# ---- 22. Enchant weapon not enough gold ----

def test_enchant_weapon_no_gold(engine, sample_weapon):
    engine.gold = 0
    engine.shards = {5: 500}
    weapon = dict(sample_weapon)
    result = engine.enchant_weapon(weapon, "bleeding")
    assert result.ok is False
    assert weapon.get("enchantment") is None


# ---- 23. Enchant weapon not enough shards ----

def test_enchant_weapon_no_shards(engine, sample_weapon):
    engine.gold = 200000
    engine.shards = {5: 0}
    weapon = dict(sample_weapon)
    result = engine.enchant_weapon(weapon, "bleeding")
    assert result.ok is False
    assert weapon.get("enchantment") is None


# ---- 24. Enchant non-weapon fails ----

def test_enchant_non_weapon_fails(engine, sample_armor):
    engine.gold = 200000
    engine.shards = {5: 500}
    armor = dict(sample_armor)
    result = engine.enchant_weapon(armor, "bleeding")
    assert result.ok is False
    assert armor.get("enchantment") is None


# ---- 25. Unlock perk success ----

def test_unlock_perk_success(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.perk_points = 5
    result = engine.unlock_perk(0, "merc_iron_will")
    assert result.ok is True
    assert "merc_iron_will" in f.unlocked_perks
    assert f.perk_points == 4  # cost 1


# ---- 26. Unlock perk not enough points ----

def test_unlock_perk_no_points(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.perk_points = 0
    result = engine.unlock_perk(0, "merc_iron_will")
    assert result.ok is False
    assert "merc_iron_will" not in f.unlocked_perks


# ---- 27. Unlock cross-class perk costs more ----

def test_unlock_cross_class_perk(engine):
    engine.gold = 500
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.perk_points = 10
    # Unlock assassin perk (cross-class cost = 1 * 2.0 = 2)
    result = engine.unlock_perk(0, "assa_keen_edge")
    assert result.ok is True
    assert "assa_keen_edge" in f.unlocked_perks
    assert f.perk_points == 8  # cost 2 (cross-class)
