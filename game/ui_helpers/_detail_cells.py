# Build: 1
"""BattleDetailLineView, FighterEquipChoiceView — RV cells."""
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

class BattleDetailLineView(RecycleDataViewBehavior, Label):
    """One colorized log line inside a battle-detail view.

    Plain Kivy Label (NOT AutoShrinkLabel) — on-device profiling showed
    AutoShrinkLabel's on_text→font_size→_check_fit cascade re-ran for
    each row on every layout pass and each rv.data assignment. For the
    1500-line cap of a 1000-vs-1000 log that was seconds of main-thread
    work. Log lines are fixed-width, single-line, no shrink needed —
    plain Label is correct.

    Before (thousands of AutoShrinkLabels in GridLayout): seconds of lag.
    After (pooled RV + plain Label): just the colour/text reassignment
    on ~20 visible rows per layout pass.
    """

    # Pre-allocated colour lists — avoid building a new list every row.
    _COLOR_CRIT    = list(ACCENT_GOLD)
    _COLOR_DODGE   = list(ACCENT_CYAN)
    _COLOR_KILL    = list(ACCENT_RED)
    _COLOR_VICTORY = list(ACCENT_GREEN)
    _COLOR_STATUS  = list(ACCENT_PURPLE)
    _COLOR_DEFAULT = list(TEXT_SECONDARY)

    def __init__(self, **kwargs):
        kwargs.setdefault('font_size', '11sp')
        kwargs.setdefault('halign', 'left')
        kwargs.setdefault('valign', 'middle')
        kwargs.setdefault('font_name', 'PixelFont')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(18))
        # Clip overflow rather than wrap — keeps height stable at dp(18).
        kwargs.setdefault('shorten', True)
        super().__init__(**kwargs)
        # Bind text_size to self.size so halign actually works.
        self.bind(size=lambda w, s: setattr(w, 'text_size', s))

    def refresh_view_attrs(self, rv, index, data):
        line = data.get('text', '') or ''
        self.text = line
        # Explicit colour wins (used for the two header rows).
        explicit = data.get('color')
        if explicit is not None:
            self.color = list(explicit)
            self.height = data.get('height', dp(18))
            self.bold = bool(data.get('bold', False))
            self.font_size = data.get('font_size', '11sp')
            return
        # Keyword scan picks a pre-allocated colour list — no per-call
        # `list(CONST)` allocations.
        if "CRIT" in line:
            self.color = self._COLOR_CRIT
        elif "DODGE" in line:
            self.color = self._COLOR_DODGE
        elif "KILL" in line or "FALLEN" in line or "DEFEAT" in line:
            self.color = self._COLOR_KILL
        elif "VICTORY" in line:
            self.color = self._COLOR_VICTORY
        elif "POISON" in line or "BLEED" in line or "BURN" in line:
            self.color = self._COLOR_STATUS
        else:
            self.color = self._COLOR_DEFAULT
        # Height/font/bold are the same for the vast majority of rows —
        # only assign if they differ from current, to skip redundant
        # Kivy property dispatches.
        h = data.get('height', dp(18))
        if self.height != h:
            self.height = h
        fs = data.get('font_size', '11sp')
        if self.font_size != fs:
            self.font_size = fs
        if self.bold:
            self.bold = False


class FighterEquipChoiceView(RecycleDataViewBehavior, MinimalButton):
    """One button in the 'pick which fighter to equip' popup.

    Lightweight wrapper over MinimalButton that gets recycled by a
    RecycleView so we don't pay the canvas-setup cost per fighter.
    Previous impl built 1000 MinimalButton instances up-front for a
    1000-fighter roster — opening the popup took 1-2 seconds.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault('font_size', 11)
        kwargs.setdefault('btn_color', list(BTN_PRIMARY))
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(50))
        super().__init__(**kwargs)
        self._fi = -1
        # Bind once in __init__; dispatch through the module-level callback
        # table so the pool of recycled buttons doesn't each hold a back-ref
        # to the popup.
        self.bind(on_press=self._on_press)

    def refresh_view_attrs(self, rv, index, data):
        self._fi = data.get('fi', -1)
        self.text = data.get('text', '')

    def _on_press(self, *a):
        cb = _equip_choice_callbacks.get('pick')
        if cb is not None and self._fi >= 0:
            cb(self._fi)
