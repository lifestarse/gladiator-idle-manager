# Build: 1
"""RosterScreen _FighterDetailMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _FighterDetailMixin:

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
