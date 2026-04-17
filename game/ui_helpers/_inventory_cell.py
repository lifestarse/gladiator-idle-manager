# Build: 1
"""InventoryCardView — inventory grid cell (RecycleView viewclass)."""
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
from ._common import _batch_fill_grid, _bind_long_tap

class InventoryCardView(RecycleDataViewBehavior, BoxLayout):
    """RecycleView viewclass for inventory item cards."""

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(75))
        super().__init__(**kwargs)
        self._iid = ''
        self._mode = 'inv'      # 'inv' or 'equip'
        self._idx = 0           # inv_idx or fighter_idx
        self._slot = ''         # needed for equipped detail lookup
        self._forge_screen = None

        from game.widgets import BaseCard
        self._info = BaseCard(
            orientation="vertical", size_hint_y=1,
            padding=[dp(12), dp(8)], spacing=dp(4),
        )

        # Row 1: name | level | enchantment
        row1 = BoxLayout(size_hint_y=0.35, spacing=dp(4))
        self._name_lbl = AutoShrinkLabel(
            font_size=sp(12), bold=True, halign="left",
            size_hint_x=None, width=1,
        )
        self._name_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row1.add_widget(self._name_lbl)
        self._level_lbl = AutoShrinkLabel(
            font_size=sp(10), bold=True, color=list(ACCENT_GOLD),
            halign="left", size_hint_x=None, width=dp(28),
        )
        self._level_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row1.add_widget(self._level_lbl)
        self._ench_lbl = AutoShrinkLabel(
            font_size=sp(11), bold=True, color=list(ACCENT_PURPLE),
            halign="left", size_hint_x=None, width=1,
        )
        self._ench_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row1.add_widget(self._ench_lbl)
        self._info.add_widget(row1)

        # Row 2: slot/rarity + equipped_on
        self._row2 = BoxLayout(size_hint_y=0.25, spacing=dp(4))
        self._sr_lbl = AutoShrinkLabel(
            font_size=sp(11), color=list(TEXT_MUTED),
            halign="left", size_hint_x=None, width=1,
        )
        self._sr_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        self._row2.add_widget(self._sr_lbl)
        self._eq_lbl = AutoShrinkLabel(
            font_size=sp(11), bold=True, color=list(ACCENT_CYAN),
            halign="left", size_hint_x=None, width=1,
        )
        self._eq_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        # eq_lbl conditionally added in refresh_view_attrs
        self._info.add_widget(self._row2)

        # Row 3: stats
        self._row3 = BoxLayout(size_hint_y=0.40, spacing=dp(8))

        def _mk_stat(icon_src):
            lbl = AutoShrinkLabel(
                font_size=sp(10), bold=True, color=list(ACCENT_GREEN),
                halign="left", valign="middle", size_hint_x=None, width=1,
            )
            lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
            ico = Image(source=icon_src, fit_mode="contain",
                        size_hint=(None, 1), width=dp(16))
            return lbl, ico
        self._str_lbl, self._str_ico = _mk_stat("sprites/icons/ic_str.png")
        self._agi_lbl, self._agi_ico = _mk_stat("sprites/icons/ic_agi.png")
        self._vit_lbl, self._vit_ico = _mk_stat("sprites/icons/ic_vit.png")
        self._no_stat_lbl = AutoShrinkLabel(
            text="—", font_size=sp(10), color=list(TEXT_MUTED), halign="left",
        )
        self._info.add_widget(self._row3)
        self.add_widget(self._info)

        _bind_long_tap(self._info, lambda w: self._on_tap())

    def refresh_view_attrs(self, rv, index, data):
        self._iid = data.get('iid', '')
        self._mode = data.get('mode', 'inv')
        self._idx = data.get('idx', 0)
        self._slot = data.get('slot', '')
        self._forge_screen = data.get('_forge')
        rcolor = list(data.get('rarity_color', TEXT_PRIMARY))
        self._info.border_color = rcolor

        self._name_lbl.text = data.get('name', '')
        self._name_lbl.color = rcolor

        lvl = data.get('upgrade_level', 0)
        self._level_lbl.text = f"+{lvl}" if lvl > 0 else ""
        self._ench_lbl.text = data.get('ench_display', '')
        self._sr_lbl.text = data.get('slot_rarity_text', '')

        # Row 2 equipped_on — add/remove label as needed
        eq_on = data.get('equipped_on', '')
        if self._eq_lbl.parent is None and eq_on:
            self._row2.add_widget(self._eq_lbl)
        elif self._eq_lbl.parent and not eq_on:
            self._row2.remove_widget(self._eq_lbl)
        self._eq_lbl.text = eq_on

        # Row 3: clear and re-add visible stats
        self._row3.clear_widgets()
        s = data.get('s', 0); a = data.get('a', 0); v = data.get('v', 0)
        if s > 0:
            self._str_lbl.text = str(s)
            self._row3.add_widget(self._str_lbl); self._row3.add_widget(self._str_ico)
        if a > 0:
            self._agi_lbl.text = str(a)
            self._row3.add_widget(self._agi_lbl); self._row3.add_widget(self._agi_ico)
        if v > 0:
            self._vit_lbl.text = str(v)
            self._row3.add_widget(self._vit_lbl); self._row3.add_widget(self._vit_ico)
        if not (s or a or v):
            self._row3.add_widget(self._no_stat_lbl)

    def _on_tap(self):
        if not self._forge_screen:
            return
        if self._mode == 'inv':
            self._forge_screen._show_inv_detail(self._idx)
        elif self._mode == 'equip':
            # Look up the live item dict from engine
            from kivy.app import App
            f = App.get_running_app().engine.fighters[self._idx]
            item = f.equipment.get(self._slot)
            if item:
                self._forge_screen._show_equipped_detail(self._idx, item)
