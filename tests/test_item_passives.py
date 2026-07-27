# Build: 1
"""Per-item passive effects — registry, compiler, wiring and remote patching.

The vertical slice this covers: a definition in data/item_passives.json becomes
a PassiveSpec, reaches Fighter.get_perk_effects through the equipped item, is
snapshotted by the battle stat cache, renders in every language, survives a
save round-trip without a migration, and can be renumbered by a remote patch
but never re-pointed at a different mechanic.
"""
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
    return {"w1": "weapon", "a1": "armor", "r1": "relic"}


def _compile(defs):
    return passives.compile_all(defs, _slots())


def test_compiles_a_well_formed_definition():
    out = _compile({"w1#0": {"item": "w1", "kind": "lifesteal_pct",
                             "value": 0.05}})
    assert list(out) == ["w1"]
    spec = out["w1"][0]
    assert spec.kind == "lifesteal_pct"
    assert spec.params == {"value": 0.05}
    assert dict(spec.static_effect) == {"type": "lifesteal_pct", "value": 0.05}


def test_specs_are_ordered_by_index_not_by_file_order():
    """The JSON is hand-authored; reordering it must not reorder dispatch."""
    out = _compile({
        "w1#2": {"item": "w1", "kind": "lifesteal_pct", "value": 0.03},
        "w1#0": {"item": "w1", "kind": "lifesteal_pct", "value": 0.01},
        "w1#1": {"item": "w1", "kind": "lifesteal_pct", "value": 0.02},
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


def test_per_item_cap_is_enforced():
    from game.constants import PASSIVE_MAX_PER_ITEM

    defs = {f"w1#{i}": {"item": "w1", "kind": "lifesteal_pct",
                        "value": 0.01 * (i + 1)}
            for i in range(PASSIVE_MAX_PER_ITEM + 2)}
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

    fighter.equipment["weapon"] = _weapon(engine, SLICE_ITEM)
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

    fighter.equipment["weapon"] = _weapon(engine, SLICE_ITEM)
    expected = passives.COMPILED_PASSIVES[SLICE_ITEM][0].params["value"]
    assert fighter.get_perk_effects("lifesteal_pct") == pytest.approx(
        perk_only + expected)


def test_battle_stat_cache_sees_the_item_passive(engine):
    """The snapshot in BattleManager._fighter_stats is what the on-hit heal
    actually reads — reaching get_perk_effects is not enough on its own."""
    from game.models import Fighter

    fighter = Fighter(name="Cached", fighter_class="mercenary")
    fighter.equipment["weapon"] = _weapon(engine, SLICE_ITEM)
    stats = engine.battle_mgr._fighter_stats(fighter)
    expected = passives.COMPILED_PASSIVES[SLICE_ITEM][0].params["value"]
    assert stats["lifesteal_pct"] == pytest.approx(expected)


def test_an_item_without_passives_changes_nothing(engine):
    from game.models import Fighter
    import game.models as models

    plain = next(item for item in models.FORGE_WEAPONS
                 if item["id"] not in passives.COMPILED_PASSIVES)
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


def test_marker_is_one_glyph_per_passive(engine):
    import game.models as models

    item = _weapon(engine, SLICE_ITEM)
    assert passives.passive_marker(item) == passives.PASSIVE_MARK
    plain = next(i for i in models.FORGE_WEAPONS
                 if i["id"] not in passives.COMPILED_PASSIVES)
    assert passives.passive_marker(plain) == ""


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
