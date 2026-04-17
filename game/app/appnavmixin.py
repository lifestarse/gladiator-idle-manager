# Build: 1
"""App _AppNavMixin."""
from game.app._shared import *  # noqa: F401,F403


class _AppNavMixin:
    def _navigate_to_forge(self, state):
        """Set ForgeScreen pending state and navigate (or refresh if already there)."""
        fs = self.sm.get_screen("forge")
        fs._pending_state = state
        if self.sm.current == "forge":
            fs._apply_pending_state()
        else:
            # Mark cross-screen entry depth so back unwinds correctly
            fs._cross_screen_pending = True
            if state.get('eq_detail_fighter', -1) >= 0 or state.get('inv_detail_idx', -1) >= 0:
                fs._entry_depth = 2   # item detail
            elif '_preview_item' in state:
                fs._entry_depth = 3   # shop preview
            elif state.get('show_inventory'):
                fs._entry_depth = 4   # inventory
            else:
                fs._entry_depth = 5   # shop tab
            self.sm.current = "forge"

    def open_equipped_detail(self, fighter_idx, slot):
        """Navigate to ForgeScreen and open equipped item detail — works from any screen."""
        self._navigate_to_forge({
            'show_inventory': True,
            'eq_detail_fighter': fighter_idx,
            'eq_detail_slot': slot,
        })

    def open_item_detail(self, inv_idx):
        """Navigate to ForgeScreen and open item detail — works from any screen."""
        self._navigate_to_forge({
            'show_inventory': True,
            'inv_detail_idx': inv_idx,
        })

    def open_forge_tab(self, slot):
        """Navigate to ForgeScreen shop with the given tab selected."""
        self._navigate_to_forge({'forge_tab': slot})

    def open_inventory_tab(self, tab, equip_filter="all"):
        """Navigate to ForgeScreen inventory with the given tab filter."""
        self._navigate_to_forge({
            'show_inventory': True,
            'inventory_tab': tab,
            'inventory_equip_filter': equip_filter,
        })

    def open_shop_preview(self, item):
        """Navigate to ForgeScreen and show read-only item preview."""
        self._navigate_to_forge({'_preview_item': item})

    def _on_screen_change(self, sm, new_screen):
        """Track navigation history whenever the active screen changes."""
        self.engine._ui_dirty = True  # force refresh on screen switch
        if self._going_back:
            self._going_back = False
        elif new_screen != self._current_screen:
            # Save current screen + its view state
            state = self._get_screen_state(self._current_screen)
            self._nav_history.append((self._current_screen, state))
        self._current_screen = new_screen

    def _get_screen_state(self, screen_name):
        """Snapshot the current view state of a screen."""
        scr = self.sm.get_screen(screen_name)
        if hasattr(scr, 'get_nav_state'):
            return scr.get_nav_state()
        return {}

    def _restore_screen_state(self, screen_name, state):
        """Restore a screen's view state from snapshot."""
        scr = self.sm.get_screen(screen_name)
        if hasattr(scr, 'restore_nav_state') and state:
            scr.restore_nav_state(state)

    def _on_keyboard(self, window, key, scancode, codepoint, modifier):
        """Handle Android back button (key 27) and desktop Escape."""
        if key == 27:
            self.go_back()
            return True  # always consume; prevent Android from exiting
        return False

    def go_back(self):
        """Navigate one step back: first within a screen, then to previous tab."""
        scr = self.sm.current_screen
        if hasattr(scr, "on_back_pressed") and scr.on_back_pressed():
            return  # screen handled it internally
        if self._nav_history:
            prev_name, prev_state = self._nav_history.pop()
            self._going_back = True
            self._restore_screen_state(prev_name, prev_state)
            self.sm.current = prev_name
