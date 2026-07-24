# Build: 2
"""Interpreter statement executors (`_exec_*`) — one method per Statement node."""
from __future__ import annotations

from . import ast_nodes as ast
from .builtins import BUILTIN_ACTIONS
from .errors import ScriptError, BreakSignal, ContinueSignal


class _InterpreterExecMixin:
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
        # Sub-expressions are evaluated OUTSIDE the lock (their engine
        # touches lock individually) so the throttle sleep inside _tick
        # never runs while the lock is held.
        value = self._eval(node.value)
        if node.target_kind == "local":
            self.locals[node.name] = value  # interpreter-private, no lock
        elif node.target_kind == "global":
            with self._state_lock:
                self.g_vars[node.name] = value
        elif node.target_kind == "fighter_field":
            fighter = self._eval(node.fighter)
            if fighter is None:
                return
            if node.name not in ast.WRITABLE_FIGHTER_FIELDS:
                raise ScriptError(f"fighter field {node.name!r} is not writable")
            with self._state_lock:
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
            # The one op that compound-mutates engine state (buy → gold−,
            # inventory+; battle → …). Atomic vs main-thread ticks/saves.
            with self._state_lock:
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

    def _resolve_source(self, source: str):
        with self._state_lock:
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
