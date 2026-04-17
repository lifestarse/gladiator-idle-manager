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

class Fighter(CombatUnit):
    """Player-owned arena fighter with stat distribution.

    Luck-based combat:
      STR -> attack power (linear)
      AGI -> crit chance (3% per point), dodge (2% per point)
      VIT -> max HP, minor defense

    A high-AGI fighter can dodge lethal hits and crit for massive
    damage, making agility builds viable even against stronger enemies.
    """

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

    # --- Stat-derived properties ---

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
    def total_strength(self):
        return self.strength + self.equip_str

    @property
    def total_agility(self):
        return self.agility + self.equip_agi

    @property
    def total_vitality(self):
        return self.vitality + self.equip_vit

    def _stat_pool(self, stat_names):
        """Sum total_<stat> for each stat in the tuple (uses total_* properties)."""
        getters = {
            "str": lambda: self.total_strength,
            "agi": lambda: self.total_agility,
            "vit": lambda: self.total_vitality,
        }
        return sum(getters[s]() for s in stat_names)

    def _slot_upgrade_bonus(self, slot_id, target):
        """Generic per-target upgrade bonus driven by SLOTS registry.

        Formula: pool(slot, target) * lvl * 20% * mult(slot, target) / split_divisor.
        """
        slot = SLOTS.get(slot_id)
        if slot is None:
            return 0
        item = self.equipment.get(slot_id)
        if not item:
            return 0
        lvl = item.get("upgrade_level", 0)
        if lvl <= 0:
            return 0
        pool_val = self._stat_pool(slot.pool_for(target))
        raw = pool_val * lvl * UPGRADE_BONUS_PER_LEVEL / 100 * slot.mult_for(target)
        return int(raw) // slot.split_divisor

    def upgrade_bonus_for(self, target):
        """Sum upgrade bonuses from every equipped slot that targets `target`.

        target ∈ ("atk", "def", "hp"). Preserves prior behavior: weapon→atk,
        armor→def, accessory→hp, relic→all three (split by 3).
        """
        total = 0
        for slot in SLOTS.values():
            if target in slot.upgrade_targets:
                total += self._slot_upgrade_bonus(slot.id, target)
        return total

    # Legacy property names — thin wrappers for call sites elsewhere.
    @property
    def weapon_upgrade_atk(self):
        return self._slot_upgrade_bonus("weapon", "atk")

    @property
    def armor_upgrade_def(self):
        return self._slot_upgrade_bonus("armor", "def")

    @property
    def accessory_upgrade_hp(self):
        return self._slot_upgrade_bonus("accessory", "hp")

    @property
    def relic_upgrade_atk(self):
        return self._slot_upgrade_bonus("relic", "atk")

    @property
    def relic_upgrade_def(self):
        return self._slot_upgrade_bonus("relic", "def")

    @property
    def relic_upgrade_hp(self):
        return self._slot_upgrade_bonus("relic", "hp")

    @property
    def attack(self):
        base = (self.total_strength * FIGHTER_ATK_PER_STR + self.base_attack
                + (self.level - 1) * FIGHTER_ATK_PER_LEVEL
                + self.weapon_upgrade_atk + self.relic_upgrade_atk)
        result = int(base * (1 + self.get_perk_effects("damage_bonus")))
        penalty = self._injury_stat_penalty("attack", "strength")
        return max(1, int(result * (1 - penalty)))

    @property
    def defense(self):
        base = self.total_vitality + self.base_defense + self.armor_upgrade_def + self.relic_upgrade_def
        penalty = self._injury_stat_penalty("defense")
        return max(0, int(base * (1 - penalty)))

    @property
    def max_hp(self):
        base = (FIGHTER_BASE_HP + self.total_vitality * FIGHTER_HP_PER_VIT
                + self.base_hp + (self.level - 1) * FIGHTER_HP_PER_LEVEL
                + self.accessory_upgrade_hp + self.relic_upgrade_hp)
        result = int(base * self.hp_mult * (1 + self.get_perk_effects("hp_bonus_pct")))
        penalty = self._injury_stat_penalty("max_hp", "vitality")
        return max(1, int(result * (1 - penalty)))

    @property
    def effective_agility(self):
        """Total AGI including perk bonuses (crit/dodge perks add AGI)."""
        perk_bonus = (self.get_perk_effects("crit_chance_bonus")
                      + self.get_perk_effects("dodge_chance_bonus"))
        # Convert % bonuses to AGI points (e.g. 0.05 = +5 AGI)
        return self.total_agility + int(perk_bonus * 100)

    @property
    def crit_chance(self):
        agi = self.effective_agility
        raw = agi / (agi + CRIT_K) + self.crit_bonus
        penalty = self._injury_stat_penalty("crit_chance")
        return min(FIGHTER_CRIT_CAP, max(0.0, raw * (1 - penalty)))

    @property
    def crit_mult(self):
        return CRIT_MULT_BASE + self.effective_agility * CRIT_MULT_PER_AGI + self.get_perk_effects("crit_damage_bonus")

    @property
    def dodge_chance(self):
        raw = self.effective_agility * DODGE_AGI_FACTOR + self.dodge_bonus
        base = 1.0 - 1.0 / (1.0 + raw * DODGE_DIMINISH_FACTOR)
        penalty = self._injury_stat_penalty("dodge_chance", "agility")
        return min(FIGHTER_DODGE_CAP, max(0.0, base * (1 - penalty)))

    @property
    def damage_reduction(self):
        return self.get_perk_effects("damage_reduction")

    @property
    def upgrade_cost(self):
        return DifficultyScaler.upgrade_cost(self.level)

    @property
    def power_rating(self):
        return self.attack + self.defense + self.max_hp // 5

    @property
    def death_chance(self):
        from game.constants import SEVERITY_DEATH_CHANCE
        total = DEATH_CHANCE_BASE
        for inj in self.injuries:
            data = self._get_injury_data(inj["id"])
            severity = data.get("severity", "minor")
            total += SEVERITY_DEATH_CHANCE.get(severity, 0.06)
        return min(DEATH_CHANCE_CAP, total)

    @property
    def class_name(self):
        return FIGHTER_CLASSES.get(self.fighter_class, {}).get("name", "Unknown")

    # --- Injuries ---

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

    # --- Perks ---

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

    # Perk registry cache. FIGHTER_CLASSES comes from static JSON so the
    # map is constant for the lifetime of a data load. Previously this was
    # rebuilt on every `get_perk_effects` call (profiler showed ~11k calls
    # per 1000-vs-1000 battle, eating ~13% of total battle time).
    # `invalidate_perks_map_cache` is called by data_loader on reload.
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

    # --- Actions ---

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
