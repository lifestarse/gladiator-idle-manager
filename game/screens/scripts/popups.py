# Build: 7
"""Modal popups for the squad-script editor.

Old build had a deep popup chain (palette -> block editor -> expr editor) that
required up to 5 taps to change a single condition. That chain is GONE.
Inline editing lives in ``cells.py`` now.

What remains here is only those interactions that are inherently modal:

    open_block_palette(on_pick)
        Pick which kind of statement to add (IF / WHILE / FOR / Assign /
        Action / Break / Continue). Returns a freshly-built node.

    open_action_picker(current, on_pick)
        Pick which concrete Action to use (bench / activate / buy_item / ...),
        grouped by category with localized labels and descriptions.

    open_template_picker(on_apply)
        Pick a built-in program template to append to the program list.

    open_program_menu(...)
        Three-dot menu on a program card (run / enable-disable / rename /
        duplicate / export / delete).

    open_run_log(program_name, last_run)
        Dialog showing the last run's status, action count, error message.

    open_confirm(title, body, yes_label, on_yes)
        Generic destructive-confirm.

Helpers:

    default_action_args(name)  — build the AST default args for an action,
                                  used by BlockCard when the user switches the
                                  action type of an existing DO block.
    default_block(kind)        — build a fresh node for a given palette kind.
"""
from __future__ import annotations
import logging
from typing import Callable

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.metrics import dp

from game.localization import t
from game.theme import BTN_PRIMARY, ACCENT_GOLD, ACCENT_RED, TEXT_PRIMARY, BG_DARK
from game.widgets import MinimalButton, SafeTextInput as TextInput
from game.scripting.ast_nodes import (
    If, While, ForEach, Assign, Action, Break, Continue,
    Const, LocalVar, BinOp, FighterField,
)
from game.scripting.builtins import BUILTIN_ACTIONS
from game.scripting.ast_nodes import Program
from game.scripting import labels as L
from game.scripting import online_library
from game.scripting import templates as T

_log = logging.getLogger(__name__)

POPUP_BG = (0.10, 0.10, 0.12, 1)


# ---------- shared helpers ----------

def _btn(text_, on_press=None, color=None, h=44):
    b = MinimalButton(
        text=text_, size_hint_y=None, height=dp(h), font_size=12,
        btn_color=color or BTN_PRIMARY,
        text_color=BG_DARK if color is ACCENT_GOLD else TEXT_PRIMARY,
    )
    if on_press is not None:
        b.bind(on_release=lambda *_: on_press())
    return b


def _section(text_):
    l = Label(text=text_, size_hint_y=None, height=dp(24),
               font_size="12sp", bold=True,
               halign="left", valign="middle", color=(0.85, 0.88, 0.95, 1))
    l.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
    return l


# ---------- default node factories ----------

def default_action_args(name: str) -> list:
    """Build the default arg expressions for ``name`` per BUILTIN_ACTIONS spec.

    Mirrors the logic that used to live in ``popups._new_action`` but exposed
    publicly so BlockCard can rebuild args when the user switches the action
    type of an existing DO block.
    """
    spec = BUILTIN_ACTIONS.get(name)
    if spec is None:
        return []
    amin, _ = spec["args"]
    if "default_args" in spec:
        return list(spec["default_args"])
    args = []
    if spec.get("fighter_arg") and amin >= 1:
        args.append(LocalVar("f"))
        rest = list(spec.get("default_args_after_fighter", []))
        for i in range(amin - 1):
            args.append(rest[i] if i < len(rest) else Const(0))
    else:
        for _ in range(amin):
            args.append(Const(0))
    return args


def default_block(kind: str):
    """Build a fresh AST node for one of the palette categories."""
    if kind == "if":
        return If(cond=Const(True), then_body=[], else_body=[])
    if kind == "while":
        return While(cond=Const(False), body=[])
    if kind == "foreach":
        return ForEach(var_name="f", source="fighters", body=[], where=None)
    if kind == "assign_local":
        return Assign("local", "x", Const(0))
    if kind == "assign_global":
        return Assign("global", "counter", Const(0))
    if kind == "assign_field":
        return Assign("fighter_field", "is_active", Const(True), fighter=LocalVar("f"))
    if kind == "break":
        return Break()
    if kind == "continue":
        return Continue()
    if kind.startswith("action:"):
        name = kind.split(":", 1)[1]
        return Action(name=name, args=default_action_args(name))
    raise ValueError(f"unknown block kind: {kind!r}")


# ---------- block palette ----------

def open_block_palette(on_pick: Callable[[object], None]):
    """Pick which kind of statement to add. Calls on_pick(node) with the new
    AST node. Actions go through a follow-up picker (open_action_picker)
    instead of being flattened into this top-level list."""
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    sv = ScrollView()
    body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
    body.bind(minimum_height=body.setter("height"))

    def _close_then(node):
        on_pick(node)
        popup.dismiss()

    body.add_widget(_section(t("scr_cat_control")))
    body.add_widget(_btn(t("scr_btn_if"),
                          lambda: _close_then(default_block("if"))))
    body.add_widget(_btn(t("scr_btn_while"),
                          lambda: _close_then(default_block("while"))))
    body.add_widget(_btn(t("scr_btn_foreach"),
                          lambda: _close_then(default_block("foreach"))))

    body.add_widget(_section(t("scr_cat_actions")))
    # Open the action picker as a follow-up popup so 16 actions don't all
    # fit at once on a small screen.
    body.add_widget(_btn(
        t("scr_pick_action"),
        lambda: (popup.dismiss(),
                  open_action_picker(current=None,
                                      on_pick=lambda name: on_pick(default_block(f"action:{name}")))),
        color=ACCENT_GOLD,
    ))

    body.add_widget(_section(t("scr_cat_assign")))
    body.add_widget(_btn(t("scr_btn_assign_local"),
                          lambda: _close_then(default_block("assign_local"))))
    body.add_widget(_btn(t("scr_btn_assign_global"),
                          lambda: _close_then(default_block("assign_global"))))
    body.add_widget(_btn(t("scr_btn_assign_field"),
                          lambda: _close_then(default_block("assign_field"))))

    body.add_widget(_section(t("scr_cat_flow")))
    body.add_widget(_btn(t("scr_btn_break"),
                          lambda: _close_then(default_block("break"))))
    body.add_widget(_btn(t("scr_btn_continue"),
                          lambda: _close_then(default_block("continue"))))

    sv.add_widget(body)
    root.add_widget(sv)
    root.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss()))

    popup = Popup(title=t("scr_palette_title"), content=root,
                  size_hint=(0.90, 0.85), background_color=POPUP_BG)
    popup.open()


# ---------- action picker (for the "DO X" block) ----------

def open_action_picker(*, current: str | None,
                        on_pick: Callable[[str], None]):
    """Show all BUILTIN_ACTIONS grouped by category with localized labels."""
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    sv = ScrollView()
    body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
    body.bind(minimum_height=body.setter("height"))

    # Group action names by category
    by_cat: dict[str, list[str]] = {}
    for name, meta in L.ACTION_META.items():
        by_cat.setdefault(meta["cat"], []).append(name)

    for cat_id, cat_key in L.ACTION_CATEGORIES:
        names = sorted(by_cat.get(cat_id, []))
        if not names:
            continue
        body.add_widget(_section(t(cat_key)))
        for name in names:
            meta = L.ACTION_META[name]
            available = meta.get("available", True)
            # Visual cue for no-op actions: keep them pickable (the user might
            # be building a script for a future game build, or just want the
            # syntax in place) but mark them clearly so they don't waste time
            # debugging a silent fail. Gray text instead of normal accent.
            if available:
                color = ACCENT_GOLD if name == current else BTN_PRIMARY
            else:
                color = (0.35, 0.35, 0.40, 1)
            row = BoxLayout(orientation="vertical", size_hint_y=None,
                             spacing=dp(0))
            row.bind(minimum_height=row.setter("height"))
            label_text = t(meta["label"])
            if not available:
                label_text = label_text + "  " + t("scr_act_unavailable")
            row.add_widget(_btn(label_text,
                                 on_press=lambda n=name: (on_pick(n),
                                                           popup.dismiss()),
                                 color=color, h=36))
            desc_text = t(meta["desc"])
            if not available:
                # Long-form warning under the description so the user reads it
                # before tapping. Yellow-ish so it stands out from the regular
                # neutral description grey.
                desc_text = desc_text + "\n[!] " + t("scr_act_unavailable_long")
            desc = Label(text=desc_text, size_hint_y=None,
                          height=dp(28 if available else 56),
                          font_size="10sp",
                          color=(0.65, 0.7, 0.78, 1) if available
                                else (0.95, 0.78, 0.40, 1),
                          halign="left", valign="middle")
            desc.bind(size=lambda s, *_: setattr(s, "text_size",
                                                  (s.width - dp(8), s.height)))
            row.add_widget(desc)
            body.add_widget(row)

    sv.add_widget(body)
    root.add_widget(sv)
    root.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss()))

    popup = Popup(title=t("scr_pick_action"), content=root,
                  size_hint=(0.92, 0.92), background_color=POPUP_BG)
    popup.open()


# ---------- template picker ----------

def open_template_picker(on_apply: Callable[[object], None]):
    """Pick a built-in template. Calls on_apply(program) with a freshly built
    Program instance. The caller is responsible for actually appending it to
    the manager's list."""
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    sv = ScrollView()
    body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
    body.bind(minimum_height=body.setter("height"))

    def _pick(tmpl: T.Template):
        on_apply(tmpl.factory())
        popup.dismiss()

    for tmpl in T.TEMPLATES:
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                          padding=dp(6), spacing=dp(2))
        card.bind(minimum_height=card.setter("height"))
        card.add_widget(_btn(t(tmpl.name_key),
                              on_press=lambda x=tmpl: _pick(x),
                              color=ACCENT_GOLD, h=36))
        desc = Label(text=t(tmpl.desc_key), size_hint_y=None,
                      height=dp(36), font_size="10sp",
                      color=(0.65, 0.70, 0.78, 1),
                      halign="left", valign="middle")
        desc.bind(size=lambda s, *_: setattr(s, "text_size",
                                              (s.width - dp(8), s.height)))
        card.add_widget(desc)
        body.add_widget(card)

    sv.add_widget(body)
    root.add_widget(sv)
    root.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss()))

    popup = Popup(title=t("scr_tmpl_title"), content=root,
                  size_hint=(0.92, 0.92), background_color=POPUP_BG)
    popup.open()


# ---------- program three-dot menu ----------

def open_program_menu(
    *, program,
    on_run: Callable[[], None],
    on_toggle: Callable[[], None],
    on_rename: Callable[[str], None],
    on_duplicate: Callable[[], None],
    on_export: Callable[[], None],
    on_delete: Callable[[], None],
    on_move_up: Callable[[], None],
    on_move_down: Callable[[], None],
):
    """Drop-in menu shown when the user taps the gear icon on a program card."""
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(4))

    def _wrap(fn):
        def _go():
            popup.dismiss()
            fn()
        return _go

    root.add_widget(_btn(t("scr_menu_run"), _wrap(on_run), color=ACCENT_GOLD, h=42))
    toggle_label = t("scr_menu_toggle_off" if program.enabled
                       else "scr_menu_toggle_on")
    root.add_widget(_btn(toggle_label, _wrap(on_toggle), h=40))

    # Rename: present an inline TextInput inside the menu rather than chain
    # another popup. Submit on the "Done" button.
    rename_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(40), spacing=dp(4))
    ti = TextInput(text=program.name, multiline=False, size_hint_y=None, height=dp(36))
    rename_row.add_widget(ti)
    rename_row.add_widget(_btn(t("scr_menu_rename"),
                                lambda: (on_rename(ti.text.strip() or program.name),
                                          popup.dismiss()),
                                h=36))
    root.add_widget(rename_row)

    root.add_widget(_btn(t("scr_menu_duplicate"), _wrap(on_duplicate), h=40))
    root.add_widget(_btn(t("scr_menu_export"), _wrap(on_export), h=40))
    row = BoxLayout(orientation="horizontal", size_hint_y=None,
                     height=dp(40), spacing=dp(4))
    row.add_widget(_btn(t("scr_menu_move_up"), _wrap(on_move_up), h=36))
    row.add_widget(_btn(t("scr_menu_move_down"), _wrap(on_move_down), h=36))
    root.add_widget(row)
    root.add_widget(_btn(t("scr_menu_delete"), _wrap(on_delete),
                          color=ACCENT_RED, h=42))
    root.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss(), h=36))

    popup = Popup(title=program.name, content=root,
                  size_hint=(0.85, 0.85), background_color=POPUP_BG)
    popup.open()


# ---------- run log ----------

def open_run_log(program_name: str, last_run):
    """Show one-program run history. ``last_run`` is a RunStats or None."""
    root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
    if last_run is None:
        root.add_widget(_section(t("scr_log_empty")))
    else:
        import time as _time
        age = int(_time.time() - last_run.ts)
        root.add_widget(_section(t("scr_last_run", s=age)))
        if last_run.error:
            root.add_widget(Label(
                text=t("scr_log_error", e=last_run.error),
                size_hint_y=None, height=dp(40), font_size="11sp",
                color=(1, 0.5, 0.5, 1),
                halign="left", valign="middle",
            ))
        else:
            root.add_widget(Label(
                text=t("scr_log_ok", n=last_run.actions_fired),
                size_hint_y=None, height=dp(28), font_size="11sp",
                color=(0.5, 1, 0.5, 1),
            ))
        root.add_widget(Label(
            text=f"{last_run.duration_ms:.1f} ms",
            size_hint_y=None, height=dp(20), font_size="10sp",
            color=(0.6, 0.7, 0.8, 1),
        ))
    root.add_widget(_btn(t("scr_inline_close"), lambda: popup.dismiss(),
                          color=ACCENT_GOLD, h=40))
    popup = Popup(title=t("scr_log_title") + " — " + program_name,
                  content=root, size_hint=(0.80, 0.45),
                  background_color=POPUP_BG)
    popup.open()


# ---------- confirm ----------

def open_confirm(title: str, body: str, yes_label: str,
                  on_yes: Callable[[], None],
                  yes_color=ACCENT_RED):
    root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
    msg = Label(text=body, font_size="12sp",
                 halign="center", valign="middle")
    msg.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
    root.add_widget(msg)
    row = BoxLayout(orientation="horizontal", size_hint_y=None,
                     height=dp(44), spacing=dp(8))
    row.add_widget(_btn(t("scr_confirm_no"), lambda: popup.dismiss(), h=42))
    row.add_widget(_btn(yes_label,
                         lambda: (popup.dismiss(), on_yes()),
                         color=yes_color, h=42))
    root.add_widget(row)
    popup = Popup(title=title, content=root,
                  size_hint=(0.80, 0.40), background_color=POPUP_BG)
    popup.open()


# ---------- export / import (kept from old build, no chain through) ----------

def open_export_text(text: str, title: str):
    """Show a read-only JSON blob with Copy / Close. Same as before but isolated
    from the editor's edit chain."""
    from kivy.core.clipboard import Clipboard
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    ti = TextInput(text=text, readonly=True, font_size="11sp")
    root.add_widget(ti)
    row = BoxLayout(orientation="horizontal", size_hint_y=None,
                     height=dp(44), spacing=dp(6))
    def _copy():
        try:
            Clipboard.copy(text)
        except Exception as exc:  # noqa: BLE001 - provider-specific; must not kill the popup
            _log.warning("[scripts] clipboard copy failed: %s", exc)
    row.add_widget(_btn(t("scr_copy"), _copy, color=ACCENT_GOLD, h=42))
    row.add_widget(_btn(t("scr_inline_close"), lambda: popup.dismiss(), h=42))
    root.add_widget(row)
    popup = Popup(title=title, content=root,
                  size_hint=(0.92, 0.85), background_color=POPUP_BG)
    popup.open()


def open_online_library(on_apply: Callable[[Program], None]):
    """Browse the community scripts library hosted on GitHub Pages.

    Fetch happens on a worker thread (UI doesn't freeze on the timeout).
    The popup shows a "Loading..." state immediately, then swaps to the
    real list when the worker reports back via Clock.schedule_once.

    on_apply(program) is invoked with a freshly-built Program when the
    user taps Apply on any entry. The caller is responsible for actually
    appending it to the manager — same contract as open_template_picker.
    """
    import threading
    from kivy.clock import Clock

    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))

    # ---- initial loading state ----
    loading_lbl = Label(
        text=t("scr_online_loading"),
        size_hint_y=None, height=dp(48),
        font_size="13sp", halign="center", valign="middle",
        color=(0.8, 0.85, 0.95, 1),
    )
    loading_lbl.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
    root.add_widget(loading_lbl)

    # Bottom buttons (Reload + Close) created up front so we can wire them
    # immediately and the user can dismiss the popup even mid-load.
    btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
    reload_btn = _btn(t("scr_online_reload"), None, h=42)
    cancel_btn = _btn(t("scr_inline_close"), None, h=42)
    btn_row.add_widget(reload_btn)
    btn_row.add_widget(cancel_btn)
    root.add_widget(btn_row)

    popup = Popup(title=t("scr_online_title"), content=root,
                  size_hint=(0.94, 0.94), background_color=POPUP_BG)
    cancel_btn.bind(on_release=lambda *_: popup.dismiss())

    def _render(payload):
        """Replace the loading label with the scripts list (or an
        offline message if payload is None). Called on the main thread
        via Clock.schedule_once."""
        # Strip out everything above the button row so a Reload click
        # cleanly re-renders without piling content.
        for child in list(root.children):
            if child is btn_row:
                continue
            root.remove_widget(child)

        if payload is None:
            offline = Label(
                text=t("scr_online_offline"),
                size_hint_y=None, height=dp(60),
                font_size="12sp", halign="center", valign="middle",
                color=(1, 0.7, 0.5, 1),
            )
            offline.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
            # Insert at position 1 so it lands ABOVE the button row.
            root.add_widget(offline, index=len(root.children))
            return

        scripts = payload.get("scripts", [])
        # Top: small header with manifest's "updated" date and count.
        header = Label(
            text=t("scr_online_header",
                   n=len(scripts), updated=payload.get("updated", "?")),
            size_hint_y=None, height=dp(28),
            font_size="11sp", color=(0.6, 0.7, 0.85, 1),
            halign="left", valign="middle",
        )
        header.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
        root.add_widget(header, index=len(root.children))

        sv = ScrollView()
        body = BoxLayout(orientation="vertical", size_hint_y=None,
                          spacing=dp(8), padding=[0, dp(4)])
        body.bind(minimum_height=body.setter("height"))

        for entry in scripts:
            card = BoxLayout(orientation="vertical", size_hint_y=None,
                              padding=dp(6), spacing=dp(2))
            card.bind(minimum_height=card.setter("height"))
            title_line = t(
                "scr_online_card_title",
                title=entry.get("title", "?"),
                author=entry.get("author", "anon"),
            )

            def _make_apply(e=entry):
                def _do():
                    try:
                        prog = Program.from_dict(e["program"])
                    except Exception as exc:
                        Popup(title=t("scr_error_title"),
                              content=Label(text=str(exc)),
                              size_hint=(0.7, 0.4)).open()
                        return
                    on_apply(prog)
                    popup.dismiss()
                return _do

            card.add_widget(_btn(
                title_line, _make_apply(), color=ACCENT_GOLD, h=38))
            desc = Label(
                text=entry.get("description", ""),
                size_hint_y=None, height=dp(36),
                font_size="10sp", color=(0.65, 0.7, 0.78, 1),
                halign="left", valign="middle",
            )
            desc.bind(size=lambda s, *_:
                       setattr(s, "text_size", (s.width - dp(8), s.height)))
            card.add_widget(desc)
            tags = entry.get("tags", [])
            if tags:
                tag_lbl = Label(
                    text=" · ".join(tags),
                    size_hint_y=None, height=dp(20),
                    font_size="10sp", color=(0.5, 0.6, 0.75, 1),
                    halign="left", valign="middle",
                )
                tag_lbl.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
                card.add_widget(tag_lbl)
            body.add_widget(card)

        sv.add_widget(body)
        # Insert at index=len(root.children) places it just before the
        # last child (button row), i.e. above it visually.
        root.add_widget(sv, index=1)

    def _fetch(force_refresh: bool):
        def _worker():
            payload = online_library.get_library(force_refresh=force_refresh)
            Clock.schedule_once(lambda *_: _render(payload), 0)
        threading.Thread(target=_worker, daemon=True).start()

    def _reload(*_):
        # Restore the loading label and re-fetch ignoring cache.
        for child in list(root.children):
            if child is btn_row:
                continue
            root.remove_widget(child)
        root.add_widget(loading_lbl, index=len(root.children))
        _fetch(force_refresh=True)

    reload_btn.bind(on_release=_reload)

    popup.open()
    _fetch(force_refresh=False)


def open_import_dialog(on_import: Callable[[str, bool], str | None]):
    """Paste-or-type JSON of a single program or a bundle. ``on_import(text,
    replace)`` should return ``None`` on success or an error message string.
    """
    from kivy.core.clipboard import Clipboard
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    root.add_widget(Label(text=t("scr_import_hint"),
                           size_hint_y=None, height=dp(40),
                           font_size="11sp", halign="left", valign="middle"))
    ti = TextInput(text="", font_size="11sp", hint_text="JSON ...")
    root.add_widget(ti)

    def _paste():
        try:
            ti.text = Clipboard.paste() or ""
        except Exception as exc:  # noqa: BLE001 - provider-specific; must not kill the popup
            _log.warning("[scripts] clipboard paste failed: %s", exc)
    root.add_widget(_btn(t("scr_paste"), _paste, h=36))

    err_label = Label(text="", size_hint_y=None, height=dp(28),
                       font_size="11sp", color=(1, 0.6, 0.6, 1),
                       halign="left", valign="middle")
    err_label.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
    root.add_widget(err_label)

    def _go(replace: bool):
        err = on_import(ti.text, replace)
        if err is None:
            popup.dismiss()
        else:
            err_label.text = err

    row = BoxLayout(orientation="horizontal", size_hint_y=None,
                     height=dp(44), spacing=dp(6))
    row.add_widget(_btn(t("scr_import_replace"),
                         lambda: _go(True), color=ACCENT_RED, h=42))
    row.add_widget(_btn(t("scr_import_merge"),
                         lambda: _go(False), color=ACCENT_GOLD, h=42))
    root.add_widget(row)
    root.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss(), h=36))

    popup = Popup(title=t("scr_import_title"), content=root,
                  size_hint=(0.92, 0.92), background_color=POPUP_BG)
    popup.open()
