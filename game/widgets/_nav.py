# Build: 1
"""Widgets submodule — NavBar, TouchPanel."""
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
_SCROLL_THRESHOLD = 12  # px — if finger moves more than this, it's a scroll


class NavBar(BoxLayout):
    """Navigation bar — set active_screen to highlight the current tab."""
    active_screen = StringProperty("arena")

    def _sync_font_sizes(self, *args):
        """Make all NavButton labels use the same (smallest) font_size."""
        buttons = [c for c in self.children if isinstance(c, NavButton)]
        if not buttons:
            return
        min_fs = min(b._text_label.font_size for b in buttons)
        for b in buttons:
            b._text_label.font_size = min_fs


class TouchPanel(BoxLayout):
    """Panel that guarantees touch isolation between switchable views.

    - Active (disabled=False): consumes all touches within bounds, even empty
      areas, so touches never bleed through to sibling panels.
    - Inactive (disabled=True): silently blocks touches within its bounds
      without dispatching to any child.
    """

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if not self.disabled:
            super().on_touch_down(touch)
        return True
