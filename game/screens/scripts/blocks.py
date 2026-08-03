# Build: 5
"""One-line summarizers + helpers shared by editor widgets.

Editing model: control-flow nodes own their children directly. The editor
recursively renders nested BoxLayouts (no flatten step), and drag-and-drop
operates within a single body list. This keeps re-ordering predictable
and avoids the ambiguity of a flat representation with synthetic markers.

Both ``summarize`` and ``expr_str`` route every user-visible token (action
names, field names, operator symbols, source names) through
:mod:`game.scripting.labels` + ``t()`` so the editor reads like Russian /
English instead of like raw AST identifiers.
"""
from __future__ import annotations

from game.scripting.ast_nodes import (
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
    WRITABLE_FIGHTER_FIELDS,
)
from game.scripting import labels as L
from game.localization import t


def is_control(node) -> bool:
    return isinstance(node, (If, While, ForEach))


def default_writable_fighter_field() -> str:
    """The field a fresh ``SET f.<field>`` block targets.

    Read off the AST whitelist rather than named here: ``Assign.__post_init__``
    rejects anything outside WRITABLE_FIGHTER_FIELDS, so a hardcoded name turns
    every narrowing of that whitelist into a ValueError thrown into the UI at
    the moment the user taps the palette entry. Sorted so the choice is stable
    across runs instead of following set iteration order.
    """
    fields = sorted(WRITABLE_FIGHTER_FIELDS)
    if not fields:
        raise ValueError("no writable fighter fields — SET f.<field> is unavailable")
    return fields[0]


def _action_label(name: str) -> str:
    meta = L.ACTION_META.get(name)
    return t(meta["label"]) if meta else name


def _fighter_field_label(field: str) -> str:
    key = L.FIGHTER_FIELD_LABELS.get(field)
    return t(key) if key else field


def _engine_field_label(field: str) -> str:
    key = L.ENGINE_FIELD_LABELS.get(field)
    return t(key) if key else field


def _source_label(src: str) -> str:
    key = L.SOURCE_LABELS.get(src)
    return t(key) if key else src


def _op_symbol(op: str) -> str:
    key = L.OP_LABELS.get(op)
    return t(key) if key else op


def _unary_symbol(op: str) -> str:
    key = L.UNARY_OP_LABELS.get(op)
    return t(key) if key else op


def _call_label(name: str) -> str:
    key = L.CALL_LABELS.get(name)
    return t(key) if key else name


def summarize(node) -> str:
    """One-line human-readable summary of a node — for block card text."""
    if isinstance(node, If):
        return f"{t('scr_kw_if')} {expr_str(node.cond)}"
    if isinstance(node, While):
        return f"{t('scr_kw_while')} {expr_str(node.cond)}"
    if isinstance(node, ForEach):
        w = f" {t('scr_kw_where')} {expr_str(node.where)}" if node.where else ""
        return (f"{t('scr_kw_foreach')} {node.var_name} "
                f"{t('scr_kw_in')} {_source_label(node.source)}{w}")
    if isinstance(node, Assign):
        if node.target_kind == "local":
            return f"{node.name} := {expr_str(node.value)}"
        if node.target_kind == "global":
            return f"g.{node.name} := {expr_str(node.value)}"
        if node.target_kind == "fighter_field":
            return (f"{expr_str(node.fighter)}.{_fighter_field_label(node.name)} "
                    f":= {expr_str(node.value)}")
    if isinstance(node, Action):
        args = ", ".join(expr_str(a) for a in node.args)
        return f"{_action_label(node.name)}({args})"
    if isinstance(node, Break):
        return t("scr_kw_break")
    if isinstance(node, Continue):
        return t("scr_kw_continue")
    return type(node).__name__


def expr_str(e) -> str:
    if e is None:
        return "?"
    if isinstance(e, Const):
        if isinstance(e.value, bool):
            # PixelFont doesn't carry the ✓/✗ glyphs — they render as "?"
            # boxes. Localised plain-text via i18n keeps the summary
            # readable in both English and Russian.
            return t("scr_yes") if e.value else t("scr_no")
        if isinstance(e.value, str):
            return f'"{e.value}"'
        if e.value is None:
            return t("scr_kw_none")
        return str(e.value)
    if isinstance(e, LocalVar):
        return e.name
    if isinstance(e, GlobalVar):
        return f"g.{e.name}"
    if isinstance(e, FighterField):
        return f"{expr_str(e.fighter)}.{_fighter_field_label(e.field_name)}"
    if isinstance(e, EngineField):
        return _engine_field_label(e.field_name)
    if isinstance(e, BinOp):
        return f"({expr_str(e.lhs)} {_op_symbol(e.op)} {expr_str(e.rhs)})"
    if isinstance(e, UnaryOp):
        return f"({_unary_symbol(e.op)} {expr_str(e.operand)})"
    if isinstance(e, Call):
        return f"{_call_label(e.name)}(" + ", ".join(expr_str(a) for a in e.args) + ")"
    return type(e).__name__
