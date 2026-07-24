# Build: 1
"""Interpreter expression evaluators (`_eval_*`) — one method per Expression node."""
from __future__ import annotations

from . import ast_nodes as ast
from .builtins import BUILTIN_FIELDS, BUILTIN_ENGINE_FIELDS, BUILTIN_CALLS
from .errors import ScriptError


class _InterpreterEvalMixin:
    def _eval_Const(self, node: ast.Const):
        return node.value

    def _eval_LocalVar(self, node: ast.LocalVar):
        if node.name not in self.locals:
            raise ScriptError(f"local variable {node.name!r} is not defined")
        return self.locals[node.name]

    def _eval_GlobalVar(self, node: ast.GlobalVar):
        return self.g_vars.get(node.name, 0)

    def _eval_FighterField(self, node: ast.FighterField):
        fighter = self._eval(node.fighter)
        if fighter is None:
            return None
        accessor = BUILTIN_FIELDS.get(node.field_name)
        if accessor is None:
            raise ScriptError(f"unknown fighter field: {node.field_name!r}")
        try:
            return accessor(fighter)
        except Exception as e:
            raise ScriptError(f"reading fighter.{node.field_name} failed: {e}") from e

    def _eval_EngineField(self, node: ast.EngineField):
        if node.field_name not in BUILTIN_ENGINE_FIELDS:
            raise ScriptError(f"unknown engine field: {node.field_name!r}")
        try:
            from .builtins import _engine_field
            return _engine_field(self.engine, node.field_name)
        except AttributeError:
            return 0  # field not present on this engine version
        except Exception as e:
            raise ScriptError(f"reading engine.{node.field_name} failed: {e}") from e

    def _eval_BinOp(self, node: ast.BinOp):
        op = node.op
        if op == "and":
            return self._truthy(self._eval(node.lhs)) and self._truthy(self._eval(node.rhs))
        if op == "or":
            return self._truthy(self._eval(node.lhs)) or self._truthy(self._eval(node.rhs))
        lhs = self._eval(node.lhs)
        rhs = self._eval(node.rhs)
        try:
            if op == "+":  return lhs + rhs
            if op == "-":  return lhs - rhs
            if op == "*":  return lhs * rhs
            if op == "/":
                if rhs == 0: raise ScriptError("division by zero")
                return lhs / rhs
            if op == "%":
                if rhs == 0: raise ScriptError("modulo by zero")
                return lhs % rhs
            if op == "==": return lhs == rhs
            if op == "!=": return lhs != rhs
            if op == "<":  return lhs < rhs
            if op == "<=": return lhs <= rhs
            if op == ">":  return lhs > rhs
            if op == ">=": return lhs >= rhs
        except ScriptError:
            raise
        except Exception as e:
            raise ScriptError(f"binary {op} failed: {e}") from e
        raise ScriptError(f"unknown binary op: {op}")

    def _eval_UnaryOp(self, node: ast.UnaryOp):
        v = self._eval(node.operand)
        if node.op == "not": return not self._truthy(v)
        if node.op == "-":   return -v
        raise ScriptError(f"unknown unary op: {node.op}")

    def _eval_Call(self, node: ast.Call):
        fn = BUILTIN_CALLS.get(node.name)
        if fn is None:
            raise ScriptError(f"unknown call: {node.name!r}")
        args = [self._eval(a) for a in node.args]
        try:
            return fn(args)
        except ScriptError:
            raise
        except Exception as e:
            raise ScriptError(f"call {node.name!r} failed: {e}") from e
