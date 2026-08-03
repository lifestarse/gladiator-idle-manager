# Build: 1
"""Shared namespace for the squad-script editor package.

Every sibling screen package (arena / forge / lore / more / roster) has one of
these: a single module naming the Kivy, theme and ui_helpers imports that the
package's modules all need, pulled in with ``from ._screen_imports import *``.

This hub also OWNS the package's shared widget factories and palette
constants. The editor rebuilds its whole surface from the AST on every change,
so its buttons and captions are built in Python rather than kv, and all three
UI modules (``_core``, ``cells``, ``popups``) need the same ones. None of the
three can own them without the other two importing sideways, so they live
here.
"""
from __future__ import annotations
from typing import Callable

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner

from game.base_screen import BaseScreen
from game.localization import t
from game.theme import *  # noqa: F401,F403
from game.theme import popup_color
from game.ui_helpers import bind_text_wrap
from game.widgets import MinimalButton, SafeTextInput as TextInput


# ---------- editor palette ----------

# Popup chrome. These popups build their own content roots instead of going
# through make_styled_popup, but the background still has to be the theme's
# card colour — a neutral grey reads as a different app next to the indigo UI.
POPUP_BG = popup_color(BG_CARD)

# Surface of an expanded inline picker, and the pill of the picker currently
# open on top of it.
PICKER_BG = BG_ELEVATED
PILL_BG_HOT = BG_CARD_ACTIVE

# Run-log status text. The ACCENT_* tokens are button fills and read too dark
# as text on BG_CARD, so these lines use lighter tints of the same hues.
TEXT_ERROR = (1.00, 0.60, 0.60, 1)
TEXT_OK = (0.50, 1.00, 0.50, 1)

# Wrap inset (dp) for labels that sit inside a padded row: without it the last
# characters of a wrapped line render underneath the padding.
WRAP_INSET_DP = 8

# Alpha of the category tint painted over a block card's background.
CARD_TINT_ALPHA = 0.10


# ---------- shared widget factories ----------

def _bind_wrap(label, inset: float = 0):
    """Make ``label`` wrap its text to its own box; returns the label.

    ``inset`` is in dp and shrinks the wrap width for labels inside a padded
    row. Call once per label — it binds unconditionally.
    """
    if not inset:
        bind_text_wrap(label)
    else:
        pad = dp(inset)
        label.bind(size=lambda w, s: setattr(w, "text_size", (s[0] - pad, s[1])))
    return label


def _btn(text_, on_press=None, color=None, w=None, h=44):
    """Themed button for dynamically built editor content.

    One factory for all of it: palette rows, popup actions, inline pills and
    the per-card handles. ``w`` (dp) pins the width, otherwise the button
    fills its row; ``h`` (dp) is the height. Gold buttons flip to dark text
    because gold-on-cream is unreadable. ``on_press`` takes no arguments.
    """
    b = MinimalButton(
        text=text_, size_hint_y=None, height=dp(h), font_size=12,
        btn_color=color or BTN_PRIMARY,
        text_color=BG_DARK if color is ACCENT_GOLD else TEXT_PRIMARY,
    )
    if w is not None:
        b.size_hint_x = None
        b.width = dp(w)
    if on_press is not None:
        b.bind(on_release=lambda *_: on_press())
    return b


def _section_label(text_, h=22, inset: float = 0):
    """Small muted caption above an inline editor row."""
    lbl = Label(
        text=text_, size_hint_y=None, height=dp(h),
        font_size="11sp", color=TEXT_SECONDARY,
        halign="left", valign="middle",
    )
    return _bind_wrap(lbl, inset)


def _section(text_):
    """Bold group header inside a popup body."""
    lbl = Label(
        text=text_, size_hint_y=None, height=dp(24),
        font_size="12sp", bold=True, color=TEXT_PRIMARY,
        halign="left", valign="middle",
    )
    return _bind_wrap(lbl)


def _bg(widget, color):
    """Paint a rectangle tracking ``widget.pos``/``size`` as its background.

    Call once per widget: it appends to ``canvas.before`` and binds
    unconditionally, so a second call stacks a second rectangle and a second
    observer that nothing ever removes. Widgets whose background is repainted
    during their lifetime keep a reference to their Color instead and mutate
    ``rgba`` — see ``cells.BlockCard``.
    """
    with widget.canvas.before:
        Color(*color)
        widget._bg_rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *_: setattr(widget._bg_rect, "pos", widget.pos),
        size=lambda *_: setattr(widget._bg_rect, "size", widget.size),
    )
    return widget


# Star-imports skip underscore names, so build __all__ from everything above:
# the factories are the point of this module and every consumer needs them.
__all__ = [n for n in list(globals().keys())
           if not n.startswith('__') and n != 'annotations']
