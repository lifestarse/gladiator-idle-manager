# Build: 1
"""_ItemDescMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _ItemDescMixin:
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

