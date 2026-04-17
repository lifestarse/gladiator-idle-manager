# Build: 1
"""RosterScreen _InjuriesMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _InjuriesMixin:
    def _show_injuries_view(self, fighter_idx):
        """Separate view listing all injuries with heal buttons."""
        from game.data_loader import data_loader
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]
        self.detail_index = fighter_idx
        self._injuries_list_idx = fighter_idx
        self.roster_view = "detail"

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        # Title
        grid.add_widget(AutoShrinkLabel(
            text=f"{f.name} — {t('injuries_tab')}",
            font_size="11sp", bold=True, color=ACCENT_RED,
            halign="center", size_hint_y=None, height=dp(30),
        ))
        grid.add_widget(AutoShrinkLabel(
            text=f"{t('death_risk')}: {f.death_chance:.0%}",
            font_size="10sp", color=ACCENT_RED,
            halign="center", size_hint_y=None, height=dp(30),
        ))

        # Heal all button
        healable = [i for i, inj in enumerate(f.injuries)
                    if data_loader.injuries_by_id.get(inj["id"], {}).get("heal_cost_multiplier", 1) != 0]
        if len(healable) > 1:
            total_cost = engine.heal_fighter_all_injuries_cost(fighter_idx)
            can_heal_all = total_cost > 0 and engine.gold >= total_cost
            heal_all_btn = MinimalButton(
                text=f"{t('heal_all_injuries_btn')} ({fmt_num(total_cost)})",
                font_size=11, btn_color=ACCENT_GREEN if can_heal_all else BTN_DISABLED,
                text_color=BG_DARK if can_heal_all else TEXT_MUTED,
                size_hint_y=None, height=dp(40),
                icon_source="sprites/icons/ic_gold.png",
            )
            def _heal_all(inst, fi=fighter_idx):
                result = engine.heal_fighter_all_injuries(fi)
                if result.ok:
                    App.get_running_app().show_toast(result.message)
                    if engine.fighters[fi].injury_count > 0:
                        self._show_injuries_view(fi)
                    else:
                        self.show_fighter_detail(fi)
                else:
                    App.get_running_app().show_toast(result.message)
            heal_all_btn.bind(on_press=_heal_all)
            grid.add_widget(heal_all_btn)

        # Individual injuries
        for i_idx, inj in enumerate(f.injuries):
            inj_data = data_loader.injuries_by_id.get(inj["id"], {})
            severity = inj_data.get("severity", "?")
            name = inj_data.get("name", inj["id"])
            is_perm = inj_data.get("heal_cost_multiplier", 1) == 0
            perm_tag = f" {t('permanent_injury_tag')}" if is_perm else ""
            sev_color = ACCENT_RED if severity in ("severe", "permanent") else TEXT_MUTED

            card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(70),
                            padding=[dp(10), dp(6)], spacing=dp(2))
            card.border_color = sev_color

            inj_name_lbl = AutoShrinkLabel(
                text=f"[{severity.upper()}] {name}{perm_tag}",
                font_size="10sp", bold=True, color=sev_color,
                halign="left", size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(inj_name_lbl)
            card.add_widget(inj_name_lbl)

            # Stat penalties summary
            penalties = inj_data.get("stat_penalties", [])
            if penalties:
                pen_parts = []
                for pen in penalties:
                    stat = pen.get("stat", "?").replace("_", " ").upper()
                    val = pen.get("value", 0)
                    pen_parts.append(f"{stat} -{val:.0%}")
                pen_lbl = AutoShrinkLabel(
                    text="  ".join(pen_parts), font_size="11sp",
                    color=ACCENT_RED, halign="left",
                    size_hint_y=None, height=dp(16),
                )
                bind_text_wrap(pen_lbl)
                card.add_widget(pen_lbl)

            if not is_perm:
                heal_cost = f.get_injury_heal_cost(i_idx)
                can_heal = engine.gold >= heal_cost
                heal_btn = MinimalButton(
                    text=f"{t('heal_btn')} {fmt_num(heal_cost)}",
                    font_size=11, btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
                    text_color=BG_DARK if can_heal else TEXT_MUTED,
                    size_hint_y=None, height=dp(28),
                    icon_source="sprites/icons/ic_gold.png",
                )
                def _heal_one(inst, idx=fighter_idx, ii=i_idx):
                    result = engine.heal_fighter_injury(idx, ii)
                    if result.ok:
                        App.get_running_app().show_toast(result.message)
                        if engine.fighters[idx].injury_count > 0:
                            self._show_injuries_view(idx)
                        else:
                            self.show_fighter_detail(idx)
                    else:
                        App.get_running_app().show_toast(result.message)
                heal_btn.bind(on_press=_heal_one)
                card.add_widget(heal_btn)

            card.bind(on_press=lambda inst, iid=inj["id"], fi=fighter_idx:
                      self._show_injury_detail(iid, fi))
            grid.add_widget(card)

    def _show_injury_detail(self, injury_id, fighter_idx):
        """Show full injury info page."""
        from kivy.uix.label import Label
        from game.data_loader import data_loader
        inj_data = data_loader.injuries_by_id.get(injury_id, {})
        if not inj_data:
            return
        self._injury_detail = (injury_id, fighter_idx)
        self.roster_view = "detail"

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        severity = inj_data.get("severity", "?")
        is_perm = inj_data.get("heal_cost_multiplier", 1) == 0
        sev_colors = {
            "minor": TEXT_MUTED, "moderate": ACCENT_GOLD,
            "severe": ACCENT_RED, "permanent": ACCENT_RED,
        }
        sev_color = sev_colors.get(severity, TEXT_MUTED)

        # Name
        grid.add_widget(AutoShrinkLabel(
            text=inj_data.get("name", injury_id), font_size="11sp", bold=True,
            color=sev_color, halign="center",
            size_hint_y=None, height=dp(34),
        ))

        # Severity + body part
        body_part = inj_data.get("body_part", "").replace("_", " ").title()
        tag_text = f"[{severity.upper()}]"
        if is_perm:
            tag_text += f"  {t('permanent_injury_tag')}"
        if body_part:
            tag_text += f"  —  {body_part}"
        grid.add_widget(AutoShrinkLabel(
            text=tag_text, font_size="10sp", color=sev_color,
            halign="center", size_hint_y=None, height=dp(30),
        ))

        # Description
        desc = inj_data.get("description", "")
        if desc:
            desc_lbl = Label(
                text=desc, font_size="11sp", font_name='PixelFont',
                color=TEXT_SECONDARY, halign="left", valign="top", size_hint_y=None,
            )
            desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(16), None)))
            desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)))
            grid.add_widget(desc_lbl)

        # Stat penalties
        penalties = inj_data.get("stat_penalties", [])
        if penalties:
            grid.add_widget(AutoShrinkLabel(
                text=t("class_modifiers_label"), font_size="10sp", bold=True,
                color=ACCENT_RED, halign="left",
                size_hint_y=None, height=dp(26),
            ))
            for pen in penalties:
                stat = pen.get("stat", "?").replace("_", " ").upper()
                val = pen.get("value", 0)
                grid.add_widget(AutoShrinkLabel(
                    text=f"  {stat}  -{val:.0%}", font_size="10sp",
                    color=ACCENT_RED, halign="left",
                    size_hint_y=None, height=dp(30),
                ))

        # Heal info
        if is_perm:
            grid.add_widget(AutoShrinkLabel(
                text=t("no_healable_injuries"), font_size="10sp",
                color=TEXT_MUTED, halign="center",
                size_hint_y=None, height=dp(26),
            ))
        else:
            mult = inj_data.get("heal_cost_multiplier", 1.0)
            grid.add_widget(AutoShrinkLabel(
                text=t("heal_cost_mult", mult=f"{mult:.1f}"), font_size="10sp",
                color=ACCENT_GREEN, halign="center",
                size_hint_y=None, height=dp(26),
            ))

    def _back_from_injury(self):
        idx = getattr(self, '_injury_detail', (None, -1))[1]
        self._injury_detail = None
        if idx >= 0:
            self._show_injuries_view(idx)
        else:
            self.close_detail()

    def heal_all_injuries(self):
        app = App.get_running_app()
        result = app.engine.heal_all_injuries()
        if not result.ok and result.message:
            app.show_toast(result.message)
        self.refresh_roster()
