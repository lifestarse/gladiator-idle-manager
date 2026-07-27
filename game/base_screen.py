# Build: 8
"""BaseScreen — unified base class for all game screens."""

from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.app import App
from game.models import fmt_num
from game.ui_helpers import _invalidate_grid_cache, _needs_rebuild as _needs_rebuild_impl


class BaseScreen(Screen):
    """Common base for Arena, Roster, Forge, Expedition, Lore, More screens.

    Provides shared top-bar properties (gold, diamonds) and
    a single _update_top_bar() method so every screen doesn't duplicate
    the same lines.
    """

    gold_text = StringProperty("0")
    diamond_text = StringProperty("0")

    def _update_top_bar(self):
        self._invalidate_all_caches()
        engine = App.get_running_app().engine
        self.gold_text = fmt_num(engine.gold)
        self.diamond_text = fmt_num(engine.diamonds)
        App.get_running_app().update_top_bar()

    def on_back_pressed(self):
        """Handle hardware back button. Return True if handled internally,
        False to let the app navigate to the previous screen."""
        return False

    def _invalidate_all_caches(self):
        """Wipe all _*_key caches on self and all grid children."""
        _invalidate_grid_cache(self)
        for grid_id in ('forge_grid', 'lore_grid', 'exp_grid', 'arena_grid',
                        'roster_rv', 'enemy_detail_grid', 'fighter_detail_grid'):
            grid = self.ids.get(grid_id)
            if grid:
                _invalidate_grid_cache(grid)

    def _get_grid(self, grid_id):
        return self.ids.get(grid_id)

    # Implementation lives in ui_helpers._layouts next to its counterpart
    # _invalidate_grid_cache. Moving it back onto this class would force
    # ui_helpers to import base_screen again and reclose an import cycle.
    # staticmethod keeps every `self._needs_rebuild(...)` call site working.
    _needs_rebuild = staticmethod(_needs_rebuild_impl)
