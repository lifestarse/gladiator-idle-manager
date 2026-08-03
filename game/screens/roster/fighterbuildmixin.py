# Build: 10
"""_FighterBuildMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m

from game.theme import HP_MID, HP_MID_THRESHOLD
from game.constants import LOW_HP_THRESHOLD

_STA_LOW = 20
_FAT_HIGH = 50
_FAT_WARN_CLR = (1, 0.63, 0.25, 1)


class _FighterBuildMixin:
    def _make_help_tappable(self, widget):
        """Bind on_touch_down to a label so tapping it opens the stat-help popup."""
        def _on_touch(inst, touch):
            if inst.collide_point(*touch.pos):
                self._show_fighter_stat_help()
                return True
            return False
        widget.bind(on_touch_down=_on_touch)

    def _show_fighter_stat_help(self, *_):
        """Popup explaining all fighter stats incl. stamina/fatigue."""
        from kivy.uix.scrollview import ScrollView
        from kivy.uix.popup import Popup
        body_lbl = AutoShrinkLabel(
            text=t("fighter_help_body"),
            font_size="11sp", markup=True, color=TEXT_PRIMARY,
            halign="left", valign="top", size_hint_y=None,
        )
        body_lbl.bind(
            width=lambda inst, w: setattr(inst, "text_size", (w - dp(8), None)),
            texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)),
        )
        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(body_lbl)
        wrapper = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(6))
        wrapper.add_widget(scroll)
        close_btn = MinimalButton(
            text=t("help_btn_close"), font_size=12,
            btn_color=ACCENT_GOLD, text_color=BG_DARK,
            size_hint_y=None, height=dp(44),
        )
        wrapper.add_widget(close_btn)
        popup = Popup(
            title=t("fighter_help_title"),
            title_color=ACCENT_GOLD, title_size="12sp",
            content=wrapper, size_hint=(0.94, 0.85),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_GOLD,
        )
        close_btn.bind(on_release=lambda *_: popup.dismiss())
        popup.open()

    # Faster repeat than the gold-spending Train button: stat points are
    # already earned, so burning through them should feel immediate.
    _HOLD_INTERVAL = 0.06

    def _wire_hold_to_train(self, btn, stat_key, fighter_idx, fighter,
                            engine, stat_labels, pts_label_widget):
        """Tap fires once; press-and-hold repeats. During hold only the
        affected labels are patched in-place (a grid rebuild would destroy
        the held button); canonical refresh + save run on release."""
        total_attr = {
            "strength": "total_strength",
            "agility": "total_agility",
            "vitality": "total_vitality",
        }[stat_key]
        state = {"dirty": False}

        def _refresh_labels():
            lbl, sname = stat_labels[stat_key]
            lbl.text = f"{sname} {getattr(fighter, total_attr)}"
            if pts_label_widget is not None:
                pts_label_widget.text = t("pts_label", n=fighter.unused_points)

        def _step():
            result = engine.distribute_stat(fighter_idx, stat_key)
            if not result.ok:
                return False
            state["dirty"] = True
            _refresh_labels()
            return fighter.unused_points > 0

        def _finish():
            if state["dirty"]:
                state["dirty"] = False
                engine.save()
                self.refresh_roster()
                self.show_fighter_detail(fighter_idx)

        bind_hold_repeat(btn, _step, _finish, interval=self._HOLD_INTERVAL)

    def _stat_cell(self, caption, value, value_color=None):
        """Muted caption over a value — one cell of the stat plate."""
        cell = BoxLayout(orientation="vertical", spacing=dp(1))
        cap = AutoShrinkLabel(
            text=caption, font_size="8sp", color=TEXT_SECONDARY,
            halign="center", valign="bottom", single_line=True,
            size_hint_y=None, height=dp(14),
        )
        bind_text_wrap(cap)
        val = AutoShrinkLabel(
            text=str(value), font_size="11sp", bold=True,
            color=list(value_color) if value_color else list(TEXT_PRIMARY),
            halign="center", valign="top", single_line=True,
        )
        bind_text_wrap(val)
        cell.add_widget(cap)
        cell.add_widget(val)
        return cell

    def _build_stat_plate(self, f):
        """Aligned 3-column stat grid. Replaces three centred markup lines
        where every number had its own colour and long values wrapped."""
        from kivy.uix.gridlayout import GridLayout
        from kivy.uix.widget import Widget
        plate = BaseCard(orientation="vertical", size_hint_y=None,
                         height=dp(126), padding=[dp(10), dp(8)])
        inner = GridLayout(cols=3, spacing=dp(4))

        hp_pct = f.hp / max(1, f.max_hp)
        hp_clr = (HP_PLAYER if hp_pct >= HP_MID_THRESHOLD
                  else HP_MID if hp_pct >= LOW_HP_THRESHOLD else ACCENT_RED)
        inner.add_widget(self._stat_cell("ATK", fmt_num(f.attack)))
        inner.add_widget(self._stat_cell("DEF", fmt_def(f.defense)))
        inner.add_widget(self._stat_cell(
            "HP", f"{fmt_num(f.hp)}/{fmt_num(f.max_hp)}", hp_clr))

        sta_clr = HP_MID if f.stamina <= _STA_LOW else None
        if f.is_exhausted:
            fat_clr = ACCENT_RED
        elif f.fatigue >= _FAT_HIGH:
            fat_clr = _FAT_WARN_CLR
        else:
            fat_clr = None
        inner.add_widget(self._stat_cell("CRIT", f"{f.crit_chance:.0%}"))
        inner.add_widget(self._stat_cell("DODGE", f"{f.dodge_chance:.0%}"))
        inner.add_widget(self._stat_cell(
            t("stamina_label"), f"{f.stamina}/100", sta_clr))

        inner.add_widget(self._stat_cell(
            t("fatigue_label"), f"{f.fatigue}/100", fat_clr))
        if f.is_exhausted:
            inner.add_widget(self._stat_cell("", t("exhausted_tag"),
                                             ACCENT_RED))
        else:
            inner.add_widget(Widget())
        inner.add_widget(Widget())

        plate.add_widget(inner)
        self._make_help_tappable(plate)
        return plate

    def _build_fighter_header(self, grid, f, index, engine):
        """Add name/stats/attribute rows to detail grid."""
        header_lbl = AutoShrinkLabel(
            text=f"{f.name}  [{f.class_name}]  Lv.{f.level}", font_size="13sp", bold=True,
            color=ACCENT_GOLD, size_hint_y=None, height=dp(44), halign="center",
        )
        bind_text_wrap(header_lbl)
        grid.add_widget(header_lbl)

        grid.add_widget(self._build_stat_plate(f))

        stat_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        has_pts = f.unused_points > 0 and f.available
        stat_labels = {}
        pending_buttons = []
        for stat_name, stat_val, color, stat_key in [
            ("STR", f.total_strength, ACCENT_RED, "strength"),
            ("AGI", f.total_agility, ACCENT_GREEN, "agility"),
            ("VIT", f.total_vitality, ACCENT_BLUE, "vitality"),
        ]:
            cell = BoxLayout(spacing=dp(2))
            lbl = AutoShrinkLabel(text=f"{stat_name} {stat_val}", font_size="11sp",
                        color=color, halign="center", bold=True)
            bind_text_wrap(lbl)
            self._make_help_tappable(lbl)
            cell.add_widget(lbl)
            stat_labels[stat_key] = (lbl, stat_name)
            if has_pts:
                btn = MinimalButton(text="+", btn_color=color, text_color=BG_DARK,
                                    font_size=11, size_hint_x=0.4)
                pending_buttons.append((btn, stat_key))
                cell.add_widget(btn)
            stat_row.add_widget(cell)
        grid.add_widget(stat_row)

        pts_label_widget = None
        if has_pts:
            pts_label_widget = AutoShrinkLabel(
                text=t("pts_label", n=f.unused_points), font_size="11sp",
                color=ACCENT_GOLD, size_hint_y=None, height=dp(30), halign="center",
            )
            grid.add_widget(pts_label_widget)

        for btn, stat_key in pending_buttons:
            self._wire_hold_to_train(
                btn, stat_key, index, f, engine, stat_labels, pts_label_widget,
            )

        if f.alive:
            auto_on = bool(getattr(f, "auto_distribute_enabled", False))
            auto_label = t("auto_distribute_on") if auto_on else t("auto_distribute_off")
            auto_btn = MinimalButton(
                text=auto_label, font_size=11,
                variant="primary" if auto_on else "secondary",
                btn_color=ACCENT_GOLD if auto_on else ACCENT_BLUE,
                text_color=BG_DARK if auto_on else TEXT_PRIMARY,
                size_hint_y=None, height=dp(40),
            )
            def _toggle_auto(inst, idx=index):
                fi = engine.fighters[idx]
                engine.set_auto_distribute(idx, not fi.auto_distribute_enabled)
                self.refresh_roster()
                self.show_fighter_detail(idx)
            auto_btn.bind(on_press=_toggle_auto)
            grid.add_widget(auto_btn)

