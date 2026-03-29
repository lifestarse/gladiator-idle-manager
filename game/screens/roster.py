# Build: 3
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.metrics import dp, sp
from kivy.uix.image import Image as KvImage
from kivy.uix.scrollview import ScrollView
from kivy.effects.scroll import ScrollEffect
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard
from game.models import (
    FIGHTER_CLASSES, fmt_num, RARITY_COLORS,
    FORGE_WEAPONS, FORGE_ARMOR, FORGE_ACCESSORIES,
    item_display_name,
)
from game.theme import *
from game.theme import popup_color
from game.localization import t
from game.ui_helpers import (
    refresh_roster_grid,
    build_item_info_card,
    _roster_callbacks,
    bind_text_wrap,
)
from game.screens.shared import _safe_clear, _safe_rebind


class RosterScreen(BaseScreen):
    gladiators_data = ListProperty()
    graveyard_text = StringProperty("")
    hire_cost_text = StringProperty("")
    hire_enabled = StringProperty("true")
    heal_all_text = StringProperty("")
    heal_all_enabled = StringProperty("false")
    has_injuries = StringProperty("false")
    detail_index = NumericProperty(-1)
    roster_view = StringProperty("list")  # "list", "detail", "hire"

    def on_enter(self):
        _roster_callbacks['show_detail'] = self.show_fighter_detail
        _roster_callbacks['dismiss'] = self.dismiss
        self.detail_index = -1
        self.roster_view = "list"
        self.refresh_roster()

    def refresh_roster(self):
        engine = App.get_running_app().engine
        self._update_top_bar()
        deaths = engine.total_deaths
        self.graveyard_text = t("fallen", n=deaths) if deaths > 0 else ""
        # Fast path: skip if fighters haven't changed
        roster_key = tuple(
            (f.name, f.level, f.hp, f.alive, f.injuries, f.on_expedition,
             i == engine.active_fighter_idx)
            for i, f in enumerate(engine.fighters)
        )
        hire_affordable = engine.gold >= engine.hire_cost
        if roster_key == getattr(self, '_roster_key', None) and hire_affordable == getattr(self, '_hire_was_affordable', None):
            return
        self._roster_key = roster_key
        self._hire_was_affordable = hire_affordable

        self.gladiators_data = [
            {
                "name": f.name, "level": f.level,
                "fighter_class": f.fighter_class,
                "fighter_class_name": f.class_name,
                "str": f.strength, "agi": f.agility, "vit": f.vitality,
                "unused_points": f.unused_points,
                "atk": f.attack, "def": f.defense, "hp": f.max_hp,
                "current_hp": f.hp,
                "crit": f.crit_chance, "dodge": f.dodge_chance,
                "cost": f.upgrade_cost,
                "index": i, "active": i == engine.active_fighter_idx,
                "alive": f.alive, "injuries": f.injuries, "kills": f.kills,
                "death_chance": f.death_chance,
                "on_expedition": f.on_expedition,
                "weapon": f.equipment.get("weapon"),
                "armor": f.equipment.get("armor"),
                "accessory": f.equipment.get("accessory"),
                "relic": f.equipment.get("relic"),
            }
            for i, f in enumerate(engine.fighters)
        ]
        self.hire_cost_text = t("recruit_btn", cost=fmt_num(engine.hire_cost))
        self.hire_enabled = "true" if hire_affordable else "false"
        heal_cost = engine.heal_all_injuries_cost()
        has_injuries = heal_cost > 0
        can_afford = engine.gold >= heal_cost and has_injuries
        self.heal_all_text = t("heal_all_injuries_cost", cost=fmt_num(heal_cost)) if has_injuries else t("heal_all_injuries")
        self.heal_all_enabled = "true" if can_afford else "false"
        self.has_injuries = "true" if has_injuries else "false"
        refresh_roster_grid(self)

    def upgrade(self, index):
        app = App.get_running_app()
        result = app.engine.upgrade_gladiator(index)
        if not result.ok and result.message:
            app.show_toast(result.message)
        self.refresh_roster()

    def set_active(self, index):
        App.get_running_app().engine.active_fighter_idx = index
        self.refresh_roster()

    def hire(self):
        engine = App.get_running_app().engine
        if engine.gold < engine.hire_cost:
            App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(engine.hire_cost - engine.gold)))
            return
        self.roster_view = "hire"
        self.detail_index = -1
        self._show_hire_view()

    def _show_hire_view(self):
        engine = App.get_running_app().engine
        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        back_btn = MinimalButton(
            text=t("back_btn"), btn_color=BTN_PRIMARY, font_size=16,
            size_hint_y=None, height=dp(38),
        )
        back_btn.bind(on_press=lambda inst: self.close_detail())
        grid.add_widget(back_btn)

        grid.add_widget(AutoShrinkLabel(
            text=t("choose_class"), font_size="19sp",
            color=ACCENT_GOLD, size_hint_y=None, height=dp(30),
        ))

        for cls_id, cls_data in FIGHTER_CLASSES.items():
            card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(100),
                            padding=[dp(10), dp(6)], spacing=dp(6))
            cls_color = (ACCENT_GREEN if cls_id == "mercenary" else
                         ACCENT_RED if cls_id == "assassin" else ACCENT_BLUE)
            info = BoxLayout(orientation="vertical", size_hint_x=0.65, spacing=dp(2))
            info.add_widget(card._make_label(cls_data["name"], sp(19), True, cls_color, "left", 1))
            info.add_widget(card._make_label(
                f"STR {cls_data['base_str']}  AGI {cls_data['base_agi']}  VIT {cls_data['base_vit']}",
                sp(15), False, TEXT_SECONDARY, "left", 1))
            info.add_widget(card._make_label(cls_data["desc"], sp(14), False, TEXT_MUTED, "left", 1))
            card.add_widget(info)

            btn = MinimalButton(
                text=t("btn_select"), font_size=17, size_hint_x=0.35,
                btn_color=ACCENT_GOLD, text_color=BG_DARK,
            )
            def _hire(inst, cid=cls_id):
                engine.hire_gladiator(cid)
                self.close_detail()
            btn.bind(on_press=_hire)
            card.add_widget(btn)
            grid.add_widget(card)

    def dismiss(self, index):
        App.get_running_app().engine.dismiss_dead(index)
        self.refresh_roster()

    def add_str(self, index):
        App.get_running_app().engine.distribute_stat(index, "strength")
        self.refresh_roster()

    def add_agi(self, index):
        App.get_running_app().engine.distribute_stat(index, "agility")
        self.refresh_roster()

    def add_vit(self, index):
        App.get_running_app().engine.distribute_stat(index, "vitality")
        self.refresh_roster()

    def heal_all_injuries(self):
        app = App.get_running_app()
        result = app.engine.heal_all_injuries()
        if not result.ok and result.message:
            app.show_toast(result.message)
        self.refresh_roster()

    def _build_fighter_header(self, grid, f, index, engine):
        """Add name/stats/attribute rows to detail grid."""
        grid.add_widget(AutoShrinkLabel(
            text=f"{f.name}  [{f.class_name}]  Lv.{f.level}", font_size="20sp", bold=True,
            color=ACCENT_GOLD, size_hint_y=None, height=dp(32), halign="center",
        ))

        stats_text = (
            f"ATK {fmt_num(f.attack)}   DEF {fmt_num(f.defense)}   HP {fmt_num(f.hp)}/{fmt_num(f.max_hp)}\n"
            f"Crit {f.crit_chance:.0%}   Dodge {f.dodge_chance:.0%}"
        )
        stats_lbl = AutoShrinkLabel(
            text=stats_text, font_size="15sp",
            color=TEXT_SECONDARY, size_hint_y=None, height=dp(40), halign="center",
        )
        bind_text_wrap(stats_lbl)
        grid.add_widget(stats_lbl)

        stat_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        has_pts = f.unused_points > 0 and f.available
        for stat_name, stat_val, color, stat_key in [
            ("STR", f.strength, ACCENT_RED, "strength"),
            ("AGI", f.agility, ACCENT_GREEN, "agility"),
            ("VIT", f.vitality, ACCENT_BLUE, "vitality"),
        ]:
            cell = BoxLayout(spacing=dp(2))
            lbl = AutoShrinkLabel(text=f"{stat_name} {stat_val}", font_size="15sp",
                        color=color, halign="center", bold=True)
            bind_text_wrap(lbl)
            cell.add_widget(lbl)
            if has_pts:
                btn = MinimalButton(text="+", btn_color=color, text_color=BG_DARK,
                                    font_size=16, size_hint_x=0.4)
                def _add(inst, sk=stat_key, idx=index):
                    engine.distribute_stat(idx, sk)
                    engine.save()
                    self.refresh_roster()
                    self.show_fighter_detail(idx)
                btn.bind(on_press=_add)
                cell.add_widget(btn)
            stat_row.add_widget(cell)
        grid.add_widget(stat_row)

        if has_pts:
            grid.add_widget(AutoShrinkLabel(
                text=t("pts_label", n=f.unused_points), font_size="14sp",
                color=ACCENT_GOLD, size_hint_y=None, height=dp(20), halign="center",
            ))

    def _build_fighter_equipment(self, grid, f, index, engine):
        """Add equipment slot rows to detail grid."""
        seen_relic_ids = set()
        inv_relics = []
        for inv_item in engine.inventory:
            if inv_item.get("slot") == "relic" and inv_item.get("id") not in seen_relic_ids:
                inv_relics.append(inv_item)
                seen_relic_ids.add(inv_item.get("id"))
        for slot, icon_src, items_list in [
            ("weapon", "icons/ic_weapon.png", FORGE_WEAPONS),
            ("armor", "icons/ic_armor.png", FORGE_ARMOR),
            ("accessory", "icons/ic_accessory.png", FORGE_ACCESSORIES),
            ("relic", "icons/ic_accessory.png", inv_relics),
        ]:
            eq_row = BaseCard(
                orientation="horizontal", size_hint_y=None, height=dp(36),
                spacing=dp(6), padding=[dp(4), 0],
                card_color=[0, 0, 0, 0], border_color=[0, 0, 0, 0],
            )
            eq_row.add_widget(KvImage(source=icon_src, fit_mode="contain",
                                      size_hint=(None, 1), width=dp(28)))
            item = f.equipment.get(slot)
            if item:
                rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
                eq_row.border_color = rcolor
                display = item_display_name(item)
                iatk, idef, ihp = f.item_total_stats(slot)
                stat_parts = []
                if iatk: stat_parts.append(f"+{fmt_num(iatk)} ATK")
                if idef: stat_parts.append(f"+{fmt_num(idef)} DEF")
                if ihp: stat_parts.append(f"+{fmt_num(ihp)} HP")
                if stat_parts:
                    display += f"  ({', '.join(stat_parts)})"
                eq_row.add_widget(eq_row._make_label(display, sp(15), True, rcolor, "left", 1))
            else:
                eq_row.add_widget(eq_row._make_label(t("empty_slot"), sp(15), False, TEXT_MUTED, "left", 1))
            if f.available:
                def _open_eq(inst, s=slot, il=items_list, idx=index):
                    self._show_equipment_popup(idx, s, il)
                eq_row.bind(on_press=_open_eq)
            grid.add_widget(eq_row)

    def _build_fighter_actions(self, grid, f, index, engine):
        """Add injuries/kills labels and action buttons to detail grid."""
        if f.injuries > 0:
            grid.add_widget(AutoShrinkLabel(
                text=t("injuries_label", n=f.injuries, risk=f"{f.death_chance:.0%}"),
                font_size="15sp", color=ACCENT_RED,
                size_hint_y=None, height=dp(24), halign="center",
            ))

        grid.add_widget(AutoShrinkLabel(
            text=t("kills_label", n=f.kills), font_size="14sp", color=TEXT_MUTED,
            size_hint_y=None, height=dp(20), halign="center",
        ))

        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))
        if f.available:
            cost = f.upgrade_cost
            can_train = engine.gold >= cost
            train_btn = MinimalButton(
                text=t("train_btn", lv=f.level + 1, cost=fmt_num(cost)),
                btn_color=ACCENT_GOLD if can_train else BTN_DISABLED,
                text_color=BG_DARK if can_train else TEXT_MUTED,
                font_size=22, icon_source="icons/ic_gold.png",
            )
            def _train(inst, idx=index):
                result = engine.upgrade_gladiator(idx)
                if not result.ok and result.message:
                    App.get_running_app().show_toast(result.message)
                self.refresh_roster()
                self.show_fighter_detail(idx)
            train_btn.bind(on_press=_train)
            btn_row.add_widget(train_btn)

        if f.injuries > 0:
            heal_cost = f.get_injury_heal_cost()
            can_heal = engine.gold >= heal_cost
            heal_btn = MinimalButton(
                text=f"{t('heal_btn')} {fmt_num(heal_cost)}",
                btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
                text_color=BG_DARK if can_heal else TEXT_MUTED,
                font_size=22, icon_source="icons/ic_gold.png",
            )
            def on_heal(inst, idx=index):
                result = engine.heal_fighter_injury(idx)
                if not result.ok and result.message:
                    App.get_running_app().show_toast(result.message)
                self.refresh_roster()
                self.show_fighter_detail(idx)
            heal_btn.bind(on_press=on_heal)
            btn_row.add_widget(heal_btn)
        grid.add_widget(btn_row)

        back_btn = MinimalButton(
            text=t("back_btn"), btn_color=BTN_PRIMARY, font_size=16,
            size_hint_y=None, height=dp(38),
        )
        back_btn.bind(on_press=lambda inst: self.close_detail())
        grid.add_widget(back_btn)

    def show_fighter_detail(self, index):
        engine = App.get_running_app().engine
        if index < 0 or index >= len(engine.fighters):
            return
        self.detail_index = index
        self.roster_view = "detail"
        f = engine.fighters[index]

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        self._build_fighter_header(grid, f, index, engine)
        self._build_fighter_equipment(grid, f, index, engine)
        self._build_fighter_actions(grid, f, index, engine)

    def close_detail(self):
        self.detail_index = -1
        self.roster_view = "list"
        self.refresh_roster()

    def on_back_pressed(self):
        if self.roster_view != "list":
            self.close_detail()
            return True
        return False

    def _show_equipment_popup(self, fighter_idx, slot, items_list):
        """Popup showing all items for a slot — buy or equip from inventory."""
        engine = App.get_running_app().engine
        f = engine.fighters[fighter_idx]

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False,
                            effect_cls=ScrollEffect,
                            scroll_distance=dp(20), scroll_timeout=150)
        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            padding=[dp(8), dp(6)], size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # Currently equipped
        current = f.equipment.get(slot)
        if current:
            def _tap_equipped(inst, fi=fighter_idx, s=slot):
                equip_popup.dismiss()
                App.get_running_app().open_equipped_detail(fi, s)
            content.add_widget(build_item_info_card(current, fighter=f, equipped_on=f.name,
                                                    on_tap=_tap_equipped))
            unequip_btn = MinimalButton(
                text=t("unequip_btn"), font_size=14,
                btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(36),
            )
            def _unequip(inst, s=slot, idx=fighter_idx):
                result = engine.unequip_from_fighter(idx, s)
                if not result.ok:
                    App.get_running_app().show_toast(result.message or t("not_in_battle"))
                    return
                equip_popup.dismiss()
                self.refresh_roster()
                self.show_fighter_detail(idx)
            unequip_btn.bind(on_press=_unequip)
            content.add_widget(unequip_btn)

        for template_item in items_list:
            # Use actual inventory item (with upgrade_level) if available
            inv_idx = engine.find_inventory_index(template_item["id"])
            item = engine.inventory[inv_idx] if inv_idx >= 0 else template_item
            inv_count = engine.get_inventory_count(item["id"])

            # Item card — tap opens detail in ForgeScreen (or popup for shop-only items)
            def _tap_card(inst, it=item):
                ii = engine.find_inventory_index(it["id"])
                if ii >= 0:
                    equip_popup.dismiss()
                    App.get_running_app().open_item_detail(ii)
                else:
                    equip_popup.dismiss()
                    App.get_running_app().open_shop_preview(it)
            info_card = build_item_info_card(item, fighter=f, on_tap=_tap_card)
            content.add_widget(info_card)

            # Action button row under the card
            btn_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
            if inv_count > 0:
                btn_row.add_widget(AutoShrinkLabel(
                    text=f"x{inv_count}", font_size="14sp", color=ACCENT_GOLD,
                    size_hint_x=0.15, halign="center",
                ))
                equip_btn = MinimalButton(
                    text=t("equip_btn"), font_size=14,
                    btn_color=ACCENT_GREEN, text_color=BG_DARK,
                )
                def _equip(inst, iid=item["id"], idx=fighter_idx):
                    if engine.battle_active:
                        App.get_running_app().show_toast(t("not_in_battle"))
                        return
                    inv_idx = engine.find_inventory_index(iid)
                    if inv_idx >= 0:
                        engine.equip_from_inventory(idx, inv_idx)
                        equip_popup.dismiss()
                        self.refresh_roster()
                        self.show_fighter_detail(idx)
                equip_btn.bind(on_press=_equip)
                btn_row.add_widget(equip_btn)
            else:
                shop_cost = template_item["cost"]
                affordable = engine.gold >= shop_cost
                rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
                buy_btn = MinimalButton(
                    text=t("buy_btn_price", price=fmt_num(shop_cost)), font_size=16,
                    btn_color=rcolor if affordable else BTN_DISABLED,
                    text_color=BG_DARK if affordable else TEXT_MUTED,
                    icon_source="icons/ic_gold.png",
                )
                def _buy(inst, iid=template_item["id"], idx=fighter_idx, s=slot, il=items_list):
                    result = engine.buy_forge_item(iid)
                    if result.message:
                        App.get_running_app().show_toast(result.message)
                    equip_popup.dismiss()
                    self.refresh_roster()
                    self._show_equipment_popup(idx, s, il)
                if affordable:
                    buy_btn.bind(on_press=_buy)
                btn_row.add_widget(buy_btn)
            content.add_widget(btn_row)

        scroll.add_widget(content)

        equip_popup = Popup(
            title=f"{slot.upper()} — {f.name}",
            title_color=ACCENT_GOLD, title_size="16sp",
            content=scroll, size_hint=(0.94, 0.7),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_GOLD,
        )
        equip_popup.open()
