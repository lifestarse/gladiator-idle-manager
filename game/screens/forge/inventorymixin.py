# Build: 1
"""ForgeScreen _InventoryMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _batch_fill_grid


class _InventoryMixin:
    @staticmethod
    def _item_total_stats(item):
        """Composite 'power' score used for best/worst sort.

        Returned as a tuple so Python sorts lexicographically:

          1. enchantment flag — ANY enchanted item outranks ANY
             unenchanted one (user request: enchantment beats +25).
          2. power score — base stats × upgrade multiplier,
             capturing the 20%-per-level upgrade mechanic so two
             identical Abyssal Tridents rank +5 > +4 > +2.

        Within each (enchanted / unenchanted) group, higher power wins.
        """
        base = item.get("str", 0) + item.get("agi", 0) + item.get("vit", 0)
        lvl = item.get("upgrade_level", 0)
        power = base * (1 + lvl * 0.2)
        has_ench = 1 if item.get("enchantment") else 0
        return (has_ench, power)


    def _show_shop_preview(self, item):
        """Show read-only detail view for a shop item (no sell/equip/improve)."""
        self._enter_detail_mode()
        # view_state set to "shop_preview" by refresh_forge caller
        sv = self.ids.get("forge_scroll")
        if sv:
            sv.scroll_y = 1
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        sub = self._item_slot_subtitle(item)

        grid.add_widget(build_item_info_card(item, subtitle=sub))
        desc_card = self._build_description_card(item)
        if desc_card:
            grid.add_widget(desc_card)

    def _close_shop_preview(self):
        self._preview_item = None
        self.refresh_forge()

    def _close_inv_detail(self):
        self.inv_detail_idx = -1
        self.eq_detail_fighter = -1
        self.eq_detail_slot = ""
        self._enchant_source = None
        self._enchant_idx = None
        self._enchant_item = None
        self._enchant_fighter = None
        self._inv_grid_key = None
        self._shard_grid_key = None
        self._inv_tabs_key = None
        self._inv_card_cache = {}
        self._set_view("inventory_list")
        self.refresh_forge()
