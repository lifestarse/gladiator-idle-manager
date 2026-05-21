# Build: 6
"""ui_helpers._roster_grid — refresh_roster_grid entry point."""
from ._imports import *  # noqa: F401,F403
from ._widgets import _auto_text_size


# ============================================================
#  ROSTER
# ============================================================


def build_roster_card(data, roster_screen):
    """Minimal card: name, level, STR/AGI/HP icons. Tap to open detail popup."""
    from game.widgets import BaseCard, MinimalBar

    stamina = data.get("stamina", 100)
    fatigue = data.get("fatigue", 0)
    exhausted = data.get("exhausted", False)

    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(96),
                    padding=[dp(10), dp(6)], spacing=dp(4))

    if not data["alive"]:
        card.card_color = (0.15, 0.08, 0.08, 1)
        card.border_color = ACCENT_RED
    elif exhausted:
        card.card_color = (0.18, 0.06, 0.06, 1)
        card.border_color = ACCENT_RED
    elif fatigue >= 50:
        card.card_color = (0.18, 0.12, 0.06, 1)
    elif stamina <= 20:
        card.card_color = (0.18, 0.16, 0.06, 1)

    idx = data["index"]

    if not data["alive"]:
        name_text = f"{data['name']} [{t('dead_tag')}]"
        name_color = ACCENT_RED
    elif exhausted:
        name_text = f"{data['name']} 🔒"
        name_color = ACCENT_RED
    elif data["on_expedition"]:
        name_text = data["name"]
        name_color = ACCENT_CYAN
    else:
        name_text = data["name"]
        name_color = TEXT_PRIMARY

    # Row 1: Name + Level + status/dismiss
    status_widget = Label(size_hint_x=0.25)
    if not data["alive"]:
        status_widget = MinimalButton(
            text="X", btn_color=ACCENT_RED, font_size=11, size_hint_x=0.25,
        )
        status_widget.bind(on_press=lambda inst, i=idx: roster_screen.dismiss(i))
    elif data["on_expedition"]:
        status_widget = _auto_text_size(AutoShrinkLabel(
            text=t("away_tag"), font_size="10sp", color=ACCENT_CYAN,
            halign="right", size_hint_x=0.25,
        ))
    card.add_text_row(
        (name_text, sp(11), True, name_color, 0.55),
        (f"LV {data['level']}", sp(11), True, ACCENT_GOLD, 0.2),
        status_widget,
        height=dp(34),
    )

    # Row 2: HP
    card.add_icon_labels([
        ("sprites/icons/ic_hp.png", fmt_num(data['hp']), (1, 0.3, 0.3, 1), sp(8)),
    ], height=dp(28), spacing=dp(8))

    # Row 3: stamina + fatigue mini-bars (only meaningful for living fighters).
    if data["alive"]:
        sta_color = (0.95, 0.85, 0.2, 1) if stamina <= 20 else (0.4, 0.85, 0.4, 1)
        if exhausted:
            fat_color = (0.95, 0.2, 0.2, 1)
        elif fatigue >= 50:
            fat_color = (0.95, 0.55, 0.15, 1)
        else:
            fat_color = (0.55, 0.55, 0.65, 1)
        bars = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(8), spacing=dp(4))
        sta_bar = MinimalBar(value=stamina / 100.0,
                             bar_color=list(sta_color),
                             bg_color=[0.12, 0.12, 0.12, 1])
        fat_bar = MinimalBar(value=fatigue / 100.0,
                             bar_color=list(fat_color),
                             bg_color=[0.12, 0.12, 0.12, 1])
        bars.add_widget(sta_bar)
        bars.add_widget(fat_bar)
        card.add_widget(bars)

    card.bind(on_release=lambda *a, i=idx: roster_screen.show_fighter_detail(i))
    return card


def refresh_roster_grid(roster_screen):
    rv = roster_screen.ids.get('roster_rv')
    if not rv:
        return
    rv.data = [dict(d) for d in roster_screen.gladiators_data]
