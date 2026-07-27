# Build: 1
"""Static passive kinds — declarations only, no mechanics.

A static kind names an existing `get_perk_effects` effect type, so the
mechanic is already implemented and already tested: Fighter.get_perk_effects
sums it, `_consume`'s `*_upgrade`-replaces-sum override applies to it, and
every consumer picks it up untouched. For `lifesteal_pct` that is
BattleManager._fighter_stats (game/battle/_manager_stats.py:44) feeding the
on-hit heal in _player_attack_phase.

That reuse is the reason statics carry the bulk of the catalogue: an item
granting lifesteal needs zero new lines in the battle loop.
"""
from ._registry import CATEGORY_STATIC, PassiveKind, register_kind

register_kind(PassiveKind(
    kind="lifesteal_pct",
    category=CATEGORY_STATIC,
    effect_type="lifesteal_pct",
    # Weapons and relics only. Draining life belongs to the thing that opens
    # the wound or to the thing that bends a rule — not to a breastplate.
    slots=frozenset({"weapon", "relic"}),
    # Upper bound is a sanity rail, not a target: the strongest lifesteal in
    # the game today is the mercenary capstone perk Sellsword Mastery at 0.08.
    params={"value": (0.0, 0.50)},
    l10n="passive_lifesteal_pct",
    l10n_args=(("pct", "value", 100),),
    notes="Heals the attacker for a share of damage dealt, per landed hit.",
))
