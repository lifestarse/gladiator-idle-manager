# Build: 1
"""Tree-walking interpreter for the squad scripting language.

Safety limits (configurable via constructor):
    max_steps       — total node executions (default 5000).
    max_loop_iters  — single while/foreach iteration cap (default 1000).
    max_loop_depth  — nesting depth of loops (default 10).

Exceptions:
    ScriptError — wraps any runtime failure with the originating node kind.
    BreakSignal / ContinueSignal — internal control-flow.
"""
from __future__ import annotations
from typing import Any

from . import ast_nodes as ast
from .builtins import (
    BUILTIN_FIELDS, BUILTIN_ENGINE_FIELDS, BUILTIN_CALLS, BUILTIN_ACTIONS,
)


class ScriptError(Exception):
    pass


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


class Interpreter:
    def __init__(
        self,
        engine,
        program: ast.Program,
        g_vars: dict | None = None,
        *,
        max_steps: int = 5000,
        max_loop_iters: int = 1000,
        max_loop_depth: int = 10,
    ):
        self.engine = engine
        self.program = program
        self.g_vars = g_vars if g_vars is not None else {}
        self.locals: dict[str, Any] = {}
        self.steps = 0
        self.loop_depth = 0
        # Number of side-effect actions that actually fired during this run.
        # Surfaced via ScriptManager.last_runs for the editor's "Run log" panel
        # so the user can verify "yes, something happened" without having to
        # cross-check gold/inventory numbers manually.
        self.actions_fired = 0
        self.max_steps = max_steps
        self.max_loop_iters = max_loop_iters
        self.max_loop_depth = max_loop_depth

    # ---------- public ----------

    def run(self) -> None:
        for k, v in self.program.g_var_init.items():
            self.g_vars.setdefault(k, v)
        try:
            self._exec_body(self.program.body)
        except BreakSignal:
            raise ScriptError("`break` outside of loop")
        except ContinueSignal:
            raise ScriptError("`continue` outside of loop")

    # ---------- core execution ----------

    def _tick(self):
        self.steps += 1
        # max_steps == 0 disables the global cap — used by force-runs from
        # the Scripts editor where the user has explicitly asked for a
        # long-running while loop (e.g. "farm until 500k gold"). The
        # per-loop cap below has the same opt-out.
        if self.max_steps > 0 and self.steps > self.max_steps:
            raise ScriptError(f"step limit exceeded ({self.max_steps})")

    def _exec_body(self, stmts):
        for s in stmts:
            self._exec(s)

    def _exec(self, node):
        self._tick()
        cls = type(node).__name__
        method = getattr(self, f"_exec_{cls}", None)
        if method is None:
            raise ScriptError(f"cannot execute node {cls}")
        method(node)

    def _eval(self, node):
        self._tick()
        cls = type(node).__name__
        method = getattr(self, f"_eval_{cls}", None)
        if method is None:
            raise ScriptError(f"cannot evaluate node {cls}")
        return method(node)

    # ---------- statements ----------

    def _exec_If(self, node: ast.If):
        if self._truthy(self._eval(node.cond)):
            self._exec_body(node.then_body)
        else:
            self._exec_body(node.else_body)

    def _exec_While(self, node: ast.While):
        if self.loop_depth >= self.max_loop_depth:
            raise ScriptError(f"loop nesting depth exceeded ({self.max_loop_depth})")
        self.loop_depth += 1
        try:
            iters = 0
            while self._truthy(self._eval(node.cond)):
                iters += 1
                if self.max_loop_iters > 0 and iters > self.max_loop_iters:
                    raise ScriptError(f"while iteration limit exceeded ({self.max_loop_iters})")
                try:
                    self._exec_body(node.body)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
        finally:
            self.loop_depth -= 1

    def _exec_ForEach(self, node: ast.ForEach):
        if self.loop_depth >= self.max_loop_depth:
            raise ScriptError(f"loop nesting depth exceeded ({self.max_loop_depth})")
        source = self._resolve_source(node.source)
        self.loop_depth += 1
        prev = self.locals.get(node.var_name, None)
        had_prev = node.var_name in self.locals
        try:
            iters = 0
            for item in source:
                iters += 1
                if self.max_loop_iters > 0 and iters > self.max_loop_iters:
                    raise ScriptError(f"foreach iteration limit exceeded ({self.max_loop_iters})")
                self.locals[node.var_name] = item
                if node.where is not None and not self._truthy(self._eval(node.where)):
                    continue
                try:
                    self._exec_body(node.body)
                except ContinueSignal:
                    continue
                except BreakSignal:
                    break
        finally:
            self.loop_depth -= 1
            if had_prev:
                self.locals[node.var_name] = prev
            else:
                self.locals.pop(node.var_name, None)

    def _exec_Assign(self, node: ast.Assign):
        value = self._eval(node.value)
        if node.target_kind == "local":
            self.locals[node.name] = value
        elif node.target_kind == "global":
            self.g_vars[node.name] = value
        elif node.target_kind == "fighter_field":
            fighter = self._eval(node.fighter)
            if fighter is None:
                return
            if node.name not in ast.WRITABLE_FIGHTER_FIELDS:
                raise ScriptError(f"fighter field {node.name!r} is not writable")
            setattr(fighter, node.name, value)
        else:
            raise ScriptError(f"unknown assign target: {node.target_kind!r}")

    def _exec_Action(self, node: ast.Action):
        spec = BUILTIN_ACTIONS.get(node.name)
        if spec is None:
            raise ScriptError(f"unknown action: {node.name!r}")
        args = [self._eval(a) for a in node.args]
        amin, amax = spec["args"]
        if not (amin <= len(args) <= amax):
            raise ScriptError(f"action {node.name!r} expects {amin}..{amax} args, got {len(args)}")
        try:
            spec["fn"](self.engine, *args)
        except Exception as e:
            raise ScriptError(f"action {node.name!r} failed: {e}") from e
        self.actions_fired += 1

    def _exec_Break(self, node: ast.Break):
        if self.loop_depth == 0:
            raise ScriptError("`break` outside of loop")
        raise BreakSignal()

    def _exec_Continue(self, node: ast.Continue):
        if self.loop_depth == 0:
            raise ScriptError("`continue` outside of loop")
        raise ContinueSignal()

    # ---------- expressions ----------

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

    # ---------- helpers ----------

    @staticmethod
    def _truthy(v) -> bool:
        return bool(v)

    def _resolve_source(self, source: str):
        fighters = list(getattr(self.engine, "fighters", []))
        if source == "fighters":
            return fighters
        if source == "active":
            return [f for f in fighters if getattr(f, "is_active", True)]
        if source == "benched":
            return [f for f in fighters if not getattr(f, "is_active", True)]
        if source == "available":
            return [f for f in fighters if getattr(f, "available", True)]
        if source == "exhausted":
            return [f for f in fighters if getattr(f, "is_exhausted", False)]
        raise ScriptError(f"unknown iteration source: {source!r}")
