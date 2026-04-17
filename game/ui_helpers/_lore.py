# Build: 2
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
from ._common import _batch_fill_grid, _bind_long_tap, _auto_text_size, _diamond_label


# ============================================================
#  BATTLE LOG (ArenaScreen)
# ============================================================



# ============================================================
#  ACHIEVEMENTS (LoreScreen)
# ============================================================

# ------------------------------------------------------------------
#  Achievement RecycleView viewclass — name + desc + reward indicator.
#  Horizontal layout, 75dp. Widgets pre-created; refresh_view_attrs
#  swaps the reward slot (DONE label vs diamond icon) based on unlocked.
# ------------------------------------------------------------------

class AchievementCardView(RecycleDataViewBehavior, BoxLayout):
    """RecycleView viewclass for achievements list."""

    def __init__(self, **kwargs):
        from game.widgets import BaseCard
        from kivy.uix.anchorlayout import AnchorLayout
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(75))
        super().__init__(**kwargs)

        self._card = BaseCard(
            orientation="horizontal", size_hint_y=1,
            padding=[dp(10), dp(6)], spacing=dp(8),
        )

        # Info column: name + desc
        self._info = BoxLayout(orientation="vertical",
                               size_hint_x=0.7, spacing=dp(4))
        self._name_lbl = _auto_text_size(AutoShrinkLabel(
            font_size="11sp", bold=True,
            halign="left", size_hint_y=0.5,
        ))
        self._desc_lbl = _auto_text_size(AutoShrinkLabel(
            font_size="10sp", color=list(TEXT_MUTED),
            halign="left", size_hint_y=0.5,
        ))
        self._info.add_widget(self._name_lbl)
        self._info.add_widget(self._desc_lbl)
        self._card.add_widget(self._info)

        # Reward column: DONE label OR diamond count — pre-create both, swap.
        self._reward_slot = AnchorLayout(
            size_hint_x=0.3, anchor_x="center", anchor_y="center",
        )
        self._done_lbl = AutoShrinkLabel(
            text=t("done_label"), font_size="12sp", bold=True,
            color=list(ACCENT_GREEN), halign="center", valign="middle",
            size_hint=(1, 1),
        )
        # Diamond reward (constructed on demand; re-created for each card
        # since _diamond_label may include inline Image widgets).
        self._diamond_widget = None
        self._card.add_widget(self._reward_slot)
        self.add_widget(self._card)

    def refresh_view_attrs(self, rv, index, data):
        unlocked = data.get('unlocked', False)
        if unlocked:
            self._card.border_color = list(ACCENT_GOLD)
            self._card.card_color = (0.12, 0.12, 0.08, 1)
            name_color = list(ACCENT_GOLD)
        else:
            self._card.border_color = list(DIVIDER)
            self._card.card_color = list(BG_CARD)
            name_color = list(TEXT_SECONDARY)

        self._name_lbl.text = data.get('name', '')
        self._name_lbl.color = name_color
        self._desc_lbl.text = data.get('desc', '')

        # Swap reward slot content
        self._reward_slot.clear_widgets()
        if unlocked:
            if self._done_lbl.parent:
                self._done_lbl.parent.remove_widget(self._done_lbl)
            self._reward_slot.add_widget(self._done_lbl)
        else:
            # Re-create diamond label (it contains an Image child that
            # can't be reparented cleanly between refreshes)
            self._diamond_widget = _diamond_label(data.get('diamonds', 0))
            self._reward_slot.add_widget(self._diamond_widget)


def _achievement_to_rv_data(ach):
    """Convert achievement dict to AchievementCardView data dict."""
    return {
        'name': ach.get('name', ''),
        'desc': ach.get('desc', ''),
        'diamonds': ach.get('diamonds', 0),
        'unlocked': ach.get('unlocked', False),
    }


# ------------------------------------------------------------------
#  Battle log + Event log — RecycleView viewclasses. Up to 200 entries
#  each, previously rendered as 200 widgets causing lag on entry.
# ------------------------------------------------------------------





def build_achievement_card(ach):
    from game.widgets import BaseCard
    from kivy.uix.anchorlayout import AnchorLayout

    unlocked = ach.get("unlocked", False)
    card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(75),
                    padding=[dp(10), dp(6)], spacing=dp(8))
    if unlocked:
        card.border_color = ACCENT_GOLD
        card.card_color = (0.12, 0.12, 0.08, 1)

    info = BoxLayout(orientation="vertical", size_hint_x=0.7, spacing=dp(4))
    name_color = ACCENT_GOLD if unlocked else TEXT_SECONDARY
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=ach["name"], font_size="11sp", bold=True,
        color=name_color, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=ach["desc"], font_size="10sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    reward = AnchorLayout(size_hint_x=0.3, anchor_x="center", anchor_y="center")
    if unlocked:
        reward.add_widget(AutoShrinkLabel(
            text=t("done_label"), font_size="12sp", bold=True,
            color=ACCENT_GREEN, halign="center", valign="middle",
            size_hint=(1, 1),
        ))
    else:
        reward.add_widget(_diamond_label(ach["diamonds"]))

    card.add_widget(info)
    card.add_widget(reward)
    return card


def refresh_achievement_grid(lore_screen):
    """Populate achievements list. Prefers RecycleView (achievements_rv);
    falls back to legacy GridLayout (lore_grid) otherwise."""
    data = lore_screen.achievements_data

    # Prefer RecycleView — virtualizes to ~10 visible widgets
    rv = lore_screen.ids.get("achievements_rv")
    if rv is not None:
        rv.data = [_achievement_to_rv_data(a) for a in data]
        return

    # Legacy path
    grid = lore_screen.ids.get("lore_grid")
    if not grid:
        return
    unlock_hash = tuple(ach.get("unlocked", False) for ach in data)
    if (lore_screen._achievement_widgets
            and len(lore_screen._achievement_widgets) == len(data)
            and lore_screen._achievement_unlock_hash == unlock_hash):
        _batch_fill_grid(grid, lore_screen._achievement_widgets)
        return
    cards = [build_achievement_card(ach) for ach in data]
    lore_screen._achievement_widgets = cards
    lore_screen._achievement_unlock_hash = unlock_hash
    _batch_fill_grid(grid, cards)
