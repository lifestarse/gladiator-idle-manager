# Build: 1
"""ui_helpers._combat_animations — in-place updates and flash effects for battle cards."""
from ._imports import *  # noqa: F401,F403


def flash_hp_bar(bar_widget, flash_color=ACCENT_RED):
    """Flash a bar red briefly to show damage taken."""
    from kivy.animation import Animation
    if not hasattr(bar_widget, '_bar') or bar_widget._bar is None:
        return
    bar = bar_widget._bar
    orig = list(bar.bg_color)
    bar.bg_color = list(flash_color)
    anim = Animation(duration=0.15)
    anim.bind(on_complete=lambda *a: setattr(bar, 'bg_color', orig))
    anim.start(bar)


def update_fighter_pit_card(card, fighter, skill_text=None):
    """Update unit card in-place."""
    hp_pct = max(0, fighter.hp) / max(1, fighter.max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD
    card._name_lbl.color = TEXT_PRIMARY if fighter.alive and fighter.hp > 0 else ACCENT_RED
    card._hp_lbl.text = fmt_num(max(0, fighter.hp))
    card._hp_lbl.color = ACCENT_RED if is_low else (1, 0.3, 0.3, 1)
    badge = card._skill_badge
    if badge and skill_text is not None:
        badge.text = skill_text
        badge.color = list(ACCENT_CYAN if skill_text == "RDY" else TEXT_MUTED)
        badge.width = dp(40)
        badge.opacity = 1


def update_enemy_hp_row(row, enemy):
    """Update unit card in-place."""
    hp_pct = max(0, enemy.hp) / max(1, enemy.max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD
    row._hp_lbl.text = fmt_num(max(0, enemy.hp))
    row._hp_lbl.color = ACCENT_RED if is_low else (1, 0.3, 0.3, 1)
