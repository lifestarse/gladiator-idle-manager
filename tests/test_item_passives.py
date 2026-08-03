# Build: 4
"""Per-item passive effects — registry, compiler, wiring and remote patching.

The vertical slice this covers: a definition in data/item_passives.json becomes
a PassiveSpec, reaches Fighter.get_perk_effects through the equipped item, is
snapshotted by the battle stat cache, renders in every language, survives a
save round-trip without a migration, and can be renumbered by a remote patch
but never re-pointed at a different mechanic.

Slot unlocking (the "passive slots" section): an item's slot count equals its
rarity rank, slot #n activates at upgrade level (n + 1) *
PASSIVE_SLOT_UNLOCK_STEP, and a locked slot must be inert everywhere — the
validator refuses indexes the rarity can never unlock, the fighter gate skips
locked specs, and the renderer shows them as locked rows.
"""
import collections
import json
import os

import pytest

from game import passives
from game.passives import _validate as passives_validate
from game.passives._registry import (CATEGORY_STATIC, CATEGORY_TRIGGERED,
                                     PassiveKind, register_kind)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFS_PATH = os.path.join(ROOT, "data", "item_passives.json")

# The item the Stage-1 slice is built on. Kept as a name so a rename shows up
# here as one edit rather than as six mysterious failures.
SLICE_ITEM = "rusty_blade"
SLICE_KEY = "rusty_blade#0"


def _weapon(engine, item_id):
    import game.models as models

    for item in models.FORGE_WEAPONS:
        if item["id"] == item_id:
            return dict(item)
    raise AssertionError(f"{item_id} missing from FORGE_WEAPONS")


def _bare_item():
    """A synthetic item guaranteed to carry no authored passives.

    Every shipped FORGE_WEAPONS entry has gained a passive since this suite
    was written, so "the item without any" can no longer be found by
    filtering real content — searching FORGE_WEAPONS for one now raises
    StopIteration. The control case this covers (an id absent from
    COMPILED_PASSIVES) does not depend on the content team ever leaving one
    weapon bare, so it is synthesized instead. Only `id` is populated: it is
    the only field get_perk_effects, passive_marker and render_slots read
    before short-circuiting on the empty COMPILED_PASSIVES lookup.
    """
    return {"id": "test_bare_item_no_passives"}


# --------------------------------------------------------------- registry

def test_registry_rejects_a_duplicate_kind():
    """Two mechanics under one name would silently resolve to whichever module
    imported last."""
    existing = next(iter(passives.PASSIVE_KINDS.values()))
    with pytest.raises(ValueError, match="duplicate"):
        register_kind(PassiveKind(
            kind=existing.kind, category=CATEGORY_STATIC,
            effect_type="lifesteal_pct", slots=frozenset({"weapon"}),
            params={"value": (0.0, 1.0)}, l10n="passive_lifesteal_pct",
        ))


@pytest.mark.parametrize("broken, match", [
    (dict(category="nonsense"), "unknown category"),
    (dict(slots=frozenset()), "declares no slots"),
    (dict(slots=frozenset({"hat"})), "unknown slots"),
    (dict(effect_type=None), "must name the get_perk_effects"),
    (dict(trigger="on_hit"), "must not declare a trigger"),
    (dict(params={"value": (1.0, 0.0)}), "needs a .low, high. range"),
    (dict(l10n_args=(("pct", "nope", 100),)), "undeclared param"),
])
def test_registry_rejects_malformed_declarations(broken, match):
    """Loud at import time beats a mechanic that quietly does nothing."""
    spec = dict(
        kind="__test_kind__", category=CATEGORY_STATIC,
        effect_type="lifesteal_pct", slots=frozenset({"weapon"}),
        params={"value": (0.0, 1.0)}, l10n="passive_lifesteal_pct",
    )
    spec.update(broken)
    with pytest.raises(ValueError, match=match):
        register_kind(PassiveKind(**spec))
    assert "__test_kind__" not in passives.PASSIVE_KINDS


def test_triggered_kind_must_declare_a_hook():
    with pytest.raises(ValueError, match="must declare"):
        register_kind(PassiveKind(
            kind="__test_triggered__", category=CATEGORY_TRIGGERED,
            slots=frozenset({"weapon"}), params={"value": (0.0, 1.0)},
            l10n="passive_lifesteal_pct",
        ))


def test_every_static_kind_maps_to_an_effect_type():
    for kind, kind_def in passives.PASSIVE_KINDS.items():
        if kind_def.category == CATEGORY_STATIC:
            assert passives.STATIC_EFFECT_KINDS.get(kind) == kind_def.effect_type


def test_passives_package_imports_no_heavy_siblings():
    """game.models.fighterperksmixin imports this package, and
    game/battle/_shared.py imports game.models — so a reverse dependency here
    would close an import cycle. Checked on the source, not on sys.modules,
    which is already polluted by whatever else the suite imported."""
    import game.passives as pkg

    pkg_dir = os.path.dirname(pkg.__file__)
    offenders = []
    for name in sorted(os.listdir(pkg_dir)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(pkg_dir, name), encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                stripped = line.strip()
                if not stripped.startswith(("import ", "from ")):
                    continue          # only module-scope import statements
                if line[:1].isspace():
                    continue          # indented = deferred inside a function
                if ("game.models" in stripped or "game.battle" in stripped):
                    offenders.append(f"{name}:{lineno}: {stripped}")
    assert not offenders, ("game.passives must not import game.models or "
                           "game.battle at module scope:\n  "
                           + "\n  ".join(offenders))


# --------------------------------------------------------------- compiler

def _slots():
    """{item id: (slot, rarity)} — the shape slot_index() feeds compile_all.

    w1 is legendary so single-item tests have all five slot indexes legal;
    the wc/wu/wr/we ladder exists for the rarity-cap tests."""
    return {"w1": ("weapon", "legendary"), "a1": ("armor", "common"),
            "r1": ("relic", "rare"),
            "wc": ("weapon", "common"), "wu": ("weapon", "uncommon"),
            "wr": ("weapon", "rare"), "we": ("weapon", "epic")}


def _compile(defs):
    return passives.compile_all(defs, _slots())


@pytest.fixture
def extra_kinds(monkeypatch):
    """Six throwaway static weapon kinds, reverted after the test.

    Needed because one item may not carry the same kind twice, and the
    shipped registry has a limited kind set — multi-slot fixtures want one
    kind per slot. monkeypatch.setitem mutates the real PASSIVE_KINDS dict
    (the object _validate reads) and restores it on teardown, so nothing
    leaks into the language-coverage tests that iterate the registry."""
    from game.passives._registry import PASSIVE_KINDS

    names = []
    for i in range(6):
        name = f"__slot_test_{i}__"
        monkeypatch.setitem(PASSIVE_KINDS, name, PassiveKind(
            kind=name, category=CATEGORY_STATIC,
            effect_type="lifesteal_pct", slots=frozenset({"weapon"}),
            params={"value": (0.0, 1.0)}, l10n="passive_lifesteal_pct",
            l10n_args=(("pct", "value", 100),),
        ))
        names.append(name)
    return names


def test_compiles_a_well_formed_definition():
    out = _compile({"w1#0": {"item": "w1", "kind": "lifesteal_pct",
                             "value": 0.05}})
    assert list(out) == ["w1"]
    spec = out["w1"][0]
    assert spec.kind == "lifesteal_pct"
    assert spec.params == {"value": 0.05}
    assert dict(spec.static_effect) == {"type": "lifesteal_pct", "value": 0.05}


def test_specs_are_ordered_by_index_not_by_file_order(extra_kinds):
    """The JSON is hand-authored; reordering it must not reorder dispatch."""
    out = _compile({
        "w1#2": {"item": "w1", "kind": extra_kinds[2], "value": 0.03},
        "w1#0": {"item": "w1", "kind": extra_kinds[0], "value": 0.01},
        "w1#1": {"item": "w1", "kind": extra_kinds[1], "value": 0.02},
    })
    assert [s.index for s in out["w1"]] == [0, 1, 2]
    assert [s.params["value"] for s in out["w1"]] == [0.01, 0.02, 0.03]


@pytest.mark.parametrize("defs", [
    pytest.param({"w1": {"item": "w1", "kind": "lifesteal_pct", "value": 0.05}},
                 id="key-without-index"),
    pytest.param({"w1#x": {"item": "w1", "kind": "lifesteal_pct", "value": 0.05}},
                 id="non-numeric-index"),
    pytest.param({"w1#0": {"item": "w2", "kind": "lifesteal_pct", "value": 0.05}},
                 id="item-disagrees-with-key"),
    pytest.param({"ghost#0": {"item": "ghost", "kind": "lifesteal_pct",
                              "value": 0.05}}, id="unknown-item"),
    pytest.param({"w1#0": {"item": "w1", "kind": "nope", "value": 0.05}},
                 id="unknown-kind"),
    pytest.param({"a1#0": {"item": "a1", "kind": "lifesteal_pct", "value": 0.05}},
                 id="kind-not-allowed-on-slot"),
    pytest.param({"w1#0": {"item": "w1", "kind": "lifesteal_pct", "value": 9.0}},
                 id="param-out-of-range"),
    pytest.param({"w1#0": {"item": "w1", "kind": "lifesteal_pct", "value": True}},
                 id="bool-is-not-a-number"),
    pytest.param({"w1#0": {"item": "w1", "kind": "lifesteal_pct",
                           "value": "0.05"}}, id="string-is-not-a-number"),
    pytest.param({"w1#0": {"item": "w1", "kind": "lifesteal_pct"}},
                 id="missing-param"),
    pytest.param({"w1#0": {"item": "w1", "kind": "lifesteal_pct", "value": 0.05,
                           "vlaue": 0.9}}, id="typo-param-is-rejected-not-ignored"),
    pytest.param({"w1#0": {"item": "w1", "kind": "lifesteal_pct", "value": 0.05,
                           "trigger": "on_hit"}}, id="static-with-trigger"),
    pytest.param({"w1#0": {"item": "w1", "kind": "lifesteal_pct", "value": 0.05,
                           "cond": "vs_boss"}}, id="unknown-condition"),
    pytest.param({"w1#0": "not an object"}, id="entry-is-not-an-object"),
])
def test_malformed_definitions_are_dropped_not_raised(defs):
    """A shipped game must not die on bad data — the same policy _validate_ids
    already follows. The passive is lost; the install is not."""
    assert _compile(defs) == {}


def test_definitions_must_be_a_mapping():
    assert passives.compile_all([], _slots()) == {}
    assert passives.compile_all(None, _slots()) == {}


def test_the_global_cap_matches_the_top_rarity_slot_count(extra_kinds):
    """PASSIVE_MAX_PER_ITEM stays as a backstop; the real per-item limit is
    slot_count(rarity). For a legendary the two coincide, so one spec past
    the cap loses exactly the surplus index to the dead-slot check."""
    from game.constants import PASSIVE_MAX_PER_ITEM
    from game.models._helpers import RARITY_LEGENDARY

    assert PASSIVE_MAX_PER_ITEM == passives.slot_count(
        {"rarity": RARITY_LEGENDARY})

    defs = {f"w1#{i}": {"item": "w1", "kind": extra_kinds[i], "value": 0.01}
            for i in range(PASSIVE_MAX_PER_ITEM + 1)}
    out = _compile(defs)
    assert len(out["w1"]) == PASSIVE_MAX_PER_ITEM


def test_install_replaces_in_place(engine):
    """Consumers capture COMPILED_PASSIVES at import time; a rebind would leave
    them reading an empty dict forever.

    Takes the `engine` fixture so the shipped compilation can be restored
    through the real path afterwards — this mutates module-level state that the
    rest of the session shares.
    """
    before = passives.COMPILED_PASSIVES
    try:
        passives.install({"w1#0": {"item": "w1", "kind": "lifesteal_pct",
                                   "value": 0.05}}, _slots())
        assert passives.COMPILED_PASSIVES is before
        assert "w1" in before
        passives.install({}, _slots())
        assert before == {}, "an empty definitions file must clear stale specs"
    finally:
        engine._wire_data()
    assert SLICE_ITEM in passives.COMPILED_PASSIVES, "restore path is broken"


# ----------------------------------------------------------- passive slots

def test_rarity_max_upgrade_is_step_times_rarity_rank():
    """The invariant the whole unlock formula rides on: every rarity's upgrade
    cap is PASSIVE_SLOT_UNLOCK_STEP times its rank, so slot_count(r) == rank
    and each rarity's LAST slot unlocks exactly at its own upgrade cap."""
    from game.constants import PASSIVE_SLOT_UNLOCK_STEP
    from game.models._helpers import RARITY_MAX_UPGRADE

    for rank, (rarity, cap) in enumerate(RARITY_MAX_UPGRADE.items(), start=1):
        assert cap == PASSIVE_SLOT_UNLOCK_STEP * rank, rarity
        assert passives.slot_count({"rarity": rarity}) == rank


def test_unlock_threshold_is_derived_from_the_slot_index():
    """The threshold is a formula over the `#n` suffix, never stored in data —
    a remote patch cannot desync what does not exist."""
    from game.constants import PASSIVE_MAX_PER_ITEM, PASSIVE_SLOT_UNLOCK_STEP

    for index in range(PASSIVE_MAX_PER_ITEM):
        assert (passives.unlock_threshold(index)
                == (index + 1) * PASSIVE_SLOT_UNLOCK_STEP)


@pytest.mark.parametrize("item_id, rank", [
    ("wc", 1), ("wu", 2), ("wr", 3), ("we", 4), ("w1", 5),
])
def test_rarity_limits_the_slot_count(extra_kinds, item_id, rank):
    """Author one spec more than the rarity's rank allows: the surplus index
    can never unlock, and the validator drops exactly it."""
    defs = {f"{item_id}#{i}": {"item": item_id, "kind": extra_kinds[i],
                               "value": 0.01}
            for i in range(rank + 1)}
    out = _compile(defs)
    assert [s.index for s in out[item_id]] == list(range(rank))


def test_a_dead_slot_is_rejected_by_the_validator(extra_kinds):
    """"#1" on a common item can never activate — its threshold exceeds the
    rarity's upgrade cap — so the validator refuses it while keeping "#0"."""
    out = _compile({
        "wc#0": {"item": "wc", "kind": extra_kinds[0], "value": 0.02},
        "wc#1": {"item": "wc", "kind": extra_kinds[1], "value": 0.03},
    })
    assert [s.index for s in out["wc"]] == [0]


def test_a_duplicate_kind_on_one_item_is_dropped():
    """Stacked copies of one effect on one item would defeat the balance
    rails; the lower-indexed copy — the one that unlocks first — wins."""
    out = _compile({
        "w1#0": {"item": "w1", "kind": "lifesteal_pct", "value": 0.02},
        "w1#1": {"item": "w1", "kind": "lifesteal_pct", "value": 0.05},
    })
    assert [(s.index, s.kind) for s in out["w1"]] == [(0, "lifesteal_pct")]
    assert out["w1"][0].params["value"] == 0.02


def test_a_locked_slot_gives_no_effect_until_its_threshold(engine):
    """Static item passives are not always-on: slot #0 contributes only once
    THIS item instance reaches its unlock threshold. Below it, the fighter
    reads exactly the baseline."""
    from game.models import Fighter

    fighter = Fighter(name="Gated", fighter_class="mercenary")
    baseline = fighter.get_perk_effects("lifesteal_pct")
    threshold = passives.unlock_threshold(0)
    value = passives.COMPILED_PASSIVES[SLICE_ITEM][0].params["value"]

    item = _weapon(engine, SLICE_ITEM)
    fighter.equipment["weapon"] = item
    for level, expected in ((0, baseline), (threshold - 1, baseline),
                            (threshold, baseline + value)):
        item["upgrade_level"] = level
        assert fighter.get_perk_effects("lifesteal_pct") == pytest.approx(
            expected), f"at +{level}"


def test_the_battle_stat_cache_respects_the_gate(engine):
    """The snapshot in BattleManager._fighter_stats goes through the same
    get_perk_effects gate — a locked slot must not reach combat either."""
    from game.models import Fighter

    fighter = Fighter(name="GatedCache", fighter_class="mercenary")
    item = _weapon(engine, SLICE_ITEM)
    fighter.equipment["weapon"] = item

    assert engine.battle_mgr._fighter_stats(fighter)["lifesteal_pct"] == 0

    # The snapshot is cached per battle; upgrading between battles reaches
    # combat through a fresh snapshot, which the invalidation stands in for.
    engine.battle_mgr._invalidate_fighter_stats(fighter)
    item["upgrade_level"] = passives.unlock_threshold(0)
    expected = passives.COMPILED_PASSIVES[SLICE_ITEM][0].params["value"]
    assert engine.battle_mgr._fighter_stats(fighter)[
        "lifesteal_pct"] == pytest.approx(expected)


def test_rusty_blade_stays_valid_and_unlocks_at_the_common_cap(engine):
    """The one shipped passive compiles under the slot rules and — common
    having exactly one slot — activates precisely at the rarity's max
    upgrade level."""
    from game.constants import MAX_UPGRADE_COMMON

    specs = passives.COMPILED_PASSIVES[SLICE_ITEM]
    assert [s.index for s in specs] == [0]
    assert passives.unlock_threshold(specs[0].index) == MAX_UPGRADE_COMMON

    item = _weapon(engine, SLICE_ITEM)
    item["upgrade_level"] = MAX_UPGRADE_COMMON - 1
    assert not passives.is_unlocked(specs[0], item)
    item["upgrade_level"] = MAX_UPGRADE_COMMON
    assert passives.is_unlocked(specs[0], item)


# --------------------------------------------------- shipped data + wiring

def test_shipped_definitions_all_compile(engine):
    """Every entry in the shipped file must survive validation. A silent drop
    here is an item that lost its passive between review and release."""
    with open(DEFS_PATH, encoding="utf-8") as handle:
        raw = json.load(handle)["passives"]
    compiled = passives.COMPILED_PASSIVES
    total = sum(len(specs) for specs in compiled.values())
    assert total == len(raw), (
        f"{len(raw)} definitions shipped but {total} compiled — "
        "check the warnings from game.passives._validate")


def test_wire_data_compiles_the_shipped_file(engine):
    assert SLICE_ITEM in passives.COMPILED_PASSIVES
    spec = passives.COMPILED_PASSIVES[SLICE_ITEM][0]
    assert spec.key == SLICE_KEY
    assert spec.kind == "lifesteal_pct"


def test_every_definition_names_an_item_that_exists(engine):
    """Guards the reverse of the drop path: a typo'd item id compiles to
    nothing and would otherwise be invisible."""
    import game.models as models

    known = {item["id"] for item in
             models.FORGE_WEAPONS + models.FORGE_ARMOR
             + models.FORGE_ACCESSORIES}
    for relics in models.RELICS.values():
        known.update(item["id"] for item in relics)
    with open(DEFS_PATH, encoding="utf-8") as handle:
        raw = json.load(handle)["passives"]
    unknown = sorted({entry["item"] for entry in raw.values()} - known)
    assert not unknown, f"definitions reference unknown items: {unknown}"


# ----------------------------------------------------------- fighter wiring

def test_equipping_grants_the_effect_and_unequipping_removes_it(engine):
    from game.models import Fighter

    fighter = Fighter(name="Passive Test", fighter_class="mercenary")
    baseline = fighter.get_perk_effects("lifesteal_pct")

    item = _weapon(engine, SLICE_ITEM)
    item["upgrade_level"] = passives.unlock_threshold(0)   # slot #0 active
    fighter.equipment["weapon"] = item
    equipped = fighter.get_perk_effects("lifesteal_pct")
    expected = passives.COMPILED_PASSIVES[SLICE_ITEM][0].params["value"]
    assert equipped == pytest.approx(baseline + expected)

    fighter.unequip_item("weapon")
    assert fighter.get_perk_effects("lifesteal_pct") == pytest.approx(baseline)


def test_item_passive_stacks_with_the_perk_of_the_same_type(engine):
    """Equipment is a third source into the same `_consume`, so it sums with
    the class passive and the perks rather than replacing them."""
    from game.models import Fighter

    fighter = Fighter(name="Stacker", fighter_class="mercenary")
    fighter.unlocked_perks = ["merc_sellsword_mastery"]   # lifesteal_pct 0.08
    perk_only = fighter.get_perk_effects("lifesteal_pct")
    assert perk_only > 0, "fixture perk no longer grants lifesteal"

    item = _weapon(engine, SLICE_ITEM)
    item["upgrade_level"] = passives.unlock_threshold(0)   # slot #0 active
    fighter.equipment["weapon"] = item
    expected = passives.COMPILED_PASSIVES[SLICE_ITEM][0].params["value"]
    assert fighter.get_perk_effects("lifesteal_pct") == pytest.approx(
        perk_only + expected)


def test_an_item_without_passives_changes_nothing(engine):
    from game.models import Fighter

    plain = _bare_item()
    fighter = Fighter(name="Plain", fighter_class="mercenary")
    before = fighter.get_perk_effects("lifesteal_pct")
    fighter.equipment["weapon"] = dict(plain)
    assert fighter.get_perk_effects("lifesteal_pct") == before


# ------------------------------------------------------------- persistence

def test_an_item_saved_before_this_feature_gains_it_on_load(engine,
                                                            tmp_save_path):
    """No save migration is needed: _migrate_item rebuilds every owned item
    from its JSON template, preserving only upgrade_level and enchantment. An
    inventory entry stored without special_effect must come back with it."""
    legacy = {"id": SLICE_ITEM, "name": "Rusty Blade", "slot": "weapon",
              "rarity": "common", "cost": 400, "str": 4, "agi": 0, "vit": 0,
              "upgrade_level": 2}
    engine.inventory.append(legacy)
    engine._migrate_all_items()

    restored = engine.inventory[-1]
    assert restored["upgrade_level"] == 2, "player progress must survive"
    assert restored.get("special_effect"), "flavour text did not reach the item"
    assert passives.passive_count(restored) == 1
    # +2 is below the slot #0 threshold: the passive is authored but not yet
    # active — legacy items come back locked, not retroactively empowered.
    assert passives.unlocked_count(restored) == 0


def test_no_passive_mechanics_are_written_into_the_save(engine):
    """Mechanics must never reach the save.

    `_migrate_item` rebuilds every owned item from its template and preserves
    exactly `upgrade_level` and `enchantment`, so anything else stored per item
    is either destroyed on the next load or, worse, a stale copy that disagrees
    with the shipped data. Keeping kind/params purely in COMPILED_PASSIVES is
    what makes the whole feature migration-free.

    `special_effect` is a deliberate exception and is NOT asserted against: the
    save stores the item dict wholesale, so the flavour string rides along with
    `description`, which has always been stored the same way. That is waste,
    not a correctness problem — it is rebuilt from the template on load either
    way. See the note in this test for the size it costs.
    """
    engine.inventory.append(_weapon(engine, SLICE_ITEM))
    blob = json.dumps(engine._build_save_data())
    assert "lifesteal_pct" not in blob, "a passive kind leaked into the save"
    assert SLICE_KEY not in blob, "a passive key leaked into the save"
    for saved in engine._build_save_data()["inventory"]:
        assert "passives" not in saved
        assert "kind" not in saved


# ------------------------------------------------------------- remote patch

def test_a_remote_patch_can_retune_a_passive(engine):
    from game.remote_content import gamedata

    accepted, rejected = gamedata.validate(
        {"item_passives": {SLICE_KEY: {"value": 0.05}}})
    assert not rejected
    assert accepted["item_passives"][SLICE_KEY]["value"] == 0.05


@pytest.mark.parametrize("field, value", [
    ("kind", "thorns_reflect"),      # would re-point at another mechanic
    ("item", "godslayer_pilum"),     # would move the passive to another item
    ("trigger", "on_hit"),
])
def test_a_remote_patch_cannot_change_what_a_passive_is(field, value):
    from game.remote_content import gamedata

    _accepted, rejected = gamedata.validate(
        {"item_passives": {SLICE_KEY: {field: value}}})
    assert rejected, f"{field} must not be patchable"


def test_a_patched_value_outside_the_kind_range_is_dropped_not_shipped():
    """The PATCHABLE range is only a typo rail; the kind's own range is applied
    afterwards, at compile time, so a bad remote number costs one passive
    rather than shipping a broken mechanic."""
    from game.remote_content import gamedata

    over = 9.0
    kind_low, kind_high = passives.PASSIVE_KINDS["lifesteal_pct"].params["value"]
    patch_low, patch_high = gamedata.PATCHABLE["item_passives"][2]["value"]
    assert patch_low <= over <= patch_high, "fixture no longer passes the rail"
    assert not kind_low <= over <= kind_high, "fixture no longer breaks the kind"

    assert _compile({"w1#0": {"item": "w1", "kind": "lifesteal_pct",
                              "value": over}}) == {}


# ------------------------------------------------------------------ render

def test_render_substitutes_the_declared_l10n_args(engine):
    from game.localization import get_language, set_language

    previous = get_language()
    try:
        set_language("en")
        spec = passives.COMPILED_PASSIVES[SLICE_ITEM][0]
        assert passives.render_args(spec) == {"pct": "2"}
        assert "2%" in passives.render(spec)
    finally:
        set_language(previous)


def test_every_kind_has_a_template_that_formats_in_every_language():
    """t() returns the key on a miss and swallows format errors, so a missing
    or mis-placeholdered template shows up to the player as raw
    "passive_<kind>" instead of raising. This is what catches it."""
    from game.localization import SUPPORTED_LANGUAGES, get_language, set_language

    previous = get_language()
    bad = []
    try:
        for lang in SUPPORTED_LANGUAGES:
            set_language(lang)
            for kind, kind_def in passives.PASSIVE_KINDS.items():
                args = {kwarg: "7" for kwarg, _p, _m in kind_def.l10n_args}
                from game.localization import t
                rendered = t(kind_def.l10n, **args)
                if rendered == kind_def.l10n:
                    bad.append(f"{lang}: no template for {kind}")
                    continue
                for kwarg in args:
                    if "7" not in rendered:
                        bad.append(f"{lang}: {kind} dropped {{{kwarg}}}")
                        break
    finally:
        set_language(previous)
    assert not bad, "\n".join(bad)


def test_fmt_amount_drops_a_pointless_decimal():
    assert passives.fmt_amount(0.02 * 100) == "2"
    assert passives.fmt_amount(2.5) == "2.5"
    assert passives.fmt_amount(10) == "10"


def test_marker_counts_only_active_passives(engine):
    """Grid stars mean effects the fighter actually gets — an item whose only
    slot is still locked shows no star, same as an item with none authored."""
    item = _weapon(engine, SLICE_ITEM)                     # +0: slot locked
    assert passives.passive_marker(item) == ""
    item["upgrade_level"] = passives.unlock_threshold(0)
    assert passives.passive_marker(item) == passives.PASSIVE_MARK
    assert passives.passive_marker(_bare_item()) == ""


def test_render_slots_shows_the_effect_on_a_locked_row_too(engine):
    """Below the threshold the card row still names the effect — a player
    deciding whether to spend upgrade materials needs to see what a slot pays
    out — with the locked template's +N appended so the row still reads as
    not active yet."""
    from game.localization import get_language, set_language

    previous = get_language()
    try:
        set_language("en")
        item = _weapon(engine, SLICE_ITEM)                 # +0: slot locked
        threshold = passives.unlock_threshold(0)
        rule = passives.render(passives.COMPILED_PASSIVES[SLICE_ITEM][0])

        rows = passives.render_slots(item)
        assert len(rows) == passives.slot_count(item) == 1
        text, unlocked, shown = rows[0]
        assert (unlocked, shown) == (False, threshold)
        assert f"+{threshold}" in text
        assert rule in text, "a locked row must still show the effect"

        item["upgrade_level"] = threshold
        rows = passives.render_slots(item)
        assert rows == [(f"{passives.PASSIVE_MARK} {rule}", True, threshold)]
    finally:
        set_language(previous)


def test_render_slots_locked_hole_stays_text_only(engine, extra_kinds):
    """A locked slot with no authored spec (a mid-patch hole) has no rule to
    show, so its row is the bare passive_slot_locked template, same as
    before this feature."""
    from game.localization import get_language, set_language, t

    previous = get_language()
    try:
        set_language("en")
        passives.install(
            {"w1#0": {"item": "w1", "kind": extra_kinds[0], "value": 0.01}},
            _slots())
        item = {"id": "w1", "rarity": "legendary", "upgrade_level": 0}
        rows = passives.render_slots(item)
        # slot #0 is authored but locked at +0: shows the rule; slots #1-4
        # are holes: bare locked text.
        threshold0 = passives.unlock_threshold(0)
        rule0 = passives.render(passives.COMPILED_PASSIVES["w1"][0])
        assert rows[0] == (f"{rule0} {t('passive_slot_locked', n=threshold0)}",
                            False, threshold0)
        for index in range(1, 5):
            threshold = passives.unlock_threshold(index)
            assert rows[index] == (t("passive_slot_locked", n=threshold),
                                    False, threshold)
    finally:
        engine._wire_data()
        set_language(previous)
    assert SLICE_ITEM in passives.COMPILED_PASSIVES, "restore path is broken"


def test_render_slots_orders_the_open_prefix_before_the_locked_tail(
        engine, extra_kinds):
    """A legendary two thresholds in has its first two slots active and the
    other three visible but locked, in slot order; the unlocked-only views
    (render_item, marker) agree with the same gate."""
    from game.localization import get_language, set_language

    previous = get_language()
    try:
        set_language("en")
        passives.install(
            {f"w1#{i}": {"item": "w1", "kind": extra_kinds[i], "value": 0.01}
             for i in range(5)},
            _slots())
        item = {"id": "w1", "rarity": "legendary",
                "upgrade_level": passives.unlock_threshold(1)}
        rows = passives.render_slots(item)
        assert [unlocked for _text, unlocked, _n in rows] == [
            True, True, False, False, False]
        assert [n for _text, _u, n in rows] == [
            passives.unlock_threshold(i) for i in range(5)]
        assert passives.unlocked_count(item) == 2
        assert passives.passive_marker(item) == passives.PASSIVE_MARK * 2
        assert passives.render_item(item) == [
            passives.render(spec)
            for spec in passives.COMPILED_PASSIVES["w1"][:2]]
    finally:
        engine._wire_data()
        set_language(previous)
    assert SLICE_ITEM in passives.COMPILED_PASSIVES, "restore path is broken"


def test_render_slots_is_empty_for_an_item_with_nothing_authored(engine):
    """No authored passives — no rarity-sized column of padlocks promising
    content the data does not have."""
    assert passives.render_slots(_bare_item()) == []


def test_locked_template_formats_where_authored():
    """en and ru carry passive_slot_locked (the i18n conveyor cascades it to
    the other languages); the {n} placeholder must survive formatting."""
    from game.localization import get_language, set_language, t

    previous = get_language()
    try:
        for lang in ("en", "ru"):
            set_language(lang)
            rendered = t("passive_slot_locked", n=7)
            assert rendered != "passive_slot_locked", f"{lang}: template missing"
            assert "+7" in rendered, f"{lang}: dropped the threshold"
    finally:
        set_language(previous)


def test_marker_glyph_exists_in_the_ui_font():
    """PixelFont (PressStart2P) is the default for the grid labels and does not
    carry ◆ or ⚠ — a marker it cannot render would ship as tofu."""
    fonttools = pytest.importorskip("fontTools.ttLib")
    font = fonttools.TTFont(os.path.join(ROOT, "fonts",
                                         "PressStart2P-Regular.ttf"),
                            fontNumber=0, lazy=True)
    covered = set()
    for table in font["cmap"].tables:
        covered |= set(table.cmap)
    assert ord(passives.PASSIVE_MARK) in covered


# ------------------------------------------------ content variety gate
#
# data/item_passives.json is monotonous today: several (source file, slot
# position) groups are dominated by one kind (e.g. weapon slot #4 is
# crit_damage_bonus in 70% of the weapons that have one), and several
# (kind, rarity) pairs repeat the same one or two numbers across a dozen
# items instead of being tuned per item. This gate is EXPECTED to fail until
# the content is re-authored — that is its job.
#
# Thresholds are picked to be strictly tighter than what the current data
# does, so the gate cannot pass by accident:
#   - a same-file, same-position monopoly at 26% (one kind past a clean
#     quarter of that group) must fail -> cap set at 25%.
#   - slot #0 is the one passive every single item carries, the widest
#     sample in the file, so its global cap is tighter still.
#   - an 11-item (kind, rarity) pair cycling through only 2 numbers (e.g.
#     crit_chance_bonus/rare in the shipped file today) must fail -> a pair
#     with enough samples needs at least 3 distinct values.
MIN_GROUP_SIZE_FOR_SLOT_CHECK = 8     # below this, one repeat is noise, not a trend
MAX_SLOT_KIND_SHARE_PER_FILE = 0.25   # >1/4 of one file's same-position items sharing a kind is a monopoly
MAX_SLOT0_KIND_SHARE_GLOBAL = 0.18    # slot #0's sample is every item, so its cap is stricter than the per-file one
MIN_PAIR_SIZE_FOR_VARIETY_CHECK = 6
MIN_DISTINCT_VALUES_PER_PAIR = 3      # fewer than this is a copy-pasted number, not a tuned one

SOURCE_DATA_FILES = {
    "weapon": "weapons.json",
    "armor": "armor.json",
    "accessory": "accessories.json",
    "relic": "relics.json",
}


def _item_catalog():
    """{item id: (slot id, rarity)}, read straight from the shipped per-slot
    data files — the only place that ties an id back to weapons vs armor vs
    accessories vs relics. Slot ids come from these files, not a guess: each
    file carries exactly one item["slot"] value for all its entries, and
    that value is the same id game/slots.py uses.
    """
    from game.slots import EQUIPMENT_SLOTS

    assert set(SOURCE_DATA_FILES) == set(EQUIPMENT_SLOTS), (
        "a slot was added to game/slots.py without adding its data file here")

    catalog = {}
    for slot_id, filename in SOURCE_DATA_FILES.items():
        path = os.path.join(ROOT, "data", filename)
        with open(path, encoding="utf-8") as handle:
            items = json.load(handle)["items"]
        for item in items:
            assert item["slot"] == slot_id, (
                f"{filename} has an item on slot {item['slot']!r}, expected "
                f"{slot_id!r}")
            catalog[item["id"]] = (slot_id, item["rarity"])
    return catalog


def _passive_entries():
    """[(slot id, rarity, slot position, kind, value), ...] for every entry
    in the shipped data/item_passives.json."""
    with open(DEFS_PATH, encoding="utf-8") as handle:
        raw = json.load(handle)["passives"]
    catalog = _item_catalog()

    entries = []
    for key, entry in raw.items():
        slot_id, rarity = catalog[entry["item"]]
        position = int(key.rsplit("#", 1)[1])
        entries.append((slot_id, rarity, position, entry["kind"], entry["value"]))
    return entries


def test_no_slot_kind_monopoly_per_file():
    """Within one item file, one passive position (#0, #1, ...) must not be
    dominated by a single kind — rerolling weapons should turn up more than
    one kind of slot-#0 passive."""
    groups = collections.defaultdict(collections.Counter)
    for slot_id, _rarity, position, kind, _value in _passive_entries():
        groups[(slot_id, position)][kind] += 1

    offenders = []
    for (slot_id, position), counter in sorted(groups.items()):
        total = sum(counter.values())
        if total < MIN_GROUP_SIZE_FOR_SLOT_CHECK:
            continue
        top_kind, top_count = counter.most_common(1)[0]
        share = top_count / total
        if share > MAX_SLOT_KIND_SHARE_PER_FILE:
            offenders.append(
                f"{slot_id} slot #{position}: {top_kind} is {top_count}/"
                f"{total} ({share:.0%}) > {MAX_SLOT_KIND_SHARE_PER_FILE:.0%}")
    assert not offenders, "\n".join(offenders)


def test_no_global_first_slot_kind_monopoly():
    """Slot #0 is authored on every item that has any passive at all, so its
    cap on one kind's share is tighter than the per-file check."""
    counter = collections.Counter(
        kind for _slot_id, _rarity, position, kind, _value
        in _passive_entries() if position == 0)
    total = sum(counter.values())
    top_kind, top_count = counter.most_common(1)[0]
    share = top_count / total
    assert share <= MAX_SLOT0_KIND_SHARE_GLOBAL, (
        f"slot #0: {top_kind} is {top_count}/{total} ({share:.0%}) > "
        f"{MAX_SLOT0_KIND_SHARE_GLOBAL:.0%}")


def test_kind_rarity_pairs_have_value_variety():
    """A (kind, rarity) pair repeated across many items should read as tuned
    per item, not copy-pasted — a pair with enough samples must use at least
    MIN_DISTINCT_VALUES_PER_PAIR different numbers."""
    values_by_pair = collections.defaultdict(list)
    for _slot_id, rarity, _position, kind, value in _passive_entries():
        values_by_pair[(kind, rarity)].append(value)

    offenders = []
    for (kind, rarity), values in sorted(values_by_pair.items()):
        if len(values) < MIN_PAIR_SIZE_FOR_VARIETY_CHECK:
            continue
        distinct = len(set(values))
        if distinct < MIN_DISTINCT_VALUES_PER_PAIR:
            offenders.append(
                f"{kind}/{rarity}: {len(values)} items share only {distinct} "
                f"distinct value(s) < {MIN_DISTINCT_VALUES_PER_PAIR}")
    assert not offenders, "\n".join(offenders)
