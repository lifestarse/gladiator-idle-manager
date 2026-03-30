# Build: 18
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.metrics import dp, sp
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard
import game.models as _m
from game.models import (
    fmt_num, RARITY_COLORS,
    get_upgrade_tier, item_display_name,
    get_max_upgrade, RARITY_MAX_UPGRADE,
)
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


class ForgeScreen(BaseScreen):
    forge_items = ListProperty()
    show_inventory = BooleanProperty(False)
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
    weapon_upgrade_active = BooleanProperty(False)
    enchant_active = BooleanProperty(False)
    lbl_top_title = StringProperty("")
    _show_inv_tabs = BooleanProperty(False)

    _preview_item = None
    _nav_from = StringProperty("")
    _nav_back_fighter_idx = -1
    _enchant_source = None
    _enchant_idx = None
    _enchant_item = None
    _enchant_fighter = None
    _scroll_positions = {}  # key → scroll_y

    def on_enter(self):
        self._reset_forge_state()
        self._scroll_positions = {}
        self.refresh_forge()

    def _reset_forge_state(self, keep_inventory=False):
        """Reset all navigation/detail state. Call on enter or back navigation."""
        if not keep_inventory:
            self.show_inventory = False
        self.inv_detail_idx = -1
        self.eq_detail_fighter = -1
        self.eq_detail_slot = ""
        self.weapon_upgrade_active = False
        self.enchant_active = False
        self._enchant_source = None
        self._enchant_idx = None
        self._enchant_item = None
        self._enchant_fighter = None
        self._preview_item = None
        self._nav_from = ""
        self._nav_back_fighter_idx = -1
        self._inv_tabs_key = None
        self._shop_tabs_key = None
        self._inv_grid_key = None
        self._shard_grid_key = None
        self._inv_card_cache = {}

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
        self.lbl_top_title = t("inventory_label") if self.show_inventory else t("title_anvil")
        # Shard display
        s = engine.shards
        self.shard_text = f"I:{s.get(1,0)} II:{s.get(2,0)} III:{s.get(3,0)} IV:{s.get(4,0)} V:{s.get(5,0)}"
        if self.show_inventory:
            if self.weapon_upgrade_active or self.enchant_active:
                return  # don't redraw while upgrade/enchant screen is open
            if self.inv_detail_idx >= 0:
                self._show_inv_detail(self.inv_detail_idx)
            elif self.eq_detail_fighter >= 0 and self.eq_detail_slot:
                f = engine.fighters[self.eq_detail_fighter]
                item = f.equipment.get(self.eq_detail_slot)
                if item:
                    self._show_equipped_detail(self.eq_detail_fighter, item)
                else:
                    self.eq_detail_fighter = -1
                    self.eq_detail_slot = ""
                    self._refresh_inventory_grid()
            else:
                self._refresh_inventory_grid()
            return
        if self._preview_item is not None:
            self._show_shop_preview(self._preview_item)
            return
        # Show rarity filter tabs for shop
        self._show_inv_tabs = True
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
                text=sort_label, font_size=13,
                btn_color=ACCENT_CYAN, text_color=BG_DARK,
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
        refresh_forge_grid(self)

    def set_forge_tab(self, tab):
        self._save_scroll()
        self._reset_forge_state()
        self.forge_tab = tab
        self.refresh_forge()
        self._restore_scroll()

    def toggle_inventory(self):
        self._save_scroll()
        new_inv = not self.show_inventory
        self._reset_forge_state()
        self.show_inventory = new_inv
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
        return item.get("str", 0) + item.get("agi", 0) + item.get("vit", 0)

    def _refresh_inventory_grid(self):
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        self._show_inv_tabs = True
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
                    text=sort_label, font_size=13,
                    btn_color=ACCENT_CYAN, text_color=BG_DARK,
                    size_hint_y=None, height=dp(30),
                    icon_source=sort_icon,
                )
                sort_btn.bind(on_press=self.toggle_inventory_sort)
                tabs_box.add_widget(sort_btn)

        # Shard tab — show shard counts
        if self.inventory_tab == "shard":
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
                    (t(f"shard_name_{tier}"), sp(16), True, ACCENT_GOLD, 0.6),
                    (f"x {engine.shards.get(tier, 0)}", sp(18), True, TEXT_PRIMARY, 0.4),
                )
                grid.add_widget(shard_card)
            return

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
                    text=t("inventory_empty"), font_size="16sp",
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
            text=desc, font_size="12sp", color=TEXT_MUTED,
            halign="left", valign="top",
            size_hint_y=None,
        )
        lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
        lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
        lbl.bind(height=lambda inst, h: setattr(card, "height", h + dp(16)))
        card.add_widget(lbl)
        return card

    def _show_inv_detail(self, inv_idx):
        """Show detail view for a single inventory item."""
        self._show_inv_tabs = False; self._inv_tabs_key = None
        self.inv_detail_idx = inv_idx
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
            self._refresh_inventory_grid()
            return

        item = engine.inventory[inv_idx]
        slot = item.get("slot", "?")
        rarity = item.get("rarity", "common")
        max_upg = get_max_upgrade(item)
        sub = f"{slot.upper()} [{rarity.upper()}] max +{max_upg}" if slot in ("weapon", "armor", "accessory", "relic") else None

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
            text=t("sell_btn", price=fmt_num(sell_price)), font_size=16,
            btn_color=ACCENT_GOLD, text_color=BG_DARK,
            icon_source="icons/ic_gold.png",
        )
        def _sell(*a, idx=inv_idx):
            engine.sell_inventory_item(idx)
            self.inv_detail_idx = -1
            self.refresh_forge()
        sell_btn.bind(on_press=_sell)
        action_row.add_widget(sell_btn)

        equip_btn = MinimalButton(
            text=t("equip_btn"), font_size=15,
            btn_color=ACCENT_GREEN, text_color=BG_DARK,
        )
        equip_btn.bind(on_press=lambda *a: self._show_equip_fighter_popup(inv_idx, item))
        action_row.add_widget(equip_btn)
        grid.add_widget(action_row)

        # Upgradable items: IMPROVE button
        if item.get("slot") in ("weapon", "armor", "accessory", "relic"):
            improve_btn = MinimalButton(
                text=t("improve_btn"), font_size=16,
                btn_color=ACCENT_BLUE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            improve_btn.bind(on_press=lambda *a: self._show_item_upgrade("inv", inv_idx, item, None))
            grid.add_widget(improve_btn)

        # Weapon enchantment button
        if item.get("slot") == "weapon":
            enchant_btn = MinimalButton(
                text=t("tab_enchant"), font_size=16,
                btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            enchant_btn.bind(on_press=lambda *a: self._show_enchant_view("inv", inv_idx, item, None))
            grid.add_widget(enchant_btn)

    def _show_shop_preview(self, item):
        """Show read-only detail view for a shop item (no sell/equip/improve)."""
        self._show_inv_tabs = False; self._inv_tabs_key = None
        sv = self.ids.get("forge_scroll")
        if sv:
            sv.scroll_y = 1
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        slot = item.get("slot", "?")
        rarity = item.get("rarity", "common")
        max_upg = get_max_upgrade(item)
        sub = f"{slot.upper()} [{rarity.upper()}] max +{max_upg}" if slot in ("weapon", "armor", "accessory", "relic") else None

        grid.add_widget(build_item_info_card(item, subtitle=sub))
        desc_card = self._build_description_card(item)
        if desc_card:
            grid.add_widget(desc_card)


    def _close_shop_preview(self):
        nav = getattr(self, '_nav_from', None)
        fighter_idx = getattr(self, '_nav_back_fighter_idx', -1)
        self._preview_item = None
        self._nav_from = ""
        self._nav_back_fighter_idx = -1
        if nav:
            app = App.get_running_app()
            app._going_back = True
            app.sm.current = nav
            if fighter_idx >= 0 and nav == "roster":
                def _reopen(dt):
                    rs = app.sm.get_screen("roster")
                    rs.show_fighter_detail(fighter_idx)
                Clock.schedule_once(_reopen, 0)
        else:
            self.refresh_forge()

    def _close_inv_detail(self):
        nav = getattr(self, '_nav_from', None)
        fighter_idx = getattr(self, '_nav_back_fighter_idx', -1)
        self.inv_detail_idx = -1
        self.eq_detail_fighter = -1
        self.eq_detail_slot = ""
        self.weapon_upgrade_active = False
        self.enchant_active = False
        self._enchant_source = None
        self._enchant_idx = None
        self._enchant_item = None
        self._enchant_fighter = None
        self._inv_grid_key = None
        self._shard_grid_key = None
        self._inv_tabs_key = None
        self._inv_card_cache = {}
        self._nav_from = ""
        self._nav_back_fighter_idx = -1
        if nav:
            app = App.get_running_app()
            app._going_back = True
            app.sm.current = nav
            if fighter_idx >= 0 and nav == "roster":
                def _reopen(dt):
                    rs = app.sm.get_screen("roster")
                    rs.show_fighter_detail(fighter_idx)
                Clock.schedule_once(_reopen, 0)
        else:
            self.refresh_forge()

    def on_back_pressed(self):
        # Level 0: enchant view → back to item detail
        if self.enchant_active:
            self._close_enchant_view()
            return True
        # Level 1: weapon upgrade → back to item detail
        if self.weapon_upgrade_active:
            self.weapon_upgrade_active = False
            self.refresh_forge()
            return True
        # Level 2: item detail or equipped detail
        if self.inv_detail_idx != -1 or self.eq_detail_fighter != -1:
            if self._nav_from:
                # Came from another screen — clear state, let history navigate back
                self._reset_forge_state()
                return False  # go_back() pops history → previous screen
            self._close_inv_detail()
            return True
        # Level 3: shop preview
        if self._preview_item is not None:
            if self._nav_from:
                self._preview_item = None
                self._nav_from = ""
                return False
            self._close_shop_preview()
            return True
        # Level 4: inventory view → back to shop (or previous screen)
        if self.show_inventory:
            if self._nav_from:
                self._reset_forge_state()
                return False  # go_back() pops history → previous screen
            self.toggle_inventory()
            return True
        # Level 5: shop view — came from another screen
        if self._nav_from:
            self._reset_forge_state()
            return False
        return False

    @staticmethod
    def _get_slot_upgrade_config(slot, item):
        """Return (base_val, stat_pair, stat_label, base_label) for a given slot."""
        if slot == "weapon":
            return item.get("str", 0), "STR", "STR", t("weapon_base_atk")
        elif slot == "armor":
            return item.get("agi", 0), "AGI", "AGI", t("armor_base_def")
        elif slot == "relic":
            return 0, "STR+AGI+VIT", "STR/AGI/VIT", t("relic_base")
        else:  # accessory
            return item.get("vit", 0), "VIT", "VIT", t("accessory_base_hp")

    def _build_upgrade_comparison_card(self, item, fighter, engine):
        """Build and return the stat comparison BaseCard for an upgrade screen."""
        slot = item.get("slot", "weapon")
        is_relic = (slot == "relic")
        rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
        current_lvl = item.get("upgrade_level", 0)
        max_lvl = get_max_upgrade(item)
        base_val, stat_pair, stat_label, base_label = self._get_slot_upgrade_config(slot, item)

        num_rows = (12 if is_relic else 8) if fighter else 5
        comp_card = BC(
            orientation="vertical", size_hint_y=None, height=dp(30 + num_rows * 24),
            padding=[dp(12), dp(8)], spacing=dp(2),
        )
        comp_card.border_color = rcolor
        comp_card.add_label(item_display_name(item), font_size=sp(18), bold=True,
                            color=rcolor, halign="center", size_hint_y=0.15)

        def _info_row(label, value, color=TEXT_SECONDARY):
            return comp_card.add_text_row(
                (label, sp(12), False, TEXT_MUTED, 0.5),
                (str(value), sp(13), True, color, 0.5),
                height=dp(22),
            )

        def _breakdown(pct, label_prefix):
            if not fighter:
                if slot == "weapon":
                    _info_row(f"{label_prefix} {t('bonus_label')}", f"{pct}% (STR+AGI) → ATK", ACCENT_GREEN)
                elif slot == "armor":
                    _info_row(f"{label_prefix} {t('bonus_label')}", f"{pct}% (AGI+VIT) → DEF", ACCENT_GREEN)
                elif slot == "accessory":
                    _info_row(f"{label_prefix} {t('bonus_label')}", f"{pct}% (VIT+STR)x5 → HP", ACCENT_GREEN)
                elif is_relic:
                    _info_row(f"{label_prefix} {t('bonus_label')}", f"{pct}%/3 → ATK+DEF+HP", ACCENT_GREEN)
                return

            if slot == "weapon":
                pair_val = fighter.total_strength + fighter.total_agility
                bonus = int(pair_val * pct / 100)
                _info_row(f"{label_prefix} ({pct}% STR+AGI)", f"+{bonus} ATK", ACCENT_GREEN)
                _info_row(f"{t('total_label')} ATK", fighter.attack, ACCENT_GOLD)
            elif slot == "armor":
                pair_val = fighter.total_agility + fighter.total_vitality
                bonus = int(pair_val * pct / 100)
                _info_row(f"{label_prefix} ({pct}% AGI+VIT)", f"+{bonus} DEF", ACCENT_GREEN)
                _info_row(f"{t('total_label')} DEF", fighter.defense, ACCENT_GOLD)
            elif slot == "accessory":
                pair_val = fighter.total_vitality + fighter.total_strength
                bonus = int(pair_val * pct / 100 * 5)
                _info_row(f"{label_prefix} ({pct}% VIT+STR x5)", f"+{bonus} HP", ACCENT_GREEN)
                _info_row(f"{t('total_label')} HP", fighter.max_hp, ACCENT_GOLD)
            elif is_relic:
                sa = fighter.total_strength + fighter.total_agility
                av = fighter.total_agility + fighter.total_vitality
                vs = fighter.total_vitality + fighter.total_strength
                atk_b = int(sa * pct / 100) // 3
                def_b = int(av * pct / 100) // 3
                hp_b = int(vs * pct / 100 * 5) // 3
                _info_row(f"{label_prefix} ATK ({pct}%/3)", f"+{atk_b}", ACCENT_GREEN)
                _info_row(f"{label_prefix} DEF ({pct}%/3)", f"+{def_b}", ACCENT_GREEN)
                _info_row(f"{label_prefix} HP ({pct}%x5/3)", f"+{hp_b}", ACCENT_GREEN)

        if fighter and slot == "weapon":
            _info_row(f"STR ({fighter.total_strength}) x2", fighter.total_strength * 2, ACCENT_RED)
            _info_row("STR+AGI", f"{fighter.total_strength}+{fighter.total_agility}={fighter.total_strength + fighter.total_agility}", TEXT_SECONDARY)
        elif fighter and slot == "armor":
            _info_row("AGI+VIT", f"{fighter.total_agility}+{fighter.total_vitality}={fighter.total_agility + fighter.total_vitality}", TEXT_SECONDARY)
        elif fighter and slot == "accessory":
            _info_row("VIT+STR", f"{fighter.total_vitality}+{fighter.total_strength}={fighter.total_vitality + fighter.total_strength}", TEXT_SECONDARY)
        if is_relic:
            _info_row(t("relic_base"), f"ATK+{item.get('atk',0)} DEF+{item.get('def',0)} HP+{item.get('hp',0)}", TEXT_PRIMARY)
        else:
            _info_row(base_label, f"+{base_val}", TEXT_PRIMARY)
        _breakdown(current_lvl * UPGRADE_BONUS_PER_LEVEL, f"+{current_lvl}")

        if current_lvl < max_lvl:
            next_lvl = current_lvl + 1
            comp_card.add_widget(AutoShrinkLabel(
                text=f"--- +{next_lvl} ---", font_size="12sp",
                color=ACCENT_GOLD, halign="center", size_hint_y=None, height=dp(20),
            ))
            _breakdown(next_lvl * UPGRADE_BONUS_PER_LEVEL, f"+{next_lvl}")
            tier, count = get_upgrade_tier(next_lvl)
            if is_relic:
                count *= 10
            have = engine.shards.get(tier, 0)
            cost_text = f"{count}x {t('shard_name_' + str(tier))}"
            _info_row(t("cost_label"),
                      f"{cost_text} ({t('have_label')}: {have})",
                      ACCENT_GREEN if have >= count else ACCENT_RED)
        else:
            comp_card.add_widget(AutoShrinkLabel(
                text=f"MAX +{max_lvl}", font_size="16sp", bold=True,
                color=ACCENT_GOLD, halign="center", size_hint_y=None, height=dp(24),
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
        self._show_inv_tabs = False; self._inv_tabs_key = None
        self.enchant_active = True
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
            text=t("enchant_label"), font_size="16sp", bold=True,
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
            text=status_text, font_size="13sp",
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
            card.add_widget(AutoShrinkLabel(
                text=name_text, font_size="14sp", bold=True,
                color=name_color, halign="left",
                size_hint_y=None, height=dp(22),
            ))

            # Description
            desc = ench_data.get("description", "")
            if desc:
                desc_lbl = Label(
                    text=desc, font_size="11sp", color=TEXT_MUTED,
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
            card.add_widget(AutoShrinkLabel(
                text=cost_str, font_size="12sp",
                color=cost_color, halign="left",
                size_hint_y=None, height=dp(20),
            ))

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
                text=btn_text, font_size=13,
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
        self.enchant_active = False
        source = self._enchant_source or "inv"
        idx = self._enchant_idx if self._enchant_idx is not None else -1
        item = self._enchant_item
        if source == "inv":
            self._show_inv_detail(idx)
        else:
            self._show_equipped_detail(idx, item)

    def _show_item_upgrade(self, source, idx, item, fighter=None):
        """Universal upgrade/enchant comparison screen for weapon/armor/accessory."""
        self._show_inv_tabs = False; self._inv_tabs_key = None
        self.weapon_upgrade_active = True
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        engine = App.get_running_app().engine
        slot = item.get("slot", "weapon")
        current_lvl = item.get("upgrade_level", 0)
        max_lvl = get_max_upgrade(item)

        def _back(*a):
            self.weapon_upgrade_active = False
            if source == "inv":
                self._show_inv_detail(idx)
            else:
                self._show_equipped_detail(idx, item)

        grid.add_widget(self._build_upgrade_comparison_card(item, fighter, engine))

        if current_lvl < max_lvl:
            tier, count = get_upgrade_tier(current_lvl + 1)
            if slot == "relic":
                count *= 10
            have = engine.shards.get(tier, 0)
            can_upgrade = have >= count
            upg_btn = MinimalButton(
                text=f"{t('upgrade_btn')} +{current_lvl + 1}", font_size=16,
                btn_color=ACCENT_GREEN if can_upgrade else BTN_DISABLED,
                text_color=BG_DARK if can_upgrade else TEXT_MUTED,
                size_hint_y=None, height=dp(46),
            )
            def _do_upgrade(inst, w=item, s=source, i=idx, f=fighter):
                result = engine.upgrade_item(w)
                if result.ok:
                    self._show_item_upgrade(s, i, w, f)
                else:
                    App.get_running_app().show_toast(result.message)
            upg_btn.bind(on_press=_do_upgrade)
            grid.add_widget(upg_btn)

    def _show_equipped_detail(self, fighter_idx, item):
        """Detail view for an item currently equipped on a fighter."""
        self._show_inv_tabs = False; self._inv_tabs_key = None
        self.eq_detail_fighter = fighter_idx
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
            text=t("unequip_btn"), font_size=15,
            btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(44),
        )
        def _unequip(*a, s=slot, fi=fighter_idx):
            result = engine.unequip_from_fighter(fi, s)
            if not result.ok:
                App.get_running_app().show_toast(result.message or t("not_in_battle"))
                return
            self._close_inv_detail()
        unequip_btn.bind(on_press=_unequip)
        grid.add_widget(unequip_btn)

        # Upgradable items: IMPROVE button
        if item.get("slot") in ("weapon", "armor", "accessory", "relic"):
            improve_btn = MinimalButton(
                text=t("improve_btn"), font_size=16,
                btn_color=ACCENT_BLUE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            improve_btn.bind(on_press=lambda *a: self._show_item_upgrade("equip", fighter_idx, item, f))
            grid.add_widget(improve_btn)

        # Weapon enchantment button
        if item.get("slot") == "weapon":
            enchant_btn = MinimalButton(
                text=t("tab_enchant"), font_size=16,
                btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            enchant_btn.bind(on_press=lambda *a: self._show_enchant_view("equip", fighter_idx, item, f))
            grid.add_widget(enchant_btn)

    def _show_equip_fighter_popup(self, inv_idx, item):
        engine = App.get_running_app().engine
        alive = [(i, f) for i, f in enumerate(engine.fighters)
                 if f.available]
        if not alive:
            App.get_running_app().show_toast(t("no_fighters"))
            return

        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        popup = Popup(
            title=f"{t('equip_btn')}: {item_display_name(item)}",
            title_color=popup_color(ACCENT_GOLD),
            title_size=sp(15),
            content=content,
            size_hint=(0.85, None),
            height=dp(80 + len(alive) * 54),
            background_color=popup_color(BG_CARD),
            separator_color=popup_color(ACCENT_GOLD),
            auto_dismiss=True,
        )
        for fi, f in alive:
            cur = f.equipment.get(item.get("slot", "weapon"))
            cur_name = cur.get("name", "—") if cur else "—"
            btn = MinimalButton(
                text=f"{f.name}  [{cur_name}]",
                font_size=14,
                btn_color=BTN_PRIMARY,
            )
            def _do_equip(inst, fidx=fi):
                if engine.battle_active:
                    App.get_running_app().show_toast(t("not_in_battle"))
                    return
                engine.equip_from_inventory(fidx, inv_idx)
                popup.dismiss()
                self.inv_detail_idx = -1
                self.refresh_forge()
            btn.bind(on_press=_do_equip)
            content.add_widget(btn)
        popup.open()

    def buy(self, item_id):
        app = App.get_running_app()
        result = app.engine.buy_forge_item(item_id)
        if result.message:
            app.show_toast(result.message)
        self.refresh_forge()
