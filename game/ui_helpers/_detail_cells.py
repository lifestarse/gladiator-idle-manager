# Build: 3
"""BattleDetailLineView, FighterEquipChoiceView — RV cells."""
from ._imports import *  # noqa: F401,F403
from ._perks_cells import _equip_choice_callbacks


_DEFAULT_LINE_HEIGHT = dp(18)
_DEFAULT_LINE_FONT = '11sp'


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
        kwargs.setdefault('font_size', _DEFAULT_LINE_FONT)
        kwargs.setdefault('halign', 'left')
        kwargs.setdefault('valign', 'middle')
        kwargs.setdefault('font_name', 'PixelFont')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', _DEFAULT_LINE_HEIGHT)
        kwargs.setdefault('shorten', True)
        super().__init__(**kwargs)
        self.bind(size=lambda w, s: setattr(w, 'text_size', s))

    def refresh_view_attrs(self, rv, index, data):
        line = data.get('text', '') or ''
        self.text = line
        explicit = data.get('color')
        if explicit is not None:
            self.color = list(explicit)
            self.height = data.get('height', _DEFAULT_LINE_HEIGHT)
            self.bold = bool(data.get('bold', False))
            self.font_size = data.get('font_size', _DEFAULT_LINE_FONT)
            return
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
        if self.height != _DEFAULT_LINE_HEIGHT:
            self.height = _DEFAULT_LINE_HEIGHT
        if self.font_size != _DEFAULT_LINE_FONT:
            self.font_size = _DEFAULT_LINE_FONT
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
