# Build: 5
import logging

from kivy.app import App
from kivy.clock import Clock
from game.ui_helpers import _invalidate_grid_cache

_log = logging.getLogger(__name__)

# Fallback used before App.engine exists (headless tests, early startup).
_DEFAULT_SOUND_VOLUME = 1.0


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


def _current_sound_volume():
    """Read sound volume from engine; fall back when engine isn't ready."""
    app = App.get_running_app()
    engine = getattr(app, "engine", None) if app is not None else None
    vol = getattr(engine, "sound_volume", _DEFAULT_SOUND_VOLUME)
    try:
        return max(0.0, min(1.0, float(vol)))
    except (TypeError, ValueError):
        return _DEFAULT_SOUND_VOLUME


def apply_sound_volume(volume: float) -> None:
    """Push a new volume to the already-loaded hit sound (if any).

    Called from the settings slider so the change is audible immediately
    without waiting for the next attack. Safe to call when the sound
    hasn't been loaded yet — the next _play_hit_sound() will pick up the
    engine value via _current_sound_volume().
    """
    if _hit_sound is not None:
        try:
            _hit_sound.volume = max(0.0, min(1.0, float(volume)))
        except (TypeError, ValueError):
            pass


def _play_hit_sound():
    global _hit_sound
    try:
        if _hit_sound is None:
            from kivy.core.audio import SoundLoader
            _hit_sound = SoundLoader.load("sounds/hit.wav")
        if _hit_sound:
            _hit_sound.volume = _current_sound_volume()
            _hit_sound.play()
    except Exception as exc:
        # Non-fatal: audio may be unavailable (headless CI, missing file,
        # backend error). Log at debug so it doesn't spam production logs.
        _log.debug("hit sound unavailable: %s", exc)
