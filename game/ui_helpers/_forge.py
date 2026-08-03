# Build: 9
"""ui_helpers._forge — RV data adapters + forge grid refresh.

build_forge_card() / _get_card_cache() and the legacy GridLayout branch of
refresh_forge_grid() were removed in the 2026-08 redesign wave 0 cleanup:
forge_rv is always present in kv/forge_screen.kv, so the fallback never ran.
(forge_grid itself is alive — it hosts the detail/upgrade/enchant views.)
"""
from ._imports import *  # noqa: F401,F403
from game.passives import passive_marker


# ============================================================
#  FORGE
# ============================================================

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
    passive_mark = passive_marker(item)
    s, a, v = calc_item_stats(item)
    return {
        'iid': item.get('id', ''),
        '_forge': forge_screen,
        'mode': source,  # 'inv' or 'equip'
        'idx': idx,
        'slot': slot,
        'rarity': rarity,
        'name': item_display_name(item),
        'rarity_color': list(rcolor),
        'upgrade_level': item.get('upgrade_level', 0),
        'ench_display': ench_display,
        'passive_mark': passive_mark,
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
    passive_mark = passive_marker(item)
    s, a, v = calc_item_stats(item)
    return {
        'iid': item['id'],
        '_forge': forge_screen,
        'slot': slot,
        'rarity': rarity,
        'name': item_display_name(item),
        'rarity_color': list(rcolor),
        'upgrade_level': item.get('upgrade_level', 0),
        'ench_display': ench_display,
        'passive_mark': passive_mark,
        'slot_rarity_text': slot_rarity,
        's': s, 'a': a, 'v': v,
        'affordable': item.get('affordable', False),
        'buy_text': t('buy_btn_price', price=fmt_num(item['cost'])),
    }


def refresh_forge_grid(forge_screen):
    """Populate the forge shop RecycleView (forge_rv)."""
    items = forge_screen.forge_items

    rv = forge_screen.ids.get("forge_rv")
    if rv is None:
        return
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
