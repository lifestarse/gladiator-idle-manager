# Build: 2
"""RosterScreen _PerksMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m
from .perkstree import build_perk_tree_data


class _PerksMixin:

    def _build_perk_card(self, perk, fighter, fighter_idx, is_cross, engine):
        """Build a single perk card with unlock button if applicable."""
        from kivy.uix.label import Label
        pid = perk["id"]
        is_unlocked = pid in fighter.unlocked_perks
        cost = perk["cost"]
        if is_cross:
            cost = int(cost * perk.get("cross_class_cost_mult", 2.0))
        can_unlock = not is_unlocked and fighter.perk_points >= cost

        if is_unlocked:
            border_color = ACCENT_GOLD
        elif can_unlock:
            border_color = ACCENT_CYAN
        else:
            border_color = BTN_DISABLED

        card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(90),
                        padding=[dp(10), dp(6)], spacing=dp(2))
        card.border_color = border_color

        name_text = perk["name"]
        if is_unlocked:
            name_text += f"  [{t('perk_unlocked')}]"
        perk_nm_lbl = AutoShrinkLabel(
            text=name_text, font_size="10sp", bold=True,
            color=ACCENT_GOLD if is_unlocked else (TEXT_PRIMARY if can_unlock else TEXT_MUTED),
            halign="left", size_hint_y=None, height=dp(18),
        )
        bind_text_wrap(perk_nm_lbl)
        card.add_widget(perk_nm_lbl)

        desc_lbl = Label(
            text=perk.get("description", ""), font_size="11sp", font_name='PixelFont',
            color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
        )
        desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
        desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
        def _upd_card(inst, h, c=card):
            c.height = max(dp(90), h + dp(60))
        desc_lbl.bind(height=_upd_card)
        card.add_widget(desc_lbl)

        if not is_unlocked:
            btn = MinimalButton(
                text=t("perk_unlock_btn", cost=cost), font_size=11,
                btn_color=ACCENT_CYAN if can_unlock else BTN_DISABLED,
                text_color=BG_DARK if can_unlock else TEXT_MUTED,
                size_hint_y=None, height=dp(30),
            )
            def _unlock(inst, fi=fighter_idx, pi=pid):
                result = engine.unlock_perk(fi, pi)
                if result.ok:
                    self._show_perk_tree(fi)
                else:
                    App.get_running_app().show_toast(result.message)
            btn.bind(on_press=_unlock)
            card.add_widget(btn)

        return card

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
