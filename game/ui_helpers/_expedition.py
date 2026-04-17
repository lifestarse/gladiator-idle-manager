# Build: 1
"""Auto-generated submodule of game.ui_helpers package."""
from contextlib import contextmanager
import time

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from game.widgets import CardWidget, MinimalButton, MinimalBar, AutoShrinkLabel, GladiatorAvatar
from game.theme import *
from game.models import RARITY_COLORS, fmt_num
from game.slots import SLOTS
from game.localization import t
from game.constants import LOW_HP_THRESHOLD
from ._common import _batch_fill_grid


# ============================================================
#  EXPEDITIONS
# ============================================================

def build_expedition_card(exp, fighters, expedition_screen):
    from game.widgets import BaseCard
    from game.models import SHARD_TIERS

    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(190),
                    padding=[dp(12), dp(8)], spacing=dp(6))

    card.add_text_row(
        (exp["name"], sp(11), True, ACCENT_PURPLE, 0.7),
        (exp["duration_text"], sp(10), False, TEXT_SECONDARY, 0.3),
        size_hint_y=0.3,
    )
    card.add_label(exp["desc"], font_size=sp(11), color=TEXT_MUTED, halign="left", size_hint_y=0.2)
    card.add_text_row(
        (f"Lv.{exp['min_level']}+", sp(11), False, ACCENT_CYAN, 0.33),
        (t("danger_label", v=f"{exp['danger']:.0%}"), sp(11), False, ACCENT_RED, 0.34),
        (t("relic_chance", v=f"{exp['relic_chance']:.0%}"), sp(11), False, ACCENT_GOLD, 0.33),
        size_hint_y=0.2,
    )

    shard_info = SHARD_TIERS.get(exp["id"])
    relic_pct = int(exp.get("relic_chance", 0) * 100)
    reward_parts = []
    if shard_info:
        tier = shard_info["tier"]
        _key = f"shard_tier_{tier}_name"
        _translated = t(_key)
        reward_parts.append(_translated if _translated != _key else shard_info["name"])
    reward_parts.append(f"{t('relic_slot')} ({relic_pct}%)")
    card.add_label(" + ".join(reward_parts), font_size=sp(10), color=ACCENT_GOLD, size_hint_y=0.12)

    eligible = [f for f in fighters if f["level"] >= exp["min_level"]]
    if eligible:
        send_btn = MinimalButton(text=t("send_btn"), font_size=sp(11), btn_color=ACCENT_PURPLE)
        def _open_send_popup(inst, elig=eligible, eid=exp["id"], scr=expedition_screen):
            _show_send_fighter_popup(elig, eid, scr)
        send_btn.bind(on_press=_open_send_popup)
        card.add_button_row([send_btn], height=dp(190 * 0.25))
    else:
        card.add_label(t("no_eligible"), font_size=sp(11), color=TEXT_MUTED, size_hint_y=0.25)
    return card


def build_expedition_status_card(status):
    from game.widgets import BaseCard

    card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(44),
                    padding=[dp(10), dp(4)], spacing=dp(6))
    card.border_color = ACCENT_CYAN
    card.add_text_row(
        (status["fighter_name"], sp(8), True, ACCENT_CYAN, 0.30),
        (status["expedition_name"], sp(7), False, TEXT_SECONDARY, 0.45),
        (status["remaining_text"], sp(8), True, ACCENT_GOLD, 0.25),
    )
    return card


def _show_send_fighter_popup(eligible, expedition_id, expedition_screen):
    """Popup to select which fighter to send on expedition."""
    from kivy.uix.scrollview import ScrollView

    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    content = BoxLayout(orientation="vertical", spacing=dp(8),
                        padding=dp(12), size_hint_y=None)
    content.bind(minimum_height=content.setter("height"))

    popup = Popup(
        title=t("send_btn"),
        title_color=list(ACCENT_PURPLE)[:3] + [1],
        title_size=sp(11),
        content=scroll,
        size_hint=(0.85, None),
        height=dp(80 + len(eligible) * 54),
        background_color=list(BG_CARD)[:3] + [1],
        separator_color=list(ACCENT_PURPLE)[:3] + [1],
        auto_dismiss=True,
    )

    for f_data in eligible:
        btn = MinimalButton(
            text=f"{f_data['name']}  LV{f_data['level']}",
            font_size=sp(11),
            btn_color=ACCENT_PURPLE,
            size_hint_y=None, height=dp(44),
        )
        def _send(inst, fi=f_data["index"], eid=expedition_id):
            popup.dismiss()
            expedition_screen.send(fi, eid)
        btn.bind(on_press=_send)
        content.add_widget(btn)

    scroll.add_widget(content)
    popup.open()


def refresh_expedition_grid(expedition_screen):
    grid = expedition_screen.ids.get("expedition_grid")
    if not grid:
        return

    tab = getattr(expedition_screen, "expedition_tab", "missions")
    if tab == "missions":
        # Build cache key from status data (remaining times change every tick)
        status_key = tuple((s["fighter_name"], s["remaining_text"]) for s in expedition_screen.status_data)
        if status_key == getattr(grid, '_exp_status_key', None) and grid.children:
            return
        grid._exp_status_key = status_key
        cards = [build_expedition_status_card(s)
                 for s in expedition_screen.status_data]
    else:
        # Available expeditions — only rebuild if data changed
        exp_key = tuple(e["id"] for e in expedition_screen.expeditions_data)
        fighters_key = tuple((f["index"], f["level"]) for f in expedition_screen.fighters_for_send)
        full_key = (exp_key, fighters_key)
        if full_key == getattr(grid, '_exp_hunts_key', None) and grid.children:
            return
        grid._exp_hunts_key = full_key
        cards = [
            build_expedition_card(exp, expedition_screen.fighters_for_send, expedition_screen)
            for exp in expedition_screen.expeditions_data
        ]
    _batch_fill_grid(grid, cards)
