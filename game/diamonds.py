# Build: 1
"""Diamond currency data — in-game shop items and real-money IAP bundles.

Split out of achievements.py because these are unrelated to progression
milestones; they are premium-currency inventory and the Google Play
billing price tiers. Keeping them here makes the achievements file a
pure milestone-definition file.
"""


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


DIAMOND_BUNDLES = [
    {"id": "gems_100", "diamonds": 100, "price": "20 UAH", "price_usd": "$0.49"},
    {"id": "gems_500", "diamonds": 500, "price": "59 UAH", "price_usd": "$1.49"},
    {"id": "gems_1000", "diamonds": 1000, "price": "79 UAH", "price_usd": "$1.99"},
    {"id": "gems_2500", "diamonds": 2500, "price": "179 UAH", "price_usd": "$4.49",
     "bonus": "+10%"},
    {"id": "gems_6000", "diamonds": 6000, "price": "399 UAH", "price_usd": "$9.99",
     "bonus": "+20%"},
]
