# Build: 1
"""Fighter _FighterEquipMixin."""
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


class _FighterEquipMixin:
    def _relic_bonus(self, stat):
        """Relic upgrade bonus for str/agi/vit: equal split."""
        item = self.equipment.get("relic")
        if not item:
            return 0
        return item.get(stat, 0)

    def item_total_stats(self, slot):
        """Return total (str, agi, vit) an equipped item gives."""
        item = self.equipment.get(slot)
        if not item:
            return 0, 0, 0
        return item.get("str", 0), item.get("agi", 0), item.get("vit", 0)

    def _equip_stat(self, stat):
        """Sum base equipment stats only (no upgrade bonuses).

        All upgrade bonuses are now applied directly to final stats:
        weapon → ATK, armor → DEF, accessory → HP, relic → all three.
        See weapon_upgrade_atk, armor_upgrade_def, accessory_upgrade_hp, relic_upgrade_*.
        """
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get(stat, 0)
        return total

    @property
    def equip_str(self):
        return self._equip_stat("str")

    @property
    def equip_agi(self):
        return self._equip_stat("agi")

    @property
    def equip_vit(self):
        return self._equip_stat("vit")

    @property
    def upgrade_cost(self):
        return DifficultyScaler.upgrade_cost(self.level)

    def equip_item(self, item):
        """Equip item, returns the old item (or None) for inventory.
        Heals HP by the net HP gain from the new item (outside battle)."""
        slot = item["slot"]
        old = self.equipment.get(slot)
        old_max = self.max_hp
        self.equipment[slot] = item
        new_max = self.max_hp
        hp_gain = new_max - old_max
        if hp_gain > 0:
            self.hp = min(self.hp + hp_gain, new_max)
        elif self.hp > new_max:
            self.hp = new_max
        return old

    def unequip_item(self, slot):
        """Remove item from slot, cap HP to new max. Returns removed item."""
        old = self.equipment.get(slot)
        if not old:
            return None
        self.equipment[slot] = None
        if self.hp > self.max_hp:
            self.hp = self.max_hp
        return old
