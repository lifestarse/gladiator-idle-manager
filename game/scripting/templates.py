# Build: 1
"""Built-in program templates for the squad-scripting UI.

A template is a small factory function returning a fresh :class:`Program`
with sensible defaults. The user imports a template by name (UI: "Templates"
button on the scripts list) — applying it APPENDS a freshly-built program to
the user's list, never mutates the template itself.

Each template comes with two i18n keys (``name_key`` / ``desc_key``) so the
picker can show a human-readable label + one-line description.

The two examples seeded into a brand-new save by ScriptManager
(``bench_tired`` and ``activate_ready``) are intentionally listed first here
so a returning user who deleted them can re-insert them from this menu.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable

from .ast_nodes import (
    Program, Trigger,
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
)


@dataclass(frozen=True)
class Template:
    """One entry in the templates picker."""
    id: str
    name_key: str
    desc_key: str
    factory: Callable[[], Program]


# ---------- factories ----------

def _t_bench_tired() -> Program:
    return Program(
        name="bench tired",
        trigger=Trigger.ON_BATTLE_END,
        body=[
            ForEach(
                var_name="f", source="fighters",
                where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(80)),
                body=[Action("bench", [LocalVar("f")])],
            ),
        ],
    )


def _t_activate_ready() -> Program:
    return Program(
        name="activate ready",
        trigger=Trigger.ON_BATTLE_END,
        body=[
            ForEach(
                var_name="f", source="fighters",
                where=BinOp(">=", FighterField(LocalVar("f"), "stamina"), Const(100)),
                body=[Action("activate", [LocalVar("f")])],
            ),
        ],
    )


def _t_buy_weapon_if_rich() -> Program:
    return Program(
        name="buy weapon if rich",
        trigger=Trigger.ON_BATTLE_END,
        body=[
            If(
                cond=BinOp(">", EngineField("gold"), Const(1000)),
                then_body=[Action("buy_item", [Const("weapon")])],
                else_body=[],
            ),
        ],
    )


def _t_equip_empty_weapons() -> Program:
    return Program(
        name="equip empty weapons",
        trigger=Trigger.ON_BATTLE_END,
        body=[
            ForEach(
                var_name="f", source="fighters",
                where=UnaryOp("not", FighterField(LocalVar("f"), "has_weapon")),
                body=[Action("equip_best", [LocalVar("f"), Const("weapon")])],
            ),
        ],
    )


def _t_auto_arena_idle() -> Program:
    return Program(
        name="auto-arena (idle)",
        trigger=Trigger.ON_TICK,
        tick_interval=60,
        body=[
            If(
                cond=BinOp(
                    "and",
                    BinOp(">=", EngineField("active_count"), Const(3)),
                    UnaryOp("not", EngineField("battle_active")),
                ),
                then_body=[Action("start_arena_battle", [])],
                else_body=[],
            ),
        ],
    )


def _t_train_all_to_5() -> Program:
    return Program(
        name="train to 5",
        trigger=Trigger.ON_DEMAND,
        body=[
            ForEach(
                var_name="f", source="fighters",
                body=[Action("train_to", [LocalVar("f"), Const(5)])],
            ),
        ],
    )


def _t_unequip_exhausted() -> Program:
    return Program(
        name="unequip exhausted",
        trigger=Trigger.ON_BATTLE_END,
        body=[
            ForEach(
                var_name="f", source="exhausted",
                body=[Action("unequip_all", [LocalVar("f")])],
            ),
        ],
    )


def _t_periodic_expedition_t1() -> Program:
    return Program(
        name="expedition T1",
        trigger=Trigger.ON_TICK,
        tick_interval=300,  # 5 minutes
        body=[
            If(
                cond=UnaryOp("not", EngineField("expedition_active")),
                then_body=[Action("start_expedition", [Const(1)])],
                else_body=[],
            ),
        ],
    )


def _t_farm_to_500k() -> Program:
    """After every battle, kick off a fresh arena battle while gold < 500k.

    Uses the ``on_battle_end`` trigger: this means the program only fires
    when a battle just finished (either a manual one in Arena, or a previous
    scripted ``start_arena_battle``). One extra battle per natural Arena
    tick — useful if the user wants the script to "extend" their play
    session without taking it over.

    For fully autonomous farming (no user interaction needed), use
    ``_t_autofarm_to_500k_tick`` instead.
    """
    return Program(
        name="farm to 500k",
        trigger=Trigger.ON_BATTLE_END,
        body=[
            If(
                cond=BinOp(
                    "and",
                    BinOp("<", EngineField("gold"), Const(500_000)),
                    UnaryOp("not", EngineField("battle_active")),
                ),
                then_body=[Action("start_arena_battle", [])],
                else_body=[],
            ),
        ],
    )


def _t_autofarm_to_500k_tick() -> Program:
    """Truly automatic farming: every second, recover the squad then start a
    fresh arena battle if gold < 500k and no battle is running.

    The "rest the squad first" step is the trick that makes this loop go
    for tens of thousands of battles instead of dying after ~20. Each
    scripted battle calls ``apply_battle_fought`` on every participant
    (stamina -10; once at 0, fatigue +10), and at fatigue=100 the fighter
    becomes exhausted and falls out of ``available``. Without anyone to
    deploy, ``start_arena_battle`` is a silent no-op. ``rest(f)`` runs the
    same recovery the engine applies to skipped/benched fighters, so by
    resting every fighter at the start of each tick we cancel out one
    battle's worth of drain and the cycle is sustainable.

    Tick-driven (not while-loop): the interpreter caps loops at 1000 iters
    and ``battle_skip`` is synchronous, so a while loop would freeze the
    UI for as long as it ran. Per-tick lets Kivy breathe between battles.
    """
    return Program(
        name="auto-farm to 500k",
        trigger=Trigger.ON_TICK,
        tick_interval=1,
        body=[
            # Step 1: rest the whole squad (no-op when at full stamina / 0 fatigue).
            ForEach(
                var_name="f", source="fighters",
                body=[Action("rest", [LocalVar("f")])],
            ),
            # Step 2: start one battle if conditions allow.
            If(
                cond=BinOp(
                    "and",
                    BinOp("<", EngineField("gold"), Const(500_000)),
                    UnaryOp("not", EngineField("battle_active")),
                ),
                then_body=[Action("start_arena_battle", [])],
                else_body=[],
            ),
        ],
    )


# ---------- registry ----------

# Order shown in the picker. Most common / safe templates first.
TEMPLATES: tuple[Template, ...] = (
    Template("t1", "scr_tmpl_t1_name", "scr_tmpl_t1_desc", _t_bench_tired),
    Template("t2", "scr_tmpl_t2_name", "scr_tmpl_t2_desc", _t_activate_ready),
    Template("t3", "scr_tmpl_t3_name", "scr_tmpl_t3_desc", _t_buy_weapon_if_rich),
    Template("t4", "scr_tmpl_t4_name", "scr_tmpl_t4_desc", _t_equip_empty_weapons),
    Template("t5", "scr_tmpl_t5_name", "scr_tmpl_t5_desc", _t_auto_arena_idle),
    Template("t6", "scr_tmpl_t6_name", "scr_tmpl_t6_desc", _t_train_all_to_5),
    Template("t7", "scr_tmpl_t7_name", "scr_tmpl_t7_desc", _t_unequip_exhausted),
    Template("t8", "scr_tmpl_t8_name", "scr_tmpl_t8_desc", _t_periodic_expedition_t1),
    Template("t9", "scr_tmpl_t9_name", "scr_tmpl_t9_desc", _t_farm_to_500k),
    Template("t10", "scr_tmpl_t10_name", "scr_tmpl_t10_desc", _t_autofarm_to_500k_tick),
)


def template_by_id(tid: str) -> Template | None:
    for t in TEMPLATES:
        if t.id == tid:
            return t
    return None
