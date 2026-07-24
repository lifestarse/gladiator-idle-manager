# Build: 3
"""Tree-walking interpreter for the squad scripting language.

Safety limits (configurable via constructor):
    max_steps       — total node executions (default 5000).
    max_loop_iters  — single while/foreach iteration cap (default 1000).
    max_loop_depth  — nesting depth of loops (default 10).

Thread safety: when the program runs on ScriptManager's async worker
thread, every read/write of shared engine state (fighter fields, engine
fields, actions, g_vars) is taken under engine.state_lock. The lock is
deliberately NOT held across _tick() — the async runner's hooked tick
sleeps there for ops/sec throttling, and sleeping while holding the lock
would starve the Kivy main thread.

Exceptions:
    ScriptError — wraps any runtime failure with the originating node kind.
    BreakSignal / ContinueSignal — internal control-flow.

Node handlers live in sibling mixins: statements in interpreterexecmixin.py
(`_exec_*`), expressions in interpreterevalmixin.py (`_eval_*`). Exceptions
are defined in errors.py and re-exported here for external importers.
"""
from __future__ import annotations
from contextlib import nullcontext
from typing import Any

from . import ast_nodes as ast
from .errors import ScriptError, BreakSignal, ContinueSignal  # noqa: F401
from .interpreterexecmixin import _InterpreterExecMixin
from .interpreterevalmixin import _InterpreterEvalMixin


class Interpreter(_InterpreterExecMixin, _InterpreterEvalMixin):
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
        # Serializes engine access against the Kivy main thread (RLock on
        # real engines — the synchronous trigger path re-enters while
        # idle_tick already holds it). Test stubs without state_lock get a
        # no-op context.
        self._state_lock = getattr(engine, "state_lock", None) or nullcontext()

    # ---------- public ----------

    def run(self) -> None:
        with self._state_lock:
            # g_vars is shared with the main thread's save snapshot
            # (scripts.to_dict inside _build_save_data).
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

    # ---------- helpers ----------

    @staticmethod
    def _truthy(v) -> bool:
        return bool(v)
