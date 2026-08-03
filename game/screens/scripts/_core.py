# Build: 12
"""ScriptsScreen + ScriptEditorScreen.

Layout shell (background, TopBar, top toolbar buttons, separator,
scrollable container) lives in ``kv/scripts_screen.kv`` — same pattern
every other screen uses. Python is responsible only for the dynamic
content inside the containers:

    ScriptsScreen.ids.program_list   ← one BlockCard per saved Program
    ScriptEditorScreen.ids.editor_body ← name field, trigger picker,
                                          tick-interval (conditional),
                                          recursive block tree

KV references methods on the Screen instance via ``root._method()``.
Those have to be defined on this class even when they're one-liners,
otherwise the on_press wires throw at first tap.
"""
from __future__ import annotations
import logging

from ._screen_imports import *  # noqa: F401,F403
from game.scripting.ast_nodes import Program, Trigger, If, While, ForEach
from game.scripting.manager import COPY_MARKER
from game.scripting import labels as L
from .cells import BlockCard, TriggerPicker
from .popups import (
    open_block_palette, open_template_picker, open_program_menu,
    open_run_log, open_confirm, open_export_text, open_import_dialog,
    open_online_library,
)


_log = logging.getLogger(__name__)

# Time in seconds to wait after the last edit before flushing engine.save().
# Debouncing keeps the UI snappy when the user is dragging through a value
# field where each keystroke fires on_change.
SAVE_DEBOUNCE_S = 0.8

# Snapshot debounce. Each "logical action" (typing a value, sliding a picker)
# fires _on_changed many times; we want ONE undo entry per action, not one
# per keystroke. Slightly longer than the save debounce so the snapshot
# captures the final settled state.
SNAPSHOT_DEBOUNCE_S = 1.0

# Hard cap on undo history so a long editing session doesn't grow memory
# without bound. 50 actions is plenty for the kind of editing a player
# does on a script — far more would just hide which step they need to undo
# back to anyway.
UNDO_MAX = 50


# Width of the status/label column the program cards lay text into. The cards
# live in a fixed-width scroll container, so the labels get an explicit
# text_size rather than one bound to their own (unconstrained) width.
CARD_TEXT_W = 360

# How much of a failed run's message fits on a program card's status line
# before the card starts pushing the list around.
ERR_SNIPPET_LEN = 40


# ---------- shared helpers ----------

def _info(title: str, msg: str):
    Popup(title=title or " ", content=Label(text=str(msg)),
          size_hint=(0.75, 0.40)).open()


def _show_run_toast(program, run):
    """Surface RunStats as a toast — see prior commits for full rationale.
    Briefly: "0 actions" + no error means the program ran but its body
    produced no side effects (something to debug); "3 actions" means it
    actually did work. Without this the user can't tell scripted no-ops
    apart from real-but-silent runs."""
    app = App.get_running_app()
    if not hasattr(app, "show_toast"):
        return
    if run is None:
        app.show_toast(f"{program.name}: ?")
        return
    if run.error:
        app.show_toast(f"{program.name}: {run.error}")
    else:
        app.show_toast(
            f"{program.name}: "
            f"{t('scr_log_ok', n=run.actions_fired)} ({run.duration_ms:.0f}ms)"
        )


# ---------- save debounce mixin ----------

class _SaveDebounceMixin:
    """Shared engine.save() debouncer used by both screens."""

    _save_clock = None

    def _schedule_save(self):
        if self._save_clock is not None:
            self._save_clock.cancel()
        self._save_clock = Clock.schedule_once(self._do_save, SAVE_DEBOUNCE_S)

    def _do_save(self, *_):
        self._save_clock = None
        try:
            App.get_running_app().engine.save()
        except Exception as exc:
            _log.warning("scripts save failed: %s", exc)

    def _flush_save_now(self):
        """Cancel any pending debounced save and write to disk immediately.

        Called from ``on_pre_leave`` so the user's last edit (e.g. typing a
        new tick interval) doesn't get dropped if they navigate away inside
        the 0.8 s debounce window. Without this, the Clock scheduling was
        cancelled by the screen change before _do_save could fire, and on
        return the TextInput rebuilt from the old persisted value — the
        "interval doesn't save" bug.
        """
        if self._save_clock is not None:
            self._save_clock.cancel()
            self._save_clock = None
        try:
            App.get_running_app().engine.save()
        except Exception as exc:
            _log.warning("scripts flush save failed: %s", exc)


# ---------- Scripts list screen ----------

class ScriptsScreen(BaseScreen, _SaveDebounceMixin):
    """Top-level list of programs.

    Shell is declared in ``kv/scripts_screen.kv``. Python only:
    populates ``ids.program_list`` with one card per program and handles
    the toolbar callbacks referenced from kv (_new_program,
    _open_templates, _export_all, _import_dialog).

    Two tabs via ``scripts_tab``:
        "all"     — every program in the manager, in storage order
        "running" — only enabled + auto-firing triggers (on_battle_end /
                    on_tick). on_demand programs are NEVER in running
                    because they never fire on their own — even if
                    enabled=True their state is identical to disabled.
    """

    # Kept as a StringProperty (not a more-fitting OptionProperty) because
    # kv binds via equality comparisons (e.g. ``if root.scripts_tab == "all"``)
    # which is cleaner with plain strings, and there are only two values.
    scripts_tab = StringProperty("all")

    def on_pre_enter(self, *args):
        self._update_top_bar()
        self._build()

    def on_pre_leave(self, *args):
        # Flush any pending debounced save so a quick edit-then-navigate
        # doesn't drop the change. See _SaveDebounceMixin._flush_save_now.
        self._flush_save_now()

    def refresh(self):
        """BaseScreen per-tick entry point."""
        self.refresh_scripts()

    def refresh_scripts(self):
        """Called every second by App._idle_tick when engine._ui_dirty.

        Pushes the latest gold/diamond counts into the shared TopBar
        (via _update_top_bar → app.update_top_bar) AND rebuilds the
        program cards so the "ran Ns ago" indicators tick forward.
        """
        self._update_top_bar()
        self._build()

    def set_tab(self, tab: str):
        """Called from kv tab buttons. Rebuild immediately so the user
        sees the filtered list flip without waiting for the next idle tick."""
        if tab not in ("all", "running"):
            return
        if self.scripts_tab == tab:
            return
        self.scripts_tab = tab
        self._build()

    def _is_running(self, p: Program) -> bool:
        """Whether a program would fire on its own right now.

        "Running" semantics: the program is enabled AND has an auto-firing
        trigger. ``on_demand`` programs are excluded — they only fire via
        Run, so listing them under "Running" would be misleading. Listed:

            - on_battle_end + enabled — will fire next time a battle ends
            - on_tick      + enabled — fires every ``tick_interval`` seconds

        Note this is a STATIC check (would-fire), not a dynamic one (is
        currently inside an interpreter call). The dynamic case is too
        short-lived (sub-millisecond) to be useful for the user.
        """
        if not p.enabled:
            return False
        return p.trigger in (Trigger.ON_BATTLE_END, Trigger.ON_TICK)

    def _build(self):
        """Rebuild dynamic content inside ids.program_list, filtered by tab."""
        container = self.ids.get("program_list")
        if container is None:
            return  # kv not loaded yet; on_pre_enter will retry
        container.clear_widgets()
        engine = App.get_running_app().engine
        mgr = engine.scripts

        # Apply tab filter. Keep the original index inside the manager's
        # list so editor / move / delete operations still target the right
        # program (filtering changes the visible order on the Running tab
        # but the underlying mgr.programs list stays intact).
        if self.scripts_tab == "running":
            entries = [(i, p) for i, p in enumerate(mgr.programs)
                       if self._is_running(p)]
            empty_msg = t("scr_no_running")
        else:
            entries = list(enumerate(mgr.programs))
            empty_msg = t("scr_no_programs")

        if not entries:
            container.add_widget(Label(
                text=empty_msg,
                size_hint_y=None, height=dp(40),
                font_size="12sp", color=TEXT_SECONDARY,
                halign="center", valign="middle",
                text_size=(dp(CARD_TEXT_W), dp(40)),
            ))
            return
        for i, p in entries:
            container.add_widget(self._program_card(i, p, mgr))

    def _program_card(self, idx: int, p: Program, mgr) -> BoxLayout:
        """Single program row: name+gear / trigger label / status line.

        Tapping the name opens the editor; tapping ``⋮`` opens
        ``open_program_menu`` with run/toggle/rename/duplicate/export/
        move-up/move-down/delete actions.
        """
        wrap = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=dp(8), spacing=dp(2))
        wrap.bind(minimum_height=wrap.setter("height"))
        _bg(wrap, BG_CARD)

        # Title row: name + gear menu.
        # NOTE: ⋮ ● ○ ✗ ↑ ↓ all rendered as "?" in PixelFont — that font
        # only carries the printable-ASCII range plus Cyrillic. Symbol
        # buttons therefore use icon_source instead of text glyphs.
        top = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(32), spacing=dp(6))
        name_btn = MinimalButton(
            text=p.name,
            # Green check when enabled, red close when disabled — the
            # status indicator that used to be ● / ○ in text form.
            icon_source=("icons/ic_check.png" if p.enabled
                         else "icons/ic_close.png"),
            font_size=13, variant="secondary",
            btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(30),
        )
        name_btn.bind(on_release=lambda *_, i=idx: self._edit_program(i))
        top.add_widget(name_btn)
        gear = MinimalButton(
            text="",
            icon_source="icons/ic_dots.png",
            size_hint_x=None, width=dp(36),
            size_hint_y=None, height=dp(30),
            variant="ghost", btn_color=TEXT_SECONDARY,
        )
        gear.bind(on_release=lambda *_, i=idx, prog=p: self._open_menu(i, prog))
        top.add_widget(gear)
        wrap.add_widget(top)

        # Trigger line — localised
        trig_label = t(L.TRIGGER_LABELS.get(p.trigger, p.trigger))
        if p.trigger == Trigger.ON_TICK:
            trig_label = f"{trig_label} ({p.tick_interval}s)"
        wrap.add_widget(Label(
            text=trig_label, size_hint_y=None, height=dp(20),
            font_size="12sp", font_name="BodyFont", color=TEXT_PRIMARY,
            halign="left", valign="middle",
            text_size=(dp(CARD_TEXT_W), dp(20)),
        ))

        # Status line: enabled, blocks count, last-run/error
        run = mgr.last_run_for(p)
        err = mgr.last_error_for(p)
        bits = [
            t("scr_on") if p.enabled else t("scr_off"),
            t("scr_blocks_n", n=len(p.body)),
        ]
        if run is not None:
            import time as _t
            age = int(_t.time() - run.ts)
            bits.append(t("scr_last_run", s=age))
        else:
            bits.append(t("scr_never_ran"))
        status = " · ".join(bits)
        status_color = TEXT_ERROR if err else TEXT_SECONDARY
        if err:
            status += f" · {t('scr_run_failed')}: {err[:ERR_SNIPPET_LEN]}"
        wrap.add_widget(Label(
            text=status, size_hint_y=None, height=dp(20),
            font_size="11sp", font_name="BodyFont", color=status_color,
            halign="left", valign="middle",
            text_size=(dp(CARD_TEXT_W), dp(20)),
        ))
        return wrap

    # ---------- callbacks (referenced from kv via root._...) ----------

    def _new_program(self):
        engine = App.get_running_app().engine
        p = Program(name=t("scr_default_program_name"),
                    trigger=Trigger.ON_BATTLE_END)
        engine.scripts.add_program(p)
        self._schedule_save()
        self._edit_program(len(engine.scripts.programs) - 1)

    def _edit_program(self, idx):
        app = App.get_running_app()
        editor = app.sm.get_screen("script_editor")
        editor.program_index = idx
        app.sm.current = "script_editor"

    def _open_menu(self, idx: int, p: Program):
        engine = App.get_running_app().engine
        mgr = engine.scripts

        def _run():
            # Index-safe: run THIS program object, not first-match-by-name
            # (duplicate names are possible after a rename).
            err = mgr.run_program_now(engine, p)
            self._schedule_save()
            if err:
                _info(t("scr_error_title"), err)
            else:
                _show_run_toast(p, mgr.last_run_for(p))
            self._update_top_bar()
            self._build()

        def _toggle():
            p.enabled = not p.enabled
            self._schedule_save()
            self._build()

        def _rename(new_name: str):
            # Uniqueness lives on the manager: the run bookkeeping is keyed by
            # trigger+name, so a rename onto an existing name would merge two
            # programs' tick accumulators and status lines.
            mgr.rename_program(p, new_name)
            self._schedule_save()
            self._build()

        def _duplicate():
            try:
                clone = Program.from_dict(p.to_dict())
                clone.name = mgr.unique_program_name(clone.name,
                                                     marker=COPY_MARKER)
                mgr.add_program(clone)
                self._schedule_save()
                self._build()
            except Exception as exc:
                _info(t("scr_error_title"), str(exc))

        def _export():
            try:
                open_export_text(mgr.export_program_json(idx),
                                  t("scr_export_title"))
            except Exception as exc:
                _info(t("scr_error_title"), str(exc))

        def _delete():
            def _yes():
                mgr.remove_program(idx)
                self._schedule_save()
                self._build()
            open_confirm(
                title=t("scr_menu_delete"),
                body=t("scr_confirm_delete", name=p.name),
                yes_label=t("scr_confirm_yes"),
                on_yes=_yes,
            )

        def _move_up():
            mgr.move_program(idx, -1)
            self._schedule_save()
            self._build()

        def _move_down():
            mgr.move_program(idx, +1)
            self._schedule_save()
            self._build()

        open_program_menu(
            program=p,
            on_run=_run, on_toggle=_toggle, on_rename=_rename,
            on_duplicate=_duplicate, on_export=_export, on_delete=_delete,
            on_move_up=_move_up, on_move_down=_move_down,
        )

    def _append_program(self, prog: Program):
        """Apply contract shared by the template and online-library pickers.

        Both hand back a freshly built Program and leave appending to us;
        ``add_program`` gives it a "(2)" / "(3)" suffix if the name is taken.
        """
        App.get_running_app().engine.scripts.add_program(prog)
        self._schedule_save()
        self._build()

    def _open_templates(self):
        open_template_picker(self._append_program)

    def _open_online(self):
        """Open the community scripts library browser.

        The picker handles all the network/cache logic; we only deal with the
        resulting Program once the user picks one.
        """
        open_online_library(self._append_program)

    def _export_all(self):
        engine = App.get_running_app().engine
        try:
            open_export_text(engine.scripts.export_all_json(),
                              t("scr_export_all_title"))
        except Exception as exc:
            _info(t("scr_error_title"), str(exc))

    def _import_dialog(self):
        engine = App.get_running_app().engine
        mgr = engine.scripts
        def _on_import(text: str, replace: bool):
            text = (text or "").strip()
            if not text:
                return t("scr_error")
            err_b = mgr.import_all_json(text, replace=replace)
            if err_b is None:
                self._schedule_save()
                self._build()
                return None
            err_p = mgr.import_program_json(text)
            if err_p is None:
                self._schedule_save()
                self._build()
                return None
            return f"{err_b} / {err_p}"
        open_import_dialog(_on_import)


# ---------- Editor screen ----------

class ScriptEditorScreen(BaseScreen, _SaveDebounceMixin):
    """Single-program editor.

    Shell (TopBar + toolbar + separator + scroll container) is in kv.
    Python populates ``ids.editor_body`` with name input, trigger picker,
    tick-interval (conditional), and the recursive BlockCard tree.

    ``editor_title`` is a StringProperty bound from kv into the TopBar's
    title_text, so the bar updates live when the user renames the program
    or navigates from one program to another.
    """

    program_index = NumericProperty(-1)
    editor_title = StringProperty("")
    # is_running drives the Run/Stop toggle in the top toolbar (see kv).
    # Recomputed on every refresh / state change so the button label flips
    # the moment the user toggles enabled or switches trigger.
    is_running = BooleanProperty(False)
    # Whether undo/redo are available right now. KV binds button enabled
    # state to these so the icons grey out when there's nothing to do.
    can_undo = BooleanProperty(False)
    can_redo = BooleanProperty(False)

    # Per-program undo/redo state. NOT a class-level list — each instance
    # has its own pair, reset whenever the user switches to a different
    # program. Stacks hold ``Program.to_dict()`` snapshots so we can fully
    # round-trip the AST including any sub-expression mutations.
    def __init__(self, **kw):
        super().__init__(**kw)
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        # Sentinel for the last-snapshotted state — used to dedupe rapid
        # successive calls so typing "5000" doesn't create 4 snapshots.
        self._last_snapshot: dict | None = None
        self._snapshot_clock = None

    def on_pre_enter(self, *args):
        # Each visit to the editor starts a fresh undo session. Editing
        # program A then switching to program B and undoing should NOT
        # undo back into A — that would be confusing.
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._last_snapshot = None
        self.can_undo = False
        self.can_redo = False
        self._update_top_bar()
        self._build()
        # Baseline snapshot so the user's very first Undo restores to the
        # state they saw when opening the editor.
        self._take_snapshot(immediate=True)

    def on_pre_leave(self, *args):
        # Flush BOTH the save debounce AND the snapshot debounce. The save
        # one matters for persistence — typing a new tick_interval and
        # leaving inside 0.8 s would otherwise leave the change in memory
        # only, until the next user-triggered save fires later. The
        # snapshot flush matters because the in-flight snapshot would lose
        # its undo entry once the screen rebuilds.
        self._settle_name()
        self._flush_pending_snapshot()
        self._flush_save_now()

    def _settle_name(self):
        """Make the typed program name unique, once the user is done typing.

        ``_set_name`` deliberately does NOT dedupe per keystroke: typing
        "Farm" while another "Farm" exists would rewrite the field to
        "Farm (2)" under the user's cursor after the "F". The invariant is
        applied here instead, on the way out, which is the point the list
        (and its trigger+name-keyed run bookkeeping) has to be consistent
        again.
        """
        p = self._program()
        if p is None:
            return
        mgr = App.get_running_app().engine.scripts
        self.editor_title = mgr.rename_program(p, p.name)

    def refresh(self):
        """BaseScreen per-tick entry point."""
        self.refresh_scripts()

    def refresh_scripts(self):
        """Per-tick TopBar refresh + Run/Stop button state.

        We intentionally DON'T rebuild the editor body — that would wipe
        TextInput and inline picker state while the user is mid-edit.
        ``is_running`` is cheap to recompute and only flips the toolbar
        button, so we keep it live."""
        self._update_top_bar()
        self._refresh_running_state()

    def _refresh_running_state(self):
        """is_running drives the Run/Stop toggle. It's True iff:

           - the program is enabled with an auto-firing trigger, OR
           - this same program is currently mid force-run in the
             background thread (so Stop = cancel that run).
        """
        p = self._program()
        if p is None:
            self.is_running = False
            return
        auto = (p.enabled
                and p.trigger in (Trigger.ON_BATTLE_END, Trigger.ON_TICK))
        engine = App.get_running_app().engine
        async_for_me = (engine.scripts.async_running_name() == p.name)
        self.is_running = bool(auto or async_for_me)

    def _program(self) -> Program | None:
        app = App.get_running_app()
        if self.program_index < 0:
            return None
        progs = app.engine.scripts.programs
        if self.program_index >= len(progs):
            return None
        return progs[self.program_index]

    def _build(self):
        body = self.ids.get("editor_body")
        if body is None:
            return
        body.clear_widgets()
        p = self._program()
        if p is None:
            self.editor_title = ""
            self.is_running = False
            body.add_widget(Label(text=t("scr_program_not_found")))
            return
        self.editor_title = p.name
        self._refresh_running_state()

        # Name edit
        ti_name = TextInput(text=p.name, multiline=False,
                              size_hint_y=None, height=dp(36),
                              font_size="13sp")
        ti_name.bind(text=lambda *_: self._set_name(p, ti_name.text))
        body.add_widget(ti_name)

        # Trigger settings
        body.add_widget(self._sub_label(t("scr_when_label")))
        body.add_widget(TriggerPicker(
            current=p.trigger,
            on_pick=lambda new: self._set_trigger(p, new),
        ))
        if p.trigger == Trigger.ON_TICK:
            body.add_widget(self._sub_label(t("scr_tick_seconds")))
            ti_int = TextInput(text=str(p.tick_interval), multiline=False,
                                size_hint_y=None, height=dp(36),
                                font_size="12sp")
            ti_int.bind(text=lambda *_: self._set_interval(p, ti_int.text))
            body.add_widget(ti_int)

        # ops_per_sec: visible only for on_demand programs (this is the
        # throttle for the background Run thread, which only on_demand
        # programs use — auto-firing triggers stay synchronous and use
        # default Interpreter caps).
        if p.trigger == Trigger.ON_DEMAND:
            body.add_widget(self._sub_label(t("scr_ops_per_sec_label"), h=44))
            ti_ops = TextInput(text=str(p.ops_per_sec), multiline=False,
                                size_hint_y=None, height=dp(36),
                                font_size="12sp")
            ti_ops.bind(text=lambda *_: self._set_ops_per_sec(p, ti_ops.text))
            body.add_widget(ti_ops)

        # Block tree
        self._render_body(p.body, body, depth=0, parent_list=p.body)
        if not p.body:
            body.add_widget(self._sub_label(t("scr_empty_body"), h=28))
        body.add_widget(self._add_button(p.body, depth=0))

    # ---------- recursive rendering ----------

    def _render_body(self, body_list: list, container: BoxLayout, depth: int,
                     parent_list: list, parent_kind: str = "top"):
        for idx, node in enumerate(body_list):
            container.add_widget(BlockCard(
                node, depth=depth,
                on_change=lambda _n: self._on_changed(),
                on_delete=lambda _l=parent_list, _i=idx: self._delete_block(_l, _i),
                on_move=lambda delta, _l=parent_list, _i=idx: self._move_block(_l, _i, delta),
            ))
            if isinstance(node, If):
                container.add_widget(self._sub_label(t("scr_then"),
                                                     indent=depth + 1))
                self._render_body(node.then_body, container,
                                   depth + 1, node.then_body, parent_kind="if-then")
                container.add_widget(self._add_button(
                    node.then_body, depth + 1, parent_kind="if-then"))
                container.add_widget(self._sub_label(t("scr_else"),
                                                     indent=depth + 1))
                self._render_body(node.else_body, container,
                                   depth + 1, node.else_body, parent_kind="if-else")
                container.add_widget(self._add_button(
                    node.else_body, depth + 1, parent_kind="if-else"))
            elif isinstance(node, While):
                self._render_body(node.body, container,
                                   depth + 1, node.body, parent_kind="while")
                container.add_widget(self._add_button(
                    node.body, depth + 1, parent_kind="while"))
            elif isinstance(node, ForEach):
                self._render_body(node.body, container,
                                   depth + 1, node.body, parent_kind="for")
                container.add_widget(self._add_button(
                    node.body, depth + 1, parent_kind="for"))

    def _sub_label(self, text_: str, indent: int = 0, h: int = 22) -> Label:
        # padding=(x, y) replaces the deprecated padding_x: each nested
        # level adds an extra dp(16) of indent so the tree depth is visible
        # without needing a dedicated indent widget per level.
        pad_x = dp(8 + indent * 16)
        return Label(
            text=text_, size_hint_y=None, height=dp(h),
            font_size="11sp", color=TEXT_SECONDARY,
            halign="left", valign="middle",
            text_size=(dp(CARD_TEXT_W), dp(h)),
            padding=(pad_x, 0),
        )

    # Suffixes shown after "+ block" to make clear which body the button
    # adds INTO. Without these all add-buttons looked identical, and users
    # tapping the one at the bottom of a while-loop were actually adding
    # to the TOP-LEVEL program body (sibling of the while), not inside.
    _ADD_SUFFIX = {
        "top":     "",
        "while":   " (in while)",
        "for":     " (in for)",
        "if-then": " (in then)",
        "if-else": " (in else)",
    }

    def _add_button(self, target_list: list, depth: int,
                    parent_kind: str = "top") -> BoxLayout:
        """Render a "+ block" button that explicitly names its parent body.

        Different button widths per depth because indented buttons need a
        bit more room for the "(in while)" suffix and we don't want the
        text to be ellipsis-clipped.
        """
        wrap = BoxLayout(size_hint_y=None, height=dp(34),
                          padding=[dp(8 + depth * 16), 0, 0, 0])
        label = t("scr_add_block") + self._ADD_SUFFIX.get(parent_kind, "")
        # Top-level buttons look slightly different (no parent annotation)
        # so the eye-tracking distinguishes "add to program" from "add to
        # child body". Background colour stays gold for both because both
        # are constructive actions.
        b = MinimalButton(
            text=label,
            icon_source="icons/ic_plus.png",
            size_hint_y=None, height=dp(30),
            size_hint_x=None, width=dp(220 if parent_kind != "top" else 148),
            font_size=12,
            btn_color=ACCENT_GOLD, text_color=BG_DARK,
        )

        def _add():
            open_block_palette(lambda new_node: (
                target_list.append(new_node),
                self._on_changed(),
                self._build(),
            ))
        b.bind(on_release=lambda *_: _add())
        wrap.add_widget(b)
        return wrap

    # ---------- mutations ----------

    def _delete_block(self, body_list: list, idx: int):
        if 0 <= idx < len(body_list):
            body_list.pop(idx)
            self._on_changed()
            self._build()

    def _move_block(self, body_list: list, idx: int, delta: int):
        new_idx = idx + delta
        if 0 <= new_idx < len(body_list):
            body_list[idx], body_list[new_idx] = body_list[new_idx], body_list[idx]
            self._on_changed()
            self._build()

    def _set_name(self, p: Program, new_name: str):
        new = new_name.strip()
        if new and new != p.name:
            p.name = new
            self.editor_title = new   # update TopBar binding
            self._on_changed()

    def _set_trigger(self, p: Program, new_trigger: str):
        if new_trigger != p.trigger and new_trigger in Trigger.ALL:
            p.trigger = new_trigger
            self._on_changed()
            self._refresh_running_state()
            self._build()

    def _set_interval(self, p: Program, text: str):
        try:
            v = int(text)
            if 1 <= v <= 3600:
                p.tick_interval = v
                self._on_changed()
        except ValueError:
            pass

    def _set_ops_per_sec(self, p: Program, text: str):
        """Set Program.ops_per_sec from a text field.

        ValueError (mid-typing empty or partial value) is silently
        ignored. Negatives clamp to 0 (= unlimited).
        """
        try:
            v = int(text)
            if v < 0:
                v = 0
            p.ops_per_sec = v
            self._on_changed()
        except ValueError:
            pass

    def _on_changed(self):
        self._schedule_save()
        # All mutations flow through here (BlockCard.on_change, expression
        # picker commits, trigger changes, etc.). Debounced snapshot so a
        # 5-keystroke value entry creates one undo entry, not five.
        self._schedule_snapshot()

    # ---------- undo / redo ----------

    def _take_snapshot(self, *, immediate: bool = False) -> None:
        """Push current Program state onto the undo stack.

        ``immediate=True`` skips the debounce — used on screen-enter to
        capture the baseline and on undo/redo to align stacks. Otherwise
        called via ``_schedule_snapshot`` so successive fast edits coalesce.

        Dedup'd: if the current state matches the last snapshot we skip
        — no point growing the stack with identical entries.
        """
        p = self._program()
        if p is None:
            return
        snap = p.to_dict()
        if snap == self._last_snapshot:
            return
        self._undo_stack.append(snap)
        if len(self._undo_stack) > UNDO_MAX:
            self._undo_stack.pop(0)
        self._last_snapshot = snap
        # A fresh action invalidates the redo branch — classic undo-tree
        # behaviour. The user can no longer "go forward" to a state they
        # already chose to diverge from.
        if self._redo_stack:
            self._redo_stack.clear()
        self.can_undo = len(self._undo_stack) > 1   # need 2+ to undo
        self.can_redo = bool(self._redo_stack)

    def _schedule_snapshot(self):
        if self._snapshot_clock is not None:
            self._snapshot_clock.cancel()
        self._snapshot_clock = Clock.schedule_once(
            lambda *_: self._take_snapshot(), SNAPSHOT_DEBOUNCE_S)

    def _flush_pending_snapshot(self):
        """Force any debounced snapshot to fire NOW.

        Called before undo so an in-flight edit that hasn't snapshotted yet
        gets captured first — otherwise undo would jump over it and lose
        the user's most recent change.
        """
        if self._snapshot_clock is not None:
            self._snapshot_clock.cancel()
            self._snapshot_clock = None
            self._take_snapshot(immediate=True)

    def _restore_snapshot(self, snap: dict) -> None:
        """Replace the current Program with one rebuilt from ``snap``.

        Preserves ``enabled`` because it's a runtime flag, not part of the
        edit history — undoing an edit shouldn't accidentally re-enable a
        program the user has explicitly stopped (or vice versa). The
        program is replaced in-place at the same index so other screens
        still find it.
        """
        mgr = App.get_running_app().engine.scripts
        if not (0 <= self.program_index < len(mgr.programs)):
            return
        cur = mgr.programs[self.program_index]
        runtime_enabled = cur.enabled
        new_prog = Program.from_dict(snap)
        new_prog.enabled = runtime_enabled
        mgr.programs[self.program_index] = new_prog
        self._last_snapshot = snap
        self._schedule_save()
        self._refresh_running_state()
        self._build()

    def _undo(self):
        """Top toolbar Undo. See class docstring for stack semantics."""
        self._flush_pending_snapshot()
        if len(self._undo_stack) < 2:
            app = App.get_running_app()
            if hasattr(app, "show_toast"):
                app.show_toast(t("scr_undo_empty"))
            return
        # Top of undo IS the current state — move it to redo first, then
        # restore the new top.
        cur = self._undo_stack.pop()
        self._redo_stack.append(cur)
        prev = self._undo_stack[-1]
        self._restore_snapshot(prev)
        self.can_undo = len(self._undo_stack) > 1
        self.can_redo = True
        app = App.get_running_app()
        if hasattr(app, "show_toast"):
            app.show_toast(t("scr_undo_done"))

    def _redo(self):
        """Top toolbar Redo. Only possible if we just undid something."""
        if not self._redo_stack:
            app = App.get_running_app()
            if hasattr(app, "show_toast"):
                app.show_toast(t("scr_redo_empty"))
            return
        nxt = self._redo_stack.pop()
        self._undo_stack.append(nxt)
        self._restore_snapshot(nxt)
        self.can_undo = len(self._undo_stack) > 1
        self.can_redo = bool(self._redo_stack)
        app = App.get_running_app()
        if hasattr(app, "show_toast"):
            app.show_toast(t("scr_redo_done"))

    # ---------- toolbar callbacks (referenced from kv) ----------

    def _run_now(self):
        """Editor-top "Run" button.

        Semantics depend on trigger type:

        - ``on_battle_end`` / ``on_tick``: Run means "start firing". We set
          ``p.enabled = True`` so the program tickets on its natural cadence
          from now on. The button label/icon immediately flips to Stop via
          ``is_running``, giving the user a single toggle for the auto-loop.

        - ``on_demand``: Run means "execute once, right now". on_demand
          programs never fire on their own, so enabling them changes nothing
          — the only meaningful Run for them is a force ``run_on_demand``.
          ``is_running`` stays False for on_demand so the button stays
          "Run" even after a successful one-shot.

        For "force one-shot regardless of trigger" the user has the
        gear-menu's "Run now" on each program card.
        """
        p = self._program()
        if p is None:
            return
        engine = App.get_running_app().engine
        app = App.get_running_app()

        if p.trigger in (Trigger.ON_BATTLE_END, Trigger.ON_TICK):
            if p.enabled:
                # Defensive: button SHOULD have shown Stop. Re-sync state in
                # case is_running got out of date for some reason and bail.
                self._refresh_running_state()
                return
            p.enabled = True
            self._refresh_running_state()
            self._schedule_save()
            if hasattr(app, "show_toast"):
                app.show_toast(f"{p.name}: {t('scr_on')}")
            self._build()
            return

        # on_demand: kick off an async force-run on a worker thread so
        # the UI stays responsive. ops_per_sec on the program throttles
        # the loop; cancel via Stop (handled in _stop_now).
        def _on_done(err, stats):
            if err == "cancelled":
                if hasattr(app, "show_toast"):
                    app.show_toast(f"{p.name}: {t('scr_cancelled')}")
            elif err:
                Popup(title=t("scr_error_title"), content=Label(text=err),
                      size_hint=(0.7, 0.4)).open()
            else:
                _show_run_toast(p, stats)
            self._refresh_running_state()
            self._update_top_bar()
            self._schedule_save()
            self._build()

        _log.info(
            "[ScriptEditor] _run_now kicking off async for %r (trigger=%s, ops_per_sec=%d)",
            p.name, p.trigger, p.ops_per_sec,
        )
        kickoff_err = engine.scripts.run_on_demand_async(
            engine, p.name, on_done=_on_done, program=p)
        if kickoff_err:
            # Can't start (another script running, or bad name).
            _log.warning("[ScriptEditor] kickoff refused: %s", kickoff_err)
            if hasattr(app, "show_toast"):
                app.show_toast(f"{p.name}: {kickoff_err}")
            return
        # Visible feedback that the worker actually started — the user
        # complained "Run does nothing", so make it impossible to miss.
        if hasattr(app, "show_toast"):
            app.show_toast(f"{p.name}: started @ {p.ops_per_sec} ops/s")
        # Flip Run -> Stop immediately so the user can cancel the run
        # they just kicked off without waiting for the next tick.
        self._refresh_running_state()
        self._build()

    def _stop_now(self):
        """Counterpart to _run_now.

        Stop now means three different things depending on what's actually
        running for this program:

          * ``on_demand`` with an async force-run in flight → cancel that
            run (signal the worker thread to stop at its next _tick).
          * Auto-firing trigger with ``enabled=True`` → flip to disabled
            so it stops firing on its natural cadence.

        The order matters: if both could apply (e.g. the user enabled a
        program AND then somehow started an async run on it), cancelling
        the in-flight run takes priority since it's the more immediate
        user expectation.
        """
        p = self._program()
        if p is None:
            return
        engine = App.get_running_app().engine
        if engine.scripts.async_running_name() == p.name:
            engine.scripts.cancel_async()
            self._refresh_running_state()
            return
        if not p.enabled:
            return
        p.enabled = False
        self._refresh_running_state()
        self._schedule_save()
        app = App.get_running_app()
        if hasattr(app, "show_toast"):
            app.show_toast(f"{p.name}: {t('scr_off')}")
        self._build()

    def _open_log(self):
        p = self._program()
        if p is None:
            return
        mgr = App.get_running_app().engine.scripts
        open_run_log(p.name, mgr.last_run_for(p))
