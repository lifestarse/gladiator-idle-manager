# Build: 1
"""Auto-split submodule: _enemy.py."""
import random
import time
import math
from collections import namedtuple
from game.constants import (
    FIGHTER_BASE_HP, FIGHTER_HP_PER_VIT, FIGHTER_HP_PER_LEVEL,
    FIGHTER_ATK_PER_STR, FIGHTER_ATK_PER_LEVEL, FIGHTER_STARTING_POINTS,
    CRIT_K, CRIT_MULT_BASE, CRIT_MULT_PER_AGI,
    DODGE_AGI_FACTOR, DODGE_DIMINISH_FACTOR,
    DEATH_CHANCE_BASE, DEATH_CHANCE_CAP,
    DAMAGE_VARIANCE_LOW, DAMAGE_VARIANCE_HIGH, DEFENSE_DIVISOR,
    UPGRADE_BONUS_PER_LEVEL, RELIC_STAT_SPLIT, ACCESSORY_HP_MULT,
    ENEMY_ATK_BASE, ENEMY_ATK_PER_TIER, ENEMY_ATK_EXPO,
    ENEMY_DEF_BASE, ENEMY_DEF_PER_TIER, ENEMY_DEF_EXPO,
    ENEMY_HP_BASE, ENEMY_HP_PER_TIER, ENEMY_HP_EXPO,
    REWARD_BASE, REWARD_EXPO, HIRE_BASE, HIRE_EXPO,
    UPGRADE_COST_BASE, UPGRADE_COST_EXPO,
    HEAL_BASE, HEAL_TIER_MULT, SURGEON_BASE, SURGEON_INFLATION,
    ENEMY_CRIT_CAP, ENEMY_CRIT_BASE, ENEMY_CRIT_PER_TIER,
    ENEMY_DODGE_CAP, ENEMY_DODGE_PER_TIER, ENEMY_CRIT_MULT,
    BOSS_TIER_OFFSET, BOSS_HP_MULT, BOSS_ATK_MULT, BOSS_DEF_MULT,
    BOSS_GOLD_MULT, BOSS_CRIT_BONUS, BOSS_CRIT_MIN,
    INJURY_HEAL_BASE_COST, TONIC_BASE_COST, TONIC_TIER_EXPO, TIER_BAND_MULT,
    MAX_UPGRADE_COMMON, MAX_UPGRADE_UNCOMMON, MAX_UPGRADE_RARE,
    MAX_UPGRADE_EPIC, MAX_UPGRADE_LEGENDARY,
    ROLE_MULT, ROLE_STAT_MULT, STAT_BIAS_MULT,
    PERK_POINT_EVERY_N_LEVELS,
    FIGHTER_CRIT_CAP, FIGHTER_DODGE_CAP,
)
from game.slots import SLOTS, EQUIPMENT_SLOTS  # noqa: E402,F401

from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler
from ._combat import CombatUnit
from ._fighter import Fighter

class Enemy(CombatUnit):
    """Arena opponent with exponential stat growth.

    Enemies get a small crit and dodge chance that scales with tier,
    making high-tier fights unpredictable and dangerous.
    """

    def __init__(self, tier=1):
        self.tier = tier
        title_idx = min(tier - 1, len(ENEMY_TITLES) - 1)
        self.name = ENEMY_TITLES[title_idx]

        atk, defense, hp = DifficultyScaler.enemy_stats(tier)
        self.attack = atk
        self.defense = defense
        self.max_hp = hp
        self.hp = self.max_hp
        self.gold_reward = DifficultyScaler.enemy_reward(tier)

        self.is_boss = False

        # Enemies get luck too — tier-scaling crit/dodge
        self.crit_chance = min(ENEMY_CRIT_CAP, ENEMY_CRIT_BASE + tier * ENEMY_CRIT_PER_TIER)
        self.dodge_chance = min(ENEMY_DODGE_CAP, tier * ENEMY_DODGE_PER_TIER)

    @property
    def crit_mult(self):
        return ENEMY_CRIT_MULT

    @classmethod
    def from_template(cls, template, tier):
        """Create enemy from JSON template with role/bias stat modifiers."""
        enemy = cls.__new__(cls)
        enemy.tier = tier
        enemy.name = template.get("name", ENEMY_TITLES[min(tier - 1, len(ENEMY_TITLES) - 1)])
        enemy.is_boss = False

        base_atk, base_def, base_hp = DifficultyScaler.enemy_stats(tier)
        role = template.get("role", "soldier")
        bias = template.get("stat_bias", "balanced")
        rm = ROLE_MULT.get(role, 1.0)
        rsm = ROLE_STAT_MULT.get(role, {})
        bm = STAT_BIAS_MULT.get(bias, {})

        enemy.attack = int(base_atk * rm * rsm.get("str", 1.0) * bm.get("str", 1.0))
        enemy.defense = int(base_def * rm * rsm.get("agi", 1.0) * bm.get("agi", 1.0))
        enemy.max_hp = int(base_hp * rm * rsm.get("vit", 1.0) * bm.get("vit", 1.0))
        enemy.hp = enemy.max_hp
        enemy.gold_reward = DifficultyScaler.enemy_reward(tier)

        enemy.crit_chance = min(ENEMY_CRIT_CAP, ENEMY_CRIT_BASE + tier * ENEMY_CRIT_PER_TIER)
        enemy.dodge_chance = min(ENEMY_DODGE_CAP, tier * ENEMY_DODGE_PER_TIER)
        return enemy


class Boss(Enemy):
    """Boss enemy — stronger stats, unique name, no dodge."""

    def __init__(self, arena_tier):
        boss_tier = arena_tier + BOSS_TIER_OFFSET
        super().__init__(tier=boss_tier)
        self._apply_boss_multipliers()
        self.name = f"BOSS: {get_boss_name(arena_tier)}"
        self.modifiers = []

    def _apply_boss_multipliers(self):
        self.max_hp = int(self.max_hp * BOSS_HP_MULT)
        self.hp = self.max_hp
        self.attack = int(self.attack * BOSS_ATK_MULT)
        self.defense = int(self.defense * BOSS_DEF_MULT)
        self.gold_reward = int(self.gold_reward * BOSS_GOLD_MULT)
        self.crit_chance = max(BOSS_CRIT_MIN, self.crit_chance + BOSS_CRIT_BONUS)
        self.dodge_chance = 0
        self.is_boss = True

    @classmethod
    def from_template(cls, template, arena_tier):
        """Create boss from JSON template with boss multipliers."""
        boss_tier = arena_tier + BOSS_TIER_OFFSET
        boss = Enemy.from_template(template, boss_tier)
        boss.__class__ = cls
        boss._apply_boss_multipliers()
        boss.name = f"BOSS: {template.get('name', get_boss_name(arena_tier))}"
        boss.modifiers = []
        return boss
