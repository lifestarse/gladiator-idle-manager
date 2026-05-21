# Build: 1
"""Unit tests for enchantment effect handlers (_trigger_enchantment).

Covers each of the 9 effect branches:
  burst, burst_debuff, dot, skip_turn, def_reduction, chain_burst,
  atk_reduction, lifesteal, burst_conditional.

Uses a minimal fake BattleState so we don't spin up the whole BattleManager.
Each test builds a fresh enemy + tracker, calls _trigger_enchantment, then
asserts the observable mutation on target / tracker / state.
"""
from game.battle._enchantments import _trigger_enchantment, _init_enemy_status


class _FakeState:
    """Minimal shape expected by _trigger_enchantment."""
    def __init__(self, enemies=None, player_fighters=None):
        self.enemies = enemies or []
        self.player_fighters = player_fighters or []
        self.enemy_status = {}


class _FakeEnemy:
    def __init__(self, name="Dummy", hp=200, max_hp=200, attack=30,
                 defense=10, is_boss=False):
        self.name = name
        self.hp = hp
        self.max_hp = max_hp
        self.attack = attack
        self.defense = defense
        self.is_boss = is_boss


class _FakeFighter:
    def __init__(self, name="Hero", hp=40, max_hp=100, equipment=None, alive=True):
        self.name = name
        self.hp = hp
        self.max_hp = max_hp
        self.equipment = equipment or {}
        self.alive = alive


def _setup(enemy, fighters=None):
    state = _FakeState(enemies=[enemy], player_fighters=fighters or [])
    _init_enemy_status(state, enemy)
    return state


# ---- burst (bleeding, burn) ----------------------------------------------

def test_burst_deals_percent_max_hp_damage():
    enemy = _FakeEnemy(hp=200, max_hp=200)
    state = _setup(enemy)
    ench = {"effect": "burst", "burst_pct": 0.15, "name": "Bleeding"}

    events = _trigger_enchantment(state, enemy, "bleeding", ench)

    assert enemy.hp == 170  # 200 - 30 (15% of 200)
    assert len(events) == 1
    assert events[0].defender == "Dummy"


# ---- burst_debuff (frostbite) ---------------------------------------------

def test_frostbite_burst_plus_atk_debuff():
    enemy = _FakeEnemy(hp=200, max_hp=200, attack=100)
    state = _setup(enemy)
    ench = {
        "effect": "burst_debuff", "burst_pct": 0.10,
        "atk_reduction_pct": 0.20, "debuff_turns": 3,
    }

    _trigger_enchantment(state, enemy, "frostbite", ench)

    assert enemy.hp == 180  # 200 - 20 (10%)
    assert enemy.attack == 80  # 100 * 0.8
    effects = state.enemy_status[id(enemy)].active_effects
    assert any(e["type"] == "atk_debuff" and e["turns_left"] == 3 for e in effects)


# ---- dot (poison) ---------------------------------------------------------

def test_poison_queues_dot_effect():
    enemy = _FakeEnemy()
    state = _setup(enemy)
    hp_before = enemy.hp
    ench = {"effect": "dot", "dot_turns": 4, "dot_pct": 0.05}

    _trigger_enchantment(state, enemy, "poison", ench)

    # Poison applies over time; no immediate damage on trigger
    assert enemy.hp == hp_before
    effects = state.enemy_status[id(enemy)].active_effects
    assert len(effects) == 1
    assert effects[0]["type"] == "poison_dot"
    assert effects[0]["turns_left"] == 4
    assert effects[0]["dot_pct"] == 0.05


# ---- skip_turn (paralyze) -------------------------------------------------

def test_paralyze_sets_skip_next_turn_flag():
    enemy = _FakeEnemy()
    state = _setup(enemy)
    ench = {"effect": "skip_turn"}

    _trigger_enchantment(state, enemy, "paralyze", ench)

    assert state.enemy_status[id(enemy)].skip_next_turn is True


# ---- def_reduction (corruption) -------------------------------------------

def test_corruption_reduces_defense_and_queues_debuff():
    enemy = _FakeEnemy(defense=100)
    state = _setup(enemy)
    ench = {"effect": "def_reduction", "reduction_pct": 0.30, "debuff_turns": 3}

    _trigger_enchantment(state, enemy, "corruption", ench)

    assert enemy.defense == 70  # 100 * 0.7
    effects = state.enemy_status[id(enemy)].active_effects
    assert any(e["type"] == "def_debuff" and e["turns_left"] == 3 for e in effects)


# ---- chain_burst (lightning) ----------------------------------------------

def test_lightning_hits_target_and_chains_to_others():
    target = _FakeEnemy(name="Primary", hp=200, max_hp=200)
    other1 = _FakeEnemy(name="Other1", hp=100, max_hp=100)
    other2 = _FakeEnemy(name="Other2", hp=50, max_hp=50)
    state = _FakeState(enemies=[target, other1, other2])
    for e in (target, other1, other2):
        _init_enemy_status(state, e)
    ench = {"effect": "chain_burst", "burst_pct": 0.10}

    _trigger_enchantment(state, target, "lightning", ench)

    # 10% of each enemy's max_hp, never 0 (max(1, ...))
    assert target.hp == 180  # -20
    assert other1.hp == 90   # -10
    assert other2.hp == 45   # -5


def test_lightning_skips_dead_enemies():
    target = _FakeEnemy(name="Primary", hp=200, max_hp=200)
    dead = _FakeEnemy(name="Corpse", hp=0, max_hp=100)
    state = _FakeState(enemies=[target, dead])
    for e in (target, dead):
        _init_enemy_status(state, e)
    ench = {"effect": "chain_burst", "burst_pct": 0.10}

    _trigger_enchantment(state, target, "lightning", ench)

    assert target.hp == 180
    assert dead.hp == 0  # unchanged — dead stays dead


# ---- atk_reduction (weaken) -----------------------------------------------

def test_weaken_reduces_attack_and_queues_debuff():
    enemy = _FakeEnemy(attack=200)
    state = _setup(enemy)
    ench = {"effect": "atk_reduction", "reduction_pct": 0.25, "debuff_turns": 4}

    _trigger_enchantment(state, enemy, "weaken", ench)

    assert enemy.attack == 150  # 200 * 0.75
    effects = state.enemy_status[id(enemy)].active_effects
    assert any(e["type"] == "atk_debuff" and e["turns_left"] == 4 for e in effects)


# ---- lifesteal (drain) ----------------------------------------------------

def test_drain_heals_fighter_carrying_the_enchantment():
    enemy = _FakeEnemy()
    hero = _FakeFighter(
        name="Drainer", hp=40, max_hp=100,
        equipment={"weapon": {"enchantment": "drain"}},
    )
    bystander = _FakeFighter(
        name="Plain", hp=50, max_hp=100,
        equipment={"weapon": {"enchantment": None}},
    )
    state = _FakeState(enemies=[enemy], player_fighters=[bystander, hero])
    _init_enemy_status(state, enemy)
    ench = {"effect": "lifesteal", "heal_pct": 0.10}

    _trigger_enchantment(state, enemy, "drain", ench)

    # Only the hero with drain weapon heals (max_hp * 0.10 = 10)
    assert hero.hp == 50
    assert bystander.hp == 50  # untouched


# ---- burst_conditional (holy_fire) ----------------------------------------

def test_holy_fire_normal_enemy_uses_normal_pct():
    enemy = _FakeEnemy(hp=200, max_hp=200, is_boss=False)
    state = _setup(enemy)
    ench = {
        "effect": "burst_conditional",
        "burst_pct_normal": 0.10, "burst_pct_boss": 0.25,
    }

    _trigger_enchantment(state, enemy, "holy_fire", ench)

    assert enemy.hp == 180  # 200 - 20 (10%)


def test_holy_fire_boss_uses_boss_pct():
    boss = _FakeEnemy(hp=1000, max_hp=1000, is_boss=True)
    state = _setup(boss)
    ench = {
        "effect": "burst_conditional",
        "burst_pct_normal": 0.10, "burst_pct_boss": 0.25,
    }

    _trigger_enchantment(state, boss, "holy_fire", ench)

    assert boss.hp == 750  # 1000 - 250 (25%)
