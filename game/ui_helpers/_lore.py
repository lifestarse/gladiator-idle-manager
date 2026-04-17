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

class BattleLogCardView(RecycleDataViewBehavior, BoxLayout):
    """Battle log entry — 78dp vertical BaseCard with 2 text rows.

    Uses plain Kivy Label, NOT AutoShrinkLabel. AutoShrinkLabel's
    on_text cascade (reset font_size → recompute texture → _check_fit
    → maybe shrink → texture redraw) is catastrophic for huge strings
    like "fighter1, fighter2, ..., fighter1000" (~10k chars) — Kivy
    has to render the whole thing once before shrinking. For 20
    visible rows × 2 such labels = 40 giant text renders per layout
    pass. Plain Label with `shorten=True` clips at card width instead.
    Name-list preview is also capped to 5 names + "+N" in the data
    layer (_show_battle_log's _preview helper).
    """

    def __init__(self, **kwargs):
        from game.widgets import BaseCard
        from kivy.uix.label import Label as _Label
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(78))
        super().__init__(**kwargs)
        self._log_idx = -1
        self._lore_screen = None

        self._card = BaseCard(
            orientation="vertical", size_hint_y=1,
            padding=[dp(8), dp(4)], spacing=dp(2),
        )

        def _mk_label(size_hint_x, font_size, bold=False, color=TEXT_SECONDARY,
                      halign="left"):
            lbl = _Label(font_size=font_size, bold=bold,
                         color=list(color), halign=halign, valign="middle",
                         font_name='PixelFont',
                         size_hint_x=size_hint_x, shorten=True,
                         shorten_from='right')
            lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            return lbl

        # Row 1: [result] [tier] [gold] [time]
        row1 = BoxLayout(size_hint_y=0.5, spacing=dp(2))
        self._result_lbl = _mk_label(0.35, sp(7), bold=True)
        self._tier_lbl   = _mk_label(0.12, sp(7), bold=True, color=ACCENT_GOLD)
        self._gold_lbl   = _mk_label(0.23, sp(7), bold=True, color=ACCENT_GOLD)
        self._time_lbl   = _mk_label(0.30, sp(6),            color=TEXT_MUTED,
                                      halign="right")
        for lbl in (self._result_lbl, self._tier_lbl,
                    self._gold_lbl, self._time_lbl):
            row1.add_widget(lbl)
        self._card.add_widget(row1)

        # Row 2: fighters vs enemies (names are pre-capped upstream)
        row2 = BoxLayout(size_hint_y=0.5, spacing=dp(2))
        self._fighters_lbl = _mk_label(0.45, sp(6))
        self._vs_lbl       = _mk_label(0.10, sp(6), color=TEXT_MUTED,
                                        halign="center")
        self._vs_lbl.text = "vs"
        self._enemies_lbl  = _mk_label(0.45, sp(6))
        row2.add_widget(self._fighters_lbl)
        row2.add_widget(self._vs_lbl)
        row2.add_widget(self._enemies_lbl)
        self._card.add_widget(row2)
        self.add_widget(self._card)

        _bind_long_tap(self._card, lambda w: self._on_tap())

    def refresh_view_attrs(self, rv, index, data):
        self._log_idx = data.get('log_idx', -1)
        self._lore_screen = data.get('_lore')
        color = list(data.get('result_color', TEXT_PRIMARY))
        self._card.border_color = color

        self._result_lbl.text = data.get('result_text', '')
        self._result_lbl.color = color
        self._tier_lbl.text = data.get('tier_text', '')
        self._gold_lbl.text = data.get('gold_text', '')
        self._time_lbl.text = data.get('time_text', '')
        self._fighters_lbl.text = data.get('fighters_text', '')
        self._enemies_lbl.text = data.get('enemies_text', '')

    def _on_tap(self):
        if self._lore_screen and self._log_idx >= 0:
            self._lore_screen._show_battle_detail(self._log_idx)


class EventLogCardView(RecycleDataViewBehavior, BoxLayout):
    """Event log entry — 48dp vertical BaseCard with 2 text rows.

    Plain Label with shorten=True (not AutoShrinkLabel) — same reason
    as BattleLogCardView: AutoShrinkLabel's text-fit cascade is
    expensive when strings are long.

    Tap opens a detail view for the event (routes to
    LoreScreen._show_event_detail).
    """

    def __init__(self, **kwargs):
        from game.widgets import BaseCard
        from kivy.uix.label import Label as _Label
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(48))
        super().__init__(**kwargs)
        self._log_idx = -1
        self._lore_screen = None

        self._card = BaseCard(
            orientation="vertical", size_hint_y=1,
            padding=[dp(8), dp(4)], spacing=dp(1),
        )

        def _mk(size_hint, font_size, bold=False, color=TEXT_SECONDARY,
                halign="left"):
            kw = dict(font_size=font_size, bold=bold, color=list(color),
                       halign=halign, valign="middle",
                       font_name='PixelFont', shorten=True,
                       shorten_from='right')
            if isinstance(size_hint, tuple):
                kw['size_hint'] = size_hint
            else:
                kw['size_hint_x'] = size_hint
            lbl = _Label(**kw)
            lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            return lbl

        # Row 1: label + time
        row1 = BoxLayout(size_hint_y=0.45, spacing=dp(2))
        self._label_lbl = _mk(0.70, sp(7), bold=True)
        self._time_lbl  = _mk(0.30, sp(6), color=TEXT_MUTED, halign="right")
        row1.add_widget(self._label_lbl)
        row1.add_widget(self._time_lbl)
        self._card.add_widget(row1)

        # Row 2: detail
        self._detail_lbl = _mk(None, sp(6))
        self._detail_lbl.size_hint_y = 0.55
        self._card.add_widget(self._detail_lbl)
        self.add_widget(self._card)

        _bind_long_tap(self._card, lambda w: self._on_tap())

    def refresh_view_attrs(self, rv, index, data):
        self._log_idx = data.get('log_idx', -1)
        self._lore_screen = data.get('_lore')
        color = list(data.get('color', TEXT_PRIMARY))
        self._card.border_color = color
        self._label_lbl.text = data.get('label', '')
        self._label_lbl.color = color
        self._time_lbl.text = data.get('time_text', '')
        self._detail_lbl.text = data.get('detail', '')

    def _on_tap(self):
        if self._lore_screen and self._log_idx >= 0:
            self._lore_screen._show_event_detail(self._log_idx)


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
