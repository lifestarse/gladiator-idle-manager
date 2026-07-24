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

Split into sibling mixins: sync runs + RunStats in managerrunmixin.py,
background force-run in managerasyncmixin.py, save/import-export/seeding
in managerpersistmixin.py. This module composes them and keeps __init__.
"""
from __future__ import annotations
import threading
from typing import Any

from .ast_nodes import Program
from .managerrunmixin import _ManagerRunMixin, RunStats  # noqa: F401
from .managerasyncmixin import _ManagerAsyncMixin
from .managerpersistmixin import (  # noqa: F401
    _ManagerPersistMixin, _SEEDED_FLAG,
    _example_bench_tired, _example_activate_ready,
)


class ScriptManager(_ManagerRunMixin, _ManagerAsyncMixin, _ManagerPersistMixin):
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
