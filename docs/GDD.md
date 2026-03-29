# Gladiator Idle Manager -- Game Design Document

**Version:** 1.5.2
**Platform:** Android (Google Play)
**Engine:** Python 3.11, Kivy 2.3.1, Buildozer
**Last Updated:** 2026-03-29

---

## 1. Game Overview

**Title:** Gladiator Idle Manager
**Genre:** Roguelike idle manager with turn-based auto-combat
**Platform:** Android (portrait orientation, API 21+)
**Target Audience:** Mobile gamers (16+) who enjoy idle/incremental games, roguelike mechanics, and dark fantasy

**Elevator Pitch:**
You are a lanista -- a gladiator trainer -- in a dark fantasy world where blood fuels the empire. Recruit fighters, equip them at the forge, send them into the arena, and watch them fight in luck-based auto-battles. Every fighter can die permanently. A total party wipe resets your run: gold, equipment, and fighters are gone. Only diamonds, achievements, and your story progress survive. Build stronger, go further, die harder.

**Core Fantasy:**
The player manages a stable of gladiators in a Roman-inspired dark fantasy setting. The arena is not sport -- it is an engine of blood that sustains the empire. The sand remembers every death. The crowd demands more.

---

## 2. Core Loop

```
Recruit Fighters --> Equip at Forge --> Arena Battles --> Earn Gold
      ^                                                      |
      |                                                      v
      +-------- Upgrade / Heal / Send on Expeditions <-------+
```

### Per-Run Loop
1. Start with 100 gold and no fighters
2. Recruit fighters (cost scales exponentially with roster size)
3. Buy equipment from the Forge (weapons, armor, accessories)
4. Fight in auto-battles (The Pit) to earn gold
5. Challenge bosses to advance arena tiers
6. Send fighters on expeditions for Metal Shards and relics
7. Upgrade equipment using Metal Shards
8. Push as far as possible before the inevitable wipe

### Roguelike Reset
A total party wipe (all fighters dead) triggers a full reset:

| Lost on Reset | Preserved Across Runs |
|---|---|
| Gold | Diamonds |
| All fighters | Achievements (+ diamond rewards) |
| All equipment & inventory | Story progress |
| Metal Shards | Best records (tier, kills) |
| Expedition progress | Total runs counter |
| Surgeon use count | Lore entries unlocked |

---

## 3. Combat System

### Overview
Turn-based auto-battle with 0.8-second turns. Combat is intentionally luck-heavy: crits and dodges can swing any fight. A weak but agile assassin can outperform a strong brute through fortunate rolls.

Two battle modes:
- **The Pit (Auto-Battle):** All available fighters vs. a wave of enemies (1 enemy per fighter)
- **Boss Challenge:** All fighters vs. a single powerful boss

### Damage Formula
```
raw_damage = attack * random(0.70, 1.30)
if crit: raw_damage *= crit_multiplier
actual_damage = raw_damage * (1 - DEF/(DEF + 100))
minimum damage = 1
```

### Critical Hits
- **Crit chance:** AGI / (AGI + 5) + class_crit_bonus (asymptotic, never reaches 100%)
- **Crit multiplier:** 1.8 + AGI * 0.04 (scales infinitely with AGI)

### Dodge
- **Dodge chance:** 1 - 1/(1 + raw * 0.6), where raw = AGI * 0.02 + class_dodge_bonus
- Diminishing returns: at raw 1.0 = 37.5%, raw 2.0 = 54.5%, never reaches 100%
- A successful dodge negates all damage from that attack

### Enemy Stats
Enemies scale exponentially with arena tier:
- ATK: (7 + tier * 3) * 1.08^(tier-1)
- DEF: (2 + tier * 2) * 1.06^(tier-1)
- HP: (35 + tier * 15) * 1.10^(tier-1)
- Crit chance: min(30%, 5% + tier * 1.5%)
- Dodge chance: min(20%, tier * 1%)

### Boss Fights
- Boss tier = arena_tier + 2
- HP multiplied by 10x
- ATK multiplied by 1.5x
- DEF multiplied by 1.3x
- Crit chance: +10% on top of normal enemy crit
- Dodge chance: 0% (bosses do not dodge)
- 100 unique boss names for tiers 1-100, procedurally generated names beyond

### Enchantment Buildup System
Inspired by Elden Ring's status buildup. Each hit with an enchanted weapon adds buildup to the target. When buildup reaches the threshold, the enchantment triggers.

| Enchantment | Buildup/Hit | Threshold | Effect |
|---|---|---|---|
| Bleeding | 20 | 100 | Burst: 15% max HP damage |
| Frostbite | 15 | 100 | Burst: 10% max HP + 20% ATK reduction (3 turns) |
| Poison | 25 | 80 | DoT: 5% max HP per turn (4 turns) |
| Burn | 25 | 80 | Burst: 20% max HP damage |
| Paralyze | 10 | 120 | Skip 1 turn |
| Corruption | 18 | 100 | 30% DEF reduction (3 turns) |
| Lightning | 22 | 90 | Chain burst: 10% max HP to all enemies |
| Weaken | 15 | 100 | 25% ATK reduction (4 turns) |
| Drain | 20 | 100 | Lifesteal: heals attacker 10% of damage |
| Holy Fire | 12 | 120 | Conditional burst: 25% vs bosses, 10% vs normal |

Enchanting a weapon costs 40,000-100,000 gold + 100 tier-5 Metal Shards.

---

## 4. Fighter System

### Classes

| Class | STR | AGI | VIT | HP Mult | Pts/Lvl | Passive |
|---|---|---|---|---|---|---|
| Mercenary | 5 | 5 | 5 | 1.0x | 4 | Versatile: +1 bonus stat point per level |
| Assassin | 4 | 8 | 3 | 0.85x | 3 | Shadow Strike: crits deal +25% bonus damage |
| Tank | 3 | 2 | 10 | 1.3x | 3 | Unbreakable: -10% all incoming damage |
| Berserker | 8 | 3 | 4 | 1.1x | 3 | Blood Fury: up to +50% damage at low HP |
| Retiarius | 5 | 6 | 4 | 0.9x | 3 | Net Mastery: counter-attack on dodge (50% damage) |
| Medicus | 3 | 5 | 7 | 1.0x | 4 | Field Surgery: 3% max HP regen per turn |

### Stats
- **STR (Strength):** Determines base attack power
- **AGI (Agility):** Determines crit chance (3% per point), crit multiplier (+4% per point), and dodge chance (2% per point)
- **VIT (Vitality):** Determines max HP and minor defense contribution

Stat points are distributed **manually** by the player on each level up. This is a core strategic decision -- no auto-allocation.

### Perk Trees
- 8 perks per class across 4 tiers
- Tier 1: 1 perk point, Tier 2: 2 points, Tier 3: 3 points, Tier 4: 4 points
- Cross-class learning available at 2x cost
- Perk effects include: damage bonus, damage reduction, HP bonus, crit chance, dodge chance, lifesteal, on-kill heal, gold bonus, injury severity reduction, status resistance, stacking combat buffs

### Injury System
- 100 unique injuries across 4 severity levels: minor (41), moderate (30), severe (19), permanent (10)
- 6 body parts: head, torso, left arm, right arm, left leg, right leg (roughly equal distribution)
- Each injury applies stat penalties (percentage-based)
- Injuries accumulate -- they are not automatically healed
- Healing requires gold (surgeon) or diamonds (Divine Surgeon)

### Permadeath
When a fighter's HP reaches 0 in battle:
```
death_chance = 0.05 + injuries * 0.06    (capped at 60%)
```
- A fresh fighter (0 injuries) has a 5% chance of dying permanently
- A fighter with 5 injuries has a 35% chance
- A fighter with 10 injuries hits the 60% cap
- If the fighter survives, they gain +1 injury (making future death more likely)
- Dead fighters are added to the graveyard and cannot be recovered (without Soul Stone)

---

## 5. Equipment

### Slots
4 equipment slots per fighter: **weapon**, **armor**, **accessory**, **relic**

### Rarities

| Rarity | Color | Stat Multiplier | Max Upgrade |
|---|---|---|---|
| Common | Brown | 1.0x | +5 |
| Uncommon | Green | 1.3x | +10 |
| Rare | Blue | 1.7x | +15 |
| Epic | Purple | 2.2x | +20 |
| Legendary | Gold | 3.0x | +25 |

### Item Counts (from data files)
- **Weapons:** 50 items (Rusty Blade to Blade of Ruin and beyond)
- **Armor:** 50 items (Leather Vest to Dragonscale Aegis and beyond)
- **Accessories:** 30 items (Bone Charm to Crown of Ash and beyond)
- **Relics:** 20 items across all rarities (found on expeditions, not purchasable from Forge)

### Upgrade System
- Equipment can be upgraded from +1 to +25 (max depends on rarity)
- Upgrades consume Metal Shards (tier determined by upgrade level: +1-5 = tier 1, +6-10 = tier 2, etc.)
- Upgrade bonuses scale with fighter stats:
  - Weapon: +(STR + AGI) * level * 20% ATK
  - Armor: +(STR + VIT) * level * 20% DEF
  - Accessory: +(AGI + VIT) * level * 20% * 10 HP
  - Relic: all three stats split evenly

### Enchantments
- Only weapons can be enchanted
- 10 enchantment types (see Combat System)
- Cost: 40,000-100,000 gold + 100 tier-5 Metal Shards per enchantment
- Enchantments are expensive end-game investments

---

## 6. Economy

### Currencies

| Currency | Source | Lost on Reset | Purpose |
|---|---|---|---|
| Gold | Arena battles, expeditions | Yes | Hiring, healing, equipment, upgrades |
| Diamonds | Achievements, IAP | No | Premium shop items, convenience |
| Metal Shards (I-V) | Expeditions | Yes | Equipment upgrades |

### Gold Economy
- Starting gold: 100
- Battle rewards: 15 * 1.12^(tier-1) per enemy killed
- Rewards grow slower than difficulty (intentional scarcity)

### Cost Scaling (all exponential)

| Action | Formula |
|---|---|
| Hire fighter | 40 * 1.6^(alive_count) |
| Level up | 35 * 1.45^(level-1) |
| Heal | 20 * 1.12^(tier-1) |
| Surgery | 80 * 1.25^(times_used) |

### Design Intent
The economy is deliberately tight. Gold income cannot keep pace with rising costs at higher tiers. Players must make hard choices: heal or recruit? Upgrade weapon or buy armor? This scarcity drives engagement and makes each decision meaningful. Total wipes are inevitable, not accidental.

---

## 7. Expeditions

### Overview
Timed missions that send a fighter into dangerous territory. The fighter is unavailable during the expedition and may die.

### Expedition Tiers

| Expedition | Duration | Min Level | Danger | Gold Range | Relic Chance | Shard Tier |
|---|---|---|---|---|---|---|
| Dark Tunnels | 1 min | 11 | 43% | 20-60 | 15% | I |
| Bandit Outpost | 3 min | 13 | 50% | 50-150 | 25% | II |
| Cursed Ruins | 5 min | 15 | 57% | 100-300 | 35% | III |
| Dragon Wastes | 10 min | 18 | 65% | 200-600 | 45% | IV |
| Void Rift | 15 min | 22 | 75% | 400-1000 | 55% | V |

### Rewards
- Gold (random within range)
- Metal Shards of the expedition's tier
- Relics (random rarity from the expedition's relic pool)
- Risk: fighter death based on danger percentage

### Expedition Slots
- 1 default slot (1 fighter at a time)
- Additional slots purchasable from diamond shop (200 diamonds, doubling each purchase)

---

## 8. Prestige System

### Overview
After reaching arena tier 15, the player can voluntarily prestige: reset the current run in exchange for permanent cumulative stat bonuses and feature unlocks.

### Requirements
- Arena tier >= 15

### Mechanics
- Prestige increments `prestige_level` by 1
- Triggers a full roguelike reset (gold, fighters, inventory, shards all wiped)
- Diamonds and achievements are preserved (as with any roguelike reset)

### Stat Bonus
Each prestige level gives +2% cumulative base stats to all fighters:
```
stat_multiplier = 1.0 + prestige_level * 0.02
```
All fighter stats (ATK, DEF, HP) are multiplied by this bonus.

### Feature Unlocks

| Prestige Level | Unlock |
|---|---|
| 1 | Mutators system |
| 5 | 2nd mutator slot, Berserker class |
| 8 | Retiarius class |
| 10 | Dual enchantment, Medicus class |
| 15 | 3rd mutator slot |
| 20 | Ascended title, +50% diamond earn rate |

Levels without a listed unlock still grant the +2% stat bonus.

---

## 9. Mutators

### Overview
Risk/reward modifiers selectable at the start of a run (unlocked at prestige level 1). Negative mutators increase difficulty but boost gold rewards. Positive mutators make runs easier but reduce rewards.

### Mutator Slots
- 1 slot at prestige level 1
- 2 slots at prestige level 5
- 3 slots at prestige level 15

### Negative Mutators (15 total)
Examples: Fragile (+30% incoming damage, 1.5x reward), No Healing (2.0x reward), Permadeath+ (instant death on first injury, 2.0x reward), No Equipment (2.5x reward).

### Positive Mutators (5 total)
Examples: Blessed (+20% all stats, 0.7x reward), Regeneration (5% HP regen/turn, 0.7x reward), Lucky (+15% crit, 0.8x reward).

### Reward Multiplier
Active mutator reward multipliers are multiplied together:
```
combined_mult = product(m.reward_mult for m in active_mutators)
```

---

## 10. Meta-Progression

### Persistent Progression
Survives roguelike reset:
- **Diamonds:** Earned from achievements, spent in premium shop
- **Achievements:** 50 achievements with diamond rewards (50-150 diamonds each)
- **Story Campaign:** Narrative chapters that unlock through arena tier progression
- **Best Records:** Highest tier reached, most kills in a single run
- **Lore Collection:** 30 entries unlocked by reaching milestones (tier, wins, kills, etc.)
- **Total Runs Counter:** Tracks how many resets the player has experienced

### Achievements (50 total)
Categories:
- Combat: first win, 10/50/200 wins, boss kills
- Progression: tier 5/10/20
- Roster: 3/6/10 fighters, level 10/20
- Economy: 1K/10K/100K total gold earned
- Death & danger: first permadeath, 5 deaths, 5+ injury survivor
- Equipment: first equip, legendary item, relic collection
- Expeditions: 10 completions, Void Rift survival
- Story: chapter completions

### Story Campaign
- Tutorial woven into Chapter 1 (5 tutorial steps triggered by gameplay milestones)
- Story chapters unlock at specific arena tiers
- Each chapter features dialogue and narrative progression
- 6+ chapters total

### Lore System
- 30 lore entries covering arena history, characters, and world-building
- Unlocked progressively by reaching tier/win/kill thresholds
- Dark fantasy tone: blood economy, cursed sand, imprisoned emperors

---

## 11. Monetization

### Diamond Bundles (IAP)

| Bundle | Diamonds | Price (UAH) | Price (USD) | Bonus |
|---|---|---|---|---|
| Pouch | 100 | 20 | $0.49 | -- |
| Sack | 500 | 59 | $1.49 | -- |
| Chest | 1,000 | 79 | $1.99 | -- |
| Vault | 2,500 | 179 | $4.49 | +10% |
| Treasury | 6,000 | 399 | $9.99 | +20% |

### Diamond Shop

| Item | Cost | Type | Effect |
|---|---|---|---|
| Soul Stone | 100 | Consumable | Revive a dead fighter (full HP, clear injuries) |
| Divine Surgeon | 1/injury | Consumable | Heal all injuries on all fighters |
| Scout Network | 200 | Permanent | +1 expedition slot |
| Golden War Set | 300 | Equipment | Blade of Ruin + Dragonscale Aegis + Crown of Ash |
| Identity Scroll | 25 | Cosmetic | Rename any fighter |

### Monetization Philosophy
- **No pay-to-win:** Diamonds provide convenience and cosmetics, not power advantages
- The Golden War Set is powerful but can be earned through normal gameplay (items available in Forge)
- Soul Stone is the strongest diamond purchase (bypasses permadeath once) but does not prevent future deaths
- Optional ads (currently disabled in production build)

---

## 12. Target Audience

### Primary
- Mobile gamers who enjoy idle/incremental games (tap-and-wait loop)
- Players who appreciate roguelike risk (permadeath, run-based progression)
- Dark fantasy genre enthusiasts (Elden Ring, Darkest Dungeon tone)

### Secondary
- Strategy gamers who want manual control (stat distribution, perk choices)
- Players looking for short-session mobile games (1-5 minute battles, timed expeditions)

### Age Rating
- 16+ (violence, dark themes, blood references)
- No explicit content, gambling, or real-money randomization (all IAP is deterministic)

---

## 13. Competitive Analysis

### vs. Gladiator Manager (genre competitors)
- **Differentiator:** Roguelike permadeath with full-run resets. Most gladiator management games have no permanent consequences. Our game punishes overconfidence and rewards strategic caution.
- **Differentiator:** Elden Ring-style enchantment buildup system adds tactical depth absent from typical idle games.
- **Differentiator:** Darker tone -- the arena is not heroic sport but a blood engine that fuels the empire.

### vs. Idle/Incremental Games (AFK Arena, Idle Heroes)
- **Differentiator:** Manual stat point distribution on level up (players make real build decisions)
- **Differentiator:** True permadeath with injury escalation (not just "retry" mechanics)
- **Differentiator:** No VIP systems, no gacha -- all purchases are deterministic
- **Trade-off:** Smaller content scope (no PvP, no guilds) in exchange for deeper single-player mechanics

### vs. Roguelikes (Darkest Dungeon)
- **Differentiator:** Idle/auto-battle format makes it accessible on mobile
- **Differentiator:** Shorter run cycles (runs end around tier 10-20, not hours-long dungeon crawls)
- **Trade-off:** Less tactical combat depth in exchange for faster, luck-driven fights

---

## 14. Technical

### Stack
- **Language:** Python 3.11
- **UI Framework:** Kivy 2.3.1
- **Build System:** Buildozer (targeting arm64-v8a)
- **Minimum API:** 21 (Android 5.0)
- **Target API:** 35 (Android 15, 16KB page alignment)

### Data Architecture
- Game data defined in JSON files: weapons, armor, accessories, relics, enchantments, injuries, fighter classes, achievements, lore, enemies, fighter names
- Save system: JSON file stored in app-private storage
- Cloud save backup (Google Play Services)

### External Services
- **Google Play Games v2:** Leaderboards, achievements sync
- **Google Play Billing v6:** Diamond IAP
- **AdMob:** Optional rewarded ads (currently disabled)

### Project Structure
```
gladiator-idle-manager/
  main.py                  # App entry point
  gladiatoridle.kv         # Kivy UI layout
  ui_config.json           # UI configuration
  tweaker.py               # Balance tweaking tool
  buildozer.spec           # Android build config
  game/
    engine.py              # Core game engine, save/load, roguelike reset
    models.py              # Fighter, Enemy, Equipment, Economy, DifficultyScaler
    battle.py              # Turn-based combat system
    achievements.py        # Achievements, diamond shop, IAP bundles
    story.py               # Tutorial steps, story chapters
    localization.py        # i18n support
    constants.py           # Game-wide constants
    base_screen.py         # Base UI screen class
    widgets.py             # Custom Kivy widgets
    theme.py               # Visual theme
    ui_helpers.py          # UI utility functions
    ads.py                 # Ad integration
    iap.py                 # In-app purchase integration
    cloud_save.py          # Cloud save via Google Play
    leaderboard.py         # Google Play Games leaderboard
    screens/
      arena.py             # Arena / battle screen
      roster.py            # Fighter management screen
      forge.py             # Equipment shop / upgrade screen
      expedition.py        # Expedition management
      lore.py              # Lore collection viewer
      more.py              # Settings, about, links
      shared.py            # Shared screen components
  data/
    fighter_classes.json   # Class definitions with perk trees
    weapons.json           # 50 weapons
    armor.json             # 50 armor pieces
    accessories.json       # 30 accessories
    relics.json            # 20 relics (5 rarities)
    enchantments.json      # 10 enchantment types
    injuries.json          # 100 injuries (4 severities, 6 body parts)
    achievements.json      # 50 achievements
    lore.json              # 30 lore entries
    enemies.json           # Enemy data
    fighter_names.json     # Name pools
  docs/
    privacy-policy.html
    GDD.md                 # This document
```

### Performance Considerations
- Auto-battle runs at 0.8s per turn (configurable via constants)
- Full battle skip mode processes all turns instantly (capped at 200 events)
- Large number formatting (fmt_num) supports values up to decillions (1e33)
- Portrait-only orientation, fullscreen

---

## Appendix A: Damage Calculation Walkthrough

**Example:** Level 10 Assassin (AGI 18) with Steel Falcata (+8 ATK) vs. Tier 5 enemy

1. Fighter attack = STR*2 + equipment ATK = ~16 + 8 = 24
2. Raw damage = 24 * random(0.70, 1.30) = ~17-31
3. Crit chance = 18/(18+5) = 78.3% (+ 20% class bonus)
4. If crit: damage * (1.8 + 18*0.04) = damage * 2.52
5. Enemy DEF at tier 5: ~16
6. Reduction = 16/(16+100) = 13.8%
7. Final damage = raw * 0.862

**Result:** Non-crit hits land ~15-27. Crits hit ~37-68. Against an enemy with ~125 HP, 2-3 crits can end the fight.

---

## Appendix B: Economy Progression

| Tier | Enemy HP | Enemy ATK | Gold/Kill | Hire Cost (5th fighter) |
|---|---|---|---|---|
| 1 | 50 | 10 | 15 | 419 |
| 5 | 143 | 31 | 24 | 419 |
| 10 | 359 | 68 | 42 | 419 |
| 15 | 847 | 138 | 74 | 419 |
| 20 | 1,937 | 274 | 131 | 419 |

Note: Hire cost depends on alive fighter count, not tier. The 5th fighter always costs 40 * 1.6^5 = ~419 gold regardless of when you hire them.
