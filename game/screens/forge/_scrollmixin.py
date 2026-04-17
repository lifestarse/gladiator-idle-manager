# Build: 1
"""_ScrollMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _ScrollMixin:
    def _scroll_key(self):
        if self.show_inventory:
            return f"inv_{self.inventory_tab}_{self.inventory_rarity_filter}"
        return f"shop_{self.forge_tab}_{self.shop_rarity_filter}"

    def _save_scroll(self):
        sv = self.ids.get("forge_scroll")
        if sv:
            self._scroll_positions[self._scroll_key()] = sv.scroll_y

    def _restore_scroll(self):
        sv = self.ids.get("forge_scroll")
        if sv:
            pos = self._scroll_positions.get(self._scroll_key(), 1.0)
            Clock.schedule_once(lambda dt: setattr(sv, 'scroll_y', pos), 0)

