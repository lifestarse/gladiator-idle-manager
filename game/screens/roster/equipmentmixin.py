# Build: 1
"""RosterScreen _EquipmentMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _EquipmentMixin:
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
                text=t("unequip_btn"), font_size=11,
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
                    text=f"x{inv_count}", font_size="10sp", color=ACCENT_GOLD,
                    size_hint_x=0.15, halign="center",
                ))
                equip_btn = MinimalButton(
                    text=t("equip_btn"), font_size=11,
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
                    text=t("buy_btn_price", price=fmt_num(shop_cost)), font_size=11,
                    btn_color=rcolor if affordable else BTN_DISABLED,
                    text_color=BG_DARK if affordable else TEXT_MUTED,
                    icon_source="sprites/icons/ic_gold.png",
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
            title_color=ACCENT_GOLD, title_size="11sp",
            content=scroll, size_hint=(0.94, 0.7),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_GOLD,
        )
        equip_popup.open()
