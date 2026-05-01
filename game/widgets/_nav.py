# Build: 2
"""Widgets — NavBar, TouchPanel."""
from ._imports import *  # noqa: F401,F403
from ._scroll import ScrollSafeButtonMixin  # noqa: F401


class NavBar(BoxLayout):
    """Navigation bar — set active_screen to highlight the current tab."""
    active_screen = StringProperty("arena")

    def _sync_font_sizes(self, *args):
        """Make all NavButton labels use the same (smallest) font_size."""
        from ._buttons import NavButton  # lazy: avoids _nav↔_buttons cycle
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
