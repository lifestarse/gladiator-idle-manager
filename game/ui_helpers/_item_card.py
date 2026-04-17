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
from ._common import _auto_text_size


# ============================================================
#  UNIFIED ITEM CARD
# ============================================================


def build_item_info_card(item, subtitle=None, subtitle_color=None, fighter=None, equipped_on=None, on_tap=None):
    """Unified item info card — 3 rows: name, subtitle, total stats."""
    import game.models as _m
    from game.models import item_display_name, calc_item_stats
    from game.widgets import BaseCard

    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)
    slot = item.get("slot", "?")

    display_name = item_display_name(item) if slot in SLOTS else item.get("name", "?")
    upgrade_lvl = item.get("upgrade_level", 0)
    level_display = f"+{upgrade_lvl}" if upgrade_lvl > 0 else ""
    ench = item.get("enchantment", "")
    ench_display = ""
    if ench:
        ench_data = _m.ENCHANTMENT_TYPES.get(ench)
        ench_display = f"[{ench_data['name']}]" if ench_data else f"[{ench}]"
    if subtitle:
        slot_rarity = subtitle
    elif slot in SLOTS:
        slot_rarity = f"{t(SLOTS[slot].label_keys['upper'])} [{t('rarity_' + rarity + '_upper')}]"
    else:
        slot_rarity = f"{t('slot_' + slot + '_upper')} [{t('rarity_' + rarity + '_upper')}]"
    s, a, v = calc_item_stats(item, fighter)

    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(75),
                    padding=[dp(12), dp(8)], spacing=dp(4))
    card.border_color = rcolor

    # Row 1: name | +level | [enchantment]
    row1 = BoxLayout(size_hint_y=0.35, spacing=dp(4))
    name_lbl = AutoShrinkLabel(
        text=display_name, font_size=sp(12), bold=True, color=rcolor,
        halign="left", size_hint_x=None, width=1,
    )
    name_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row1.add_widget(name_lbl)
    level_lbl = AutoShrinkLabel(
        text=level_display, font_size=sp(10), bold=True, color=ACCENT_GOLD,
        halign="left", size_hint_x=None, width=dp(28),
    )
    level_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row1.add_widget(level_lbl)
    ench_lbl = AutoShrinkLabel(
        text=ench_display, font_size=sp(11), bold=True, color=ACCENT_PURPLE,
        halign="left", size_hint_x=None, width=1,
    )
    ench_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row1.add_widget(ench_lbl)
    card.add_widget(row1)

    # Row 2: slot/rarity | equipped fighter
    row2 = BoxLayout(size_hint_y=0.25, spacing=dp(4))
    sr_lbl = AutoShrinkLabel(
        text=slot_rarity, font_size=sp(11), color=subtitle_color or TEXT_MUTED,
        halign="left", size_hint_x=None, width=1,
    )
    sr_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row2.add_widget(sr_lbl)
    if equipped_on:
        eq_lbl = AutoShrinkLabel(
            text=equipped_on, font_size=sp(11), bold=True, color=ACCENT_CYAN,
            halign="left", size_hint_x=None, width=1,
        )
        eq_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row2.add_widget(eq_lbl)
    card.add_widget(row2)

    # Row 3: stat icons
    row3 = BoxLayout(size_hint_y=0.40, spacing=dp(8))
    ico_h = dp(16)
    stat_items = []
    if s > 0:
        stat_items.append(("sprites/icons/ic_str.png", fmt_num(s)))
    if a > 0:
        stat_items.append(("sprites/icons/ic_agi.png", fmt_num(a)))
    if v > 0:
        stat_items.append(("sprites/icons/ic_vit.png", fmt_num(v)))
    for icon_src, val_text in stat_items:
        lbl = AutoShrinkLabel(
            text=val_text, font_size=sp(10), bold=True, color=ACCENT_GREEN,
            halign="left", valign="middle",
            size_hint_x=None, width=1,
        )
        lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row3.add_widget(lbl)
        row3.add_widget(Image(source=icon_src, fit_mode="contain",
                              size_hint=(None, 1), width=ico_h))
    if not (s or a or v):
        row3.add_widget(_auto_text_size(AutoShrinkLabel(
            text="—", font_size=sp(10), color=TEXT_MUTED, halign="left",
        )))
    card.add_widget(row3)

    if on_tap:
        card.bind(on_press=on_tap)
    return card
