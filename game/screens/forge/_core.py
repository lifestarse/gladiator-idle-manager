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


class ForgeScreen(BaseScreen, _InventoryMixin, _UpgradeMixin, _EnchantMixin, _EquipSwapMixin, _ShopMixin, _ViewStateMixin, _ScrollMixin, _TabsMixin, _ItemDescMixin, _EquipFighterPopupMixin):
    forge_items = ListProperty()

    view_state = StringProperty("shop")

    show_inventory = BooleanProperty(False)

    _forge_rv_active = BooleanProperty(False)

    _inventory_rv_active = BooleanProperty(False)

    _show_inv_tabs = BooleanProperty(False)

    weapon_upgrade_active = BooleanProperty(False)

    enchant_active = BooleanProperty(False)

    inventory_btn_text = StringProperty("")

    forge_tab = StringProperty("weapon")

    inventory_tab = StringProperty("weapon")

    inventory_rarity_filter = StringProperty("all")

    inventory_equip_filter = StringProperty("all")  # "all", "free", "equipped"

    shop_rarity_filter = StringProperty("all")

    shop_sort = StringProperty("best")       # "best" or "worst"

    inventory_sort = StringProperty("best")  # "best" or "worst"

    shard_text = StringProperty("")

    inv_detail_idx = NumericProperty(-1)

    eq_detail_fighter = NumericProperty(-1)

    eq_detail_slot = StringProperty("")

    lbl_top_title = StringProperty("")

    _preview_item = None

    _pending_state = None

    _enchant_source = None

    _enchant_idx = None

    _enchant_item = None

    _enchant_fighter = None

    _scroll_positions = {}  # key → scroll_y

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

    def on_enter(self):
        # _entry_depth is set by _navigate_to_forge for cross-screen entry.
        # For NavBar or back-navigation entry, reset to 0.
        if not getattr(self, '_cross_screen_pending', False):
            self._entry_depth = 0
        self._cross_screen_pending = False
        self._apply_pending_state()

    def refresh_forge(self):
        engine = App.get_running_app().engine
        self._update_top_bar()
        # Defensive: on_view_state only fires when view_state *changes*,
        # so if we re-enter forge while view_state is still what it was
        # last time, the derived Kivy flags (_forge_rv_active etc.) may
        # be out of sync with what the KV bindings expect. Re-apply the
        # flag tuple from _VIEW_FLAGS unconditionally here — it's an O(6)
        # attr set, and it fixes the "empty forge on re-entry" case where
        # the RV was hidden from a stale shop_preview / inventory visit.
        flags = _VIEW_FLAGS.get(self.view_state)
        if flags is not None:
            (self.show_inventory, self._forge_rv_active,
             self._inventory_rv_active, self._show_inv_tabs,
             self.weapon_upgrade_active, self.enchant_active) = flags
        # Title: inventory view label when we're anywhere under the inventory
        # branch, forge label for shop/shop_preview.
        in_inventory = self.view_state in (
            "inventory_list", "inventory_detail", "equipped_detail",
            "upgrade", "enchant",
        )
        self.lbl_top_title = t("inventory_label") if in_inventory else t("title_anvil")
        # Shard display
        s = engine.shards
        self.shard_text = f"I:{s.get(1,0)} II:{s.get(2,0)} III:{s.get(3,0)} IV:{s.get(4,0)} V:{s.get(5,0)}"
        if in_inventory:
            if self.view_state in ("upgrade", "enchant"):
                # Detail screen owns the render pass; don't redraw over it.
                return
            if self.view_state == "inventory_detail":
                self._show_inv_detail(self.inv_detail_idx)
            elif self.view_state == "equipped_detail":
                f = engine.fighters[self.eq_detail_fighter]
                item = f.equipment.get(self.eq_detail_slot)
                if item:
                    self._show_equipped_detail(self.eq_detail_fighter, item)
                else:
                    # Equipped item vanished — fall back to the list.
                    self.eq_detail_fighter = -1
                    self.eq_detail_slot = ""
                    self._set_view("inventory_list")
                    self._refresh_inventory_grid()
            else:  # inventory_list
                self._refresh_inventory_grid()
            return
        if self._preview_item is not None:
            self._set_view("shop_preview")
            self._show_shop_preview(self._preview_item)
            return
        # Shop mode
        self._set_view("shop")
        self._inv_tabs_key = None  # clear inventory tabs key
        tabs_box = self.ids.get("inv_tabs_box")
        tabs_key = ("shop", self.forge_tab, self.shop_rarity_filter, self.shop_sort)
        if tabs_box and self._needs_rebuild(self, '_shop_tabs_key', tabs_key):
            tabs_box.clear_widgets()
            rarity_tabs = [(r, t(k)) for r, k in [
                ("all", "filter_all"), ("common", "filter_common"),
                ("uncommon", "filter_uncommon"), ("rare", "filter_rare"),
                ("epic", "filter_epic"), ("legendary", "filter_legendary"),
            ]]
            tabs_box.add_widget(build_tab_row(
                rarity_tabs, self.shop_rarity_filter, self.set_shop_rarity_filter,
                active_color=ACCENT_GOLD, height=dp(30),
            ))
            sort_icon = "icons/ic_down.png" if self.shop_sort == "best" else "icons/ic_up.png"
            sort_label = t("sort_best") if self.shop_sort == "best" else t("sort_worst")
            sort_btn = MinimalButton(
                text=sort_label, font_size=11,
                btn_color=ACCENT_BROWN, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(30),
                icon_source=sort_icon,
            )
            sort_btn.bind(on_press=self.toggle_shop_sort)
            tabs_box.add_widget(sort_btn)
        all_items = engine.get_forge_items()
        self.forge_items = [i for i in all_items if i["slot"] == self.forge_tab]
        if self.shop_rarity_filter != "all":
            self.forge_items = [i for i in self.forge_items if i.get("rarity") == self.shop_rarity_filter]
        reverse = self.shop_sort == "best"
        self.forge_items.sort(key=self._item_total_stats, reverse=reverse)
        inv_count = len(engine.inventory)
        self.inventory_btn_text = t("inventory_count", n=inv_count) if inv_count > 0 else t("inventory_label")
        # view_state already "shop" — derived flags set by on_view_state.
        refresh_forge_grid(self)

    def on_back_pressed(self):
        depth = getattr(self, '_entry_depth', 0)
        state = self.view_state
        # Level 0: enchant view → back to item detail
        if state == "enchant":
            self._close_enchant_view()
            return True
        # Level 1: item upgrade → back to item detail
        if state == "upgrade":
            # Return to whichever detail spawned the upgrade screen
            if self.inv_detail_idx >= 0:
                self._set_view("inventory_detail")
            elif self.eq_detail_fighter >= 0:
                self._set_view("equipped_detail")
            else:
                self._set_view("inventory_list")
            self.refresh_forge()
            return True
        # Level 2: item detail or equipped detail
        if state in ("inventory_detail", "equipped_detail"):
            if depth == 2:
                self._reset_forge_state()
                return False  # exit to previous screen
            self._close_inv_detail()
            return True
        # Level 3: shop preview
        if self._preview_item is not None:
            if depth == 3:
                self._reset_forge_state()
                return False
            self._close_shop_preview()
            return True
        # Level 4: inventory view
        if self.show_inventory:
            if depth == 4:
                self._reset_forge_state()
                return False
            self.toggle_inventory()
            return True
        # Level 5: shop view — let go_back() handle via history
        return False

    _TARGET_LABELS = {"atk": "ATK", "def": "DEF", "hp": "HP"}
