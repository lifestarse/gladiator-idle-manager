# Build: 39
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.metrics import dp, sp
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard, FloatingText
import game.models as _m
from game.models import (
    fmt_num, RARITY_COLORS,
    get_upgrade_tier, item_display_name,
    get_max_upgrade, RARITY_MAX_UPGRADE,
)
from game.slots import SLOTS
from game.theme import *
from game.theme import popup_color
from game.constants import (
    UPGRADE_BONUS_PER_LEVEL, RELIC_STAT_SPLIT, ACCESSORY_HP_MULT,
)
from game.localization import t
from game.ui_helpers import (
    _batch_fill_grid,
    refresh_forge_grid,
    build_item_info_card, build_tab_row,
    bind_text_wrap,
)
from game.screens.shared import _safe_clear, _safe_rebind

BC = BaseCard  # short alias used in _build_upgrade_comparison_card


# ---- View state machine ----------------------------------------------------
# The forge used to have six independent BooleanProperty flags that could
# contradict each other (e.g. both weapon_upgrade_active AND enchant_active
# True). `view_state` is now the single source of truth; the six flags below
# are derived output kept in sync by `on_view_state` for KV-binding compat.
#
# Allowed transitions (enforced by _set_view via the transition map):
#   shop            <-> shop_preview, inventory_list
#   inventory_list  <-> shop, inventory_detail, equipped_detail
#   inventory_detail -> inventory_list, upgrade, enchant
#   equipped_detail  -> inventory_list, upgrade, enchant
#   upgrade         -> inventory_detail, equipped_detail
#   enchant         -> inventory_detail, equipped_detail
VIEW_STATES = (
    "shop", "shop_preview",
    "inventory_list", "inventory_detail", "equipped_detail",
    "upgrade", "enchant",
)

# Flag tuple order: (show_inventory, _forge_rv_active, _inventory_rv_active,
#                    _show_inv_tabs, weapon_upgrade_active, enchant_active)
_VIEW_FLAGS = {
    "shop":             (False, True,  False, True,  False, False),
    "shop_preview":     (False, False, False, False, False, False),
    "inventory_list":   (True,  False, True,  True,  False, False),
    "inventory_detail": (True,  False, False, False, False, False),
    "equipped_detail":  (True,  False, False, False, False, False),
    "upgrade":          (True,  False, False, False, True,  False),
    "enchant":          (True,  False, False, False, False, True),
}


class ForgeScreen(BaseScreen):
    forge_items = ListProperty()
    # One-true-state: written via `_set_view` / `self.view_state = "..."`.
    view_state = StringProperty("shop")
    # --- Derived flags (driven by on_view_state). Read-only for outside code;
    #     KV bindings unchanged so templates keep working. ---
    show_inventory = BooleanProperty(False)
    _forge_rv_active = BooleanProperty(False)
    _inventory_rv_active = BooleanProperty(False)
    _show_inv_tabs = BooleanProperty(False)
    weapon_upgrade_active = BooleanProperty(False)
    enchant_active = BooleanProperty(False)
    # --- Independent payload/filter state (not part of the view machine) ---
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

    _preview_item = None
    _pending_state = None
    _enchant_source = None

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

    def set_forge_tab(self, tab):
        self._save_scroll()
        self._reset_forge_state()
        self.forge_tab = tab
        self.refresh_forge()
        self._restore_scroll()

    def toggle_inventory(self):
        self._save_scroll()
        was_inv = self.show_inventory
        # _reset_forge_state resets to "shop"; if we were in shop, flip to inv.
        self._reset_forge_state(keep_inventory=not was_inv)
        self.forge_tab = "weapon"
        self.refresh_forge()
        self._restore_scroll()

    def set_inventory_tab(self, tab):
        self._save_scroll()
        self.inventory_tab = tab
        self._inv_grid_key = None
        self._shard_grid_key = None
        self.refresh_forge()
        self._restore_scroll()

    def set_rarity_filter(self, rarity):
        self._save_scroll()
        self.inventory_rarity_filter = rarity
        self._inv_grid_key = None
        self.refresh_forge()
        self._restore_scroll()

    def set_equip_filter(self, value):
        self._save_scroll()
        self.inventory_equip_filter = value
        self._inv_grid_key = None
        self.refresh_forge()
        self._restore_scroll()

    def set_shop_rarity_filter(self, rarity):
        self._save_scroll()
        self.shop_rarity_filter = rarity
        self.refresh_forge()
        self._restore_scroll()

    def toggle_shop_sort(self, *a):
        self.shop_sort = "worst" if self.shop_sort == "best" else "best"
        self.refresh_forge()

    def toggle_inventory_sort(self, *a):
        self.inventory_sort = "worst" if self.inventory_sort == "best" else "best"
        self._inv_grid_key = None
        self.refresh_forge()

    @staticmethod
    def _item_total_stats(item):
        """Composite 'power' score used for best/worst sort.

        Returned as a tuple so Python sorts lexicographically:

          1. enchantment flag — ANY enchanted item outranks ANY
             unenchanted one (user request: enchantment beats +25).
          2. power score — base stats × upgrade multiplier,
             capturing the 20%-per-level upgrade mechanic so two
             identical Abyssal Tridents rank +5 > +4 > +2.

        Within each (enchanted / unenchanted) group, higher power wins.
        """
        base = item.get("str", 0) + item.get("agi", 0) + item.get("vit", 0)
        lvl = item.get("upgrade_level", 0)
        power = base * (1 + lvl * 0.2)
        has_ench = 1 if item.get("enchantment") else 0
        return (has_ench, power)

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

    @staticmethod
    def _build_description_card(item):
        """Return a BaseCard with item description text, or None if no description."""
        from kivy.uix.label import Label
        desc = item.get("description", "")
        if not desc:
            return None
        pad = dp(12)
        card = BC(orientation="vertical", size_hint_y=None, height=dp(50),
                  padding=[pad, dp(8)])
        lbl = Label(
            text=desc, font_size="11sp", color=TEXT_MUTED,
            halign="left", valign="top",
            size_hint_y=None,
        )
        lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
        lbl.bind(height=lambda inst, h: setattr(card, "height", h + dp(16)))
        card.add_widget(lbl)
        return card

    def _item_slot_subtitle(self, item):
        """Return the '[SLOT] [RARITY] (max +N)' subtitle, or None if not equipment."""
        slot = item.get("slot", "?")
        if slot not in SLOTS:
            return None
        rarity = item.get("rarity", "common")
        max_upg = get_max_upgrade(item)
        return (f"{t(SLOTS[slot].label_keys['upper'])} "
                f"[{t('rarity_' + rarity + '_upper')}] "
                f"{t('item_max_upgrade', n=max_upg)}")

    def _show_inv_detail(self, inv_idx):
        """Show detail view for a single inventory item."""
        self._enter_detail_mode()
        self.inv_detail_idx = inv_idx
        self._set_view("inventory_detail")
        sv = self.ids.get("forge_scroll")
        if sv:
            sv.scroll_y = 1
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        engine = App.get_running_app().engine

        if inv_idx < 0 or inv_idx >= len(engine.inventory):
            self.inv_detail_idx = -1
            self._set_view("inventory_list")
            self._refresh_inventory_grid()
            return

        item = engine.inventory[inv_idx]
        slot = item.get("slot", "?")
        slot_def = SLOTS.get(slot)
        sub = self._item_slot_subtitle(item)

        # Info card
        grid.add_widget(build_item_info_card(item, subtitle=sub))
        desc_card = self._build_description_card(item)
        if desc_card:
            grid.add_widget(desc_card)

        # Action buttons row: Sell + Equip
        action_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8),
                               padding=[0, dp(4)])
        sell_price = item.get("cost", 0) // 2
        sell_btn = MinimalButton(
            text=t("sell_btn", price=fmt_num(sell_price)), font_size=11,
            btn_color=ACCENT_GOLD, text_color=BG_DARK,
            icon_source="sprites/icons/ic_gold.png",
        )
        def _sell(*a, idx=inv_idx):
            engine.sell_inventory_item(idx)
            self.inv_detail_idx = -1
            self._set_view("inventory_list")
            self.refresh_forge()
        sell_btn.bind(on_press=_sell)
        action_row.add_widget(sell_btn)

        equip_btn = MinimalButton(
            text=t("equip_btn"), font_size=11,
            btn_color=ACCENT_GREEN, text_color=BG_DARK,
        )
        equip_btn.bind(on_press=lambda *a: self._show_equip_fighter_popup(inv_idx, item))
        action_row.add_widget(equip_btn)
        grid.add_widget(action_row)

        # Upgradable items: IMPROVE button (any equipment slot is upgradable)
        if slot_def is not None:
            improve_btn = MinimalButton(
                text=t("improve_btn"), font_size=11,
                btn_color=ACCENT_BLUE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            improve_btn.bind(on_press=lambda *a: self._show_item_upgrade("inv", inv_idx, item, None))
            grid.add_widget(improve_btn)

        # Enchant button (per slot registry)
        if slot_def is not None and slot_def.can_enchant:
            enchant_btn = MinimalButton(
                text=t("tab_enchant"), font_size=11,
                btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            enchant_btn.bind(on_press=lambda *a: self._show_enchant_view("inv", inv_idx, item, None))
            grid.add_widget(enchant_btn)

    def _show_shop_preview(self, item):
        """Show read-only detail view for a shop item (no sell/equip/improve)."""
        self._enter_detail_mode()
        # view_state set to "shop_preview" by refresh_forge caller
        sv = self.ids.get("forge_scroll")
        if sv:
            sv.scroll_y = 1
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        sub = self._item_slot_subtitle(item)

        grid.add_widget(build_item_info_card(item, subtitle=sub))
        desc_card = self._build_description_card(item)
        if desc_card:
            grid.add_widget(desc_card)


    def _close_shop_preview(self):
        self._preview_item = None
        self.refresh_forge()

    def _close_inv_detail(self):
        self.inv_detail_idx = -1
        self.eq_detail_fighter = -1
        self.eq_detail_slot = ""
        self._enchant_source = None
        self._enchant_idx = None
        self._enchant_item = None
        self._enchant_fighter = None
        self._inv_grid_key = None
        self._shard_grid_key = None
        self._inv_tabs_key = None
        self._inv_card_cache = {}
        self._set_view("inventory_list")
        self.refresh_forge()

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

    @staticmethod
    def _fighter_target_total(fighter, target):
        """Current totalized final stat on fighter for a given target."""
        if target == "atk":
            return fighter.attack
        if target == "def":
            return fighter.defense
        if target == "hp":
            return fighter.max_hp
        return 0

    @staticmethod
    def _fighter_pool_value(fighter, stat_names):
        """Sum total_<stat> from fighter for a tuple of stat names."""
        m = {"str": fighter.total_strength,
             "agi": fighter.total_agility,
             "vit": fighter.total_vitality}
        return sum(m[s] for s in stat_names)

    def _build_upgrade_comparison_card(self, item, fighter, engine):
        """Build the stat-comparison BaseCard for an upgrade screen.

        Driven entirely by the SlotDef registry — per-slot branching collapses
        into a loop over slot.upgrade_targets.
        """
        slot_id = item.get("slot", "weapon")
        slot_def = SLOTS.get(slot_id)
        if slot_def is None:
            # Non-equipment fallback (shouldn't reach the upgrade screen, but
            # leave a safe path in case data drifts).
            slot_def = SLOTS["weapon"]

        is_relic = (slot_id == "relic")
        rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
        current_lvl = item.get("upgrade_level", 0)
        max_lvl = get_max_upgrade(item)

        num_rows = (12 if is_relic else 8) if fighter else 5
        comp_card = BC(
            orientation="vertical", size_hint_y=None, height=dp(30 + num_rows * 24),
            padding=[dp(12), dp(8)], spacing=dp(2),
        )
        comp_card.border_color = rcolor
        comp_card.add_label(item_display_name(item), font_size=sp(11), bold=True,
                            color=rcolor, halign="center", size_hint_y=0.15)

        def _info_row(label, value, color=TEXT_SECONDARY):
            return comp_card.add_text_row(
                (label, sp(6), False, TEXT_MUTED, 0.5),
                (str(value), sp(7), True, color, 0.5),
                height=dp(30),
            )

        def _pool_display(stat_names):
            return "+".join(s.upper() for s in stat_names)

        def _breakdown(pct, label_prefix):
            # No fighter context → compact summary describing the formula.
            if not fighter:
                for target in slot_def.upgrade_targets:
                    pool = slot_def.pool_for(target)
                    mult = slot_def.mult_for(target)
                    mult_s = f"x{int(mult)}" if mult != 1.0 else ""
                    div_s = f"/{slot_def.split_divisor}" if slot_def.split_divisor > 1 else ""
                    target_label = self._TARGET_LABELS.get(target, target.upper())
                    if is_relic:
                        # Compact single-line summary for relics (they list all 3).
                        _info_row(
                            f"{label_prefix} {t('bonus_label')}",
                            f"{pct}%{div_s} → ATK+DEF+HP",
                            ACCENT_GREEN,
                        )
                        return
                    _info_row(
                        f"{label_prefix} {t('bonus_label')}",
                        f"{pct}% ({_pool_display(pool)}){mult_s} → {target_label}",
                        ACCENT_GREEN,
                    )
                return

            # Fighter context → show pool value, computed bonus, running total.
            for target in slot_def.upgrade_targets:
                pool = slot_def.pool_for(target)
                mult = slot_def.mult_for(target)
                pair_val = self._fighter_pool_value(fighter, pool)
                bonus = int(pair_val * pct / 100 * mult) // slot_def.split_divisor
                mult_s = f" x{int(mult)}" if mult != 1.0 else ""
                div_s = f"/{slot_def.split_divisor}" if slot_def.split_divisor > 1 else ""
                target_label = self._TARGET_LABELS.get(target, target.upper())
                if is_relic:
                    _info_row(
                        f"{label_prefix} {target_label} ({pct}%{div_s})",
                        f"+{bonus}",
                        ACCENT_GREEN,
                    )
                else:
                    _info_row(
                        f"{label_prefix} ({pct}% {_pool_display(pool)}{mult_s})",
                        f"+{bonus} {target_label}",
                        ACCENT_GREEN,
                    )
                    _info_row(
                        f"{t('total_label')} {target_label}",
                        self._fighter_target_total(fighter, target),
                        ACCENT_GOLD,
                    )

        # Context rows above the breakdown.
        if fighter and slot_id == "weapon":
            _info_row(f"STR ({fighter.total_strength}) x2", fighter.total_strength * 2, ACCENT_RED)
            _info_row("STR+AGI", f"{fighter.total_strength}+{fighter.total_agility}={fighter.total_strength + fighter.total_agility}", TEXT_SECONDARY)
        elif fighter and slot_id == "armor":
            _info_row("AGI+VIT", f"{fighter.total_agility}+{fighter.total_vitality}={fighter.total_agility + fighter.total_vitality}", TEXT_SECONDARY)
        elif fighter and slot_id == "accessory":
            _info_row("VIT+STR", f"{fighter.total_vitality}+{fighter.total_strength}={fighter.total_vitality + fighter.total_strength}", TEXT_SECONDARY)

        base_label_key = slot_def.label_keys.get("base", "")
        base_label = t(base_label_key) if base_label_key else ""
        if is_relic:
            # Relics provide STR/AGI/VIT (not flat ATK/DEF/HP). These feed into
            # all three final stats via the upgrade formulas.
            _info_row(t("relic_base"),
                      f"STR+{item.get('str',0)} AGI+{item.get('agi',0)} VIT+{item.get('vit',0)}",
                      TEXT_PRIMARY)
        else:
            # Non-relic items have a primary stat matching their target.
            # weapon→STR, armor→AGI, accessory→VIT
            primary_stat_map = {"weapon": "str", "armor": "agi", "accessory": "vit"}
            base_val = item.get(primary_stat_map.get(slot_id, "str"), 0)
            _info_row(base_label, f"+{base_val}", TEXT_PRIMARY)
        _breakdown(current_lvl * UPGRADE_BONUS_PER_LEVEL, f"+{current_lvl}")

        if current_lvl < max_lvl:
            next_lvl = current_lvl + 1
            comp_card.add_widget(AutoShrinkLabel(
                text=f"--- +{next_lvl} ---", font_size="11sp",
                color=ACCENT_GOLD, halign="center", size_hint_y=None, height=dp(30),
            ))
            _breakdown(next_lvl * UPGRADE_BONUS_PER_LEVEL, f"+{next_lvl}")
            tier, count = get_upgrade_tier(next_lvl)
            count *= slot_def.shard_multiplier
            have = engine.shards.get(tier, 0)
            cost_text = f"{count}x {t('shard_tier_' + str(tier) + '_name')}"
            _info_row(t("cost_label"),
                      f"{cost_text} ({t('have_label')}: {have})",
                      ACCENT_GREEN if have >= count else ACCENT_RED)
        else:
            comp_card.add_widget(AutoShrinkLabel(
                text=f"MAX +{max_lvl}", font_size="11sp", bold=True,
                color=ACCENT_GOLD, halign="center", size_hint_y=None, height=dp(30),
            ))
        return comp_card

    @staticmethod
    def _get_enchant_display_name(ench_id):
        loc_key = f"enchant_{ench_id}"
        name = t(loc_key)
        if name == loc_key:
            ench_data = _m.ENCHANTMENT_TYPES.get(ench_id, {})
            name = ench_data.get("name", ench_id.replace("_", " ").title())
        return name

    def _show_enchant_view(self, source, idx, item, fighter=None):
        """Separate enchantment tab for a weapon item."""
        from kivy.uix.label import Label
        self._enter_detail_mode()
        self._set_view("enchant")
        self._enchant_source = source
        self._enchant_idx = idx
        self._enchant_item = item
        self._enchant_fighter = fighter
        sv = self.ids.get("forge_scroll")
        if sv:
            sv.scroll_y = 1
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        engine = App.get_running_app().engine

        # Title
        grid.add_widget(AutoShrinkLabel(
            text=t("enchant_label"), font_size="11sp", bold=True,
            color=ACCENT_PURPLE, halign="center",
            size_hint_y=None, height=dp(34),
        ))

        # Current enchantment status
        current_ench = item.get("enchantment")
        if current_ench:
            status_text = t("current_enchant", name=self._get_enchant_display_name(current_ench))
        else:
            status_text = t("no_enchant")
        grid.add_widget(AutoShrinkLabel(
            text=status_text, font_size="10sp",
            color=ACCENT_GOLD if current_ench else TEXT_MUTED,
            halign="center", size_hint_y=None, height=dp(26),
        ))

        # Enchantment cards
        pad = dp(12)
        for ench_id, ench_data in _m.ENCHANTMENT_TYPES.items():
            is_current = (current_ench == ench_id)
            gold_cost = ench_data.get("cost_gold", 0)
            sh_tier = ench_data.get("cost_shard_tier", 5)
            sh_count = ench_data.get("cost_shard_count", 100)
            can_afford = engine.gold >= gold_cost and engine.shards.get(sh_tier, 0) >= sh_count
            ench_name = self._get_enchant_display_name(ench_id)

            card = BC(orientation="vertical", size_hint_y=None, height=dp(130),
                      padding=[pad, dp(8)], spacing=dp(4))
            if is_current:
                card.border_color = ACCENT_GOLD
            else:
                card.border_color = ACCENT_PURPLE

            # Name row
            name_text = f"{ench_name}  [OK]" if is_current else ench_name
            name_color = ACCENT_GOLD if is_current else ACCENT_PURPLE
            ench_name_lbl = AutoShrinkLabel(
                text=name_text, font_size="10sp", bold=True,
                color=name_color, halign="left",
                size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(ench_name_lbl)
            card.add_widget(ench_name_lbl)

            # Description (localized via enchant_desc_<id>; fallback to JSON)
            loc_desc_key = f"enchant_desc_{ench_id}"
            desc = t(loc_desc_key)
            if desc == loc_desc_key:
                desc = ench_data.get("description", "")
            if desc:
                desc_lbl = Label(
                    text=desc, font_size="11sp", font_name='PixelFont', color=TEXT_MUTED,
                    halign="left", valign="top",
                    size_hint_y=None,
                )
                desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - pad * 2, None)))
                desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
                def _update_card_h(inst, h, c=card):
                    c.height = max(dp(130), h + dp(90))
                desc_lbl.bind(height=_update_card_h)
                card.add_widget(desc_lbl)

            # Cost line
            cost_str = f"{fmt_num(gold_cost)}g + {sh_count}x {t('shard_name_' + str(sh_tier))}"
            cost_color = ACCENT_GREEN if can_afford else ACCENT_RED
            ench_cost_lbl = AutoShrinkLabel(
                text=cost_str, font_size="11sp",
                color=cost_color, halign="left",
                size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(ench_cost_lbl)
            card.add_widget(ench_cost_lbl)

            # Apply button
            if is_current:
                btn_color = ACCENT_GOLD
                btn_text_color = BG_DARK
                btn_text = f"{ench_name} [OK]"
            elif can_afford:
                btn_color = ACCENT_PURPLE
                btn_text_color = TEXT_PRIMARY
                btn_text = t("tab_enchant")
            else:
                btn_color = BTN_DISABLED
                btn_text_color = TEXT_MUTED
                btn_text = t("tab_enchant")
            apply_btn = MinimalButton(
                text=btn_text, font_size=11,
                btn_color=btn_color, text_color=btn_text_color,
                size_hint_y=None, height=dp(36),
            )
            def _do_enchant(inst, w=item, eid=ench_id, s=source, i=idx, f=fighter):
                result = engine.enchant_weapon(w, eid)
                if result.ok:
                    self._show_enchant_view(s, i, w, f)
                else:
                    App.get_running_app().show_toast(result.message)
            apply_btn.bind(on_press=_do_enchant)
            card.add_widget(apply_btn)

            grid.add_widget(card)


    def _close_enchant_view(self):
        """Close enchantment view and return to item detail."""
        # _set_view will be called by the detail show method we re-enter.
        source = self._enchant_source or "inv"
        idx = self._enchant_idx if self._enchant_idx is not None else -1
        item = self._enchant_item
        if source == "inv":
            self._show_inv_detail(idx)
        else:
            self._show_equipped_detail(idx, item)

    def _show_item_upgrade(self, source, idx, item, fighter=None):
        """Universal upgrade screen for any equipment slot."""
        self._enter_detail_mode()
        self._set_view("upgrade")
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        engine = App.get_running_app().engine
        slot_id = item.get("slot", "weapon")
        slot_def = SLOTS.get(slot_id)
        current_lvl = item.get("upgrade_level", 0)
        max_lvl = get_max_upgrade(item)

        grid.add_widget(self._build_upgrade_comparison_card(item, fighter, engine))

        if current_lvl < max_lvl:
            tier, count = get_upgrade_tier(current_lvl + 1)
            if slot_def is not None:
                count *= slot_def.shard_multiplier
            have = engine.shards.get(tier, 0)
            can_upgrade = have >= count
            upg_btn = MinimalButton(
                text=f"{t('upgrade_btn')} +{current_lvl + 1}", font_size=11,
                btn_color=ACCENT_GREEN if can_upgrade else BTN_DISABLED,
                text_color=BG_DARK if can_upgrade else TEXT_MUTED,
                size_hint_y=None, height=dp(46),
            )
            def _do_upgrade(inst, w=item, s=source, i=idx, f=fighter):
                result = engine.upgrade_item(w)
                if result.ok:
                    self._sparkle_effect(inst)
                    self._show_item_upgrade(s, i, w, f)
                else:
                    App.get_running_app().show_toast(result.message)
            upg_btn.bind(on_press=_do_upgrade)
            grid.add_widget(upg_btn)

    def _show_equipped_detail(self, fighter_idx, item):
        """Detail view for an item currently equipped on a fighter."""
        self._enter_detail_mode()
        self.eq_detail_fighter = fighter_idx
        self.eq_detail_slot = item.get("slot", "")
        self._set_view("equipped_detail")
        sv = self.ids.get("forge_scroll")
        if sv:
            sv.scroll_y = 1
        self.eq_detail_slot = item.get("slot", "")
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        engine = App.get_running_app().engine
        f = engine.fighters[fighter_idx]
        slot = item.get("slot", "?")
        max_upg = get_max_upgrade(item)
        # Info card
        grid.add_widget(build_item_info_card(item, fighter=f, equipped_on=f.name))
        desc_card = self._build_description_card(item)
        if desc_card:
            grid.add_widget(desc_card)

        # Unequip button
        slot = item.get("slot", "weapon")
        unequip_btn = MinimalButton(
            text=t("unequip_btn"), font_size=11,
            btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(44),
        )
        def _unequip(*a, s=slot, fi=fighter_idx):
            result = engine.unequip_from_fighter(fi, s)
            if not result.ok:
                App.get_running_app().show_toast(result.message or t("not_in_battle"))
                return
            # Stay on forge — show item in inventory now
            self.eq_detail_fighter = -1
            self.eq_detail_slot = ""
            # Find item in inventory to show its detail
            inv = engine.inventory
            found_idx = -1
            for idx, it in enumerate(inv):
                if it.get("name") == item.get("name") and it.get("slot") == s:
                    found_idx = idx
                    break
            if found_idx >= 0:
                self.inv_detail_idx = found_idx
                self._set_view("inventory_detail")
            else:
                self._set_view("inventory_list")
            self.refresh_forge()
        unequip_btn.bind(on_press=_unequip)
        grid.add_widget(unequip_btn)

        slot_def = SLOTS.get(slot)
        # Upgradable items: IMPROVE button (any equipment slot)
        if slot_def is not None:
            improve_btn = MinimalButton(
                text=t("improve_btn"), font_size=11,
                btn_color=ACCENT_BLUE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            improve_btn.bind(on_press=lambda *a: self._show_item_upgrade("equip", fighter_idx, item, f))
            grid.add_widget(improve_btn)

        # Enchant button — slot registry decides eligibility
        if slot_def is not None and slot_def.can_enchant:
            enchant_btn = MinimalButton(
                text=t("tab_enchant"), font_size=11,
                btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            enchant_btn.bind(on_press=lambda *a: self._show_enchant_view("equip", fighter_idx, item, f))
            grid.add_widget(enchant_btn)

    def _show_equip_fighter_popup(self, inv_idx, item):
        """Pick a fighter to equip `item` on.

        Two fast paths bypass the popup entirely:
          1. `app.pending_equip_target_idx` is set — user navigated here
             from an empty slot on a specific fighter's Squad page. We
             equip on that fighter AND navigate back to their Squad detail
             so Back behaves naturally ("fill slot → see fighter with the
             new item"). If they wanted to keep browsing inventory, they
             would have opened the forge directly rather than tapping an
             empty slot.
          2. Roster has only one available fighter — the picker has one
             option anyway. Stay in the forge inventory in this case,
             user explicitly came through the forge.

        Otherwise build a TouchRecycleView inside the popup so 1000-fighter
        rosters open instantly (was 1-2 s for 1000 MinimalButtons).
        """
        from kivy.uix.recyclelayout import RecycleLayout  # noqa: F401  (viewclass reg)
        from kivy.uix.recycleboxlayout import RecycleBoxLayout
        from game.widgets import TouchRecycleView
        from game.ui_helpers import _equip_choice_callbacks, FighterEquipChoiceView  # noqa: F401
        from kivy.metrics import dp as _dp

        app = App.get_running_app()
        engine = app.engine
        alive = [(i, f) for i, f in enumerate(engine.fighters) if f.available]
        if not alive:
            app.show_toast(t("no_fighters"))
            return

        # Fast path 1: user came from an empty-slot tap on Squad.
        pending = getattr(app, 'pending_equip_target_idx', -1)
        app.pending_equip_target_idx = -1  # one-shot, always clear
        if 0 <= pending < len(engine.fighters):
            target = engine.fighters[pending]
            if target.available:
                self._equip_and_return_to_roster(pending, inv_idx)
                return

        # Fast path 2: single fighter — no picker needed.
        if len(alive) == 1:
            self._equip_and_refresh(alive[0][0], inv_idx)
            return

        # Build the picker via RecycleView — only visible rows materialize.
        popup_box = BoxLayout(orientation="vertical", spacing=dp(4),
                              padding=dp(8))
        rv = TouchRecycleView(
            viewclass='FighterEquipChoiceView',
            bar_width=2, bar_color=TEXT_MUTED,
            do_scroll_x=False, scroll_type=['bars', 'content'],
            scroll_distance=_dp(8), scroll_timeout=50,
        )
        rbl = RecycleBoxLayout(
            default_size=(None, _dp(50)),
            default_size_hint=(1, None),
            size_hint_y=None, orientation='vertical',
            spacing=_dp(4), padding=[_dp(4), _dp(4)],
        )
        rbl.bind(minimum_height=rbl.setter('height'))
        rv.add_widget(rbl)
        slot = item.get("slot", "weapon")
        rv.data = [
            {
                'fi': fi,
                'text': f"{f.name}  [{(f.equipment.get(slot) or {}).get('name', '—')}]",
            }
            for fi, f in alive
        ]
        popup_box.add_widget(rv)

        # Clamp popup to screen — for big rosters it doesn't blow past the
        # top/bottom of the window.
        from kivy.core.window import Window
        rows_h = dp(50 + 4) * min(len(alive), 10)
        popup_h = min(Window.height * 0.85, dp(80) + rows_h)
        popup = Popup(
            title=f"{t('equip_btn')}: {item_display_name(item)}",
            title_color=popup_color(ACCENT_GOLD),
            title_size=sp(11),
            content=popup_box,
            size_hint=(0.85, None),
            height=popup_h,
            background_color=popup_color(BG_CARD),
            separator_color=popup_color(ACCENT_GOLD),
            auto_dismiss=True,
        )

        # Wire the picker callback once per popup-open.
        def _pick(fidx):
            if engine.battle_active:
                app.show_toast(t("not_in_battle"))
                return
            popup.dismiss()
            self._equip_and_refresh(fidx, inv_idx)
        _equip_choice_callbacks['pick'] = _pick
        popup.open()

    def _equip_and_refresh(self, fighter_idx, inv_idx):
        """Equip the inventory item onto a specific fighter + refresh view."""
        engine = App.get_running_app().engine
        if engine.battle_active:
            App.get_running_app().show_toast(t("not_in_battle"))
            return
        engine.equip_from_inventory(fighter_idx, inv_idx)
        self.inv_detail_idx = -1
        self._set_view("inventory_list")
        self.refresh_forge()

    def _equip_and_return_to_roster(self, fighter_idx, inv_idx):
        """Equip and navigate back to the fighter's Squad detail.

        Used for the empty-slot → inventory → equip flow. The user started
        on Squad; going forward to the forge pushed ("roster", ...) onto
        the nav history, then coming back to Roster would normally push
        ("forge", ...) on top — so Back would take the user INTO the forge
        instead of to the roster list.

        Fix: treat this as a Back action rather than forward navigation.
        Pop the stale ("roster", ...) frame that's already on top of the
        history (that's where we came from), and set _going_back so the
        upcoming screen change doesn't append a new frame. Net result:
        one Back from the Squad detail unwinds to whatever was before the
        user entered roster — exactly what a user who'd pressed Back from
        Forge → Roster detail would expect.
        """
        app = App.get_running_app()
        engine = app.engine
        if engine.battle_active:
            app.show_toast(t("not_in_battle"))
            return
        engine.equip_from_inventory(fighter_idx, inv_idx)
        # Reset forge UI state so when user enters the forge later they
        # land on the shop, not on a stale inventory-detail view.
        self.inv_detail_idx = -1
        self._set_view("shop")

        # Nav-history cleanup: drop the ("roster", ...) frame we pushed
        # when entering the forge, and mark the incoming screen change as
        # a back-step so it doesn't push ("forge", ...).
        history = getattr(app, '_nav_history', None)
        if history and history[-1][0] == "roster":
            history.pop()
        app._going_back = True

        roster = app.sm.get_screen("roster")
        # `_return_to_list` tells Roster.on_enter that Back should unwind
        # to the roster list (not to whatever is below Roster in nav
        # history). Without this, Back from the fighter detail skips over
        # the list and lands on Arena/Pit.
        roster._pending_state = {
            'detail_index': fighter_idx,
            '_return_to_list': True,
        }
        app.sm.current = "roster"

    def buy(self, item_id):
        app = App.get_running_app()
        result = app.engine.buy_forge_item(item_id)
        if result.message:
            app.show_toast(result.message)
        self.refresh_forge()
