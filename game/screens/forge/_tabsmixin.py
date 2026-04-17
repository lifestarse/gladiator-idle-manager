# Build: 1
"""_TabsMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _TabsMixin:
    def set_forge_tab(self, tab):
        self._save_scroll()
        self._reset_forge_state()
        self.forge_tab = tab
        self.refresh_forge()
        self._restore_scroll()

    def toggle_inventory(self):
        self._save_scroll()
        was_inv = self.show_inventory
        # _reset_forge_state resets to "shop"; if we were in shop, flip to inv.
        self._reset_forge_state(keep_inventory=not was_inv)
        self.forge_tab = "weapon"
        self.refresh_forge()
        self._restore_scroll()

    def set_inventory_tab(self, tab):
        self._save_scroll()
        self.inventory_tab = tab
        self._inv_grid_key = None
        self._shard_grid_key = None
        self.refresh_forge()
        self._restore_scroll()

    def set_rarity_filter(self, rarity):
        self._save_scroll()
        self.inventory_rarity_filter = rarity
        self._inv_grid_key = None
        self.refresh_forge()
        self._restore_scroll()

    def set_equip_filter(self, value):
        self._save_scroll()
        self.inventory_equip_filter = value
        self._inv_grid_key = None
        self.refresh_forge()
        self._restore_scroll()

    def set_shop_rarity_filter(self, rarity):
        self._save_scroll()
        self.shop_rarity_filter = rarity
        self.refresh_forge()
        self._restore_scroll()

    def toggle_shop_sort(self, *a):
        self.shop_sort = "worst" if self.shop_sort == "best" else "best"
        self.refresh_forge()

    def toggle_inventory_sort(self, *a):
        self.inventory_sort = "worst" if self.inventory_sort == "best" else "best"
        self._inv_grid_key = None
        self.refresh_forge()

