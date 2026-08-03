# Build: 2
"""HP-healing seam on the engine.

get_single_heal_cost / heal_one_hp are what the arena screen calls instead
of re-deriving the cost formula in the UI layer; these tests pin them to
the same tier-scaled curve get_hp_heal_cost / heal_all_hp use, so the two
entry points cannot drift apart again.
"""
import math

import pytest

from game.constants import HP_HEAL_DIVISOR, HP_HEAL_TIER_MULT
from game.models import Fighter


def _damaged_fighter(engine, missing):
    """Add one roster fighter, knocked down by `missing` HP (still standing)."""
    f = Fighter(fighter_class="mercenary")
    assert f.max_hp > missing, "test fixture must leave the fighter alive"
    engine.fighters.append(f)
    f.hp = f.max_hp - missing
    return f


def test_single_heal_cost_matches_the_all_fighters_formula(engine):
    f = _damaged_fighter(engine, 50)
    tier_mult = HP_HEAL_TIER_MULT ** (engine.arena_tier - 1)
    expected = math.ceil(50 / HP_HEAL_DIVISOR * tier_mult)
    assert engine.get_single_heal_cost(f) == expected
    assert engine.get_single_heal_cost(f) == engine.get_hp_heal_cost([f])


def test_single_heal_cost_scales_with_arena_tier(engine):
    f = _damaged_fighter(engine, 60)
    tier_one = engine.get_single_heal_cost(f)
    engine.arena_tier = 5
    tier_five = engine.get_single_heal_cost(f)
    assert tier_five > tier_one
    assert tier_five == math.ceil(60 / HP_HEAL_DIVISOR * HP_HEAL_TIER_MULT ** 4)


def test_single_heal_cost_is_zero_when_nothing_to_heal(engine):
    f = _damaged_fighter(engine, 0)
    assert engine.get_single_heal_cost(f) == 0
    f.hp = 0
    assert engine.get_single_heal_cost(f) == 0


def test_heal_one_hp_full_heal_spends_exactly_the_quoted_cost(engine):
    f = _damaged_fighter(engine, 40)
    cost = engine.get_single_heal_cost(f)
    engine.gold = cost + 500
    healed, spent = engine.heal_one_hp(f)
    assert (healed, spent) == (1, cost)
    assert f.hp == f.max_hp
    assert engine.gold == 500


def test_heal_one_hp_partial_heal_spends_all_gold(engine):
    f = _damaged_fighter(engine, 60)
    cost = engine.get_single_heal_cost(f)
    engine.gold = cost // 2
    before = f.hp
    healed, spent = engine.heal_one_hp(f)
    assert healed == 1
    assert spent == cost // 2
    assert engine.gold == 0
    assert before < f.hp < f.max_hp


def test_heal_one_hp_reports_nothing_healed_without_gold(engine):
    f = _damaged_fighter(engine, 30)
    engine.gold = 0
    before = f.hp
    assert engine.heal_one_hp(f) == (0, 0)
    assert f.hp == before


def test_heal_one_hp_leaves_other_fighters_untouched(engine):
    first = _damaged_fighter(engine, 30)
    second = _damaged_fighter(engine, 30)
    engine.gold = 10000
    engine.heal_one_hp(first)
    assert first.hp == first.max_hp
    assert second.hp == second.max_hp - 30


def test_ui_constant_for_heal_cost_is_gone():
    """The arena screen used to re-derive the cost from its own constant."""
    import game.constants as constants
    assert not hasattr(constants, "HEAL_GOLD_PER_HP")
