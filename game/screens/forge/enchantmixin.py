# Build: 1
"""ForgeScreen _EnchantMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _EnchantMixin:
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
