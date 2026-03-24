"""Dynamic UI builders for all screens — minimalist CardWidget style."""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

from game.widgets import CardWidget, MinimalButton, MinimalBar
from game.theme import *
from game.models import RARITY_COLORS


def _auto_text_size(label):
    label.bind(size=lambda w, s: setattr(w, "text_size", s))
    return label


# ============================================================
#  ROSTER
# ============================================================

def build_roster_card(data, roster_screen):
    has_points = data.get("unused_points", 0) > 0
    card = CardWidget(
        orientation="vertical",
        size_hint_y=None,
        height=155 if has_points else 130,
        padding=[10, 6],
        spacing=3,
        active=data["active"],
    )

    if not data["alive"]:
        card.card_color = (0.15, 0.08, 0.08, 1)
        card.border_color = ACCENT_RED

    # --- Top row: name + class + buttons ---
    top_row = BoxLayout(size_hint_y=None, height=32, spacing=6)

    # Name + status
    if not data["alive"]:
        name_text = f"{data['name']} [DEAD]"
        name_color = ACCENT_RED
    elif data["on_expedition"]:
        name_text = f"{data['name']} [AWAY]"
        name_color = ACCENT_CYAN
    elif data["active"]:
        name_text = data["name"]
        name_color = ACCENT_GREEN
    else:
        name_text = data["name"]
        name_color = TEXT_PRIMARY

    top_row.add_widget(_auto_text_size(Label(
        text=name_text, font_size="13sp", bold=True, color=name_color,
        halign="left", size_hint_x=0.5,
    )))
    top_row.add_widget(_auto_text_size(Label(
        text=f"[{data.get('fighter_class', 'Mercenary')}]",
        font_size="10sp", color=TEXT_MUTED, halign="left", size_hint_x=0.25,
    )))

    idx = data["index"]
    if not data["alive"]:
        dismiss_btn = MinimalButton(
            text="X", btn_color=ACCENT_RED, font_size=10, size_hint_x=0.25,
        )
        dismiss_btn.bind(on_press=lambda inst, i=idx: roster_screen.dismiss(i))
        top_row.add_widget(dismiss_btn)
    elif not data["on_expedition"] and not data["active"]:
        select_btn = MinimalButton(
            text="SELECT", btn_color=BTN_PRIMARY, font_size=10, size_hint_x=0.25,
        )
        select_btn.bind(on_press=lambda inst, i=idx: roster_screen.set_active(i))
        top_row.add_widget(select_btn)
    else:
        tag = "ACTIVE" if data["active"] else "AWAY"
        tag_color = ACCENT_GOLD if data["active"] else ACCENT_CYAN
        top_row.add_widget(_auto_text_size(Label(
            text=tag, font_size="9sp", color=tag_color,
            halign="right", size_hint_x=0.25,
        )))
    card.add_widget(top_row)

    # --- Stats line: LV, ATK, DEF, HP, crit, dodge ---
    stats_text = (
        f"LV {data['level']}  ATK {data['atk']}  DEF {data['def']}  "
        f"HP {data['hp']}  Crit {data.get('crit', 0):.0%}  Dodge {data.get('dodge', 0):.0%}"
    )
    card.add_widget(_auto_text_size(Label(
        text=stats_text, font_size="9sp", color=TEXT_SECONDARY,
        halign="left", size_hint_y=None, height=18,
    )))

    # --- STR / AGI / VIT display ---
    stat_row = BoxLayout(size_hint_y=None, height=18, spacing=4)
    stat_row.add_widget(_auto_text_size(Label(
        text=f"STR {data.get('str', 0)}", font_size="10sp",
        color=ACCENT_RED, halign="center",
    )))
    stat_row.add_widget(_auto_text_size(Label(
        text=f"AGI {data.get('agi', 0)}", font_size="10sp",
        color=ACCENT_GREEN, halign="center",
    )))
    stat_row.add_widget(_auto_text_size(Label(
        text=f"VIT {data.get('vit', 0)}", font_size="10sp",
        color=ACCENT_BLUE, halign="center",
    )))
    card.add_widget(stat_row)

    # --- Stat distribution buttons (if unused points > 0) ---
    if has_points and data["alive"] and not data["on_expedition"]:
        pts_row = BoxLayout(size_hint_y=None, height=30, spacing=4)
        pts_row.add_widget(_auto_text_size(Label(
            text=f"{data['unused_points']} pts", font_size="10sp",
            color=ACCENT_GOLD, halign="center", size_hint_x=0.25,
        )))
        str_btn = MinimalButton(
            text="+STR", btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
            font_size=10, size_hint_x=0.25,
        )
        str_btn.bind(on_press=lambda inst, i=idx: roster_screen.add_str(i))
        pts_row.add_widget(str_btn)

        agi_btn = MinimalButton(
            text="+AGI", btn_color=ACCENT_GREEN, text_color=BG_DARK,
            font_size=10, size_hint_x=0.25,
        )
        agi_btn.bind(on_press=lambda inst, i=idx: roster_screen.add_agi(i))
        pts_row.add_widget(agi_btn)

        vit_btn = MinimalButton(
            text="+VIT", btn_color=ACCENT_BLUE, text_color=TEXT_PRIMARY,
            font_size=10, size_hint_x=0.25,
        )
        vit_btn.bind(on_press=lambda inst, i=idx: roster_screen.add_vit(i))
        pts_row.add_widget(vit_btn)
        card.add_widget(pts_row)

    # --- Equipment summary ---
    equip_parts = []
    if data.get("weapon"):
        equip_parts.append(data["weapon"]["name"])
    if data.get("armor"):
        equip_parts.append(data["armor"]["name"])
    if data.get("accessory"):
        equip_parts.append(data["accessory"]["name"])
    equip_text = " | ".join(equip_parts) if equip_parts else "No equipment"
    card.add_widget(_auto_text_size(Label(
        text=equip_text, font_size="9sp", color=TEXT_MUTED,
        halign="left", size_hint_y=None, height=16,
    )))

    # --- Injuries / kills / relics ---
    meta_parts = [f"Kills: {data['kills']}"]
    if data["relics"] > 0:
        meta_parts.append(f"Relics: {data['relics']}")
    if data["injuries"] > 0:
        meta_parts.append(f"Injuries: {data['injuries']} ({data['death_chance']:.0%} risk)")
    card.add_widget(_auto_text_size(Label(
        text="  ".join(meta_parts), font_size="9sp",
        color=ACCENT_RED if data["injuries"] > 2 else TEXT_MUTED,
        halign="left", size_hint_y=None, height=16,
    )))

    # --- Train button ---
    if data["alive"] and not data["on_expedition"]:
        upgrade_btn = MinimalButton(
            text=f"TRAIN Lv.{data['level'] + 1}  ({data['cost']}g)", btn_color=ACCENT_GOLD,
            text_color=BG_DARK, font_size=11, size_hint_y=None, height=32,
        )
        upgrade_btn.bind(on_press=lambda inst, i=idx: roster_screen.upgrade(i))
        card.add_widget(upgrade_btn)

    return card


def refresh_roster_grid(roster_screen):
    grid = roster_screen.ids.get("roster_grid")
    if not grid:
        return
    grid.clear_widgets()
    for gdata in roster_screen.gladiators_data:
        grid.add_widget(build_roster_card(gdata, roster_screen))


# ============================================================
#  FORGE
# ============================================================

def build_forge_card(item, forge_screen):
    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)

    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=80,
        padding=[12, 8],
        spacing=10,
    )
    card.border_color = rcolor

    info = BoxLayout(orientation="vertical", size_hint_x=0.6, spacing=2)

    info.add_widget(_auto_text_size(Label(
        text=item["name"], font_size="13sp", bold=True, color=rcolor,
        halign="left", size_hint_y=0.35,
    )))

    slot_text = item["slot"].upper()
    info.add_widget(_auto_text_size(Label(
        text=f"{slot_text}  [{rarity.upper()}]", font_size="9sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.25,
    )))

    stats_parts = []
    if item["atk"] > 0:
        stats_parts.append(f"+{item['atk']} ATK")
    if item["def"] > 0:
        stats_parts.append(f"+{item['def']} DEF")
    if item["hp"] > 0:
        stats_parts.append(f"+{item['hp']} HP")
    info.add_widget(_auto_text_size(Label(
        text="  ".join(stats_parts), font_size="10sp",
        color=ACCENT_GREEN, halign="left", size_hint_y=0.4,
    )))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=f"{item['cost']}g", font_size=13, size_hint_x=0.4,
        btn_color=rcolor if affordable else BTN_DISABLED,
        text_color=TEXT_PRIMARY if affordable else TEXT_MUTED,
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: forge_screen.buy(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_forge_grid(forge_screen):
    grid = forge_screen.ids.get("forge_grid")
    if not grid:
        return
    grid.clear_widgets()
    for item in forge_screen.forge_items:
        grid.add_widget(build_forge_card(item, forge_screen))


# ============================================================
#  EXPEDITIONS
# ============================================================

def build_expedition_card(exp, fighters, expedition_screen):
    card = CardWidget(
        orientation="vertical",
        size_hint_y=None,
        height=130,
        padding=[12, 8],
        spacing=4,
    )

    # Header
    header = BoxLayout(size_hint_y=0.35, spacing=5)
    header.add_widget(_auto_text_size(Label(
        text=exp["name"], font_size="14sp", bold=True,
        color=ACCENT_PURPLE, halign="left",
    )))
    header.add_widget(_auto_text_size(Label(
        text=exp["duration_text"], font_size="11sp",
        color=TEXT_SECONDARY, halign="right", size_hint_x=0.3,
    )))
    card.add_widget(header)

    card.add_widget(_auto_text_size(Label(
        text=exp["desc"], font_size="10sp", color=TEXT_MUTED,
        halign="left", size_hint_y=0.2,
    )))

    # Stats row
    stats = BoxLayout(size_hint_y=0.2, spacing=3)
    stats.add_widget(_auto_text_size(Label(
        text=f"Lv.{exp['min_level']}+", font_size="10sp",
        color=ACCENT_CYAN, halign="left",
    )))
    stats.add_widget(_auto_text_size(Label(
        text=f"Danger: {exp['danger']:.0%}", font_size="10sp",
        color=ACCENT_RED, halign="center",
    )))
    stats.add_widget(_auto_text_size(Label(
        text=f"Relic: {exp['relic_chance']:.0%}", font_size="10sp",
        color=ACCENT_GOLD, halign="right",
    )))
    card.add_widget(stats)

    # Send buttons — one per available fighter
    send_row = BoxLayout(size_hint_y=0.25, spacing=5)
    eligible = [f for f in fighters if f["level"] >= exp["min_level"]]
    if eligible:
        for f_data in eligible[:3]:  # max 3 buttons
            btn = MinimalButton(
                text=f"Send {f_data['name']}", font_size=10,
                btn_color=ACCENT_PURPLE,
            )
            btn.bind(on_press=lambda inst, fi=f_data["index"], eid=exp["id"]:
                     expedition_screen.send(fi, eid))
            send_row.add_widget(btn)
    else:
        send_row.add_widget(_auto_text_size(Label(
            text="No eligible fighters", font_size="10sp", color=TEXT_MUTED,
        )))
    card.add_widget(send_row)
    return card


def build_expedition_status_card(status):
    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=50,
        padding=[12, 6],
        spacing=10,
    )
    card.border_color = ACCENT_CYAN

    card.add_widget(_auto_text_size(Label(
        text=f"{status['fighter_name']} @ {status['expedition_name']}",
        font_size="12sp", bold=True, color=ACCENT_CYAN, halign="left",
    )))

    card.add_widget(_auto_text_size(Label(
        text=status["remaining_text"], font_size="14sp", bold=True,
        color=ACCENT_GOLD, halign="right", size_hint_x=0.35,
    )))
    return card


def refresh_expedition_grid(expedition_screen):
    # Active expeditions
    status_grid = expedition_screen.ids.get("expedition_status_grid")
    if status_grid:
        status_grid.clear_widgets()
        for s in expedition_screen.status_data:
            status_grid.add_widget(build_expedition_status_card(s))

    # Available expeditions
    grid = expedition_screen.ids.get("expedition_grid")
    if not grid:
        return
    grid.clear_widgets()
    for exp in expedition_screen.expeditions_data:
        grid.add_widget(build_expedition_card(
            exp, expedition_screen.fighters_for_send, expedition_screen
        ))


# ============================================================
#  MARKET (Shop) — now inside MoreScreen
# ============================================================

def build_shop_card(item, shop_screen):
    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=75,
        padding=[12, 8],
        spacing=10,
    )

    info = BoxLayout(orientation="vertical", size_hint_x=0.65, spacing=2)
    info.add_widget(_auto_text_size(Label(
        text=item["name"], font_size="14sp", bold=True,
        color=TEXT_PRIMARY, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(Label(
        text=item["desc"], font_size="10sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=f"{item['cost']}g", font_size=14, size_hint_x=0.35,
        btn_color=ACCENT_BLUE if affordable else BTN_DISABLED,
        text_color=TEXT_PRIMARY if affordable else TEXT_MUTED,
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: shop_screen.buy(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_shop_grid(shop_screen):
    grid = shop_screen.ids.get("shop_grid")
    if not grid:
        return
    grid.clear_widgets()
    for item in shop_screen.items_data:
        grid.add_widget(build_shop_card(item, shop_screen))


# ============================================================
#  BATTLE LOG (ArenaScreen)
# ============================================================

def refresh_battle_log(arena_screen):
    """Update battle log label — already handled by property binding."""
    pass


# ============================================================
#  ACHIEVEMENTS (LoreScreen)
# ============================================================

def build_achievement_card(ach):
    unlocked = ach.get("unlocked", False)
    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=60,
        padding=[10, 6],
        spacing=8,
    )
    if unlocked:
        card.border_color = ACCENT_GOLD
        card.card_color = (0.12, 0.12, 0.08, 1)

    info = BoxLayout(orientation="vertical", size_hint_x=0.7, spacing=1)
    name_color = ACCENT_GOLD if unlocked else TEXT_SECONDARY
    info.add_widget(_auto_text_size(Label(
        text=ach["name"], font_size="13sp", bold=True,
        color=name_color, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(Label(
        text=ach["desc"], font_size="9sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    reward = BoxLayout(orientation="vertical", size_hint_x=0.3)
    status_text = "DONE" if unlocked else f"{ach['diamonds']} dia"
    status_color = ACCENT_GREEN if unlocked else ACCENT_CYAN
    reward.add_widget(_auto_text_size(Label(
        text=status_text, font_size="12sp", bold=True,
        color=status_color, halign="center",
    )))

    card.add_widget(info)
    card.add_widget(reward)
    return card


def refresh_achievement_grid(lore_screen):
    grid = lore_screen.ids.get("achievement_grid")
    if not grid:
        return
    grid.clear_widgets()
    for ach in lore_screen.achievements_data:
        grid.add_widget(build_achievement_card(ach))


# ============================================================
#  DIAMOND SHOP (LoreScreen)
# ============================================================

def build_diamond_shop_card(item, lore_screen):
    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=65,
        padding=[10, 6],
        spacing=8,
    )
    card.border_color = ACCENT_CYAN

    info = BoxLayout(orientation="vertical", size_hint_x=0.6, spacing=1)
    info.add_widget(_auto_text_size(Label(
        text=item["name"], font_size="13sp", bold=True,
        color=ACCENT_CYAN, halign="left", size_hint_y=0.45,
    )))
    info.add_widget(_auto_text_size(Label(
        text=item["desc"], font_size="9sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.55,
    )))

    affordable = item.get("affordable", False)
    buy_btn = MinimalButton(
        text=f"{item['cost']} dia", font_size=12, size_hint_x=0.4,
        btn_color=ACCENT_CYAN if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: lore_screen.buy_diamond_item(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_diamond_shop_grid(lore_screen):
    grid = lore_screen.ids.get("diamond_shop_grid")
    if not grid:
        return
    grid.clear_widgets()
    for item in lore_screen.diamond_shop_data:
        grid.add_widget(build_diamond_shop_card(item, lore_screen))
