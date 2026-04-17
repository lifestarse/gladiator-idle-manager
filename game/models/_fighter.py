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

from .fighterstatsmixin import _FighterStatsMixin
from .fighterequipmixin import _FighterEquipMixin
from .fighterperksmixin import _FighterPerksMixin
from .fighterserializemixin import _FighterSerializeMixin

class Fighter(CombatUnit, _FighterStatsMixin, _FighterEquipMixin, _FighterPerksMixin, _FighterSerializeMixin):
    def __init__(self, name=None, level=1, fighter_class="mercenary"):
        cls_data = FIGHTER_CLASSES.get(fighter_class, FIGHTER_CLASSES["mercenary"])
        self.name = name or random.choice(FIGHTER_NAMES)
        self.fighter_class = fighter_class
        self.level = level

        # Core stats (distributable)
        self.strength = cls_data["base_str"]
        self.agility = cls_data["base_agi"]
        self.vitality = cls_data["base_vit"]
        self.unused_points = FIGHTER_STARTING_POINTS

        # Class modifiers (stored for reference)
        self.crit_bonus = cls_data["crit_bonus"]
        self.dodge_bonus = cls_data["dodge_bonus"]
        self.hp_mult = cls_data["hp_mult"]
        self.points_per_level = cls_data["points_per_level"]

        # Expedition-granted flat bonuses (used in attack/defense/max_hp formulas)
        self.base_attack = 0
        self.base_defense = 0
        self.base_hp = 0

        self.alive = True
        self.injuries = []  # list of {"id": "split_lip"} dicts
        self.kills = 0
        self.perk_points = 0
        self.unlocked_perks = []  # list of perk IDs
        self.equipment = {"weapon": None, "armor": None, "accessory": None, "relic": None}
        self.on_expedition = False
        self.expedition_id = None
        self.expedition_end = 0.0
        self.hp = self.max_hp

    @property
    def available(self):
        """True if fighter can act: alive and not on expedition."""
        return self.alive and not self.on_expedition

    @property
    def class_name(self):
        return FIGHTER_CLASSES.get(self.fighter_class, {}).get("name", "Unknown")

    @property
    def injury_count(self):
        return len(self.injuries)

    @property
    def has_permanent_injury(self):
        """True if fighter has at least one permanent (unhealable) injury."""
        for inj in self.injuries:
            data = self._get_injury_data(inj["id"])
            if data.get("heal_cost_multiplier", 1) == 0:
                return True
        return False

    def _get_injury_data(self, injury_id):
        from game.data_loader import data_loader
        return data_loader.injuries_by_id.get(injury_id, {})

    def _injury_stat_penalty(self, *stat_names):
        """Return total percent penalty (0.0–0.95) from all injuries for given stat(s)."""
        total = 0.0
        for inj in self.injuries:
            data = self._get_injury_data(inj["id"])
            for pen in data.get("stat_penalties", []):
                if pen["stat"] in stat_names:
                    total += pen["value"]
        return min(total, 0.95)

    _cached_all_perks_map = None

    @classmethod
    def _get_all_perks_map(cls):
        """Cached {perk_id: perk_dict} from all classes."""
        cache = cls._cached_all_perks_map
        if cache is not None:
            return cache
        result = {}
        for cls_data in FIGHTER_CLASSES.values():
            for perk in cls_data.get("perk_tree", []):
                result[perk["id"]] = perk
        cls._cached_all_perks_map = result
        return result

    def distribute_point(self, stat):
        """Spend 1 unused point on STR, AGI, or VIT. Returns True if success."""
        if self.unused_points <= 0:
            return False
        if stat == "strength":
            self.strength += 1
        elif stat == "agility":
            self.agility += 1
        elif stat == "vitality":
            old_max = self.max_hp
            self.vitality += 1
            self.hp += self.max_hp - old_max
        else:
            return False
        self.unused_points -= 1
        return True

    def level_up(self):
        """Level up: gain stat points based on class, perk point every 5 levels."""
        self.level += 1
        self.unused_points += self.points_per_level
        if self.level % PERK_POINT_EVERY_N_LEVELS == 0:
            self.perk_points += 1
        self.hp = self.max_hp

    def heal(self):
        self.hp = self.max_hp

    def check_permadeath(self):
        """Check permadeath. Returns (died: bool, injury_id: str|None)."""
        if random.random() < self.death_chance:
            self.alive = False
            return True, None
        from game.data_loader import data_loader
        existing_ids = {inj["id"] for inj in self.injuries}
        injury_id = data_loader.pick_random_injury(existing_ids)
        self.injuries.append({"id": injury_id})
        if self.hp > self.max_hp:
            self.hp = self.max_hp
        return False, injury_id

    def get_injury_heal_cost(self, injury_idx=0):
        """Cost to heal a specific injury. Returns -1 for permanent (unhealable)."""
        if not self.injuries:
            return 0
        idx = min(injury_idx, len(self.injuries) - 1)
        inj = self.injuries[idx]
        data = self._get_injury_data(inj["id"])
        mult = data.get("heal_cost_multiplier", 1.0)
        if mult == 0:
            return -1
        base = INJURY_HEAL_BASE_COST * max(1, self.level)
        return int(base * mult)

    def cheapest_healable_injury_idx(self):
        """Return index of cheapest non-permanent injury, or -1 if none."""
        best_idx, best_cost = -1, float('inf')
        for i in range(len(self.injuries)):
            cost = self.get_injury_heal_cost(i)
            if 0 < cost < best_cost:
                best_idx, best_cost = i, cost
        return best_idx
