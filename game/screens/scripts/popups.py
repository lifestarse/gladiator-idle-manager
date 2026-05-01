# Build: 5
"""Popups: pick block category/type, edit block parameters, edit expressions."""
from __future__ import annotations

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.metrics import dp

from game.localization import t
from game.theme import BTN_PRIMARY, ACCENT_GOLD, TEXT_PRIMARY, BG_DARK
from game.widgets import MinimalButton, SafeTextInput as TextInput
from game.scripting.ast_nodes import (
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
    BIN_OPS, UNARY_OPS, ITERABLE_SOURCES, WRITABLE_FIGHTER_FIELDS,
)
from game.scripting.builtins import (
    BUILTIN_FIELDS, BUILTIN_ENGINE_FIELDS, BUILTIN_ACTIONS, BUILTIN_CALLS,
)
from .blocks import expr_str

POPUP_BG = (0.1, 0.1, 0.12, 1)


# ---------- helpers ----------

def _btn(text, on_press=None, height=44, color=None):
    """Themed button matching the rest of the UI. `color` defaults to
    BTN_PRIMARY; pass ACCENT_GOLD for create/save/confirm.
    """
    b = MinimalButton(
        text=text, size_hint_y=None, height=dp(height), font_size=12,
        btn_color=color or BTN_PRIMARY,
        text_color=BG_DARK if color is ACCENT_GOLD else TEXT_PRIMARY,
    )
    if on_press:
        b.bind(on_release=lambda *_: on_press())
    return b


def _label(text, h=28, bold=False):
    l = Label(text=text, size_hint_y=None, height=dp(h), font_size="12sp",
              halign="left", valign="middle", bold=bold)
    l.bind(size=lambda s, value: setattr(s, "text_size", value))
    return l


# ---------- block category palette ----------

def open_block_palette(on_pick):
    """Open palette popup. on_pick(node) called with the new statement."""
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    sv = ScrollView()
    inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
    inner.bind(minimum_height=inner.setter("height"))

    # Control flow
    inner.add_widget(_label(t("scr_cat_control"), bold=True))
    inner.add_widget(_btn(t("scr_btn_if"), lambda: _finish(_new_if())))
    inner.add_widget(_btn(t("scr_btn_while"), lambda: _finish(_new_while())))
    inner.add_widget(_btn(t("scr_btn_foreach"), lambda: _finish(_new_foreach())))

    # Actions
    inner.add_widget(_label(t("scr_cat_actions"), bold=True))
    for name in BUILTIN_ACTIONS.keys():
        inner.add_widget(_btn(name, lambda n=name: _finish(_new_action(n))))

    # Assignments
    inner.add_widget(_label(t("scr_cat_assign"), bold=True))
    inner.add_widget(_btn(t("scr_btn_assign_local"),
                          lambda: _finish(Assign("local", "x", Const(0)))))
    inner.add_widget(_btn(t("scr_btn_assign_global"),
                          lambda: _finish(Assign("global", "counter", Const(0)))))
    inner.add_widget(_btn(t("scr_btn_assign_field"),
                          lambda: _finish(Assign("fighter_field", "is_active",
                                                 Const(True), fighter=LocalVar("f")))))

    # Flow control inside loops
    inner.add_widget(_label(t("scr_cat_flow"), bold=True))
    inner.add_widget(_btn(t("scr_btn_break"), lambda: _finish(Break())))
    inner.add_widget(_btn(t("scr_btn_continue"), lambda: _finish(Continue())))

    sv.add_widget(inner)
    root.add_widget(sv)
    cancel = _btn(t("scr_cancel"), lambda: popup.dismiss())
    root.add_widget(cancel)

    popup = Popup(title=t("scr_palette_title"), content=root,
                  size_hint=(0.88, 0.85), background_color=POPUP_BG)

    def _finish(node):
        on_pick(node)
        popup.dismiss()

    popup.open()


def _new_if():
    return If(cond=Const(True), then_body=[], else_body=[])


def _new_while():
    return While(cond=Const(False), body=[])


def _new_foreach():
    return ForEach(var_name="f", source="fighters", body=[], where=None)


def _new_action(name: str):
    """Create a fresh Action with reasonable default arg expressions.

    Priority for arg defaults:
      1. spec["default_args"]                    (full override)
      2. LocalVar("f") + spec["default_args_after_fighter"]
      3. fallback to Const(0) for every slot
    """
    spec = BUILTIN_ACTIONS[name]
    nargs_min, _ = spec["args"]
    if "default_args" in spec:
        return Action(name=name, args=list(spec["default_args"]))
    args = []
    if spec.get("fighter_arg") and nargs_min >= 1:
        args.append(LocalVar("f"))
        rest = list(spec.get("default_args_after_fighter", []))
        for i in range(nargs_min - 1):
            args.append(rest[i] if i < len(rest) else Const(0))
    else:
        for _ in range(nargs_min):
            args.append(Const(0))
    return Action(name=name, args=args)


# ---------- expression editor ----------

# (label_key, internal_id) — internal_id used in if/elif so logic is locale-independent.
EXPR_CATEGORIES = [
    ("scr_expr_const",   "const"),
    ("scr_expr_local",   "local"),
    ("scr_expr_global",  "global"),
    ("scr_expr_engine",  "engine"),
    ("scr_expr_fighter", "fighter"),
    ("scr_expr_binop",   "binop"),
    ("scr_expr_call",    "call"),
]


def open_expr_editor(current, on_done):
    """Edit a single Expression. on_done(new_expr) called on save."""
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    root.add_widget(_label(f"{t('scr_expr_current')}: {expr_str(current)}", h=32))

    cat_labels = [t(k) for k, _ in EXPR_CATEGORIES]
    label_to_id = {t(k): cid for k, cid in EXPR_CATEGORIES}

    cat_spinner = Spinner(text=t("scr_expr_type"), values=cat_labels,
                          size_hint_y=None, height=dp(36))
    root.add_widget(cat_spinner)

    body = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
    body.bind(minimum_height=body.setter("height"))
    sv = ScrollView()
    sv.add_widget(body)
    root.add_widget(sv)

    state = {"node": current}

    def _commit(node):
        state["node"] = node

    def _refresh(*_):
        body.clear_widgets()
        cat = label_to_id.get(cat_spinner.text)
        if cat == "const":
            ti_v = TextInput(text=str(getattr(current, "value", 0)),
                             multiline=False, size_hint_y=None, height=dp(36))
            type_sp = Spinner(text="int", values=["int", "bool", "str"],
                              size_hint_y=None, height=dp(36))
            body.add_widget(_label(t("scr_expr_value")))
            body.add_widget(ti_v)
            body.add_widget(_label(t("scr_expr_type")))
            body.add_widget(type_sp)
            def _save_const(*_):
                ty = type_sp.text
                v = ti_v.text
                try:
                    if ty == "int":
                        _commit(Const(int(v)))
                    elif ty == "bool":
                        _commit(Const(v.lower() in ("true", "1", "yes")))
                    else:
                        _commit(Const(v))
                except Exception:
                    pass
            ti_v.bind(text=_save_const)
            type_sp.bind(text=_save_const)
            _save_const()
        elif cat == "local":
            ti = TextInput(text=getattr(current, "name", "f") if isinstance(current, LocalVar) else "f",
                           multiline=False, size_hint_y=None, height=dp(36))
            body.add_widget(_label(t("scr_expr_local_name")))
            body.add_widget(ti)
            def _save(*_):
                if ti.text:
                    _commit(LocalVar(ti.text))
            ti.bind(text=_save)
            _save()
        elif cat == "global":
            ti = TextInput(text=getattr(current, "name", "n") if isinstance(current, GlobalVar) else "n",
                           multiline=False, size_hint_y=None, height=dp(36))
            body.add_widget(_label(t("scr_expr_global_name")))
            body.add_widget(ti)
            def _save(*_):
                try:
                    if ti.text:
                        _commit(GlobalVar(ti.text))
                except ValueError:
                    pass
            ti.bind(text=_save)
            _save()
        elif cat == "engine":
            sp = Spinner(text="gold", values=sorted(BUILTIN_ENGINE_FIELDS),
                         size_hint_y=None, height=dp(36))
            body.add_widget(_label(t("scr_expr_engine_field")))
            body.add_widget(sp)
            def _save(*_):
                _commit(EngineField(sp.text))
            sp.bind(text=_save)
            _save()
        elif cat == "fighter":
            ti = TextInput(text="f", multiline=False, size_hint_y=None, height=dp(36),
                           hint_text=t("scr_expr_fighter_hint"))
            sp = Spinner(text="hp", values=sorted(BUILTIN_FIELDS.keys()),
                         size_hint_y=None, height=dp(36))
            body.add_widget(_label(t("scr_expr_fighter_var")))
            body.add_widget(ti)
            body.add_widget(_label(t("scr_expr_field")))
            body.add_widget(sp)
            def _save(*_):
                _commit(FighterField(LocalVar(ti.text or "f"), sp.text))
            ti.bind(text=_save)
            sp.bind(text=_save)
            _save()
        elif cat == "binop":
            sp = Spinner(text=">=", values=sorted(BIN_OPS),
                         size_hint_y=None, height=dp(36))
            ti_l = TextInput(text=expr_str(getattr(current, "lhs", Const(0))),
                             multiline=False, size_hint_y=None, height=dp(36))
            ti_r = TextInput(text=expr_str(getattr(current, "rhs", Const(0))),
                             multiline=False, size_hint_y=None, height=dp(36))
            body.add_widget(_label(t("scr_expr_lhs")))
            body.add_widget(ti_l)
            body.add_widget(_label(t("scr_expr_op")))
            body.add_widget(sp)
            body.add_widget(_label(t("scr_expr_rhs")))
            body.add_widget(ti_r)
            def _save(*_):
                _commit(BinOp(sp.text, _parse_simple(ti_l.text), _parse_simple(ti_r.text)))
            sp.bind(text=_save)
            ti_l.bind(text=_save)
            ti_r.bind(text=_save)
            _save()
        elif cat == "call":
            sp = Spinner(text="len", values=sorted(BUILTIN_CALLS.keys()),
                         size_hint_y=None, height=dp(36))
            ti = TextInput(text="0", multiline=False, size_hint_y=None, height=dp(36),
                           hint_text=t("scr_expr_args_hint"))
            body.add_widget(_label(t("scr_expr_func")))
            body.add_widget(sp)
            body.add_widget(_label(t("scr_expr_args")))
            body.add_widget(ti)
            def _save(*_):
                args = [_parse_simple(p.strip()) for p in ti.text.split(",") if p.strip()]
                _commit(Call(sp.text, args))
            sp.bind(text=_save)
            ti.bind(text=_save)
            _save()

    cat_spinner.bind(text=_refresh)

    btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
    save_btn = _btn(t("scr_save"),
                    lambda: (on_done(state["node"]), popup.dismiss()),
                    color=ACCENT_GOLD)
    cancel_btn = _btn(t("scr_cancel"), lambda: popup.dismiss())
    btns.add_widget(save_btn)
    btns.add_widget(cancel_btn)
    root.add_widget(btns)

    popup = Popup(title=t("scr_expr_title"), content=root,
                  size_hint=(0.92, 0.85), background_color=POPUP_BG)
    popup.open()


def _parse_simple(s: str):
    """Parse a tiny expression string into Const/LocalVar/GlobalVar/EngineField.

    Format:
        123 / -5 / true / false / "text"  → Const
        f                                 → LocalVar
        g.foo                             → GlobalVar
        engine.gold                       → EngineField
        f.hp                              → FighterField(LocalVar("f"), "hp")
    Anything else falls back to LocalVar(s).
    """
    s = s.strip()
    if not s:
        return Const(0)
    if s.startswith('"') and s.endswith('"'):
        return Const(s[1:-1])
    if s in ("true", "True"):  return Const(True)
    if s in ("false", "False"): return Const(False)
    try:
        return Const(int(s))
    except ValueError:
        pass
    if s.startswith("g."):
        try:
            return GlobalVar(s[2:])
        except ValueError:
            return LocalVar("invalid")
    if s.startswith("engine."):
        return EngineField(s[7:])
    if "." in s:
        var, field = s.split(".", 1)
        return FighterField(LocalVar(var), field)
    return LocalVar(s)


# ---------- per-statement parameter editor ----------

def open_block_editor(node, on_save):
    """Edit parameters of a Statement node. on_save(updated_node) called on save."""
    root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
    sv = ScrollView()
    inner = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
    inner.bind(minimum_height=inner.setter("height"))
    sv.add_widget(inner)
    root.add_widget(sv)

    state = {"node": node}

    if isinstance(node, If):
        inner.add_widget(_label(f"{t('scr_block_cond')}: {expr_str(node.cond)}"))
        def _edit_cond():
            open_expr_editor(node.cond, lambda new: (
                setattr(node, "cond", new),
                open_block_editor(node, on_save), popup.dismiss(),
            ))
        inner.add_widget(_btn(t("scr_block_edit_cond"), _edit_cond))
    elif isinstance(node, While):
        inner.add_widget(_label(f"{t('scr_block_cond')}: {expr_str(node.cond)}"))
        def _edit_cond():
            open_expr_editor(node.cond, lambda new: (
                setattr(node, "cond", new),
                open_block_editor(node, on_save), popup.dismiss(),
            ))
        inner.add_widget(_btn(t("scr_block_edit_cond"), _edit_cond))
    elif isinstance(node, ForEach):
        ti_var = TextInput(text=node.var_name, multiline=False,
                           size_hint_y=None, height=dp(36))
        sp_src = Spinner(text=node.source, values=list(ITERABLE_SOURCES),
                         size_hint_y=None, height=dp(36))
        inner.add_widget(_label(t("scr_block_var_name")))
        inner.add_widget(ti_var)
        inner.add_widget(_label(t("scr_block_source")))
        inner.add_widget(sp_src)
        where_str = expr_str(node.where) if node.where else t("scr_block_filter_none")
        inner.add_widget(_label(f"{t('scr_block_filter')}: {where_str}"))
        def _edit_where():
            open_expr_editor(node.where or Const(True),
                             lambda new: (setattr(node, "where", new),
                                          open_block_editor(node, on_save),
                                          popup.dismiss()))
        inner.add_widget(_btn(t("scr_block_edit_where"), _edit_where))
        inner.add_widget(_btn(t("scr_block_remove_where"),
                              lambda: (setattr(node, "where", None),
                                       open_block_editor(node, on_save),
                                       popup.dismiss())))
        def _save_fe(*_):
            node.var_name = ti_var.text or "f"
            try:
                node.source = sp_src.text if sp_src.text in ITERABLE_SOURCES else "fighters"
            except Exception:
                pass
        ti_var.bind(text=_save_fe)
        sp_src.bind(text=_save_fe)
    elif isinstance(node, Assign):
        if node.target_kind == "local":
            ti_name = TextInput(text=node.name, multiline=False, size_hint_y=None, height=dp(36))
            inner.add_widget(_label(t("scr_block_local_name")))
            inner.add_widget(ti_name)
            ti_name.bind(text=lambda *_: setattr(node, "name", ti_name.text or "x"))
        elif node.target_kind == "global":
            ti_name = TextInput(text=node.name, multiline=False, size_hint_y=None, height=dp(36))
            inner.add_widget(_label(t("scr_block_global_name")))
            inner.add_widget(ti_name)
            def _save_global(*_):
                try:
                    GlobalVar(ti_name.text)  # validate
                    node.name = ti_name.text
                except ValueError:
                    pass
            ti_name.bind(text=_save_global)
        elif node.target_kind == "fighter_field":
            sp_field = Spinner(text=node.name, values=sorted(WRITABLE_FIGHTER_FIELDS),
                               size_hint_y=None, height=dp(36))
            inner.add_widget(_label(t("scr_block_fighter_field")))
            inner.add_widget(sp_field)
            sp_field.bind(text=lambda *_: setattr(node, "name", sp_field.text))
        inner.add_widget(_label(f"{t('scr_expr_value')}: {expr_str(node.value)}"))
        def _edit_val():
            open_expr_editor(node.value,
                             lambda new: (setattr(node, "value", new),
                                          open_block_editor(node, on_save),
                                          popup.dismiss()))
        inner.add_widget(_btn(t("scr_block_edit_value"), _edit_val))
    elif isinstance(node, Action):
        inner.add_widget(_label(f"{t('scr_block_action')}: {node.name}"))
        for i, a in enumerate(list(node.args)):
            inner.add_widget(_label(f"{t('scr_block_arg')} {i+1}: {expr_str(a)}"))
            def _edit_arg(idx=i):
                open_expr_editor(node.args[idx],
                                 lambda new: (node.args.__setitem__(idx, new),
                                              open_block_editor(node, on_save),
                                              popup.dismiss()))
            inner.add_widget(_btn(f"{t('scr_block_edit_arg')} {i+1}", _edit_arg))
    else:
        inner.add_widget(_label(t("scr_block_no_params")))

    btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
    btns.add_widget(_btn(t("scr_save"),
                          lambda: (on_save(state["node"]), popup.dismiss()),
                          color=ACCENT_GOLD))
    btns.add_widget(_btn(t("scr_cancel"), lambda: popup.dismiss()))
    root.add_widget(btns)

    popup = Popup(title=t("scr_block_params_title"), content=root,
                  size_hint=(0.92, 0.85), background_color=POPUP_BG)
    popup.open()
