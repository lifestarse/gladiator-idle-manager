# Build: 5
"""ui_helpers._layouts — grid batching, rebuild-cache keys, tap binding."""
from kivy.clock import Clock

from ._imports import *  # noqa: F401,F403


# Press-and-hold auto-repeat defaults. The delay is a feel constant shared by
# every holdable button; the interval is per-button (see bind_hold_repeat).
_HOLD_REPEAT_DELAY = 0.35
_HOLD_REPEAT_INTERVAL = 0.10


def _invalidate_grid_cache(grid):
    """Wipe every _*_key cache stored on a grid widget."""
    for attr in list(vars(grid)):
        if attr.endswith('_key'):
            setattr(grid, attr, None)


def _needs_rebuild(obj, key_attr, new_key, require_children=False):
    """Check if cached key changed. Updates key and returns True if rebuild needed.

    Counterpart of _invalidate_grid_cache: that one clears every _*_key,
    this one writes a single _*_key and reports whether it moved.

    Lives here rather than on BaseScreen so that game.ui_helpers never has
    to import game.base_screen back (base_screen imports this package at
    module level; the reverse edge closed an import cycle). BaseScreen
    re-binds it as a staticmethod so `self._needs_rebuild(...)` still works.

    Args:
        obj: object holding the cache key (screen, grid widget, etc.)
        key_attr: attribute name for the cache key (e.g. '_roster_key')
        new_key: new key value to compare
        require_children: if True, also rebuild when obj has no children
    """
    old = getattr(obj, key_attr, None)
    if old == new_key and (not require_children or getattr(obj, 'children', True)):
        return False
    setattr(obj, key_attr, new_key)
    return True


@contextmanager
def grid_batch(grid):
    """Context manager: unbinds minimum_height during widget adds, rebinds after.
    Usage:
        with grid_batch(grid):
            grid.clear_widgets()
            grid.add_widget(...)
    """
    _invalidate_grid_cache(grid)
    grid.unbind(minimum_height=grid.setter('height'))
    try:
        yield grid
    finally:
        grid.height = grid.minimum_height
        grid.bind(minimum_height=grid.setter('height'))


def _batch_fill_grid(grid, widgets):
    """Add widgets to grid with only one layout pass instead of N.

    Unbinds the minimum_height→height KV rule before the loop so that
    each add_widget() does NOT trigger a full layout recalculation.
    Sets height once at the end, then rebinds.
    Skips reparenting if widgets are already the grid's children.
    """
    if (grid.children and len(grid.children) == len(widgets)
            and all(a is b for a, b in zip(reversed(grid.children), widgets))):
        return
    _invalidate_grid_cache(grid)
    grid.unbind(minimum_height=grid.setter('height'))
    grid.clear_widgets()
    for w in widgets:
        if w.parent:
            w.parent.remove_widget(w)
        grid.add_widget(w)
    grid.height = grid.minimum_height
    grid.bind(minimum_height=grid.setter('height'))


def bind_hold_repeat(btn, on_step, on_finish=None,
                     delay=_HOLD_REPEAT_DELAY, interval=_HOLD_REPEAT_INTERVAL):
    """Wire press-and-hold auto-repeat onto a button.

    ``on_step()`` fires once on press and then every ``interval`` seconds
    for as long as the button stays held, the repeat starting ``delay``
    seconds after the press. It returns True to keep repeating and False
    to stop; False from the initial press means no repeat is scheduled at
    all. ``on_finish()``, when given, runs on release once the repeat is
    torn down — the caller decides there whether anything actually
    happened (persisting, refreshing the screen).

    ``interval`` is per-button and belongs at the call site: a step that
    spends gold wants a slower repeat than a free one. Pass it by keyword
    so the chosen pace stays readable where the button is built.

    The Clock events live in this closure only; a press that never sees
    its touch-up (widget rebuilt mid-hold) is cancelled by the next press
    rather than ticking forever.
    """
    state = {"delay_event": None, "hold_event": None}

    def _cancel():
        for key in ("delay_event", "hold_event"):
            event = state[key]
            if event is not None:
                event.cancel()
                state[key] = None

    def _tick(_dt):
        if on_step():
            return True
        _cancel()
        return False

    def _start_repeat(_dt):
        state["delay_event"] = None
        state["hold_event"] = Clock.schedule_interval(_tick, interval)

    def _on_press(_inst):
        _cancel()
        if not on_step():
            return
        state["delay_event"] = Clock.schedule_once(_start_repeat, delay)

    def _on_release(_inst):
        _cancel()
        if on_finish is not None:
            on_finish()

    btn.bind(on_press=_on_press, on_release=_on_release)


def _bind_long_tap(widget, callback):
    """Bind simple tap (with scroll protection) to fire callback on touch_up."""
    def _on_down(w, touch):
        if not w.collide_point(*touch.pos):
            return False
        touch.ud.setdefault('_tap_t', {})[id(w)] = True
        return False

    def _on_up(w, touch):
        if touch.grab_current is not None:
            return False
        if not w.collide_point(*touch.pos):
            return False
        if hasattr(touch, 'ox') and hasattr(touch, 'oy'):
            dx = abs(touch.x - touch.ox)
            dy = abs(touch.y - touch.oy)
            if dx > dp(8) or dy > dp(8):
                return False
        if not touch.ud.get('_tap_t', {}).get(id(w)):
            return False
        callback(w)
        return True

    widget.bind(on_touch_down=_on_down)
    widget.bind(on_touch_up=_on_up)
