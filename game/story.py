# Build: 2
"""
Story campaign — narrative chapters with tutorial integrated.

Story unfolds as the player progresses through arena tiers.
Each chapter has dialogue, a story boss, and unlocks new features.
Tutorial is woven into Chapter 1.
"""

# --- Tutorial steps (shown during Chapter 1) ---

TUTORIAL_STEPS = [
    {
        "id": "welcome",
        "trigger": "first_launch",
        "title": "Welcome to the Pit",
        "lines": [
            "You wake up in chains. The crowd roars above.",
            "A grizzled man tosses you a rusty blade.",
            "'Fight or die. That's how it works down here.'",
            "TAP 'FIGHT' to attack the enemy.",
        ],
    },
    {
        "id": "first_win",
        "trigger": "wins >= 1",
        "title": "First Blood",
        "lines": [
            "The crowd cheers. Gold coins rain into the pit.",
            "Gold lets you recruit more fighters and buy equipment.",
            "Check the SQUAD tab to manage your fighters.",
        ],
    },
    {
        "id": "hire_fighter",
        "trigger": "fighters >= 2",
        "title": "Strength in Numbers",
        "lines": [
            "'One blade breaks easy. A dozen? That's an army.'",
            "All your fighters now battle together in the Pit!",
            "The more fighters you have, the stronger your force.",
        ],
    },
    {
        "id": "discover_forge",
        "trigger": "wins >= 5",
        "title": "The Anvil",
        "lines": [
            "An old blacksmith eyes you from the shadows.",
            "'I can forge weapons and armor... if the gold's right.'",
            "Visit THE ANVIL to equip your fighters with gear.",
        ],
    },
    {
        "id": "discover_hunts",
        "trigger": "wins >= 10",
        "title": "Beyond the Walls",
        "lines": [
            "Rumors spread of treasure in the tunnels below.",
            "Send fighters on HUNTS to find gold and relics.",
            "Warning: expeditions carry real danger.",
        ],
    },
    {
        "id": "first_death",
        "trigger": "deaths >= 1",
        "title": "The Price of Freedom",
        "lines": [
            "Silence falls. The crowd doesn't cheer for death.",
            "In the Pit, death is PERMANENT. Fighters don't come back.",
            "Injuries increase death risk. Use Surgeon's Kits wisely.",
        ],
    },
    {
        "id": "discover_boss",
        "trigger": "tier >= 3",
        "title": "The Champion Awaits",
        "lines": [
            "A massive gate groans open at the far end of the arena.",
            "'That's the Champion's Gate. Only the bold enter.'",
            "BOSS CHALLENGES are tougher but reward much more gold.",
        ],
    },
]


def get_pending_tutorial(engine):
    """Get next unshown tutorial step based on game state, or None."""
    shown = engine.tutorial_shown or []
    for step in TUTORIAL_STEPS:
        if step["id"] in shown:
            continue
        trigger = step["trigger"]
        if trigger == "first_launch":
            return step
        if trigger.startswith("wins") and engine.wins >= int(trigger.split()[-1]):
            return step
        if trigger.startswith("fighters") and len([f for f in engine.fighters if f.alive]) >= int(trigger.split()[-1]):
            return step
        if trigger.startswith("deaths") and engine.total_deaths >= int(trigger.split()[-1]):
            return step
        if trigger.startswith("tier") and engine.arena_tier >= int(trigger.split()[-1]):
            return step
    return None


# ============================================================
#  STORY CHAPTERS — quest chains with rewards
# ============================================================

STORY_CHAPTERS = [
    {
        "id": "ch1", "name": "Chapter I: The Pit",
        "quests": [
            {"id": "ch1_q1", "name": "Into the Arena",
             "desc": "Reach arena tier 3",
             "check": lambda e: e.arena_tier >= 3,
             "reward": {"diamonds": 25}},
            {"id": "ch1_q2", "name": "Brothers in Arms",
             "desc": "Have 2 fighters alive",
             "check": lambda e: len([f for f in e.fighters if f.alive]) >= 2,
             "reward": {"shards": {1: 5}}},
            {"id": "ch1_q3", "name": "Armed",
             "desc": "Equip any weapon",
             "check": lambda e: any(
                 f.equipment.get("weapon") for f in e.fighters if f.alive),
             "reward": {"diamonds": 25}},
            {"id": "ch1_q4", "name": "Blooded",
             "desc": "Defeat 1 boss",
             "check": lambda e: e.bosses_killed >= 1,
             "reward": {"shards": {1: 5}}},
        ],
    },
    {
        "id": "ch2", "name": "Chapter II: Blood & Iron",
        "quests": [
            {"id": "ch2_q1", "name": "Climber",
             "desc": "Reach arena tier 7",
             "check": lambda e: e.arena_tier >= 7,
             "reward": {"diamonds": 50}},
            {"id": "ch2_q2", "name": "Sharpened",
             "desc": "Upgrade any item to +2",
             "check": lambda e: any(
                 any((f.equipment.get(s) or {}).get("upgrade_level", 0) >= 2
                     for s in ["weapon", "armor", "accessory", "relic"])
                 for f in e.fighters),
             "reward": {"shards": {1: 10}}},
            {"id": "ch2_q3", "name": "War Band",
             "desc": "Have 4 fighters alive",
             "check": lambda e: len([f for f in e.fighters if f.alive]) >= 4,
             "reward": {"diamonds": 50}},
            {"id": "ch2_q4", "name": "Armored",
             "desc": "Equip armor on any fighter",
             "check": lambda e: any(
                 f.equipment.get("armor") for f in e.fighters if f.alive),
             "reward": {"shards": {2: 5}}},
        ],
    },
    {
        "id": "ch3", "name": "Chapter III: The Hunt",
        "quests": [
            {"id": "ch3_q1", "name": "Scout",
             "desc": "Complete 3 expeditions",
             "check": lambda e: len(e.expedition_log) >= 3,
             "reward": {"diamonds": 75}},
            {"id": "ch3_q2", "name": "Rising Power",
             "desc": "Reach arena tier 12",
             "check": lambda e: e.arena_tier >= 12,
             "reward": {"shards": {2: 10}}},
            {"id": "ch3_q3", "name": "Master",
             "desc": "Train a fighter to Lv.10",
             "check": lambda e: any(f.level >= 10 for f in e.fighters),
             "reward": {"diamonds": 75}},
            {"id": "ch3_q4", "name": "Relic Found",
             "desc": "Own 1 relic",
             "check": lambda e: any(
                 f.equipment.get("relic") for f in e.fighters) or
                 any(i.get("slot") == "relic" for i in e.inventory),
             "reward": {"shards": {3: 5}}},
        ],
    },
    {
        "id": "ch4", "name": "Chapter IV: The Graveyard",
        "quests": [
            {"id": "ch4_q1", "name": "Blood Price",
             "desc": "Lose 3 fighters to permadeath",
             "check": lambda e: e.total_deaths >= 3,
             "reward": {"diamonds": 100}},
            {"id": "ch4_q2", "name": "Unstoppable",
             "desc": "Reach arena tier 18",
             "check": lambda e: e.arena_tier >= 18,
             "reward": {"shards": {3: 10}}},
            {"id": "ch4_q3", "name": "Titan Breaker",
             "desc": "Defeat 5 bosses",
             "check": lambda e: e.bosses_killed >= 5,
             "reward": {"diamonds": 100}},
            {"id": "ch4_q4", "name": "Collector",
             "desc": "Own 3 relics",
             "check": lambda e: (
                 sum(1 for f in e.fighters if f.equipment.get("relic")) +
                 sum(1 for i in e.inventory if i.get("slot") == "relic")
             ) >= 3,
             "reward": {"shards": {4: 5}}},
        ],
    },
    {
        "id": "ch5", "name": "Chapter V: Empire",
        "quests": [
            {"id": "ch5_q1", "name": "Legion",
             "desc": "Have 8 fighters alive",
             "check": lambda e: len([f for f in e.fighters if f.alive]) >= 8,
             "reward": {"diamonds": 125}},
            {"id": "ch5_q2", "name": "Warlord",
             "desc": "Reach arena tier 25",
             "check": lambda e: e.arena_tier >= 25,
             "reward": {"shards": {4: 10}}},
            {"id": "ch5_q3", "name": "Full Set",
             "desc": "Fighter with weapon + armor + accessory",
             "check": lambda e: any(
                 all(f.equipment.get(s) for s in ["weapon", "armor", "accessory"])
                 for f in e.fighters if f.alive),
             "reward": {"diamonds": 125}},
            {"id": "ch5_q4", "name": "Grand Master",
             "desc": "Train a fighter to Lv.20",
             "check": lambda e: any(f.level >= 20 for f in e.fighters),
             "reward": {"shards": {5: 5}}},
        ],
    },
    {
        "id": "ch6", "name": "Chapter VI: The Void",
        "quests": [
            {"id": "ch6_q1", "name": "Ascendant",
             "desc": "Reach arena tier 35",
             "check": lambda e: e.arena_tier >= 35,
             "reward": {"diamonds": 200}},
            {"id": "ch6_q2", "name": "Legend",
             "desc": "Defeat 20 bosses",
             "check": lambda e: e.bosses_killed >= 20,
             "reward": {"shards": {5: 10}}},
            {"id": "ch6_q3", "name": "Void Walker",
             "desc": "Return from the Void Rift",
             "check": lambda e: any(
                 "Void Rift" in log and "returned" in log
                 for log in e.expedition_log),
             "reward": {"diamonds": 200}},
            {"id": "ch6_q4", "name": "Immortal",
             "desc": "Train a fighter to Lv.30",
             "check": lambda e: any(f.level >= 30 for f in e.fighters),
             "reward": {"shards": {5: 20}}},
        ],
    },
]
