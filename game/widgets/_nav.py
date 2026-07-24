# Build: 3
"""Widgets — NavBar, NavButton, TouchPanel."""
from ._imports import *  # noqa: F401,F403
from ._scroll import ScrollSafeButtonMixin  # noqa: F401


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
