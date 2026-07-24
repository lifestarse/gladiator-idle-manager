# Build: 4
"""Widgets — MinimalButton (pixel-framed, variant-aware)."""
from ._imports import *  # noqa: F401,F403
from ._imports import _SCROLL_THRESHOLD  # noqa: F401
from ._scroll import ScrollSafeButtonMixin

_VARIANTS = ('primary', 'secondary', 'ghost')
_PRESS_DARKEN = 0.82
_SECONDARY_PRESS_LIGHTEN = 1.3
_GHOST_BORDER_ALPHA = 0.55
_SECONDARY_BEVEL_SCALE = 0.5
_DISABLED_ICON_ALPHA = 0.35


def _scaled(color, factor):
    r, g, b, a = color
    return (min(1, r * factor), min(1, g * factor), min(1, b * factor), a)


class MinimalButton(ScrollSafeButtonMixin, ButtonBehavior, Widget):
    """Pixel-art button: dark contour, top highlight, bottom shadow,
    content sinks while pressed.

    variant:
      'primary'   — filled accent slab (default, loudest)
      'secondary' — dark fill, accent border + accent text
      'ghost'     — transparent fill, dim border; quiet toolbar actions

    font_size is a raw point size: pass plain integers (e.g. 11), NOT
    sp(11). The button applies sp() internally so the rendered text scales
    with screen density. Passing already-scaled values would double-scale.
    """

    text = StringProperty("")
    btn_color = ListProperty(BTN_PRIMARY)
    text_color = ListProperty(TEXT_PRIMARY)
    font_size = NumericProperty(11)
    icon_source = StringProperty("")
    variant = StringProperty("primary")

    def on_touch_down(self, touch):
        if self.disabled:
            return False
        return super().on_touch_down(touch)

    def __init__(self, **kwargs):
        # Explicit text_color wins over the variant's derived text colour.
        self._explicit_text_color = 'text_color' in kwargs
        super().__init__(**kwargs)
        self._base_fs = sp(self.font_size)
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
            self._bg_color = Color(*self.btn_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            self._hi_color = Color(*BEVEL_LIGHT)
            self._hi_rect = Rectangle(pos=self.pos, size=(0, 0))
            self._sh_color = Color(*BEVEL_DARK)
            self._sh_rect = Rectangle(pos=self.pos, size=(0, 0))
            self._br_color = Color(*BTN_OUTLINE)
            self._br_line = Line(rectangle=(0, 0, 0, 0), width=1.2)
        self.bind(pos=self._sync, size=self._on_resize,
                  text=self._update_text, font_size=self._update_font_size,
                  btn_color=self._restyle, variant=self._restyle,
                  state=self._on_state, disabled=self._restyle,
                  text_color=self._on_text_color,
                  icon_source=self._update_icon)
        if self.icon_source:
            self._update_icon()
        self._restyle()

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
        sink = dp(BTN_PRESS_OFFSET_PX) if self.state == 'down' else 0
        self._anchor.pos = (self.x, self.y - sink)
        self._anchor.size = self.size
        self._bg_rect.pos = self.pos
        self._bg_rect.size = self.size
        edge = dp(BEVEL_EDGE_PX)
        self._hi_rect.pos = (self.x, self.top - edge)
        self._hi_rect.size = (self.width, edge)
        self._sh_rect.pos = (self.x, self.y)
        self._sh_rect.size = (self.width, edge)
        self._br_line.rectangle = (
            self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1)

    def _on_state(self, *args):
        self._sync()
        self._restyle()

    def _restyle(self, *args):
        """Apply variant + state + disabled colours to the canvas."""
        down = self.state == 'down'
        accent = list(self.btn_color)
        if self.disabled:
            if self.variant == 'ghost':
                self._bg_color.rgba = (0, 0, 0, 0)
                self._br_color.rgba = (TEXT_MUTED[0], TEXT_MUTED[1],
                                       TEXT_MUTED[2], 0.4)
            else:
                self._bg_color.rgba = list(BTN_DISABLED)
                self._br_color.rgba = list(BTN_OUTLINE)
            self._hi_color.rgba = (0, 0, 0, 0)
            self._sh_color.rgba = (0, 0, 0, 0)
            self._label.color = list(TEXT_MUTED)
            if self._icon:
                self._icon.color = [1, 1, 1, _DISABLED_ICON_ALPHA]
            return
        if self._icon:
            self._icon.color = [1, 1, 1, 1]
        v = self.variant if self.variant in _VARIANTS else 'primary'
        if v == 'primary':
            self._bg_color.rgba = _scaled(accent, _PRESS_DARKEN) if down else accent
            self._br_color.rgba = list(BTN_OUTLINE)
            hi_a, sh_a = BEVEL_LIGHT[3], BEVEL_DARK[3]
            self._label.color = list(self.text_color)
        elif v == 'secondary':
            fill = list(BG_ELEVATED)
            self._bg_color.rgba = _scaled(fill, _SECONDARY_PRESS_LIGHTEN) if down else fill
            self._br_color.rgba = accent
            hi_a = BEVEL_LIGHT[3] * _SECONDARY_BEVEL_SCALE
            sh_a = BEVEL_DARK[3] * _SECONDARY_BEVEL_SCALE
            self._label.color = (list(self.text_color)
                                 if self._explicit_text_color else accent)
        else:  # ghost
            self._bg_color.rgba = (1, 1, 1, 0.05) if down else (0, 0, 0, 0)
            self._br_color.rgba = (accent[0], accent[1], accent[2],
                                   _GHOST_BORDER_ALPHA)
            hi_a = sh_a = 0
            self._label.color = (list(self.text_color)
                                 if self._explicit_text_color else accent)
        # Pressed = bevel inverts (light moves to the bottom edge)
        if down:
            self._hi_color.rgba = (0, 0, 0, sh_a)
            self._sh_color.rgba = (1, 1, 1, hi_a)
        else:
            self._hi_color.rgba = (1, 1, 1, hi_a)
            self._sh_color.rgba = (0, 0, 0, sh_a)

    def _update_text(self, *args):
        self._label.text = self.text
        self._label.font_size = self._base_fs

    def _update_font_size(self, *args):
        self._base_fs = sp(self.font_size)
        self._label.font_size = sp(self.font_size)

    def _on_text_color(self, *args):
        self._explicit_text_color = True
        self._restyle()

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
        # _on_tex normally drives _box.size from the label's texture_size,
        # but when text="" the texture is (0,0) and _on_tex fires BEFORE
        # the icon is added (during __init__) — Kivy never refires it on
        # a child add, so the icon would end up in a zero-width container
        # and render invisible. Forcing _on_tex after icon mutation picks
        # up the icon's dimensions and re-centres the layout.
        self._on_tex()
