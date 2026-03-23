"""Dynamic UI builders for roster and shop screens."""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.app import App


def build_roster_card(gladiator_data, roster_screen):
    """Build a single gladiator card widget."""
    card = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=80,
        padding=5,
        spacing=5,
    )

    is_active = gladiator_data["active"]
    bg_color = (0.2, 0.4, 0.2, 1) if is_active else (0.2, 0.2, 0.2, 1)

    # Info section
    info = BoxLayout(orientation="vertical", size_hint_x=0.5)
    name_label = Label(
        text=("► " if is_active else "") + gladiator_data["name"],
        font_size="14sp",
        bold=True,
        color=(0.4, 1, 0.4, 1) if is_active else (0.8, 0.8, 0.8, 1),
        halign="left",
        text_size=(None, None),
    )
    stats_label = Label(
        text=f"Lv.{gladiator_data['level']}  ATK:{gladiator_data['atk']}  DEF:{gladiator_data['def']}  HP:{gladiator_data['hp']}",
        font_size="11sp",
        color=(0.7, 0.7, 0.7, 1),
    )
    info.add_widget(name_label)
    info.add_widget(stats_label)

    # Buttons
    btns = BoxLayout(orientation="vertical", size_hint_x=0.5, spacing=3)

    idx = gladiator_data["index"]
    select_btn = Button(
        text="Active" if is_active else "Select",
        font_size="12sp",
        background_color=(0.3, 0.6, 0.3, 1) if is_active else (0.4, 0.4, 0.4, 1),
        disabled=is_active,
    )
    select_btn.bind(on_press=lambda inst, i=idx: roster_screen.set_active(i))

    upgrade_btn = Button(
        text=f"Upgrade ({gladiator_data['cost']}g)",
        font_size="12sp",
        background_color=(0.6, 0.5, 0.1, 1),
    )
    upgrade_btn.bind(on_press=lambda inst, i=idx: roster_screen.upgrade(i))

    btns.add_widget(select_btn)
    btns.add_widget(upgrade_btn)

    card.add_widget(info)
    card.add_widget(btns)
    return card


def build_shop_card(item_data, shop_screen):
    """Build a single shop item widget."""
    card = BoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=70,
        padding=5,
        spacing=5,
    )

    info = BoxLayout(orientation="vertical", size_hint_x=0.6)
    info.add_widget(Label(
        text=item_data["name"],
        font_size="14sp",
        bold=True,
        color=(0.8, 0.85, 1, 1),
        halign="left",
    ))
    info.add_widget(Label(
        text=item_data["desc"],
        font_size="11sp",
        color=(0.6, 0.6, 0.6, 1),
    ))

    affordable = item_data["affordable"]
    buy_btn = Button(
        text=f"{item_data['cost']}g",
        font_size="14sp",
        size_hint_x=0.4,
        background_color=(0.2, 0.5, 0.7, 1) if affordable else (0.3, 0.3, 0.3, 1),
    )
    buy_btn.bind(on_press=lambda inst, iid=item_data["id"]: shop_screen.buy(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_roster_grid(roster_screen):
    """Rebuild the roster grid with current gladiator data."""
    grid = roster_screen.ids.get("roster_grid")
    if not grid:
        return
    grid.clear_widgets()
    for gdata in roster_screen.gladiators_data:
        grid.add_widget(build_roster_card(gdata, roster_screen))


def refresh_shop_grid(shop_screen):
    """Rebuild the shop grid with current item data."""
    grid = shop_screen.ids.get("shop_grid")
    if not grid:
        return
    grid.clear_widgets()
    for item in shop_screen.items_data:
        grid.add_widget(build_shop_card(item, shop_screen))
