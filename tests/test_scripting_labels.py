# Build: 1
"""Label / i18n parity tests for the scripting subsystem.

Every internal name surfaced in the UI (action, trigger, fighter field,
engine field, operator, foreach source, call, slot, fighter class, template)
must:

  * have an entry in ``game.scripting.labels`` mapping it to an i18n key
  * have that i18n key actually present in both ``ru.json`` and ``en.json``
  * (for ACTION_META) have a matching arg_labels length to BUILTIN_ACTIONS' nargs_min

Without this test, adding a new action and forgetting to add a Russian
translation would surface only as a UI button labelled "scr_act_foo" — easy
to miss in code review, embarrassing in production.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

import pytest

from game.scripting import labels as L
from game.scripting.builtins import (
    BUILTIN_ACTIONS, BUILTIN_FIELDS, BUILTIN_ENGINE_FIELDS, BUILTIN_CALLS,
)
from game.scripting.ast_nodes import (
    Trigger, BIN_OPS, UNARY_OPS, ITERABLE_SOURCES,
)
from game.scripting.templates import TEMPLATES


# ---------- load both language JSONs once ----------

REPO_ROOT = Path(__file__).resolve().parents[1]
LANG_DIR = REPO_ROOT / "data" / "languages"


def _load_lang(code: str) -> dict:
    with open(LANG_DIR / f"{code}.json", encoding="utf-8") as f:
        return json.load(f)


EN = _load_lang("en")
RU = _load_lang("ru")


def _exists(key: str) -> tuple[bool, bool]:
    return (key in EN, key in RU)


def _assert_key(key: str, where: str):
    en, ru = _exists(key)
    assert en, f"{where}: i18n key {key!r} missing in en.json"
    assert ru, f"{where}: i18n key {key!r} missing in ru.json"


# ---------- triggers ----------

@pytest.mark.parametrize("trig", list(Trigger.ALL))
def test_trigger_has_label(trig):
    key = L.TRIGGER_LABELS.get(trig)
    assert key, f"trigger {trig!r} has no entry in TRIGGER_LABELS"
    _assert_key(key, f"trigger {trig}")


# ---------- actions ----------

@pytest.mark.parametrize("name", sorted(BUILTIN_ACTIONS.keys()))
def test_action_has_meta(name):
    meta = L.ACTION_META.get(name)
    assert meta, f"action {name!r} has no entry in ACTION_META"
    _assert_key(meta["label"], f"action {name}.label")
    _assert_key(meta["desc"], f"action {name}.desc")
    assert meta["cat"] in {c[0] for c in L.ACTION_CATEGORIES}, (
        f"action {name!r} category {meta['cat']!r} not in ACTION_CATEGORIES"
    )


@pytest.mark.parametrize("name", sorted(BUILTIN_ACTIONS.keys()))
def test_action_arg_labels_match_spec(name):
    """Each action's arg_labels in ACTION_META must align with nargs_min in
    BUILTIN_ACTIONS — otherwise the inline editor either over-builds widgets
    for missing args or under-builds and the user can't see required slots."""
    spec = BUILTIN_ACTIONS[name]
    meta = L.ACTION_META[name]
    amin, amax = spec["args"]
    arg_labels = meta.get("arg_labels", [])
    assert len(arg_labels) == amin, (
        f"action {name!r}: arg_labels has {len(arg_labels)} entries, "
        f"but BUILTIN_ACTIONS expects nargs_min={amin}"
    )
    # Each non-None label must be a valid i18n key
    for i, key in enumerate(arg_labels):
        if key is None:
            continue
        _assert_key(key, f"action {name}.arg_labels[{i}]")


@pytest.mark.parametrize("cat_id,cat_key", list(L.ACTION_CATEGORIES))
def test_action_categories(cat_id, cat_key):
    _assert_key(cat_key, f"action category {cat_id}")


# ---------- fighter fields ----------

@pytest.mark.parametrize("field", sorted(BUILTIN_FIELDS.keys()))
def test_fighter_field_has_label(field):
    key = L.FIGHTER_FIELD_LABELS.get(field)
    assert key, f"fighter field {field!r} has no entry in FIGHTER_FIELD_LABELS"
    _assert_key(key, f"fighter field {field}")


# ---------- engine fields ----------

@pytest.mark.parametrize("field", sorted(BUILTIN_ENGINE_FIELDS))
def test_engine_field_has_label(field):
    key = L.ENGINE_FIELD_LABELS.get(field)
    assert key, f"engine field {field!r} has no entry in ENGINE_FIELD_LABELS"
    _assert_key(key, f"engine field {field}")


# ---------- operators ----------

@pytest.mark.parametrize("op", sorted(BIN_OPS))
def test_bin_op_has_label(op):
    key = L.OP_LABELS.get(op)
    assert key, f"binary op {op!r} has no entry in OP_LABELS"
    _assert_key(key, f"binary op {op}")


@pytest.mark.parametrize("op", sorted(UNARY_OPS))
def test_unary_op_has_label(op):
    key = L.UNARY_OP_LABELS.get(op)
    assert key, f"unary op {op!r} has no entry in UNARY_OP_LABELS"
    _assert_key(key, f"unary op {op}")


# ---------- sources ----------

@pytest.mark.parametrize("src", list(ITERABLE_SOURCES))
def test_source_has_label(src):
    key = L.SOURCE_LABELS.get(src)
    assert key, f"foreach source {src!r} has no entry in SOURCE_LABELS"
    _assert_key(key, f"foreach source {src}")
    assert src in L.SOURCE_ORDER, f"foreach source {src!r} missing from SOURCE_ORDER"


# ---------- calls ----------

@pytest.mark.parametrize("call_name", sorted(BUILTIN_CALLS.keys()))
def test_call_has_label(call_name):
    key = L.CALL_LABELS.get(call_name)
    assert key, f"call {call_name!r} has no entry in CALL_LABELS"
    _assert_key(key, f"call {call_name}")


# ---------- enums (slot / class) ----------

def test_slot_options_have_labels():
    for slot in L.SLOT_OPTIONS:
        key = L.SLOT_LABELS.get(slot)
        assert key, f"slot {slot!r} has no entry in SLOT_LABELS"
        _assert_key(key, f"slot {slot}")


def test_class_options_have_labels():
    for cls in L.CLASS_OPTIONS:
        key = L.CLASS_LABELS.get(cls)
        assert key, f"class {cls!r} has no entry in CLASS_LABELS"
        _assert_key(key, f"class {cls}")


# ---------- templates ----------

@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.id)
def test_template_has_localized_labels(tmpl):
    _assert_key(tmpl.name_key, f"template {tmpl.id}.name_key")
    _assert_key(tmpl.desc_key, f"template {tmpl.id}.desc_key")


# ---------- visual category map ----------

def test_category_colors_cover_all_node_kinds():
    needed = {"control", "flow", "assign", "action", "value", "trigger"}
    assert needed <= L.CATEGORY_COLORS.keys(), (
        f"CATEGORY_COLORS missing: {needed - L.CATEGORY_COLORS.keys()}"
    )


# ---------- arg vocabulary sanity ----------

def test_arg_vocabularies_reference_real_actions():
    for (action_name, arg_idx) in L.ARG_VOCABULARIES.keys():
        assert action_name in BUILTIN_ACTIONS, (
            f"ARG_VOCABULARIES references unknown action {action_name!r}"
        )
        # The arg_idx must be within nargs_min for that action
        spec = BUILTIN_ACTIONS[action_name]
        amin, _amax = spec["args"]
        assert 0 <= arg_idx < amin, (
            f"ARG_VOCABULARIES[{action_name}].arg{arg_idx} is out of range "
            f"(nargs_min={amin})"
        )
