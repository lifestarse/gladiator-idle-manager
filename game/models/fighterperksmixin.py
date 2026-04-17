# Build: 1
"""Fighter _FighterPerksMixin."""
# Build: 1
"""Auto-split submodule: _fighter.py."""
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
from ._data import FIGHTER_NAMES, FIGHTER_CLASSES


class _FighterPerksMixin:
    def get_perk_effects(self, effect_type):
        """Sum all unlocked perk effect values of given type, including passive."""
        total = 0.0
        cls_data = FIGHTER_CLASSES.get(self.fighter_class, {})
        # Passive ability (always active)
        passive = cls_data.get("passive_ability")
        if passive:
            eff = passive.get("effect", {})
            if eff.get("type") == effect_type:
                total += eff.get("value", 0)
        # Unlocked perks
        all_perks = self._get_all_perks_map()
        for pid in self.unlocked_perks:
            perk = all_perks.get(pid)
            if perk:
                eff = perk.get("effect", {})
                if eff.get("type") == effect_type:
                    total += eff.get("value", 0)
        return total

    def get_active_skill(self):
        """Return the active skill definition dict for this fighter's class, or None."""
        cls_data = FIGHTER_CLASSES.get(self.fighter_class, {})
        return cls_data.get("active_skill")

    def get_perk_effect_data(self, effect_type):
        """Get full effect dict for a perk effect type (for max_stacks etc)."""
        all_perks = self._get_all_perks_map()
        for pid in self.unlocked_perks:
            perk = all_perks.get(pid)
            if perk:
                eff = perk.get("effect", {})
                if eff.get("type") == effect_type:
                    return eff
        return None

    @classmethod
    def invalidate_perks_map_cache(cls):
        """Call after reloading FIGHTER_CLASSES (e.g. language switch)."""
        cls._cached_all_perks_map = None

    @property
    def perk_tree_maxed(self):
        """True if all perks of own class are unlocked."""
        cls_data = FIGHTER_CLASSES.get(self.fighter_class, {})
        tree = cls_data.get("perk_tree", [])
        if not tree:
            return False
        own_ids = {p["id"] for p in tree}
        return own_ids.issubset(set(self.unlocked_perks))
