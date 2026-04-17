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
from ._common import _batch_fill_grid, _bind_long_tap


# ============================================================
#  FORGE
# ============================================================

def build_forge_card(item, forge_screen):
    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)

    wrapper = BoxLayout(
        orientation="vertical",
        size_hint_y=None, height=dp(114),
        spacing=dp(4),
    )

    from kivy.app import App
    def _tap(inst, it=item):
        # Shop tap always opens pristine shop preview (never the
        # upgraded/enchanted inventory copy — use ИНВЕНТАРЬ for that).
        App.get_running_app().open_shop_preview(it)
    wrapper.add_widget(build_item_info_card(item, on_tap=_tap))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=t("buy_btn_price", price=fmt_num(item['cost'])), font_size=sp(11),
        size_hint_y=None, height=dp(32),
        btn_color=rcolor if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gold.png",
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: forge_screen.buy(iid))
    wrapper.add_widget(buy_btn)
    return wrapper


def _get_card_cache(forge_screen):
    """Get or create the permanent {item_id: card} cache."""
    cache = getattr(forge_screen, '_card_by_id', None)
    if cache is None:
        cache = {}
        forge_screen._card_by_id = cache
    return cache


# ------------------------------------------------------------------
#  RecycleView viewclass — forge shop card. Widgets pre-created once,
#  refresh_view_attrs just updates text/color/visibility. Allows
#  RecycleView to virtualize (only ~10 cards exist at any time, rest
#  recycled on scroll).
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
#  Inventory RecycleView viewclass — item card without buy button.
#  Used in the forge ИНВЕНТАРЬ tab. Tap opens inv or equipped detail
#  based on data['mode'].
# ------------------------------------------------------------------

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


def _inventory_item_to_rv_data(source, idx, item, fighter_name, forge_screen):
    """Convert inventory/equipped item to InventoryCardView data dict."""
    import game.models as _m
    from game.models import calc_item_stats, item_display_name

    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)
    slot = item.get("slot", "?")
    ench_id = item.get("enchantment", "")
    ench_display = ""
    if ench_id:
        ench_data = _m.ENCHANTMENT_TYPES.get(ench_id)
        ench_display = f"[{ench_data['name']}]" if ench_data else f"[{ench_id}]"
    slot_rarity = f"{t('slot_' + slot + '_upper')} [{t('rarity_' + rarity + '_upper')}]"
    s, a, v = calc_item_stats(item, None)
    return {
        'iid': item.get('id', ''),
        '_forge': forge_screen,
        'mode': source,  # 'inv' or 'equip'
        'idx': idx,
        'slot': slot,
        'name': item_display_name(item),
        'rarity_color': list(rcolor),
        'upgrade_level': item.get('upgrade_level', 0),
        'ench_display': ench_display,
        'slot_rarity_text': slot_rarity,
        'equipped_on': fighter_name or '',
        's': s, 'a': a, 'v': v,
    }


def _forge_item_to_rv_data(item, forge_screen):
    """Convert engine forge item dict to ForgeCardView data dict."""
    import game.models as _m
    from game.models import calc_item_stats, item_display_name

    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)
    slot = item.get("slot", "?")
    ench_id = item.get("enchantment", "")
    ench_display = ""
    if ench_id:
        ench_data = _m.ENCHANTMENT_TYPES.get(ench_id)
        ench_display = f"[{ench_data['name']}]" if ench_data else f"[{ench_id}]"
    slot_rarity = f"{t('slot_' + slot + '_upper')} [{t('rarity_' + rarity + '_upper')}]"
    s, a, v = calc_item_stats(item, None)
    return {
        'iid': item['id'],
        '_forge': forge_screen,
        'name': item_display_name(item),
        'rarity_color': list(rcolor),
        'upgrade_level': item.get('upgrade_level', 0),
        'ench_display': ench_display,
        'slot_rarity_text': slot_rarity,
        's': s, 'a': a, 'v': v,
        'affordable': item.get('affordable', False),
        'buy_text': t('buy_btn_price', price=fmt_num(item['cost'])),
    }


def refresh_forge_grid(forge_screen):
    """Populate forge shop list. Uses RecycleView (forge_rv) if available,
    falls back to legacy GridLayout (forge_grid) otherwise."""
    items = forge_screen.forge_items

    # Prefer RecycleView — virtualizes to ~10 visible widgets
    rv = forge_screen.ids.get("forge_rv")
    if rv is not None:
        new_data = [_forge_item_to_rv_data(i, forge_screen) for i in items]
        # Reported bug: navigating into Forge directly from Lore's
        # blog_detail sometimes left the forge showing tabs but no items.
        # Root cause: the blog_detail RV occupies the same layout
        # scheduling queue; when Forge's on_enter fires right after, its
        # rv.data assignment can collide with pending layout work and the
        # RV pool fails to materialize the visible rows. Workaround: hard-
        # reset the RV's pool by going through empty list first, then
        # explicitly ask for a refresh. Cheap enough to do every time.
        rv.data = []
        rv.data = new_data
        if hasattr(rv, 'refresh_from_data'):
            rv.refresh_from_data()
        return

    # Legacy path: GridLayout with pre-built cached cards (all 130 in tree)
    grid = forge_screen.ids.get("forge_grid")
    if not grid:
        return
    item_ids = [i["id"] for i in items]

    # Build missing cards (once per item, cached forever)
    cache = _get_card_cache(forge_screen)
    for item in items:
        iid = item["id"]
        if iid not in cache:
            cache[iid] = build_forge_card(item, forge_screen)

    # Collect cards in display order and update affordability
    cards = []
    for item in items:
        card = cache[item["id"]]
        rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
        affordable = item["affordable"]
        buy_btn = card.children[0]
        buy_btn.btn_color = rcolor if affordable else BTN_DISABLED
        buy_btn.text_color = BG_DARK if affordable else TEXT_MUTED
        cards.append(card)

    # Skip re-layout if already showing the same cards in same order
    if (hasattr(grid, '_item_ids') and grid._item_ids == item_ids
            and len(grid.children) == len(cards)):
        return

    grid._item_ids = item_ids
    _batch_fill_grid(grid, cards)
