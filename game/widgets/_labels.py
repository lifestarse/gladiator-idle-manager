# Build: 3
"""Widgets — AutoShrinkLabel + text measurement helper."""
from ._imports import *  # noqa: F401,F403

_MIN_FONT_SIZE_SP = 9
_SINGLE_LINE_MIN_SP = 7
_FIT_SAFETY = 0.97


def measure_text(text, font_size, font_name='PixelFont', bold=False):
    """Natural (unwrapped) pixel width of *text* at *font_size*.

    Uses a throwaway CoreLabel render — cheap for short UI strings, and the
    only reliable way to know intrinsic width BEFORE a Kivy Label wraps it.
    """
    if not text:
        return 0
    from kivy.core.text import Label as CoreLabel
    cl = CoreLabel(text=text, font_size=font_size, font_name=font_name,
                   bold=bold)
    cl.refresh()
    return cl.texture.size[0] if cl.texture else 0


class AutoShrinkLabel(Label):
    """Label that auto-shrinks font_size so text always fits.
    Reactive — no texture_update() calls, no Clock spam.

    single_line=True: never wrap — measure the intrinsic width via
    CoreLabel and scale the font down to fit the label width. The plain
    texture-based path can't do this: with text_size bound to the widget
    size the texture wraps first and never reports an overflow.
    """
    _base_font_size = NumericProperty(0)
    single_line = BooleanProperty(False)
    _shrinking = False

    def __init__(self, **kwargs):
        kwargs.setdefault('font_name', 'PixelFont')
        super().__init__(**kwargs)
        self._base_font_size = self.font_size
        self.bind(texture_size=self._check_fit,
                  single_line=self._fit_single_line,
                  width=self._fit_single_line)
        if self.single_line:
            # text + fixed width both set via constructor kwargs → neither
            # bind above ever fires; fit once after init settles.
            Clock.schedule_once(self._fit_single_line, 0)

    def on_text(self, *args):
        if self._shrinking:
            return
        self._shrinking = True
        self.font_size = self._base_font_size
        self._shrinking = False
        self._fit_single_line()

    def _fit_single_line(self, *args):
        if not self.single_line or self._shrinking or self.width <= 1:
            return
        avail = self.width - dp(2)
        natural = measure_text(self.text, self._base_font_size,
                               self.font_name, self.bold)
        self._shrinking = True
        if natural > avail > 0:
            ratio = avail / natural
            self.font_size = max(sp(_SINGLE_LINE_MIN_SP),
                                 self._base_font_size * ratio * _FIT_SAFETY)
        else:
            self.font_size = self._base_font_size
        self._shrinking = False

    def _check_fit(self, *args):
        if self._shrinking or self.single_line:
            return
        max_w = self.text_size[0] if self.text_size[0] else self.width
        if max_w <= 0 or self.texture_size[0] <= 0:
            return
        tw = self.texture_size[0]
        th = self.texture_size[1]
        max_h = self.height
        min_fs = sp(_MIN_FONT_SIZE_SP)
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


class PixelBadge(AutoShrinkLabel):
    """Tiny bordered status chip (skill ready/cooldown, unit statuses).

    Renders a dark plate with a 1px accent border behind the text so a
    3-letter abbreviation no longer reads as clipped garbage.
    """

    badge_color = ListProperty(list(ACCENT_CYAN))

    def __init__(self, **kwargs):
        kwargs.setdefault('single_line', True)
        kwargs.setdefault('bold', True)
        super().__init__(**kwargs)
        with self.canvas.before:
            self._bg_c = Color(*BG_ELEVATED)
            self._bg_r = Rectangle(pos=self.pos, size=self.size)
            self._br_c = Color(*self.badge_color)
            self._br_l = Line(rectangle=(0, 0, 0, 0), width=1.0)
        self.bind(pos=self._update_canvas, size=self._update_canvas,
                  badge_color=self._update_canvas, opacity=self._update_canvas)

    def _update_canvas(self, *args):
        self._bg_r.pos = self.pos
        self._bg_r.size = self.size
        self._br_l.rectangle = (self.x + 0.5, self.y + 0.5,
                                self.width - 1, self.height - 1)
        a = self.opacity
        self._bg_c.rgba = (BG_ELEVATED[0], BG_ELEVATED[1], BG_ELEVATED[2],
                           BG_ELEVATED[3] * a)
        bc = self.badge_color
        self._br_c.rgba = (bc[0], bc[1], bc[2], bc[3] * a)
