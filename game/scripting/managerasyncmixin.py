# Build: 2
"""ScriptManager _ManagerAsyncMixin — background force-run (UI Run button)."""
from __future__ import annotations
import logging
import threading
import time
from typing import Callable

from .ast_nodes import Program
from .interpreter import Interpreter, ScriptError
from .managerrunmixin import RunStats

_log = logging.getLogger(__name__)


class _ManagerAsyncMixin:
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
