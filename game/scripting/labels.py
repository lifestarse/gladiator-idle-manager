# Build: 2
"""Display metadata for AST entities — labels, descriptions, categories, colors.

The AST itself keeps stable internal names (``bench``, ``activate``, ``hp``,
``fatigue``, ``on_battle_end``, …). This module is a pure-data layer mapping
those internal names to i18n keys and visual hints used by the UI. Saved
programs only reference the internal names; nothing in this file is ever
serialised into a save.

Anything the UI wants to show to the user goes through here — that way the
moment a new action/field/operator is added in :mod:`game.scripting.builtins`
or :mod:`game.scripting.ast_nodes`, the only places that need to learn about
it are this file and the two language JSONs.
"""
from __future__ import annotations

from .builtins import BUILTIN_ENGINE_FIELDS


# ---------- triggers ----------

TRIGGER_LABELS: dict[str, str] = {
    "on_battle_end": "scr_trig_battle_end",
    "on_tick":       "scr_trig_tick",
    "on_demand":     "scr_trig_demand",
}

# Stable ordering for trigger pickers.
TRIGGER_ORDER = ("on_battle_end", "on_tick", "on_demand")


# ---------- side-effect actions ----------

# Each entry:
#   label      — i18n key for the short button text shown in palette/cards
#   desc       — i18n key for the one-line description in the picker
#   cat        — palette category ("roster" | "forge" | "battle" | "misc")
#   arg_labels — list of i18n keys (or None) describing each positional arg;
#                length must match the action's nargs_min in BUILTIN_ACTIONS.
#                ``None`` means "this slot is the implicit fighter (LocalVar f)
#                and the UI should not draw a label for it".
#   available  — False if BUILTIN_ACTIONS' callable is a silent no-op on the
#                current engine build (the matching engine.<method> is absent
#                or doesn't actually wire to game state). The palette shows
#                a "(no-op on current build)" tag next to these so the user
#                doesn't pick them and then wonder why nothing happens. The
#                interpreter still accepts them — they just do nothing.
#                Default: True (omitted means available).
ACTION_META: dict[str, dict] = {
    "bench":              {"label": "scr_act_bench",              "desc": "scr_act_bench_d",
                           "cat": "roster", "arg_labels": [None]},
    "activate":           {"label": "scr_act_activate",           "desc": "scr_act_activate_d",
                           "cat": "roster", "arg_labels": [None]},
    "rest":               {"label": "scr_act_rest",                "desc": "scr_act_rest_d",
                           "cat": "roster", "arg_labels": [None]},
    "unequip_all":        {"label": "scr_act_unequip_all",        "desc": "scr_act_unequip_all_d",
                           "cat": "forge",  "arg_labels": [None]},
    "unequip_slot":       {"label": "scr_act_unequip_slot",       "desc": "scr_act_unequip_slot_d",
                           "cat": "forge",  "arg_labels": [None, "scr_arg_slot"]},
    "start_arena_battle": {"label": "scr_act_start_arena",        "desc": "scr_act_start_arena_d",
                           "cat": "battle", "arg_labels": []},
    "stop_arena_battle":  {"label": "scr_act_stop_arena",         "desc": "scr_act_stop_arena_d",
                           "cat": "battle", "arg_labels": []},
    "start_expedition":   {"label": "scr_act_start_exp",          "desc": "scr_act_start_exp_d",
                           "cat": "battle", "arg_labels": ["scr_arg_tier"]},
    "stop_expedition":    {"label": "scr_act_stop_exp",           "desc": "scr_act_stop_exp_d",
                           "cat": "battle", "arg_labels": []},
    "spawn_boss":         {"label": "scr_act_spawn_boss",         "desc": "scr_act_spawn_boss_d",
                           "cat": "battle", "arg_labels": []},
    "log":                {"label": "scr_act_log",                "desc": "scr_act_log_d",
                           "cat": "misc",   "arg_labels": ["scr_arg_message"]},
    "buy_item":           {"label": "scr_act_buy_item",           "desc": "scr_act_buy_item_d",
                           "cat": "forge",  "arg_labels": ["scr_arg_slot"]},
    "buy_best":           {"label": "scr_act_buy_best",           "desc": "scr_act_buy_best_d",
                           "cat": "forge",  "arg_labels": ["scr_arg_slot"]},
    "equip_best":         {"label": "scr_act_equip_best",         "desc": "scr_act_equip_best_d",
                           "cat": "forge",  "arg_labels": [None, "scr_arg_slot"]},
    "forge_upgrade":      {"label": "scr_act_forge_upgrade",      "desc": "scr_act_forge_upgrade_d",
                           "cat": "forge",  "arg_labels": [None, "scr_arg_slot"]},
    "hire":               {"label": "scr_act_hire",               "desc": "scr_act_hire_d",
                           "cat": "roster", "arg_labels": ["scr_arg_class"]},
    "train_to":           {"label": "scr_act_train_to",           "desc": "scr_act_train_to_d",
                           "cat": "roster", "arg_labels": [None, "scr_arg_level"]},
    "give_item":          {"label": "scr_act_give_item",          "desc": "scr_act_give_item_d",
                           "cat": "forge",  "arg_labels": [None, "scr_arg_item_id"]},
}


def is_action_available(name: str) -> bool:
    """True if the named action does real work on the current engine build."""
    meta = ACTION_META.get(name)
    if meta is None:
        return False
    return meta.get("available", True)

# Order in which action categories are listed in the palette.
ACTION_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("roster", "scr_cat_roster"),
    ("forge",  "scr_cat_forge"),
    ("battle", "scr_cat_battle"),
    ("misc",   "scr_cat_misc"),
)


# ---------- fighter and engine fields ----------

FIGHTER_FIELD_LABELS: dict[str, str] = {
    "hp":             "scr_f_hp",
    "max_hp":         "scr_f_max_hp",
    "hp_pct":         "scr_f_hp_pct",
    "fatigue":        "scr_f_fatigue",
    "stamina":        "scr_f_stamina",
    "level":          "scr_f_level",
    "strength":       "scr_f_strength",
    "agility":        "scr_f_agility",
    "vitality":       "scr_f_vitality",
    "is_active":      "scr_f_is_active",
    "is_exhausted":   "scr_f_is_exhausted",
    "available":      "scr_f_available",
    "alive":          "scr_f_alive",
    "has_any_injury": "scr_f_has_injury",
    "has_weapon":     "scr_f_has_weapon",
    "has_armor":      "scr_f_has_armor",
    "has_accessory":  "scr_f_has_accessory",
    "has_relic":      "scr_f_has_relic",
    "name":           "scr_f_name",
    "fighter_class":  "scr_f_class",
}

# Fields that return numbers — used by the expression-picker to auto-wrap
# them in a BinOp(">=", field, Const(0)) when the user picks one as the
# entire condition of an IF / WHILE. Without this users would pick
# "Stamina" expecting "stamina > 50", get just "f.stamina" (an integer
# truthy-evaluated to always-true), and have to dig into the "Compare /
# Calc" category to wrap it — a 6+-tap detour for the most common case.
# Boolean / string fields (alive, has_weapon, name, ...) are NOT in this
# set so they stay as-is: `if f.alive:` is perfectly valid.
NUMERIC_FIGHTER_FIELDS = frozenset({
    "hp", "max_hp", "hp_pct",
    "fatigue", "stamina",
    "level", "strength", "agility", "vitality",
})


# Same idea as NUMERIC_FIGHTER_FIELDS but for engine fields, except the
# engine vocabulary is small enough to name the exceptions instead of the
# rule: everything in BUILTIN_ENGINE_FIELDS reads as a number apart from
# these two bools, which stay out so `if engine.battle_active:` keeps
# working. Listing the bools rather than the numbers means a new numeric
# field added to the registry gets the auto-wrap for free.
BOOLEAN_ENGINE_FIELDS = frozenset({"battle_active", "expedition_active"})

NUMERIC_ENGINE_FIELDS = frozenset(BUILTIN_ENGINE_FIELDS) - BOOLEAN_ENGINE_FIELDS


# Every key of BUILTIN_ENGINE_FIELDS needs an entry here; the i18n keys are
# not derivable from the field names (current_tier -> scr_e_tier), so the
# parity is enforced by tests/test_scripting_labels.py instead.
ENGINE_FIELD_LABELS: dict[str, str] = {
    "gold":              "scr_e_gold",
    "diamonds":          "scr_e_diamonds",
    "victories":         "scr_e_victories",
    "current_tier":      "scr_e_tier",
    "battle_active":     "scr_e_battle_active",
    "expedition_active": "scr_e_exp_active",
    "fighter_count":     "scr_e_fighter_count",
    "active_count":      "scr_e_active_count",
    "available_count":   "scr_e_available_count",
    "current_floor":     "scr_e_current_floor",
    "inventory_size":    "scr_e_inv_size",
    "inv_weapons":       "scr_e_inv_weapons",
    "inv_armor":         "scr_e_inv_armor",
    "inv_accessories":   "scr_e_inv_accessories",
    "inv_relics":        "scr_e_inv_relics",
}


# ---------- operators ----------

# UI symbol for each binary operator. Plain ASCII for ASCII ops, Unicode for the
# few that benefit from it (≠, ≤, ≥, ×, ÷). i18n keys carry the LOCALISED words
# (AND/OR translate to И/ИЛИ).
OP_LABELS: dict[str, str] = {
    "==":  "scr_op_eq",
    "!=":  "scr_op_neq",
    "<":   "scr_op_lt",
    "<=":  "scr_op_le",
    ">":   "scr_op_gt",
    ">=":  "scr_op_ge",
    "+":   "scr_op_plus",
    "-":   "scr_op_minus",
    "*":   "scr_op_mul",
    "/":   "scr_op_div",
    "%":   "scr_op_mod",
    "and": "scr_op_and",
    "or":  "scr_op_or",
}

# Ordering: comparisons first (most common in conditions), then arithmetic,
# then boolean. Matches the spinner picker order.
OP_ORDER = ("==", "!=", "<", "<=", ">", ">=", "+", "-", "*", "/", "%", "and", "or")

UNARY_OP_LABELS: dict[str, str] = {
    "not": "scr_uop_not",
    "-":   "scr_uop_neg",
}


# ---------- foreach sources ----------

SOURCE_LABELS: dict[str, str] = {
    "fighters":  "scr_src_fighters",
    "active":    "scr_src_active",
    "benched":   "scr_src_benched",
    "available": "scr_src_available",
    "exhausted": "scr_src_exhausted",
}

SOURCE_ORDER = ("fighters", "active", "benched", "available", "exhausted")


# ---------- value-returning calls ----------

CALL_LABELS: dict[str, str] = {
    "len": "scr_call_len",
    "min": "scr_call_min",
    "max": "scr_call_max",
    "abs": "scr_call_abs",
}


# ---------- enum-like arg vocabularies ----------

# Order is also the order shown in the inline picker.
SLOT_OPTIONS = ("weapon", "armor", "accessory", "relic")
# Subset of SLOT_OPTIONS without relic — used by the buy_* actions because
# relics aren't sold in the forge; they only drop from expeditions. Picker
# wouldn't have a single item to offer for slot="relic", so showing it
# would just be a trap. Other actions (unequip / equip_best / forge_upgrade)
# legitimately deal with already-equipped relics and keep the full set.
BUYABLE_SLOT_OPTIONS = ("weapon", "armor", "accessory")
SLOT_LABELS: dict[str, str] = {
    "weapon":    "scr_slot_weapon",
    "armor":     "scr_slot_armor",
    "accessory": "scr_slot_accessory",
    "relic":     "scr_slot_relic",
}

CLASS_OPTIONS = ("mercenary", "assassin", "tank", "berserker", "retiarius", "medicus")
CLASS_LABELS: dict[str, str] = {
    "mercenary": "scr_class_mercenary",
    "assassin":  "scr_class_assassin",
    "tank":      "scr_class_tank",
    "berserker": "scr_class_berserker",
    "retiarius": "scr_class_retiarius",
    "medicus":   "scr_class_medicus",
}


# ---------- Scratch-style category colours (no two warm hues adjacent) ----------

# Used by the editor to colour block cards and palette pills. The category
# itself is derived from the AST node type by :func:`category_of`.
CATEGORY_COLORS: dict[str, tuple[float, float, float, float]] = {
    "trigger": (1.00, 0.80, 0.15, 1),   # warm yellow — events
    "control": (0.30, 0.55, 0.95, 1),   # blue — if/while/for
    "flow":    (0.55, 0.55, 0.65, 1),   # gray — break/continue
    "assign":  (0.30, 0.75, 0.45, 1),   # green — set vars
    "action":  (0.65, 0.40, 0.85, 1),   # purple — side effects
    "value":   (0.60, 0.70, 0.80, 1),   # cool gray — const/var/field reads
}


def category_of(node) -> str:
    """Return the visual category key for an AST node.

    Uses string-level isinstance via class name to avoid importing ast_nodes
    here (keeps this module pure data — no circular import risk for the UI
    layer that imports both this module and the AST).
    """
    cn = type(node).__name__
    if cn in ("If", "While", "ForEach"):
        return "control"
    if cn in ("Break", "Continue"):
        return "flow"
    if cn == "Assign":
        return "assign"
    if cn == "Action":
        return "action"
    return "value"


# ---------- arg-vocabulary helper ----------

# When an action expects a slot/class/etc. as one of its args, the inline editor
# needs to know "this arg position is an enum picker, not a free expression."
# Reading this from ACTION_META + arg_labels works for simple cases; for
# multi-arg actions we still need to map arg-position → vocabulary.
ARG_VOCABULARIES: dict[tuple[str, int], tuple[str, ...]] = {
    # action_name, arg_index (0-based) → enum options tuple
    ("unequip_slot",   1): SLOT_OPTIONS,
    ("buy_item",       0): BUYABLE_SLOT_OPTIONS,   # no relic — not sold
    ("buy_best",       0): BUYABLE_SLOT_OPTIONS,
    ("equip_best",     1): SLOT_OPTIONS,
    ("forge_upgrade",  1): SLOT_OPTIONS,
    ("hire",           0): CLASS_OPTIONS,
}


def vocab_label_for(action_name: str, arg_index: int, value: str) -> str | None:
    """Return the i18n key for an enum value, or None if no vocabulary applies."""
    vocab = ARG_VOCABULARIES.get((action_name, arg_index))
    if not vocab or value not in vocab:
        return None
    if vocab is SLOT_OPTIONS:
        return SLOT_LABELS.get(value)
    if vocab is CLASS_OPTIONS:
        return CLASS_LABELS.get(value)
    return None
