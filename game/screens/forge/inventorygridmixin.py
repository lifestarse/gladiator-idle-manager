# Build: 1
"""_InventoryGridMixin — heavy _refresh_inventory_grid method."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _batch_fill_grid, _m


class _InventoryGridMixin:
    def _refresh_inventory_grid(self):
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        # view_state is "inventory_list" here; derived flags (including
        # _show_inv_tabs=True) have already been set by on_view_state.
        engine = App.get_running_app().engine

        # Inventory tab buttons — in fixed box above scroll (rebuild only on tab change)
        tabs_box = self.ids.get("inv_tabs_box")
        tabs_key = (self.inventory_tab, self.inventory_rarity_filter, self.inventory_equip_filter, self.inventory_sort)
        if tabs_box and self._needs_rebuild(self, '_inv_tabs_key', tabs_key):
            tabs_box.clear_widgets()
            slot_tabs = [(s, t(k)) for s, k in [
                ("weapon", "tab_weapon"), ("armor", "tab_armor"),
                ("accessory", "tab_accessory"), ("relic", "tab_relic"), ("shard", "tab_shard"),
            ]]
            tabs_box.add_widget(build_tab_row(slot_tabs, self.inventory_tab, self.set_inventory_tab))

            if self.inventory_tab != "shard":
                rarity_tabs = [(r, t(k)) for r, k in [
                    ("all", "filter_all"), ("common", "filter_common"),
                    ("uncommon", "filter_uncommon"), ("rare", "filter_rare"),
                    ("epic", "filter_epic"), ("legendary", "filter_legendary"),
                ]]
                tabs_box.add_widget(build_tab_row(
                    rarity_tabs, self.inventory_rarity_filter, self.set_rarity_filter,
                    active_color=ACCENT_GOLD, height=dp(30),
                ))
                equip_tabs = [
                    ("all", t("filter_all")),
                    ("free", t("filter_free")),
                    ("equipped", t("filter_equipped")),
                ]
                tabs_box.add_widget(build_tab_row(
                    equip_tabs, self.inventory_equip_filter, self.set_equip_filter,
                    active_color=ACCENT_CYAN, height=dp(30),
                ))
                sort_icon = "icons/ic_down.png" if self.inventory_sort == "best" else "icons/ic_up.png"
                sort_label = t("sort_best") if self.inventory_sort == "best" else t("sort_worst")
                sort_btn = MinimalButton(
                    text=sort_label, font_size=11,
                    btn_color=ACCENT_BROWN, text_color=TEXT_PRIMARY,
                    size_hint_y=None, height=dp(30),
                    icon_source=sort_icon,
                )
                sort_btn.bind(on_press=self.toggle_inventory_sort)
                tabs_box.add_widget(sort_btn)

        # Shard tab — show shard counts. Render goes to forge_grid (the
        # legacy ScrollView), NOT to inventory_rv (which virtualizes item
        # cards of a different shape). So we have to force the layout to
        # hide the inventory RV and expose forge_grid. Without this, the
        # inventory RV kept its stale data from the previous tab (e.g.
        # 'relic' items would continue to show under the 'Осколки' tab).
        if self.inventory_tab == "shard":
            # Flip flags: hide inventory RV, expose forge_grid's ScrollView.
            # refresh_forge re-applies _VIEW_FLAGS unconditionally next
            # entry, so these overrides are effectively scoped to this
            # shard-tab pass.
            self._inventory_rv_active = False
            self._forge_rv_active = False
            # Wipe stale data so nothing shows through if the RV layout
            # pass lags behind our flag change.
            inv_rv = self.ids.get("inventory_rv")
            if inv_rv is not None:
                inv_rv.data = []

            shard_key = tuple(engine.shards.get(t_, 0) for t_ in range(1, 6))
            if not self._needs_rebuild(self, '_shard_grid_key', shard_key, require_children=True):
                return
            _safe_clear(grid)
            for tier in range(1, 6):
                shard_card = BaseCard(
                    orientation="horizontal", size_hint_y=None, height=dp(48),
                    padding=[dp(12), dp(6)], spacing=dp(8),
                )
                shard_card.border_color = ACCENT_GOLD
                shard_card.add_text_row(
                    (t(f"shard_name_{tier}"), sp(11), True, ACCENT_GOLD, 0.6),
                    (f"x {engine.shards.get(tier, 0)}", sp(11), True, TEXT_PRIMARY, 0.4),
                )
                grid.add_widget(shard_card)
            return

        # Non-shard tab — make sure inventory RV is back on if we just
        # came from the shard tab (flags above were force-flipped).
        self._inventory_rv_active = True

        # Build unified list: ("inv", inv_idx, item, None) or ("equip", fighter_idx, item, fighter_name)
        eq_filter = self.inventory_equip_filter
        items_list = []
        if eq_filter != "equipped":
            for idx, item in enumerate(engine.inventory):
                if item.get("slot") == self.inventory_tab:
                    if self.inventory_rarity_filter == "all" or item.get("rarity") == self.inventory_rarity_filter:
                        items_list.append(("inv", idx, item, None))
        if eq_filter != "free":
            for fi, f in enumerate(engine.fighters):
                if f.alive:
                    eq = f.equipment.get(self.inventory_tab)
                    if eq:
                        if self.inventory_rarity_filter == "all" or eq.get("rarity") == self.inventory_rarity_filter:
                            items_list.append(("equip", fi, eq, f.name))

        reverse = self.inventory_sort == "best"
        items_list.sort(key=lambda x: self._item_total_stats(x[2]), reverse=reverse)

        # Prefer RecycleView for inventory list
        inv_rv = self.ids.get("inventory_rv")
        if inv_rv is not None:
            # _inventory_rv_active already True via view_state="inventory_list"
            from game.ui_helpers import _inventory_item_to_rv_data
            inv_rv.data = [
                _inventory_item_to_rv_data(src, idx, item, fn, self)
                for src, idx, item, fn in items_list
            ]
            return

        # Fast path: skip rebuild if same items
        inv_key = [(s, i, it.get("id"), it.get("upgrade_level", 0), fn) for s, i, it, fn in items_list]
        if not self._needs_rebuild(self, '_inv_grid_key', inv_key, require_children=True):
            return

        # Medium path: reuse cached cards for this tab+filter+sort
        cache_key = (self.inventory_tab, self.inventory_rarity_filter, self.inventory_equip_filter, self.inventory_sort)
        inv_cache = getattr(self, '_inv_card_cache', {})
        cached = inv_cache.get(cache_key)
        if cached and cached[0] == inv_key:
            cards = cached[1]
        else:
            cards = []
            if not items_list:
                cards.append(AutoShrinkLabel(
                    text=t("inventory_empty"), font_size="11sp",
                    color=TEXT_MUTED, size_hint_y=None, height=dp(60),
                    halign="center",
                ))
            else:
                for source, idx, item, fighter_name in items_list:
                    if source == "equip" and fighter_name:
                        f_obj = engine.fighters[idx]
                    else:
                        f_obj = None
                    if source == "inv":
                        def _tap(inst, i=idx): self._show_inv_detail(i)
                    else:
                        def _tap(inst, fi=idx, itm=item): self._show_equipped_detail(fi, itm)
                    cards.append(build_item_info_card(item, fighter=f_obj,
                                                     equipped_on=fighter_name if source == "equip" else None,
                                                     on_tap=_tap))
            inv_cache[cache_key] = (inv_key, cards)
            self._inv_card_cache = inv_cache

        _batch_fill_grid(grid, cards)
