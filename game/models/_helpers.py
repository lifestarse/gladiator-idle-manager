# Build: 1
"""Auto-split submodule: _helpers.py."""
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


ENCHANTMENT_TYPES = {}


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
