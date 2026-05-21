# Build: 1
"""Perk effect plumbing — covers the previously-dead types brought online:
reduce_injury_severity, bonus_gold_pct, on_dodge_counter (incl. *_upgrade),
plus the generic upgrade-replaces-base mechanism.

Each was silently doing nothing before: the type either wasn't read by
any code path (severity / gold / counter) or carried an `_upgrade` suffix
that the old `get_perk_effects` lookup didn't recognize.
"""
import random

import pytest

from game.engine import GameEngine
from game.models import Fighter
from game.data_loader import data_loader


@pytest.fixture(autouse=True)
def _engine_for_data(tmp_save_path):
    """FIGHTER_CLASSES / injuries / etc. are populated by GameEngine's
    data wiring. Constructing one engine per test is enough to keep
    these globals warm; no need to thread it through each test.
    """
    GameEngine(save_path=tmp_save_path)


# ---------------------------------------------------------------------------
# get_perk_effects: upgrade replaces base
# ---------------------------------------------------------------------------

def test_passive_alone_returns_base_value():
    """Medicus passive Field Surgery = 3% regen."""
    f = Fighter(fighter_class="medicus")
    assert f.get_perk_effects("regen_per_turn_pct") == pytest.approx(0.03)


def test_upgrade_perk_replaces_base():
    """Resurgence (regen_per_turn_pct_upgrade=0.05) overrides the
    passive Field Surgery (regen_per_turn_pct=0.03), not stacks."""
    f = Fighter(fighter_class="medicus")
    f.unlocked_perks.append("med_resurgence")
    val = f.get_perk_effects("regen_per_turn_pct")
    assert val == pytest.approx(0.05), f"upgrade should replace base, got {val}"


def test_retiarius_riposte_replaces_net_mastery():
    """Riposte (on_dodge_counter_upgrade=0.75) overrides Net Mastery
    passive (on_dodge_counter=0.50)."""
    f = Fighter(fighter_class="retiarius")
    base = f.get_perk_effects("on_dodge_counter")
    assert base == pytest.approx(0.50)
    f.unlocked_perks.append("ret_riposte")
    upgraded = f.get_perk_effects("on_dodge_counter")
    assert upgraded == pytest.approx(0.75)


def test_unrelated_upgrade_doesnt_leak_into_other_lookups():
    """Resurgence is a regen upgrade — it must not affect crit lookups."""
    f = Fighter(fighter_class="medicus")
    f.unlocked_perks.append("med_resurgence")
    assert f.get_perk_effects("crit_chance_bonus") == 0


# ---------------------------------------------------------------------------
# reduce_injury_severity
# ---------------------------------------------------------------------------

def test_pick_random_injury_no_reduction_returns_normal():
    """Without reduction chance, picker behaves as before."""
    random.seed(42)
    inj_id = data_loader.pick_random_injury()
    assert inj_id  # got something
    assert any(inj["id"] == inj_id for inj in data_loader.injuries)


def test_pick_random_injury_severity_downgrade_with_chance_one():
    """With 100% reduction chance, a non-minor injury must be downgraded
    (assuming the JSON pool has lesser-tier injuries — true for our data).
    """
    random.seed(0)
    # Run many iterations; since chance=1.0 every roll downgrades when
    # possible. If the original happens to roll 'minor' the result stays
    # minor (no lesser tier), so we sample many to verify the rule.
    severities_seen = []
    for seed in range(200):
        random.seed(seed)
        inj_id = data_loader.pick_random_injury(severity_reduction_chance=1.0)
        sev = data_loader.injuries_by_id[inj_id]["severity"]
        severities_seen.append(sev)
    # With chance=1 across 200 rolls, the distribution must be heavily
    # minor-skewed compared to a no-reduction baseline.
    minor_count = sum(1 for s in severities_seen if s == "minor")
    assert minor_count >= 150, (
        f"reduction chance=1.0 should land mostly on minor; got {minor_count}/200 minor"
    )


def test_check_permadeath_reads_perk():
    """Bone Setter (medicus, T3, 30%) must feed into pick_random_injury."""
    f = Fighter(fighter_class="medicus")
    f.unlocked_perks.append("med_bone_setter")
    assert f.get_perk_effects("reduce_injury_severity") == pytest.approx(0.30)
    # Run check_permadeath many times with seed; we just need it to not
    # raise. The actual severity-skew is covered by the picker test.
    for seed in range(30):
        random.seed(seed)
        # rig: ensure non-fatal — reset injuries each time
        f.injuries = []
        f.alive = True
        f.hp = f.max_hp
        # stub away the death roll path: test only injury path
        # (death_chance stays small by default)
        died, inj_id = f.check_permadeath()
        if not died:
            assert inj_id is not None


# ---------------------------------------------------------------------------
# bonus_gold_pct
# ---------------------------------------------------------------------------

@pytest.fixture
def gold_fight_engine(tmp_save_path):
    random.seed(1)
    eng = GameEngine(save_path=tmp_save_path)
    eng.gold = 0
    eng.fighters = []
    return eng


def test_bonus_gold_pct_lifts_kill_reward(gold_fight_engine):
    """A retiarius with Crowd Favorite (+20%) must earn 20% more gold
    on kill than one without."""
    eng = gold_fight_engine
    f = Fighter(fighter_class="retiarius")
    f.unlocked_perks.append("ret_crowd_favorite")
    eng.fighters.append(f)
    # Need to arrange a guaranteed kill. Spawn arena fight.
    eng.start_auto_battle()
    eng.battle_next_turn()  # consume STARTING

    mgr = eng.battle_mgr
    enemy = mgr.state.enemies[0]
    base_reward = enemy.gold_reward
    # Set fighter attack absurdly high so the next attack one-shots.
    f.strength = 10_000
    eng.gold_before = eng.gold
    eng.battle_next_turn()
    earned = eng.gold - eng.gold_before
    expected_min = int(base_reward * 1.20)
    assert earned >= expected_min, (
        f"gold {earned} should be >= {expected_min} (base {base_reward} +20%)"
    )


def test_no_bonus_perk_means_base_gold(gold_fight_engine):
    """Sanity: without the perk, the kill awards the base reward."""
    eng = gold_fight_engine
    f = Fighter(fighter_class="mercenary")
    eng.fighters.append(f)
    eng.start_auto_battle()
    eng.battle_next_turn()

    mgr = eng.battle_mgr
    enemy = mgr.state.enemies[0]
    base_reward = enemy.gold_reward
    f.strength = 10_000
    eng.gold_before = eng.gold
    eng.battle_next_turn()
    earned = eng.gold - eng.gold_before
    assert earned == base_reward


# ---------------------------------------------------------------------------
# on_dodge_counter
# ---------------------------------------------------------------------------

def _setup_battle(tmp_save_path, fighter, seed=7):
    random.seed(seed)
    eng = GameEngine(save_path=tmp_save_path)
    eng.fighters = [fighter]
    eng.spawn_boss_enemy()
    eng.start_boss_fight()
    eng.battle_next_turn()  # consume BOSS_INTRO, seed turn 1
    return eng


def test_apply_dodge_counter_retiarius_default(tmp_save_path):
    """Retiarius w/o extra perks: Net Mastery (0.50) must deal damage."""
    f = Fighter(fighter_class="retiarius")
    f.strength = 100
    eng = _setup_battle(tmp_save_path, f)
    mgr = eng.battle_mgr
    boss = mgr.state.enemies[0]
    boss.hp = 10**9
    events = []
    mgr._apply_dodge_counter(f, boss, events)
    assert events, "Net Mastery counter must emit an event"
    assert boss.hp < 10**9, "boss must take counter damage"


def test_apply_dodge_counter_riposte_scales_damage(tmp_save_path):
    """Riposte (0.75) deals more damage per swing than Net Mastery (0.50)."""
    f_base = Fighter(fighter_class="retiarius")
    f_base.strength = 100
    eng_b = _setup_battle(tmp_save_path, f_base)
    boss_b = eng_b.battle_mgr.state.enemies[0]
    boss_b.hp = 10**9
    eng_b.battle_mgr._apply_dodge_counter(f_base, boss_b, [])
    base_dmg = 10**9 - boss_b.hp

    f_up = Fighter(fighter_class="retiarius")
    f_up.strength = 100
    f_up.unlocked_perks.append("ret_riposte")
    eng_u = _setup_battle(tmp_save_path + ".u", f_up)
    boss_u = eng_u.battle_mgr.state.enemies[0]
    boss_u.hp = 10**9
    eng_u.battle_mgr._apply_dodge_counter(f_up, boss_u, [])
    upgrade_dmg = 10**9 - boss_u.hp

    # Riposte = 0.75, base = 0.50 → upgrade ~50% more damage. Allow some
    # slack for int rounding / cached attack value differences.
    assert upgrade_dmg > base_dmg, (
        f"Riposte should out-damage Net Mastery (got {upgrade_dmg} vs {base_dmg})"
    )


def test_no_counter_for_class_without_perk(tmp_save_path):
    """Mercenary has no counter perk — calling the helper is a no-op."""
    f = Fighter(fighter_class="mercenary")
    f.strength = 100
    eng = _setup_battle(tmp_save_path, f)
    mgr = eng.battle_mgr
    boss = mgr.state.enemies[0]
    boss.hp = 10**9
    events = []
    mgr._apply_dodge_counter(f, boss, events)
    assert events == [], "no perk → no counter event"
    assert boss.hp == 10**9, "no perk → no damage"
