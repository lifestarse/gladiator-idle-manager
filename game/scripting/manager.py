# Build: 9
"""ScriptManager — owns the program list, persistent globals, trigger dispatch.

Responsibilities:
- Hold list[Program] with unique names (see ``unique_program_name``).
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


# Marker word placed in the parenthesised suffix of a duplicated program's
# name ("Farm" -> "Farm (copy)" -> "Farm (copy 2)").
COPY_MARKER = "copy"


class ScriptManager(_ManagerRunMixin, _ManagerAsyncMixin, _ManagerPersistMixin):
    def __init__(self):
        self.programs: list[Program] = []
        self.g_vars: dict[str, Any] = {}
        # accumulated seconds since last fire, keyed by _program_key (object id
        # is unstable across save/load). That key is trigger+name, which is why
        # program names have to stay unique — see unique_program_name.
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

    # ---------- naming ----------

    def unique_program_name(self, base: str, *, marker: str = "",
                            exclude: Program | None = None) -> str:
        """Return ``base`` decorated so no *other* program carries that name.

        Program names are the identity the run bookkeeping is keyed by
        (``_program_key`` -> ``last_runs`` / ``last_errors`` / ``_tick_accum``),
        so two programs sharing one name share a tick accumulator: both fire at
        roughly double their interval and each one's status lands under the
        other's card. The invariant therefore belongs to the list, not to any
        single caller — every entry point that names or renames a program goes
        through this method or through ``add_program`` / ``rename_program``.

        ``marker`` is an optional word for the parenthesised suffix:
        ``marker="copy"`` yields "Farm (copy)", "Farm (copy 2)", ...; the empty
        default yields "Farm", "Farm (2)", ... ``exclude`` is the program being
        renamed, so keeping its own name is not treated as a collision.
        """
        taken = {p.name for p in self.programs if p is not exclude}
        candidate = f"{base} ({marker})" if marker else base
        n = 1
        while candidate in taken:
            n += 1
            candidate = f"{base} ({marker} {n})" if marker else f"{base} ({n})"
        return candidate

    def rename_program(self, p: Program, new_name: str) -> str:
        """Rename ``p`` and return the name actually applied.

        A blank ``new_name`` keeps the current one. Idempotent: re-applying a
        program's own name is not a collision with itself.
        """
        candidate = (new_name or "").strip() or p.name
        p.name = self.unique_program_name(candidate, exclude=p)
        return p.name

    # ---------- mutation ----------

    def add_program(self, p: Program) -> None:
        """Append ``p``, renaming it when its name is already taken."""
        p.name = self.unique_program_name(p.name, exclude=p)
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
