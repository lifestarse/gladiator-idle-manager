"""Dynamic UI builders using minimalist CardWidget style."""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from game.widgets import CardWidget, MinimalButton, MinimalBar
from game.theme import *


def build_roster_card(data, roster_screen):
    """Minimalist gladiator roster card."""
    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=90,
        padding=[12, 8],
        spacing=10,
        active=data["active"],
    )

    # Left: info
    info = BoxLayout(orientation="vertical", size_hint_x=0.55, spacing=2)

    name_color = ACCENT_GREEN if data["active"] else TEXT_PRIMARY
    name = Label(
        text=data["name"],
        font_size="15sp",
        bold=True,
        color=name_color,
        halign="left",
        text_size=(None, None),
        size_hint_y=0.35,
    )
    name.bind(size=lambda w, s: setattr(w, "text_size", s))

    stats = Label(
        text=f"LV {data['level']}   ATK {data['atk']}   DEF {data['def']}   HP {data['hp']}",
        font_size="10sp",
        color=TEXT_SECONDARY,
        halign="left",
        size_hint_y=0.25,
    )
    stats.bind(size=lambda w, s: setattr(w, "text_size", s))

    # Mini HP bar showing relative power
    power_bar = MinimalBar(
        size_hint_y=0.15,
        value=min(1.0, data["level"] / 20),
        bar_color=ACCENT_CYAN,
        bg_color=BG_ELEVATED,
    )

    tag = Label(
        text="ACTIVE" if data["active"] else "",
        font_size="9sp",
        color=ACCENT_GOLD if data["active"] else TEXT_MUTED,
        halign="left",
        size_hint_y=0.25,
    )
    tag.bind(size=lambda w, s: setattr(w, "text_size", s))

    info.add_widget(name)
    info.add_widget(stats)
    info.add_widget(power_bar)
    info.add_widget(tag)

    # Right: buttons
    btns = BoxLayout(orientation="vertical", size_hint_x=0.45, spacing=5, padding=[0, 4])
    idx = data["index"]

    if not data["active"]:
        select_btn = MinimalButton(
            text="SELECT",
            btn_color=BTN_PRIMARY,
            font_size=12,
            size_hint_y=0.5,
        )
        select_btn.bind(on_press=lambda inst, i=idx: roster_screen.set_active(i))
        btns.add_widget(select_btn)

    upgrade_btn = MinimalButton(
        text=f"UPGRADE  {data['cost']}g",
        btn_color=ACCENT_GOLD,
        text_color=BG_DARK,
        font_size=11,
        size_hint_y=0.5,
    )
    upgrade_btn.bind(on_press=lambda inst, i=idx: roster_screen.upgrade(i))
    btns.add_widget(upgrade_btn)

    card.add_widget(info)
    card.add_widget(btns)
    return card


def build_shop_card(item, shop_screen):
    """Minimalist shop item card."""
    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=75,
        padding=[12, 8],
        spacing=10,
    )

    # Left: info
    info = BoxLayout(orientation="vertical", size_hint_x=0.65, spacing=2)

    name = Label(
        text=item["name"],
        font_size="14sp",
        bold=True,
        color=TEXT_PRIMARY,
        halign="left",
        size_hint_y=0.5,
    )
    name.bind(size=lambda w, s: setattr(w, "text_size", s))

    desc = Label(
        text=item["desc"],
        font_size="10sp",
        color=TEXT_MUTED,
        halign="left",
        size_hint_y=0.5,
    )
    desc.bind(size=lambda w, s: setattr(w, "text_size", s))

    info.add_widget(name)
    info.add_widget(desc)

    # Right: buy button
    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=f"{item['cost']}g",
        btn_color=ACCENT_BLUE if affordable else BTN_DISABLED,
        text_color=TEXT_PRIMARY if affordable else TEXT_MUTED,
        font_size=14,
        size_hint_x=0.35,
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: shop_screen.buy(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_roster_grid(roster_screen):
    grid = roster_screen.ids.get("roster_grid")
    if not grid:
        return
    grid.clear_widgets()
    for gdata in roster_screen.gladiators_data:
        grid.add_widget(build_roster_card(gdata, roster_screen))


def refresh_shop_grid(shop_screen):
    grid = shop_screen.ids.get("shop_grid")
    if not grid:
        return
    grid.clear_widgets()
    for item in shop_screen.items_data:
        grid.add_widget(build_shop_card(item, shop_screen))
