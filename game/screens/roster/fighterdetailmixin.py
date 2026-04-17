# Build: 1
"""RosterScreen _FighterDetailMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _FighterDetailMixin:
    def _build_fighter_header(self, grid, f, index, engine):
        """Add name/stats/attribute rows to detail grid."""
        header_lbl = AutoShrinkLabel(
            text=f"{f.name}  [{f.class_name}]  Lv.{f.level}", font_size="13sp", bold=True,
            color=ACCENT_GOLD, size_hint_y=None, height=dp(44), halign="center",
        )
        bind_text_wrap(header_lbl)
        grid.add_widget(header_lbl)

        def _c(color):
            return ''.join(f'{int(v*255):02x}' for v in color[:3])
        rc, gc, bc = _c(ACCENT_RED), _c(ACCENT_GREEN), _c(ACCENT_BLUE)
        gc2, cc = _c(ACCENT_GOLD), _c(ACCENT_CYAN)
        atk_text = (
            f"[color=#{rc}]ATK {fmt_num(f.attack)}[/color]   "
            f"[color=#{bc}]DEF {fmt_num(f.defense)}[/color]   "
            f"[color=#{gc}]HP {fmt_num(f.hp)}/{fmt_num(f.max_hp)}[/color]"
        )
        stats_lbl = AutoShrinkLabel(
            text=atk_text, font_size="11sp", markup=True, color=TEXT_SECONDARY,
            size_hint_y=None, height=dp(30), halign="center",
        )
        bind_text_wrap(stats_lbl)
        grid.add_widget(stats_lbl)

        crit_text = (
            f"[color=#{gc2}]Crit {f.crit_chance:.0%}[/color]   "
            f"[color=#{cc}]Dodge {f.dodge_chance:.0%}[/color]"
        )
        crit_lbl = AutoShrinkLabel(
            text=crit_text, font_size="11sp", markup=True, color=TEXT_SECONDARY,
            size_hint_y=None, height=dp(30), halign="center",
        )
        bind_text_wrap(crit_lbl)
        grid.add_widget(crit_lbl)

        stat_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        has_pts = f.unused_points > 0 and f.available
        for stat_name, stat_val, color, stat_key in [
            ("STR", f.total_strength, ACCENT_RED, "strength"),
            ("AGI", f.total_agility, ACCENT_GREEN, "agility"),
            ("VIT", f.total_vitality, ACCENT_BLUE, "vitality"),
        ]:
            cell = BoxLayout(spacing=dp(2))
            lbl = AutoShrinkLabel(text=f"{stat_name} {stat_val}", font_size="11sp",
                        color=color, halign="center", bold=True)
            bind_text_wrap(lbl)
            cell.add_widget(lbl)
            if has_pts:
                btn = MinimalButton(text="+", btn_color=color, text_color=BG_DARK,
                                    font_size=11, size_hint_x=0.4)
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
                text=t("pts_label", n=f.unused_points), font_size="11sp",
                color=ACCENT_GOLD, size_hint_y=None, height=dp(30), halign="center",
            ))

    def _build_fighter_equipment(self, grid, f, index, engine):
        """Add equipment slot rows to detail grid.

        Uses the same card style as the main inventory list: `name`,
        `SLOT [RARITY]` subtitle (no "max +N" suffix — that's the detail
        view), and base STR/AGI/VIT stats. No `fighter=` arg and no
        `equipped_on` badge: we're already on this fighter's own page so
        owner info would be redundant.
        """
        from game.slots import SLOTS
        from game.localization import t as tr

        seen_relic_ids = set()
        inv_relics = []
        for inv_item in engine.inventory:
            if inv_item.get("slot") == "relic" and inv_item.get("id") not in seen_relic_ids:
                inv_relics.append(inv_item)
                seen_relic_ids.add(inv_item.get("id"))

        for slot, icon_src in [
            ("weapon", "icons/ic_weapon.png"),
            ("armor", "icons/ic_armor.png"),
            ("accessory", "icons/ic_accessory.png"),
            ("relic", "icons/ic_accessory.png"),
        ]:
            item = f.equipment.get(slot)
            if item:
                def _open_eq(inst, fi=index, s=slot):
                    if not f.available:
                        return
                    Clock.schedule_once(
                        lambda dt: App.get_running_app().open_equipped_detail(fi, s),
                        0.05)

                card = build_item_info_card(
                    item,
                    on_tap=_open_eq if f.available else None,
                )
                grid.add_widget(card)
            else:
                # Empty-slot placeholder: icon + label, dp(75) to match
                # non-empty cards so the layout doesn't jump when a slot
                # flips between filled/empty.
                from game.widgets import BaseCard
                empty_card = BaseCard(
                    orientation="horizontal", size_hint_y=None, height=dp(75),
                    padding=[dp(12), dp(8)], spacing=dp(8),
                )
                empty_card.border_color = TEXT_MUTED
                empty_card.add_widget(KvImage(
                    source=icon_src, fit_mode="contain",
                    size_hint=(None, 1), width=dp(32),
                ))
                slot_def = SLOTS.get(slot)
                slot_label = tr(slot_def.label_keys['upper']) if slot_def else slot.upper()
                empty_card.add_widget(empty_card._make_label(
                    f"{slot_label}: {tr('empty_slot')}",
                    sp(11), False, TEXT_MUTED, "left", 1,
                ))
                if f.available:
                    def _open_empty(inst, s=slot, fi=index):
                        def _nav(dt):
                            app = App.get_running_app()
                            # Stash the source fighter so the forge's
                            # equip flow auto-targets them instead of
                            # opening a picker popup.
                            app.pending_equip_target_idx = fi
                            has_free = any(
                                it.get("slot") == s for it in app.engine.inventory
                            )
                            if has_free:
                                app.open_inventory_tab(s, equip_filter="free")
                            else:
                                app.open_forge_tab(s)
                        Clock.schedule_once(_nav, 0.05)
                    empty_card.bind(on_press=_open_empty)
                grid.add_widget(empty_card)

    def _build_fighter_actions(self, grid, f, index, engine):
        """Add kills label, injuries button, and action buttons to detail grid."""
        grid.add_widget(AutoShrinkLabel(
            text=t("kills_label", n=f.kills), font_size="11sp", color=TEXT_MUTED,
            size_hint_y=None, height=dp(32), halign="center",
        ))

        # Injuries button (only if fighter has injuries)
        if f.injury_count > 0:
            inj_btn = MinimalButton(
                text=f"{t('injuries_tab')} ({f.injury_count})  —  {t('death_risk')}: {f.death_chance:.0%}",
                font_size=11, btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(48),
            )
            inj_btn.bind(on_press=lambda inst, idx=index: self._show_injuries_view(idx))
            grid.add_widget(inj_btn)

        # Skills button
        skills_btn = MinimalButton(
            text=t("skills_btn"), font_size=11,
            btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(48),
        )
        skills_btn.bind(on_press=lambda inst, idx=index: self._show_skills_view(idx))
        grid.add_widget(skills_btn)

        # Perk tree button
        if f.available:
            perk_label = f"{t('perks_btn')} ({f.perk_points})" if f.perk_points > 0 else t("perks_btn")
            perk_btn = MinimalButton(
                text=perk_label, font_size=11,
                btn_color=ACCENT_CYAN, text_color=BG_DARK,
                size_hint_y=None, height=dp(48),
            )
            perk_btn.bind(on_press=lambda inst, idx=index: self._show_perk_tree(idx))
            grid.add_widget(perk_btn)

        if f.available:
            cost = f.upgrade_cost
            can_train = engine.gold >= cost
            train_btn = MinimalButton(
                text=t("train_btn", lv=f.level + 1, cost=fmt_num(cost)),
                btn_color=ACCENT_GOLD if can_train else BTN_DISABLED,
                text_color=BG_DARK if can_train else TEXT_MUTED,
                font_size=11, icon_source="sprites/icons/ic_gold.png",
                size_hint_y=None, height=dp(48),
            )
            def _train(inst, idx=index):
                result = engine.upgrade_gladiator(idx)
                if not result.ok and result.message:
                    App.get_running_app().show_toast(result.message)
                self.refresh_roster()
                self.show_fighter_detail(idx)
            train_btn.bind(on_press=_train)
            grid.add_widget(train_btn)

        # Dismiss button
        dismiss_btn = MinimalButton(
            text=t("dismiss_btn"), font_size=11,
            btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(48),
        )
        dismiss_btn.bind(on_press=lambda inst, idx=index: self._confirm_dismiss(idx))
        grid.add_widget(dismiss_btn)

    def _confirm_dismiss(self, fighter_idx):
        """Show confirmation popup before dismissing a fighter."""
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]

        content = BoxLayout(orientation="vertical", spacing=dp(8),
                            padding=[dp(12), dp(8)])
        content.add_widget(AutoShrinkLabel(
            text=t("dismiss_confirm_msg", name=f.name),
            font_size="11sp", color=TEXT_SECONDARY,
            halign="center", valign="middle",
            size_hint_y=0.6,
        ))
        btn_row = BoxLayout(size_hint_y=0.4, spacing=dp(8))
        cancel_btn = MinimalButton(
            text=t("back_btn"), btn_color=BTN_PRIMARY,
            font_size=11,
        )
        confirm_btn = MinimalButton(
            text=t("dismiss_confirm_btn"), btn_color=ACCENT_RED,
            text_color=TEXT_PRIMARY, font_size=11,
        )
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)

        popup = make_styled_popup(t("dismiss_confirm_title"), content,
                                  size_hint=(0.85, 0.35))
        cancel_btn.bind(on_press=lambda inst: popup.dismiss())
        def _do_dismiss(inst, idx=fighter_idx):
            popup.dismiss()
            result = engine.dismiss_fighter(idx)
            if result.ok:
                App.get_running_app().show_toast(result.message)
                self.close_detail()
            else:
                App.get_running_app().show_toast(result.message)
        confirm_btn.bind(on_press=_do_dismiss)
        popup.open()

    def show_fighter_detail(self, index):
        engine = App.get_running_app().engine
        if index < 0 or index >= len(engine.fighters):
            return
        was_already_on_same = (self.roster_view == "detail"
                               and self.detail_index == index)
        self.detail_index = index
        self.roster_view = "detail"
        f = engine.fighters[index]

        grid = self.ids.get("detail_grid")
        if not grid:
            return

        # Preserve scroll position on re-render of the SAME fighter (train
        # button, stat allocation, equip/unequip). Without this the grid
        # rebuild snaps the ScrollView back to the top every time, which
        # kicked the user off the Train button after every level up.
        # First-time opens (new fighter) keep default behaviour — scroll
        # to top so the header is visible.
        sv = self.ids.get("detail_scroll")
        preserved_y = sv.scroll_y if (sv and was_already_on_same) else None

        _safe_clear(grid)

        self._build_fighter_header(grid, f, index, engine)
        self._build_fighter_equipment(grid, f, index, engine)
        self._build_fighter_actions(grid, f, index, engine)

        if preserved_y is not None and sv is not None:
            # Restore after this frame so layout has re-computed grid
            # height first — setting scroll_y immediately would clamp
            # against the stale pre-clear height.
            Clock.schedule_once(lambda dt, y=preserved_y:
                                setattr(sv, 'scroll_y', y), 0)

    def close_detail(self):
        self.detail_index = -1
        self.roster_view = "list"
        self.refresh_roster()

    def _build_passive_card(self, passive):
        """Build card for a class's passive ability."""
        from kivy.uix.label import Label
        p_card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(70),
                          padding=[dp(10), dp(6)], spacing=dp(2))
        p_card.border_color = ACCENT_GOLD
        passive_lbl = AutoShrinkLabel(
            text=f"{t('perk_passive_label')}: {passive['name']}", font_size="10sp",
            bold=True, color=ACCENT_GOLD, halign="left",
            size_hint_y=None, height=dp(30),
        )
        bind_text_wrap(passive_lbl)
        p_card.add_widget(passive_lbl)
        desc_lbl = Label(
            text=passive.get("description", ""), font_size="11sp", font_name='PixelFont',
            color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
        )
        desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
        desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
        desc_lbl.bind(height=lambda inst, h, c=p_card: setattr(c, "height", max(dp(70), h + dp(40))))
        p_card.add_widget(desc_lbl)
        return p_card
