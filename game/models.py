# Build: 31
"""Game data models — fighters, enemies, equipment, expeditions, economy.

Roguelike-manager: permadeath resets the run, stats distributed manually,
fighters have classes with unique modifiers. Luck-based combat where
crits and dodge can turn the tide — weak but agile fighters can win.
"""

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

# --- Result type for engine operations ---
# ok=True  → message is success text (show as toast/info)
# ok=False → message is error text (show as warning toast)
# code     → machine-readable tag, e.g. "not_enough_gold", "name_change"
Result = namedtuple("Result", ["ok", "message", "code"], defaults=[True, "", ""])


_NUM_SUFFIXES = [
    ("Dc", 1e33),   # decillion
    ("No", 1e30),   # nonillion
    ("Oc", 1e27),   # octillion
    ("Sp", 1e24),   # septillion
    ("Sx", 1e21),   # sextillion
    ("Qi", 1e18),   # quintillion
    ("Qa", 1e15),   # quadrillion
    ("T", 1e12),    # trillion
    ("B", 1e9),     # billion
    ("M", 1e6),     # million
    ("K", 1e3),     # thousand
]

def fmt_num(n):
    """Format large numbers: 1500 -> 1.5K, up to decillion (Dc)."""
    if n is None:
        return "0"
    n = float(n)
    if abs(n) < 1000:
        return f"{n:.0f}"
    for suffix, threshold in _NUM_SUFFIXES:
        if abs(n) >= threshold:
            val = n / threshold
            return f"{val:.1f}{suffix}" if val != int(val) else f"{int(val)}{suffix}"
    return f"{n:.0f}"

# --- Rarity system ---

RARITY_COMMON = "common"
RARITY_UNCOMMON = "uncommon"
RARITY_RARE = "rare"
RARITY_EPIC = "epic"
RARITY_LEGENDARY = "legendary"

RARITY_COLORS = {
    RARITY_COMMON: (0.55, 0.55, 0.50, 1),
    RARITY_UNCOMMON: (0.20, 0.72, 0.30, 1),
    RARITY_RARE: (0.25, 0.50, 0.90, 1),
    RARITY_EPIC: (0.65, 0.25, 0.85, 1),
    RARITY_LEGENDARY: (0.95, 0.75, 0.15, 1),
}

RARITY_MULTIPLIER = {
    RARITY_COMMON: 1.0,
    RARITY_UNCOMMON: 1.3,
    RARITY_RARE: 1.7,
    RARITY_EPIC: 2.2,
    RARITY_LEGENDARY: 3.0,
}

RARITY_MAX_UPGRADE = {
    RARITY_COMMON: MAX_UPGRADE_COMMON,
    RARITY_UNCOMMON: MAX_UPGRADE_UNCOMMON,
    RARITY_RARE: MAX_UPGRADE_RARE,
    RARITY_EPIC: MAX_UPGRADE_EPIC,
    RARITY_LEGENDARY: MAX_UPGRADE_LEGENDARY,
}

# Equipment slot registry (single source of truth for per-slot behavior).
# Re-exported here for back-compat with existing imports.
from game.slots import SLOTS, EQUIPMENT_SLOTS  # noqa: E402,F401

# ============================================================
#  ALL GAME DATA — loaded from data/*.json at import time.
#  No hardcoded items, classes, enemies, or expeditions.
#  engine._wire_data() may re-assign these after full init.
# ============================================================

FIGHTER_NAMES = []
FIGHTER_CLASSES = {}
FORGE_WEAPONS = []
FORGE_ARMOR = []
FORGE_ACCESSORIES = []
ALL_FORGE_ITEMS = []
ENCHANTMENT_TYPES = {}
EXPEDITIONS = []
RELICS = {}
SHARD_TIERS = {}

BOSS_PREFIXES = [
    "Infernal", "Abyssal", "Dread", "Void", "Doom", "Shadow", "Blood",
    "Iron", "Storm", "Flame", "Frost", "Death", "Dark", "Grim", "War",
    "Soul", "Bone", "Night", "Chaos", "Wrath", "Blight", "Hell", "Thunder",
]
BOSS_SUFFIXES = [
    "Destroyer", "Annihilator", "Overlord", "Tyrant", "Conqueror",
    "Decimator", "Executioner", "Warlord", "Champion", "Colossus",
    "Devourer", "Slayer", "Ravager", "Dominator", "Eradicator",
    "Vanquisher", "Titan", "Sovereign", "Emperor", "Nemesis",
]
ENEMY_TITLES = [
    "Pit Rat", "Chained Brute", "Sand Crawler", "Iron Fang",
    "Bone Breaker", "Blood Warden", "Doom Herald", "Warlord",
    "Shadow Titan", "The Undying",
]


# Data is loaded via GameEngine._wire_data() at startup — no import-time init.


def get_boss_name(tier):
    """Return a unique boss name for the given arena tier.

    Priority: JSON bosses_by_tier → procedural prefix+suffix.
    """
    from game.data_loader import data_loader
    bosses = data_loader.bosses_by_tier.get(tier)
    if bosses:
        return bosses[0].get("name", f"Boss Tier {tier}")
    idx = (tier - 1) % (len(BOSS_PREFIXES) * len(BOSS_SUFFIXES))
    prefix = BOSS_PREFIXES[idx % len(BOSS_PREFIXES)]
    suffix = BOSS_SUFFIXES[idx // len(BOSS_PREFIXES) % len(BOSS_SUFFIXES)]
    rank = (tier - 1) // (len(BOSS_PREFIXES) * len(BOSS_SUFFIXES)) + 1
    if rank > 1:
        return f"{prefix} {suffix} Mk.{rank}"
    return f"{prefix} {suffix}"


def get_max_upgrade(item):
    """Max upgrade level based on item rarity."""
    return RARITY_MAX_UPGRADE.get(item.get("rarity", "common"), 5)


def get_upgrade_tier(target_level):
    """Returns (shard_tier, shard_count) needed for upgrading to +target_level."""
    tier = (target_level - 1) // 5 + 1
    count = ((target_level - 1) % 5) + 1
    return tier, count


def item_display_name(item_dict):
    """Format item name only (upgrade & enchantment shown separately in UI)."""
    return item_dict.get("name", "?")


def calc_item_stats(item, fighter=None):
    """Calculate total (str, agi, vit) for any item."""
    s = item.get("str", 0)
    a = item.get("agi", 0)
    v = item.get("vit", 0)
    return s, a, v


# ============================================================
#  DIFFICULTY & ECONOMY SCALING — roguelike balanced
# ============================================================

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


# --- Dynamic market items — consumables only ---

def get_dynamic_shop_items(arena_tier, surgeon_uses):
    """Generate shop items: consumables. Equipment is in the Forge."""
    from game.localization import t
    consumables = [
        {
            "id": "heal_potion", "name": t("blood_salve"),
            "desc": t("blood_salve_desc"),
            "cost": DifficultyScaler.heal_cost(arena_tier),
            "effect": {"heal": True},
        },
        {
            "id": "atk_tonic", "name": t("fury_tonic"),
            "desc": t("fury_tonic_desc"),
            "cost": int(TONIC_BASE_COST * (TONIC_TIER_EXPO ** (arena_tier - 1))),
            "effect": {"base_attack": 2},
        },
        {
            "id": "def_tonic", "name": t("stone_brew"),
            "desc": t("stone_brew_desc"),
            "cost": int(TONIC_BASE_COST * (TONIC_TIER_EXPO ** (arena_tier - 1))),
            "effect": {"base_defense": 2},
        },
        {
            "id": "injury_cure", "name": t("surgeon_kit"),
            "desc": t("surgeon_kit_desc", n=surgeon_uses),
            "cost": DifficultyScaler.surgeon_cost(surgeon_uses),
            "effect": {"cure_injury": 1},
        },
    ]

    return consumables


# ============================================================
#  FIGHTER (Roguelike with STR/AGI/VIT, luck-based combat)
# ============================================================


class CombatUnit:
    """Shared combat methods for Fighter and Enemy."""

    def take_damage(self, raw_dmg):
        if random.random() < self.dodge_chance:
            return 0
        reduction = self.defense / (self.defense + DEFENSE_DIVISOR)
        reduced = max(1, int(raw_dmg * (1 - reduction)))
        self.hp = max(0, self.hp - reduced)
        return reduced

    def deal_damage(self):
        variance = random.uniform(DAMAGE_VARIANCE_LOW, DAMAGE_VARIANCE_HIGH)
        return max(1, int(self.attack * variance))


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


# ============================================================
#  ENEMY (luck-based: enemies also have crit/dodge)
# ============================================================

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



