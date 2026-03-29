# Gladiator Idle Manager -- Balance Document

All values computed from the actual game formulas in `game/models.py` and `game/battle.py`.

---

## 1. Core Formulas

### 1.1 Enemy Stats (DifficultyScaler)

```
ATK = floor( (7 + tier*3) * 1.08^(tier-1) )
DEF = floor( (2 + tier*2) * 1.06^(tier-1) )
HP  = floor( (35 + tier*15) * 1.10^(tier-1) )
Gold Reward = floor( 15 * 1.12^(tier-1) )
Crit Chance = min(0.30, 0.05 + tier * 0.015)
Dodge Chance = min(0.20, tier * 0.01)
Crit Multiplier = 1.8 (flat for all enemies)
```

### 1.2 Boss Stats

Bosses use **tier + 2** as their base tier, then multiply:

```
Base stats from enemy_stats(arena_tier + 2)
HP  *= 10
ATK *= 1.5
DEF *= 1.3
Gold *= 10
Crit += 0.10 (capped at 0.35)
Dodge = 0 (bosses never dodge)
```

### 1.3 Fighter Stats

```
ATK     = STR*2 + base_attack + (level-1) + equip_atk
DEF     = VIT + base_defense + equip_def
Max HP  = floor( (30 + VIT*8 + base_hp + (level-1)*5) * hp_mult ) + equip_hp
Crit %  = AGI / (AGI + 5) + crit_bonus        [asymptotic, never 100%]
Crit x  = 1.8 + AGI * 0.04                    [uncapped, grows forever]
Dodge % = 1 - 1 / (1 + (AGI*0.02 + dodge_bonus) * 0.6)  [diminishing returns]
Power   = ATK + DEF + Max_HP / 5
```

### 1.4 Damage Resolution

```
1. Raw damage  = ATK * uniform(0.70, 1.30)
2. Crit check  : if random < crit_chance -> raw *= crit_mult
3. Dodge check : if random < defender.dodge_chance -> damage = 0 (full negate)
4. Armor reduce: actual = max(1, floor( raw * (1 - DEF/(DEF+100)) ))
5. Apply to HP : defender.hp -= actual
```

### 1.5 Economy Costs

```
Hire fighter   = floor( 40 * 1.6^(alive_count) )
Upgrade level  = floor( 35 * 1.45^(level-1) )
Heal (potion)  = floor( 20 * 1.12^(arena_tier-1) )
Surgery        = floor( 80 * 1.25^(times_used) )
Injury heal    = 50 * (1 + injuries_healed) * max(1, level)
```

### 1.6 Permadeath / Injury

```
Death chance on KO = min(0.60, 0.05 + injuries * 0.06)
```

- 0 injuries: 5% permadeath chance
- 1 injury: 11%
- 5 injuries: 35%
- 9 injuries: 59% (near cap)

---

## 2. Tier Progression Table

### 2.1 Regular Enemies (T1-T15)

| Tier | ATK | DEF | HP | Gold | Crit% | Dodge% |
|------|----:|----:|---:|-----:|------:|-------:|
| 1 | 10 | 4 | 50 | 15 | 6.5% | 1.0% |
| 2 | 14 | 6 | 71 | 16 | 8.0% | 2.0% |
| 3 | 18 | 8 | 96 | 18 | 9.5% | 3.0% |
| 4 | 23 | 11 | 126 | 21 | 11.0% | 4.0% |
| 5 | 29 | 15 | 161 | 23 | 12.5% | 5.0% |
| 6 | 36 | 18 | 201 | 26 | 14.0% | 6.0% |
| 7 | 44 | 22 | 248 | 29 | 15.5% | 7.0% |
| 8 | 53 | 27 | 302 | 33 | 17.0% | 8.0% |
| 9 | 62 | 31 | 364 | 37 | 18.5% | 9.0% |
| 10 | 73 | 37 | 436 | 41 | 20.0% | 10.0% |
| 11 | 86 | 42 | 518 | 46 | 21.5% | 11.0% |
| 12 | 100 | 49 | 613 | 52 | 23.0% | 12.0% |
| 13 | 115 | 56 | 721 | 58 | 24.5% | 13.0% |
| 14 | 133 | 63 | 845 | 65 | 26.0% | 14.0% |
| 15 | 152 | 72 | 987 | 73 | 27.5% | 15.0% |

### 2.2 Bosses (T1-T15)

Boss base tier = arena_tier + 2. Stats after multipliers:

| Arena Tier | Boss ATK | Boss DEF | Boss HP | Boss Gold | Boss Crit% |
|------------|--------:|--------:|--------:|----------:|-----------:|
| 1 | 27 | 10 | 960 | 180 | 20.0% |
| 2 | 34 | 14 | 1,260 | 210 | 21.0% |
| 3 | 43 | 19 | 1,610 | 230 | 23.0% |
| 4 | 54 | 23 | 2,010 | 260 | 24.0% |
| 5 | 66 | 28 | 2,480 | 290 | 26.0% |
| 6 | 79 | 35 | 3,020 | 330 | 27.0% |
| 7 | 93 | 40 | 3,640 | 370 | 29.0% |
| 8 | 109 | 48 | 4,360 | 410 | 30.0% |
| 9 | 129 | 54 | 5,180 | 460 | 31.0% |
| 10 | 150 | 63 | 6,130 | 520 | 33.0% |
| 11 | 172 | 72 | 7,210 | 580 | 34.0% |
| 12 | 199 | 81 | 8,450 | 650 | 35.0% |
| 13 | 228 | 93 | 9,870 | 730 | 35.0% |
| 14 | 261 | 105 | 11,480 | 820 | 35.0% |
| 15 | 297 | 118 | 13,320 | 910 | 35.0% |

### 2.3 Recommended Fighter Level per Tier

| Tier | Rec. Level | Rec. Power Rating |
|------|----------:|------------------:|
| 1 | 1 | 24 |
| 2 | 3 | 34 |
| 3 | 5 | 45 |
| 4 | 7 | 59 |
| 5 | 9 | 76 |
| 6 | 11 | 94 |
| 7 | 13 | 115 |
| 8 | 15 | 140 |
| 9 | 17 | 165 |
| 10 | 19 | 197 |
| 11 | 21 | 231 |
| 12 | 23 | 271 |
| 13 | 25 | 315 |
| 14 | 27 | 365 |
| 15 | 29 | 421 |

Power rating here = Enemy ATK + Enemy DEF + Enemy HP / 5 (the "minimum fighter power to stand a chance").

---

## 3. Equipment Stats Table

### 3.1 Weapons

| Item | Rarity | ATK | DEF | HP | Cost |
|------|--------|----:|----:|---:|-----:|
| Rusty Blade | Common | 3 | 0 | 0 | 400 |
| Iron Sword | Common | 5 | 0 | 0 | 900 |
| Steel Falcata | Uncommon | 8 | 0 | 5 | 2,000 |
| Obsidian Edge | Rare | 12 | 2 | 0 | 5,000 |
| Inferno Cleaver | Epic | 18 | 0 | 10 | 12,000 |
| Blade of Ruin | Legendary | 28 | 5 | 20 | 30,000 |

### 3.2 Armor

| Item | Rarity | ATK | DEF | HP | Cost |
|------|--------|----:|----:|---:|-----:|
| Leather Vest | Common | 0 | 3 | 10 | 500 |
| Chain Mail | Common | 0 | 5 | 15 | 1,200 |
| Bronze Plate | Uncommon | 0 | 8 | 25 | 2,800 |
| Shadow Guard | Rare | 3 | 12 | 30 | 6,500 |
| Titan Shell | Epic | 0 | 18 | 50 | 15,000 |
| Dragonscale Aegis | Legendary | 5 | 25 | 70 | 35,000 |

### 3.3 Accessories

| Item | Rarity | ATK | DEF | HP | Cost |
|------|--------|----:|----:|---:|-----:|
| Bone Charm | Common | 2 | 2 | 5 | 450 |
| Iron Ring | Uncommon | 4 | 4 | 10 | 1,600 |
| Blood Pendant | Rare | 7 | 3 | 20 | 4,000 |
| Void Amulet | Epic | 10 | 7 | 30 | 10,000 |
| Crown of Ash | Legendary | 15 | 10 | 50 | 25,000 |

### 3.4 Combined Equipment by Rarity (Best-in-Slot)

Total stats from weapon + armor + accessory combined:

| Rarity | Total ATK | Total DEF | Total HP | Total Cost |
|--------|----------:|----------:|---------:|-----------:|
| Common | 5 | 5 | 15 | 1,350 |
| Uncommon | 12 | 12 | 40 | 6,400 |
| Rare | 22 | 17 | 50 | 15,500 |
| Epic | 28 | 25 | 90 | 37,000 |
| Legendary | 48 | 40 | 140 | 90,000 |

### 3.5 Rarity Multipliers

| Rarity | Multiplier | Max Upgrade Level |
|--------|----------:|-----------------:|
| Common | 1.0x | +5 |
| Uncommon | 1.3x | +10 |
| Rare | 1.7x | +15 |
| Epic | 2.2x | +20 |
| Legendary | 3.0x | +25 |

---

## 4. Class Comparison Table

The game currently has 3 fighter classes:

| Stat | Mercenary | Assassin | Tank |
|------|----------:|---------:|-----:|
| Base STR | 5 | 4 | 3 |
| Base AGI | 5 | 8 | 2 |
| Base VIT | 5 | 3 | 10 |
| Crit Bonus | +0% | +20% | -5% |
| Dodge Bonus | 0% | +5% | 0% |
| HP Multiplier | 1.0x | 0.85x | 1.3x |
| Points/Level | 4 | 3 | 3 |
| Starting Points | 3 | 3 | 3 |

### Passive Effects

- **Mercenary**: No passive. Gains +1 extra stat point per level (4 vs 3). Best generalist.
- **Assassin**: +20% crit chance, +5% dodge bonus, 0.85x HP. Glass cannon; wins fast or dies.
- **Tank**: -5% crit chance, 1.3x HP multiplier. Survives longest, deals less burst.

### Recommended Builds

| Class | STR:AGI:VIT | Playstyle |
|-------|-------------|-----------|
| Mercenary | 1:1:1 (balanced) | Even stat distribution works best due to 4 pts/level advantage |
| Assassin | 3:6:1 (AGI-heavy) | Stack AGI for crit + dodge, minimal VIT (you die fast anyway) |
| Tank | 2:2:6 (VIT-heavy) | Stack VIT for max survivability, some AGI for crits |

### Level 25 Stats (optimal builds, no equipment)

| Class | STR | AGI | VIT | ATK | DEF | HP | Crit% | Crit x | Dodge% | Power |
|-------|----:|----:|----:|----:|----:|---:|------:|-------:|-------:|------:|
| Mercenary (38/38/38) | 38 | 38 | 38 | 100 | 38 | 454 | 88.4% | 3.32x | 31.3% | 228 |
| Assassin (26/53/11) | 26 | 53 | 11 | 76 | 11 | 202 | 111.4% | 3.92x | 40.0% | 127 |
| Tank (18/17/55) | 18 | 17 | 55 | 60 | 55 | 767 | 72.3% | 2.48x | 16.9% | 268 |

Note: Assassin crit > 100% means every hit crits (excess is wasted).

---

## 5. Enchantment Comparison

Three Elden Ring-style buildup enchantments applied to weapons:

| Enchantment | Buildup/Hit | Threshold | Hits to Proc | Effect | Gold Cost | Shard Cost |
|-------------|------------:|----------:|-------------:|--------|----------:|-----------:|
| Bleeding | 20 | 100 | 5 | 15% max HP burst damage | 50,000 | 100x Tier V |
| Frostbite | 15 | 100 | 7 | 10% max HP burst + 20% ATK debuff (3 turns) | 80,000 | 100x Tier V |
| Poison | 25 | 80 | 4 | 5% max HP DOT per turn for 4 turns (20% total) | 60,000 | 100x Tier V |

### Effective DPS Contribution per Hit

| Tier | Enemy HP | Bleeding (dmg/hit) | Frostbite (dmg/hit) | Poison (dmg/hit) |
|------|--------:|---------:|----------:|--------:|
| 5 | 161 | 4.8 | 2.3 | 8.0 |
| 10 | 436 | 13.0 | 6.1 | 21.8 |
| 15 | 987 | 29.6 | 14.0 | 49.2 |

### Enchantment Ranking

1. **Poison** -- highest raw damage output (20% HP over 4 turns), procs fastest (4 hits). Best pure DPS enchantment.
2. **Bleeding** -- solid burst (15% HP), procs every 5 hits. Good all-around.
3. **Frostbite** -- lowest direct damage (10% HP), slowest proc (7 hits), BUT the 20% ATK debuff for 3 turns is invaluable against bosses. The debuff effectively reduces incoming damage by 20% for 3 turns after every 7 hits. Best defensive enchantment.

### Boss Enchantment Analysis

Against T10 Boss (HP 6,130):
- Poison: 306 damage per proc, every 4 hits = 76.5 bonus dmg/hit
- Bleeding: 919 damage per proc, every 5 hits = 183.9 bonus dmg/hit
- Frostbite: 613 damage per proc + ATK debuff, every 7 hits = 87.6 dmg/hit + survivability

Against bosses with massive HP pools, **Bleeding** becomes the best DPS enchantment because the 15% burst scales with the enormous boss HP.

---

## 6. Simulated Battles

All simulations use the formulas from section 1. Point distribution follows class-optimal builds.
Expected damage per hit = ATK * (1 + crit% * (crit_mult - 1)) * (1 - target_DEF/(target_DEF+100)) * (1 - target_dodge%).

### 6.1 Battle Summary Table

| # | Battle | Fighter ATK/DEF/HP | Crit%/Dodge% | Enemy ATK/DEF/HP | F dmg/hit | E dmg/hit | Turns to Kill | Turns to Die | Win% | Gold |
|---|--------|-------------------|-------------|-----------------|-----------|-----------|---------------|-------------|------|------|
| 1 | T1 Lvl1 Merc (naked) vs T1 | 12/6/78 | 54.5%/6.7% | 10/4/50 | 17.9 | 9.3 | 3 | 9 | ~80% | 15 |
| 2 | T1 Lvl3 Merc (common) vs T1 | 23/15/135 | 61.5%/8.8% | 10/4/50 | 37.0 | 8.3 | 2 | 17 | ~95% | 15 |
| 3 | T3 Lvl5 Assassin (uncommon) vs T3 | 32/17/116 | 97.3%/19.0% | 18/8/96 | 70.1 | 13.4 | 2 | 9 | ~95% | 18 |
| 4 | T5 Lvl8 Tank (rare) vs T5 | 43/41/384 | 56.5%/8.8% | 29/15/161 | 58.0 | 20.6 | 3 | 19 | ~95% | 23 |
| 5 | T5 Lvl8 Merc vs T5 **Boss** | 59/33/243 | 75.0%/15.3% | 66/28/2480 | 94.5 | 50.6 | 27 | 5 | ~5% | 290 |
| 6 | T7 Lvl12 Assassin (rare) vs T7 | 61/25/176 | 105.3%/27.4% | 44/22/248 | 142.5 | 28.7 | 2 | 7 | ~88% | 29 |
| 7 | T7 Lvl12 Tank (rare) vs T7 | 53/48/482 | 61.7%/10.7% | 44/22/248 | 70.3 | 29.8 | 4 | 17 | ~95% | 29 |
| 8 | T10 Lvl15 Merc (epic) vs T10 | 90/51/398 | 82.8%/22.4% | 73/37/436 | 145.2 | 43.5 | 4 | 10 | ~72% | 41 |
| 9 | T10 Lvl15 Assassin (epic) vs T10 **Boss** | 76/33/229 | 107.5%/31.0% | 150/63/6130 | 156.9 | 98.3 | 40 | 3 | ~5% | 520 |
| 10 | T10 Lvl18 Tank (epic) vs T10 | 71/67/676 | 68.7%/14.4% | 73/37/436 | 90.2 | 43.4 | 5 | 16 | ~83% | 41 |
| 11 | T12 Lvl20 Merc (epic) vs T12 | 109/57/471 | 86.1%/27.1% | 100/49/613 | 177.5 | 55.0 | 4 | 9 | ~69% | 52 |
| 12 | T12 Lvl20 Assassin (epic) vs T12 | 91/34/257 | 109.8%/35.8% | 100/49/613 | 204.8 | 56.7 | 3 | 5 | ~60% | 52 |
| 13 | T15 Lvl25 Merc (legendary) vs T15 | 148/78/594 | 88.4%/31.3% | 152/72/987 | 223.1 | 71.6 | 5 | 9 | ~62% | 73 |
| 14 | T15 Lvl25 Assassin (legendary) vs T15 | 124/51/342 | 111.4%/40.0% | 152/72/987 | 260.6 | 73.7 | 4 | 5 | ~54% | 73 |
| 15 | T15 Lvl25 Tank (legendary) vs T15 | 108/95/907 | 72.3%/16.9% | 152/72/987 | 110.5 | 79.0 | 9 | 12 | ~55% | 73 |
| 16 | T15 Lvl25 Merc (legendary) vs T15 **Boss** | 148/78/594 | 88.4%/31.3% | 297/118/13320 | 207.1 | 146.7 | 65 | 5 | ~5% | 910 |

### 6.2 Team Fight: 3x Lvl25 Legendary vs T15 Boss

Boss: ATK 297, DEF 118, HP 13,320, Gold 910, Crit 35%

| Fighter | ATK | DEF | HP | Dmg/Hit | Turns Survive |
|---------|----:|----:|---:|--------:|--------------:|
| Mercenary | 148 | 78 | 594 | 207.1 | 5 |
| Assassin | 124 | 51 | 342 | 241.9 | 3 |
| Tank | 108 | 95 | 907 | 102.5 | 6 |

- **Combined team damage/turn**: 551.5
- **Turns to kill boss**: 25
- **Average turns any fighter survives**: 5

The boss attacks one random fighter per turn. The team needs ~25 turns but individual fighters survive only 3-6 turns. With 3 fighters, the team has roughly 14 total fighter-turns of survival (3+5+6), well short of 25. **Win probability: ~15-25% depending on RNG (who gets targeted, crits, dodges).**

Key insight: a solo fighter cannot beat a same-tier boss. Even a full team of max-level legendary fighters has only modest odds against the T15 boss. This is by design -- the roguelike forces eventual resets.

### 6.3 Detailed Battle: T1 Lvl1 Mercenary (no gear) vs T1 Enemy

**Turn-by-turn example (average rolls):**

Fighter: ATK 12, DEF 6, HP 78 | Enemy: ATK 10, DEF 4, HP 50

| Turn | Fighter Hits Enemy | Enemy Hits Fighter | Enemy HP | Fighter HP |
|------|------------------:|------------------:|---------:|-----------:|
| 1 | ~18 dmg (crit likely at 54.5%) | ~9 dmg | 32 | 69 |
| 2 | ~18 dmg | ~9 dmg | 14 | 60 |
| 3 | ~14 dmg (no crit) | -- | **0 (dead)** | 60 |

Result: Victory in 3 turns, ~80% win rate. Gold: 15.

### 6.4 Detailed Battle: T5 Lvl8 Mercenary vs T5 Boss

Fighter: ATK 59, DEF 33, HP 243 | Boss: ATK 66, DEF 28, HP 2,480

| Turn | Fighter Hits Boss | Boss Hits Fighter | Boss HP | Fighter HP |
|------|------------------:|------------------:|--------:|-----------:|
| 1 | ~94 dmg | ~51 dmg | 2,386 | 192 |
| 2 | ~94 dmg | ~51 dmg | 2,292 | 141 |
| 3 | ~94 dmg | ~51 dmg | 2,198 | 90 |
| 4 | ~94 dmg | ~51 dmg | 2,104 | 39 |
| 5 | ~94 dmg | ~51 dmg | 2,010 | **0 (KO)** |

Result: Fighter deals ~470 of 2,480 boss HP (19%) before dying. **Loss**. Need 5+ fighters or much higher levels.

### 6.5 Bleeding Enchantment Proc Analysis (10 Turns, T10 Enemy)

Enemy HP: 436, Fighter with Bleeding weapon.

Buildup: +20 per hit, threshold: 100, burst: 15% max HP = 65 damage.

| Turn | Buildup | Proc? | Bleed Dmg | Notes |
|------|--------:|------:|----------:|-------|
| 1 | 20 | No | 0 | |
| 2 | 40 | No | 0 | |
| 3 | 60 | No | 0 | |
| 4 | 80 | No | 0 | |
| 5 | 100 | Yes | 65 | Proc! Buildup resets to 0 |
| 6 | 20 | No | 0 | |
| 7 | 40 | No | 0 | |
| 8 | 60 | No | 0 | |
| 9 | 80 | No | 0 | |
| 10 | 100 | Yes | 65 | Proc! |

**Total bonus damage over 10 turns: 130** (2 procs).
Against T10 enemy (436 HP), this is 29.8% of max HP in bonus damage.
Effective DPS boost: 13.0 damage per hit on average.

---

## 7. Economy Flow Analysis

### 7.1 Income vs Costs by Tier

| Tier | Gold/Fight | Heal Cost | Net per 3 Fights | Upgrade Cost (to ~2x tier lvl) | Fights to Afford Upgrade |
|------|----------:|----------:|------------------:|-------------------------------:|------------------------:|
| 1 | 15 | 20 | 25 | 50 (lvl 2) | 4 |
| 2 | 16 | 22 | 26 | 106 (lvl 4) | 7 |
| 3 | 18 | 25 | 29 | 224 (lvl 6) | 13 |
| 4 | 21 | 28 | 35 | 471 (lvl 8) | 23 |
| 5 | 23 | 31 | 38 | 991 (lvl 10) | 44 |
| 6 | 26 | 35 | 43 | 2,085 (lvl 12) | 81 |
| 7 | 29 | 39 | 48 | 4,383 (lvl 14) | 152 |
| 8 | 33 | 44 | 55 | 9,216 (lvl 16) | 280 |
| 9 | 37 | 49 | 62 | 19,378 (lvl 18) | 524 |
| 10 | 41 | 55 | 68 | 40,743 (lvl 20) | 994 |
| 11 | 46 | 62 | 76 | 85,663 (lvl 22) | 1,863 |
| 12 | 52 | 69 | 87 | 180,107 (lvl 24) | 3,464 |
| 13 | 58 | 77 | 97 | 378,676 (lvl 26) | 6,529 |
| 14 | 65 | 87 | 108 | 796,166 (lvl 28) | 12,249 |
| 15 | 73 | 97 | 122 | 1,673,940 (lvl 30) | 22,931 |

### 7.2 Hiring Costs

| Fighters Alive | Hire Cost |
|---------------:|----------:|
| 0 | 40 |
| 1 | 64 |
| 2 | 102 |
| 3 | 163 |
| 4 | 262 |
| 5 | 419 |
| 6 | 671 |
| 7 | 1,073 |

### 7.3 Surgery Costs (Injury Cure)

| Times Used | Cost |
|-----------:|-----:|
| 0 | 80 |
| 1 | 100 |
| 2 | 125 |
| 3 | 156 |
| 4 | 195 |
| 5 | 244 |
| 6 | 305 |
| 7 | 381 |

### 7.4 Where the Economy Breaks

**The breaking point is around Tier 8-10.**

Key observations:

1. **Gold income grows at 1.12x per tier** but **upgrade costs grow at 1.45x per level**. Since fighters need ~2 levels per tier, the effective upgrade scaling per tier is 1.45^2 = 2.10x. Income grows at 1.12x. This means upgrades become exponentially harder to afford.

2. **At Tier 5**: an upgrade costs ~44 fights. Manageable.
   **At Tier 10**: an upgrade costs ~994 fights. Brutal.
   **At Tier 15**: an upgrade costs ~22,931 fights. Effectively impossible without boss gold.

3. **Boss gold is the only viable path** for late-game progression. A T10 boss drops 520g (equivalent to ~13 regular fights). A T15 boss drops 910g. But boss fights have very low win rates at-tier.

4. **Equipment costs plateau**: Legendary gear costs 90,000 total, which is ~1,233 fights at T15 income. This is a one-time investment that dramatically shifts power.

5. **The death spiral**: at high tiers, fighters die more often, requiring replacements (hire + level from scratch). Each death resets tens of thousands of gold worth of upgrades.

**This is intentional roguelike design**: the economy forces a natural ceiling around T10-15 where the player must accept losses, reset, and start fresh runs. The game is about managing resources within a doomed run, not infinite progression.

---

## 8. Injury Impact Analysis

### 8.1 Permadeath Chance by Injury Count

| Injuries | Death Chance on KO | Expected KOs Before Death |
|---------:|-------------------:|--------------------------:|
| 0 | 5% | 20 |
| 1 | 11% | ~9 |
| 2 | 17% | ~6 |
| 3 | 23% | ~4 |
| 4 | 29% | ~3 |
| 5 | 35% | ~3 |
| 6 | 41% | ~2 |
| 7 | 47% | ~2 |
| 8 | 53% | ~2 |
| 9 | 59% | ~1-2 |
| 10 (cap) | 60% | ~1-2 |

### 8.2 Injury Heal Costs

Formula: `50 * (1 + injuries_healed) * max(1, level)`

| Fighter Level | 1st Heal | 2nd Heal | 3rd Heal | 5th Heal |
|--------------:|---------:|---------:|---------:|---------:|
| 1 | 50 | 100 | 150 | 250 |
| 5 | 250 | 500 | 750 | 1,250 |
| 10 | 500 | 1,000 | 1,500 | 2,500 |
| 15 | 750 | 1,500 | 2,250 | 3,750 |
| 20 | 1,000 | 2,000 | 3,000 | 5,000 |
| 25 | 1,250 | 2,500 | 3,750 | 6,250 |

### 8.3 Fighter Viability by Injury Count

| Injuries | Status | Recommendation |
|---------:|--------|----------------|
| 0 | Pristine. 5% death chance -- very safe. | Full combat duty. |
| 1-2 | Bruised. 11-17% death risk. | Still viable, heal if affordable. |
| 3-4 | Damaged. 23-29% death risk. | Prioritize healing. Switch to expeditions if possible. |
| 5-6 | Critical. 35-41% death risk. | Heal immediately or retire from combat. Use for expeditions only. |
| 7+ | Walking dead. 47%+ death risk. | Each fight is a coin flip. Only use if desperate or expendable. |

### 8.4 Injury Economics

At Tier 10 with a Level 15 fighter:
- Income per fight: 41 gold
- 1st injury heal: 750 gold (18 fights)
- 3rd injury heal: 2,250 gold (55 fights)
- Surgery (first use): 80 gold
- Surgery (5th use): 244 gold

Surgery is far cheaper than injury healing but only removes 1 injury per use. The escalating surgery cost still makes it more economical than repeated injury heals for high-level fighters.

**Break-even analysis**: A Level 15 fighter costs ~6,356 gold to upgrade from Level 14 to 15. If they die, replacing them costs:
- Hire: 163-262 gold (depending on roster size)
- Leveling 1 to 15: sum of upgrades = ~11,285 gold total
- Total replacement: ~11,500 gold

Therefore, healing injuries is almost always cheaper than replacement, until the fighter accumulates 5+ injuries and their per-KO death risk exceeds 35%.

---

## Appendix A: Upgrade Cost Table

| Level | Cost to Upgrade | Cumulative Cost |
|------:|----------------:|----------------:|
| 1 | 35 | 35 |
| 2 | 50 | 85 |
| 3 | 73 | 158 |
| 4 | 106 | 264 |
| 5 | 154 | 418 |
| 6 | 224 | 642 |
| 7 | 325 | 967 |
| 8 | 471 | 1,438 |
| 9 | 683 | 2,121 |
| 10 | 991 | 3,112 |
| 11 | 1,437 | 4,549 |
| 12 | 2,085 | 6,634 |
| 13 | 3,023 | 9,657 |
| 14 | 4,383 | 14,040 |
| 15 | 6,356 | 20,396 |
| 16 | 9,216 | 29,612 |
| 17 | 13,364 | 42,976 |
| 18 | 19,378 | 62,354 |
| 19 | 28,099 | 90,453 |
| 20 | 40,743 | 131,196 |
| 21 | 59,078 | 190,274 |
| 22 | 85,663 | 275,937 |
| 23 | 124,212 | 400,149 |
| 24 | 180,107 | 580,256 |
| 25 | 261,156 | 841,412 |

## Appendix B: Relics by Rarity

| Relic | Rarity | ATK | DEF | HP | Diamond Cost |
|-------|--------|----:|----:|---:|-----------:|
| Cracked Idol | Common | 2 | 1 | 5 | 30 |
| Dusty Talisman | Common | 1 | 2 | 8 | 35 |
| Worn Signet | Common | 3 | 0 | 3 | 25 |
| Serpent Fang | Uncommon | 5 | 2 | 10 | 80 |
| Stone of Vigor | Uncommon | 2 | 5 | 15 | 90 |
| Wolf Pelt Cloak | Uncommon | 3 | 4 | 12 | 85 |
| Eye of the Storm | Rare | 10 | 5 | 20 | 250 |
| Frozen Heart | Rare | 5 | 10 | 25 | 300 |
| War Banner | Rare | 8 | 8 | 15 | 270 |
| Soul Lantern | Epic | 15 | 10 | 35 | 700 |
| Titan's Finger | Epic | 10 | 15 | 40 | 750 |
| Eclipse Shard | Epic | 18 | 8 | 30 | 680 |
| Heart of the Colossus | Legendary | 25 | 20 | 60 | 2,000 |
| Abyssal Crown | Legendary | 30 | 15 | 50 | 1,800 |
| Ember of Creation | Legendary | 20 | 25 | 70 | 2,200 |

## Appendix C: Expedition Data

| Expedition | Duration | Min Level | Danger% | Gold Range | Relic Chance | Relic Pool |
|------------|----------|-----------|---------|------------|-------------|------------|
| Dark Tunnels | 60s | 11 | 43% | 20-60 | 15% | Common/Uncommon |
| Bandit Outpost | 180s | 13 | 50% | 50-150 | 25% | Uncommon/Rare |
| Cursed Ruins | 300s | 15 | 57% | 100-300 | 35% | Rare/Epic |
| Dragon Wastes | 600s | 18 | 65% | 200-600 | 45% | Epic/Legendary |
| Void Rift | 900s | 22 | 75% | 400-1000 | 55% | Legendary |

---

## Appendix D: Prestige Bonus Formula

```
stat_multiplier = 1.0 + prestige_level * 0.02
```

All fighter ATK, DEF, and HP are multiplied by this value.

| Prestige Level | Stat Bonus | Multiplier |
|---:|---:|---:|
| 0 | +0% | 1.00x |
| 1 | +2% | 1.02x |
| 5 | +10% | 1.10x |
| 10 | +20% | 1.20x |
| 15 | +30% | 1.30x |
| 20 | +40% | 1.40x |

---

## Appendix E: Mutator Reward Multipliers

### Negative Mutators (increase reward)

| Mutator | Reward Mult | Effect |
|---|---:|---|
| Fragile | 1.5x | +30% incoming damage |
| Poverty | 1.5x | All prices x2 |
| No Healing | 2.0x | Cannot heal between fights |
| Glass Cannon | 1.3x | -50% HP, +50% ATK |
| Permadeath+ | 2.0x | First injury = instant death |
| Cursed Arena | 1.5x | Random debuff every 3 waves |
| Iron Foes | 1.3x | Enemies +25% DEF |
| Swift Enemies | 1.4x | Enemies +20% dodge |
| Crit Immune | 1.6x | Enemies immune to crits |
| Berserker Foes | 1.3x | Enemies enrage below 30% HP |
| No Equipment | 2.5x | Cannot equip items |
| One Fighter | 1.8x | Can only hire 1 fighter |
| Toxic Arena | 1.5x | 2% HP poison/turn |
| Gold Drain | 1.3x | Lose 5% gold per fight |
| Escalation | 1.6x | Enemy stats +5% per win |

### Positive Mutators (decrease reward)

| Mutator | Reward Mult | Effect |
|---|---:|---|
| Blessed | 0.7x | +20% all stats |
| Rich Start | 0.8x | x3 starting gold |
| Regeneration | 0.7x | 5% HP regen/turn |
| Lucky | 0.8x | +15% crit chance |
| Armored | 0.85x | +25% DEF |

### Combined Example
Fragile (1.5) + No Healing (2.0) + Escalation (1.6) = 1.5 * 2.0 * 1.6 = **4.8x reward multiplier**.

---

## Appendix F: Tier-Band Scaling

Heal/reward cost growth multiplier varies by tier band:

| Tier Band | Growth Multiplier |
|---|---:|
| T1-T15 | 1.20 |
| T16-T30 | 1.12 |
| T31-T50 | 1.08 |
| T51-T100 | 1.05 |
