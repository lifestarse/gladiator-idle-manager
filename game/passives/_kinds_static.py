# Build: 2
"""Static passive kinds — declarations only, no mechanics.

A static kind names an existing `get_perk_effects` effect type, so the
mechanic is already implemented and already tested: Fighter.get_perk_effects
sums it, `_consume`'s `*_upgrade`-replaces-sum override applies to it, and
every consumer picks it up untouched. For `lifesteal_pct` that is
BattleManager._fighter_stats (game/battle/_manager_stats.py:44) feeding the
on-hit heal in _player_attack_phase.

That reuse is the reason statics carry the bulk of the catalogue: an item
granting lifesteal needs zero new lines in the battle loop.

This module now carries the full initial static catalogue (scratch/
passives_design/catalog.json, version 1) — twelve kinds, one per
get_perk_effects effect_type actually read by a downstream consumer
(scratch/passives_design/facts.json section 3, cross-checked directly
against game/models/fighterstatsmixin.py, game/models/_fighter.py and
game/battle/_manager_stats.py — see the per-kind `notes` below for exact
file:line). `params["value"]` bounds are the catalogue's sanity rails, not
balance targets: every authored per-rarity value in data/item_passives.json
must fall inside them, but nothing requires an item to reach the ceiling.
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

register_kind(PassiveKind(
    kind="damage_bonus_pct",
    category=CATEGORY_STATIC,
    # Reuses "damage_bonus", the effect_type the class-passive/perk system
    # already sums (game/models/fighterstatsmixin.py:91, Fighter.attack) —
    # the kind is named "_pct" for clarity in data/item_passives.json, the
    # effect_type it feeds is not.
    effect_type="damage_bonus",
    slots=frozenset({"weapon", "armor", "relic"}),
    # Multiplies the whole ATK (int(base * (1 + bonus))), hence the tight
    # ceiling relative to hp/crit kinds below.
    params={"value": (0.0, 0.25)},
    l10n="passive_damage_bonus_pct",
    l10n_args=(("pct", "value", 100),),
    notes="Flat percentage bonus to attack damage.",
))

register_kind(PassiveKind(
    kind="hp_bonus_pct",
    category=CATEGORY_STATIC,
    effect_type="hp_bonus_pct",
    slots=frozenset({"armor", "accessory", "relic"}),
    # game/models/fighterstatsmixin.py:106, Fighter.max_hp.
    params={"value": (0.0, 0.30)},
    l10n="passive_hp_bonus_pct",
    l10n_args=(("pct", "value", 100),),
    notes="Flat percentage bonus to maximum HP.",
))

register_kind(PassiveKind(
    kind="crit_chance_bonus",
    category=CATEGORY_STATIC,
    effect_type="crit_chance_bonus",
    slots=frozenset({"weapon", "armor", "accessory", "relic"}),
    # game/models/fighterstatsmixin.py:113 folds this into effective_agility
    # (converted to AGI points via value*100) ahead of the crit soft-cap
    # curve — same convention the existing crit/dodge perks already use.
    params={"value": (0.0, 0.15)},
    l10n="passive_crit_chance_bonus",
    l10n_args=(("pct", "value", 100),),
    notes="Increases critical hit chance.",
))

register_kind(PassiveKind(
    kind="crit_damage_bonus",
    category=CATEGORY_STATIC,
    effect_type="crit_damage_bonus",
    slots=frozenset({"weapon", "armor", "accessory", "relic"}),
    # game/models/fighterstatsmixin.py:127, Fighter.crit_mult. The assassin
    # class passive alone reaches 0.25 — the legendary rail tops out there.
    params={"value": (0.0, 0.50)},
    l10n="passive_crit_damage_bonus",
    l10n_args=(("pct", "value", 100),),
    notes="Increases the damage multiplier of critical hits.",
))

register_kind(PassiveKind(
    kind="dodge_chance_bonus",
    category=CATEGORY_STATIC,
    effect_type="dodge_chance_bonus",
    slots=frozenset({"weapon", "armor", "accessory", "relic"}),
    # game/models/fighterstatsmixin.py:114 — same AGI-point conversion as
    # crit_chance_bonus, summed into the same effective_agility call.
    params={"value": (0.0, 0.12)},
    l10n="passive_dodge_chance_bonus",
    l10n_args=(("pct", "value", 100),),
    notes="Increases dodge chance.",
))

register_kind(PassiveKind(
    kind="damage_reduction",
    category=CATEGORY_STATIC,
    effect_type="damage_reduction",
    # Weapons and relics only, on the same "not a breastplate" reasoning as
    # lifesteal_pct — this reduction stacks additively with the tank class
    # passive and defense perks (Fighter.damage_reduction), which already
    # reach 0.10, hence the low ceiling here.
    slots=frozenset({"weapon", "armor", "relic"}),
    params={"value": (0.0, 0.12)},
    l10n="passive_damage_reduction",
    l10n_args=(("pct", "value", 100),),
    notes="Reduces incoming damage. game/models/fighterstatsmixin.py:138, "
          "cached at game/battle/_manager_stats.py:43.",
))

register_kind(PassiveKind(
    kind="reduce_injury_severity",
    category=CATEGORY_STATIC,
    effect_type="reduce_injury_severity",
    slots=frozenset({"weapon", "armor", "accessory", "relic"}),
    # Non-combat QoL rather than a per-hit combat stat, hence the widest
    # rails in the catalogue. game/models/_fighter.py:237.
    params={"value": (0.0, 0.40)},
    l10n="passive_reduce_injury_severity",
    l10n_args=(("pct", "value", 100),),
    notes="Reduces the severity of injuries taken.",
))

register_kind(PassiveKind(
    kind="on_kill_heal_pct",
    category=CATEGORY_STATIC,
    effect_type="on_kill_heal_pct",
    slots=frozenset({"weapon", "accessory", "relic"}),
    # game/battle/_manager_stats.py:45 (cached), applied at
    # game/battle/_manager_player_attack.py:80.
    params={"value": (0.0, 0.15)},
    l10n="passive_on_kill_heal_pct",
    l10n_args=(("pct", "value", 100),),
    notes="Heals a share of max HP whenever the wearer lands a kill.",
))

register_kind(PassiveKind(
    kind="regen_per_turn_pct",
    category=CATEGORY_STATIC,
    effect_type="regen_per_turn_pct",
    slots=frozenset({"armor", "accessory", "relic"}),
    # Every turn of every fight — tightest rails in the catalogue on
    # purpose. game/battle/_manager_stats.py:46 (cached), applied at
    # game/battle/_manager_support.py:66.
    params={"value": (0.0, 0.06)},
    l10n="passive_regen_per_turn_pct",
    l10n_args=(("pct", "value", 100),),
    notes="Regenerates a share of max HP at the start of each turn.",
))

register_kind(PassiveKind(
    kind="on_dodge_counter",
    category=CATEGORY_STATIC,
    effect_type="on_dodge_counter",
    # Not accessory: a counter-attack belongs to the thing that strikes back
    # or to the thing that bends a rule, same reasoning as lifesteal_pct.
    slots=frozenset({"weapon", "armor", "relic"}),
    # Sums with the retiarius class passive (0.50, upgrade 0.75) — capped
    # low here on purpose. Rides the existing cache path
    # (game/battle/_manager_stats.py:50, gpe('on_dodge_counter') stored under
    # the cache key 'on_dodge_counter_pct'; consumed at
    # game/battle/_manager_enemy_attack.py:20) — no battle-cycle edits.
    params={"value": (0.0, 0.40)},
    l10n="passive_on_dodge_counter",
    l10n_args=(("pct", "value", 100),),
    notes="Counter-attacks for a share of normal damage after a dodge.",
))

register_kind(PassiveKind(
    kind="bonus_gold_pct",
    category=CATEGORY_STATIC,
    effect_type="bonus_gold_pct",
    slots=frozenset({"weapon", "armor", "accessory", "relic"}),
    # Economy-only, safe at the top rail. game/battle/_manager_stats.py:51
    # (cached), applied at game/battle/_manager_player_attack.py:70 and
    # game/battle/_manager_enemy_attack.py:37.
    params={"value": (0.0, 0.25)},
    l10n="passive_bonus_gold_pct",
    l10n_args=(("pct", "value", 100),),
    notes="Earns more gold from victories.",
))
