# Build: 3
"""RosterScreen _PerksMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m
from .perkstree import build_perk_tree_data


class _PerksMixin:

    def _show_perk_tree(self, fighter_idx):
        """Show perk tree view via the perk_tree_rv RecycleView.

        Previously: cleared detail_grid and rebuilt up to ~40 BaseCards +
        MinimalButtons per tier toggle, each with dynamic text-wrap binds.
        That was the biggest remaining rebuild-lag hotspot after the arena
        refactor.

        Now: compute a flat list of dicts (one per visible row), set
        perk_tree_rv.data = ... — only visible rows become real widgets,
        and tier toggles are just another data-list rebuild (no widget
        allocation, no per-row binds).
        """
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]
        self.perk_view = True
        self.detail_index = fighter_idx
        self.roster_view = "detail"

        rv = self.ids.get("perk_tree_rv")
        if not rv:
            return

        if not hasattr(self, '_perk_expanded'):
            self._perk_expanded = {}
        expanded = self._perk_expanded.setdefault(f.name, {})

        rv.data = build_perk_tree_data(f, fighter_idx, expanded)

    def _on_perk_tier_toggle(self, tier_key, fighter_idx):
        """Callback fired by PerkTreeTierButtonView."""
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]
        if not hasattr(self, '_perk_expanded'):
            self._perk_expanded = {}
        expanded = self._perk_expanded.setdefault(f.name, {})
        expanded[tier_key] = not expanded.get(tier_key, False)
        rv = self.ids.get("perk_tree_rv")
        if rv is not None:
            rv.data = build_perk_tree_data(f, fighter_idx, expanded)

    def _on_perk_unlock(self, perk_id, fighter_idx):
        """Callback fired by PerkTreePerkCardView's unlock button."""
        # Passive-row synthetic id: ignore taps on those.
        if perk_id.startswith("__"):
            return
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        result = engine.unlock_perk(fighter_idx, perk_id)
        if result.ok:
            # Rebuild with new unlocked set; expansion state is preserved.
            self._show_perk_tree(fighter_idx)
        else:
            App.get_running_app().show_toast(result.message)
