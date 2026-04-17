# Build: 1
"""Widgets submodule — CardWidget, BaseCard."""
import os
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.recycleview import RecycleView
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import (
    Color, RoundedRectangle, Rectangle, Line, Ellipse,
    PushMatrix, PopMatrix, Rotate,
)
from kivy.properties import (
    NumericProperty, StringProperty, ListProperty, BooleanProperty
)
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp, sp
from game.theme import *
from ._scroll import ScrollSafeButtonMixin
from ._labels import AutoShrinkLabel
from ._scroll import ScrollSafeButtonMixin
from ._buttons import MinimalButton

class CardWidget(ScrollSafeButtonMixin, ButtonBehavior, BoxLayout):
    """Pixel-art card container with 1px border and 3D bevel. Supports on_press."""

    card_color = ListProperty(BG_CARD)
    border_color = ListProperty(DIVIDER)
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_color = Color(*self.card_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            self._br_color = Color(*self.border_color)
            self._br_line = Line(
                rectangle=(self.x, self.y, self.width, self.height),
                width=1.0,
            )
            # Pixel highlight (top + left, brighter)
            Color(1, 1, 1, 0.08)
            self._hi_line = Line(points=[], width=1.0)
            # Pixel shadow (bottom + right, darker)
            Color(0, 0, 0, 0.15)
            self._sh_line = Line(points=[], width=1.0)
        self.bind(pos=self._update_geom, size=self._update_geom,
                  active=self._update_colors,
                  card_color=self._update_colors,
                  border_color=self._update_colors)

    def _update_geom(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._br_line.rectangle = (self.x, self.y, self.width, self.height)
        x, y, w, h = self.x, self.y, self.width, self.height
        self._hi_line.points = [x, y, x, y + h, x + w, y + h]
        self._sh_line.points = [x + w, y + h, x + w, y, x, y]

    def _update_colors(self, *args):
        bg = BG_CARD_ACTIVE if self.active else self.card_color
        self._bg_color.rgba = bg
        bc = ACCENT_GOLD if self.active else self.border_color
        self._br_color.rgba = bc
        self._br_line.width = 1.2 if self.active else 1.0


class BaseCard(CardWidget):
    """Declarative card builder. Builds cards row-by-row.

    Usage:
        card = BaseCard(height=dp(97), padding=[dp(12), dp(8)], spacing=dp(2))
        card.border_color = rcolor
        card.add_text_row(
            ("Iron Sword", sp(25), True, rcolor, None),
            ("+3", sp(14), True, ACCENT_GOLD, None),
            size_hint_y=0.35,
        )
        card.add_stat_row([("icons/ic_str.png", "150")], size_hint_y=0.40)
    """

    def _make_label(self, text, font_size=sp(10), bold=False, color=TEXT_PRIMARY,
                    halign="left", size_hint_x=None):
        lbl = AutoShrinkLabel(
            text=str(text), font_size=font_size, bold=bold, color=list(color),
            halign=halign, valign="middle", font_name='PixelFont',
        )
        if size_hint_x is None:
            lbl.size_hint_x = None
            lbl.width = 1
            lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        else:
            lbl.size_hint_x = size_hint_x
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        return lbl

    def add_text_row(self, *cells, size_hint_y=None, height=None, spacing=dp(4)):
        """Add horizontal row of text cells.
        Each cell: (text, font_size, bold, color, size_hint_x).
        size_hint_x=None → auto-width from texture_size.
        """
        row = BoxLayout(spacing=spacing)
        if size_hint_y is not None:
            row.size_hint_y = size_hint_y
        if height is not None:
            row.size_hint_y = None
            row.height = height
        for cell in cells:
            if isinstance(cell, tuple):
                text, fs, bld, clr, shx = cell
                row.add_widget(self._make_label(text, fs, bld, clr, "left", shx))
            else:
                row.add_widget(cell)
        self.add_widget(row)
        return row

    def add_label(self, text, font_size=sp(11), bold=False, color=TEXT_PRIMARY,
                  halign="left", size_hint_y=None, height=None):
        """Add a single full-width label row."""
        lbl = self._make_label(text, font_size, bold, color, halign, size_hint_x=1)
        if size_hint_y is not None:
            lbl.size_hint_y = size_hint_y
        if height is not None:
            lbl.size_hint_y = None
            lbl.height = height
        self.add_widget(lbl)
        return lbl

    def add_stat_row(self, stats, color=ACCENT_GREEN, font_size=sp(10),
                     icon_height=dp(18), size_hint_y=None, height=None,
                     spacing=dp(8), empty_text="—"):
        """Add row of icon+value pairs.
        stats: [(icon_src, value_text), ...].
        """
        row = BoxLayout(spacing=spacing)
        if size_hint_y is not None:
            row.size_hint_y = size_hint_y
        if height is not None:
            row.size_hint_y = None
            row.height = height
        ico_h = icon_height
        if not stats or all(not v for _, v in stats):
            row.add_widget(self._make_label(empty_text, font_size, False, TEXT_MUTED, "left", 1))
        else:
            for icon_src, val_text in stats:
                if not val_text:
                    continue
                lbl = self._make_label(val_text, font_size, True, color, "left", None)
                row.add_widget(lbl)
                row.add_widget(Image(source=icon_src, fit_mode="contain",
                                     size_hint=(None, 1), width=ico_h))
        self.add_widget(row)
        return row

    def add_icon_labels(self, items, height=dp(28), spacing=dp(2)):
        """Add row of icon+label pairs (e.g. STR/AGI/HP in roster card).
        items: [(icon_src, text, color, font_size), ...].
        """
        row = BoxLayout(size_hint_y=None, height=height, spacing=spacing)
        for icon_src, text, color, fs in items:
            pair = BoxLayout(spacing=dp(2))
            pair.add_widget(Image(source=icon_src, fit_mode="contain",
                                  size_hint=(None, 1), width=height * 0.8))
            pair.add_widget(self._make_label(text, fs, True, color, "left", 1))
            row.add_widget(pair)
        self.add_widget(row)
        return row

    def add_button_row(self, buttons, height=dp(38), spacing=dp(5)):
        """Add row of MinimalButton widgets."""
        row = BoxLayout(size_hint_y=None, height=height, spacing=spacing)
        for btn in buttons:
            row.add_widget(btn)
        self.add_widget(row)
        return row

    def add_separator(self, color=DIVIDER, height=1):
        """Add thin horizontal divider."""
        from kivy.uix.widget import Widget as W
        sep = W(size_hint_y=None, height=height)
        with sep.canvas:
            Color(*color)
            r = Rectangle(pos=sep.pos, size=sep.size)
        sep.bind(pos=lambda w, p: setattr(r, 'pos', p),
                 size=lambda w, s: setattr(r, 'size', s))
        self.add_widget(sep)
        return sep
