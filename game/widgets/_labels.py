# Build: 1
"""Widgets submodule — AutoShrinkLabel."""
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


class AutoShrinkLabel(Label):
    """Label that auto-shrinks font_size so text always fits.
    Reactive — no texture_update() calls, no Clock spam."""
    _base_font_size = NumericProperty(0)
    _shrinking = False

    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', 'PixelFont')
        super().__init__(**kwargs)
        self._base_font_size = self.font_size
        self.bind(texture_size=self._check_fit)

    def on_text(self, *args):
        if not self._shrinking:
            self._shrinking = True
            self.font_size = self._base_font_size
            self._shrinking = False

    def _check_fit(self, *args):
        if self._shrinking:
            return
        max_w = self.text_size[0] if self.text_size[0] else self.width
        if max_w <= 0 or self.texture_size[0] <= 0:
            return
        tw = self.texture_size[0]
        th = self.texture_size[1]
        max_h = self.height
        min_fs = sp(9)
        ratio = 1.0
        if tw > max_w + 2:
            ratio = min(ratio, max_w / tw)
        if max_h > 0 and th > max_h + 2:
            ratio = min(ratio, max_h / th)
        if ratio < 1.0 and self.font_size > min_fs:
            self._shrinking = True
            self.font_size = max(min_fs, self.font_size * ratio * 0.92)
            self._shrinking = False

    def on_font_size(self, *args):
        if self._base_font_size == 0:
            self._base_font_size = self.font_size
