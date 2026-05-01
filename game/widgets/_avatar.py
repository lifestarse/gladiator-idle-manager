# Build: 2
"""Widgets — GladiatorAvatar (sprite-based)."""
from ._imports import *  # noqa: F401,F403


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
