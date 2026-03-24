"""Game data models — fighters, enemies, equipment, expeditions, economy."""

import random
import time
import math

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

# --- Rarity system ---

RARITY_COMMON = "common"
RARITY_UNCOMMON = "uncommon"
RARITY_RARE = "rare"
RARITY_EPIC = "epic"
RARITY_LEGENDARY = "legendary"

RARITY_COLORS = {
    RARITY_COMMON: (0.6, 0.6, 0.6, 1),
    RARITY_UNCOMMON: (0.3, 0.8, 0.3, 1),
    RARITY_RARE: (0.3, 0.5, 1.0, 1),
    RARITY_EPIC: (0.7, 0.3, 0.9, 1),
    RARITY_LEGENDARY: (1.0, 0.78, 0.2, 1),
}

RARITY_MULTIPLIER = {
    RARITY_COMMON: 1.0,
    RARITY_UNCOMMON: 1.3,
    RARITY_RARE: 1.7,
    RARITY_EPIC: 2.2,
    RARITY_LEGENDARY: 3.0,
}

# --- Equipment ---

EQUIPMENT_SLOTS = ["weapon", "armor", "accessory"]

FORGE_WEAPONS = [
    {"id": "rusty_blade", "name": "Rusty Blade", "slot": "weapon", "rarity": RARITY_COMMON,
     "atk": 3, "def": 0, "hp": 0, "cost": 60},
    {"id": "iron_sword", "name": "Iron Sword", "slot": "weapon", "rarity": RARITY_COMMON,
     "atk": 6, "def": 0, "hp": 0, "cost": 150},
    {"id": "steel_falcata", "name": "Steel Falcata", "slot": "weapon", "rarity": RARITY_UNCOMMON,
     "atk": 10, "def": 0, "hp": 5, "cost": 350},
    {"id": "obsidian_edge", "name": "Obsidian Edge", "slot": "weapon", "rarity": RARITY_RARE,
     "atk": 16, "def": 2, "hp": 0, "cost": 800},
    {"id": "inferno_cleaver", "name": "Inferno Cleaver", "slot": "weapon", "rarity": RARITY_EPIC,
     "atk": 24, "def": 0, "hp": 10, "cost": 2000},
    {"id": "blade_of_ruin", "name": "Blade of Ruin", "slot": "weapon", "rarity": RARITY_LEGENDARY,
     "atk": 35, "def": 5, "hp": 20, "cost": 5000},
]

FORGE_ARMOR = [
    {"id": "leather_vest", "name": "Leather Vest", "slot": "armor", "rarity": RARITY_COMMON,
     "atk": 0, "def": 3, "hp": 10, "cost": 80},
    {"id": "chain_mail", "name": "Chain Mail", "slot": "armor", "rarity": RARITY_COMMON,
     "atk": 0, "def": 6, "hp": 15, "cost": 200},
    {"id": "bronze_plate", "name": "Bronze Plate", "slot": "armor", "rarity": RARITY_UNCOMMON,
     "atk": 0, "def": 10, "hp": 25, "cost": 450},
    {"id": "shadow_guard", "name": "Shadow Guard", "slot": "armor", "rarity": RARITY_RARE,
     "atk": 3, "def": 15, "hp": 30, "cost": 1000},
    {"id": "titan_shell", "name": "Titan Shell", "slot": "armor", "rarity": RARITY_EPIC,
     "atk": 0, "def": 22, "hp": 50, "cost": 2500},
    {"id": "dragonscale", "name": "Dragonscale Aegis", "slot": "armor", "rarity": RARITY_LEGENDARY,
     "atk": 5, "def": 30, "hp": 80, "cost": 6000},
]

FORGE_ACCESSORIES = [
    {"id": "bone_charm", "name": "Bone Charm", "slot": "accessory", "rarity": RARITY_COMMON,
     "atk": 2, "def": 2, "hp": 5, "cost": 70},
    {"id": "iron_ring", "name": "Iron Ring", "slot": "accessory", "rarity": RARITY_UNCOMMON,
     "atk": 4, "def": 4, "hp": 10, "cost": 250},
    {"id": "blood_pendant", "name": "Blood Pendant", "slot": "accessory", "rarity": RARITY_RARE,
     "atk": 8, "def": 3, "hp": 20, "cost": 600},
    {"id": "void_amulet", "name": "Void Amulet", "slot": "accessory", "rarity": RARITY_EPIC,
     "atk": 12, "def": 8, "hp": 30, "cost": 1500},
    {"id": "crown_of_ash", "name": "Crown of Ash", "slot": "accessory", "rarity": RARITY_LEGENDARY,
     "atk": 18, "def": 12, "hp": 50, "cost": 4000},
]

ALL_FORGE_ITEMS = FORGE_WEAPONS + FORGE_ARMOR + FORGE_ACCESSORIES

# --- Expeditions ---

EXPEDITIONS = [
    {
        "id": "dark_tunnels",
        "name": "Dark Tunnels",
        "desc": "Scout the tunnels beneath the arena",
        "duration": 60,
        "min_level": 1,
        "danger": 0.05,
        "gold_range": (30, 80),
        "relic_chance": 0.15,
        "relic_pool": [RARITY_COMMON, RARITY_UNCOMMON],
    },
    {
        "id": "bandit_outpost",
        "name": "Bandit Outpost",
        "desc": "Raid a bandit camp in the hills",
        "duration": 180,
        "min_level": 3,
        "danger": 0.10,
        "gold_range": (80, 200),
        "relic_chance": 0.25,
        "relic_pool": [RARITY_UNCOMMON, RARITY_RARE],
    },
    {
        "id": "cursed_ruins",
        "name": "Cursed Ruins",
        "desc": "Ancient temple with deadly traps",
        "duration": 300,
        "min_level": 5,
        "danger": 0.18,
        "gold_range": (150, 400),
        "relic_chance": 0.35,
        "relic_pool": [RARITY_RARE, RARITY_EPIC],
    },
    {
        "id": "dragon_wastes",
        "name": "Dragon Wastes",
        "desc": "Scorched lands where few return",
        "duration": 600,
        "min_level": 8,
        "danger": 0.25,
        "gold_range": (300, 800),
        "relic_chance": 0.45,
        "relic_pool": [RARITY_EPIC, RARITY_LEGENDARY],
    },
    {
        "id": "void_rift",
        "name": "Void Rift",
        "desc": "A tear in reality. Maximum risk.",
        "duration": 900,
        "min_level": 12,
        "danger": 0.35,
        "gold_range": (500, 1500),
        "relic_chance": 0.55,
        "relic_pool": [RARITY_LEGENDARY],
    },
]

# --- Relics ---

RELICS = {
    RARITY_COMMON: [
        {"name": "Cracked Idol", "atk": 2, "def": 1, "hp": 5},
        {"name": "Dusty Talisman", "atk": 1, "def": 2, "hp": 8},
        {"name": "Worn Signet", "atk": 3, "def": 0, "hp": 3},
    ],
    RARITY_UNCOMMON: [
        {"name": "Serpent Fang", "atk": 5, "def": 2, "hp": 10},
        {"name": "Stone of Vigor", "atk": 2, "def": 5, "hp": 15},
        {"name": "Wolf Pelt Cloak", "atk": 3, "def": 4, "hp": 12},
    ],
    RARITY_RARE: [
        {"name": "Eye of the Storm", "atk": 10, "def": 5, "hp": 20},
        {"name": "Frozen Heart", "atk": 5, "def": 10, "hp": 25},
        {"name": "War Banner", "atk": 8, "def": 8, "hp": 15},
    ],
    RARITY_EPIC: [
        {"name": "Soul Lantern", "atk": 15, "def": 10, "hp": 35},
        {"name": "Titan's Finger", "atk": 10, "def": 15, "hp": 40},
        {"name": "Eclipse Shard", "atk": 18, "def": 8, "hp": 30},
    ],
    RARITY_LEGENDARY: [
        {"name": "Heart of the Colossus", "atk": 25, "def": 20, "hp": 60},
        {"name": "Abyssal Crown", "atk": 30, "def": 15, "hp": 50},
        {"name": "Ember of Creation", "atk": 20, "def": 25, "hp": 70},
    ],
}


# ============================================================
#  DIFFICULTY & ECONOMY SCALING
# ============================================================

class DifficultyScaler:
    """Manages exponential difficulty curve and resource scarcity."""

    # Enemy scaling — exponential growth
    ENEMY_ATK_BASE = 6
    ENEMY_ATK_PER_TIER = 4
    ENEMY_ATK_EXPO = 1.12       # +12% compounding per tier
    ENEMY_DEF_BASE = 2
    ENEMY_DEF_PER_TIER = 2
    ENEMY_DEF_EXPO = 1.10
    ENEMY_HP_BASE = 30
    ENEMY_HP_PER_TIER = 20
    ENEMY_HP_EXPO = 1.15        # HP grows fastest

    # Gold reward — grows slower than enemy power (diminishing returns)
    REWARD_BASE = 20
    REWARD_EXPO = 1.18          # was 1.3 linear, now slower exponential

    # Costs — inflate faster than income
    HIRE_BASE = 50
    HIRE_EXPO = 1.8             # each new fighter costs almost 2x more
    UPGRADE_BASE = 50
    UPGRADE_EXPO = 1.65         # steeper than before (was 1.5)

    # Idle income costs — exponential inflation
    IDLE_COST_INFLATION = 1.35  # each purchase of same tier costs 35% more

    # Heal cost scales with tier
    HEAL_BASE = 30
    HEAL_TIER_MULT = 1.25

    # Surgeon scales with injuries cured total
    SURGEON_BASE = 200
    SURGEON_INFLATION = 1.4

    @staticmethod
    def enemy_stats(tier):
        s = DifficultyScaler
        atk = int((s.ENEMY_ATK_BASE + tier * s.ENEMY_ATK_PER_TIER)
                   * (s.ENEMY_ATK_EXPO ** (tier - 1)))
        defense = int((s.ENEMY_DEF_BASE + tier * s.ENEMY_DEF_PER_TIER)
                       * (s.ENEMY_DEF_EXPO ** (tier - 1)))
        hp = int((s.ENEMY_HP_BASE + tier * s.ENEMY_HP_PER_TIER)
                  * (s.ENEMY_HP_EXPO ** (tier - 1)))
        return atk, defense, hp

    @staticmethod
    def enemy_reward(tier):
        s = DifficultyScaler
        return int(s.REWARD_BASE * (s.REWARD_EXPO ** (tier - 1)))

    @staticmethod
    def hire_cost(alive_count):
        s = DifficultyScaler
        return int(s.HIRE_BASE * (s.HIRE_EXPO ** alive_count))

    @staticmethod
    def upgrade_cost(level):
        s = DifficultyScaler
        return int(s.UPGRADE_BASE * (s.UPGRADE_EXPO ** (level - 1)))

    @staticmethod
    def heal_cost(arena_tier):
        s = DifficultyScaler
        return int(s.HEAL_BASE * (s.HEAL_TIER_MULT ** (arena_tier - 1)))

    @staticmethod
    def surgeon_cost(times_used):
        s = DifficultyScaler
        return int(s.SURGEON_BASE * (s.SURGEON_INFLATION ** times_used))


# --- Dynamic market items (costs scale) ---

def get_dynamic_shop_items(arena_tier, idle_purchases, surgeon_uses):
    """Generate shop items with inflating costs."""
    s = DifficultyScaler

    # Idle income items — each purchase inflates cost
    idle_items = [
        {
            "id": "idle_boost_1", "name": "Street Bets",
            "desc": f"+1 gold/sec (bought {idle_purchases.get('idle_boost_1', 0)}x)",
            "cost": int(100 * (s.IDLE_COST_INFLATION ** idle_purchases.get("idle_boost_1", 0))),
            "effect": {"idle_gold_rate": 1.0},
        },
        {
            "id": "idle_boost_2", "name": "Fight Club",
            "desc": f"+5 gold/sec (bought {idle_purchases.get('idle_boost_2', 0)}x)",
            "cost": int(500 * (s.IDLE_COST_INFLATION ** idle_purchases.get("idle_boost_2", 0))),
            "effect": {"idle_gold_rate": 5.0},
        },
        {
            "id": "idle_boost_3", "name": "Noble Patron",
            "desc": f"+25 gold/sec (bought {idle_purchases.get('idle_boost_3', 0)}x)",
            "cost": int(2500 * (s.IDLE_COST_INFLATION ** idle_purchases.get("idle_boost_3", 0))),
            "effect": {"idle_gold_rate": 25.0},
        },
    ]

    consumables = [
        {
            "id": "heal_potion", "name": "Blood Salve",
            "desc": "Fully heal active fighter",
            "cost": DifficultyScaler.heal_cost(arena_tier),
            "effect": {"heal": True},
        },
        {
            "id": "atk_tonic", "name": "Fury Tonic",
            "desc": "+3 base ATK to active fighter",
            "cost": int(300 * (1.2 ** (arena_tier - 1))),
            "effect": {"base_attack": 3},
        },
        {
            "id": "def_tonic", "name": "Stone Brew",
            "desc": "+3 base DEF to active fighter",
            "cost": int(300 * (1.2 ** (arena_tier - 1))),
            "effect": {"base_defense": 3},
        },
        {
            "id": "injury_cure", "name": "Surgeon's Kit",
            "desc": f"Remove 1 injury (used {surgeon_uses}x)",
            "cost": DifficultyScaler.surgeon_cost(surgeon_uses),
            "effect": {"cure_injury": 1},
        },
    ]

    return idle_items + consumables


# ============================================================
#  FIGHTER
# ============================================================

class Fighter:
    """Player-owned arena fighter. Can die permanently."""

    def __init__(self, name=None, level=1):
        self.name = name or random.choice(FIGHTER_NAMES)
        self.level = level
        self.base_attack = random.randint(8, 12)
        self.base_defense = random.randint(3, 7)
        self.base_hp = random.randint(40, 60)
        self.alive = True
        self.injuries = 0
        self.kills = 0
        self.equipment = {"weapon": None, "armor": None, "accessory": None}
        self.relics: list[dict] = []
        self.on_expedition = False
        self.expedition_id = None
        self.expedition_end = 0.0
        self.hp = self.max_hp  # must be after equipment/relics init

    @property
    def equip_atk(self):
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get("atk", 0)
        for r in self.relics:
            total += r.get("atk", 0)
        return total

    @property
    def equip_def(self):
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get("def", 0)
        for r in self.relics:
            total += r.get("def", 0)
        return total

    @property
    def equip_hp(self):
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get("hp", 0)
        for r in self.relics:
            total += r.get("hp", 0)
        return total

    @property
    def attack(self):
        return self.base_attack + (self.level - 1) * 3 + self.equip_atk

    @property
    def defense(self):
        return self.base_defense + (self.level - 1) * 2 + self.equip_def

    @property
    def max_hp(self):
        return self.base_hp + (self.level - 1) * 15 + self.equip_hp

    @property
    def upgrade_cost(self):
        return DifficultyScaler.upgrade_cost(self.level)

    @property
    def power_rating(self):
        return self.attack + self.defense + self.max_hp // 5

    @property
    def death_chance(self):
        base = 0.03
        injury_bonus = self.injuries * 0.04
        return min(0.50, base + injury_bonus)

    def heal(self):
        self.hp = self.max_hp

    def take_damage(self, raw_dmg):
        reduced = max(1, raw_dmg - self.defense // 2)
        self.hp = max(0, self.hp - reduced)
        return reduced

    def deal_damage(self):
        variance = random.uniform(0.8, 1.2)
        return int(self.attack * variance)

    def check_permadeath(self) -> bool:
        if random.random() < self.death_chance:
            self.alive = False
            return True
        self.injuries += 1
        return False

    def equip_item(self, item: dict):
        slot = item["slot"]
        self.equipment[slot] = item
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def add_relic(self, relic: dict):
        self.relics.append(relic)

    def to_dict(self):
        return {
            "name": self.name,
            "level": self.level,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_hp": self.base_hp,
            "hp": self.hp,
            "alive": self.alive,
            "injuries": self.injuries,
            "kills": self.kills,
            "equipment": self.equipment,
            "relics": self.relics,
            "on_expedition": self.on_expedition,
            "expedition_id": self.expedition_id,
            "expedition_end": self.expedition_end,
        }

    @classmethod
    def from_dict(cls, data):
        g = cls.__new__(cls)
        g.name = data["name"]
        g.level = data["level"]
        g.base_attack = data["base_attack"]
        g.base_defense = data["base_defense"]
        g.base_hp = data["base_hp"]
        g.hp = data["hp"]
        g.alive = data.get("alive", True)
        g.injuries = data.get("injuries", 0)
        g.kills = data.get("kills", 0)
        g.equipment = data.get("equipment", {"weapon": None, "armor": None, "accessory": None})
        g.relics = data.get("relics", [])
        g.on_expedition = data.get("on_expedition", False)
        g.expedition_id = data.get("expedition_id")
        g.expedition_end = data.get("expedition_end", 0.0)
        return g


Gladiator = Fighter


# ============================================================
#  ENEMY (with exponential scaling)
# ============================================================

class Enemy:
    """Arena opponent with exponential stat growth."""

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

    def take_damage(self, raw_dmg):
        reduced = max(1, raw_dmg - self.defense // 2)
        self.hp = max(0, self.hp - reduced)
        return reduced

    def deal_damage(self):
        variance = random.uniform(0.8, 1.2)
        return int(self.attack * variance)


# Legacy flat list for backward compat (forge still uses it)
SHOP_ITEMS = []
