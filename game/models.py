"""Game data models — gladiators, enemies, items."""

import random

GLADIATOR_NAMES = [
    "Spartacus", "Maximus", "Crixus", "Flamma", "Priscus",
    "Verus", "Commodus", "Tetraites", "Carpophorus", "Hermes",
    "Marcus", "Lucius", "Gaius", "Titus", "Decimus",
]

ENEMY_TITLES = [
    "Wild Beast", "Slave Fighter", "Pit Brawler", "Arena Thug",
    "Veteran Gladiator", "Champion", "War Chief", "Colosseum Legend",
]


class Gladiator:
    """Player-owned gladiator."""

    def __init__(self, name=None, level=1):
        self.name = name or random.choice(GLADIATOR_NAMES)
        self.level = level
        self.base_attack = random.randint(8, 12)
        self.base_defense = random.randint(3, 7)
        self.base_hp = random.randint(40, 60)
        self.hp = self.max_hp

    @property
    def attack(self):
        return self.base_attack + (self.level - 1) * 3

    @property
    def defense(self):
        return self.base_defense + (self.level - 1) * 2

    @property
    def max_hp(self):
        return self.base_hp + (self.level - 1) * 15

    @property
    def upgrade_cost(self):
        return int(50 * (1.5 ** (self.level - 1)))

    def heal(self):
        self.hp = self.max_hp

    def take_damage(self, raw_dmg):
        reduced = max(1, raw_dmg - self.defense // 2)
        self.hp = max(0, self.hp - reduced)
        return reduced

    def deal_damage(self):
        variance = random.uniform(0.8, 1.2)
        return int(self.attack * variance)

    def to_dict(self):
        return {
            "name": self.name,
            "level": self.level,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_hp": self.base_hp,
            "hp": self.hp,
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
        return g


class Enemy:
    """Auto-generated arena opponent."""

    def __init__(self, tier=1):
        self.tier = tier
        title_idx = min(tier - 1, len(ENEMY_TITLES) - 1)
        self.name = ENEMY_TITLES[title_idx]
        self.attack = 6 + tier * 4
        self.defense = 2 + tier * 2
        self.max_hp = 30 + tier * 20
        self.hp = self.max_hp
        self.gold_reward = int(20 * (1.3 ** (tier - 1)))

    def take_damage(self, raw_dmg):
        reduced = max(1, raw_dmg - self.defense // 2)
        self.hp = max(0, self.hp - reduced)
        return reduced

    def deal_damage(self):
        variance = random.uniform(0.8, 1.2)
        return int(self.attack * variance)


SHOP_ITEMS = [
    {
        "id": "idle_boost_1",
        "name": "Training Dummy",
        "desc": "+1 gold/sec idle income",
        "cost": 100,
        "effect": {"idle_gold_rate": 1.0},
    },
    {
        "id": "idle_boost_2",
        "name": "Gladiator School",
        "desc": "+5 gold/sec idle income",
        "cost": 500,
        "effect": {"idle_gold_rate": 5.0},
    },
    {
        "id": "idle_boost_3",
        "name": "Colosseum Sponsorship",
        "desc": "+25 gold/sec idle income",
        "cost": 2500,
        "effect": {"idle_gold_rate": 25.0},
    },
    {
        "id": "heal_potion",
        "name": "Healing Potion",
        "desc": "Fully heal active gladiator",
        "cost": 30,
        "effect": {"heal": True},
    },
    {
        "id": "atk_scroll",
        "name": "Scroll of Might",
        "desc": "+5 base ATK to active gladiator",
        "cost": 300,
        "effect": {"base_attack": 5},
    },
    {
        "id": "def_scroll",
        "name": "Scroll of Iron Skin",
        "desc": "+5 base DEF to active gladiator",
        "cost": 300,
        "effect": {"base_defense": 5},
    },
]
