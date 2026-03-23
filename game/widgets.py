"""Custom minimalist widgets — geometric, clean, The Tower inspired."""

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, RoundedRectangle, Rectangle, Line, Ellipse
from kivy.properties import (
    NumericProperty, StringProperty, ListProperty, BooleanProperty
)
from kivy.animation import Animation
from kivy.clock import Clock

from game.theme import *


class MinimalBar(Widget):
    """Sleek animated HP / progress bar."""

    value = NumericProperty(1.0)  # 0.0 — 1.0
    bar_color = ListProperty(HP_PLAYER)
    bg_color = ListProperty(HP_PLAYER_BG)
    _display_value = NumericProperty(1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, _display_value=self._draw)
        self.bind(value=self._animate)
        Clock.schedule_once(self._draw, 0)

    def _animate(self, *args):
        Animation.cancel_all(self, "_display_value")
        anim = Animation(_display_value=self.value, duration=0.4, t="out_cubic")
        anim.start(self)

    def _draw(self, *args):
        self.canvas.clear()
        with self.canvas:
            # Background
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[4])
            # Fill
            Color(*self.bar_color)
            w = max(0, self.width * max(0, min(1, self._display_value)))
            if w > 0:
                RoundedRectangle(pos=self.pos, size=(w, self.height), radius=[4])


class GladiatorAvatar(Widget):
    """Geometric gladiator figure — minimalist silhouette."""

    accent_color = ListProperty(ACCENT_GREEN)
    tier = NumericProperty(1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._draw, 0)

    def _draw(self, *args):
        self.canvas.clear()
        cx = self.center_x
        cy = self.center_y
        s = min(self.width, self.height)

        with self.canvas:
            # Glow circle behind
            Color(self.accent_color[0], self.accent_color[1],
                  self.accent_color[2], 0.12)
            Ellipse(pos=(cx - s * 0.45, cy - s * 0.45), size=(s * 0.9, s * 0.9))

            # Body — rounded rect
            Color(*self.accent_color)
            body_w = s * 0.3
            body_h = s * 0.4
            RoundedRectangle(
                pos=(cx - body_w / 2, cy - s * 0.15),
                size=(body_w, body_h),
                radius=[6],
            )

            # Head — circle
            head_r = s * 0.12
            Ellipse(
                pos=(cx - head_r, cy + s * 0.28),
                size=(head_r * 2, head_r * 2),
            )

            # Shield — small square (left)
            shield_s = s * 0.14
            Color(self.accent_color[0] * 0.7, self.accent_color[1] * 0.7,
                  self.accent_color[2] * 0.7, 1)
            RoundedRectangle(
                pos=(cx - body_w / 2 - shield_s * 0.8, cy),
                size=(shield_s, shield_s * 1.2),
                radius=[3],
            )

            # Sword — thin rect (right)
            Color(0.75, 0.75, 0.8, 1)
            sword_w = s * 0.04
            sword_h = s * 0.35
            Rectangle(
                pos=(cx + body_w / 2 + sword_w, cy + s * 0.05),
                size=(sword_w, sword_h),
            )

            # Level indicator dots
            Color(*ACCENT_GOLD)
            dots = min(self.tier, 5)
            dot_r = s * 0.03
            start_x = cx - (dots - 1) * dot_r * 1.5
            for i in range(dots):
                Ellipse(
                    pos=(start_x + i * dot_r * 3 - dot_r,
                         cy - s * 0.25),
                    size=(dot_r * 2, dot_r * 2),
                )


class MinimalButton(ButtonBehavior, Widget):
    """Flat button with subtle press animation."""

    text = StringProperty("")
    btn_color = ListProperty(BTN_PRIMARY)
    text_color = ListProperty(TEXT_PRIMARY)
    font_size = NumericProperty(16)
    _press_alpha = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._label = Label(
            text=self.text,
            color=self.text_color,
            font_size=self.font_size,
            bold=True,
            halign="center",
            valign="middle",
        )
        self.add_widget(self._label)
        self.bind(pos=self._update, size=self._update, text=self._update_text,
                  btn_color=self._update, _press_alpha=self._update,
                  text_color=self._update_text_color)
        Clock.schedule_once(self._update, 0)

    def _update(self, *args):
        self._label.pos = self.pos
        self._label.size = self.size
        self._label.text_size = self.size
        self.canvas.before.clear()
        with self.canvas.before:
            r, g, b, a = self.btn_color
            Color(r, g, b, a - self._press_alpha * 0.3)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[8])

    def _update_text(self, *args):
        self._label.text = self.text
        self._label.font_size = self.font_size

    def _update_text_color(self, *args):
        self._label.color = self.text_color

    def on_press(self):
        Animation.cancel_all(self, "_press_alpha")
        self._press_alpha = 1
        Animation(_press_alpha=0, duration=0.3).start(self)


class CardWidget(BoxLayout):
    """Rounded card container with subtle border."""

    card_color = ListProperty(BG_CARD)
    border_color = ListProperty(DIVIDER)
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, active=self._draw)
        Clock.schedule_once(self._draw, 0)

    def _draw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            bg = BG_CARD_ACTIVE if self.active else self.card_color
            Color(*bg)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[10])
            # Border
            bc = ACCENT_GOLD if self.active else self.border_color
            Color(*bc)
            Line(
                rounded_rectangle=(
                    self.x, self.y, self.width, self.height, 10
                ),
                width=1.2 if self.active else 0.7,
            )


class NavButton(ButtonBehavior, Widget):
    """Bottom nav icon button."""

    text = StringProperty("")
    icon = StringProperty("")
    is_active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._icon_label = Label(
            text=self.icon,
            font_size="22sp",
            halign="center",
            valign="bottom",
        )
        self._text_label = Label(
            text=self.text,
            font_size="10sp",
            halign="center",
            valign="top",
        )
        self.add_widget(self._icon_label)
        self.add_widget(self._text_label)
        self.bind(pos=self._update, size=self._update,
                  is_active=self._update, text=self._update,
                  icon=self._update)
        Clock.schedule_once(self._update, 0)

    def _update(self, *args):
        color = NAV_ACTIVE if self.is_active else NAV_INACTIVE
        self._icon_label.text = self.icon
        self._icon_label.color = color
        self._icon_label.pos = (self.x, self.y + self.height * 0.2)
        self._icon_label.size = (self.width, self.height * 0.6)
        self._icon_label.text_size = self._icon_label.size

        self._text_label.text = self.text
        self._text_label.color = color
        self._text_label.pos = (self.x, self.y)
        self._text_label.size = (self.width, self.height * 0.4)
        self._text_label.text_size = self._text_label.size


class FloatingText(Label):
    """Animated floating damage/gold text."""

    def __init__(self, **kwargs):
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
