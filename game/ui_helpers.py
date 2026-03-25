# Build: 3
"""Dynamic UI builders for all screens — minimalist CardWidget style."""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp

from game.widgets import CardWidget, MinimalButton, MinimalBar
from game.theme import *
from game.models import RARITY_COLORS, fmt_num
from game.localization import t


def _auto_text_size(label):
    label.bind(size=lambda w, s: setattr(w, "text_size", s))
    return label


def _diamond_label(amount, font_size="17sp", color=ACCENT_CYAN):
    """BoxLayout with number + diamond icon (icon to the right)."""
    box = BoxLayout(orientation="horizontal", size_hint=(1, 1), spacing=dp(2))
    lbl = Label(
        text=str(amount), font_size=font_size, bold=True,
        color=color, halign="right", valign="middle",
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    box.add_widget(lbl)
    box.add_widget(Image(
        source="icons/ic_diamond.png", fit_mode="contain",
        size_hint=(None, 1), width=dp(24),
    ))
    return box


# ============================================================
#  ROSTER
# ============================================================

def _icon_label(icon_src, text, color, font_size="16sp", height=dp(28)):
    """Helper: icon image + label in a horizontal box."""
    row = BoxLayout(size_hint_y=None, height=height, spacing=dp(2))
    ico = Image(source=icon_src, fit_mode="contain",
                size_hint=(None, 1), width=height * 0.8)
    ico.color = [1, 1, 1, 1]
    row.add_widget(ico)
    lbl = Label(text=str(text), font_size=font_size, bold=True,
                color=color, halign="left", valign="middle")
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    row.add_widget(lbl)
    return row


def build_roster_card(data, roster_screen):
    """Minimal card: name, level, STR/AGI/HP icons. Tap to open detail popup."""
    card = CardWidget(
        orientation="vertical",
        size_hint_y=None,
        height=dp(90),
        padding=[dp(10), dp(6)],
        spacing=dp(4),
    )

    if not data["alive"]:
        card.card_color = (0.15, 0.08, 0.08, 1)
        card.border_color = ACCENT_RED

    idx = data["index"]

    # --- Row 1: Name + Level + status tag ---
    top_row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(6))

    if not data["alive"]:
        name_text = f"{data['name']} [{t('dead_tag')}]"
        name_color = ACCENT_RED
    elif data["on_expedition"]:
        name_text = f"{data['name']} [{t('away_tag')}]"
        name_color = ACCENT_CYAN
    else:
        name_text = data["name"]
        name_color = TEXT_PRIMARY

    top_row.add_widget(_auto_text_size(Label(
        text=name_text, font_size="18sp", bold=True, color=name_color,
        halign="left", size_hint_x=0.55,
    )))
    top_row.add_widget(_auto_text_size(Label(
        text=f"LV {data['level']}", font_size="17sp", bold=True,
        color=ACCENT_GOLD, halign="center", size_hint_x=0.2,
    )))

    # Status tag or dismiss button
    if not data["alive"]:
        dismiss_btn = MinimalButton(
            text="X", btn_color=ACCENT_RED, font_size=15, size_hint_x=0.25,
        )
        dismiss_btn.bind(on_press=lambda inst, i=idx: roster_screen.dismiss(i))
        top_row.add_widget(dismiss_btn)
    elif data["on_expedition"]:
        top_row.add_widget(_auto_text_size(Label(
            text=t("away_tag"), font_size="14sp", color=ACCENT_CYAN,
            halign="right", size_hint_x=0.25,
        )))
    else:
        # No tag for alive non-expedition fighters
        top_row.add_widget(Label(size_hint_x=0.25))
    card.add_widget(top_row)

    # --- Row 2: STR icon + val | AGI icon + val | HP icon + val ---
    stat_row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(8))
    stat_row.add_widget(_icon_label("icons/ic_str.png", data.get("str", 0), ACCENT_RED))
    stat_row.add_widget(_icon_label("icons/ic_agi.png", data.get("agi", 0), ACCENT_GREEN))
    stat_row.add_widget(_icon_label("icons/ic_hp.png", f"{data.get('current_hp', data['hp'])}/{data['hp']}", (1, 0.3, 0.3, 1)))
    card.add_widget(stat_row)

    # Make the entire card clickable to open detail popup
    def _on_card_touch(widget, touch, i=idx):
        if touch.grab_current is not None:
            return False
        if not widget.collide_point(*touch.pos):
            return False
        if hasattr(touch, 'ox') and hasattr(touch, 'oy'):
            dx = abs(touch.x - touch.ox)
            dy = abs(touch.y - touch.oy)
            if dx > dp(8) or dy > dp(8):
                return False
        roster_screen.show_fighter_detail(i)
        return True
    card.bind(on_touch_up=_on_card_touch)

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
        height=dp(100),
        padding=[dp(12), dp(8)],
        spacing=dp(10),
    )
    card.border_color = rcolor

    info = BoxLayout(orientation="vertical", size_hint_x=0.6, spacing=2)

    info.add_widget(_auto_text_size(Label(
        text=item["name"], font_size="18sp", bold=True, color=rcolor,
        halign="left", size_hint_y=0.35,
    )))

    slot_text = item["slot"].upper()
    info.add_widget(_auto_text_size(Label(
        text=f"{slot_text}  [{rarity.upper()}]", font_size="19sp",
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
        text="  ".join(stats_parts), font_size="15sp",
        color=ACCENT_GREEN, halign="left", size_hint_y=0.4,
    )))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=f"{fmt_num(item['cost'])}g", font_size=18, size_hint_x=0.4,
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
        height=dp(160),
        padding=[dp(12), dp(8)],
        spacing=dp(4),
    )

    # Header
    header = BoxLayout(size_hint_y=0.35, spacing=5)
    header.add_widget(_auto_text_size(Label(
        text=exp["name"], font_size="19sp", bold=True,
        color=ACCENT_PURPLE, halign="left",
    )))
    header.add_widget(_auto_text_size(Label(
        text=exp["duration_text"], font_size="16sp",
        color=TEXT_SECONDARY, halign="right", size_hint_x=0.3,
    )))
    card.add_widget(header)

    card.add_widget(_auto_text_size(Label(
        text=exp["desc"], font_size="15sp", color=TEXT_MUTED,
        halign="left", size_hint_y=0.2,
    )))

    # Stats row
    stats = BoxLayout(size_hint_y=0.2, spacing=3)
    stats.add_widget(_auto_text_size(Label(
        text=f"Lv.{exp['min_level']}+", font_size="15sp",
        color=ACCENT_CYAN, halign="left",
    )))
    stats.add_widget(_auto_text_size(Label(
        text=t("danger_label", v=f"{exp['danger']:.0%}"), font_size="15sp",
        color=ACCENT_RED, halign="center",
    )))
    stats.add_widget(_auto_text_size(Label(
        text=t("relic_chance", v=f"{exp['relic_chance']:.0%}"), font_size="15sp",
        color=ACCENT_GOLD, halign="right",
    )))
    card.add_widget(stats)

    # Send buttons — one per available fighter
    send_row = BoxLayout(size_hint_y=0.25, spacing=5)
    eligible = [f for f in fighters if f["level"] >= exp["min_level"]]
    if eligible:
        for f_data in eligible[:3]:  # max 3 buttons
            btn = MinimalButton(
                text=t("send_name", name=f_data['name']), font_size=15,
                btn_color=ACCENT_PURPLE,
            )
            btn.bind(on_press=lambda inst, fi=f_data["index"], eid=exp["id"]:
                     expedition_screen.send(fi, eid))
            send_row.add_widget(btn)
    else:
        send_row.add_widget(_auto_text_size(Label(
            text=t("no_eligible"), font_size="15sp", color=TEXT_MUTED,
        )))
    card.add_widget(send_row)
    return card


def build_expedition_status_card(status):
    card = CardWidget(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(60),
        padding=[dp(12), dp(6)],
        spacing=dp(10),
    )
    card.border_color = ACCENT_CYAN

    card.add_widget(_auto_text_size(Label(
        text=f"{status['fighter_name']} @ {status['expedition_name']}",
        font_size="17sp", bold=True, color=ACCENT_CYAN, halign="left",
    )))

    card.add_widget(_auto_text_size(Label(
        text=status["remaining_text"], font_size="19sp", bold=True,
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
        height=dp(95),
        padding=[dp(12), dp(8)],
        spacing=dp(10),
    )

    info = BoxLayout(orientation="vertical", size_hint_x=0.65, spacing=2)
    info.add_widget(_auto_text_size(Label(
        text=item["name"], font_size="19sp", bold=True,
        color=TEXT_PRIMARY, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(Label(
        text=item["desc"], font_size="15sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=f"{fmt_num(item['cost'])}g", font_size=14, size_hint_x=0.35,
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
#  BATTLE FIGHTERS PANEL (ArenaScreen — individual HP bars)
# ============================================================

def build_total_hp_row(summary_text, total_hp, total_max, is_expanded, toggle_callback):
    """Total HP summary bar — tap the bar itself to expand/collapse."""
    from kivy.uix.behaviors import ButtonBehavior

    BAR_H = dp(72)
    centered = f"{summary_text}({max(0, total_hp)}/{total_max})"

    container = RelativeLayout(size_hint_y=None, height=BAR_H)
    hp_pct = max(0, total_hp) / max(1, total_max)
    is_low = hp_pct < 0.35

    bar = MinimalBar(
        pos_hint={"x": 0, "y": 0}, size_hint=(1, 1),
        value=hp_pct,
        bar_color=HP_PLAYER if not is_low else ACCENT_RED,
        bg_color=HP_PLAYER_BG,
    )
    container.add_widget(bar)

    lbl = Label(
        text=centered, font_size="22sp", bold=True,
        color=TEXT_PRIMARY, halign="center", valign="middle",
        pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(1, 1),
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    container.add_widget(lbl)

    # Tap the bar to toggle detail
    def _on_touch(widget, touch):
        if touch.grab_current is not None:
            return False
        if not widget.collide_point(*touch.pos):
            return False
        if hasattr(touch, 'ox') and hasattr(touch, 'oy'):
            dx = abs(touch.x - touch.ox)
            dy = abs(touch.y - touch.oy)
            if dx > dp(8) or dy > dp(8):
                return False
        toggle_callback(widget)
        return True
    container.bind(on_touch_up=_on_touch)

    return container


def _build_hp_bar_widget(name, hp, max_hp, bar_color, bg_color, height=dp(60),
                         on_tap=None):
    """HP bar with name and HP centered inside. Optionally tappable."""
    hp_pct = max(0, hp) / max(1, max_hp)
    is_low = hp_pct < 0.35

    container = RelativeLayout(size_hint_y=None, height=height)

    bar = MinimalBar(
        pos_hint={"x": 0, "y": 0}, size_hint=(1, 1),
        value=hp_pct,
        bar_color=bar_color if not is_low else ACCENT_RED,
        bg_color=bg_color,
    )
    container.add_widget(bar)
    container._bar = bar  # keep ref for flash animation

    centered = f"{name}  ({max(0, hp)}/{max_hp})"
    lbl = Label(
        text=centered, font_size="18sp", bold=True,
        color=TEXT_PRIMARY, halign="center", valign="middle",
        pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(1, 1),
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    container.add_widget(lbl)

    if on_tap:
        def _on_touch(widget, touch):
            if touch.grab_current is not None:
                return False
            if not widget.collide_point(*touch.pos):
                return False
            if hasattr(touch, 'ox') and hasattr(touch, 'oy'):
                dx = abs(touch.x - touch.ox)
                dy = abs(touch.y - touch.oy)
                if dx > dp(8) or dy > dp(8):
                    return False
            on_tap(widget)
            return True
        container.bind(on_touch_up=_on_touch)

    return container


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


def build_fighter_hp_row(fighter, index, heal_cost, can_afford, heal_callback,
                         on_tap=None):
    """Individual fighter HP bar — tappable for heal."""
    BAR_H = dp(60)

    bar_widget = _build_hp_bar_widget(
        fighter.name, fighter.hp, fighter.max_hp,
        HP_PLAYER, HP_PLAYER_BG, height=BAR_H,
        on_tap=on_tap,
    )
    return bar_widget


def build_fighter_pit_card(fighter, on_tap=None):
    """Squad-style compact card for a fighter in the PIT screen.
    Shows name, LV, STR/AGI/HP icons. Tap to heal."""
    card = CardWidget(
        orientation="vertical",
        size_hint_y=None,
        height=dp(56),
        padding=[dp(8), dp(3)],
        spacing=dp(1),
    )

    # Row 1: Name + Level
    top_row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(4))
    name_color = TEXT_PRIMARY if fighter.alive and fighter.hp > 0 else ACCENT_RED
    top_row.add_widget(_auto_text_size(Label(
        text=fighter.name, font_size="16sp", bold=True, color=name_color,
        halign="left", size_hint_x=0.6,
    )))
    top_row.add_widget(_auto_text_size(Label(
        text=f"LV {fighter.level}", font_size="15sp", bold=True,
        color=ACCENT_GOLD, halign="right", size_hint_x=0.4,
    )))
    card.add_widget(top_row)

    # Row 2: STR icon + val | AGI icon + val | HP icon + val
    stat_row = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(6))
    stat_row.add_widget(_icon_label(
        "icons/ic_str.png", fighter.strength, ACCENT_RED, font_size="14sp", height=dp(24)))
    stat_row.add_widget(_icon_label(
        "icons/ic_agi.png", fighter.agility, ACCENT_GREEN, font_size="14sp", height=dp(24)))
    hp_color = ACCENT_RED if fighter.hp < fighter.max_hp * 0.35 else (1, 0.3, 0.3, 1)
    stat_row.add_widget(_icon_label(
        "icons/ic_hp.png", f"{max(0,fighter.hp)}/{fighter.max_hp}", hp_color,
        font_size="14sp", height=dp(24)))
    card.add_widget(stat_row)

    # Make tappable
    if on_tap:
        def _on_touch(widget, touch):
            if touch.grab_current is not None:
                return False
            if not widget.collide_point(*touch.pos):
                return False
            if hasattr(touch, 'ox') and hasattr(touch, 'oy'):
                dx = abs(touch.x - touch.ox)
                dy = abs(touch.y - touch.oy)
                if dx > dp(8) or dy > dp(8):
                    return False
            on_tap(widget)
            return True
        card.bind(on_touch_up=_on_touch)

    # Store a _bar ref for flash_hp_bar compatibility
    card._bar = None

    return card


def build_enemy_hp_row(enemy, show_stats=False, on_tap=None):
    BAR_H = dp(56)

    row = BoxLayout(
        orientation="vertical",
        size_hint_y=None, height=BAR_H,
        spacing=0, padding=[0, 0],
    )

    bar_widget = _build_hp_bar_widget(
        enemy.name, enemy.hp, enemy.max_hp,
        HP_ENEMY, HP_ENEMY_BG, height=BAR_H,
        on_tap=on_tap,
    )
    row.add_widget(bar_widget)

    return row


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
        height=dp(75),
        padding=[dp(10), dp(6)],
        spacing=dp(8),
    )
    if unlocked:
        card.border_color = ACCENT_GOLD
        card.card_color = (0.12, 0.12, 0.08, 1)

    info = BoxLayout(orientation="vertical", size_hint_x=0.7, spacing=1)
    name_color = ACCENT_GOLD if unlocked else TEXT_SECONDARY
    info.add_widget(_auto_text_size(Label(
        text=ach["name"], font_size="18sp", bold=True,
        color=name_color, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(Label(
        text=ach["desc"], font_size="19sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    reward = BoxLayout(orientation="vertical", size_hint_x=0.3)
    if unlocked:
        reward.add_widget(_auto_text_size(Label(
            text=t("done_label"), font_size="17sp", bold=True,
            color=ACCENT_GREEN, halign="center",
        )))
    else:
        reward.add_widget(_diamond_label(ach["diamonds"]))

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
        height=dp(80),
        padding=[dp(10), dp(6)],
        spacing=dp(8),
    )
    card.border_color = ACCENT_CYAN

    info = BoxLayout(orientation="vertical", size_hint_x=0.6, spacing=1)
    info.add_widget(_auto_text_size(Label(
        text=item["name"], font_size="18sp", bold=True,
        color=ACCENT_CYAN, halign="left", size_hint_y=0.45,
    )))
    info.add_widget(_auto_text_size(Label(
        text=item["desc"], font_size="19sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.55,
    )))

    affordable = item.get("affordable", False)
    buy_col = BoxLayout(orientation="horizontal", size_hint_x=0.4, spacing=dp(4))
    buy_btn = MinimalButton(
        text=str(item["cost"]), font_size=12, size_hint_x=1,
        btn_color=ACCENT_CYAN if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: lore_screen.buy_diamond_item(iid))
    buy_col.add_widget(buy_btn)
    buy_col.add_widget(Image(
        source="icons/ic_diamond.png", fit_mode="contain",
        size_hint=(None, 1), width=dp(24),
    ))

    card.add_widget(info)
    card.add_widget(buy_col)
    return card


def refresh_diamond_shop_grid(lore_screen):
    grid = lore_screen.ids.get("diamond_shop_grid")
    if not grid:
        return
    grid.clear_widgets()
    for item in lore_screen.diamond_shop_data:
        grid.add_widget(build_diamond_shop_card(item, lore_screen))
