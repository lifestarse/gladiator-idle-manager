# Build: 10
"""
Achievement system — earn diamonds for milestones.
Diamonds are premium currency for special features.
"""

import logging
from game.achievements_checks import _build_check

_log = logging.getLogger(__name__)




def build_achievements_from_json(json_list):
    """Convert JSON achievement list to runtime format with check functions."""
    result = []
    for entry in json_list:
        condition = entry.get("condition")
        if not condition:
            continue
        ach = {
            "id": entry["id"],
            "name": entry["name"],
            "desc": entry["desc"],
            "diamonds": entry["diamonds"],
            "check": _build_check(condition),
        }
        result.append(ach)
    return result


# --- Achievement definitions (hardcoded fallback) ---

ACHIEVEMENTS = [
    # Combat achievements
    {"id": "first_blood", "name": "First Blood",
     "desc": "Win your first battle", "diamonds": 50,
     "check": lambda e: e.wins >= 1},
    {"id": "warrior_10", "name": "Seasoned Warrior",
     "desc": "Win 10 battles", "diamonds": 75,
     "check": lambda e: e.wins >= 10},
    {"id": "warrior_50", "name": "Arena Veteran",
     "desc": "Win 50 battles", "diamonds": 100,
     "check": lambda e: e.wins >= 50},
    {"id": "warrior_200", "name": "Living Legend",
     "desc": "Win 200 battles", "diamonds": 150,
     "check": lambda e: e.wins >= 200},
    {"id": "boss_slayer", "name": "Boss Slayer",
     "desc": "Defeat your first boss", "diamonds": 100,
     "check": lambda e: e.bosses_killed >= 1},
    {"id": "boss_10", "name": "Titan Breaker",
     "desc": "Defeat 10 bosses", "diamonds": 150,
     "check": lambda e: e.bosses_killed >= 10},

    # Progression
    {"id": "tier_5", "name": "Rising Star",
     "desc": "Reach arena tier 5", "diamonds": 75,
     "check": lambda e: e.arena_tier >= 5},
    {"id": "tier_10", "name": "Pit Champion",
     "desc": "Reach arena tier 10", "diamonds": 100,
     "check": lambda e: e.arena_tier >= 10},
    {"id": "tier_20", "name": "Warlord",
     "desc": "Reach arena tier 20", "diamonds": 150,
     "check": lambda e: e.arena_tier >= 20},

    # Roster
    {"id": "recruit_3", "name": "Squad Leader",
     "desc": "Have 3 fighters alive", "diamonds": 50,
     "check": lambda e: len([f for f in e.fighters if f.alive]) >= 3},
    {"id": "recruit_6", "name": "War Band",
     "desc": "Have 6 fighters alive", "diamonds": 75,
     "check": lambda e: len([f for f in e.fighters if f.alive]) >= 6},
    {"id": "recruit_10", "name": "Legion Commander",
     "desc": "Have 10 fighters alive", "diamonds": 100,
     "check": lambda e: len([f for f in e.fighters if f.alive]) >= 10},
    {"id": "level_10", "name": "Master Trainer",
     "desc": "Train a fighter to Lv.10", "diamonds": 100,
     "check": lambda e: any(f.level >= 10 for f in e.fighters if f.alive)},
    {"id": "level_20", "name": "Grand Master",
     "desc": "Train a fighter to Lv.20", "diamonds": 150,
     "check": lambda e: any(f.level >= 20 for f in e.fighters if f.alive)},

    # Economy
    {"id": "gold_1k", "name": "Coin Collector",
     "desc": "Earn 1,000 total gold", "diamonds": 50,
     "check": lambda e: e.total_gold_earned >= 1000},
    {"id": "gold_10k", "name": "Wealthy",
     "desc": "Earn 10,000 total gold", "diamonds": 75,
     "check": lambda e: e.total_gold_earned >= 10000},
    {"id": "gold_100k", "name": "Tycoon",
     "desc": "Earn 100,000 total gold", "diamonds": 100,
     "check": lambda e: e.total_gold_earned >= 100000},

    # Death & danger
    {"id": "first_death", "name": "Blood Price",
     "desc": "Lose a fighter to permadeath", "diamonds": 50,
     "check": lambda e: e.total_deaths >= 1},
    {"id": "graveyard_5", "name": "Grave Digger",
     "desc": "Lose 5 fighters to permadeath", "diamonds": 75,
     "check": lambda e: e.total_deaths >= 5},
    {"id": "survivor", "name": "Scarred Survivor",
     "desc": "Have a fighter survive with 5+ injuries", "diamonds": 100,
     "check": lambda e: any(f.injury_count >= 5 for f in e.fighters if f.alive)},

    # Equipment & relics
    {"id": "first_equip", "name": "Armed & Ready",
     "desc": "Equip any item from the Anvil", "diamonds": 50,
     "check": lambda e: any(
         any(f.equipment.get(s) for s in ["weapon", "armor", "accessory"])
         for f in e.fighters if f.alive
     )},
    {"id": "legendary_equip", "name": "Legendary Wielder",
     "desc": "Equip a legendary item", "diamonds": 100,
     "check": lambda e: any(
         any(f.equipment.get(s, {}).get("rarity") == "legendary" if f.equipment.get(s) else False
             for s in ["weapon", "armor", "accessory"])
         for f in e.fighters if f.alive
     )},
    {"id": "relic_hunter", "name": "Relic Hunter",
     "desc": "Collect 5 relics", "diamonds": 75,
     "check": lambda e: (
         sum(1 for f in e.fighters if f.equipment.get("relic")) +
         sum(1 for i in e.inventory if i.get("slot") == "relic")
     ) >= 5},
    {"id": "relic_hoarder", "name": "Relic Hoarder",
     "desc": "Collect 20 relics", "diamonds": 100,
     "check": lambda e: (
         sum(1 for f in e.fighters if f.equipment.get("relic")) +
         sum(1 for i in e.inventory if i.get("slot") == "relic")
     ) >= 20},

    # Expeditions
    {"id": "explorer", "name": "Explorer",
     "desc": "Complete 10 expeditions", "diamonds": 75,
     "check": lambda e: len(e.expedition_log) >= 10},
    {"id": "void_walker", "name": "Void Walker",
     "desc": "Return alive from the Void Rift", "diamonds": 150,
     "check": lambda e: any("Void Rift" in log and "returned" in log
                            for log in e.expedition_log)},

    # Story
    {"id": "ch1_complete", "name": "Chapter I",
     "desc": "Complete the first story chapter", "diamonds": 100,
     "check": lambda e: e.story_chapter >= 2},
    {"id": "ch3_complete", "name": "Chapter III",
     "desc": "Complete story chapter 3", "diamonds": 100,
     "check": lambda e: e.story_chapter >= 4},
    {"id": "story_complete", "name": "The End...?",
     "desc": "Complete the main story", "diamonds": 150,
     "check": lambda e: e.story_chapter >= 6},
]


# --- Diamond shop items ---

DIAMOND_SHOP = [
    {
        "id": "revive_token",
        "name": "Soul Stone",
        "desc": "Revive a dead fighter (full HP, clear injuries)",
        "cost": 100,
        "category": "consumable",
    },
    {
        "id": "heal_all_injuries_diamond",
        "name": "Divine Surgeon",
        "desc": "Heal ALL injuries on ALL fighters (10 diamonds per injury, min 10)",
        "cost": 0,
        "category": "consumable",
    },
    {
        "id": "extra_expedition_slot",
        "name": "Scout Network",
        "desc": "Send +1 fighter on expeditions simultaneously",
        "cost": 200,
        "category": "permanent",
    },
    {
        "id": "golden_armor",
        "name": "Golden War Set",
        "desc": "Blade of Ruin + Dragonscale Aegis + Crown of Ash",
        "cost": 3000,
        "category": "equipment",
    },
    {
        "id": "name_change",
        "name": "Identity Scroll",
        "desc": "Rename any fighter",
        "cost": 25,
        "category": "cosmetic",
    },
]

# Diamond purchase tiers (real money)
DIAMOND_BUNDLES = [
    {"id": "gems_100", "diamonds": 100, "price": "20 UAH", "price_usd": "$0.49"},
    {"id": "gems_500", "diamonds": 500, "price": "59 UAH", "price_usd": "$1.49"},
    {"id": "gems_1000", "diamonds": 1000, "price": "79 UAH", "price_usd": "$1.99"},
    {"id": "gems_2500", "diamonds": 2500, "price": "179 UAH", "price_usd": "$4.49",
     "bonus": "+10%"},
    {"id": "gems_6000", "diamonds": 6000, "price": "399 UAH", "price_usd": "$9.99",
     "bonus": "+20%"},
]
