# Build: 6
"""ScriptsScreen + ScriptEditorScreen."""
from __future__ import annotations

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.core.clipboard import Clipboard

from game.base_screen import BaseScreen
from game.localization import t
from game.theme import (
    BTN_PRIMARY, ACCENT_GOLD, ACCENT_RED, TEXT_PRIMARY, BG_DARK,
)
from game.widgets import MinimalButton, SafeTextInput as TextInput
from game.widgets._scroll import ScrollSafeButtonMixin
from game.scripting.ast_nodes import (
    Program, Trigger, If, While, ForEach, Assign, Action, Break, Continue,
    Const, LocalVar,
)
from .blocks import summarize, is_control
from .popups import open_block_palette, open_block_editor


# Mindustry-flavoured category colours for block cards. Each block gets a
# bright vertical bar on the left + a faded tint of the same colour as
# background, so categories pop visually without sacrificing readability
# of the summary text on the dark theme.
CAT_IF       = (0.96, 0.62, 0.20, 1)   # orange — branching
CAT_WHILE    = (0.92, 0.40, 0.30, 1)   # red-orange — loop
CAT_FOREACH  = (0.95, 0.78, 0.20, 1)   # yellow — iteration
CAT_ACTION   = (0.85, 0.30, 0.30, 1)   # red — side effects
CAT_ASSIGN   = (0.30, 0.75, 0.45, 1)   # green — store value
CAT_FLOW     = (0.55, 0.55, 0.62, 1)   # gray — break/continue


def _category_color(node):
    if isinstance(node, If):
        return CAT_IF
    if isinstance(node, While):
        return CAT_WHILE
    if isinstance(node, ForEach):
        return CAT_FOREACH
    if isinstance(node, Action):
        return CAT_ACTION
    if isinstance(node, Assign):
        return CAT_ASSIGN
    if isinstance(node, (Break, Continue)):
        return CAT_FLOW
    return (0.40, 0.40, 0.45, 1)


def _category_tag(node) -> str:
    """Short uppercase keyword shown in the colored tag of the card."""
    if isinstance(node, If):       return "IF"
    if isinstance(node, While):    return "WHILE"
    if isinstance(node, ForEach):  return "FOR"
    if isinstance(node, Action):   return "DO"
    if isinstance(node, Assign):   return "SET"
    if isinstance(node, Break):    return "BRK"
    if isinstance(node, Continue): return "CONT"
    return "?"


# ---------- helpers ----------

def _btn(text, on_press=None, w=None, h=44, color=None, text_color=None):
    """Themed button. `color` defaults to BTN_PRIMARY (blue); pass
    ACCENT_GOLD for create/confirm, ACCENT_RED for destructive.
    """
    b = MinimalButton(
        text=text, size_hint_y=None, height=dp(h), font_size=12,
        btn_color=color or BTN_PRIMARY,
        text_color=text_color or (BG_DARK if color is ACCENT_GOLD else TEXT_PRIMARY),
    )
    if w is not None:
        b.size_hint_x = None
        b.width = dp(w)
    if on_press:
        b.bind(on_release=lambda *_: on_press())
    return b


class IconButton(ButtonBehavior, Image):
    """Square button rendering a PNG icon. Uses repo's existing icons/ assets."""
    def __init__(self, source, on_press=None, size=36, **kw):
        super().__init__(source=f"icons/{source}", fit_mode="contain",
                          size_hint=(None, None),
                          width=dp(size), height=dp(size), **kw)
        if on_press:
            self.bind(on_release=lambda *_: on_press())


def _icon_btn(source, on_press=None, size=36):
    return IconButton(source, on_press=on_press, size=size)


class BlockTapBody(ScrollSafeButtonMixin, ButtonBehavior, BoxLayout):
    """Horizontal row that fires its callback when tapped, but not when the
    finger is moving (scroll). Used as the tap-to-edit body of a block card.
    """
    def __init__(self, on_tap=None, **kw):
        super().__init__(orientation="horizontal", **kw)
        if on_tap:
            self.bind(on_release=lambda *_: on_tap())


def _hr():
    s = BoxLayout(size_hint_y=None, height=dp(1))
    with s.canvas:
        Color(0.3, 0.3, 0.35, 1)
        s._rect = Rectangle(pos=s.pos, size=s.size)
    s.bind(pos=lambda *_: setattr(s._rect, "pos", s.pos),
           size=lambda *_: setattr(s._rect, "size", s.size))
    return s


# ---------- Scripts list screen ----------

class ScriptsScreen(BaseScreen):
    """List of programs. Add/edit/delete/reorder/toggle/run."""

    def on_pre_enter(self, *args):
        self._build()

    def _build(self):
        self.clear_widgets()
        engine = App.get_running_app().engine
        mgr = engine.scripts

        root = BoxLayout(orientation="vertical")

        # Top bar
        top = BoxLayout(size_hint_y=None, height=dp(48), padding=dp(8), spacing=dp(6))
        top.add_widget(_btn(t("scr_back"), self._go_back, w=80, h=40))
        top.add_widget(Label(text=t("scripts_btn"), font_size="14sp", bold=True))
        top.add_widget(_btn(t("scr_new"), self._new_program, w=100, h=40,
                            color=ACCENT_GOLD))
        root.add_widget(top)

        # Export/Import strip
        ie = BoxLayout(size_hint_y=None, height=dp(36),
                        padding=[dp(8), 0], spacing=dp(6))
        ie.add_widget(_btn(t("scr_export_all"), self._export_all, h=32))
        ie.add_widget(_btn(t("scr_import"), self._import_dialog, h=32))
        root.add_widget(ie)
        root.add_widget(_hr())

        # List
        sv = ScrollView()
        col = BoxLayout(orientation="vertical", size_hint_y=None,
                        spacing=dp(6), padding=[dp(8), dp(8)])
        col.bind(minimum_height=col.setter("height"))

        if not mgr.programs:
            col.add_widget(Label(text=t("scr_no_programs"),
                                  size_hint_y=None, height=dp(40),
                                  font_size="12sp", color=(0.7, 0.7, 0.7, 1)))
        else:
            for i, p in enumerate(mgr.programs):
                col.add_widget(self._program_row(i, p, mgr))

        sv.add_widget(col)
        root.add_widget(sv)
        self.add_widget(root)

    def _program_row(self, idx: int, p: Program, mgr) -> BoxLayout:
        row = BoxLayout(orientation="vertical", size_hint_y=None,
                        padding=dp(6), spacing=dp(4))
        row.bind(minimum_height=row.setter("height"))
        with row.canvas.before:
            Color(0.13, 0.13, 0.16, 1)
            row._rect = Rectangle(pos=row.pos, size=row.size)
        row.bind(pos=lambda *_: setattr(row._rect, "pos", row.pos),
                 size=lambda *_: setattr(row._rect, "size", row.size))

        # Title line: name + trigger
        line1 = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(6))
        line1.add_widget(Label(text=p.name, font_size="13sp", bold=True,
                                halign="left", valign="middle",
                                text_size=(dp(180), dp(28))))
        line1.add_widget(Label(text=f"[{p.trigger}]", font_size="11sp",
                                color=(0.7, 0.8, 1, 1)))
        if p.trigger == Trigger.ON_TICK:
            line1.add_widget(Label(text=f"{p.tick_interval}с", font_size="10sp"))
        row.add_widget(line1)

        # Status: enabled + last error
        err = mgr.last_errors.get(f"{p.trigger}:{p.name}", "")
        status = f"{t('scr_on') if p.enabled else t('scr_off')} | {t('scr_blocks_count')}: {len(p.body)}"
        if err:
            status += f" | {t('scr_error')}: {err[:40]}"
        row.add_widget(Label(text=status, font_size="10sp", size_hint_y=None,
                              height=dp(20), color=(0.7, 0.7, 0.7, 1),
                              halign="left", valign="middle",
                              text_size=(dp(360), dp(20))))

        # Action buttons
        btns = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        btns.add_widget(_btn(t("scr_edit"), lambda i=idx: self._edit_program(i), h=32))
        btns.add_widget(_btn(t("scr_export"), lambda i=idx: self._export_one(i), h=32, w=60))
        btns.add_widget(_icon_btn("ic_play.png",  lambda i=idx: self._run_program(i), size=32))
        btns.add_widget(_icon_btn("ic_check.png" if p.enabled else "ic_close.png",
                                   lambda i=idx: self._toggle(i), size=32))
        btns.add_widget(_icon_btn("ic_up.png",    lambda i=idx: self._move(i, -1), size=32))
        btns.add_widget(_icon_btn("ic_down.png",  lambda i=idx: self._move(i, 1), size=32))
        btns.add_widget(_icon_btn("ic_close.png", lambda i=idx: self._delete(i), size=32))
        row.add_widget(btns)
        return row

    # ---------- actions ----------

    def _go_back(self):
        app = App.get_running_app()
        app.sm.current = "roster"

    def _new_program(self):
        # Prompt for name
        ti = TextInput(text=t("scr_default_program_name"), multiline=False,
                       size_hint_y=None, height=dp(36))
        trig = Spinner(text=Trigger.ON_BATTLE_END,
                       values=[Trigger.ON_BATTLE_END, Trigger.ON_TICK, Trigger.ON_DEMAND],
                       size_hint_y=None, height=dp(36))
        body = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        body.add_widget(Label(text=t("scr_program_name"), size_hint_y=None, height=dp(24), font_size="12sp"))
        body.add_widget(ti)
        body.add_widget(Label(text=t("scr_trigger"), size_hint_y=None, height=dp(24), font_size="12sp"))
        body.add_widget(trig)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        body.add_widget(btns)

        popup = Popup(title=t("scr_new_program_title"), content=body, size_hint=(0.85, 0.5))
        def _save():
            try:
                p = Program(name=ti.text or "untitled", trigger=trig.text)
                App.get_running_app().engine.scripts.add_program(p)
                popup.dismiss()
                self._build()
            except Exception:
                pass
        btns.add_widget(_btn(t("scr_create"), _save, color=ACCENT_GOLD))
        btns.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss()))
        popup.open()

    def _edit_program(self, idx):
        app = App.get_running_app()
        editor = app.sm.get_screen("script_editor")
        editor.program_index = idx
        app.sm.current = "script_editor"

    def _run_program(self, idx):
        engine = App.get_running_app().engine
        p = engine.scripts.programs[idx]
        err = engine.scripts.run_on_demand(engine, p.name)
        if err:
            Popup(title=t("scr_error_title"), content=Label(text=err),
                  size_hint=(0.7, 0.4)).open()
        self._build()

    def _toggle(self, idx):
        engine = App.get_running_app().engine
        p = engine.scripts.programs[idx]
        p.enabled = not p.enabled
        self._build()

    def _move(self, idx, delta):
        engine = App.get_running_app().engine
        engine.scripts.move_program(idx, delta)
        self._build()

    def _delete(self, idx):
        engine = App.get_running_app().engine
        engine.scripts.remove_program(idx)
        self._build()

    # ---------- import / export ----------

    def _export_one(self, idx):
        mgr = App.get_running_app().engine.scripts
        try:
            text = mgr.export_program_json(idx)
        except Exception as e:
            self._show_msg(t("scr_error_title"), str(e))
            return
        self._show_export_popup(text, t("scr_export_title"))

    def _export_all(self):
        mgr = App.get_running_app().engine.scripts
        text = mgr.export_all_json()
        self._show_export_popup(text, t("scr_export_all_title"))

    def _show_export_popup(self, text, title):
        body = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        ti = TextInput(text=text, readonly=True, font_size="11sp")
        body.add_widget(ti)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        def _copy():
            try:
                Clipboard.copy(text)
                self._show_msg("", t("scr_copied"))
            except Exception as e:
                self._show_msg(t("scr_error_title"), str(e))
        btns.add_widget(_btn(t("scr_copy"), _copy))
        btns.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss()))
        body.add_widget(btns)
        popup = Popup(title=title, content=body, size_hint=(0.92, 0.85))
        popup.open()

    def _import_dialog(self):
        body = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        body.add_widget(Label(text=t("scr_import_hint"),
                               size_hint_y=None, height=dp(36),
                               font_size="11sp", halign="left", valign="middle"))
        ti = TextInput(text="", font_size="11sp", hint_text="JSON ...")
        body.add_widget(ti)

        paste_btn = _btn(t("scr_paste"), None, h=36)
        def _paste():
            try:
                ti.text = Clipboard.paste() or ""
            except Exception:
                pass
        paste_btn.bind(on_release=lambda *_: _paste())
        body.add_widget(paste_btn)

        # Two-row buttons: replace bundle vs append, plus cancel
        row1 = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        row1.add_widget(_btn(t("scr_import_replace"),
                             lambda: self._do_import(ti.text, popup, replace=True),
                             color=ACCENT_RED))
        row1.add_widget(_btn(t("scr_import_merge"),
                             lambda: self._do_import(ti.text, popup, replace=False),
                             color=ACCENT_GOLD))
        body.add_widget(row1)
        body.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss(), h=40))

        popup = Popup(title=t("scr_import_title"), content=body,
                      size_hint=(0.92, 0.92))
        popup.open()

    def _do_import(self, text, popup, replace: bool):
        text = (text or "").strip()
        if not text:
            return
        engine = App.get_running_app().engine
        mgr = engine.scripts
        # Try bundle first, then single program.
        err_b = mgr.import_all_json(text, replace=replace)
        if err_b is None:
            engine.save()
            popup.dismiss()
            self._show_msg("", t("scr_imported_bundle", n=len(mgr.programs)))
            self._build()
            return
        err_p = mgr.import_program_json(text)
        if err_p is None:
            engine.save()
            popup.dismiss()
            self._show_msg("", t("scr_imported_program"))
            self._build()
            return
        # Both failed — surface the more informative error.
        self._show_msg(t("scr_error_title"), f"{err_b} / {err_p}")

    def _show_msg(self, title, msg):
        Popup(title=title or " ", content=Label(text=str(msg)),
              size_hint=(0.7, 0.4)).open()


# ---------- Editor screen ----------

class ScriptEditorScreen(BaseScreen):
    program_index = NumericProperty(-1)

    def on_pre_enter(self, *args):
        self._build()

    def _program(self) -> Program | None:
        app = App.get_running_app()
        if self.program_index < 0:
            return None
        progs = app.engine.scripts.programs
        if self.program_index >= len(progs):
            return None
        return progs[self.program_index]

    def _build(self):
        self.clear_widgets()
        p = self._program()
        if p is None:
            self.add_widget(Label(text=t("scr_program_not_found")))
            return

        root = BoxLayout(orientation="vertical")

        top = BoxLayout(size_hint_y=None, height=dp(48), padding=dp(8), spacing=dp(6))
        top.add_widget(_btn(t("scr_back"), self._go_back, w=80, h=40))
        top.add_widget(Label(text=p.name, font_size="14sp", bold=True))
        top.add_widget(_icon_btn("ic_play.png", self._run_now, size=40))
        root.add_widget(top)
        root.add_widget(_hr())

        # Settings strip
        settings = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6),
                              padding=[dp(8), 0])
        ti_name = TextInput(text=p.name, multiline=False, size_hint_y=None,
                             height=dp(32))
        trig = Spinner(text=p.trigger,
                       values=[Trigger.ON_BATTLE_END, Trigger.ON_TICK, Trigger.ON_DEMAND],
                       size_hint_y=None, height=dp(32))
        ti_int = TextInput(text=str(p.tick_interval), multiline=False,
                            size_hint_y=None, height=dp(32))
        settings.add_widget(ti_name)
        settings.add_widget(trig)
        settings.add_widget(ti_int)
        def _save_meta(*_):
            p.name = ti_name.text or p.name
            try:
                p.trigger = trig.text
            except Exception:
                pass
            try:
                v = int(ti_int.text)
                if 1 <= v <= 3600:
                    p.tick_interval = v
            except ValueError:
                pass
        ti_name.bind(text=_save_meta)
        trig.bind(text=_save_meta)
        ti_int.bind(text=_save_meta)
        root.add_widget(settings)
        root.add_widget(_hr())

        # Body — recursive render
        sv = ScrollView()
        body_col = BoxLayout(orientation="vertical", size_hint_y=None,
                              spacing=dp(2), padding=[dp(4), dp(4)])
        body_col.bind(minimum_height=body_col.setter("height"))
        self._render_body(p.body, body_col, depth=0, parent_list=p.body)
        sv.add_widget(body_col)
        root.add_widget(sv)

        self.add_widget(root)

    # ---------- recursive body rendering ----------

    def _render_body(self, body, container, depth: int, parent_list: list):
        for idx, node in enumerate(body):
            container.add_widget(self._make_block_card(node, idx, parent_list, depth))
            if isinstance(node, If):
                # then-body
                container.add_widget(self._sub_label(t("scr_then"), depth + 1))
                self._render_body(node.then_body, container, depth + 1, node.then_body)
                container.add_widget(self._add_button(node.then_body, depth + 1))
                # else-body
                container.add_widget(self._sub_label(t("scr_else"), depth + 1))
                self._render_body(node.else_body, container, depth + 1, node.else_body)
                container.add_widget(self._add_button(node.else_body, depth + 1))
            elif isinstance(node, (While, ForEach)):
                self._render_body(node.body, container, depth + 1, node.body)
                container.add_widget(self._add_button(node.body, depth + 1))
        if depth == 0:
            container.add_widget(self._add_button(parent_list, depth))

    def _sub_label(self, text, depth):
        l = Label(text=text, size_hint_y=None, height=dp(22),
                   font_size="11sp", color=(0.7, 0.8, 1, 1),
                   halign="left", valign="middle")
        l.text_size = (dp(400), dp(22))
        l.padding_x = dp(8 + depth * 16)
        return l

    def _add_button(self, target_list, depth):
        b = _btn(t("scr_add_block"), h=32, color=ACCENT_GOLD)
        b.size_hint_x = None
        b.width = dp(120)
        b.x = dp(8 + depth * 16)

        def _add():
            open_block_palette(lambda node: (target_list.append(node), self._build()))
        b.bind(on_release=lambda *_: _add())
        wrap = BoxLayout(size_hint_y=None, height=dp(34), padding=[dp(8 + depth * 16), 0, 0, 0])
        wrap.add_widget(b)
        return wrap

    def _make_block_card(self, node, idx, parent_list, depth):
        """Mindustry-style block card.

        Layout:  [colored bar][TAG][summary tap-to-edit][↑][↓][X]
        The whole text area is a tappable button — no separate Edit button.
        Reorder is via ↑/↓ buttons (drag-handle inside ScrollView fights with
        scroll gestures; explicit buttons match the script-list pattern).
        """
        cat_color = _category_color(node)
        wrap = BoxLayout(size_hint_y=None, height=dp(52), spacing=0,
                          padding=[dp(8 + depth * 16), dp(2), dp(8), dp(2)])
        # Faded category tint over a card-dark base
        with wrap.canvas.before:
            Color(0.10, 0.10, 0.13, 1)
            wrap._bg_rect = Rectangle(pos=wrap.pos, size=wrap.size)
            r, g, b, _ = cat_color
            Color(r, g, b, 0.10)
            wrap._tint_rect = Rectangle(pos=wrap.pos, size=wrap.size)

        def _resync(*_):
            wrap._bg_rect.pos = wrap.pos
            wrap._bg_rect.size = wrap.size
            wrap._tint_rect.pos = wrap.pos
            wrap._tint_rect.size = wrap.size
        wrap.bind(pos=_resync, size=_resync)

        # Vertical category bar (drawn inside its own widget so it stays
        # a sharp full-height stripe even as the card resizes).
        bar = BoxLayout(size_hint_x=None, width=dp(6))
        with bar.canvas.before:
            Color(*cat_color)
            bar._rect = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda *_: setattr(bar._rect, "pos", bar.pos),
                 size=lambda *_: setattr(bar._rect, "size", bar.size))
        wrap.add_widget(bar)

        # Tap-to-edit body: category tag + summary
        body = BlockTapBody(on_tap=lambda: self._edit_block(node))
        body.padding = [dp(8), 0, dp(4), 0]
        body.spacing = dp(6)

        tag = Label(
            text=_category_tag(node),
            size_hint_x=None, width=dp(48), height=dp(22),
            font_size="11sp", bold=True, color=cat_color,
            halign="center", valign="middle",
        )
        tag.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
        body.add_widget(tag)

        lbl = Label(text=summarize(node), font_size="12sp",
                     halign="left", valign="middle")
        lbl.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
        body.add_widget(lbl)

        wrap.add_widget(body)

        wrap.add_widget(_icon_btn("ic_up.png",
                                   lambda: self._reorder_block(parent_list, idx, -1),
                                   size=28))
        wrap.add_widget(_icon_btn("ic_down.png",
                                   lambda: self._reorder_block(parent_list, idx, 1),
                                   size=28))
        wrap.add_widget(_icon_btn("ic_close.png",
                                   lambda: (parent_list.pop(idx), self._build()),
                                   size=32))
        return wrap

    def _reorder_block(self, parent_list, idx, delta):
        new_idx = idx + delta
        if 0 <= new_idx < len(parent_list):
            parent_list[idx], parent_list[new_idx] = parent_list[new_idx], parent_list[idx]
            self._build()

    def _edit_block(self, node):
        open_block_editor(node, lambda new: self._build())

    def _run_now(self):
        p = self._program()
        if p is None:
            return
        engine = App.get_running_app().engine
        err = engine.scripts.run_on_demand(engine, p.name)
        if err:
            Popup(title=t("scr_error_title"), content=Label(text=err),
                  size_hint=(0.7, 0.4)).open()
        self._build()

    def _go_back(self):
        App.get_running_app().sm.current = "scripts"
