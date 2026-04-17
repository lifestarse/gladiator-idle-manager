# Build: 1
"""Fighter _FighterSerializeMixin."""
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


class _FighterSerializeMixin:
    def to_dict(self):
        return {
            "name": self.name,
            "fighter_class": self.fighter_class,
            "level": self.level,
            "strength": self.strength,
            "agility": self.agility,
            "vitality": self.vitality,
            "unused_points": self.unused_points,
            "crit_bonus": self.crit_bonus,
            "dodge_bonus": self.dodge_bonus,
            "hp_mult": self.hp_mult,
            "points_per_level": self.points_per_level,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_hp": self.base_hp,
            "hp": self.hp,
            "alive": self.alive,
            "injuries": [inj.copy() for inj in self.injuries],
            "kills": self.kills,
            "perk_points": self.perk_points,
            "unlocked_perks": self.unlocked_perks,
            "equipment": self.equipment,
            "on_expedition": self.on_expedition,
            "expedition_id": self.expedition_id,
            "expedition_end": self.expedition_end,
        }

    @classmethod
    def from_dict(cls, data):
        g = cls.__new__(cls)
        g.name = data.get("name", "Unknown")
        g.fighter_class = data.get("fighter_class", "mercenary")
        g.level = data.get("level", 1)
        g.strength = data.get("strength", 5)
        g.agility = data.get("agility", 5)
        g.vitality = data.get("vitality", 5)
        g.unused_points = data.get("unused_points", 0)
        cls_data = FIGHTER_CLASSES.get(g.fighter_class, FIGHTER_CLASSES["mercenary"])
        g.crit_bonus = data.get("crit_bonus", cls_data["crit_bonus"])
        g.dodge_bonus = data.get("dodge_bonus", cls_data["dodge_bonus"])
        g.hp_mult = data.get("hp_mult", cls_data["hp_mult"])
        g.points_per_level = data.get("points_per_level", cls_data["points_per_level"])
        g.base_attack = data.get("base_attack", 0)
        g.base_defense = data.get("base_defense", 0)
        g.base_hp = data.get("base_hp", 0)
        g.hp = data.get("hp", 50)
        g.alive = data.get("alive", True)
        g.injuries = data.get("injuries", [])
        g.kills = data.get("kills", 0)
        g.perk_points = data.get("perk_points", 0)
        g.unlocked_perks = data.get("unlocked_perks", [])
        equip = data.get("equipment", {"weapon": None, "armor": None, "accessory": None, "relic": None})
        # Back-compat: old saves didn't have a 'relic' slot.
        if "relic" not in equip:
            equip["relic"] = None
        g.equipment = equip
        g.on_expedition = data.get("on_expedition", False)
        g.expedition_id = data.get("expedition_id")
        g.expedition_end = data.get("expedition_end", 0.0)
        return g
