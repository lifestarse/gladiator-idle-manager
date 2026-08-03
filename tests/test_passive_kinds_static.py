# Build: 1
"""Static passive-kind catalogue: registration, effect_type wiring, bounds.

Covers the twelve STATIC PassiveKind declarations in
game/passives/_kinds_static.py — the initial catalogue drafted in
scratch/passives_design/catalog.json (version 1). That file (and its sibling
facts.json) lives under scratch/, which is gitignored — a test must not read
it at collection time or it would pass locally and vanish in any clean
checkout/CI. Both are therefore transcribed here as literal data, captured at
authoring time, with the effect_type set additionally cross-checked directly
against the consumer source (not just against facts.json's own summary,
which undercounts the consumed set by one — see CONSUMED_EFFECT_TYPES below).
"""
from game import passives

# kind -> (effect_type, slots, bounds, l10n, rails)
#   effect_type/slots/bounds/l10n: scratch/passives_design/catalog.json v1.
#   rails: catalog's per-rarity [min, max] authoring bands (fractions).
# lifesteal_pct predates the catalogue (already shipped, catalog "exists":
# true) and is included so the registration/consumption tests below cover
# the whole static set, not just the eleven added by this catalogue.
CATALOG = {
    "lifesteal_pct": dict(
        effect_type="lifesteal_pct", slots=frozenset({"weapon", "relic"}),
        bounds=(0.0, 0.50), l10n="passive_lifesteal_pct",
        rails={"common": (0.01, 0.02), "uncommon": (0.02, 0.03),
               "rare": (0.03, 0.04), "epic": (0.04, 0.06),
               "legendary": (0.06, 0.08)},
    ),
    "damage_bonus_pct": dict(
        effect_type="damage_bonus",
        slots=frozenset({"weapon", "armor", "relic"}),
        bounds=(0.0, 0.25), l10n="passive_damage_bonus_pct",
        rails={"common": (0.01, 0.02), "uncommon": (0.02, 0.03),
               "rare": (0.03, 0.05), "epic": (0.05, 0.07),
               "legendary": (0.07, 0.10)},
    ),
    "hp_bonus_pct": dict(
        effect_type="hp_bonus_pct",
        slots=frozenset({"armor", "accessory", "relic"}),
        bounds=(0.0, 0.30), l10n="passive_hp_bonus_pct",
        rails={"common": (0.02, 0.03), "uncommon": (0.03, 0.05),
               "rare": (0.05, 0.07), "epic": (0.07, 0.10),
               "legendary": (0.10, 0.15)},
    ),
    "crit_chance_bonus": dict(
        effect_type="crit_chance_bonus",
        slots=frozenset({"weapon", "armor", "accessory", "relic"}),
        bounds=(0.0, 0.15), l10n="passive_crit_chance_bonus",
        rails={"common": (0.01, 0.02), "uncommon": (0.02, 0.03),
               "rare": (0.03, 0.04), "epic": (0.04, 0.06),
               "legendary": (0.06, 0.08)},
    ),
    "crit_damage_bonus": dict(
        effect_type="crit_damage_bonus",
        slots=frozenset({"weapon", "armor", "accessory", "relic"}),
        bounds=(0.0, 0.50), l10n="passive_crit_damage_bonus",
        rails={"common": (0.03, 0.05), "uncommon": (0.05, 0.08),
               "rare": (0.08, 0.12), "epic": (0.12, 0.18),
               "legendary": (0.18, 0.25)},
    ),
    "dodge_chance_bonus": dict(
        effect_type="dodge_chance_bonus",
        slots=frozenset({"weapon", "armor", "accessory", "relic"}),
        bounds=(0.0, 0.12), l10n="passive_dodge_chance_bonus",
        rails={"common": (0.01, 0.02), "uncommon": (0.02, 0.03),
               "rare": (0.03, 0.04), "epic": (0.04, 0.05),
               "legendary": (0.05, 0.06)},
    ),
    "damage_reduction": dict(
        effect_type="damage_reduction",
        slots=frozenset({"weapon", "armor", "relic"}),
        bounds=(0.0, 0.12), l10n="passive_damage_reduction",
        rails={"common": (0.01, 0.02), "uncommon": (0.02, 0.03),
               "rare": (0.03, 0.04), "epic": (0.04, 0.05),
               "legendary": (0.05, 0.07)},
    ),
    "reduce_injury_severity": dict(
        effect_type="reduce_injury_severity",
        slots=frozenset({"weapon", "armor", "accessory", "relic"}),
        bounds=(0.0, 0.40), l10n="passive_reduce_injury_severity",
        rails={"common": (0.05, 0.08), "uncommon": (0.08, 0.12),
               "rare": (0.12, 0.15), "epic": (0.15, 0.20),
               "legendary": (0.20, 0.25)},
    ),
    "on_kill_heal_pct": dict(
        effect_type="on_kill_heal_pct",
        slots=frozenset({"weapon", "accessory", "relic"}),
        bounds=(0.0, 0.15), l10n="passive_on_kill_heal_pct",
        rails={"common": (0.02, 0.03), "uncommon": (0.03, 0.04),
               "rare": (0.04, 0.05), "epic": (0.05, 0.07),
               "legendary": (0.07, 0.10)},
    ),
    "regen_per_turn_pct": dict(
        effect_type="regen_per_turn_pct",
        slots=frozenset({"armor", "accessory", "relic"}),
        bounds=(0.0, 0.06), l10n="passive_regen_per_turn_pct",
        rails={"common": (0.01, 0.01), "uncommon": (0.01, 0.02),
               "rare": (0.02, 0.02), "epic": (0.02, 0.03),
               "legendary": (0.03, 0.04)},
    ),
    "on_dodge_counter": dict(
        effect_type="on_dodge_counter",
        slots=frozenset({"weapon", "armor", "relic"}),
        bounds=(0.0, 0.40), l10n="passive_on_dodge_counter",
        rails={"common": (0.05, 0.08), "uncommon": (0.08, 0.12),
               "rare": (0.12, 0.18), "epic": (0.18, 0.25),
               "legendary": (0.25, 0.30)},
    ),
    "bonus_gold_pct": dict(
        effect_type="bonus_gold_pct",
        slots=frozenset({"weapon", "armor", "accessory", "relic"}),
        bounds=(0.0, 0.25), l10n="passive_bonus_gold_pct",
        rails={"common": (0.02, 0.03), "uncommon": (0.03, 0.05),
               "rare": (0.05, 0.08), "epic": (0.08, 0.12),
               "legendary": (0.12, 0.15)},
    ),
}

# get_perk_effects() effect_type strings a downstream consumer actually reads,
# grep-verified in this session against:
#   game/models/fighterstatsmixin.py:91,106,113,114,127,138
#   game/models/_fighter.py:237
#   game/battle/_manager_stats.py:44-51 (the per-battle stat-cache snapshot;
#     on_dodge_counter is passed to get_perk_effects under this name even
#     though the cache key it fills is 'on_dodge_counter_pct')
# 12 entries — scratch/passives_design/facts.json's own tally ("11") miscounts
# by one against its own listed array; the array (not the tally) is what was
# cross-checked against source and is reproduced here.
CONSUMED_EFFECT_TYPES = frozenset({
    "damage_bonus", "hp_bonus_pct", "crit_chance_bonus", "dodge_chance_bonus",
    "crit_damage_bonus", "damage_reduction", "reduce_injury_severity",
    "lifesteal_pct", "on_kill_heal_pct", "regen_per_turn_pct",
    "on_dodge_counter", "bonus_gold_pct",
})


def test_catalog_effect_types_are_exactly_the_consumed_set():
    """Sanity-check the two literal fixtures above agree with each other
    before trusting either against the live registry."""
    catalog_effect_types = {spec["effect_type"] for spec in CATALOG.values()}
    assert catalog_effect_types == CONSUMED_EFFECT_TYPES


def test_every_catalog_kind_is_registered():
    missing = set(CATALOG) - set(passives.PASSIVE_KINDS)
    assert not missing, f"catalog kinds never registered: {sorted(missing)}"


def test_no_stray_static_kind_outside_the_catalog():
    """Every STATIC kind registered today should trace back to the catalogue
    — anything else is either the catalogue going stale or a kind that
    bypassed it. (Non-static/triggered kinds, once they exist, are exempt.)"""
    static_kinds = {k for k, d in passives.PASSIVE_KINDS.items()
                    if d.category == passives.CATEGORY_STATIC}
    extra = static_kinds - set(CATALOG)
    assert not extra, f"static kinds missing from the catalog fixture: {sorted(extra)}"


def test_registered_effect_type_matches_catalog():
    for kind, spec in CATALOG.items():
        kind_def = passives.PASSIVE_KINDS[kind]
        assert kind_def.effect_type == spec["effect_type"], (
            f"{kind}: registered effect_type {kind_def.effect_type!r} != "
            f"catalog {spec['effect_type']!r}")


def test_effect_type_is_consumed_by_a_downstream_reader():
    for kind, spec in CATALOG.items():
        assert spec["effect_type"] in CONSUMED_EFFECT_TYPES, (
            f"{kind}: effect_type {spec['effect_type']!r} has no known "
            "downstream consumer — a passive that computes nothing")


def test_registered_slots_match_catalog():
    for kind, spec in CATALOG.items():
        kind_def = passives.PASSIVE_KINDS[kind]
        assert kind_def.slots == spec["slots"], (
            f"{kind}: registered slots {sorted(kind_def.slots)} != "
            f"catalog {sorted(spec['slots'])}")


def test_registered_bounds_match_catalog():
    for kind, spec in CATALOG.items():
        kind_def = passives.PASSIVE_KINDS[kind]
        assert kind_def.params["value"] == spec["bounds"], (
            f"{kind}: registered bounds {kind_def.params['value']} != "
            f"catalog {spec['bounds']}")


def test_registered_l10n_key_matches_catalog():
    for kind, spec in CATALOG.items():
        kind_def = passives.PASSIVE_KINDS[kind]
        assert kind_def.l10n == spec["l10n"]


def test_rails_are_monotonic_and_fit_inside_the_bounds():
    """The rails are authoring guidance for data/item_passives.json, not the
    registry's own params — but a rail outside its kind's bounds would mean
    every value an author picks near the top of that rarity gets silently
    dropped by _validate._check_params at compile time."""
    for kind, spec in CATALOG.items():
        low_bound, high_bound = spec["bounds"]
        rarities = ("common", "uncommon", "rare", "epic", "legendary")
        prev_high = low_bound
        for rarity in rarities:
            r_low, r_high = spec["rails"][rarity]
            assert r_low <= r_high, f"{kind}/{rarity}: rail min > max"
            assert low_bound <= r_low and r_high <= high_bound, (
                f"{kind}/{rarity}: rail {spec['rails'][rarity]} escapes "
                f"registered bounds {spec['bounds']}")
            assert r_low >= prev_high, (
                f"{kind}/{rarity}: rail {spec['rails'][rarity]} dips below "
                f"the previous rarity's ceiling {prev_high}")
            prev_high = r_high


def test_static_kinds_carry_exactly_one_param_named_value():
    """static_effect_for (game/passives/_registry.py:155-165) assumes this
    shape — a second param on a static kind would be silently dropped from
    the get_perk_effects payload it builds."""
    for kind in CATALOG:
        kind_def = passives.PASSIVE_KINDS[kind]
        assert set(kind_def.params) == {"value"}
