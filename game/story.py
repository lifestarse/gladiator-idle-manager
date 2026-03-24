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

# --- Story chapters ---

STORY_CHAPTERS = [
    {
        "chapter": 1,
        "title": "The Pit",
        "unlock_tier": 1,
        "intro": [
            "You are nobody. A slave, thrown into the fighting pits",
            "beneath the great city of Ashenmoor.",
            "Survive. Earn gold. Build your squad.",
            "The only way out is up — through blood and iron.",
        ],
        "boss_name": "Grakk the Pit Lord",
        "boss_tier_bonus": 2,
        "boss_hp_mult": 2.5,
        "completion": [
            "Grakk falls. The crowd erupts.",
            "For the first time, a guard addresses you by name.",
            "'The Arena Master wants to see you.'",
        ],
        "reward_diamonds": 100,
        "unlocks": "boss_fights",
    },
    {
        "chapter": 2,
        "title": "Blood & Gold",
        "unlock_tier": 5,
        "intro": [
            "The Arena Master offers a deal: fight for him,",
            "and you earn a share of the gate. Refuse, and...",
            "well, nobody refuses the Arena Master.",
            "Your squad grows. Enemies grow stronger.",
        ],
        "boss_name": "The Iron Twins",
        "boss_tier_bonus": 3,
        "boss_hp_mult": 3.0,
        "completion": [
            "The Iron Twins collapse in sync.",
            "Nobles in the stands take notice.",
            "Whispers of a rebellion reach your ears.",
        ],
        "reward_diamonds": 100,
        "unlocks": "diamond_shop",
    },
    {
        "chapter": 3,
        "title": "The Rebellion",
        "unlock_tier": 10,
        "intro": [
            "A hooded figure visits your cell at night.",
            "'We're planning something. We need warriors.'",
            "'Help us overthrow the Arena Master,",
            "and we'll give you something gold can't buy: freedom.'",
        ],
        "boss_name": "Arena Master Volkan",
        "boss_tier_bonus": 4,
        "boss_hp_mult": 3.5,
        "completion": [
            "Volkan's crown clatters to the ground.",
            "The slaves erupt in cheers. The gates open.",
            "But freedom has a price — the Empire takes notice.",
        ],
        "reward_diamonds": 100,
        "unlocks": "expeditions_t2",
    },
    {
        "chapter": 4,
        "title": "Empire's Wrath",
        "unlock_tier": 15,
        "intro": [
            "Imperial legions march on Ashenmoor.",
            "'The Emperor doesn't tolerate rebel arenas.'",
            "You must defend what you've built.",
            "Rally your fighters. This is war.",
        ],
        "boss_name": "Legatus Marius",
        "boss_tier_bonus": 5,
        "boss_hp_mult": 4.0,
        "completion": [
            "The Legatus kneels, defeated but alive.",
            "'The Emperor will send more. You can't win.'",
            "'Watch me,' you reply.",
        ],
        "reward_diamonds": 100,
        "unlocks": "legendary_forge",
    },
    {
        "chapter": 5,
        "title": "The Void Below",
        "unlock_tier": 20,
        "intro": [
            "Beneath the arena, the tunnels go deeper than anyone knew.",
            "Ancient things stir in the dark.",
            "The Void Rift isn't just a place — it's a doorway.",
            "Something is coming through.",
        ],
        "boss_name": "The Abyssal Herald",
        "boss_tier_bonus": 7,
        "boss_hp_mult": 5.0,
        "completion": [
            "The Herald dissolves into shadow.",
            "But the Rift remains open. Pulsing.",
            "Whatever lies beyond... it's watching you.",
        ],
        "reward_diamonds": 150,
        "unlocks": "void_expeditions",
    },
]


def get_current_chapter(story_chapter_idx):
    """Get current chapter data. Returns None if story complete."""
    if story_chapter_idx >= len(STORY_CHAPTERS):
        return None
    return STORY_CHAPTERS[story_chapter_idx]


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
