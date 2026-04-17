# Build: 1
"""ForgeScreen _NavStateMixin."""
# Build: 1
"""ForgeScreen core — lifecycle + small methods."""
from ._screen_imports import *  # noqa: F401,F403
from .inventorymixin import _InventoryMixin
from .upgrademixin import _UpgradeMixin
from .enchantmixin import _EnchantMixin
from .equipswapmixin import _EquipSwapMixin
from .shopmixin import _ShopMixin
from ._viewstate import _ViewStateMixin
from ._scrollmixin import _ScrollMixin
from ._tabsmixin import _TabsMixin
from .itemdescmixin import _ItemDescMixin
from .equipfighterpopupmixin import _EquipFighterPopupMixin


from ._screen_imports import _m

class _NavStateMixin:
    def get_nav_state(self):
        """Snapshot current view for navigation stack."""
        return {
            'view_state': self.view_state,
            'forge_tab': self.forge_tab,
            'inventory_tab': self.inventory_tab,
            'inv_detail_idx': self.inv_detail_idx,
            'eq_detail_fighter': self.eq_detail_fighter,
            'eq_detail_slot': self.eq_detail_slot,
            'inventory_rarity_filter': self.inventory_rarity_filter,
            'inventory_equip_filter': self.inventory_equip_filter,
            'shop_rarity_filter': self.shop_rarity_filter,
            'shop_sort': self.shop_sort,
            'inventory_sort': self.inventory_sort,
        }

    def restore_nav_state(self, state):
        """Restore view from navigation stack — on_enter will use this."""
        self._pending_state = state

    def _apply_pending_state(self):
        """Consume _pending_state and refresh. Called by on_enter and direct navigation."""
        state = self._pending_state
        self._pending_state = None
        self._reset_forge_state()
        if state:
            # Apply payload/filter keys first, then pick the view state
            # based on WHICH payload keys are present. Legacy callers
            # (App.open_equipped_detail etc.) pass show_inventory=True
            # plus eq_detail_fighter/eq_detail_slot — we have to route
            # those to "equipped_detail", not "inventory_list", or the
            # tap from Roster lands on the bare inventory grid instead
            # of the item's detail page.
            view_key = state.pop('view_state', None)
            legacy_show_inv = state.pop('show_inventory', False)
            preview_item = state.pop('_preview_item', None)
            for k, v in state.items():
                if hasattr(self, k):
                    setattr(self, k, v)
            if preview_item is not None:
                self._preview_item = preview_item
            # Infer view_state from payload when not explicit. Precedence
            # mirrors on_back_pressed levels so navigation is symmetric.
            if view_key is None:
                if self.view_state in ("upgrade", "enchant"):
                    # Already in a detail-stacked view; don't clobber.
                    view_key = self.view_state
                elif (getattr(self, 'eq_detail_fighter', -1) >= 0
                      and getattr(self, 'eq_detail_slot', "")):
                    view_key = "equipped_detail"
                elif getattr(self, 'inv_detail_idx', -1) >= 0:
                    view_key = "inventory_detail"
                elif preview_item is not None:
                    view_key = "shop_preview"
                elif legacy_show_inv:
                    view_key = "inventory_list"
                else:
                    view_key = "shop"
            self._set_view(view_key)
        self._scroll_positions = {}
        self.refresh_forge()
        # Safety net: Kivy RecycleView occasionally misses its first
        # layout pass when data is set before the screen's widget tree
        # finishes its own layout (the empty-forge-on-entry bug the
        # user reported). Re-run the refresh on the next frame — if the
        # first run succeeded this is a no-op (same rv.data), and if it
        # didn't, this catches up before the user sees the blank panel.
        Clock.schedule_once(lambda dt: self.refresh_forge(), 0)
