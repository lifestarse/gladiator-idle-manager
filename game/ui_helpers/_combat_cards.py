# Build: 3
"""ui_helpers._combat_cards — static builders for battle unit panels and cards."""
from ._imports import *  # noqa: F401,F403
from ._layouts import _bind_long_tap
from ._widgets import _CLASS_COLORS, _icon_label


def build_total_hp_row(summary_text, total_hp, total_max, is_expanded, toggle_callback):
    """Total HP summary bar — tap the bar itself to expand/collapse."""
    from kivy.uix.behaviors import ButtonBehavior

    BAR_H = dp(52)
    centered = f"{summary_text}({max(0, total_hp)}/{total_max})"

    container = RelativeLayout(size_hint_y=None, height=BAR_H)
    hp_pct = max(0, total_hp) / max(1, total_max)
    is_low = hp_pct < LOW_HP_THRESHOLD

    bar = MinimalBar(
        pos_hint={"x": 0, "y": 0}, size_hint=(1, 1),
        value=hp_pct,
        bar_color=HP_PLAYER if not is_low else ACCENT_RED,
        bg_color=HP_PLAYER_BG,
    )
    container.add_widget(bar)

    lbl = AutoShrinkLabel(
        text=centered, font_size="11sp", bold=True,
        color=TEXT_PRIMARY, halign="center", valign="middle",
        pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(1, 1),
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    container.add_widget(lbl)

    _bind_long_tap(container, toggle_callback)

    return container


def _build_hp_bar_widget(name, hp, max_hp, bar_color, bg_color, height=dp(40),
                         on_tap=None):
    """HP bar with name and HP centered inside. Optionally tappable."""
    hp_pct = max(0, hp) / max(1, max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD

    container = RelativeLayout(size_hint_y=None, height=height)

    bar = MinimalBar(
        pos_hint={"x": 0, "y": 0}, size_hint=(1, 1),
        value=hp_pct,
        bar_color=bar_color if not is_low else ACCENT_RED,
        bg_color=bg_color,
    )
    container.add_widget(bar)
    container._bar = bar

    centered = f"{name}  ({max(0, hp)}/{max_hp})"
    lbl = AutoShrinkLabel(
        text=centered, font_size="11sp", bold=True,
        color=TEXT_PRIMARY, halign="center", valign="middle",
        pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(1, 1),
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    container.add_widget(lbl)

    if on_tap:
        _bind_long_tap(container, on_tap)

    return container


def build_fighter_hp_row(fighter, index, heal_cost, can_afford, heal_callback,
                         on_tap=None):
    """Individual fighter HP bar — tappable for heal."""
    BAR_H = dp(48)

    bar_widget = _build_hp_bar_widget(
        fighter.name, fighter.hp, fighter.max_hp,
        HP_PLAYER, HP_PLAYER_BG, height=BAR_H,
        on_tap=on_tap,
    )
    return bar_widget


def build_unit_card(name, hp, max_hp, border_color=DIVIDER,
                    name_color=TEXT_PRIMARY, hp_color=(1, 0.3, 0.3, 1),
                    avatar_color=None, tier=1, level=None,
                    skill_text=None, fighter_class="mercenary",
                    on_tap=None):
    """Single universal unit card — identical to RosterCardView layout.
    Used on arena, roster detail, and anywhere a unit card is needed.
    Layout: [Avatar | Name | LV X | Skill | spacer | HP icon+number]
    """
    ROW_H = dp(56)

    card = CardWidget(
        orientation="horizontal", size_hint_y=None, height=dp(84),
        padding=[dp(8), dp(10)], spacing=dp(6),
    )
    card.border_color = border_color

    hp_pct = max(0, hp) / max(1, max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD

    avatar = GladiatorAvatar(
        fighter_class=fighter_class,
        accent_color=list(avatar_color or ACCENT_GREEN),
        tier=tier,
        size_hint=(None, None),
        width=dp(48), height=dp(52),
    )
    card.add_widget(avatar)

    name_lbl = AutoShrinkLabel(
        text=name, font_size="12sp", bold=True, color=name_color,
        halign="left", size_hint_x=None, width=dp(130),
        size_hint_y=None, height=ROW_H,
    )
    name_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    card.add_widget(name_lbl)

    level_lbl = AutoShrinkLabel(
        font_size="11sp", bold=True, color=list(ACCENT_GOLD),
        halign="left", size_hint_x=None, width=dp(56),
        size_hint_y=None, height=ROW_H,
    )
    level_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    if level is not None:
        level_lbl.text = f"LV {level}"
    card.add_widget(level_lbl)

    skill_badge = AutoShrinkLabel(
        font_size="11sp", bold=True, color=list(TEXT_MUTED),
        halign="center", size_hint_x=None, width=dp(40) if skill_text else 0,
        size_hint_y=None, height=ROW_H,
        opacity=1 if skill_text else 0,
    )
    if skill_text:
        skill_badge.text = skill_text
        skill_badge.color = list(ACCENT_CYAN if skill_text == "RDY" else TEXT_MUTED)
    skill_badge.bind(size=lambda w, s: setattr(w, 'text_size', s))
    card.add_widget(skill_badge)

    card.add_widget(Label(size_hint_x=1))

    stat_box = BoxLayout(
        orientation="horizontal", spacing=dp(2),
        size_hint_x=None, width=dp(94),
        size_hint_y=None, height=ROW_H,
    )
    hp_row = _icon_label(
        "sprites/icons/ic_hp.png",
        fmt_num(max(0, hp)),
        ACCENT_RED if is_low else hp_color,
        font_size="11sp", height=ROW_H,
    )
    stat_box.add_widget(hp_row)
    card.add_widget(stat_box)

    card._avatar = avatar
    card._name_lbl = name_lbl
    card._level_lbl = level_lbl
    card._skill_badge = skill_badge
    card._hp_lbl = hp_row.children[0]

    if on_tap:
        # CardWidget is ButtonBehavior+ScrollSafeButtonMixin — on_release is
        # already scroll-safe. _bind_long_tap would double the per-touch work.
        card.bind(on_release=lambda *a: on_tap(card))

    return card


def build_fighter_pit_card(fighter, on_tap=None, skill_text=None):
    """Fighter card — uses build_unit_card (same as roster)."""
    fc = getattr(fighter, "fighter_class", "mercenary")
    return build_unit_card(
        fighter.name, max(0, fighter.hp), fighter.max_hp,
        name_color=TEXT_PRIMARY if fighter.alive and fighter.hp > 0 else ACCENT_RED,
        avatar_color=_CLASS_COLORS.get(fc, ACCENT_GREEN),
        tier=getattr(fighter, "tier", 1),
        level=getattr(fighter, "level", 1),
        skill_text=skill_text, fighter_class=fc, on_tap=on_tap,
    )


def build_enemy_hp_row(enemy, show_stats=False, on_tap=None):
    """Enemy card — uses build_unit_card (same layout as fighters)."""
    fc = getattr(enemy, "fighter_class", "mercenary")
    return build_unit_card(
        enemy.name, max(0, enemy.hp), enemy.max_hp,
        border_color=ACCENT_RED,
        name_color=ACCENT_RED,
        avatar_color=ACCENT_RED,
        tier=getattr(enemy, "tier", 1),
        level=getattr(enemy, "level", None),
        fighter_class=fc, on_tap=on_tap,
    )
