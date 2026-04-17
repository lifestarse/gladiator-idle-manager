# Build: 1
"""Auto-generated submodule of game.ui_helpers package."""
from contextlib import contextmanager
import time

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from game.widgets import CardWidget, MinimalButton, MinimalBar, AutoShrinkLabel, GladiatorAvatar
from game.theme import *
from game.models import RARITY_COLORS, fmt_num
from game.slots import SLOTS
from game.localization import t
from game.constants import LOW_HP_THRESHOLD


_HOLD_MS = 100  # minimum hold time in ms to open popup


def bind_text_wrap(label):
    """Make a Kivy Label wrap text to its widget size. Call after construction."""
    label.bind(size=lambda w, s: setattr(w, "text_size", s))

_CLASS_COLORS = {
    "mercenary": ACCENT_GREEN,
    "assassin": ACCENT_RED,
    "tank": ACCENT_BLUE,
    "berserker": ACCENT_RED,
    "retiarius": ACCENT_CYAN,
    "medicus": ACCENT_PURPLE,
}


from contextlib import contextmanager

def _invalidate_grid_cache(grid):
    """Wipe every _*_key cache stored on a grid widget."""
    for attr in list(vars(grid)):
        if attr.endswith('_key'):
            setattr(grid, attr, None)


@contextmanager
def grid_batch(grid):
    """Context manager: unbinds minimum_height during widget adds, rebinds after.
    Usage:
        with grid_batch(grid):
            grid.clear_widgets()
            grid.add_widget(...)
    """
    _invalidate_grid_cache(grid)
    grid.unbind(minimum_height=grid.setter('height'))
    try:
        yield grid
    finally:
        grid.height = grid.minimum_height
        grid.bind(minimum_height=grid.setter('height'))


def build_back_btn(callback):
    """Standard back button used across all detail views."""
    btn = MinimalButton(
        text=t("back_btn"), btn_color=BTN_PRIMARY, font_size=sp(11),
        size_hint_y=None, height=dp(48),
    )
    btn.bind(on_press=lambda *a: callback())
    return btn


def make_styled_popup(title, content, size_hint=(0.92, 0.75)):
    """Popup styled with game theme colours."""
    return Popup(
        title=title, content=content,
        size_hint=size_hint,
        title_size=sp(12),
        background_color=popup_color(BG_CARD),
        title_color=popup_color(ACCENT_GOLD),
        separator_color=popup_color(ACCENT_GOLD),
    )


def make_dynamic_label(text, font_size="11sp", color=TEXT_SECONDARY,
                       padding=dp(16), halign="left"):
    """Label that auto-wraps and auto-sizes height to content."""
    lbl = AutoShrinkLabel(
        text=text, font_size=font_size, color=color,
        size_hint_y=None, halign=halign, valign="top", markup=True,
    )
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - padding, None)))
    lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)))
    return lbl


def _batch_fill_grid(grid, widgets):
    """Add widgets to grid with only one layout pass instead of N.

    Unbinds the minimum_height→height KV rule before the loop so that
    each add_widget() does NOT trigger a full layout recalculation.
    Sets height once at the end, then rebinds.
    Skips reparenting if widgets are already the grid's children.
    """
    # Skip if already showing these exact widgets in order
    if (grid.children and len(grid.children) == len(widgets)
            and all(a is b for a, b in zip(reversed(grid.children), widgets))):
        return
    _invalidate_grid_cache(grid)
    grid.unbind(minimum_height=grid.setter('height'))
    grid.clear_widgets()
    for w in widgets:
        if w.parent:
            w.parent.remove_widget(w)
        grid.add_widget(w)
    grid.height = grid.minimum_height
    grid.bind(minimum_height=grid.setter('height'))


def _bind_long_tap(widget, callback):
    """Bind simple tap (with scroll protection) to fire callback on touch_up."""
    def _on_down(w, touch):
        if not w.collide_point(*touch.pos):
            return False
        touch.ud.setdefault('_tap_t', {})[id(w)] = True
        return False  # don't consume — let scroll etc. work

    def _on_up(w, touch):
        if touch.grab_current is not None:
            return False
        if not w.collide_point(*touch.pos):
            return False
        if hasattr(touch, 'ox') and hasattr(touch, 'oy'):
            dx = abs(touch.x - touch.ox)
            dy = abs(touch.y - touch.oy)
            if dx > dp(8) or dy > dp(8):
                return False
        if not touch.ud.get('_tap_t', {}).get(id(w)):
            return False
        callback(w)
        return True

    widget.bind(on_touch_down=_on_down)
    widget.bind(on_touch_up=_on_up)


def build_tab_row(tabs, current, on_select, active_color=None, inactive_color=None,
                  height=None, font_size=sp(10)):
    """Build a horizontal row of tab buttons.

    Args:
        tabs: list of (value, display_text) pairs
        current: currently active value
        on_select: callable(value) called when a tab is pressed
        active_color: RGBA for the active button background (default: ACCENT_RED)
        inactive_color: RGBA for inactive buttons (default: BTN_DISABLED)
        height: row height (default: dp(36))
        font_size: button font size
    Returns:
        BoxLayout row widget
    """
    if active_color is None:
        active_color = ACCENT_RED
    if inactive_color is None:
        inactive_color = BTN_DISABLED
    if height is None:
        height = dp(36)

    row = BoxLayout(size_hint_y=None, height=height, spacing=dp(4))
    for value, label_text in tabs:
        active = (value == current)
        btn = MinimalButton(
            text=label_text, font_size=font_size,
            btn_color=active_color if active else inactive_color,
            text_color=TEXT_PRIMARY if active else TEXT_MUTED,
        )
        btn.bind(on_press=lambda inst, v=value: on_select(v))
        row.add_widget(btn)
    return row


def _debug_border(widget, color=(1, 0, 0, 1)):
    from kivy.graphics import Color, Line
    def _update(*args):
        widget.canvas.after.clear()
        with widget.canvas.after:
            Color(*color)
            Line(rectangle=(widget.x, widget.y, widget.width, widget.height), width=1)
    widget.bind(pos=_update, size=_update)
    return widget


def _auto_text_size(label):
    bind_text_wrap(label)
    return label


def _diamond_label(amount, font_size="12sp", color=ACCENT_CYAN):
    """BoxLayout with number + diamond icon (icon to the right), vertically centered."""
    from kivy.uix.anchorlayout import AnchorLayout
    anchor = AnchorLayout(size_hint=(1, 1), anchor_x="center", anchor_y="center")
    box = BoxLayout(
        orientation="horizontal", size_hint=(None, None),
        spacing=0, height=dp(28),
    )
    box.bind(minimum_width=box.setter("width"))
    lbl = AutoShrinkLabel(
        text=str(amount), font_size=font_size, bold=True,
        color=color, halign="right", valign="middle",
        size_hint_x=None,
    )
    lbl.bind(texture_size=lbl.setter("size"))
    box.add_widget(lbl)
    box.add_widget(Image(
        source="sprites/icons/ic_gem.png", fit_mode="contain",
        size_hint=(None, None), width=dp(18), height=dp(18),
    ))
    anchor.add_widget(box)
    return anchor


def _icon_label(icon_src, text, color, font_size="11sp", height=dp(28)):
    """Helper: icon image + label in a horizontal box."""
    row = BoxLayout(size_hint_y=None, height=height, spacing=0)
    ico = Image(source=icon_src, fit_mode="contain",
                size_hint=(None, 1), width=height * 0.8)
    ico.color = [1, 1, 1, 1]
    row.add_widget(ico)
    lbl = AutoShrinkLabel(text=str(text), font_size=font_size, bold=True,
                color=color, halign="left", valign="middle")
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    row.add_widget(lbl)
    return row
