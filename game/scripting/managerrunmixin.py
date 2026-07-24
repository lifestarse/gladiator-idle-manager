# Build: 1
"""ScriptManager _ManagerRunMixin — trigger dispatch + synchronous runs.

Also home of RunStats (needed by both sync and async runners; manager.py
re-exports it so `from .manager import RunStats` keeps working).
"""
from __future__ import annotations
import time
from dataclasses import dataclass

from .ast_nodes import Program, Trigger
from .interpreter import Interpreter, ScriptError


@dataclass
class RunStats:
    """One line in a program's run log. In-memory only — not persisted."""
    ts: float                  # wall-clock seconds (time.time()) at run end
    actions_fired: int         # how many side-effect actions executed
    duration_ms: float         # interpreter walltime
    error: str | None = None   # ScriptError message or unexpected exception


class _ManagerRunMixin:
    # ---------- triggers ----------

    def on_battle_end(self, engine) -> None:
        self._fire_trigger(engine, Trigger.ON_BATTLE_END)

    def on_tick(self, engine, dt: float) -> None:
        for p in self.programs:
            if not p.enabled or p.trigger != Trigger.ON_TICK:
                continue
            key = self._program_key(p)
            self._tick_accum[key] = self._tick_accum.get(key, 0.0) + dt
            if self._tick_accum[key] >= p.tick_interval:
                self._tick_accum[key] = 0.0
                self._run_program(engine, p)

    def run_on_demand(self, engine, name: str) -> str | None:
        """Run a single program by name regardless of enabled state. Returns error or None."""
        for p in self.programs:
            if p.name == name:
                return self._run_program(engine, p, force=True)
        return f"program {name!r} not found"

    def run_program_now(self, engine, p: Program) -> str | None:
        """Force-run a specific Program instance.

        Name-based lookup (run_on_demand) picks the FIRST program with a
        matching name — under duplicate names (rename doesn't dedupe) the
        wrong program runs. UI callsites that already hold the Program
        object should use this instead.
        """
        if p not in self.programs:
            return f"program {p.name!r} not found"
        return self._run_program(engine, p, force=True)

    # ---------- internal ----------

    def _fire_trigger(self, engine, trigger: str) -> None:
        for p in self.programs:
            if p.enabled and p.trigger == trigger:
                self._run_program(engine, p)

    def _run_program(self, engine, p: Program, force: bool = False) -> str | None:
        if not force and not p.enabled:
            return None
        key = self._program_key(p)
        t0 = time.monotonic()
        # Synchronous interpreter. Force-runs through this codepath
        # (gear-menu "Run now" on the program card) keep the default
        # safety caps so they're a quick test, not a half-hour freeze —
        # the editor's Run button uses run_on_demand_async for the
        # long-running, throttled, cancellable case.
        interp = Interpreter(engine, p, self.g_vars)
        try:
            interp.run()
            self.last_errors.pop(key, None)
            self.last_runs[key] = RunStats(
                ts=time.time(),
                actions_fired=interp.actions_fired,
                duration_ms=(time.monotonic() - t0) * 1000.0,
                error=None,
            )
            return None
        except ScriptError as e:
            msg = str(e)
            self.last_errors[key] = msg
            self.last_runs[key] = RunStats(
                ts=time.time(),
                actions_fired=interp.actions_fired,
                duration_ms=(time.monotonic() - t0) * 1000.0,
                error=msg,
            )
            return msg
        except Exception as e:
            msg = f"unexpected: {e}"
            self.last_errors[key] = msg
            self.last_runs[key] = RunStats(
                ts=time.time(),
                actions_fired=interp.actions_fired,
                duration_ms=(time.monotonic() - t0) * 1000.0,
                error=msg,
            )
            return msg

    @staticmethod
    def _program_key(p: Program) -> str:
        return f"{p.trigger}:{p.name}"
