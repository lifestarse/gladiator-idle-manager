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


# ============================================================
#  PERK TREE VIEW — heterogeneous RecycleView rows
# ============================================================
#
# Before: RosterScreen._show_perk_tree cleared detail_grid and re-built up
# to ~40 BaseCards + 6 MinimalButtons on every tier toggle and every perk
# unlock. Each perk card had 3-4 dynamic property bindings. Visibly laggy
# when the user flipped tiers open/closed.
#
# After: data-driven RecycleView with per-row viewclass. Three viewclass
# types below; the RV's data list mixes them by setting the `viewclass`
# key per row. Only visible rows are real widgets, and a tier toggle is
# just a data-list rebuild (no widget allocation).

_perk_callbacks = {}
"""Registered by RosterScreen.on_enter.
Keys:
  'toggle_tier' → callable(tier_key, fighter_idx)
  'unlock'      → callable(perk_id, fighter_idx)
"""


class PerkTreeLabelView(RecycleDataViewBehavior, AutoShrinkLabel):
    """Heading/subheading row — class title, perk points line, section header.

    The RV gives this a fixed height from data; we just update text + color.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault('halign', 'center')
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)

    def refresh_view_attrs(self, rv, index, data):
        self.text = data.get('text', '')
        self.halign = data.get('halign', 'center')
        self.bold = bool(data.get('bold', False))
        self.color = list(data.get('color', TEXT_MUTED))
        fs = data.get('font_size', '10sp')
        # AutoShrinkLabel resets _base_font_size whenever font_size is
        # assigned, so this is safe to call on every rebind.
        self.font_size = fs
        self.height = data.get('height', dp(30))


class PerkTreeTierButtonView(RecycleDataViewBehavior, MinimalButton):
    """Tier toggle button — arrow + "Tier N (X/Y)". Tapping flips expand state."""

    def __init__(self, **kwargs):
        kwargs.setdefault('btn_color', list(ACCENT_CYAN))
        kwargs.setdefault('text_color', list(BG_DARK))
        kwargs.setdefault('font_size', 11)
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(30))
        super().__init__(**kwargs)
        self._tier_key = ''
        self._fighter_idx = -1
        self.bind(on_press=lambda *a: self._on_toggle())

    def _on_toggle(self):
        cb = _perk_callbacks.get('toggle_tier')
        if cb and self._tier_key:
            cb(self._tier_key, self._fighter_idx)

    def refresh_view_attrs(self, rv, index, data):
        self._tier_key = data.get('tier_key', '')
        self._fighter_idx = data.get('fighter_idx', -1)
        self.text = data.get('text', '')
        self.height = data.get('height', dp(30))


class PerkTreePerkCardView(RecycleDataViewBehavior, BoxLayout):
    """One perk card with name, description, and (if locked) an unlock button.

    Height is fixed per row (caller picks via data['height']). Descriptions
    that overflow the card will clip at valign=top rather than push the
    card taller — avoids the dynamic-measure dance of the old GridLayout
    code, which was the main source of perk-tree lag.
    """

    def __init__(self, **kwargs):
        from kivy.uix.label import Label
        from kivy.graphics import Color, Line
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(110))
        kwargs.setdefault('padding', [dp(10), dp(6)])
        kwargs.setdefault('spacing', dp(2))
        super().__init__(**kwargs)
        self._perk_id = ''
        self._fighter_idx = -1

        # Border — thin line around the card. We update the Color per row
        # (locked/unlockable/unlocked).
        with self.canvas.before:
            self._bg_color = Color(*BG_CARD)
            self._bg_rect = _RRect = None  # placeholder, assigned via graphics below
            # We'll use a simple Rectangle via canvas.after for the border.
        # Use a Kivy Line instruction for the 1px border; recolored per state.
        with self.canvas.after:
            self._border_color = Color(*BTN_DISABLED)
            self._border_line = Line(rectangle=[0, 0, 1, 1], width=1.0)
        self.bind(pos=self._sync_canvas, size=self._sync_canvas)

        self._name_lbl = AutoShrinkLabel(
            font_size="10sp", bold=True, color=list(TEXT_PRIMARY),
            halign="left", size_hint_y=None, height=dp(22),
        )
        bind_text_wrap(self._name_lbl)
        self._desc_lbl = Label(
            font_size="11sp", font_name='PixelFont', color=list(TEXT_MUTED),
            halign="left", valign="top", size_hint_y=None,
        )
        # Description wraps to width but is clipped by card height; no
        # height→card-height propagation (that was the perf hit).
        self._desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size",
                                                           (w - dp(20), None)))
        # Anchor description height to 50% of the remaining card space; this
        # is recomputed in refresh_view_attrs whenever the card height changes.
        self._desc_lbl.height = dp(50)

        self._btn = MinimalButton(
            text="", font_size=11, size_hint_y=None, height=dp(28),
        )
        self._btn.bind(on_press=lambda *a: self._on_unlock())

        self.add_widget(self._name_lbl)
        self.add_widget(self._desc_lbl)
        self.add_widget(self._btn)
        self._btn_visible = True  # tracks whether button is currently in the layout

    def _sync_canvas(self, *args):
        # Background rect
        if self.canvas.before.children:
            # Border line follows current rect
            pass
        self._border_line.rectangle = [self.x, self.y, self.width, self.height]

    def _on_unlock(self):
        cb = _perk_callbacks.get('unlock')
        if cb and self._perk_id:
            cb(self._perk_id, self._fighter_idx)

    def refresh_view_attrs(self, rv, index, data):
        self._perk_id = data.get('perk_id', '')
        self._fighter_idx = data.get('fighter_idx', -1)
        self.height = data.get('height', dp(110))

        state = data.get('state', 'locked')  # 'unlocked' | 'can_unlock' | 'locked'
        if state == 'unlocked':
            border = ACCENT_GOLD
            name_color = ACCENT_GOLD
        elif state == 'can_unlock':
            border = ACCENT_CYAN
            name_color = TEXT_PRIMARY
        else:
            border = BTN_DISABLED
            name_color = TEXT_MUTED
        self._border_color.rgba = list(border)

        self._name_lbl.text = data.get('name', '')
        self._name_lbl.color = list(name_color)
        self._desc_lbl.text = data.get('desc', '')
        self._desc_lbl.height = max(dp(24), self.height - dp(60))

        # Button swap: visible only for locked/can_unlock rows.
        should_show_btn = state != 'unlocked'
        if should_show_btn and not self._btn_visible:
            self.add_widget(self._btn)
            self._btn_visible = True
        elif not should_show_btn and self._btn_visible:
            self.remove_widget(self._btn)
            self._btn_visible = False

        if should_show_btn:
            self._btn.text = data.get('btn_text', '')
            can_unlock = state == 'can_unlock'
            self._btn.btn_color = list(ACCENT_CYAN if can_unlock else BTN_DISABLED)
            self._btn.text_color = list(BG_DARK if can_unlock else TEXT_MUTED)




_equip_choice_callbacks = {}
"""Registered by ForgeScreen._show_equip_fighter_popup before open.
Keys: 'pick' → callable(fighter_idx: int).
"""




def _measure_perk_card_height(description):
    """Pick a fixed row height based on description length.

    Cheap linear heuristic — errs on the side of taller cards so short
    descriptions have breathing room and longer ones don't clip too hard.
    Exact wrap depends on font/width, but for PressStart2P at 11sp the
    ~40 chars-per-line estimate is close enough.
    """
    n = len(description or "")
    if n <= 40:
        lines = 1
    elif n <= 100:
        lines = 2
    elif n <= 180:
        lines = 3
    else:
        lines = 4
    # name(22) + desc(lines*18) + btn(28) + padding/spacing(28) ≈
    return dp(22 + lines * 18 + 28 + 28)
