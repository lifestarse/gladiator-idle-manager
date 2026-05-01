# Build: 3
"""One-line summarizers + helpers shared by editor widgets.

Editing model: control-flow nodes own their children directly. The editor
recursively renders nested BoxLayouts (no flatten step), and drag-and-drop
operates within a single body list. This keeps re-ordering predictable
and avoids the ambiguity of a flat representation with synthetic markers.
"""
from __future__ import annotations

from game.scripting.ast_nodes import (
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
)
from game.localization import t


def is_control(node) -> bool:
    return isinstance(node, (If, While, ForEach))


def summarize(node) -> str:
    """One-line human-readable summary of a node — for block card text."""
    if isinstance(node, If):
        return f"{t('scr_kw_if')} {expr_str(node.cond)}"
    if isinstance(node, While):
        return f"{t('scr_kw_while')} {expr_str(node.cond)}"
    if isinstance(node, ForEach):
        w = f" {t('scr_kw_where')} {expr_str(node.where)}" if node.where else ""
        return f"{t('scr_kw_foreach')} {node.var_name} {t('scr_kw_in')} {node.source}{w}"
    if isinstance(node, Assign):
        if node.target_kind == "local":
            return f"{node.name} := {expr_str(node.value)}"
        if node.target_kind == "global":
            return f"g.{node.name} := {expr_str(node.value)}"
        if node.target_kind == "fighter_field":
            return f"{expr_str(node.fighter)}.{node.name} := {expr_str(node.value)}"
    if isinstance(node, Action):
        args = ", ".join(expr_str(a) for a in node.args)
        return f"{node.name}({args})"
    if isinstance(node, Break):
        return t("scr_kw_break")
    if isinstance(node, Continue):
        return t("scr_kw_continue")
    return type(node).__name__


def expr_str(e) -> str:
    if e is None:
        return "?"
    if isinstance(e, Const):
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
        return f"{expr_str(e.fighter)}.{e.field_name}"
    if isinstance(e, EngineField):
        return f"engine.{e.field_name}"
    if isinstance(e, BinOp):
        return f"({expr_str(e.lhs)} {e.op} {expr_str(e.rhs)})"
    if isinstance(e, UnaryOp):
        return f"({e.op} {expr_str(e.operand)})"
    if isinstance(e, Call):
        return f"{e.name}(" + ", ".join(expr_str(a) for a in e.args) + ")"
    return type(e).__name__
