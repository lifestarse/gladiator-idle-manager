# Build: 1
"""Tests for game models (game/models.py) — 15 tests."""
import math

import pytest

from game.models import (
    Fighter, Enemy, DifficultyScaler, FIGHTER_CLASSES,
)


# ---- 1. Fighter attack formula ----

def test_fighter_attack_formula(fighter_factory):
    f = fighter_factory("mercenary", level=1)
    # Mercenary STR=5, base_attack=0, level=1, no equip
    # attack = STR*2 + base_attack + (level-1)*1 + equip_atk
    assert f.attack == 5 * 2 + 0 + 0 + 0  # 10


# ---- 2. Fighter defense formula ----

def test_fighter_defense_formula(fighter_factory):
    f = fighter_factory("mercenary", level=1)
    # defense = VIT + base_defense + equip_def
    assert f.defense == 5 + 0 + 0  # 5


# ---- 3. Fighter max HP formula ----

def test_fighter_max_hp_formula(fighter_factory):
    f = fighter_factory("mercenary", level=1)
    # max_hp = (30 + VIT*8 + base_hp + (level-1)*5) * hp_mult + equip_hp
    expected = int((30 + 5 * 8 + 0 + 0) * 1.0) + 0  # 70
    assert f.max_hp == expected


# ---- 4. Assassin crit chance ----

def test_assassin_crit_chance(fighter_factory):
    f = fighter_factory("assassin", level=1)
    # AGI=8, crit_bonus=0.20
    # crit_chance = AGI/(AGI+5) + crit_bonus = 8/13 + 0.20
    expected = 8 / (8 + 5) + 0.20
    assert abs(f.crit_chance - expected) < 1e-9


# ---- 5. Tank max HP ----

def test_tank_max_hp(fighter_factory):
    f = fighter_factory("tank", level=1)
    # VIT=10, hp_mult=1.3, base_hp=0, level=1
    # (30 + 10*8 + 0 + 0) * 1.3 = 110 * 1.3 = 143
    expected = int((30 + 10 * 8 + 0 + 0) * 1.3) + 0
    assert f.max_hp == expected  # 143


# ---- 6. Fighter with equipment ----

def test_fighter_with_equipment(fighter_factory, sample_weapon):
    f = fighter_factory("mercenary", level=1)
    base_attack = f.attack
    f.equip_item(dict(sample_weapon))
    assert f.attack == base_attack + sample_weapon["atk"]


# ---- 7. Level up ----

def test_level_up(fighter_factory):
    f = fighter_factory("mercenary", level=1)
    pts_before = f.unused_points
    ppl = f.points_per_level
    f.level_up()
    assert f.level == 2
    assert f.unused_points == pts_before + ppl
    assert f.hp == f.max_hp  # healed to full on level up


# ---- 8. Distribute point ----

def test_distribute_point(fighter_factory):
    f = fighter_factory("mercenary", level=1)
    f.unused_points = 1
    old_str = f.strength
    ok = f.distribute_point("strength")
    assert ok is True
    assert f.strength == old_str + 1
    assert f.unused_points == 0


# ---- 9. Power rating ----

def test_power_rating(fighter_factory):
    f = fighter_factory("mercenary", level=1)
    expected = f.attack + f.defense + f.max_hp // 5
    assert f.power_rating == expected


# ---- 10. Death chance formula ----

def test_death_chance_formula(fighter_factory):
    f = fighter_factory("mercenary", level=1)
    f.injuries = 0
    assert abs(f.death_chance - 0.05) < 1e-9
    f.injuries = 5
    assert abs(f.death_chance - 0.35) < 1e-9
    f.injuries = 20  # capped at 0.60
    assert abs(f.death_chance - 0.60) < 1e-9


# ---- 11. Enemy stats tier 1 ----

def test_enemy_stats_tier1():
    from game.constants import (
        ENEMY_ATK_BASE, ENEMY_ATK_PER_TIER, ENEMY_ATK_EXPO,
        ENEMY_DEF_BASE, ENEMY_DEF_PER_TIER, ENEMY_DEF_EXPO,
        ENEMY_HP_BASE, ENEMY_HP_PER_TIER, ENEMY_HP_EXPO,
    )
    atk, defense, hp = DifficultyScaler.enemy_stats(1)
    expected_atk = int((ENEMY_ATK_BASE + 1 * ENEMY_ATK_PER_TIER) * (ENEMY_ATK_EXPO ** 0))
    expected_def = int((ENEMY_DEF_BASE + 1 * ENEMY_DEF_PER_TIER) * (ENEMY_DEF_EXPO ** 0))
    expected_hp = int((ENEMY_HP_BASE + 1 * ENEMY_HP_PER_TIER) * (ENEMY_HP_EXPO ** 0))
    assert atk == expected_atk
    assert defense == expected_def
    assert hp == expected_hp


# ---- 12. Enemy stats scale with tier ----

def test_enemy_stats_scaling():
    atk1, def1, hp1 = DifficultyScaler.enemy_stats(1)
    atk5, def5, hp5 = DifficultyScaler.enemy_stats(5)
    assert atk5 > atk1
    assert def5 > def1
    assert hp5 > hp1


# ---- 13. Boss stats ----

def test_boss_stats():
    arena_tier = 3
    boss = Enemy.create_boss(arena_tier)
    # Boss uses tier = arena_tier + 2
    base_enemy = Enemy(tier=arena_tier + 2)
    assert boss.max_hp == int(base_enemy.max_hp * 10)
    assert boss.attack == int(base_enemy.attack * 1.5)
    assert boss.defense == int(base_enemy.defense * 1.3)
    assert boss.is_boss is True


# ---- 14. Fighter to_dict / from_dict roundtrip ----

def test_fighter_to_dict_from_dict(fighter_factory, sample_weapon):
    f = fighter_factory("assassin", level=3, name="Kira")
    f.injuries = 2
    f.kills = 7
    f.equip_item(dict(sample_weapon))
    d = f.to_dict()
    f2 = Fighter.from_dict(d)
    assert f2.name == f.name
    assert f2.fighter_class == f.fighter_class
    assert f2.level == f.level
    assert f2.strength == f.strength
    assert f2.agility == f.agility
    assert f2.vitality == f.vitality
    assert f2.injuries == f.injuries
    assert f2.kills == f.kills
    assert f2.equipment["weapon"]["id"] == sample_weapon["id"]
    assert f2.hp == f.hp
    assert f2.alive == f.alive


# ---- 15. Difficulty scaler costs ----

def test_difficulty_scaler_costs():
    # hire_cost = 40 * 1.6^alive
    assert DifficultyScaler.hire_cost(0) == int(40 * 1.6 ** 0)  # 40
    assert DifficultyScaler.hire_cost(1) == int(40 * 1.6 ** 1)  # 64
    assert DifficultyScaler.hire_cost(3) == int(40 * 1.6 ** 3)  # 163

    # upgrade_cost = 35 * 1.45^(level-1)
    assert DifficultyScaler.upgrade_cost(1) == int(35 * 1.45 ** 0)  # 35
    assert DifficultyScaler.upgrade_cost(2) == int(35 * 1.45 ** 1)  # 50
    assert DifficultyScaler.upgrade_cost(5) == int(35 * 1.45 ** 4)  # 154
