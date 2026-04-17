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
from ._common import _CLASS_COLORS, _bind_long_tap, _icon_label


# ============================================================
#  ROSTER CARD VIEW (RecycleView viewclass)
# ============================================================

_roster_callbacks = {}
"""Callbacks registered by RosterScreen.on_enter.
Keys: 'show_detail', 'dismiss' → callable(fighter_index: int)
"""


class RosterCardView(RecycleDataViewBehavior, CardWidget):
    """RecycleView viewclass for roster cards.

    A small pool of these is kept alive by RecycleView (only visible rows
    + a buffer).  refresh_view_attrs() updates visuals in-place so no
    widget construction happens during scrolling.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(84))
        kwargs.setdefault('padding', [dp(8), dp(10)])
        kwargs.setdefault('spacing', dp(6))
        super().__init__(**kwargs)
        self._fighter_index = 0
        self._dismiss_cb = None

        ROW_H = dp(56)

        # Avatar
        self._avatar = GladiatorAvatar(
            fighter_class="mercenary",
            accent_color=list(ACCENT_GREEN),
            tier=1,
            size_hint=(None, None),
            width=dp(48), height=dp(52),
        )

        # Name
        self._name_lbl = AutoShrinkLabel(
            font_size="12sp", bold=True, color=list(TEXT_PRIMARY),
            halign="left", size_hint_x=None, width=dp(130),
            size_hint_y=None, height=ROW_H,
        )
        self._name_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))

        # Level
        self._level_lbl = AutoShrinkLabel(
            font_size="11sp", bold=True, color=list(ACCENT_GOLD),
            halign="left", size_hint_x=None, width=dp(56),
            size_hint_y=None, height=ROW_H,
        )
        self._level_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))

        # Third slot (dismiss btn / away label / empty)
        self._dismiss_btn = MinimalButton(
            text="X", btn_color=list(ACCENT_RED), font_size=sp(11),
            size_hint_x=None, width=dp(36),
        )
        self._away_lbl = AutoShrinkLabel(
            font_size="11sp", color=list(ACCENT_CYAN), halign="center",
            size_hint_x=None, width=dp(44), size_hint_y=None, height=ROW_H,
        )
        self._away_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self._empty_lbl = Label(size_hint_x=None, width=0)
        self._slot = 'empty'

        # Spacer pushes stats to the right
        self._spacer = Label(size_hint_x=1)

        # Stats: HP only — compact, fixed width
        ICON_W = dp(90)
        self._stat_box = BoxLayout(
            orientation="horizontal", spacing=dp(2),
            size_hint_x=None, width=ICON_W + dp(4),
            size_hint_y=None, height=ROW_H,
        )
        self._hp_row = _icon_label("sprites/icons/ic_hp.png", 0, (1, 0.3, 0.3, 1), font_size="11sp", height=ROW_H)
        self._stat_box.add_widget(self._hp_row)

        # Plus indicator — available stat/perk points
        self._plus_icon = Image(
            source="icons/ic_plus.png", fit_mode="contain",
            size_hint=(None, None), width=dp(18), height=dp(18),
            opacity=0,
        )

        self.add_widget(self._avatar)
        self.add_widget(self._name_lbl)
        self.add_widget(self._level_lbl)
        self.add_widget(self._plus_icon)
        self.add_widget(self._empty_lbl)
        self.add_widget(self._spacer)
        self.add_widget(self._stat_box)

        # Long-tap opens fighter detail popup
        _bind_long_tap(self, lambda w: self._on_tap())

    def _on_tap(self):
        cb = _roster_callbacks.get('show_detail')
        if cb:
            cb(self._fighter_index)

    def _set_slot(self, slot):
        """Swap the last element (dismiss/away/empty) in the card row."""
        if self._slot == slot:
            return
        if self._slot == 'dismiss':
            self.remove_widget(self._dismiss_btn)
        elif self._slot == 'away':
            self.remove_widget(self._away_lbl)
        else:
            self.remove_widget(self._empty_lbl)
        if slot == 'dismiss':
            self.add_widget(self._dismiss_btn)
        elif slot == 'away':
            self.add_widget(self._away_lbl)
        else:
            self.add_widget(self._empty_lbl)
        self._slot = slot

    def refresh_view_attrs(self, rv, index, data):
        """Called by RecycleView when this instance is (re)assigned to a row."""
        self._fighter_index = data['index']

        # Avatar sprite by class
        fc = data.get('fighter_class', 'mercenary')
        self._avatar.fighter_class = fc
        self._avatar.accent_color = list(_CLASS_COLORS.get(fc, ACCENT_GREEN))
        self._avatar.tier = data.get('level', 1)
        self._avatar.is_wounded = bool(data.get('injuries', 0))

        # Card background — directly update canvas Color objects
        if not data['alive']:
            self._bg_color.rgba = (0.15, 0.08, 0.08, 1)
            self._br_color.rgba = list(ACCENT_RED)
        else:
            self._bg_color.rgba = list(BG_CARD)
            self._br_color.rgba = list(DIVIDER)

        # Name label
        if not data['alive']:
            self._name_lbl.text = f"{data['name']} [{t('dead_tag')}]"
            self._name_lbl.color = list(ACCENT_RED)
        elif data['on_expedition']:
            self._name_lbl.text = data['name']
            self._name_lbl.color = list(ACCENT_CYAN)
        else:
            self._name_lbl.text = data['name']
            self._name_lbl.color = list(TEXT_PRIMARY)

        # Level label
        self._level_lbl.text = f"LV {data['level']}"

        # Third slot
        if not data['alive']:
            self._set_slot('dismiss')
            if self._dismiss_cb is not None:
                self._dismiss_btn.unbind(on_press=self._dismiss_cb)
            idx = data['index']
            self._dismiss_cb = lambda inst, i=idx: (
                _roster_callbacks.get('dismiss') and _roster_callbacks['dismiss'](i)
            )
            self._dismiss_btn.bind(on_press=self._dismiss_cb)
        elif data['on_expedition']:
            self._set_slot('away')
            self._away_lbl.text = t('away_tag')
        else:
            self._set_slot('empty')

        # Plus icon — available upgrades
        has_upgrades = data['alive'] and (
            data.get('unused_points', 0) > 0 or data.get('perk_points', 0) > 0
        )
        self._plus_icon.opacity = 1 if has_upgrades else 0

        # Stat label
        self._hp_row.children[0].text = fmt_num(data['hp'])
        # Do NOT call super().refresh_view_attrs — it would auto-setattr all data
        # keys onto this widget, overwriting CardWidget.active etc.
        # refresh_view_layout is still inherited from RecycleDataViewBehavior.
