# Build: 2
"""The DEF -> damage-reduction curve has three consumers.

game.models.defense_mitigation is the definition; CombatUnit.take_damage
and fmt_def go through it, while game/battle/_resolve.py inlines the same
expression on purpose (hot path). These tests are what keeps the inline
copy and the displayed percentage honest if the curve is ever reshaped.

Also home to the guards on where enemy DEF *comes from*:
Enemy.from_template must derive it from the vit keys of the role/bias
multipliers (same pipeline as fighters — CLAUDE.md), not the agi keys.
"""
import re

import pytest

from game.constants import (
    DEFENSE_DIVISOR, ROLE_MULT, ROLE_STAT_MULT, STAT_BIAS_MULT,
)
from game.models import DifficultyScaler, Enemy, defense_mitigation, fmt_def
from game.models._combat import CombatUnit


_DEFENSES = [0, 1, 7, 25, 100, 250, 370, 1000, 12345]
_RAW = 100000


class _Target(CombatUnit):
    """Minimal CombatUnit: defense + hp, dodge disabled."""

    def __init__(self, defense):
        self.defense = defense
        self.dodge_chance = 0.0
        self.hp = _RAW * 10
        self.name = "Target"


class _FixedRandom:
    """No crit, no dodge, no damage variance."""

    def random(self):
        return 0.99

    def uniform(self, low, high):
        return 1.0

    def choice(self, seq):
        return seq[0]


def _displayed_pct(defense):
    match = re.search(r"\((\d+)%\)", fmt_def(defense))
    assert match, f"fmt_def({defense}) lost its percentage: {fmt_def(defense)}"
    return int(match.group(1))


@pytest.mark.parametrize("defense", _DEFENSES)
def test_fmt_def_percentage_is_the_reduction_take_damage_applies(defense):
    target = _Target(defense)
    dealt = target.take_damage(_RAW)
    applied = defense_mitigation(defense)
    assert dealt == max(1, int(_RAW * (1 - applied)))
    assert _displayed_pct(defense) == int(applied * 100)


@pytest.mark.parametrize("defense", _DEFENSES)
def test_battle_resolve_inline_copy_matches_take_damage(defense, monkeypatch):
    """_resolve_attack duplicates the formula for the cached-stats path."""
    from game.battle import _resolve

    monkeypatch.setattr(_resolve, "random", _FixedRandom())
    attacker = _Target(0)
    attacker.attack = _RAW
    attacker.crit_chance = 0.0
    attacker.crit_mult = 1.0
    defender = _Target(defense)
    _ev, actual, is_crit = _resolve._resolve_attack(
        attacker, defender,
        def_cache={'dodge_chance': 0.0, 'defense': defense},
    )
    assert is_crit is False
    assert actual == _Target(defense).take_damage(_RAW)


def test_mitigation_is_bounded_and_monotonic():
    values = [defense_mitigation(d) for d in _DEFENSES]
    assert all(0.0 <= v < 1.0 for v in values)
    assert values == sorted(values)
    assert defense_mitigation(DEFENSE_DIVISOR) == pytest.approx(0.5)
    assert defense_mitigation(0) == 0.0
    assert defense_mitigation(-50) == 0.0


# --- Enemy DEF derivation (role/bias templates) ---------------------------
#
# Regression guard: Enemy.from_template used to scale DEF by the 'agi' keys
# of ROLE_STAT_MULT/STAT_BIAS_MULT, so tanky roles (bruiser agi 0.8,
# guardian agi 0.8) got *reduced* defense while glass assassin (agi 1.0)
# kept full defense. DEF derives from vitality in this project's stat
# pipeline — these tests pin from_template to the vit keys.

_TEMPLATE_TIER = 5


def _role_enemy(role, bias="balanced"):
    return Enemy.from_template(
        {"name": "T", "role": role, "stat_bias": bias}, _TEMPLATE_TIER)


def test_enemy_def_follows_vit_multipliers():
    _, base_def, _ = DifficultyScaler.enemy_stats(_TEMPLATE_TIER)
    for role, mults in ROLE_STAT_MULT.items():
        expected = int(base_def * ROLE_MULT[role] * mults["vit"])
        assert _role_enemy(role).defense == expected, role
    # A vit-heavy tank role must end up above the unscaled tier baseline.
    assert _role_enemy("guardian").defense > base_def


def test_vit_bias_raises_def_agi_bias_lowers_it():
    balanced = _role_enemy("soldier", "balanced").defense
    assert _role_enemy("soldier", "vit").defense > balanced
    # agi bias trades defense away (vit key 0.9) — it must not boost DEF.
    assert _role_enemy("soldier", "agi").defense < balanced
    assert STAT_BIAS_MULT["agi"]["vit"] < 1.0 < STAT_BIAS_MULT["vit"]["vit"]


def test_bruiser_tanks_better_than_glass_roles():
    bruiser = _role_enemy("bruiser").defense
    assert bruiser > _role_enemy("assassin").defense
    assert bruiser > _role_enemy("swarm").defense
    assert bruiser > _role_enemy("soldier").defense
