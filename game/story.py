# Build: 1
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
