# Build: 1
"""Widgets submodule — MinimalButton, NavButton, CardWidget, BaseCard."""
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
_SCROLL_THRESHOLD = 12  # px — if finger moves more than this, it's a scroll


class MinimalButton(ScrollSafeButtonMixin, ButtonBehavior, Widget):
    """Flat button with subtle press animation."""

    text = StringProperty("")
    btn_color = ListProperty(BTN_PRIMARY)
    text_color = ListProperty(TEXT_PRIMARY)
    font_size = NumericProperty(11)
    icon_source = StringProperty("")
    _press_alpha = NumericProperty(0)

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        return super().on_touch_down(touch)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._base_fs = sp(self.font_size)
        # Inner layout: AnchorLayout centers a BoxLayout with [label, icon]
        from kivy.uix.anchorlayout import AnchorLayout
        self._anchor = AnchorLayout(anchor_x="center", anchor_y="center")
        self._box = BoxLayout(spacing=0, size_hint=(None, None))
        self._label = Label(
            text=self.text, color=self.text_color,
            font_size=sp(self.font_size), bold=True,
            font_name='PixelFont',
            size_hint=(None, None),
            pos_hint={'center_y': 0.5},
        )
        self._label.bind(texture_size=self._on_tex)
        self._box.add_widget(self._label)
        self._anchor.add_widget(self._box)
        self.add_widget(self._anchor)
        self._icon = None
        with self.canvas.before:
            r, g, b, a = self.btn_color
            self._bg_color = Color(r, g, b, a)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            # Pixel 3D highlight (top + left, white)
            Color(1, 1, 1, 0.12)
            self._hi_line = Line(points=[], width=1.0)
            # Pixel 3D shadow (bottom + right, black)
            Color(0, 0, 0, 0.2)
            self._sh_line = Line(points=[], width=1.0)
        self.bind(pos=self._sync, size=self._on_resize,
                  text=self._update_text, font_size=self._update_font_size,
                  btn_color=self._update_bg, _press_alpha=self._update_bg,
                  text_color=self._update_text_color,
                  icon_source=self._update_icon)
        if self.icon_source:
            self._update_icon()

    def _on_tex(self, *args):
        """Label texture changed — resize label to match, update box."""
        tw, th = self._label.texture_size
        icon_w = self._icon.width if self._icon else 0
        icon_h = self._icon.height if self._icon else 0
        self._label.size = (tw, th)
        self._box.size = (tw + icon_w, max(th, icon_h))
        # Shrink if overflows
        if self.width > 0 and (tw + icon_w) > self.width - dp(4):
            if self._label.font_size > sp(9):
                ratio = (self.width - dp(4) - icon_w) / max(1, tw)
                new_fs = max(sp(9), self._label.font_size * ratio * 0.95)
                if abs(new_fs - self._label.font_size) > sp(0.5):
                    self._label.font_size = new_fs

    def _on_resize(self, *args):
        """Button resized — reset font so _on_tex can re-check."""
        if self._label.font_size != self._base_fs:
            self._label.font_size = self._base_fs
        self._sync()

    def _sync(self, *args):
        self._anchor.pos = self.pos
        self._anchor.size = self.size
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        x, y, w, h = self.x, self.y, self.width, self.height
        # Highlight: left edge bottom-to-top, then top edge left-to-right
        self._hi_line.points = [x, y, x, y + h, x + w, y + h]
        # Shadow: right edge top-to-bottom, then bottom edge right-to-left
        self._sh_line.points = [x + w, y + h, x + w, y, x, y]

    def _update_bg(self, *args):
        r, g, b, a = self.btn_color
        self._bg_color.rgba = (r, g, b, a - self._press_alpha * 0.3)

    def _update_text(self, *args):
        self._label.text = self.text
        self._label.font_size = self._base_fs

    def _update_font_size(self, *args):
        self._base_fs = sp(self.font_size)
        self._label.font_size = sp(self.font_size)

    def _update_text_color(self, *args):
        self._label.color = self.text_color

    def _update_icon(self, *args):
        if self.icon_source:
            icon_w = dp(24)
            if not self._icon:
                self._icon = Image(
                    source=self.icon_source, fit_mode="contain",
                    size_hint=(None, None), width=icon_w, height=icon_w,
                    pos_hint={'center_y': 0.5},
                )
                self._box.add_widget(self._icon)
            else:
                self._icon.source = self.icon_source
        elif self._icon:
            self._box.remove_widget(self._icon)
            self._icon = None

    def on_press(self):
        Animation.cancel_all(self, "_press_alpha")
        self._press_alpha = 1
        Animation(_press_alpha=0, duration=0.3).start(self)


class NavButton(ScrollSafeButtonMixin, ButtonBehavior, Widget):
    """Bottom nav icon button with PNG icon sprite."""

    text = StringProperty("")
    icon = StringProperty("")          # kept for compat but unused now
    icon_source = StringProperty("")   # path to PNG icon
    is_active = BooleanProperty(False)

    # ScrollSafeButtonMixin handles scroll protection

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._icon_img = Image(
            fit_mode="contain",
        )
        self._text_label = Label(
            text=self.text,
            font_size=sp(9),
            font_name='PixelFont',
            halign="center",
            valign="top",
            bold=True,
        )
        self.add_widget(self._icon_img)
        self.add_widget(self._text_label)
        self.bind(pos=self._update, size=self._update,
                  is_active=self._update, text=self._update,
                  icon_source=self._update)
        self._text_label.bind(texture_size=self._update)
        Clock.schedule_once(self._update, 0)

    def _update(self, *args):
        color = NAV_ACTIVE if self.is_active else NAV_INACTIVE
        if self.icon_source:
            self._icon_img.source = self.icon_source
            self._icon_img.color = [1, 1, 1, 1] if self.is_active else [0.5, 0.5, 0.5, 1]
        ico_size = min(self.width * 0.7, self.height * 0.55)
        self._icon_img.size = (ico_size, ico_size)
        self._icon_img.pos = (
            self.center_x - ico_size / 2,
            self.y + self.height * 0.35,
        )

        self._text_label.text = self.text
        self._text_label.color = color
        self._text_label.pos = (self.x, self.y)
        self._text_label.size = (self.width, self.height * 0.38)
        self._text_label.text_size = (self.width, self.height * 0.38)
        # Auto-shrink nav text to fit width
        if self.width > 0 and self._text_label.texture_size[0] > self.width:
            ratio = self.width / max(1, self._text_label.texture_size[0])
            self._text_label.font_size = max(sp(5), sp(9) * ratio * 0.95)
        elif self.width > 0 and self._text_label.font_size < sp(9):
            self._text_label.font_size = sp(9)
        # Sync all NavButton font sizes to smallest in parent NavBar.
        # NavBar lives in ._nav (sibling module); lazy-import to avoid cycle.
        from ._nav import NavBar  # noqa: PLC0415
        if isinstance(self.parent, NavBar):
            Clock.unschedule(self.parent._sync_font_sizes)
            Clock.schedule_once(self.parent._sync_font_sizes, 0)




