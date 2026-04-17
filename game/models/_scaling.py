# Build: 1
"""Auto-split submodule: _scaling.py."""
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

class DifficultyScaler:
    """Roguelike economy: tighter scaling, runs end around tier 10-20.

    Strange math: enemy stats scale steeply so luck (crits, dodge)
    becomes the deciding factor at higher tiers. Raw power alone
    won't carry you — you need agility and fortunate rolls.

    All constants live in game/constants.py.
    """

    @staticmethod
    def enemy_stats(tier):
        atk = int((ENEMY_ATK_BASE + tier * ENEMY_ATK_PER_TIER)
                   * (ENEMY_ATK_EXPO ** (tier - 1)))
        defense = int((ENEMY_DEF_BASE + tier * ENEMY_DEF_PER_TIER)
                       * (ENEMY_DEF_EXPO ** (tier - 1)))
        hp = int((ENEMY_HP_BASE + tier * ENEMY_HP_PER_TIER)
                  * (ENEMY_HP_EXPO ** (tier - 1)))
        return atk, defense, hp

    @staticmethod
    def enemy_reward(tier):
        return int(REWARD_BASE * (REWARD_EXPO ** (tier - 1)))

    @staticmethod
    def hire_cost(alive_count):
        # Cap the exponent at 50 to avoid overflow past fmt_num range
        # (1.6^50 ≈ 9e9 — already billions). Beyond 50 fighters the cost
        # stays flat at endgame-max; the design never anticipated >50.
        return int(HIRE_BASE * (HIRE_EXPO ** min(alive_count, 50)))

    @staticmethod
    def upgrade_cost(level):
        return int(UPGRADE_COST_BASE * (UPGRADE_COST_EXPO ** (level - 1)))

    @staticmethod
    def _tier_band_mult(arena_tier):
        """Get the growth multiplier for a given tier band."""
        for (lo, hi), mult in TIER_BAND_MULT.items():
            if lo <= arena_tier <= hi:
                return mult
        return 1.05  # fallback for beyond T100

    @staticmethod
    def heal_cost(arena_tier):
        """Heal cost with tier-band scaling: steeper early, flatter late."""
        cost = HEAL_BASE
        for t in range(2, arena_tier + 1):
            cost *= DifficultyScaler._tier_band_mult(t)
        return int(cost)

    @staticmethod
    def surgeon_cost(times_used):
        return int(SURGEON_BASE * (SURGEON_INFLATION ** times_used))
