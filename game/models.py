# Build: 13
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
    DEATH_CHANCE_BASE, DEATH_CHANCE_PER_INJURY, DEATH_CHANCE_CAP,
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
    INJURY_HEAL_BASE_COST, TONIC_BASE_COST, TONIC_TIER_EXPO,
    MAX_UPGRADE_COMMON, MAX_UPGRADE_UNCOMMON, MAX_UPGRADE_RARE,
    MAX_UPGRADE_EPIC, MAX_UPGRADE_LEGENDARY,
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

# --- Name pools ---

FIGHTER_NAMES = [
    "Vorn", "Kaelith", "Dragan", "Fenrik", "Theron",
    "Ashara", "Brokk", "Sylas", "Morrigan", "Zephyr",
    "Ragnor", "Lyra", "Torvald", "Selene", "Grimjaw",
    "Kira", "Uldric", "Nyx", "Balor", "Ember",
]

ENEMY_TITLES = [
    "Pit Rat", "Chained Brute", "Sand Crawler", "Iron Fang",
    "Bone Breaker", "Blood Warden", "Doom Herald", "Warlord",
    "Shadow Titan", "The Undying",
]

BOSS_NAMES = [
    # Tier 1-50
    "Groth the Mangler", "Varka Ironjaw", "Skarn Bloodfist", "Molgur the Rotten",
    "Draven Ashclaw", "Toruk Bonecrusher", "Haldor the Grim", "Razek Deathbringer",
    "Ulgor Flamemaw", "Krovak the Impaler",
    "Sethara Venomtongue", "Brakka Stonehorn", "Nythgor Soulreaper", "Durn the Faceless",
    "Grimjaw the Butcher", "Vorath Skullsplitter", "Morgath Chainfury", "Ixen Darktalon",
    "Zephrak Doomhowl", "Kalgor the Merciless",
    "Thessa Bloodthorn", "Rukvak Ironfang", "Olgrim Wartusk", "Pyrak the Scorched",
    "Nethara Dreadwhisper", "Skarog Hellhammer", "Dravok the Cursed", "Ulmira Frostbane",
    "Gharak Spinerender", "Bolverk the Unyielding",
    "Xathros Shadowflame", "Jorvak Thundermaw", "Azura the Flayed", "Krommak Doomfang",
    "Selvira Nightthorn", "Urgoth the Ravager", "Thalgor Ashbringer", "Moriven Soulchain",
    "Drekthar Warborn", "Vulkara the Savage",
    "Grimnak Hellborn", "Seraphyx the Undying", "Korrath Worldbreaker", "Zarvok Blightclaw",
    "Iselda Doomweaver", "Thorgak the Eternal", "Malachar Bloodrite", "Skelvion Dreadmaw",
    "Ragnok Cinderfist", "Obraxis the Abyssal",
    # Tier 51-100
    "Vordak the Relentless", "Zharina Ghostflame", "Bulgrim Siegebreaker", "Talvok Rotfang",
    "Myrkana Shadowpiercer", "Hakkon Steelwrath", "Grenthak Plaguebringer", "Ulvira Frostvein",
    "Domrak Hellreaver", "Kassara the Unbroken",
    "Thorvex Stormjaw", "Nulgath Bonelord", "Elyxia Venomblade", "Rokvar the Desecrator",
    "Balmira Chainwraith", "Gorthan Doomwall", "Szarvok Nightripper", "Valdris the Hollow",
    "Kragmor Emberfist", "Zylithra Soulflayer",
    "Urthane the Colossus", "Draven Warshriek", "Morwenna Dreadbloom", "Skragak Thunderhorn",
    "Vexara Ashwhisper", "Tolvak the Sundered", "Grimhild Ironmaw", "Nethrak Darkforge",
    "Pyrelith the Scorching", "Bolvak Worldrender",
    "Gharvok Blighthorn", "Selthara Moonbane", "Kragnus the Devastator", "Ulvok Dreadforge",
    "Myrthen Soulbinder", "Zarkoth the Insatiable", "Dorvina Nightsteel", "Halkrath Warmonger",
    "Thervok Cindermaw", "Ragnara the Deathless",
    "Volgrim Stormbreaker", "Xervok the Unseen", "Bulgara Chainheart", "Drelmak Rotbringer",
    "Iskara Flamevein", "Tormund the Accursed", "Grolvak Hellspine", "Nythara Doomgaze",
    "Skalvok the Remorseless", "Azrathor Worldbane",
]

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


def get_boss_name(tier):
    """Return a unique boss name for the given arena tier."""
    if tier <= len(BOSS_NAMES):
        return BOSS_NAMES[tier - 1]
    # For tiers beyond the list, generate deterministic names
    idx = (tier - 1) % (len(BOSS_PREFIXES) * len(BOSS_SUFFIXES))
    prefix = BOSS_PREFIXES[idx % len(BOSS_PREFIXES)]
    suffix = BOSS_SUFFIXES[idx // len(BOSS_PREFIXES) % len(BOSS_SUFFIXES)]
    rank = (tier - 1) // (len(BOSS_PREFIXES) * len(BOSS_SUFFIXES)) + 1
    if rank > 1:
        return f"{prefix} {suffix} Mk.{rank}"
    return f"{prefix} {suffix}"

# --- Rarity system ---

RARITY_COMMON = "common"
RARITY_UNCOMMON = "uncommon"
RARITY_RARE = "rare"
RARITY_EPIC = "epic"
RARITY_LEGENDARY = "legendary"

RARITY_COLORS = {
    RARITY_COMMON: (0.45, 0.40, 0.35, 1),
    RARITY_UNCOMMON: (0.30, 0.50, 0.25, 1),
    RARITY_RARE: (0.25, 0.40, 0.65, 1),
    RARITY_EPIC: (0.50, 0.25, 0.55, 1),
    RARITY_LEGENDARY: (0.72, 0.58, 0.22, 1),
}

RARITY_MULTIPLIER = {
    RARITY_COMMON: 1.0,
    RARITY_UNCOMMON: 1.3,
    RARITY_RARE: 1.7,
    RARITY_EPIC: 2.2,
    RARITY_LEGENDARY: 3.0,
}

# --- Fighter classes ---

FIGHTER_CLASSES = {
    "mercenary": {
        "name": "Mercenary",
        "desc": "Balanced fighter. +1 stat point per level.",
        "base_str": 5, "base_agi": 5, "base_vit": 5,
        "crit_bonus": 0.0,
        "dodge_bonus": 0.0,
        "hp_mult": 1.0,
        "points_per_level": 4,
    },
    "assassin": {
        "name": "Assassin",
        "desc": "High crit, low HP. +20% crit chance.",
        "base_str": 4, "base_agi": 8, "base_vit": 3,
        "crit_bonus": 0.20,
        "dodge_bonus": 0.05,
        "hp_mult": 0.85,
        "points_per_level": 3,
    },
    "tank": {
        "name": "Tank",
        "desc": "High HP & defense. Slow but durable.",
        "base_str": 3, "base_agi": 2, "base_vit": 10,
        "crit_bonus": -0.05,
        "dodge_bonus": 0.0,
        "hp_mult": 1.3,
        "points_per_level": 3,
    },
}

# --- Equipment (lost on permadeath reset) ---

EQUIPMENT_SLOTS = ["weapon", "armor", "accessory", "relic"]

FORGE_WEAPONS = [
    {"id": "rusty_blade", "name": "Rusty Blade", "slot": "weapon", "rarity": RARITY_COMMON,
     "atk": 3, "def": 0, "hp": 0, "cost": 400},
    {"id": "iron_sword", "name": "Iron Sword", "slot": "weapon", "rarity": RARITY_COMMON,
     "atk": 5, "def": 0, "hp": 0, "cost": 900},
    {"id": "steel_falcata", "name": "Steel Falcata", "slot": "weapon", "rarity": RARITY_UNCOMMON,
     "atk": 8, "def": 0, "hp": 5, "cost": 2000},
    {"id": "obsidian_edge", "name": "Obsidian Edge", "slot": "weapon", "rarity": RARITY_RARE,
     "atk": 12, "def": 2, "hp": 0, "cost": 5000},
    {"id": "inferno_cleaver", "name": "Inferno Cleaver", "slot": "weapon", "rarity": RARITY_EPIC,
     "atk": 18, "def": 0, "hp": 10, "cost": 12000},
    {"id": "blade_of_ruin", "name": "Blade of Ruin", "slot": "weapon", "rarity": RARITY_LEGENDARY,
     "atk": 28, "def": 5, "hp": 20, "cost": 30000},
]

FORGE_ARMOR = [
    {"id": "leather_vest", "name": "Leather Vest", "slot": "armor", "rarity": RARITY_COMMON,
     "atk": 0, "def": 3, "hp": 10, "cost": 500},
    {"id": "chain_mail", "name": "Chain Mail", "slot": "armor", "rarity": RARITY_COMMON,
     "atk": 0, "def": 5, "hp": 15, "cost": 1200},
    {"id": "bronze_plate", "name": "Bronze Plate", "slot": "armor", "rarity": RARITY_UNCOMMON,
     "atk": 0, "def": 8, "hp": 25, "cost": 2800},
    {"id": "shadow_guard", "name": "Shadow Guard", "slot": "armor", "rarity": RARITY_RARE,
     "atk": 3, "def": 12, "hp": 30, "cost": 6500},
    {"id": "titan_shell", "name": "Titan Shell", "slot": "armor", "rarity": RARITY_EPIC,
     "atk": 0, "def": 18, "hp": 50, "cost": 15000},
    {"id": "dragonscale", "name": "Dragonscale Aegis", "slot": "armor", "rarity": RARITY_LEGENDARY,
     "atk": 5, "def": 25, "hp": 70, "cost": 35000},
]

FORGE_ACCESSORIES = [
    {"id": "bone_charm", "name": "Bone Charm", "slot": "accessory", "rarity": RARITY_COMMON,
     "atk": 2, "def": 2, "hp": 5, "cost": 450},
    {"id": "iron_ring", "name": "Iron Ring", "slot": "accessory", "rarity": RARITY_UNCOMMON,
     "atk": 4, "def": 4, "hp": 10, "cost": 1600},
    {"id": "blood_pendant", "name": "Blood Pendant", "slot": "accessory", "rarity": RARITY_RARE,
     "atk": 7, "def": 3, "hp": 20, "cost": 4000},
    {"id": "void_amulet", "name": "Void Amulet", "slot": "accessory", "rarity": RARITY_EPIC,
     "atk": 10, "def": 7, "hp": 30, "cost": 10000},
    {"id": "crown_of_ash", "name": "Crown of Ash", "slot": "accessory", "rarity": RARITY_LEGENDARY,
     "atk": 15, "def": 10, "hp": 50, "cost": 25000},
]

ALL_FORGE_ITEMS = FORGE_WEAPONS + FORGE_ARMOR + FORGE_ACCESSORIES

# --- Metal Shards (expedition currency for weapon upgrades) ---

SHARD_TIERS = {
    "dark_tunnels":   {"tier": 1, "name": "Metal Shard (I)"},
    "bandit_outpost": {"tier": 2, "name": "Metal Shard (II)"},
    "cursed_ruins":   {"tier": 3, "name": "Metal Shard (III)"},
    "dragon_wastes":  {"tier": 4, "name": "Metal Shard (IV)"},
    "void_rift":      {"tier": 5, "name": "Metal Shard (V)"},
}

RARITY_MAX_UPGRADE = {
    RARITY_COMMON: MAX_UPGRADE_COMMON,
    RARITY_UNCOMMON: MAX_UPGRADE_UNCOMMON,
    RARITY_RARE: MAX_UPGRADE_RARE,
    RARITY_EPIC: MAX_UPGRADE_EPIC,
    RARITY_LEGENDARY: MAX_UPGRADE_LEGENDARY,
}


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
    """Calculate total (atk, def, hp) for any item, optionally with fighter scaling.

    Works for inventory items, shop items, and equipped items alike.
    If fighter is provided, upgrade bonuses scale with fighter stats.
    If not, only base + flat upgrade bonuses are shown.
    """
    atk = item.get("atk", 0)
    dfn = item.get("def", 0)
    hp = item.get("hp", 0)
    slot = item.get("slot", "")
    lvl = item.get("upgrade_level", 0)
    if lvl > 0 and fighter:
        pct = lvl * UPGRADE_BONUS_PER_LEVEL / 100
        if slot == "weapon":
            atk += int((fighter.strength + fighter.agility) * pct)
        elif slot == "armor":
            dfn += int((fighter.strength + fighter.vitality) * pct)
        elif slot == "accessory":
            hp += int((fighter.agility + fighter.vitality) * pct) * ACCESSORY_HP_MULT
        elif slot == "relic":
            all_s = fighter.strength + fighter.agility + fighter.vitality
            b = int(all_s * pct / RELIC_STAT_SPLIT)
            atk += b
            dfn += b
            hp += b * ACCESSORY_HP_MULT
    return atk, dfn, hp


# --- Enchantments (Elden Ring-style buildup) ---

ENCHANTMENT_TYPES = {
    "bleeding": {
        "name": "Bleeding",
        "buildup_per_hit": 20,
        "threshold": 100,
        "effect": "burst",
        "burst_pct": 0.15,
        "cost_gold": 50000,
        "cost_shard_tier": 5,
        "cost_shard_count": 100,
    },
    "frostbite": {
        "name": "Frostbite",
        "buildup_per_hit": 15,
        "threshold": 100,
        "effect": "burst_debuff",
        "burst_pct": 0.10,
        "atk_reduction_pct": 0.20,
        "debuff_turns": 3,
        "cost_gold": 80000,
        "cost_shard_tier": 5,
        "cost_shard_count": 100,
    },
    "poison": {
        "name": "Poison",
        "buildup_per_hit": 25,
        "threshold": 80,
        "effect": "dot",
        "dot_pct": 0.05,
        "dot_turns": 4,
        "cost_gold": 60000,
        "cost_shard_tier": 5,
        "cost_shard_count": 100,
    },
}

# --- Expeditions ---

EXPEDITIONS = [
    {
        "id": "dark_tunnels",
        "name": "Dark Tunnels",
        "desc": "Scout the tunnels beneath the arena",
        "duration": 60,
        "min_level": 11,
        "danger": 0.43,
        "gold_range": (20, 60),
        "relic_chance": 0.15,
        "relic_pool": [RARITY_COMMON, RARITY_UNCOMMON],
    },
    {
        "id": "bandit_outpost",
        "name": "Bandit Outpost",
        "desc": "Raid a bandit camp in the hills",
        "duration": 180,
        "min_level": 13,
        "danger": 0.50,
        "gold_range": (50, 150),
        "relic_chance": 0.25,
        "relic_pool": [RARITY_UNCOMMON, RARITY_RARE],
    },
    {
        "id": "cursed_ruins",
        "name": "Cursed Ruins",
        "desc": "Ancient temple with deadly traps",
        "duration": 300,
        "min_level": 15,
        "danger": 0.57,
        "gold_range": (100, 300),
        "relic_chance": 0.35,
        "relic_pool": [RARITY_RARE, RARITY_EPIC],
    },
    {
        "id": "dragon_wastes",
        "name": "Dragon Wastes",
        "desc": "Scorched lands where few return",
        "duration": 600,
        "min_level": 18,
        "danger": 0.65,
        "gold_range": (200, 600),
        "relic_chance": 0.45,
        "relic_pool": [RARITY_EPIC, RARITY_LEGENDARY],
    },
    {
        "id": "void_rift",
        "name": "Void Rift",
        "desc": "A tear in reality. Maximum risk.",
        "duration": 900,
        "min_level": 22,
        "danger": 0.75,
        "gold_range": (400, 1000),
        "relic_chance": 0.55,
        "relic_pool": [RARITY_LEGENDARY],
    },
]

# --- Relics ---

RELICS = {
    RARITY_COMMON: [
        {"id": "cracked_idol", "name": "Cracked Idol", "slot": "relic",
         "rarity": RARITY_COMMON, "atk": 2, "def": 1, "hp": 5, "cost": 30},
        {"id": "dusty_talisman", "name": "Dusty Talisman", "slot": "relic",
         "rarity": RARITY_COMMON, "atk": 1, "def": 2, "hp": 8, "cost": 35},
        {"id": "worn_signet", "name": "Worn Signet", "slot": "relic",
         "rarity": RARITY_COMMON, "atk": 3, "def": 0, "hp": 3, "cost": 25},
    ],
    RARITY_UNCOMMON: [
        {"id": "serpent_fang", "name": "Serpent Fang", "slot": "relic",
         "rarity": RARITY_UNCOMMON, "atk": 5, "def": 2, "hp": 10, "cost": 80},
        {"id": "stone_of_vigor", "name": "Stone of Vigor", "slot": "relic",
         "rarity": RARITY_UNCOMMON, "atk": 2, "def": 5, "hp": 15, "cost": 90},
        {"id": "wolf_pelt_cloak", "name": "Wolf Pelt Cloak", "slot": "relic",
         "rarity": RARITY_UNCOMMON, "atk": 3, "def": 4, "hp": 12, "cost": 85},
    ],
    RARITY_RARE: [
        {"id": "eye_of_the_storm", "name": "Eye of the Storm", "slot": "relic",
         "rarity": RARITY_RARE, "atk": 10, "def": 5, "hp": 20, "cost": 250},
        {"id": "frozen_heart", "name": "Frozen Heart", "slot": "relic",
         "rarity": RARITY_RARE, "atk": 5, "def": 10, "hp": 25, "cost": 300},
        {"id": "war_banner", "name": "War Banner", "slot": "relic",
         "rarity": RARITY_RARE, "atk": 8, "def": 8, "hp": 15, "cost": 270},
    ],
    RARITY_EPIC: [
        {"id": "soul_lantern", "name": "Soul Lantern", "slot": "relic",
         "rarity": RARITY_EPIC, "atk": 15, "def": 10, "hp": 35, "cost": 700},
        {"id": "titans_finger", "name": "Titan's Finger", "slot": "relic",
         "rarity": RARITY_EPIC, "atk": 10, "def": 15, "hp": 40, "cost": 750},
        {"id": "eclipse_shard", "name": "Eclipse Shard", "slot": "relic",
         "rarity": RARITY_EPIC, "atk": 18, "def": 8, "hp": 30, "cost": 680},
    ],
    RARITY_LEGENDARY: [
        {"id": "heart_of_colossus", "name": "Heart of the Colossus", "slot": "relic",
         "rarity": RARITY_LEGENDARY, "atk": 25, "def": 20, "hp": 60, "cost": 2000},
        {"id": "abyssal_crown", "name": "Abyssal Crown", "slot": "relic",
         "rarity": RARITY_LEGENDARY, "atk": 30, "def": 15, "hp": 50, "cost": 1800},
        {"id": "ember_of_creation", "name": "Ember of Creation", "slot": "relic",
         "rarity": RARITY_LEGENDARY, "atk": 20, "def": 25, "hp": 70, "cost": 2200},
    ],
}


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
        return int(HIRE_BASE * (HIRE_EXPO ** alive_count))

    @staticmethod
    def upgrade_cost(level):
        return int(UPGRADE_COST_BASE * (UPGRADE_COST_EXPO ** (level - 1)))

    @staticmethod
    def heal_cost(arena_tier):
        return int(HEAL_BASE * (HEAL_TIER_MULT ** (arena_tier - 1)))

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

        # Legacy compat
        self.base_attack = 0
        self.base_defense = 0
        self.base_hp = 0

        self.alive = True
        self.injuries = 0
        self.injuries_healed = 0
        self.kills = 0
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
        """Relic upgrade bonus: (STR+AGI+VIT) * (lvl*UPGRADE%) / SPLIT for atk/def, xHP_MULT for hp."""
        item = self.equipment.get("relic")
        if not item:
            return 0
        lvl = item.get("upgrade_level", 0)
        if lvl <= 0:
            return 0
        all_stats = self.strength + self.agility + self.vitality
        pct = lvl * UPGRADE_BONUS_PER_LEVEL / 100
        base = int(all_stats * pct / RELIC_STAT_SPLIT)
        if stat == "hp":
            return base * ACCESSORY_HP_MULT
        return base

    def item_total_stats(self, slot):
        """Return total (atk, def, hp) an equipped item gives including upgrades."""
        item = self.equipment.get(slot)
        if not item:
            return 0, 0, 0
        atk = item.get("atk", 0)
        dfn = item.get("def", 0)
        hp = item.get("hp", 0)
        lvl = item.get("upgrade_level", 0)
        if lvl > 0:
            pct = lvl * UPGRADE_BONUS_PER_LEVEL / 100
            if slot == "weapon":
                atk += int((self.strength + self.agility) * pct)
            elif slot == "armor":
                dfn += int((self.strength + self.vitality) * pct)
            elif slot == "accessory":
                hp += int((self.agility + self.vitality) * pct) * ACCESSORY_HP_MULT
            elif slot == "relic":
                all_stats = self.strength + self.agility + self.vitality
                bonus = int(all_stats * pct / RELIC_STAT_SPLIT)
                atk += bonus
                dfn += bonus
                hp += bonus * ACCESSORY_HP_MULT
        return atk, dfn, hp

    @property
    def equip_atk(self):
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get("atk", 0)
                if slot == "weapon":
                    lvl = item.get("upgrade_level", 0)
                    if lvl > 0:
                        total += int((self.strength + self.agility) * (lvl * UPGRADE_BONUS_PER_LEVEL) / 100)
        total += self._relic_bonus("atk")
        return total

    @property
    def equip_def(self):
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get("def", 0)
                if slot == "armor":
                    lvl = item.get("upgrade_level", 0)
                    if lvl > 0:
                        total += int((self.strength + self.vitality) * (lvl * UPGRADE_BONUS_PER_LEVEL) / 100)
        total += self._relic_bonus("def")
        return total

    @property
    def equip_hp(self):
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get("hp", 0)
                if slot == "accessory":
                    lvl = item.get("upgrade_level", 0)
                    if lvl > 0:
                        total += int((self.agility + self.vitality) * (lvl * UPGRADE_BONUS_PER_LEVEL) / 100) * ACCESSORY_HP_MULT
        total += self._relic_bonus("hp")
        return total

    @property
    def attack(self):
        return (self.strength * FIGHTER_ATK_PER_STR + self.base_attack
                + (self.level - 1) * FIGHTER_ATK_PER_LEVEL + self.equip_atk)

    @property
    def defense(self):
        return self.vitality + self.base_defense + self.equip_def

    @property
    def max_hp(self):
        base = (FIGHTER_BASE_HP + self.vitality * FIGHTER_HP_PER_VIT
                + self.base_hp + (self.level - 1) * FIGHTER_HP_PER_LEVEL)
        return int(base * self.hp_mult) + self.equip_hp

    @property
    def crit_chance(self):
        return self.agility / (self.agility + CRIT_K) + self.crit_bonus

    @property
    def crit_mult(self):
        return CRIT_MULT_BASE + self.agility * CRIT_MULT_PER_AGI

    @property
    def dodge_chance(self):
        raw = self.agility * DODGE_AGI_FACTOR + self.dodge_bonus
        return 1.0 - 1.0 / (1.0 + raw * DODGE_DIMINISH_FACTOR)

    @property
    def upgrade_cost(self):
        return DifficultyScaler.upgrade_cost(self.level)

    @property
    def power_rating(self):
        return self.attack + self.defense + self.max_hp // 5

    @property
    def death_chance(self):
        return min(DEATH_CHANCE_CAP,
                   DEATH_CHANCE_BASE + self.injuries * DEATH_CHANCE_PER_INJURY)

    @property
    def class_name(self):
        return FIGHTER_CLASSES.get(self.fighter_class, {}).get("name", "Unknown")

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
        """Level up: gain stat points based on class."""
        self.level += 1
        self.unused_points += self.points_per_level
        self.hp = self.max_hp

    def heal(self):
        self.hp = self.max_hp

    def check_permadeath(self):
        if random.random() < self.death_chance:
            self.alive = False
            return True
        self.injuries += 1
        return False

    def get_injury_heal_cost(self):
        return INJURY_HEAL_BASE_COST * (1 + self.injuries_healed) * max(1, self.level)

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
            "injuries": self.injuries,
            "injuries_healed": self.injuries_healed,
            "kills": self.kills,
            "equipment": self.equipment,
            "on_expedition": self.on_expedition,
            "expedition_id": self.expedition_id,
            "expedition_end": self.expedition_end,
        }

    @classmethod
    def from_dict(cls, data):
        g = cls.__new__(cls)
        g.name = data["name"]
        g.fighter_class = data.get("fighter_class", "mercenary")
        g.level = data["level"]
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
        g.injuries = data.get("injuries", 0)
        g.injuries_healed = data.get("injuries_healed", 0)
        g.kills = data.get("kills", 0)
        equip = data.get("equipment", {"weapon": None, "armor": None, "accessory": None})
        if "relic" not in equip:
            equip["relic"] = None
        g.equipment = equip
        # Migrate old relics list: first relic → equipment slot, rest → _overflow_relics
        g._overflow_relics = []
        old_relics = data.get("relics", [])
        if old_relics:
            for i, r in enumerate(old_relics):
                if "slot" not in r:
                    r["slot"] = "relic"
                if "rarity" not in r:
                    r["rarity"] = RARITY_COMMON
                if "id" not in r:
                    r["id"] = r.get("name", "relic").lower().replace(" ", "_")
                if "cost" not in r:
                    r["cost"] = 30
                if i == 0 and g.equipment.get("relic") is None:
                    g.equipment["relic"] = r
                else:
                    g._overflow_relics.append(r)
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
    def create_boss(cls, arena_tier):
        boss_tier = arena_tier + BOSS_TIER_OFFSET
        boss = cls(tier=boss_tier)
        boss.max_hp = int(boss.max_hp * BOSS_HP_MULT)
        boss.hp = boss.max_hp
        boss.attack = int(boss.attack * BOSS_ATK_MULT)
        boss.defense = int(boss.defense * BOSS_DEF_MULT)
        boss.gold_reward = int(boss.gold_reward * BOSS_GOLD_MULT)
        boss.crit_chance = min(BOSS_CRIT_MIN, boss.crit_chance + BOSS_CRIT_BONUS)
        boss.dodge_chance = 0
        boss.name = f"BOSS: {get_boss_name(arena_tier)}"
        boss.is_boss = True
        return boss



SHOP_ITEMS = []
