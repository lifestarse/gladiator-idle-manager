# Build: 1
"""Tests for enemy scaling, economy growth, and DifficultyScaler (~10 tests)."""
import pytest

from game.models import DifficultyScaler, Enemy


# ---- 1. Enemy stats grow monotonically T1-T100 ----

def test_enemy_stats_monotonic():
    prev_atk, prev_def, prev_hp = 0, 0, 0
    for tier in range(1, 101):
        atk, dfn, hp = DifficultyScaler.enemy_stats(tier)
        assert atk >= prev_atk, f"ATK decreased at T{tier}"
        assert dfn >= prev_def, f"DEF decreased at T{tier}"
        assert hp >= prev_hp, f"HP decreased at T{tier}"
        prev_atk, prev_def, prev_hp = atk, dfn, hp


# ---- 2. No stat overflows at T100 ----

def test_enemy_no_overflow():
    atk, dfn, hp = DifficultyScaler.enemy_stats(100)
    assert atk < 1e18, f"ATK overflow at T100: {atk}"
    assert dfn < 1e18, f"DEF overflow at T100: {dfn}"
    assert hp < 1e18, f"HP overflow at T100: {hp}"
    assert atk > 0
    assert dfn > 0
    assert hp > 0


# ---- 3. Boss stronger than normal enemy at same tier ----

def test_boss_stronger_than_normal():
    for tier in [1, 5, 10, 15]:
        normal = Enemy(tier=tier)
        boss = Enemy.create_boss(tier)
        assert boss.max_hp > normal.max_hp, f"Boss HP not greater at T{tier}"
        assert boss.attack > normal.attack, f"Boss ATK not greater at T{tier}"
        assert boss.gold_reward > normal.gold_reward, f"Boss gold not greater at T{tier}"


# ---- 4. T100 enemy has reasonable stats (large but not infinite) ----

def test_t100_enemy_has_reasonable_stats():
    atk, dfn, hp = DifficultyScaler.enemy_stats(100)
    # Stats should be large but finite and reasonable
    assert 1_000 < atk < 1_000_000_000
    assert 1_000 < dfn < 1_000_000_000
    assert 1_000 < hp < 1_000_000_000


# ---- 5. Enemy reward grows with tier ----

def test_enemy_reward_grows():
    prev = 0
    for tier in range(1, 101):
        reward = DifficultyScaler.enemy_reward(tier)
        assert reward >= prev, f"Reward decreased at T{tier}"
        prev = reward


# ---- 6. Heal cost grows with tier ----

def test_heal_cost_grows():
    prev = 0
    for tier in range(1, 51):
        cost = DifficultyScaler.heal_cost(tier)
        assert cost >= prev, f"Heal cost decreased at T{tier}"
        prev = cost


# ---- 7. Hire cost grows with fighter count ----

def test_hire_cost_grows():
    prev = 0
    for count in range(10):
        cost = DifficultyScaler.hire_cost(count)
        assert cost >= prev, f"Hire cost decreased at count={count}"
        prev = cost


# ---- 8. Upgrade cost grows with level ----

def test_upgrade_cost_grows():
    prev = 0
    for level in range(1, 30):
        cost = DifficultyScaler.upgrade_cost(level)
        assert cost >= prev, f"Upgrade cost decreased at level={level}"
        prev = cost


# ---- 9. Tier-band scaling applies correctly ----

def test_tier_band_scaling():
    # Early tiers should have steeper cost growth than late tiers
    heal_t5 = DifficultyScaler.heal_cost(5)
    heal_t4 = DifficultyScaler.heal_cost(4)
    heal_t55 = DifficultyScaler.heal_cost(55)
    heal_t54 = DifficultyScaler.heal_cost(54)
    # Early growth ratio should be higher than late growth ratio
    early_ratio = heal_t5 / max(1, heal_t4)
    late_ratio = heal_t55 / max(1, heal_t54)
    assert early_ratio > late_ratio, "Early tier growth should be steeper than late tier"


# ---- 10. Surgeon cost grows with uses ----

def test_surgeon_cost_grows():
    prev = 0
    for uses in range(20):
        cost = DifficultyScaler.surgeon_cost(uses)
        assert cost >= prev, f"Surgeon cost decreased at uses={uses}"
        prev = cost
