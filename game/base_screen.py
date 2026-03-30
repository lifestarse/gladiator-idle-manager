# Build: 6
"""BaseScreen — unified base class for all game screens."""

from kivy.uix.screenmanager import Screen
from kivy.properties import StringProperty
from kivy.app import App
from game.models import fmt_num
from game.ui_helpers import _invalidate_grid_cache


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

    @staticmethod
    def _needs_rebuild(obj, key_attr, new_key, require_children=False):
        """Check if cached key changed. Updates key and returns True if rebuild needed.

        Args:
            obj: object holding the cache key (self, grid widget, etc.)
            key_attr: attribute name for the cache key (e.g. '_roster_key')
            new_key: new key value to compare
            require_children: if True, also rebuild when obj has no children
        """
        old = getattr(obj, key_attr, None)
        if old == new_key and (not require_children or getattr(obj, 'children', True)):
            return False
        setattr(obj, key_attr, new_key)
        return True
