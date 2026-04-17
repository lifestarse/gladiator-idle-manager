# Build: 1
"""ForgeCardView — forge grid cell (RecycleView viewclass)."""
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

class ForgeCardView(RecycleDataViewBehavior, BoxLayout):
    """RecycleView viewclass for forge shop cards."""

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(114))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)
        self._iid = ''
        self._forge_screen = None

        # --- Info card (75dp) ---
        from game.widgets import BaseCard
        self._info = BaseCard(
            orientation="vertical", size_hint_y=None, height=dp(75),
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

        # Row 2: slot/rarity label
        row2 = BoxLayout(size_hint_y=0.25, spacing=dp(4))
        self._sr_lbl = AutoShrinkLabel(
            font_size=sp(11), color=list(TEXT_MUTED),
            halign="left", size_hint_x=None, width=1,
        )
        self._sr_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row2.add_widget(self._sr_lbl)
        self._info.add_widget(row2)

        # Row 3: stat icons — pre-create all 3 pairs + "—" fallback
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

        # Buy button (32dp)
        self._buy_btn = MinimalButton(
            font_size=sp(11), size_hint_y=None, height=dp(32),
            icon_source="sprites/icons/ic_gold.png",
        )
        self._buy_btn.bind(on_press=self._on_buy_press)
        self.add_widget(self._buy_btn)

        # Tap on info card → open item detail
        _bind_long_tap(self._info, lambda w: self._on_info_tap())

    def refresh_view_attrs(self, rv, index, data):
        """Called by RecycleView when this instance should display new data.
        Do NOT call super — that would auto-setattr all data keys."""
        self._iid = data.get('iid', '')
        self._forge_screen = data.get('_forge')
        rcolor = list(data.get('rarity_color', TEXT_PRIMARY))
        self._info.border_color = rcolor

        self._name_lbl.text = data.get('name', '')
        self._name_lbl.color = rcolor

        lvl = data.get('upgrade_level', 0)
        self._level_lbl.text = f"+{lvl}" if lvl > 0 else ""
        self._ench_lbl.text = data.get('ench_display', '')
        self._sr_lbl.text = data.get('slot_rarity_text', '')

        # Stats row — clear and re-add only the stats that are > 0
        self._row3.clear_widgets()
        s = data.get('s', 0)
        a = data.get('a', 0)
        v = data.get('v', 0)
        if s > 0:
            self._str_lbl.text = str(s)
            self._row3.add_widget(self._str_lbl)
            self._row3.add_widget(self._str_ico)
        if a > 0:
            self._agi_lbl.text = str(a)
            self._row3.add_widget(self._agi_lbl)
            self._row3.add_widget(self._agi_ico)
        if v > 0:
            self._vit_lbl.text = str(v)
            self._row3.add_widget(self._vit_lbl)
            self._row3.add_widget(self._vit_ico)
        if not (s or a or v):
            self._row3.add_widget(self._no_stat_lbl)

        # Buy button
        affordable = data.get('affordable', False)
        self._buy_btn.text = data.get('buy_text', '')
        self._buy_btn.btn_color = rcolor if affordable else list(BTN_DISABLED)
        self._buy_btn.text_color = list(BG_DARK) if affordable else list(TEXT_MUTED)

    def _on_buy_press(self, inst):
        if self._forge_screen and self._iid:
            self._forge_screen.buy(self._iid)

    def _on_info_tap(self):
        """Shop tap always shows the pristine shop preview — even if the
        player already owns a (possibly upgraded/enchanted) copy. The
        upgraded inventory copy is accessible from the ИНВЕНТАРЬ tab."""
        from kivy.app import App
        app = App.get_running_app()
        item = next(
            (i for i in app.engine.get_forge_items() if i['id'] == self._iid),
            None,
        )
        if item:
            app.open_shop_preview(item)
