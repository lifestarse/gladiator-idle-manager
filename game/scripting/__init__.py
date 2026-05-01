# Build: 1
"""Squad scripting subsystem.

Visual block-based mini-language for automating gladiator management,
arena battles and expeditions. Programs are stored as nested AST,
executed by `Interpreter` against a live `engine` context.

Public API:
    Program, Trigger          — program definition & trigger enum
    Interpreter, ScriptError  — execution engine
    ScriptManager             — collection + persistence + trigger dispatch
    BUILTIN_ACTIONS, BUILTIN_FIELDS — registries
"""
from .ast_nodes import (
    Program, Trigger,
    Node, Statement, Expression,
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
    node_to_dict, node_from_dict,
)
from .interpreter import Interpreter, ScriptError, BreakSignal, ContinueSignal
from .builtins import BUILTIN_ACTIONS, BUILTIN_FIELDS, BUILTIN_CALLS
from .manager import ScriptManager

__all__ = [
    "Program", "Trigger",
    "Node", "Statement", "Expression",
    "If", "While", "ForEach", "Assign", "Action", "Break", "Continue",
    "BinOp", "UnaryOp", "Const", "LocalVar", "GlobalVar",
    "FighterField", "EngineField", "Call",
    "node_to_dict", "node_from_dict",
    "Interpreter", "ScriptError", "BreakSignal", "ContinueSignal",
    "BUILTIN_ACTIONS", "BUILTIN_FIELDS", "BUILTIN_CALLS",
    "ScriptManager",
]
