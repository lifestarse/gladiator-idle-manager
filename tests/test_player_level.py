# Build: 1
"""Player account level + feature unlock gates.

Three levels of "level" exist in this game and they are easy to confuse:
Fighter.level (bought with gold, per fighter), arena_tier (advanced by
beating a boss) and player_level (account-wide, gates features). This
module guards the third one: the XP curve, the level-up rollover, the
unlock table and persistence.
"""
import json

import pytest

from game.constants import (
    FEATURE_UNLOCKS, PLAYER_MAX_LEVEL, PLAYER_XP_BASE, PLAYER_XP_EXPO,
    PLAYER_XP_PER_ACHIEVEMENT, PLAYER_XP_PER_ARENA_WIN,
    PLAYER_XP_PER_BOSS_KILL, PLAYER_XP_PER_EXPEDITION, PLAYER_XP_PER_TIER,
)


# --- curve -----------------------------------------------------------------

def test_new_account_starts_at_level_one(engine):
    assert engine.player_level == 1
    assert engine.player_xp == 0


def test_xp_curve_is_ascending(engine):
    """Each level must cost more than the last, or the ramp is meaningless."""
    costs = [engine.xp_for_level(lv) for lv in range(1, PLAYER_MAX_LEVEL)]
    assert costs[0] == PLAYER_XP_BASE
    assert costs == sorted(costs)
    assert len(set(costs)) > 1, "a flat curve is not a curve"


def test_xp_for_level_is_zero_at_cap(engine):
    assert engine.xp_for_level(PLAYER_MAX_LEVEL) == 0
    assert engine.xp_for_level(PLAYER_MAX_LEVEL + 5) == 0


# --- awarding --------------------------------------------------------------

def test_award_below_threshold_does_not_level(engine):
    gained = engine.award_player_xp(PLAYER_XP_BASE - 1)
    assert gained == 0
    assert engine.player_level == 1
    assert engine.player_xp == PLAYER_XP_BASE - 1


def test_award_exactly_threshold_levels_once(engine):
    gained = engine.award_player_xp(PLAYER_XP_BASE)
    assert gained == 1
    assert engine.player_level == 2
    assert engine.player_xp == 0


def test_overflow_carries_into_the_new_level(engine):
    engine.award_player_xp(PLAYER_XP_BASE + 30)
    assert engine.player_level == 2
    assert engine.player_xp == 30, "leftover XP must not be discarded"


def test_one_award_can_cross_several_levels(engine):
    """A boss kill on a fresh account may legitimately cross two levels."""
    huge = sum(engine.xp_for_level(lv) for lv in (1, 2, 3))
    gained = engine.award_player_xp(huge)
    assert gained == 3
    assert engine.player_level == 4
    assert engine.player_xp == 0


def test_award_is_queued_for_the_ui(engine):
    engine.award_player_xp(PLAYER_XP_BASE)
    assert engine.take_pending_level_ups() == [2]
    assert engine.take_pending_level_ups() == [], "drain must be idempotent"


@pytest.mark.parametrize("bad", [0, -1, -9999])
def test_non_positive_award_is_a_noop(engine, bad):
    engine.award_player_xp(bad)
    assert engine.player_level == 1
    assert engine.player_xp == 0


def test_level_caps_and_stops_accumulating(engine):
    engine.player_level = PLAYER_MAX_LEVEL
    engine.player_xp = 0
    assert engine.award_player_xp(10_000) == 0
    assert engine.player_level == PLAYER_MAX_LEVEL
    assert engine.player_xp == 0, (
        "XP past the cap must not accumulate into a meaningless number"
    )


def test_level_pct_and_to_next_are_consistent(engine):
    need = engine.xp_for_level(1)
    engine.award_player_xp(need // 2)
    assert 0.0 < engine.player_level_pct < 1.0
    assert engine.player_xp_to_next == need - (need // 2)


def test_capped_account_reads_as_full(engine):
    engine.player_level = PLAYER_MAX_LEVEL
    assert engine.player_level_pct == 1.0
    assert engine.player_xp_to_next == 0


# --- unlock table ----------------------------------------------------------

def test_ungated_feature_is_always_unlocked(engine):
    assert engine.is_unlocked("arena") is True
    assert engine.unlock_level_for("arena") == 0


@pytest.mark.parametrize("feature,level", sorted(FEATURE_UNLOCKS.items()))
def test_gated_feature_locks_below_and_unlocks_at_its_level(engine,
                                                            feature, level):
    engine.player_level = level - 1
    assert engine.is_unlocked(feature) is False
    engine.player_level = level
    assert engine.is_unlocked(feature) is True


def test_scripts_are_the_last_unlock(engine):
    """Product decision: scripts gate last. Guard it so a future table edit
    that quietly promotes them ahead of something else gets caught."""
    assert FEATURE_UNLOCKS["scripts"] == max(FEATURE_UNLOCKS.values())


def test_unlock_levels_are_within_the_cap():
    for feature, level in FEATURE_UNLOCKS.items():
        assert 1 <= level <= PLAYER_MAX_LEVEL, (
            f"{feature} unlocks at {level}, unreachable with "
            f"PLAYER_MAX_LEVEL={PLAYER_MAX_LEVEL}"
        )


def test_next_unlock_walks_the_table_in_order(engine):
    engine.player_level = 1
    name, lvl = engine.next_unlock()
    assert lvl == min(FEATURE_UNLOCKS.values())
    assert FEATURE_UNLOCKS[name] == lvl

    engine.player_level = PLAYER_MAX_LEVEL
    assert engine.next_unlock() is None, "nothing left to unlock at cap"


# --- award plumbing --------------------------------------------------------

def test_arena_victory_awards_tier_scaled_xp(engine):
    """Tier scaling is the reason grinding tier 1 can't reach late unlocks."""
    class _R:
        outcome = "victory"
        is_boss = False
        enemies_killed = 1
        gold_earned = 0
        turn_number = 1
        survivors = []
        player_fighters = []
        enemies = []

    engine.arena_tier = 5
    before = engine.player_xp
    engine._post_battle_check(_R())
    expected = PLAYER_XP_PER_ARENA_WIN + PLAYER_XP_PER_TIER * 5
    assert engine.player_xp - before == expected


def test_boss_victory_awards_the_boss_bonus_on_top(engine):
    class _R:
        outcome = "victory"
        is_boss = True
        enemies_killed = 1
        gold_earned = 0
        turn_number = 1
        survivors = []
        player_fighters = []
        enemies = []

    engine.arena_tier = 1
    engine._post_battle_check(_R())
    flat = PLAYER_XP_PER_ARENA_WIN + PLAYER_XP_PER_TIER
    assert engine.player_xp == flat + PLAYER_XP_PER_BOSS_KILL


def test_xp_sources_are_all_wired(engine):
    """All four sources the design calls for actually reach award_player_xp."""
    seen = []
    engine.award_player_xp = lambda amount: seen.append(amount)

    class _R:
        outcome = "victory"
        is_boss = True
        enemies_killed = 1
        gold_earned = 0
        turn_number = 1
        survivors = []
        player_fighters = []
        enemies = []

    engine._post_battle_check(_R())
    assert seen, "arena/boss victory must award XP"
    assert PLAYER_XP_PER_EXPEDITION > 0 and PLAYER_XP_PER_ACHIEVEMENT > 0


# --- persistence -----------------------------------------------------------

def test_level_and_xp_roundtrip(engine, tmp_save_path):
    from game.engine import GameEngine
    engine.player_level = 7
    engine.player_xp = 42
    engine.save()

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.player_level == 7
    assert eng2.player_xp == 42


def test_pre_level_saves_start_at_one(engine, tmp_save_path):
    """"Everyone from scratch": saves written before the level system have
    no key and come back at level 1 with features gated."""
    from game.engine import GameEngine
    engine.save()
    with open(tmp_save_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("player_level", None)
    data.pop("player_xp", None)
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.player_level == 1
    assert eng2.player_xp == 0
    assert eng2.is_unlocked("scripts") is False


@pytest.mark.parametrize("bad,expect", [
    (0, 1), (-5, 1), (PLAYER_MAX_LEVEL + 99, PLAYER_MAX_LEVEL),
    ("nine", 1), (None, 1),
])
def test_tampered_level_is_clamped(engine, tmp_save_path, bad, expect):
    from game.engine import GameEngine
    engine.save()
    with open(tmp_save_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["player_level"] = bad
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.player_level == expect


def test_account_level_survives_the_roguelike_reset(engine):
    """The run dies, the account does not — otherwise a wipe would relock
    scripts on a player who already earned them."""
    engine.player_level = 12
    engine.player_xp = 33
    engine.roguelike_reset()
    assert engine.player_level == 12
    assert engine.player_xp == 33
    assert engine.arena_tier == 1, "the run itself must still reset"
