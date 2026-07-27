# Build: 3
"""models._scaling — DifficultyScaler: enemy/econ tier curves."""
from ._imports import *  # noqa: F401,F403
# NOTE: do NOT add `from ._helpers import *` here. _helpers imports
# DifficultyScaler at module level, so that would re-create the cycle.
# _scaling needs only game.constants values, which _imports provides.

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
