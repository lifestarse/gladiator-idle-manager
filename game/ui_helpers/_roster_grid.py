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
from ._common import _bind_long_tap, _auto_text_size


# ============================================================
#  ROSTER
# ============================================================


def build_roster_card(data, roster_screen):
    """Minimal card: name, level, STR/AGI/HP icons. Tap to open detail popup."""
    from game.widgets import BaseCard

    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(72),
                    padding=[dp(10), dp(6)], spacing=dp(4))

    if not data["alive"]:
        card.card_color = (0.15, 0.08, 0.08, 1)
        card.border_color = ACCENT_RED

    idx = data["index"]

    if not data["alive"]:
        name_text = f"{data['name']} [{t('dead_tag')}]"
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
            text="X", btn_color=ACCENT_RED, font_size=sp(11), size_hint_x=0.25,
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

    _bind_long_tap(card, lambda w, i=idx: roster_screen.show_fighter_detail(i))
    return card


def refresh_roster_grid(roster_screen):
    rv = roster_screen.ids.get('roster_rv')
    if not rv:
        return
    rv.data = [dict(d) for d in roster_screen.gladiators_data]
