# Build: 26
"""Custom pixel-art RPG widgets — crisp rectangles, PixelFont, sprite avatars."""

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

_SCROLL_THRESHOLD = 12  # px — if finger moves more than this, it's a scroll


class ScrollSafeButtonMixin:
    """Mixin that prevents button presses during/after scrolling.

    Records touch_down position, suppresses on_release if finger moved
    beyond threshold (user was scrolling, not tapping).
    """

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud.setdefault('_btn_origin', {})[id(self)] = touch.pos
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        origin = touch.ud.get('_btn_origin', {}).get(id(self))
        if origin and self.collide_point(*touch.pos):
            dx = abs(touch.pos[0] - origin[0])
            dy = abs(touch.pos[1] - origin[1])
            if dx > _SCROLL_THRESHOLD or dy > _SCROLL_THRESHOLD:
                # Finger moved — this was a scroll, cancel the press
                touch.ud['_btn_origin'].pop(id(self), None)
                return True
        return super().on_touch_up(touch)
from kivy.clock import Clock
from kivy.metrics import dp, sp

from game.theme import *


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


class GladiatorAvatar(Widget):
    """Sprite-based gladiator avatar — displays a PNG from sprites/fighters/."""

    fighter_class = StringProperty("mercenary")
    # Keep accent_color for backward compat (ignored when sprite exists)
    accent_color = ListProperty(ACCENT_GREEN)
    tier = NumericProperty(1)
    is_wounded = BooleanProperty(False)
    frame = StringProperty("idle")

    _last_path = ""
    _last_wounded = None
    _has_fallback = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sprite = Image(fit_mode="contain", opacity=0)
        self.add_widget(self._sprite)
        self.bind(
            pos=self._layout, size=self._layout,
            fighter_class=self._update_sprite,
            frame=self._update_sprite,
            is_wounded=self._update_sprite,
        )
        # Load sprite immediately — no schedule_once delay
        self._update_sprite()

    def _sprite_path(self):
        return f"sprites/fighters/{self.fighter_class}_{self.frame}.png"

    def _update_sprite(self, *args):
        path = self._sprite_path()
        wounded = self.is_wounded
        # Skip if nothing changed
        if path == self._last_path and wounded == self._last_wounded:
            return
        self._last_path = path
        self._last_wounded = wounded
        if os.path.exists(path):
            self._sprite.source = path
            self._sprite.opacity = 1
            self._sprite.color = [1, 0.5, 0.5, 0.8] if wounded else [1, 1, 1, 1]
            # Clear fallback only once when switching from fallback to sprite
            if self._has_fallback:
                self.canvas.before.clear()
                self._has_fallback = False
        else:
            self._sprite.source = ""
            self._sprite.opacity = 0
            self._draw_fallback()
        self._layout()

    def _layout(self, *args):
        self._sprite.pos = self.pos
        self._sprite.size = self.size

    def _draw_fallback(self):
        self.canvas.before.clear()
        self._has_fallback = True
        cx, cy = self.center_x, self.center_y
        s = min(self.width, self.height)
        with self.canvas.before:
            Color(*self.accent_color)
            Rectangle(
                pos=(cx - s * 0.35, cy - s * 0.35),
                size=(s * 0.7, s * 0.7),
            )
            if self.is_wounded:
                Color(0.85, 0.1, 0.1, 0.7)
                Rectangle(
                    pos=(cx - s * 0.35, cy - s * 0.35),
                    size=(s * 0.7, s * 0.7),
                )


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
        # Sync all NavButton font sizes to smallest in parent NavBar
        if isinstance(self.parent, NavBar):
            Clock.unschedule(self.parent._sync_font_sizes)
            Clock.schedule_once(self.parent._sync_font_sizes, 0)


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


class TouchScrollView(ScrollView):
    """ScrollView that blocks all touches when disabled=True.

    When inactive, returns True for touches within bounds (blocks silently).
    When active, normal ScrollView scroll/touch behaviour.
    """

    def on_touch_down(self, touch):
        if self.disabled and self.collide_point(*touch.pos):
            return True
        return super().on_touch_down(touch)


class TouchRecycleView(RecycleView):
    """RecycleView that blocks all touches when disabled=True."""

    def on_touch_down(self, touch):
        if self.disabled and self.collide_point(*touch.pos):
            return True
        return super().on_touch_down(touch)


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
