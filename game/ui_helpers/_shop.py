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
from ._common import _batch_fill_grid, _auto_text_size


# ============================================================
#  MARKET (Shop) — now inside MoreScreen
# ============================================================

def build_shop_card(item, shop_screen):
    from game.widgets import BaseCard

    card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(70),
                    padding=[dp(12), dp(8)], spacing=dp(10))

    info = BoxLayout(orientation="vertical", size_hint_x=0.65, spacing=dp(4))
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=item["name"], font_size="10sp", bold=True,
        color=TEXT_PRIMARY, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=item["desc"], font_size="11sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=f"{fmt_num(item['cost'])}", font_size=sp(11), size_hint_x=0.35,
        btn_color=ACCENT_BLUE if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gold.png",
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: shop_screen.buy(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_shop_grid(shop_screen):
    grid = shop_screen.ids.get("shop_grid")
    if not grid:
        return
    cards = [build_shop_card(item, shop_screen) for item in shop_screen.items_data]
    _batch_fill_grid(grid, cards)
