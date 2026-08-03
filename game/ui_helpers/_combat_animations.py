# Build: 2
"""ui_helpers._combat_animations — flash effects for battle cards."""
from ._imports import *  # noqa: F401,F403


def flash_hp_bar(bar_widget, flash_color=ACCENT_RED):
    """Flash a bar red briefly to show damage taken.

    Reaches into ``bar_widget._bar`` — the MinimalBar every arena viewclass
    exposes under that name (game/ui_helpers/_arena_cell.py).
    """
    from kivy.animation import Animation
    if not hasattr(bar_widget, '_bar') or bar_widget._bar is None:
        return
    bar = bar_widget._bar
    orig = list(bar.bg_color)
    bar.bg_color = list(flash_color)
    anim = Animation(duration=0.15)
    anim.bind(on_complete=lambda *a: setattr(bar, 'bg_color', orig))
    anim.start(bar)
