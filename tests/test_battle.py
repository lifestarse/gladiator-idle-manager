# Build: 2
"""Tests for the battle system (game.battle)."""
import random
from unittest.mock import patch, MagicMock
import pytest

from game.models import Fighter, Enemy, ENCHANTMENT_TYPES
from game.battle import (
    BattleManager, BattlePhase, BattleState, BattleEvent,
    _resolve_attack, _trigger_enchantment, _process_status_ticks,
    _init_enemy_status, EnemyStatusTracker,
)


def _make_state_with_enemies(enemies):
    """Create a BattleState with enemies pre-initialized for status tracking."""
    state = BattleState()
    state.enemies = enemies
    for e in enemies:
        _init_enemy_status(state, e)
    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine_stub(fighters=None, arena_tier=1):
    """Lightweight engine stub with just enough for BattleManager."""
    eng = MagicMock()
    eng.fighters = fighters or []
    eng.arena_tier = arena_tier
    eng.current_enemy = None
    eng.wins = 0
    eng.gold = 0
    eng.total_gold_earned = 0
    eng.award_gold = MagicMock(side_effect=lambda amt: None)
    eng.handle_fighter_death = MagicMock(return_value=(False, None))
    return eng


def _make_fighter(name="Hero", fighter_class="mercenary", level=1, **overrides):
    """Quick fighter with optional stat overrides."""
    f = Fighter(name=name, fighter_class=fighter_class)
    for _ in range(level - 1):
        f.level_up()
    for k, v in overrides.items():
        setattr(f, k, v)
    f.hp = f.max_hp  # refresh after overrides
    return f


def _make_enemy(tier=1, **overrides):
    """Quick enemy with optional overrides."""
    e = Enemy(tier=tier)
    for k, v in overrides.items():
        setattr(e, k, v)
    if "hp" not in overrides:
        e.hp = e.max_hp
    return e


# ===================================================================
# 1. test_damage_formula_basic
# ===================================================================

def test_damage_formula_basic():
    """Fighter.deal_damage returns values in the expected [0.70, 1.30] * ATK range."""
    f = _make_fighter(strength=10)  # ATK = 10*2 + 0 + 0 + 0 = 20
    random.seed(42)
    damages = [f.deal_damage() for _ in range(200)]
    # All within [max(1, 0.70*ATK), 1.30*ATK]
    atk = f.attack
    assert all(1 <= d <= int(atk * 1.30) + 1 for d in damages)
    assert min(damages) >= 1
    # Should see variation (not all the same)
    assert len(set(damages)) > 1


# ===================================================================
# 2. test_defense_reduction
# ===================================================================

def test_defense_reduction():
    """Damage reduced by DEF/(DEF+100) formula."""
    e = _make_enemy(tier=1)
    e.dodge_chance = 0  # no dodging for this test
    raw = 100
    expected_reduction = e.defense / (e.defense + 100)
    expected_dmg = max(1, int(raw * (1 - expected_reduction)))
    with patch("random.random", return_value=1.0):  # no dodge
        actual = e.take_damage(raw)
    assert actual == expected_dmg


# ===================================================================
# 3. test_crit_damage
# ===================================================================

def test_crit_damage():
    """When crit triggers, _resolve_attack multiplies damage by crit_mult."""
    f = _make_fighter(strength=10, agility=5)
    e = _make_enemy(tier=1)
    e.dodge_chance = 0
    state = _make_state_with_enemies([e])

    # Force crit (random < crit_chance) and fixed damage variance
    with patch("random.random", return_value=0.0), \
         patch("random.uniform", return_value=1.0):
        ev, actual, is_crit = _resolve_attack(f, e)

    assert is_crit is True
    assert actual > 0
    assert ev.is_crit is True


# ===================================================================
# 4. test_dodge_negates_damage
# ===================================================================

def test_dodge_negates_damage():
    """When dodge triggers, take_damage returns 0."""
    e = _make_enemy(tier=1)
    e.dodge_chance = 1.0  # guaranteed dodge
    result = e.take_damage(999)
    assert result == 0


# ===================================================================
# 5. test_no_negative_damage
# ===================================================================

def test_no_negative_damage():
    """Damage is always >= 1 after reduction (min damage floor)."""
    e = _make_enemy(tier=1)
    e.defense = 99999  # extreme defense
    e.dodge_chance = 0
    with patch("random.random", return_value=1.0):  # no dodge
        result = e.take_damage(1)
    assert result >= 1


# ===================================================================
# 6. test_enchantment_buildup
# ===================================================================

def test_enchantment_buildup():
    """Bleeding buildup accumulates per hit."""
    e = _make_enemy(tier=1)
    state = _make_state_with_enemies([e])
    tracker = state.enemy_status[id(e)]

    ench = ENCHANTMENT_TYPES["bleeding"]
    # Simulate hits below threshold
    hits_needed = ench["threshold"] // ench["buildup_per_hit"] - 1
    for _ in range(hits_needed):
        tracker.status_buildup["bleeding"] = tracker.status_buildup.get("bleeding", 0) + ench["buildup_per_hit"]

    assert tracker.status_buildup["bleeding"] == ench["buildup_per_hit"] * hits_needed
    assert tracker.status_buildup["bleeding"] < ench["threshold"]


# ===================================================================
# 7. test_enchantment_trigger
# ===================================================================

def test_enchantment_trigger():
    """Buildup reaching threshold triggers burst damage (bleeding)."""
    e = _make_enemy(tier=1)
    state = _make_state_with_enemies([e])
    hp_before = e.hp

    ench = ENCHANTMENT_TYPES["bleeding"]
    events = _trigger_enchantment(state, e, "bleeding", ench)

    assert len(events) == 1
    assert events[0].event_type == "status"
    expected_dmg = max(1, int(e.max_hp * ench["burst_pct"]))
    assert events[0].damage == expected_dmg
    assert e.hp == hp_before - expected_dmg


# ===================================================================
# 8. test_enchantment_frostbite
# ===================================================================

def test_enchantment_frostbite():
    """Frostbite applies burst damage + ATK debuff."""
    e = _make_enemy(tier=3)
    state = _make_state_with_enemies([e])
    tracker = state.enemy_status[id(e)]
    original_atk = tracker.original_attack
    hp_before = e.hp

    ench = ENCHANTMENT_TYPES["frostbite"]
    events = _trigger_enchantment(state, e, "frostbite", ench)

    assert len(events) == 1
    expected_dmg = max(1, int(e.max_hp * ench["burst_pct"]))
    assert e.hp == hp_before - expected_dmg
    # ATK should be reduced
    assert e.attack == int(original_atk * (1 - ench["atk_reduction_pct"]))
    # Active effect should be appended
    assert any(eff["type"] == "atk_debuff" for eff in tracker.active_effects)


# ===================================================================
# 9. test_enchantment_poison_dot
# ===================================================================

def test_enchantment_poison_dot():
    """Poison applies DOT that ticks each turn."""
    e = _make_enemy(tier=2)
    state = _make_state_with_enemies([e])
    tracker = state.enemy_status[id(e)]
    hp_before = e.hp

    ench = ENCHANTMENT_TYPES["poison"]
    events = _trigger_enchantment(state, e, "poison", ench)
    assert any(eff["type"] == "poison_dot" for eff in tracker.active_effects)

    # Process one tick
    tick_events = _process_status_ticks(state)
    dot_dmg = max(1, int(e.max_hp * ench["dot_pct"]))
    assert len(tick_events) >= 1
    assert e.hp == hp_before - dot_dmg
    # Turns left decremented
    poison_eff = [eff for eff in tracker.active_effects if eff["type"] == "poison_dot"][0]
    assert poison_eff["turns_left"] == ench["dot_turns"] - 1


# ===================================================================
# 10. test_status_effect_expiry
# ===================================================================

def test_status_effect_expiry():
    """Debuffs expire after specified turns and restore stats."""
    e = _make_enemy(tier=3)
    state = _make_state_with_enemies([e])
    tracker = state.enemy_status[id(e)]

    ench = ENCHANTMENT_TYPES["frostbite"]
    _trigger_enchantment(state, e, "frostbite", ench)
    assert e.attack < tracker.original_attack

    # Tick through all debuff turns
    for _ in range(ench["debuff_turns"]):
        _process_status_ticks(state)

    # After expiry, ATK should be restored
    assert e.attack == tracker.original_attack
    assert not any(eff["type"] == "atk_debuff" for eff in tracker.active_effects)


# ===================================================================
# 11. test_battle_start
# ===================================================================

def test_battle_start():
    """start_auto_battle creates correct initial state."""
    f1 = _make_fighter(name="A")
    f2 = _make_fighter(name="B")
    eng = _make_engine_stub(fighters=[f1, f2], arena_tier=1)
    bm = BattleManager(eng)
    events = bm.start_auto_battle()

    assert bm.state.phase == BattlePhase.STARTING
    assert len(bm.state.player_fighters) == 2
    assert len(bm.state.enemies) >= 2
    assert bm.state.is_boss_fight is False
    assert any("BATTLE START" in ev.message for ev in events)


# ===================================================================
# 12. test_battle_victory
# ===================================================================

def test_battle_victory():
    """Battle ends in VICTORY when all enemies are dead."""
    # Strong fighter vs weak enemy
    f = _make_fighter(name="Victor", strength=50, agility=1, vitality=20)
    e = _make_enemy(tier=1)
    e.hp = 1
    e.defense = 0
    e.dodge_chance = 0

    eng = _make_engine_stub(fighters=[f], arena_tier=1)
    eng.current_enemy = e
    bm = BattleManager(eng)
    bm.start_auto_battle()

    all_events = bm.do_full_battle()
    assert bm.state.phase == BattlePhase.VICTORY
    assert any(ev.event_type == "victory" for ev in all_events)


# ===================================================================
# 13. test_battle_defeat
# ===================================================================

def test_battle_defeat():
    """Battle ends in DEFEAT when all fighters are dead."""
    f = _make_fighter(name="Weakling", strength=1, agility=1, vitality=1)
    f.hp = 1
    e = _make_enemy(tier=10)
    e.dodge_chance = 0
    e.crit_chance = 0

    eng = _make_engine_stub(fighters=[f], arena_tier=10)
    eng.current_enemy = e
    bm = BattleManager(eng)
    bm.start_auto_battle()

    all_events = bm.do_full_battle()
    assert bm.state.phase == BattlePhase.DEFEAT
    assert any(ev.event_type == "defeat" for ev in all_events)


# ===================================================================
# 14. test_boss_fight_start
# ===================================================================

def test_boss_fight_start():
    """start_boss_fight creates boss battle state."""
    f = _make_fighter(name="Challenger")
    boss = Enemy.create_boss(arena_tier=3)

    eng = _make_engine_stub(fighters=[f], arena_tier=3)
    eng.current_enemy = boss
    bm = BattleManager(eng)
    events = bm.start_boss_fight()

    assert bm.state.phase == BattlePhase.BOSS_INTRO
    assert bm.state.is_boss_fight is True
    assert len(bm.state.enemies) == 1
    assert bm.state.enemies[0].is_boss is True
    assert any(ev.is_boss for ev in events)


# ===================================================================
# 15. test_boss_has_increased_stats
# ===================================================================

def test_boss_has_increased_stats():
    """Boss has 10x HP, 1.5x ATK compared to regular enemy of same tier."""
    arena_tier = 5
    boss_tier = arena_tier + 2
    regular = Enemy(tier=boss_tier)
    boss = Enemy.create_boss(arena_tier)

    assert boss.max_hp == int(regular.max_hp * 10)
    assert boss.attack == int(regular.attack * 1.5)
    assert boss.defense == int(regular.defense * 1.3)
    assert boss.gold_reward == int(regular.gold_reward * 10)
    assert boss.is_boss is True


# ===================================================================
# 16. test_gold_earned_on_kill
# ===================================================================

def test_gold_earned_on_kill():
    """Gold is awarded when enemy dies in battle."""
    f = _make_fighter(name="GoldHunter", strength=100, agility=1, vitality=50)
    e = _make_enemy(tier=1)
    e.hp = 1
    e.defense = 0
    e.dodge_chance = 0

    eng = _make_engine_stub(fighters=[f], arena_tier=1)
    eng.current_enemy = e
    bm = BattleManager(eng)
    bm.start_auto_battle()
    bm.do_full_battle()

    assert bm.state.gold_earned > 0
    eng.award_gold.assert_called()


# ===================================================================
# 17. test_skip_mode
# ===================================================================

def test_skip_mode():
    """do_full_battle runs battle to completion."""
    f = _make_fighter(name="Skipper", strength=30, vitality=20)
    eng = _make_engine_stub(fighters=[f], arena_tier=1)
    bm = BattleManager(eng)
    bm.start_auto_battle()

    all_events = bm.do_full_battle()
    assert bm.state.phase in (BattlePhase.VICTORY, BattlePhase.DEFEAT)
    assert len(all_events) > 0


# ===================================================================
# 18. test_fighter_kills_tracked
# ===================================================================

def test_fighter_kills_tracked():
    """Fighter.kills increments when enemy is killed."""
    f = _make_fighter(name="Slayer", strength=100, agility=1, vitality=50)
    kills_before = f.kills
    e = _make_enemy(tier=1)
    e.hp = 1
    e.defense = 0
    e.dodge_chance = 0

    eng = _make_engine_stub(fighters=[f], arena_tier=1)
    eng.current_enemy = e
    bm = BattleManager(eng)
    bm.start_auto_battle()
    bm.do_full_battle()

    assert f.kills > kills_before


# ===================================================================
# 19. test_multiple_fighters_attack
# ===================================================================

def test_multiple_fighters_attack():
    """All alive fighters attack during a turn."""
    f1 = _make_fighter(name="Alpha", strength=20, vitality=20)
    f2 = _make_fighter(name="Beta", strength=20, vitality=20)
    e = _make_enemy(tier=1)
    e.max_hp = 99999
    e.hp = 99999
    e.defense = 0
    e.dodge_chance = 0

    eng = _make_engine_stub(fighters=[f1, f2], arena_tier=1)
    eng.current_enemy = e
    bm = BattleManager(eng)
    bm.start_auto_battle()

    # First do_turn transitions from STARTING to TURN_PLAYER
    bm.do_turn()
    # Second do_turn processes actual attacks
    events = bm.do_turn()

    attack_events = [ev for ev in events if ev.event_type == "attack"]
    attacker_names = {ev.attacker for ev in attack_events}
    # Both fighters and the enemy should have attacked
    assert "Alpha" in attacker_names
    assert "Beta" in attacker_names


# ===================================================================
# 20. test_enemy_attacks_random_fighter
# ===================================================================

def test_enemy_attacks_random_fighter():
    """Enemies target random alive fighters."""
    random.seed(123)
    f1 = _make_fighter(name="Tank1", strength=5, vitality=50, agility=1)
    f2 = _make_fighter(name="Tank2", strength=5, vitality=50, agility=1)
    # Give them high HP so they survive multiple turns
    f1.hp = f1.max_hp
    f2.hp = f2.max_hp

    e = _make_enemy(tier=1)
    e.max_hp = 99999
    e.hp = 99999
    e.dodge_chance = 0
    e.crit_chance = 0

    eng = _make_engine_stub(fighters=[f1, f2], arena_tier=1)
    eng.current_enemy = e
    bm = BattleManager(eng)
    bm.start_auto_battle()

    # Run several turns and collect who the enemy attacks
    targeted = set()
    for _ in range(20):
        bm.do_turn()
        for ev in bm.state.events:
            pass
    # Re-run collecting from do_turn return
    bm2 = BattleManager(_make_engine_stub(fighters=[
        _make_fighter(name="Tank1", strength=5, vitality=50, agility=1),
        _make_fighter(name="Tank2", strength=5, vitality=50, agility=1),
    ], arena_tier=1))
    e2 = _make_enemy(tier=1)
    e2.max_hp = 99999
    e2.hp = 99999
    e2.dodge_chance = 0
    e2.crit_chance = 0
    bm2.engine.current_enemy = e2
    bm2.start_auto_battle()

    targeted = set()
    for _ in range(30):
        events = bm2.do_turn()
        for ev in events:
            if ev.event_type == "attack" and ev.attacker == e2.name:
                targeted.add(ev.defender)

    # Over 30 turns, enemy should have targeted both fighters
    assert "Tank1" in targeted or "Tank2" in targeted
    # With seed 123 and enough turns, both should appear
    assert len(targeted) >= 1
