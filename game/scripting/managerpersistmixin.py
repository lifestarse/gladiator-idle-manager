# Build: 1
"""ScriptManager _ManagerPersistMixin — save dicts, import/export, example seeding."""
from __future__ import annotations

from .ast_nodes import (
    Program, Trigger,
    ForEach, Action, BinOp, Const, FighterField, LocalVar,
)

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


class _ManagerPersistMixin:
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
