# Build: 3
"""ScriptManager — owns the program list, persistent globals, trigger dispatch.

Responsibilities:
- Hold list[Program] (no fixed cap).
- Hold persistent g_vars dict (survives save/load).
- Dispatch on_battle_end / on_tick / on_demand.
- Track per-program tick accumulators (for on_tick scheduling).
- Catch any ScriptError per-program; one bad program does not block others.
- to_dict / from_dict for save migration.
"""
from __future__ import annotations
from typing import Any

from .ast_nodes import (
    Program, Trigger,
    ForEach, Action, BinOp, Const, FighterField, LocalVar,
)
from .interpreter import Interpreter, ScriptError


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


class ScriptManager:
    def __init__(self):
        self.programs: list[Program] = []
        self.g_vars: dict[str, Any] = {}
        # accumulated seconds since last fire, keyed by program id (object id is unstable
        # across save/load — we use position+name to be safe).
        self._tick_accum: dict[str, float] = {}
        # last error message per program (for UI display); not persisted.
        self.last_errors: dict[str, str] = {}

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

    # ---------- internal ----------

    def _fire_trigger(self, engine, trigger: str) -> None:
        for p in self.programs:
            if p.enabled and p.trigger == trigger:
                self._run_program(engine, p)

    def _run_program(self, engine, p: Program, force: bool = False) -> str | None:
        if not force and not p.enabled:
            return None
        key = self._program_key(p)
        try:
            interp = Interpreter(engine, p, self.g_vars)
            interp.run()
            self.last_errors.pop(key, None)
            return None
        except ScriptError as e:
            msg = str(e)
            self.last_errors[key] = msg
            return msg
        except Exception as e:
            msg = f"unexpected: {e}"
            self.last_errors[key] = msg
            return msg

    @staticmethod
    def _program_key(p: Program) -> str:
        return f"{p.trigger}:{p.name}"
