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



# ------------------------------------------------------------------
#  Inventory RecycleView viewclass — item card without buy button.
#  Used in the forge ИНВЕНТАРЬ tab. Tap opens inv or equipped detail
#  based on data['mode'].
# ------------------------------------------------------------------



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
