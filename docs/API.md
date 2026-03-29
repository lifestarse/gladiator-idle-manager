# Gladiator Idle Manager -- API Reference

Public classes, methods, and utility functions from the core game modules.

---

## Table of Contents

- [Result (namedtuple)](#result-namedtuple)
- [GameEngine (game/engine.py)](#gameengine-gameenginepy)
- [BattleManager (game/battle.py)](#battlemanager-gamebattlepy)
- [BattleEvent (game/battle.py)](#battleevent-gamebattlepy)
- [BattleState (game/battle.py)](#battlestate-gamebattlepy)
- [CombatUnit (game/models.py)](#combatunit-gamemodelspy)
- [Fighter (game/models.py)](#fighter-gamemodelspy)
- [Enemy (game/models.py)](#enemy-gamemodelspy)
- [DifficultyScaler (game/models.py)](#difficultyscaler-gamemodelspy)
- [Utility Functions (game/models.py)](#utility-functions-gamemodelspy)

---

## Result (namedtuple)

```python
Result = namedtuple("Result", ["ok", "message", "code"], defaults=[True, "", ""])
```

Standard return type for all engine operations.

| Field     | Type   | Description                                        |
|-----------|--------|----------------------------------------------------|
| `ok`      | `bool` | `True` on success, `False` on failure              |
| `message` | `str`  | Human-readable text (toast/info on success, warning on failure) |
| `code`    | `str`  | Machine-readable tag, e.g. `"not_enough_gold"`, `"name_change"` |

---

## GameEngine (`game/engine.py`)

Central game state and all player-facing operations. Instantiated once; screens call its methods and read its attributes.

### Constructor

```python
GameEngine()
```

Initializes all run state (gold, fighters, arena tier, etc.) and persistent state (diamonds, achievements, records). Creates a `BattleManager` internally.

### Properties

| Property         | Type   | Description                                        |
|------------------|--------|----------------------------------------------------|
| `hire_cost`      | `int`  | Gold cost to hire next fighter (scales with alive count) |
| `battle_active`  | `bool` | `True` if a battle is in progress                  |
| `pending_reset`  | `bool` | `True` if roguelike reset is deferred (UI shows defeat first) |

---

### Fighter Management

#### `hire_gladiator(fighter_class="mercenary")`

Hire a new fighter of the given class.

| Parameter       | Type  | Default       | Description                          |
|-----------------|-------|---------------|--------------------------------------|
| `fighter_class` | `str` | `"mercenary"` | One of: `"mercenary"`, `"assassin"`, `"tank"` |

**Returns:** `Result` -- success message with name/class, or `"not_enough_gold"`.

```python
result = engine.hire_gladiator("assassin")
if result.ok:
    print(result.message)  # "Recruited Kaelith (Assassin)"
```

#### `upgrade_gladiator(index)`

Level up a fighter by spending gold.

| Parameter | Type  | Description             |
|-----------|-------|-------------------------|
| `index`   | `int` | Index in `engine.fighters` |

**Returns:** `Result` -- `"not_enough_gold"` or `"fighter_dead"` on failure.

#### `distribute_stat(fighter_idx, stat_name)`

Spend 1 unused stat point on a fighter.

| Parameter     | Type  | Description                                   |
|---------------|-------|-----------------------------------------------|
| `fighter_idx` | `int` | Index in `engine.fighters`                    |
| `stat_name`   | `str` | `"strength"`, `"agility"`, or `"vitality"`    |

**Returns:** `Result` -- `"no_points"` if no unused points remain.

#### `dismiss_dead(index)`

Remove a dead fighter from the roster. Returns equipment to inventory.

| Parameter | Type  | Description             |
|-----------|-------|-------------------------|
| `index`   | `int` | Index in `engine.fighters` |

**Returns:** `None`

#### `get_active_gladiator()`

**Returns:** `Fighter | None` -- the currently selected alive, non-expedition fighter.

#### `rename_fighter(fighter_idx, new_name)`

Rename a fighter. Costs 25 diamonds.

| Parameter     | Type  | Description           |
|---------------|-------|-----------------------|
| `fighter_idx` | `int` | Index in `engine.fighters` |
| `new_name`    | `str` | New display name      |

**Returns:** `Result`

---

### Battle

#### `start_auto_battle()`

Begin a pit battle: all available fighters vs a wave of enemies.

**Returns:** `list[BattleEvent]` -- initial battle events.

#### `start_boss_fight()`

Begin a boss fight against `current_enemy` (must be a boss).

**Returns:** `list[BattleEvent]` -- boss intro event.

#### `battle_next_turn()`

Execute one battle turn (all fighters attack, then all enemies attack).

**Returns:** `list[BattleEvent]` -- events for animation.

#### `battle_skip()`

Run the entire battle instantly (skip mode).

**Returns:** `list[BattleEvent]` -- all events from the complete battle.

#### `spawn_boss_enemy()`

Set `current_enemy` to a boss-tier enemy for the current arena tier.

**Returns:** `None`

#### `award_gold(amount)`

Add gold to the player's balance and total earned tracker.

| Parameter | Type    | Description       |
|-----------|---------|-------------------|
| `amount`  | `float` | Gold to add       |

**Returns:** `None`

#### `handle_fighter_death(fighter)`

Roll permadeath check, update graveyard if fighter dies permanently.

| Parameter | Type      | Description       |
|-----------|-----------|-------------------|
| `fighter` | `Fighter` | The downed fighter |

**Returns:** `bool` -- `True` if the fighter died permanently.

#### `execute_pending_reset()`

Called by UI after showing the defeat screen. Performs the roguelike reset.

**Returns:** `None`

#### `roguelike_reset()`

Full run reset on permadeath. Updates records (best tier, best kills, total runs), wipes gold/fighters/inventory/shards, re-spawns a starting enemy.

**Returns:** `None`

---

### Forge / Equipment

#### `get_forge_items()`

**Returns:** `list[dict]` -- all forge items with an `"affordable"` bool added.

#### `buy_forge_item(item_id)`

Buy an item from the forge; it goes to inventory.

| Parameter | Type  | Description             |
|-----------|-------|-------------------------|
| `item_id` | `str` | Item identifier, e.g. `"iron_sword"` |

**Returns:** `Result`

#### `equip_item_on(fighter_idx, item_id)`

Buy and equip an item directly onto a fighter.

| Parameter     | Type  | Description |
|---------------|-------|-------------|
| `fighter_idx` | `int` | Index in `engine.fighters` |
| `item_id`     | `str` | Forge item id |

**Returns:** `Result` -- blocked during battle.

#### `equip_from_inventory(fighter_idx, inv_index)`

Equip an item from inventory onto a fighter. Old item returns to inventory.

| Parameter     | Type  | Description |
|---------------|-------|-------------|
| `fighter_idx` | `int` | Index in `engine.fighters` |
| `inv_index`   | `int` | Index in `engine.inventory` |

**Returns:** `Result`

#### `unequip_from_fighter(fighter_idx, slot)`

Unequip an item from a fighter slot back to inventory. Blocked during battle.

| Parameter     | Type  | Description |
|---------------|-------|-------------|
| `fighter_idx` | `int` | Index in `engine.fighters` |
| `slot`        | `str` | `"weapon"`, `"armor"`, `"accessory"`, or `"relic"` |

**Returns:** `Result`

#### `sell_inventory_item(inv_index)`

Sell an inventory item for half its cost.

| Parameter   | Type  | Description |
|-------------|-------|-------------|
| `inv_index` | `int` | Index in `engine.inventory` |

**Returns:** `int` -- gold received (0 if invalid index).

#### `upgrade_item(item_dict)`

Upgrade any equipment item by +1 using metal shards. Relic upgrades cost 10x shards.

| Parameter   | Type   | Description |
|-------------|--------|-------------|
| `item_dict` | `dict` | Reference to the item dict (equipped or in inventory) |

**Returns:** `tuple[bool, str]` -- (success, message).

#### `enchant_weapon(weapon_dict, enchantment_id)`

Apply an enchantment to a weapon. Costs gold + tier-5 shards.

| Parameter        | Type   | Description |
|------------------|--------|-------------|
| `weapon_dict`    | `dict` | The weapon item dict |
| `enchantment_id` | `str`  | `"bleeding"`, `"frostbite"`, or `"poison"` |

**Returns:** `tuple[bool, str]` -- (success, message).

---

### Market (Consumables)

#### `get_shop_items()`

**Returns:** `list[dict]` -- consumable shop items with `"affordable"` flag.

#### `buy_item(item_id)`

Buy a consumable: heal potion, attack/defense tonic, or surgeon kit. Effect applies to the active gladiator.

| Parameter | Type  | Description |
|-----------|-------|-------------|
| `item_id` | `str` | `"heal_potion"`, `"atk_tonic"`, `"def_tonic"`, `"injury_cure"` |

**Returns:** `Result`

---

### Healing

#### `get_heal_cost()`

**Returns:** `int` -- gold cost for a single heal at current arena tier.

#### `get_hp_heal_cost(fighters=None)`

**Returns:** `int` -- total gold to heal all fighters to full HP.

#### `heal_all_hp(fighters=None)`

Heal all fighters to full HP. If gold is insufficient, spends all gold for partial heal (most damaged first).

**Returns:** `tuple[int, int]` -- (fighters healed, gold spent).

#### `heal_fighter_injury(index)`

Heal one injury from a fighter. Cost scales with injuries healed and level.

| Parameter | Type  | Description |
|-----------|-------|-------------|
| `index`   | `int` | Index in `engine.fighters` |

**Returns:** `tuple[bool, str]` -- (success, message).

#### `heal_all_injuries()`

Heal all injuries from all fighters at once.

**Returns:** `tuple[bool, str]` -- (success, message).

#### `heal_all_injuries_cost()`

**Returns:** `int` -- total gold cost to heal every injury on every fighter.

---

### Expeditions

#### `send_on_expedition(fighter_idx, expedition_id)`

Send a fighter on an expedition.

| Parameter       | Type  | Description |
|-----------------|-------|-------------|
| `fighter_idx`   | `int` | Index in `engine.fighters` |
| `expedition_id` | `str` | `"dark_tunnels"`, `"bandit_outpost"`, `"cursed_ruins"`, `"dragon_wastes"`, `"void_rift"` |

**Returns:** `Result` -- checks alive, level requirement, slot limit.

#### `check_expeditions()`

Poll all fighters on expedition. Resolves completed ones: rolls danger, grants shards/relics, applies injuries.

**Returns:** `list[str]` -- log messages for each resolved expedition.

#### `get_expedition_status()`

**Returns:** `list[dict]` -- active expeditions with `fighter_name`, `expedition_name`, `remaining` (seconds), `remaining_text`.

#### `get_expeditions()`

**Returns:** `list[dict]` -- all expedition definitions with `affordable` and `duration_text`.

---

### Achievements and Quests

#### `check_achievements()`

Scan all achievement conditions. Awards diamonds for newly unlocked ones. Also triggers `check_quests()`.

**Returns:** `list[dict]` -- newly unlocked achievements.

#### `check_quests()`

Evaluate story quest conditions. Awards diamonds/shards. Cascades chapter unlocks.

**Returns:** `list[dict]` -- newly completed quests.

#### `get_achievements()`

**Returns:** `list[dict]` -- all achievements with `"unlocked"` bool.

---

### Diamond Shop and IAP

#### `get_diamond_shop()`

**Returns:** `list[dict]` -- diamond shop items with dynamic costs and `"affordable"` flag.

#### `buy_diamond_item(item_id)`

Purchase a diamond shop item. Supported items: `"name_change"`, `"revive_token"`, `"heal_all_injuries_diamond"`, `"extra_expedition_slot"`, `"golden_armor"`.

**Returns:** `Result`

#### `purchase_remove_ads()`

Mark ads as removed (IAP callback).

#### `purchase_diamonds(bundle_id)`

Add diamonds from a purchased bundle.

**Returns:** `Result`

---

### Save / Load

#### `save()`

Serialize full game state to JSON file (`SAVE_PATH`).

**Returns:** `dict` -- the saved data.

#### `load(data=None)`

Load game state from JSON file or provided dict. Migrates old save formats (relics list to equipment slot). Spawns default fighter if save is empty.

| Parameter | Type         | Description |
|-----------|--------------|-------------|
| `data`    | `dict|None`  | Pre-loaded save data, or `None` to read from file |

**Returns:** `None`

#### `get_save_data_json()`

**Returns:** `str` -- JSON string of the current save (calls `save()` internally).

---

### Idle / Tick

#### `idle_tick(dt)`

Called each frame. Checks expedition completions.

**Returns:** `list[str]` -- expedition result messages.

---

### Ads

#### `should_show_interstitial()`

**Returns:** `bool` -- `True` every 5 wins (if ads not removed).

#### `should_show_banner()`

**Returns:** `bool` -- `True` if ads not removed.

---

## BattleManager (`game/battle.py`)

Manages turn-based battles with luck-based combat. Created and owned by `GameEngine`.

### Constructor

```python
BattleManager(engine: GameEngine)
```

### Methods

#### `start_auto_battle()`

Initialize a pit battle: all available fighters vs N enemies (N = fighter count). The first enemy is `engine.current_enemy`.

**Returns:** `list[BattleEvent]` -- start events.

#### `start_boss_fight()`

Initialize a boss fight against `engine.current_enemy`.

**Returns:** `list[BattleEvent]` -- boss intro event.

#### `do_turn()`

Execute one full turn: status ticks, all fighters attack, all enemies attack. Handles kills, enchantment buildup/triggers, permadeath, victory/defeat transitions.

**Returns:** `list[BattleEvent]` -- events for UI animation.

#### `do_full_battle()`

Run the entire battle instantly by looping `do_turn()` until victory/defeat (max 200 events).

**Returns:** `list[BattleEvent]` -- all events.

### Properties

| Property    | Type   | Description                  |
|-------------|--------|------------------------------|
| `is_active` | `bool` | `True` if battle is ongoing  |

---

## BattleEvent (`game/battle.py`)

Single event in the battle log, used for UI animation.

```python
BattleEvent(event_type, attacker="", defender="", damage=0,
            message="", is_kill=False, is_crit=False, is_boss=False, is_dodge=False)
```

| Field        | Type   | Description                                |
|--------------|--------|--------------------------------------------|
| `event_type` | `str`  | `"attack"`, `"death"`, `"victory"`, `"defeat"`, `"message"`, `"boss_intro"`, `"status"` |
| `attacker`   | `str`  | Attacker name                              |
| `defender`   | `str`  | Defender name                              |
| `damage`     | `int`  | Damage dealt (or gold earned on victory)   |
| `message`    | `str`  | Human-readable log line                    |
| `is_kill`    | `bool` | Target was killed                          |
| `is_crit`    | `bool` | Attack was a critical hit                  |
| `is_boss`    | `bool` | Boss fight context                         |
| `is_dodge`   | `bool` | Attack was dodged                          |

---

## BattleState (`game/battle.py`)

Tracks the state of an ongoing battle.

| Attribute             | Type              | Description                          |
|-----------------------|-------------------|--------------------------------------|
| `phase`               | `BattlePhase`     | Current phase (IDLE, STARTING, TURN_PLAYER, etc.) |
| `turn_number`         | `int`             | Current turn count                   |
| `player_fighters`     | `list[Fighter]`   | Fighters participating               |
| `enemies`             | `list[Enemy]`     | Enemies in battle                    |
| `gold_earned`         | `int`             | Total gold earned this battle        |
| `is_boss_fight`       | `bool`            | Whether this is a boss fight         |

---

## BattlePhase (Enum)

```python
class BattlePhase(Enum):
    IDLE, STARTING, TURN_PLAYER, TURN_ENEMY, TURN_RESOLVE,
    VICTORY, DEFEAT, BOSS_INTRO
```

---

## CombatUnit (`game/models.py`)

Base class for `Fighter` and `Enemy`. Provides shared combat methods.

#### `take_damage(raw_dmg)`

Apply damage after dodge check and defense reduction.

| Parameter | Type  | Description      |
|-----------|-------|------------------|
| `raw_dmg` | `int` | Pre-reduction damage |

**Returns:** `int` -- actual damage dealt (0 if dodged).

#### `deal_damage()`

Roll attack damage with +/-30% variance.

**Returns:** `int` -- damage value.

---

## Fighter (`game/models.py`)

Player-owned arena fighter. Extends `CombatUnit`.

### Constructor

```python
Fighter(name=None, level=1, fighter_class="mercenary")
```

| Parameter       | Type       | Default       | Description              |
|-----------------|------------|---------------|--------------------------|
| `name`          | `str|None` | `None`        | Random name if omitted   |
| `level`         | `int`      | `1`           | Starting level           |
| `fighter_class` | `str`      | `"mercenary"` | `"mercenary"`, `"assassin"`, or `"tank"` |

### Core Attributes

| Attribute       | Type   | Description                          |
|-----------------|--------|--------------------------------------|
| `strength`      | `int`  | STR stat (distributable)             |
| `agility`       | `int`  | AGI stat (distributable)             |
| `vitality`      | `int`  | VIT stat (distributable)             |
| `unused_points` | `int`  | Unspent stat points                  |
| `level`         | `int`  | Fighter level                        |
| `alive`         | `bool` | `False` after permadeath             |
| `injuries`      | `int`  | Current injury count (stacks death chance) |
| `kills`         | `int`  | Lifetime kill count                  |
| `equipment`     | `dict` | `{weapon, armor, accessory, relic}` slots |
| `hp`            | `int`  | Current hit points                   |

### Computed Properties

| Property        | Type    | Formula / Description                                        |
|-----------------|---------|--------------------------------------------------------------|
| `attack`        | `int`   | `STR * 2 + base_attack + (level-1) + equip_atk`             |
| `defense`       | `int`   | `VIT + base_defense + equip_def`                             |
| `max_hp`        | `int`   | `(30 + VIT*8 + base_hp + (level-1)*5) * hp_mult + equip_hp` |
| `crit_chance`   | `float` | `AGI / (AGI + 5) + crit_bonus` (asymptotic, never 100%)     |
| `crit_mult`     | `float` | `1.8 + AGI * 0.04` (no cap)                                 |
| `dodge_chance`  | `float` | `1 - 1/(1 + raw*0.6)` where `raw = AGI*0.02 + dodge_bonus`  |
| `death_chance`  | `float` | `min(0.60, 0.05 + injuries * 0.06)`                         |
| `power_rating`  | `int`   | `attack + defense + max_hp // 5`                             |
| `upgrade_cost`  | `int`   | `DifficultyScaler.upgrade_cost(level)`                       |
| `class_name`    | `str`   | Human-readable class name                                    |
| `available`     | `bool`  | `alive and not on_expedition`                                |

### Methods

#### `distribute_point(stat)`

Spend 1 unused point on a stat. If `"vitality"`, also heals the HP gained.

| Parameter | Type  | Description                            |
|-----------|-------|----------------------------------------|
| `stat`    | `str` | `"strength"`, `"agility"`, or `"vitality"` |

**Returns:** `bool` -- `True` if point was spent.

#### `level_up()`

Increment level, grant `points_per_level` unused points, heal to full HP.

**Returns:** `None`

#### `heal()`

Restore HP to `max_hp`.

**Returns:** `None`

#### `check_permadeath()`

Roll against `death_chance`. If failed: `alive = False`. Otherwise: `injuries += 1`.

**Returns:** `bool` -- `True` if the fighter died permanently.

#### `get_injury_heal_cost()`

**Returns:** `int` -- gold cost: `50 * (1 + injuries_healed) * max(1, level)`.

#### `equip_item(item)`

Equip an item dict into its slot. Returns the previously equipped item. Adjusts HP for net HP change.

| Parameter | Type   | Description |
|-----------|--------|-------------|
| `item`    | `dict` | Item dict with `"slot"` key |

**Returns:** `dict | None` -- old item, or `None`.

#### `unequip_item(slot)`

Remove item from slot, cap HP to new max.

| Parameter | Type  | Description |
|-----------|-------|-------------|
| `slot`    | `str` | Equipment slot name |

**Returns:** `dict | None` -- removed item, or `None`.

#### `to_dict()`

Serialize fighter to a JSON-safe dict.

**Returns:** `dict`

#### `from_dict(data)` (classmethod)

Deserialize a fighter from a save dict. Handles migration of old relic format.

| Parameter | Type   | Description |
|-----------|--------|-------------|
| `data`    | `dict` | Saved fighter data |

**Returns:** `Fighter`

---

## Enemy (`game/models.py`)

Arena opponent with exponential stat growth. Extends `CombatUnit`.

### Constructor

```python
Enemy(tier=1)
```

| Parameter | Type  | Default | Description            |
|-----------|-------|---------|------------------------|
| `tier`    | `int` | `1`     | Arena tier (scales all stats) |

Stats are set via `DifficultyScaler.enemy_stats(tier)`. Enemies also have tier-scaling `crit_chance` and `dodge_chance`.

### Properties

| Property      | Type    | Description                                  |
|---------------|---------|----------------------------------------------|
| `crit_mult`   | `float` | Always `1.8`                                 |
| `crit_chance`  | `float` | `min(0.30, 0.05 + tier * 0.015)`            |
| `dodge_chance` | `float` | `min(0.20, tier * 0.01)`                    |
| `gold_reward`  | `int`   | Gold dropped on death                        |
| `is_boss`      | `bool`  | `True` for boss enemies                     |

### Class Methods

#### `create_boss(arena_tier)`

Create a boss enemy: +2 tier offset, 10x HP, 1.5x ATK, 1.3x DEF, 10x gold, boosted crit, no dodge.

| Parameter    | Type  | Description     |
|--------------|-------|-----------------|
| `arena_tier` | `int` | Current arena tier |

**Returns:** `Enemy` -- a boss instance.

---

## DifficultyScaler (`game/models.py`)

Static methods for all economy and difficulty scaling. Roguelike-balanced: enemy stats scale steeply, rewards grow slower (intentional scarcity).

#### `enemy_stats(tier)`

**Returns:** `tuple[int, int, int]` -- `(attack, defense, hp)` for an enemy at the given tier.

```python
atk, defense, hp = DifficultyScaler.enemy_stats(5)
```

#### `enemy_reward(tier)`

**Returns:** `int` -- gold reward for killing an enemy at the given tier.

#### `hire_cost(alive_count)`

**Returns:** `int` -- gold cost to hire when `alive_count` fighters are already alive.

#### `upgrade_cost(level)`

**Returns:** `int` -- gold cost to upgrade a fighter at the given level.

#### `heal_cost(arena_tier)`

**Returns:** `int` -- gold cost for a heal potion at the given arena tier.

#### `surgeon_cost(times_used)`

**Returns:** `int` -- gold cost for injury cure, scaling with number of prior uses.

### Scaling Constants

| Constant          | Value  | Description                    |
|-------------------|--------|--------------------------------|
| `ENEMY_ATK_BASE`  | 7      | Base enemy attack              |
| `ENEMY_ATK_EXPO`  | 1.08   | Attack exponential growth      |
| `ENEMY_HP_BASE`   | 35     | Base enemy HP                  |
| `ENEMY_HP_EXPO`   | 1.10   | HP exponential growth          |
| `REWARD_BASE`     | 15     | Base gold reward               |
| `REWARD_EXPO`     | 1.12   | Reward exponential growth      |
| `HIRE_BASE`       | 40     | Base hire cost                 |
| `HIRE_EXPO`       | 1.6    | Hire cost exponential growth   |
| `UPGRADE_BASE`    | 35     | Base upgrade cost              |
| `UPGRADE_EXPO`    | 1.45   | Upgrade cost exponential growth |

---

## Utility Functions (`game/models.py`)

#### `fmt_num(n)`

Format large numbers with suffixes: `1500` -> `"1.5K"`, up to decillions (`Dc`).

```python
fmt_num(1500)      # "1.5K"
fmt_num(2500000)   # "2.5M"
fmt_num(42)        # "42"
```

**Returns:** `str`

#### `calc_item_stats(item, fighter=None)`

Calculate total `(atk, def, hp)` for any item dict, optionally with fighter-scaled upgrade bonuses.

| Parameter | Type           | Description |
|-----------|----------------|-------------|
| `item`    | `dict`         | Item dict with atk/def/hp/slot/upgrade_level keys |
| `fighter` | `Fighter|None` | If provided, upgrade bonuses scale with fighter stats |

**Returns:** `tuple[int, int, int]` -- `(atk, def, hp)`.

#### `item_display_name(item_dict)`

**Returns:** `str` -- the item's display name from `item_dict["name"]`.

#### `get_boss_name(tier)`

Deterministic boss name for a tier. Tiers 1-100 use a curated list; beyond that, names are procedurally generated from prefix/suffix pools.

**Returns:** `str`

#### `get_max_upgrade(item)`

Max upgrade level based on item rarity: Common=5, Uncommon=10, Rare=15, Epic=20, Legendary=25.

| Parameter | Type   | Description |
|-----------|--------|-------------|
| `item`    | `dict` | Item dict with `"rarity"` key |

**Returns:** `int`

#### `get_upgrade_tier(target_level)`

Determine which shard tier and count are needed to upgrade to `+target_level`.

| Parameter      | Type  | Description |
|----------------|-------|-------------|
| `target_level` | `int` | The upgrade level being targeted |

**Returns:** `tuple[int, int]` -- `(shard_tier, shard_count)`.

```python
tier, count = get_upgrade_tier(7)  # tier=2, count=2
```

#### `get_dynamic_shop_items(arena_tier, surgeon_uses)`

Generate the consumable shop items with prices scaled to the current arena tier.

| Parameter      | Type  | Description |
|----------------|-------|-------------|
| `arena_tier`   | `int` | Current arena tier   |
| `surgeon_uses` | `int` | Times surgeon kit has been used |

**Returns:** `list[dict]` -- consumable item dicts with `id`, `name`, `desc`, `cost`, `effect`.

---

## PrestigeManager (`game/prestige.py`)

Manages prestige progression -- permanent bonuses across roguelike runs. Created and owned by `GameEngine` as `engine.prestige_manager`.

### Methods

#### `can_prestige()`

**Returns:** `bool` -- `True` if `engine.arena_tier >= 15`.

#### `get_stat_bonus()`

**Returns:** `float` -- stat multiplier, e.g. `1.10` for prestige level 5 (+10%).

Formula: `1.0 + engine.prestige_level * 0.02`

#### `do_prestige()`

Execute prestige: increment level, perform roguelike reset, apply new stat bonus to all fighters, save.

**Returns:** `Result` -- success with description, or `"not_ready"` if tier < 15.

#### `is_unlocked(feature_id)`

Check if a prestige-gated feature is unlocked at the current prestige level.

| Parameter    | Type  | Description |
|--------------|-------|-------------|
| `feature_id` | `str` | e.g. `"mutators"`, `"class_berserker"`, `"dual_enchantment"` |

**Returns:** `bool`

#### `get_all_unlocks()`

**Returns:** `list[str]` -- all feature IDs unlocked at current prestige level.

#### `get_prestige_reward_preview()`

**Returns:** `dict` -- preview of the next prestige level: `level`, `stat_bonus_pct`, `unlock`, `description`.

---

## MutatorRegistry (`game/mutators.py`)

Registry for mutator definitions. Loaded from `data/mutators.json` via `DataLoader`. Module-level singleton: `mutator_registry`.

### Methods

#### `load(mutator_list)`

Load mutators from a list of dicts (each must have `"id"`).

#### `get(mutator_id)`

**Returns:** `dict | None` -- the mutator definition, or `None`.

#### `get_all()`

**Returns:** `list[dict]` -- all loaded mutators.

#### `get_all_negative()`

**Returns:** `list[dict]` -- mutators where `type == "negative"`.

#### `get_all_positive()`

**Returns:** `list[dict]` -- mutators where `type == "positive"`.

#### `calc_reward_multiplier(active_ids)`

Calculate combined reward multiplier by multiplying all active mutators' `reward_mult` values.

| Parameter    | Type        | Description |
|--------------|-------------|-------------|
| `active_ids` | `list[str]` | List of active mutator IDs |

**Returns:** `float`

#### `has_effect(active_ids, effect_key)`

Check if any active mutator has a specific effect key.

**Returns:** `bool`

#### `get_effect_value(active_ids, effect_key, default=None)`

Get the value of a specific effect from the first matching active mutator.

**Returns:** value or `default`.

---

## DataLoader (`game/data_loader.py`)

Singleton that reads every JSON file in `data/` once and exposes typed accessors. Module-level instance: `data_loader`.

### Methods

#### `load_all()`

Load all data files. Safe to call multiple times (no-op after first load).

### Properties

| Property          | Type        | Source File           |
|-------------------|-------------|-----------------------|
| `fighter_names`   | `list[str]` | `fighter_names.json`  |
| `weapons`         | `list[dict]`| `weapons.json`        |
| `armor`           | `list[dict]`| `armor.json`          |
| `accessories`     | `list[dict]`| `accessories.json`    |
| `relics`          | `list[dict]`| `relics.json`         |
| `enchantments`    | `dict`      | `enchantments.json`   |
| `achievements_data`| `list[dict]`| `achievements.json`  |
| `injuries`        | `list[dict]`| `injuries.json`       |
| `lore`            | `list[dict]`| `lore.json`           |
| `fighter_classes`  | `dict`     | `fighter_classes.json` |
| `enemies`         | `list[dict]`| `enemies.json`        |
| `enemies_by_tier` | `dict`      | Grouped from enemies  |
| `boss_modifiers`  | `dict`      | `boss_modifiers.json` |
| `mutators`        | `dict`      | `mutators.json`       |
| `all_forge_items`  | `list[dict]`| weapons + armor + accessories combined |
