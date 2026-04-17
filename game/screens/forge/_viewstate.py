# Build: 1
"""_ViewStateMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _ViewStateMixin:
    def on_view_state(self, inst, new_state):
        """Derive the 6 KV-bound flags from view_state.

        Kivy calls this whenever view_state changes. Keeps the flags consistent
        so two contradicting booleans cannot both be True.
        """
        flags = _VIEW_FLAGS.get(new_state)
        if flags is None:
            return
        (self.show_inventory, self._forge_rv_active, self._inventory_rv_active,
         self._show_inv_tabs, self.weapon_upgrade_active,
         self.enchant_active) = flags

    def _set_view(self, new_state):
        """Transition to a new view state. No-op if already there."""
        if new_state not in _VIEW_FLAGS:
            return
        self.view_state = new_state  # triggers on_view_state

    def _sparkle_effect(self, widget, count=5):
        """Spawn sparkle particles around a widget on upgrade success."""
        import random
        parent = widget.parent
        if not parent:
            return
        for _ in range(count):
            ft = FloatingText(
                text="*", font_size="11sp", bold=True,
                color=list(ACCENT_GOLD),
                center_x=widget.center_x + random.randint(-20, 20),
                y=widget.center_y + random.randint(-10, 10),
                size_hint=(None, None),
            )
            parent.add_widget(ft)

    def _enter_detail_mode(self):
        """Kept for backward-compat. view_state is now managed by the caller
        via _set_view; this just invalidates cached layout keys."""
        self._inv_tabs_key = None

    def _reset_forge_state(self, keep_inventory=False):
        """Reset navigation payload + view state. Call on enter or back."""
        self.inv_detail_idx = -1
        self.eq_detail_fighter = -1
        self.eq_detail_slot = ""
        self._enchant_source = None
        self._enchant_idx = None
        self._enchant_item = None
        self._enchant_fighter = None
        self._preview_item = None
        self._inv_tabs_key = None
        self._shop_tabs_key = None
        self._inv_grid_key = None
        self._shard_grid_key = None
        self._inv_card_cache = {}
        # Return to the appropriate list view
        self._set_view("inventory_list" if keep_inventory else "shop")

