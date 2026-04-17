# Build: 1
"""Widgets submodule — MinimalBar, FloatingText."""
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
_SCROLL_THRESHOLD = 12  # px — if finger moves more than this, it's a scroll


class MinimalBar(Widget):
    """Sleek animated HP / progress bar."""

    value = NumericProperty(1.0)  # 0.0 — 1.0
    bar_color = ListProperty(HP_PLAYER)
    bg_color = ListProperty(HP_PLAYER_BG)
    _display_value = NumericProperty(1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            self._bg_color = Color(*self.bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            self._fill_color = Color(*self.bar_color)
            w = max(0, self.width * max(0, min(1, self._display_value)))
            self._fill_rect = Rectangle(
                pos=self.pos, size=(w, self.height)
            )
            # 1px dark border
            Color(0.1, 0.1, 0.1, 0.9)
            self._border_line = Line(
                rectangle=(self.x, self.y, self.width, self.height),
                width=1.0,
            )
        self.bind(pos=self._update_geom, size=self._update_geom,
                  _display_value=self._update_fill,
                  bar_color=self._update_colors,
                  bg_color=self._update_colors)
        self.bind(value=self._animate)

    def _animate(self, *args):
        Animation.cancel_all(self, "_display_value")
        anim = Animation(_display_value=self.value, duration=0.4, t="out_cubic")
        anim.start(self)

    def _update_geom(self, *args):
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        self._fill_rect.pos = self.pos
        w = max(0, self.width * max(0, min(1, self._display_value)))
        self._fill_rect.size = (w, self.height)
        self._border_line.rectangle = (self.x, self.y, self.width, self.height)

    def _update_fill(self, *args):
        w = max(0, self.width * max(0, min(1, self._display_value)))
        self._fill_rect.size = (w, self.height)

    def _update_colors(self, *args):
        self._fill_color.rgba = self.bar_color
        self._bg_color.rgba = self.bg_color


class FloatingText(Label):
    """Animated floating damage/gold text."""

    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', 'PixelFont')
        super().__init__(**kwargs)
        self.opacity = 1
        Clock.schedule_once(self._animate, 0)

    def _animate(self, dt):
        anim = Animation(
            y=self.y + 60,
            opacity=0,
            duration=1.2,
            t="out_cubic",
        )
        anim.bind(on_complete=lambda *a: self.parent and self.parent.remove_widget(self))
        anim.start(self)
