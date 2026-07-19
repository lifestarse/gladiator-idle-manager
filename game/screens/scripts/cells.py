# Build: 2
"""Inline-editable cells for the Scratch-style script editor.

The whole point of this module is to KILL the popup chain. Before, editing a
single condition was:
    tap card -> popup "Edit block" -> button "Edit cond" -> popup "Edit expr"
    -> select category -> save -> save -> save  (5 taps)

After, expressions edit IN-PLACE: tap a pill -> picker expands right under it
-> pick value -> picker collapses. One tap per change.

Public widgets:
    ExpressionCell    — one Expression node (atomic OR compound)
    EnumPicker        — short list of localized choices (slot/class/source/...)
    TriggerPicker     — Trigger.ALL with localized labels
    BlockCard         — one Statement node with all its parameters inline
"""
from __future__ import annotations
from typing import Callable

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.behaviors import ButtonBehavior
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle

from game.localization import t
from game.theme import (
    BTN_PRIMARY, ACCENT_GOLD, ACCENT_RED, TEXT_PRIMARY, BG_DARK,
)
from game.widgets import MinimalButton, SafeTextInput as TextInput
from game.widgets._scroll import ScrollSafeButtonMixin

from game.scripting.ast_nodes import (
    Statement, Expression,
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
    BIN_OPS, UNARY_OPS, ITERABLE_SOURCES, WRITABLE_FIGHTER_FIELDS,
    GLOBAL_VAR_PATTERN,
)
from game.scripting.builtins import (
    BUILTIN_FIELDS, BUILTIN_ENGINE_FIELDS, BUILTIN_CALLS, BUILTIN_ACTIONS,
)
from game.scripting import labels as L
from .blocks import expr_str, summarize


# ---------- shared visual helpers ----------

# Colour of the expanded-picker background (slightly lighter than card bg)
PICKER_BG    = (0.16, 0.16, 0.20, 1)
PILL_BG      = (0.20, 0.20, 0.26, 1)
PILL_BG_HOT  = (0.28, 0.28, 0.36, 1)   # hover/expanded
SUB_LABEL    = (0.70, 0.75, 0.85, 1)


def _bg(widget, color):
    """Paint a rectangle that follows `widget.pos`/`widget.size` as the canvas bg."""
    with widget.canvas.before:
        Color(*color)
        widget._bg_rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *_: setattr(widget._bg_rect, "pos", widget.pos),
        size=lambda *_: setattr(widget._bg_rect, "size", widget.size),
    )


def _section_label(text_, h=22):
    l = Label(
        text=text_, size_hint_y=None, height=dp(h),
        font_size="11sp", color=SUB_LABEL,
        halign="left", valign="middle",
    )
    l.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
    return l


def _pill_button(text_, on_release, color=None, h=32, padding=(8, 2)):
    """Compact tappable pill used inside the inline editor."""
    b = MinimalButton(
        text=text_, size_hint_y=None, height=dp(h), font_size=12,
        btn_color=color or BTN_PRIMARY,
        text_color=BG_DARK if color is ACCENT_GOLD else TEXT_PRIMARY,
    )
    b.bind(on_release=lambda *_: on_release())
    return b


# ---------- enum / source / trigger pickers ----------

class EnumPicker(BoxLayout):
    """Single-select horizontal picker for a small enum (~3-6 options).

    Each option is rendered as a pill — the current value's pill is highlighted.
    Tapping a pill commits immediately via the on_pick callback. No popup,
    no spinner — at this scale the row of pills is faster than a dropdown and
    keeps the surrounding context visible.
    """

    def __init__(self, options: tuple[str, ...], label_map: dict[str, str],
                 current: str, on_pick: Callable[[str], None], **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                          height=dp(32), spacing=dp(4), **kw)
        self._options = options
        self._label_map = label_map
        self._current = current
        self._on_pick = on_pick
        self._render()

    def _render(self):
        self.clear_widgets()
        for opt in self._options:
            is_cur = (opt == self._current)
            color = ACCENT_GOLD if is_cur else BTN_PRIMARY
            label_key = self._label_map.get(opt, opt)
            self.add_widget(_pill_button(
                t(label_key),
                lambda o=opt: self._pick(o),
                color=color, h=28,
            ))

    def _pick(self, opt: str):
        if opt == self._current:
            return
        self._current = opt
        self._render()
        self._on_pick(opt)


class TriggerPicker(BoxLayout):
    """Three-option picker for Trigger.ON_BATTLE_END / ON_TICK / ON_DEMAND."""

    def __init__(self, current: str, on_pick: Callable[[str], None], **kw):
        super().__init__(orientation="horizontal", size_hint_y=None,
                          height=dp(34), spacing=dp(4), **kw)
        self._current = current
        self._on_pick = on_pick
        self._render()

    def _render(self):
        self.clear_widgets()
        for trig in L.TRIGGER_ORDER:
            color = ACCENT_GOLD if trig == self._current else BTN_PRIMARY
            self.add_widget(_pill_button(
                t(L.TRIGGER_LABELS[trig]),
                lambda x=trig: self._pick(x),
                color=color, h=30,
            ))

    def _pick(self, trig: str):
        if trig == self._current:
            return
        self._current = trig
        self._render()
        self._on_pick(trig)


# ---------- expression cell ----------

# Categories shown in the expression picker. Order matches the picker rows.
EXPR_CATS: tuple[tuple[str, str], ...] = (
    ("value",          "scr_expr_cat_value"),
    ("var_local",      "scr_expr_cat_var_local"),
    ("var_global",     "scr_expr_cat_var_global"),
    ("field_fighter",  "scr_expr_cat_field_fighter"),
    ("field_engine",   "scr_expr_cat_field_engine"),
    ("op",             "scr_expr_cat_op"),
    ("call",           "scr_expr_cat_call"),
)


def _guess_category(expr) -> str:
    """Best-effort initial picker tab based on current expression type."""
    if isinstance(expr, Const):        return "value"
    if isinstance(expr, LocalVar):     return "var_local"
    if isinstance(expr, GlobalVar):    return "var_global"
    if isinstance(expr, EngineField):  return "field_engine"
    if isinstance(expr, FighterField): return "field_fighter"
    if isinstance(expr, BinOp):        return "op"
    if isinstance(expr, UnaryOp):      return "op"
    if isinstance(expr, Call):         return "call"
    return "value"


class ExpressionCell(BoxLayout):
    """Inline expression editor. See module docstring."""

    def __init__(self, expr: Expression, on_change: Callable[[Expression], None],
                 *, allow_op: bool = True, **kw):
        """
        :param expr:       initial expression
        :param on_change:  called every time the expression is replaced
        :param allow_op:   if False, picker hides the "BinOp/UnaryOp" tab.
                           Useful when the cell is itself an operand of an
                           op (prevents the user from nesting "a > b > c"
                           which can't parse).
        """
        super().__init__(orientation="vertical", size_hint_y=None,
                          spacing=dp(2), **kw)
        self.bind(minimum_height=self.setter("height"))
        self._expr = expr
        self._on_change = on_change
        self._allow_op = allow_op
        self._open = False
        self._render_collapsed()

    # ---------- external API ----------

    @property
    def expr(self) -> Expression:
        return self._expr

    def _commit(self, new_expr: Expression):
        self._expr = new_expr
        self._on_change(new_expr)
        # Stay open if compound (so user can keep editing operands), collapse
        # if atomic (no further sub-editing needed at this level).
        if isinstance(new_expr, (BinOp, UnaryOp)):
            self._render_compound()
            self._open = False
        else:
            self._render_collapsed()
            self._open = False

    # ---------- rendering ----------

    def _render_collapsed(self):
        self.clear_widgets()
        if isinstance(self._expr, (BinOp, UnaryOp)):
            self._render_compound()
            return
        pill = _pill_button(expr_str(self._expr),
                            on_release=self._toggle_picker,
                            color=BTN_PRIMARY, h=32)
        self.add_widget(pill)

    def _render_compound(self):
        """Render BinOp / UnaryOp as a horizontal row of sub-cells.

        Layout discipline (was a mess before, sub-cells overflowed):

            BinOp:    [ lhs    ] [op] [ rhs    ] [×]
                       flex 1    50dp  flex 1    24dp
            UnaryOp:  [op] [ operand            ] [×]
                       50dp  flex 1               24dp

        The operator pill has a fixed width so its label never gets squeezed.
        The unwrap "×" is also fixed but smaller — it's a recovery handle
        (drop the operator wrapper, keep the operand), not a primary action,
        so we don't want it competing with the op for tap-target space.
        """
        self.clear_widgets()
        row = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(36), spacing=dp(4))

        if isinstance(self._expr, BinOp):
            row.add_widget(ExpressionCell(
                self._expr.lhs,
                lambda new: self._update_binop_lhs(new),
                allow_op=False, size_hint_x=1,
            ))
            op_pill = _pill_button(
                t(L.OP_LABELS.get(self._expr.op, self._expr.op)),
                on_release=self._open_op_picker,
                color=ACCENT_GOLD, h=32,
            )
            op_pill.size_hint_x = None
            op_pill.width = dp(50)
            row.add_widget(op_pill)
            row.add_widget(ExpressionCell(
                self._expr.rhs,
                lambda new: self._update_binop_rhs(new),
                allow_op=False, size_hint_x=1,
            ))
        elif isinstance(self._expr, UnaryOp):
            op_pill = _pill_button(
                t(L.UNARY_OP_LABELS.get(self._expr.op, self._expr.op)),
                on_release=self._open_op_picker,
                color=ACCENT_GOLD, h=32,
            )
            op_pill.size_hint_x = None
            op_pill.width = dp(50)
            row.add_widget(op_pill)
            row.add_widget(ExpressionCell(
                self._expr.operand,
                lambda new: self._update_unary_operand(new),
                allow_op=False, size_hint_x=1,
            ))

        # Single unwrap "×" — collapses the operator, keeps the lhs (BinOp)
        # or the operand (UnaryOp). One handle per compound, not the two-
        # button cluster that confused users in the previous build.
        # PNG icon (PixelFont can't render the × glyph).
        unwrap = MinimalButton(
            text="", icon_source="icons/ic_close.png",
            size_hint_y=None, height=dp(28),
            size_hint_x=None, width=dp(28),
            btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
        )
        # Resolve the kept operand at TAP time, not render time: operand
        # sub-cells replace self._expr without re-rendering this row, so a
        # snapshot taken here would silently revert the user's last edit.
        unwrap.bind(on_release=lambda *_: self._commit(
            self._expr.lhs if isinstance(self._expr, BinOp)
            else self._expr.operand))
        row.add_widget(unwrap)
        self.add_widget(row)

    def _update_binop_lhs(self, new_lhs):
        self._expr = BinOp(self._expr.op, new_lhs, self._expr.rhs)
        self._on_change(self._expr)

    def _update_binop_rhs(self, new_rhs):
        self._expr = BinOp(self._expr.op, self._expr.lhs, new_rhs)
        self._on_change(self._expr)

    def _update_unary_operand(self, new_op):
        self._expr = UnaryOp(self._expr.op, new_op)
        self._on_change(self._expr)

    # ---------- picker ----------

    def _toggle_picker(self):
        if self._open:
            self._render_collapsed()
            self._open = False
            return
        self._open = True
        self.clear_widgets()

        # Compact header — one row: [current value text] [× close]
        # The label is read-only; the close icon explicitly collapses the
        # picker. Previously the header itself was a tappable pill that
        # duplicated the picker body's selection — visually noisy and
        # users tried clicking it to "open something" when it actually
        # closed the editor.
        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(32), spacing=dp(4))
        header_lbl = Label(
            text=expr_str(self._expr), size_hint_x=1,
            font_size="12sp", color=TEXT_PRIMARY, bold=True,
            halign="left", valign="middle",
        )
        header_lbl.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
        header.add_widget(header_lbl)
        close = MinimalButton(
            text="", icon_source="icons/ic_close.png",
            size_hint_x=None, width=dp(36),
            size_hint_y=None, height=dp(30),
            btn_color=BTN_PRIMARY, text_color=TEXT_PRIMARY,
        )
        close.bind(on_release=lambda *_: self._toggle_picker())
        header.add_widget(close)
        self.add_widget(header)

        # Category — single Spinner instead of 3 rows of 7 buttons. Same
        # information density, ~80px less vertical space, no confusion
        # about which button is "selected".
        cats = [c for c in EXPR_CATS if self._allow_op or c[0] != "op"]
        cat_labels = [t(ckey) for _cid, ckey in cats]
        # Best-guess initial category — same logic as before.
        initial_cid = _guess_category(self._expr)
        initial_label = t(dict(cats).get(initial_cid, cats[0][1]))
        self._cat_label_to_id = {t(ckey): cid for cid, ckey in cats}
        cat_spinner = Spinner(
            text=initial_label,
            values=cat_labels,
            size_hint_y=None, height=dp(36),
            font_size="12sp",
        )
        cat_spinner.bind(text=lambda _sp, val: self._show_category(
            self._cat_label_to_id.get(val, initial_cid)))
        self.add_widget(cat_spinner)

        # Category-specific body
        self._body = BoxLayout(orientation="vertical", size_hint_y=None,
                                spacing=dp(4), padding=[dp(4), dp(4)])
        self._body.bind(minimum_height=self._body.setter("height"))
        _bg(self._body, PICKER_BG)
        self.add_widget(self._body)
        self._show_category(initial_cid)

    def _open_op_picker(self):
        """Replace the picker body with an operator chooser. Mutates self._expr's
        op field directly when the user picks a new one."""
        self._open = True
        self.clear_widgets()
        self.add_widget(_pill_button(
            expr_str(self._expr), on_release=self._render_compound,
            color=PILL_BG_HOT, h=32,
        ))
        body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        body.bind(minimum_height=body.setter("height"))
        _bg(body, PICKER_BG)
        if isinstance(self._expr, BinOp):
            body.add_widget(_section_label(t("scr_pick_op")))
            ops_grid = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=dp(2))
            ops_grid.bind(minimum_height=ops_grid.setter("height"))
            current_row = BoxLayout(orientation="horizontal",
                                     size_hint_y=None, height=dp(30),
                                     spacing=dp(2))
            for i, op in enumerate(L.OP_ORDER):
                color = ACCENT_GOLD if op == self._expr.op else BTN_PRIMARY
                current_row.add_widget(_pill_button(
                    t(L.OP_LABELS[op]),
                    on_release=lambda o=op: self._set_binop_op(o),
                    color=color, h=28,
                ))
                if (i + 1) % 5 == 0:
                    ops_grid.add_widget(current_row)
                    current_row = BoxLayout(orientation="horizontal",
                                             size_hint_y=None, height=dp(30),
                                             spacing=dp(2))
            ops_grid.add_widget(current_row)
            body.add_widget(ops_grid)
        elif isinstance(self._expr, UnaryOp):
            body.add_widget(_section_label(t("scr_pick_op")))
            row = BoxLayout(orientation="horizontal", size_hint_y=None,
                             height=dp(30), spacing=dp(2))
            for op in ("not", "-"):
                color = ACCENT_GOLD if op == self._expr.op else BTN_PRIMARY
                row.add_widget(_pill_button(
                    t(L.UNARY_OP_LABELS[op]),
                    on_release=lambda o=op: self._set_unary_op(o),
                    color=color, h=28,
                ))
            body.add_widget(row)
        self.add_widget(body)

    def _set_binop_op(self, op: str):
        if op not in BIN_OPS:
            return
        self._expr = BinOp(op, self._expr.lhs, self._expr.rhs)
        self._on_change(self._expr)
        self._render_compound()

    def _set_unary_op(self, op: str):
        if op not in UNARY_OPS:
            return
        self._expr = UnaryOp(op, self._expr.operand)
        self._on_change(self._expr)
        self._render_compound()

    # ---------- per-category bodies ----------

    def _show_category(self, cat: str):
        self._body.clear_widgets()
        if cat == "value":
            self._cat_value()
        elif cat == "var_local":
            self._cat_var(local=True)
        elif cat == "var_global":
            self._cat_var(local=False)
        elif cat == "field_engine":
            self._cat_field_engine()
        elif cat == "field_fighter":
            self._cat_field_fighter()
        elif cat == "op":
            self._cat_op()
        elif cat == "call":
            self._cat_call()

    def _cat_value(self):
        cur_val = getattr(self._expr, "value", 0) if isinstance(self._expr, Const) else 0
        # Type pills
        type_pick = EnumPicker(
            options=("int", "bool", "str"),
            label_map={"int": "scr_inline_done", "bool": "scr_inline_done", "str": "scr_inline_done"},
            # We override labels manually so no JSON key is needed for the
            # raw type tags.
            current=("bool" if isinstance(cur_val, bool)
                     else "int" if isinstance(cur_val, int)
                     else "str"),
            on_pick=lambda t_: self._value_change(type_=t_),
        )
        # Replace localized labels with raw type tags (they're symbols, not text)
        for child, opt in zip(type_pick.children[::-1], type_pick._options):
            child.text = {"int": "123", "bool": "✓/✗", "str": '"abc"'}[opt]
        self._body.add_widget(_section_label("Type:"))
        self._body.add_widget(type_pick)
        # Value text field
        self._body.add_widget(_section_label(t("scr_pick_value")))
        ti = TextInput(text=str(cur_val), multiline=False,
                        size_hint_y=None, height=dp(36))
        ti.bind(text=lambda *_: self._value_change(text=ti.text))
        self._body.add_widget(ti)
        self._value_text = ti
        self._value_type = type_pick._current

    def _value_change(self, type_: str | None = None, text: str | None = None):
        if type_ is not None:
            self._value_type = type_
        if text is None:
            text = self._value_text.text if hasattr(self, "_value_text") else ""
        try:
            if self._value_type == "int":
                v = int(text) if text.strip() else 0
            elif self._value_type == "bool":
                v = text.strip().lower() in ("true", "1", "yes", "y", "✓")
            else:
                v = text
            self._expr = Const(v)
            self._on_change(self._expr)
        except (ValueError, TypeError):
            # silent — user is still typing
            pass

    def _cat_var(self, *, local: bool):
        cur = getattr(self._expr, "name", "f" if local else "counter")
        if not isinstance(self._expr, (LocalVar, GlobalVar)):
            cur = "f" if local else "counter"
        self._body.add_widget(_section_label(t("scr_expr_local_name")
                                              if local else t("scr_expr_global_name")))
        ti = TextInput(text=cur, multiline=False, size_hint_y=None, height=dp(36))
        def _save(*_):
            try:
                node = LocalVar(ti.text.strip() or ("f" if local else "x")) if local \
                       else GlobalVar(ti.text.strip() or "counter")
                self._expr = node
                self._on_change(self._expr)
            except ValueError:
                pass
        ti.bind(text=_save)
        self._body.add_widget(ti)
        _save()

    def _cat_field_engine(self):
        cur = getattr(self._expr, "field_name", "gold") \
            if isinstance(self._expr, EngineField) else "gold"
        self._body.add_widget(_section_label(t("scr_pick_field")))
        opts = sorted(BUILTIN_ENGINE_FIELDS)
        loc_to_int = {t(L.ENGINE_FIELD_LABELS.get(o, o)): o for o in opts}
        cur_label = t(L.ENGINE_FIELD_LABELS.get(cur, cur))
        sp = Spinner(text=cur_label, values=sorted(loc_to_int.keys()),
                     size_hint_y=None, height=dp(36))

        def _save(*_):
            internal = loc_to_int.get(sp.text, cur)
            field = EngineField(internal)
            # Auto-wrap numeric fields in BinOp(">=", field, Const(0)) IFF
            # this cell isn't already part of a compound (allow_op==True)
            # and the user's previous state wasn't already a compound that
            # we'd be clobbering. Net effect: clicking "Gold" in a fresh
            # IF condition produces `Gold >= 0` ready to be edited to e.g.
            # `Gold >= 1000`, instead of a bare `Gold` integer.
            if (self._allow_op and internal in L.NUMERIC_ENGINE_FIELDS
                    and not isinstance(self._expr, (BinOp, UnaryOp))):
                self._commit(BinOp(">=", field, Const(0)))
            else:
                self._expr = field
                self._on_change(self._expr)
        sp.bind(text=_save)
        self._body.add_widget(sp)
        _save()

    def _cat_field_fighter(self):
        cur_var = "f"
        cur_field = "hp"
        if isinstance(self._expr, FighterField):
            if isinstance(self._expr.fighter, LocalVar):
                cur_var = self._expr.fighter.name
            cur_field = self._expr.field_name
        self._body.add_widget(_section_label(t("scr_expr_fighter_var")))
        ti_var = TextInput(text=cur_var, multiline=False, size_hint_y=None, height=dp(36),
                            hint_text=t("scr_expr_fighter_hint"))
        self._body.add_widget(ti_var)
        self._body.add_widget(_section_label(t("scr_pick_field")))
        opts = sorted(BUILTIN_FIELDS.keys())
        loc_to_int = {t(L.FIGHTER_FIELD_LABELS.get(o, o)): o for o in opts}
        cur_label = t(L.FIGHTER_FIELD_LABELS.get(cur_field, cur_field))
        sp = Spinner(text=cur_label, values=sorted(loc_to_int.keys()),
                     size_hint_y=None, height=dp(36))

        # Track whether we've already auto-wrapped during this picker session
        # so typing into the fighter-var TextInput doesn't keep re-wrapping
        # (each keystroke fires _save).
        _wrapped = {"done": False}

        def _save(*_):
            name = ti_var.text.strip() or "f"
            internal = loc_to_int.get(sp.text, cur_field)
            field = FighterField(LocalVar(name), internal)
            # Auto-wrap numeric fighter fields (hp/stamina/level/etc.)
            # in BinOp so the user sees `f.Stamina >= 0` ready to compare,
            # not a bare field expression. Boolean fields (alive,
            # has_weapon, is_active) are left untouched — `if f.alive:`
            # is the natural form for those.
            should_wrap = (
                self._allow_op
                and internal in L.NUMERIC_FIGHTER_FIELDS
                and not _wrapped["done"]
                and not isinstance(self._expr, (BinOp, UnaryOp))
            )
            if should_wrap:
                _wrapped["done"] = True
                self._commit(BinOp(">=", field, Const(0)))
            else:
                self._expr = field
                self._on_change(self._expr)
        ti_var.bind(text=_save)
        sp.bind(text=_save)
        self._body.add_widget(sp)
        _save()

    def _cat_op(self):
        """Wrap current expression in a BinOp (or pick a unary)."""
        # Two buttons: "compare/calc (binary)" and "negate (unary)".
        msg = _section_label(t("scr_pick_op"))
        self._body.add_widget(msg)
        row = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(36), spacing=dp(4))
        row.add_widget(_pill_button(
            "a " + t(L.OP_LABELS[">="]) + " b",
            on_release=lambda: self._wrap_binop(">="),
            color=ACCENT_GOLD, h=32,
        ))
        row.add_widget(_pill_button(
            t(L.UNARY_OP_LABELS["not"]) + " a",
            on_release=lambda: self._wrap_unary("not"),
            color=ACCENT_GOLD, h=32,
        ))
        self._body.add_widget(row)

    def _wrap_binop(self, op: str):
        # Use current expr as lhs, Const(0) as rhs by default.
        self._commit(BinOp(op, self._expr, Const(0)))

    def _wrap_unary(self, op: str):
        self._commit(UnaryOp(op, self._expr))

    def _cat_call(self):
        cur_name = getattr(self._expr, "name", "len") \
            if isinstance(self._expr, Call) else "len"
        cur_args = getattr(self._expr, "args", []) \
            if isinstance(self._expr, Call) else []
        self._body.add_widget(_section_label(t("scr_expr_func")))
        opts = sorted(BUILTIN_CALLS.keys())
        loc_to_int = {t(L.CALL_LABELS.get(o, o)): o for o in opts}
        cur_label = t(L.CALL_LABELS.get(cur_name, cur_name))
        sp = Spinner(text=cur_label, values=sorted(loc_to_int.keys()),
                     size_hint_y=None, height=dp(36))
        def _save(*_):
            name = loc_to_int.get(sp.text, cur_name)
            # Current args, not the ones captured at category-open:
            # _update_call_arg replaces self._expr, and a later function
            # rename must not roll those arg edits back.
            if isinstance(self._expr, Call) and self._expr.args:
                args = list(self._expr.args)
            else:
                args = list(cur_args) if cur_args else [Const(0)]
            self._expr = Call(name, args)
            self._on_change(self._expr)
        sp.bind(text=_save)
        self._body.add_widget(sp)
        # Args list (one sub-cell per arg).
        self._body.add_widget(_section_label(t("scr_expr_args")))
        args_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        args_box.bind(minimum_height=args_box.setter("height"))
        args_now = list(cur_args) if cur_args else [Const(0)]
        if not args_now:
            args_now = [Const(0)]
        for i, a in enumerate(args_now):
            args_box.add_widget(ExpressionCell(
                a,
                lambda new, idx=i: self._update_call_arg(idx, new),
                allow_op=False,
            ))
        plus = _pill_button(
            "+ arg", on_release=lambda: self._call_add_arg(),
            color=BTN_PRIMARY, h=28,
        )
        plus.size_hint_x = None
        plus.width = dp(80)
        args_box.add_widget(plus)
        self._body.add_widget(args_box)
        self._call_args = args_now
        _save()

    def _update_call_arg(self, idx: int, new):
        if isinstance(self._expr, Call) and 0 <= idx < len(self._expr.args):
            new_args = list(self._expr.args)
            new_args[idx] = new
            self._expr = Call(self._expr.name, new_args)
            self._on_change(self._expr)

    def _call_add_arg(self):
        if isinstance(self._expr, Call):
            self._expr = Call(self._expr.name, list(self._expr.args) + [Const(0)])
            self._on_change(self._expr)
            self._show_category("call")


# ---------- block card ----------

class BlockCard(BoxLayout):
    """Visual + edit surface for one Statement node.

    The card shows a coloured stripe (category), a TAG (IF/FOR/DO/...), and
    an inline parameter editor below the title row — NO popup. Reorder/delete
    live in the right-edge buttons.
    """

    def __init__(self, node: Statement, depth: int,
                 *, on_change: Callable[[Statement], None],
                 on_delete: Callable[[], None],
                 on_move: Callable[[int], None],
                 **kw):
        super().__init__(orientation="vertical", size_hint_y=None,
                          spacing=dp(2),
                          padding=[dp(8 + depth * 16), dp(4), dp(8), dp(4)],
                          **kw)
        self.bind(minimum_height=self.setter("height"))
        self._node = node
        self._on_change = on_change
        self._on_delete = on_delete
        self._on_move = on_move
        self._build()

    def _build(self):
        self.clear_widgets()
        cat = L.category_of(self._node)
        col = L.CATEGORY_COLORS[cat]
        # Tinted background
        with self.canvas.before:
            Color(0.10, 0.10, 0.13, 1)
            self._bg1 = Rectangle(pos=self.pos, size=self.size)
            Color(col[0], col[1], col[2], 0.10)
            self._bg2 = Rectangle(pos=self.pos, size=self.size)
        def _resync(*_):
            self._bg1.pos = self.pos; self._bg1.size = self.size
            self._bg2.pos = self.pos; self._bg2.size = self.size
        self.bind(pos=_resync, size=_resync)

        # Title row: TAG + summary + reorder buttons
        title = BoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(32), spacing=dp(4))
        # Vertical stripe
        stripe = BoxLayout(size_hint_x=None, width=dp(4))
        with stripe.canvas.before:
            Color(*col)
            stripe._rect = Rectangle(pos=stripe.pos, size=stripe.size)
        stripe.bind(pos=lambda *_: setattr(stripe._rect, "pos", stripe.pos),
                    size=lambda *_: setattr(stripe._rect, "size", stripe.size))
        title.add_widget(stripe)
        # TAG
        tag = Label(text=self._tag_text(), size_hint_x=None, width=dp(48),
                     font_size="11sp", bold=True, color=col,
                     halign="center", valign="middle")
        tag.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
        title.add_widget(tag)
        # Summary
        summary = Label(text=summarize(self._node), font_size="12sp",
                         halign="left", valign="middle")
        summary.bind(size=lambda s, *_: setattr(s, "text_size", s.size))
        title.add_widget(summary)
        # Move up / down / delete — use PNG icons because PixelFont has no
        # arrow / cross glyphs (they'd render as "?" boxes otherwise).
        for icon_src, cb in (
            ("icons/ic_up.png",    lambda: self._on_move(-1)),
            ("icons/ic_down.png",  lambda: self._on_move(+1)),
            ("icons/ic_close.png", lambda: self._on_delete()),
        ):
            b = MinimalButton(text="", icon_source=icon_src,
                                size_hint_x=None, width=dp(32),
                                size_hint_y=None, height=dp(28),
                                btn_color=BTN_PRIMARY,
                                text_color=TEXT_PRIMARY)
            b.bind(on_release=lambda *_, fn=cb: fn())
            title.add_widget(b)
        self.add_widget(title)

        # Parameter editor (inline)
        self._add_params()

    def _tag_text(self) -> str:
        n = self._node
        if isinstance(n, If):       return "IF"
        if isinstance(n, While):    return "WHILE"
        if isinstance(n, ForEach):  return "FOR"
        if isinstance(n, Action):   return "DO"
        if isinstance(n, Assign):   return "SET"
        if isinstance(n, Break):    return "BRK"
        if isinstance(n, Continue): return "CONT"
        return "?"

    def _add_params(self):
        n = self._node
        if isinstance(n, If):
            self._param_label(t("scr_block_cond"))
            self.add_widget(ExpressionCell(
                n.cond,
                lambda new: (setattr(n, "cond", new), self._on_change(n)),
            ))
        elif isinstance(n, While):
            self._param_label(t("scr_block_cond"))
            self.add_widget(ExpressionCell(
                n.cond,
                lambda new: (setattr(n, "cond", new), self._on_change(n)),
            ))
        elif isinstance(n, ForEach):
            # var_name + source on one row
            row = BoxLayout(orientation="horizontal", size_hint_y=None,
                             height=dp(36), spacing=dp(4))
            ti = TextInput(text=n.var_name, multiline=False,
                            size_hint_x=0.4, size_hint_y=None, height=dp(36))
            ti.bind(text=lambda *_: (setattr(n, "var_name", ti.text or "f"),
                                       self._on_change(n)))
            row.add_widget(ti)
            row.add_widget(Label(text=t("scr_kw_in"), size_hint_x=None, width=dp(24),
                                  font_size="11sp"))
            # source picker
            loc_to_int = {t(L.SOURCE_LABELS[s]): s for s in L.SOURCE_ORDER}
            sp = Spinner(text=t(L.SOURCE_LABELS.get(n.source, n.source)),
                          values=[t(L.SOURCE_LABELS[s]) for s in L.SOURCE_ORDER],
                          size_hint_x=0.6, size_hint_y=None, height=dp(36))
            def _src_change(*_):
                new_src = loc_to_int.get(sp.text, n.source)
                if new_src in ITERABLE_SOURCES:
                    n.source = new_src
                    self._on_change(n)
            sp.bind(text=_src_change)
            row.add_widget(sp)
            self.add_widget(row)
            # where (optional filter)
            self._param_label(t("scr_block_filter"))
            if n.where is not None:
                self.add_widget(ExpressionCell(
                    n.where,
                    lambda new: (setattr(n, "where", new), self._on_change(n)),
                ))
                rm = _pill_button(
                    t("scr_block_remove_where"),
                    on_release=lambda: (setattr(n, "where", None),
                                         self._on_change(n), self._build()),
                    color=ACCENT_RED, h=28,
                )
                rm.size_hint_x = None
                rm.width = dp(140)
                self.add_widget(rm)
            else:
                add = _pill_button(
                    "+ " + t("scr_block_filter"),
                    on_release=lambda: (setattr(n, "where", Const(True)),
                                         self._on_change(n), self._build()),
                    color=BTN_PRIMARY, h=28,
                )
                add.size_hint_x = None
                add.width = dp(140)
                self.add_widget(add)
        elif isinstance(n, Assign):
            self._add_assign_params(n)
        elif isinstance(n, Action):
            self._add_action_params(n)
        # Break / Continue have no params

    def _param_label(self, text_):
        self.add_widget(_section_label(text_))

    def _add_assign_params(self, n: Assign):
        # target_kind picker (local / global / fighter_field)
        row = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(34), spacing=dp(4))
        for kind, label in (
            ("local",          t("scr_btn_assign_local")),
            ("global",         t("scr_btn_assign_global")),
            ("fighter_field",  t("scr_btn_assign_field")),
        ):
            color = ACCENT_GOLD if kind == n.target_kind else BTN_PRIMARY
            row.add_widget(_pill_button(
                label,
                on_release=lambda k=kind: self._set_assign_kind(n, k),
                color=color, h=30,
            ))
        self.add_widget(row)
        # Name editor
        if n.target_kind in ("local", "global"):
            self._param_label(
                t("scr_block_local_name") if n.target_kind == "local"
                else t("scr_block_global_name")
            )
            ti = TextInput(text=n.name, multiline=False, size_hint_y=None, height=dp(36))
            def _save_name(*_):
                new = ti.text.strip()
                if not new:
                    return
                if n.target_kind == "global":
                    import re
                    if not re.match(GLOBAL_VAR_PATTERN, new):
                        return
                n.name = new
                self._on_change(n)
            ti.bind(text=_save_name)
            self.add_widget(ti)
        elif n.target_kind == "fighter_field":
            self._param_label(t("scr_block_fighter_field"))
            opts = sorted(WRITABLE_FIGHTER_FIELDS)
            loc_to_int = {t(L.FIGHTER_FIELD_LABELS.get(o, o)): o for o in opts}
            sp = Spinner(
                text=t(L.FIGHTER_FIELD_LABELS.get(n.name, n.name)),
                values=sorted(loc_to_int.keys()),
                size_hint_y=None, height=dp(36),
            )
            def _save_field(*_):
                n.name = loc_to_int.get(sp.text, n.name)
                self._on_change(n)
            sp.bind(text=_save_field)
            self.add_widget(sp)
            # Fighter expression
            self._param_label(t("scr_expr_fighter_var"))
            self.add_widget(ExpressionCell(
                n.fighter or LocalVar("f"),
                lambda new: (setattr(n, "fighter", new), self._on_change(n)),
                allow_op=False,
            ))
        # Value expression
        self._param_label(t("scr_expr_value"))
        self.add_widget(ExpressionCell(
            n.value,
            lambda new: (setattr(n, "value", new), self._on_change(n)),
        ))

    def _set_assign_kind(self, n: Assign, kind: str):
        if kind == n.target_kind:
            return
        # Reset name to sensible default per kind so previous junk doesn't
        # leak through (e.g. switching from "fighter_field" with name="is_active"
        # to "local" should not leave the local var named "is_active").
        n.target_kind = kind
        if kind == "local":
            n.name = "x"
            n.fighter = None
        elif kind == "global":
            n.name = "counter"
            n.fighter = None
        elif kind == "fighter_field":
            n.name = next(iter(WRITABLE_FIGHTER_FIELDS), "is_active")
            n.fighter = LocalVar("f")
        self._on_change(n)
        self._build()

    def _add_action_params(self, n: Action):
        # Action name picker
        self._param_label(t("scr_block_action"))
        # Show current name as a pill that opens the palette grouped by cat.
        # The actual category palette is in popups.py; here we re-use it via
        # a side-effect-free callback.
        cur_meta = L.ACTION_META.get(n.name, {})
        label = t(cur_meta.get("label", n.name)) if cur_meta else n.name
        available = cur_meta.get("available", True) if cur_meta else True
        if not available:
            # In the card itself, the action name pill keeps its accent colour
            # (so it's still clearly the editable handle), but we append the
            # short unavailable tag inline so the user spots it at a glance
            # without opening the picker.
            label = label + "  " + t("scr_act_unavailable")
        pill = _pill_button(
            label,
            on_release=lambda: self._open_action_picker(n),
            color=ACCENT_GOLD, h=32,
        )
        self.add_widget(pill)
        desc_key = cur_meta.get("desc")
        if desc_key:
            self.add_widget(_section_label(t(desc_key), h=18))
        if not available:
            warn = Label(
                text="[!] " + t("scr_act_unavailable_long"),
                size_hint_y=None, height=dp(36), font_size="10sp",
                color=(0.95, 0.78, 0.40, 1),
                halign="left", valign="middle",
            )
            warn.bind(size=lambda s, *_: setattr(
                s, "text_size", (s.width - dp(8), s.height)))
            self.add_widget(warn)
        # Per-arg editors
        meta = L.ACTION_META.get(n.name, {})
        arg_labels = meta.get("arg_labels", [])
        spec = BUILTIN_ACTIONS.get(n.name, {})
        amin = spec.get("args", (0, 0))[0]
        # Pad / shrink args to spec.
        while len(n.args) < amin:
            n.args.append(Const(0))
        for i, a in enumerate(n.args):
            arg_key = arg_labels[i] if i < len(arg_labels) else None
            if arg_key is None:
                # Implicit fighter — show a small "f" label, not editable
                self._param_label(t("scr_expr_fighter_var"))
            else:
                self._param_label(t(arg_key))
            # Check for enum vocabulary
            vocab = L.ARG_VOCABULARIES.get((n.name, i))
            if vocab is not None:
                cur_val = a.value if isinstance(a, Const) else (
                    vocab[0]
                )
                if cur_val not in vocab:
                    cur_val = vocab[0]
                # Build label map dynamically. BUYABLE_SLOT_OPTIONS is a
                # subset of SLOT_OPTIONS and shares the same labels — we
                # treat both as "use SLOT_LABELS".
                if vocab is L.SLOT_OPTIONS or vocab is L.BUYABLE_SLOT_OPTIONS:
                    lmap = L.SLOT_LABELS
                elif vocab is L.CLASS_OPTIONS:
                    lmap = L.CLASS_LABELS
                else:
                    lmap = {v: v for v in vocab}
                self.add_widget(EnumPicker(
                    options=vocab, label_map=lmap, current=cur_val,
                    on_pick=lambda v, idx=i: self._set_action_arg_const(n, idx, v),
                ))
            else:
                self.add_widget(ExpressionCell(
                    a,
                    lambda new, idx=i: self._set_action_arg(n, idx, new),
                ))

    def _set_action_arg(self, n: Action, idx: int, new):
        if 0 <= idx < len(n.args):
            n.args[idx] = new
            self._on_change(n)

    def _set_action_arg_const(self, n: Action, idx: int, value):
        if 0 <= idx < len(n.args):
            n.args[idx] = Const(value)
            self._on_change(n)

    def _open_action_picker(self, n: Action):
        # Defer to popups.open_action_picker; that one is grouped by category
        # so 16 actions are tractable. The popup is a rare action (changing the
        # very kind of side-effect) so accepting a modal here is fine.
        from .popups import open_action_picker
        open_action_picker(
            current=n.name,
            on_pick=lambda new_name: self._switch_action(n, new_name),
        )

    def _switch_action(self, n: Action, new_name: str):
        """Replace action name and reset args to spec defaults."""
        from .popups import default_action_args
        n.name = new_name
        n.args = default_action_args(new_name)
        self._on_change(n)
        # Rebuild the card: the name pill and per-arg editors still show
        # the previous action otherwise (same pattern as _set_assign_kind).
        self._build()
        self._build()
