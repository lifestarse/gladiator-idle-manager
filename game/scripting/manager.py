# Build: 7
"""ScriptManager — owns the program list, persistent globals, trigger dispatch.

Responsibilities:
- Hold list[Program] (no fixed cap).
- Hold persistent g_vars dict (survives save/load).
- Dispatch on_battle_end / on_tick / on_demand.
- Track per-program tick accumulators (for on_tick scheduling).
- Catch any ScriptError per-program; one bad program does not block others.
- Track ``last_runs`` (last timestamp + actions fired + error) for the UI's
  "Run log" panel so the user can see whether each program is doing anything.
- to_dict / from_dict for save migration.
"""
from __future__ import annotations
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .ast_nodes import (
    Program, Trigger,
    ForEach, Action, BinOp, Const, FighterField, LocalVar,
)
from .interpreter import Interpreter, ScriptError

_log = logging.getLogger(__name__)


@dataclass
class RunStats:
    """One line in a program's run log. In-memory only — not persisted."""
    ts: float                  # wall-clock seconds (time.time()) at run end
    actions_fired: int         # how many side-effect actions executed
    duration_ms: float         # interpreter walltime
    error: str | None = None   # ScriptError message or unexpected exception


# Internal flag-key in g_vars marking "default example programs already inserted".
# Persisted via save/load like any other global, so we don't re-seed on each launch.
_SEEDED_FLAG = "_examples_seeded"


def _example_bench_tired() -> Program:
    """Built-in example: at the end of every arena battle, bench every
    gladiator whose fatigue reached 80 or higher. Idempotent (no-op if
    already benched). The user is free to edit, disable, or delete it.
    """
    return Program(
        name="bench tired",
        trigger=Trigger.ON_BATTLE_END,
        enabled=True,
        body=[
            ForEach(
                var_name="f",
                source="fighters",
                where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(80)),
                body=[Action("bench", [LocalVar("f")])],
            ),
        ],
    )


def _example_activate_ready() -> Program:
    """Built-in example: at the end of every arena battle, re-activate
    every gladiator whose stamina has fully regenerated to 100. Pairs
    with `bench tired` to auto-rotate fighters in and out of the active
    roster as they tire and recover.
    """
    return Program(
        name="activate",
        trigger=Trigger.ON_BATTLE_END,
        enabled=True,
        body=[
            ForEach(
                var_name="f",
                source="fighters",
                where=BinOp(">=", FighterField(LocalVar("f"), "stamina"), Const(100)),
                body=[Action("activate", [LocalVar("f")])],
            ),
        ],
    )


class ScriptManager:
    def __init__(self):
        self.programs: list[Program] = []
        self.g_vars: dict[str, Any] = {}
        # accumulated seconds since last fire, keyed by program id (object id is unstable
        # across save/load — we use position+name to be safe).
        self._tick_accum: dict[str, float] = {}
        # last error message per program (for UI display); not persisted.
        self.last_errors: dict[str, str] = {}
        # last RunStats per program (UI "Run log" panel); not persisted.
        # Keyed by the same string as last_errors so they line up.
        self.last_runs: dict[str, RunStats] = {}
        # Async force-run state. Only one background script can run at a
        # time — sharing engine state across two concurrent interpreters
        # would race horribly on every gold/HP/inventory mutation.
        self._async_thread: threading.Thread | None = None
        self._async_running_name: str | None = None
        self._cancel_flag = threading.Event()

    # ---------- lifecycle ----------

    def to_dict(self) -> dict:
        return {
            "programs": [p.to_dict() for p in self.programs],
            "g_vars": dict(self.g_vars),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "ScriptManager":
        m = cls()
        if not d:
            return m
        for raw in d.get("programs", []):
            try:
                m.programs.append(Program.from_dict(raw))
            except Exception:
                # corrupt program — skip silently rather than blow up the save
                continue
        m.g_vars = dict(d.get("g_vars", {}))
        return m

    # ---------- mutation ----------

    def add_program(self, p: Program) -> None:
        self.programs.append(p)

    def remove_program(self, index: int) -> None:
        if 0 <= index < len(self.programs):
            self.programs.pop(index)

    def move_program(self, index: int, delta: int) -> None:
        new = index + delta
        if 0 <= index < len(self.programs) and 0 <= new < len(self.programs):
            self.programs[index], self.programs[new] = self.programs[new], self.programs[index]

    def reset_globals(self) -> None:
        self.g_vars.clear()

    # ---------- import / export ----------

    EXPORT_KIND_PROGRAM = "gladiator_script_v1"
    EXPORT_KIND_BUNDLE  = "gladiator_scripts_bundle_v1"

    def export_program_json(self, index: int) -> str:
        """Serialize a single program (by index) to a sharable JSON string.

        Wraps the raw program dict with a `kind` discriminator so the
        importer can refuse pasted unrelated JSON early.
        """
        import json
        if not (0 <= index < len(self.programs)):
            raise IndexError(f"program index out of range: {index}")
        payload = {
            "kind": self.EXPORT_KIND_PROGRAM,
            "program": self.programs[index].to_dict(),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def export_all_json(self) -> str:
        """Serialize all programs + persistent globals as a bundle."""
        import json
        payload = {
            "kind": self.EXPORT_KIND_BUNDLE,
            "programs": [p.to_dict() for p in self.programs],
            "g_vars": dict(self.g_vars),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def import_program_json(self, text: str) -> str | None:
        """Append one program from JSON text. Returns error message or None.

        Accepts either the wrapped form (`{"kind": "...", "program": {...}}`)
        or a raw program dict, so quick paste-friendly export still works.
        """
        import json
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as e:
            return f"invalid JSON: {e}"
        raw = None
        if isinstance(data, dict):
            if data.get("kind") == self.EXPORT_KIND_PROGRAM:
                raw = data.get("program")
            elif "name" in data and "body" in data:
                raw = data
        if not isinstance(raw, dict):
            return "not a program payload"
        try:
            p = Program.from_dict(raw)
        except Exception as e:
            return f"could not build program: {e}"
        self.programs.append(p)
        return None

    def import_all_json(self, text: str, replace: bool = True) -> str | None:
        """Import a bundle. `replace=True` overwrites the program list and
        g_vars; `False` appends programs and merges g_vars (existing keys
        win). Returns error message or None on success.
        """
        import json
        try:
            data = json.loads(text)
        except (ValueError, TypeError) as e:
            return f"invalid JSON: {e}"
        if not isinstance(data, dict) or data.get("kind") != self.EXPORT_KIND_BUNDLE:
            return "not a script bundle"
        progs_raw = data.get("programs", [])
        if not isinstance(progs_raw, list):
            return "bundle missing programs list"
        new_progs = []
        for raw in progs_raw:
            try:
                new_progs.append(Program.from_dict(raw))
            except Exception as e:
                return f"could not build program: {e}"
        new_globals = data.get("g_vars", {}) or {}
        if not isinstance(new_globals, dict):
            return "bundle g_vars must be an object"
        if replace:
            self.programs = new_progs
            self.g_vars = dict(new_globals)
        else:
            self.programs.extend(new_progs)
            for k, v in new_globals.items():
                self.g_vars.setdefault(k, v)
        # invalidate per-program caches that referenced old keys
        self._tick_accum.clear()
        self.last_errors.clear()
        return None

    def seed_examples_if_needed(self) -> bool:
        """Insert built-in example programs on first run.

        Idempotent via the `_examples_seeded` flag in g_vars (persisted in
        save). Returns True if anything was added — caller may want to
        save() right away so the flag survives a crash.
        """
        if self.g_vars.get(_SEEDED_FLAG):
            return False
        self.programs.append(_example_bench_tired())
        self.programs.append(_example_activate_ready())
        self.g_vars[_SEEDED_FLAG] = True
        return True

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

    # ---------- async force-run (UI Run button) ----------

    def is_running_async(self) -> bool:
        """True iff a force-run via run_on_demand_async is in flight."""
        return self._async_thread is not None and self._async_thread.is_alive()

    def async_running_name(self) -> str | None:
        """Name of the program currently running in the background, or None."""
        return self._async_running_name if self.is_running_async() else None

    def cancel_async(self) -> bool:
        """Signal the running interpreter to stop at its next _tick.

        Returns True if a cancel was scheduled, False if nothing was running.
        Real termination happens when the interpreter checks the flag in
        its hooked _tick — may take a fraction of a second on slow ops.
        """
        if not self.is_running_async():
            return False
        self._cancel_flag.set()
        return True

    def run_on_demand_async(
        self, engine, name: str,
        on_done: Callable[[str | None, RunStats | None], None] | None = None,
        program: Program | None = None,
    ) -> str | None:
        """Force-run a program in a worker thread with optional ops/sec throttle.

        Why threading:
            A while-loop that farms gold to a target may need tens of
            thousands of iterations. Running them synchronously freezes
            the Kivy main thread for minutes, hides progress, and blocks
            user input — including the Stop button that's supposed to
            cancel it. Putting the interpreter in a daemon thread lets
            the UI keep ticking: gold/diamond counters update, Cancel
            works, the user can switch screens.

        Why a global lock (single concurrent script):
            Two interpreters racing on engine.gold / fighter HP / inventory
            list would corrupt state immediately — none of those mutations
            are atomic under GIL. One-at-a-time keeps the implementation
            simple and lossless for the common case. Safety against the
            Kivy MAIN thread (idle_tick, battle turns, save snapshots) is
            separate: the Interpreter takes engine.state_lock around every
            engine-touching op, and those main-thread entry points take the
            same lock.

        Throttling (``ops_per_sec``):
            Worker sleeps 1/ops_per_sec seconds between interpreter steps.
            0 means full speed — useful when farming a tight numeric loop.
            10k–100k is the sweet spot for visible progress + responsive
            UI on typical hardware.

        Cancellation:
            ``cancel_async()`` sets a threading.Event the worker checks
            inside its hooked _tick. The interpreter raises ScriptError
            ("cancelled") and the run finishes normally with that error
            recorded — RunStats still captures actions_fired so the user
            knows how much real work was done.

        Returns an error message if the call could not start (another
        script already running, name not found). Run-completion result
        is delivered via ``on_done(err, run_stats)`` on the Kivy main
        thread via Clock.schedule_once.
        """
        if self.is_running_async():
            _log.info("[ScriptManager] async kickoff refused: already running %r",
                      self._async_running_name)
            return "another script is already running"
        # Prefer the explicit Program instance (index-safe under duplicate
        # names); fall back to first-match-by-name for older callers.
        if program is not None and program in self.programs:
            target = program
        else:
            target = next((p for p in self.programs if p.name == name), None)
        if target is None:
            _log.info("[ScriptManager] async kickoff refused: program %r not found", name)
            return f"program {name!r} not found"

        self._cancel_flag.clear()
        cancel_flag = self._cancel_flag
        key = self._program_key(target)
        ops_per_sec = target.ops_per_sec
        sleep_per_op = (1.0 / ops_per_sec) if ops_per_sec > 0 else 0.0
        _log.info(
            "[ScriptManager] async kickoff %r: trigger=%s ops_per_sec=%d sleep_per_op=%.4fs body_stmts=%d",
            name, target.trigger, ops_per_sec, sleep_per_op, len(target.body),
        )

        def _worker():
            # Imported here to keep manager.py importable in headless test
            # contexts that mock Kivy out.
            from kivy.clock import Clock

            t0 = time.monotonic()
            # max_steps=0 / max_loop_iters=0 → unlimited; the cancel flag
            # and the user's Stop button are the actual safety net now.
            interp = Interpreter(
                engine, target, self.g_vars,
                max_steps=0, max_loop_iters=0,
            )
            orig_tick = interp._tick

            def _hooked_tick():
                if cancel_flag.is_set():
                    raise ScriptError("cancelled")
                orig_tick()
                # Empty-loop guard: 5000 interpreter ticks with zero
                # actions fired is almost always the user putting the
                # action OUTSIDE the while-body instead of inside.
                # Without this the loop spins forever, never yielding
                # any visible progress, and the user thinks "Run does
                # nothing".
                if interp.steps > 5000 and interp.actions_fired == 0:
                    raise ScriptError(
                        "5000 ops with no action fired — did you put the "
                        "action INSIDE the loop body? (drag it under the "
                        "while/if block, not next to it)"
                    )
                if sleep_per_op > 0:
                    time.sleep(sleep_per_op)
                elif interp.steps % 100 == 0:
                    # Periodic micro-yield so the UI gets CPU even when
                    # ops_per_sec=0. time.sleep(0) is a GIL release hint
                    # in CPython — main thread can grab the GIL and
                    # render a frame, then we resume.
                    time.sleep(0)
            interp._tick = _hooked_tick

            err: str | None = None
            try:
                interp.run()
            except ScriptError as e:
                err = str(e)
            except Exception as e:  # pragma: no cover — defensive
                err = f"unexpected: {e}"
                _log.exception("[ScriptManager] async run crashed")

            stats = RunStats(
                ts=time.time(),
                actions_fired=interp.actions_fired,
                duration_ms=(time.monotonic() - t0) * 1000.0,
                error=err,
            )
            _log.info(
                "[ScriptManager] async finished %r: actions=%d steps=%d duration=%.1fms err=%s",
                name, interp.actions_fired, interp.steps, stats.duration_ms, err,
            )

            def _finish(_dt):
                self.last_runs[key] = stats
                if err:
                    self.last_errors[key] = err
                else:
                    self.last_errors.pop(key, None)
                self._async_thread = None
                self._async_running_name = None
                if on_done is not None:
                    try:
                        on_done(err, stats)
                    except Exception:  # pragma: no cover
                        _log.exception("[ScriptManager] async on_done callback failed")

            Clock.schedule_once(_finish, 0)

        self._async_running_name = name
        self._async_thread = threading.Thread(target=_worker, daemon=True)
        self._async_thread.start()
        return None
