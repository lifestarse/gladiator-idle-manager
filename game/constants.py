# Build: 6
"""
Game-wide constants — replaces magic numbers scattered across the codebase.

Naming convention: CATEGORY_NAME, e.g. HEAL_GOLD_PER_HP, BATTLE_AUTO_INTERVAL.
"""

# --- Economy ---
STARTING_GOLD = 100.0
HEAL_GOLD_PER_HP = 10          # 1 gold heals 10 HP (cost = missing / 10)
UPGRADE_BONUS_PER_LEVEL = 20   # +20% per upgrade level

# --- Battle ---
BATTLE_AUTO_INTERVAL = 0.8     # seconds between auto-battle turns
LOW_HP_THRESHOLD = 0.35        # HP fraction below which bars turn red
POPUP_DISMISS_DELAY = 3.0      # seconds before auto-dismissing popups

# --- Relic / Accessory multipliers ---
RELIC_STAT_SPLIT = 3           # relic bonus is split 3 ways (ATK/DEF/HP)
ACCESSORY_HP_MULT = 10         # accessory HP bonus multiplied by 10

# --- Economy: diamond shop / expedition ---
RENAME_COST_DIAMONDS = 25
EXPEDITION_SLOT_BASE_COST = 200  # doubles each purchase

# --- Injury healing ---
INJURY_HEAL_BASE_COST = 50       # base gold cost to heal an injury

# --- Shard tiers ---
SHARD_TIER_COUNT = 5             # tier 1-5

# --- Fighter base stats (models.py) ---
FIGHTER_BASE_HP = 30             # base HP before vitality/level
FIGHTER_HP_PER_VIT = 8           # +8 HP per vitality point
FIGHTER_HP_PER_LEVEL = 5         # +5 HP per level above 1
FIGHTER_ATK_PER_STR = 2          # +2 ATK per strength point
FIGHTER_ATK_PER_LEVEL = 1        # +1 ATK per level above 1
FIGHTER_STARTING_POINTS = 3      # unused stat points on creation

# --- Crit / Dodge / Death (models.py) ---
CRIT_K = 25                      # agility / (agility + K)
CRIT_MULT_BASE = 1.8            # base crit damage multiplier
CRIT_MULT_PER_AGI = 0.04        # extra crit mult per agility point
DODGE_AGI_FACTOR = 0.02          # agility contribution to dodge
DODGE_DIMINISH_FACTOR = 0.6      # diminishing-returns exponent
FIGHTER_CRIT_CAP = 0.95          # max crit chance for fighters
FIGHTER_DODGE_CAP = 0.85         # max dodge chance for fighters
PERK_POINT_EVERY_N_LEVELS = 5    # earn 1 perk point every N levels

DEATH_CHANCE_BASE = 0.05         # base death chance per injury check
DEATH_CHANCE_CAP = 0.60          # hard cap on death chance

# --- Injury severity → death chance contribution ---
SEVERITY_DEATH_CHANCE = {
    "minor": 0.03,
    "moderate": 0.06,
    "severe": 0.10,
    "permanent": 0.15,
}

# --- Combat damage (models.py) ---
DAMAGE_VARIANCE_LOW = 0.70       # min damage roll multiplier
DAMAGE_VARIANCE_HIGH = 1.30      # max damage roll multiplier
DEFENSE_DIVISOR = 100            # damage / (1 + def/DIVISOR)

# --- Rarity max upgrade levels (models.py) ---
MAX_UPGRADE_COMMON = 5
MAX_UPGRADE_UNCOMMON = 10
MAX_UPGRADE_RARE = 15
MAX_UPGRADE_EPIC = 20
MAX_UPGRADE_LEGENDARY = 25

# --- DifficultyScaler: enemy stats (models.py) ---
ENEMY_ATK_BASE = 7
ENEMY_ATK_PER_TIER = 3
ENEMY_ATK_EXPO = 1.08
ENEMY_DEF_BASE = 2
ENEMY_DEF_PER_TIER = 2
ENEMY_DEF_EXPO = 1.06
ENEMY_HP_BASE = 35
ENEMY_HP_PER_TIER = 15
ENEMY_HP_EXPO = 1.10

# --- DifficultyScaler: economy scaling (models.py) ---
REWARD_BASE = 15
REWARD_EXPO = 1.12
HIRE_BASE = 40
HIRE_EXPO = 1.6
UPGRADE_COST_BASE = 35
UPGRADE_COST_EXPO = 1.45
HEAL_BASE = 20
HEAL_TIER_MULT = 1.12
SURGEON_BASE = 80
SURGEON_INFLATION = 1.25

# --- Enemy crit / dodge (models.py) ---
ENEMY_CRIT_CAP = 0.30
ENEMY_CRIT_BASE = 0.05
ENEMY_CRIT_PER_TIER = 0.015
ENEMY_DODGE_CAP = 0.20
ENEMY_DODGE_PER_TIER = 0.01
ENEMY_CRIT_MULT = 1.8

# --- Boss multipliers (models.py) ---
BOSS_TIER_OFFSET = 2
BOSS_HP_MULT = 10
BOSS_ATK_MULT = 1.5
BOSS_DEF_MULT = 1.3
BOSS_GOLD_MULT = 10
BOSS_CRIT_BONUS = 0.10
BOSS_CRIT_MIN = 0.35

# --- HP healing costs (engine.py) ---
HP_HEAL_TIER_MULT = 1.2         # heal cost scales with tier
HP_HEAL_DIVISOR = 10            # cost = missing_hp / divisor

# --- Dynamic shop: tonics (models.py) ---
TONIC_BASE_COST = 150
TONIC_TIER_EXPO = 1.10

# --- Economy tier-band scaling ---
# Healing/reward multiplier per tier band (lower = slower cost growth at high tiers)
TIER_BAND_MULT = {
    (1, 15): 1.20,     # early game: steep growth
    (16, 30): 1.12,    # mid game: moderate
    (31, 50): 1.08,    # late game: gentle
    (51, 100): 1.05,   # endgame: near-flat
}

# --- Procedural enemy generation (T1-T100) ---
PROC_BASE_STR_T1 = 3
PROC_BASE_AGI_T1 = 2
PROC_BASE_VIT_T1 = 5
PROC_GROWTH_RATE = 1.18

# Role multipliers: overall stat multiplier for each enemy role
ROLE_MULT = {
    "swarm": 0.6,
    "soldier": 1.0,
    "bruiser": 1.3,
    "elite": 1.6,
    "assassin": 0.9,
    "guardian": 1.1,
}

# Role stat biases: per-stat multiplier for each role
ROLE_STAT_MULT = {
    "swarm": {"str": 1.0, "agi": 1.0, "vit": 1.0},
    "soldier": {"str": 1.0, "agi": 1.0, "vit": 1.0},
    "bruiser": {"str": 1.2, "agi": 0.8, "vit": 1.0},
    "elite": {"str": 1.1, "agi": 1.1, "vit": 1.0},
    "assassin": {"str": 1.4, "agi": 1.0, "vit": 0.6},
    "guardian": {"str": 0.7, "agi": 0.8, "vit": 1.5},
}

# Stat bias multipliers: boost primary, reduce others
STAT_BIAS_MULT = {
    "balanced": {"str": 1.0, "agi": 1.0, "vit": 1.0},
    "str": {"str": 1.3, "agi": 0.9, "vit": 0.9},
    "agi": {"str": 0.9, "agi": 1.3, "vit": 0.9},
    "vit": {"str": 0.9, "agi": 0.9, "vit": 1.3},
}

# Boss HP multipliers (procedural enemies)
PROC_BOSS_HP_MULT = 10
PROC_MILESTONE_BOSS_HP_MULT = 15  # every 10 tiers
