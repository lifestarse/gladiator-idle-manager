# Build: 4
"""models._helpers — Result namedtuple, fmt_num, rarity maps, boss name gen."""
from ._imports import *  # noqa: F401,F403
from ._scaling import DifficultyScaler


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


def fmt_def(defense):
    """Format DEF with damage-reduction percentage: 370 -> '370 (79%)'.

    Mirrors the combat formula DEF/(DEF+DEFENSE_DIVISOR) so the UI shows
    what the stat actually translates to in mitigation — a raw DEF number
    alone is meaningless to players without knowing the divisor.
    """
    pct = int(defense / (defense + DEFENSE_DIVISOR) * 100) if defense > 0 else 0
    return f"{fmt_num(defense)} ({pct}%)"


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
