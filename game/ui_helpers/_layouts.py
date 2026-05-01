# Build: 1
"""ui_helpers._layouts — grid batching and tap-binding primitives."""
from ._imports import *  # noqa: F401,F403


_HOLD_MS = 100


def _invalidate_grid_cache(grid):
    """Wipe every _*_key cache stored on a grid widget."""
    for attr in list(vars(grid)):
        if attr.endswith('_key'):
            setattr(grid, attr, None)


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
