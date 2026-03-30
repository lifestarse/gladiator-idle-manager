# Build: 2
from kivy.clock import Clock
from game.ui_helpers import _invalidate_grid_cache

SCREEN_ORDER = ["arena", "roster", "forge", "expedition", "lore", "more"]


def _safe_clear(grid):
    """Unbind minimum_height before clearing, schedule rebind on next frame."""
    _invalidate_grid_cache(grid)
    grid.unbind(minimum_height=grid.setter('height'))
    grid.clear_widgets()
    grid.height = 0
    Clock.schedule_once(lambda dt: _safe_rebind(grid), 0)


def _safe_rebind(grid):
    """Rebind minimum_height after all widgets are added."""
    grid.height = grid.minimum_height
    grid.bind(minimum_height=grid.setter('height'))


# --- Sword hit sound ---
_hit_sound = None

def _play_hit_sound():
    global _hit_sound
    try:
        if _hit_sound is None:
            from kivy.core.audio import SoundLoader
            _hit_sound = SoundLoader.load("sounds/hit.wav")
        if _hit_sound:
            _hit_sound.volume = 0.4
            _hit_sound.play()
    except Exception:
        pass
