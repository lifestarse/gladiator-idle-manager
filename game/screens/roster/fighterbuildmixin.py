# Build: 8
"""_FighterBuildMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


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

    _HOLD_DELAY = 0.35
    _HOLD_INTERVAL = 0.06

    def _wire_hold_to_train(self, btn, stat_key, fighter_idx, fighter,
                            engine, stat_labels, pts_label_widget):
        """Bind tap-fires-once + press-and-hold-repeats to a stat-add button.

        During hold we mutate the fighter and patch only the affected
        labels in-place. Rebuilding the detail grid mid-hold would destroy
        the button being touched, breaking the gesture; the canonical
        refresh + save runs once on release.
        """
        total_attr = {
            "strength": "total_strength",
            "agility": "total_agility",
            "vitality": "total_vitality",
        }[stat_key]
        state = {"hold_event": None, "delay_event": None, "dirty": False}

        def _refresh_labels():
            lbl, sname = stat_labels[stat_key]
            lbl.text = f"{sname} {getattr(fighter, total_attr)}"
            if pts_label_widget is not None:
                pts_label_widget.text = t("pts_label", n=fighter.unused_points)

        def _tick(dt):
            result = engine.distribute_stat(fighter_idx, stat_key)
            if not result.ok:
                _stop()
                return False
            state["dirty"] = True
            _refresh_labels()
            if fighter.unused_points <= 0:
                _stop()
                return False
            return True

        def _start_repeat(dt):
            state["delay_event"] = None
            state["hold_event"] = Clock.schedule_interval(
                _tick, self._HOLD_INTERVAL,
            )

        def _stop():
            if state["delay_event"]:
                state["delay_event"].cancel()
                state["delay_event"] = None
            if state["hold_event"]:
                state["hold_event"].cancel()
                state["hold_event"] = None

        def _on_press(_inst):
            _tick(0)
            if fighter.unused_points > 0:
                state["delay_event"] = Clock.schedule_once(
                    _start_repeat, self._HOLD_DELAY,
                )

        def _on_release(_inst):
            _stop()
            if state["dirty"]:
                state["dirty"] = False
                engine.save()
                self.refresh_roster()
                self.show_fighter_detail(fighter_idx)

        btn.bind(on_press=_on_press, on_release=_on_release)

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
            f"[color=#{bc}]DEF {fmt_def(f.defense)}[/color]   "
            f"[color=#{gc}]HP {fmt_num(f.hp)}/{fmt_num(f.max_hp)}[/color]"
        )
        stats_lbl = AutoShrinkLabel(
            text=atk_text, font_size="11sp", markup=True, color=TEXT_SECONDARY,
            size_hint_y=None, height=dp(30), halign="center",
        )
        bind_text_wrap(stats_lbl)
        self._make_help_tappable(stats_lbl)
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
        self._make_help_tappable(crit_lbl)
        grid.add_widget(crit_lbl)

        # Stamina / Fatigue row + lock indicator if exhausted.
        sta_color = "ffd040" if f.stamina <= 20 else "80ff80"
        if f.is_exhausted:
            fat_color = "ff4040"
            fat_suffix = f"  [color=#ff4040][b]🔒 {t('exhausted_tag')}[/b][/color]"
        elif f.fatigue >= 50:
            fat_color = "ffa040"
            fat_suffix = ""
        else:
            fat_color = "9090a0"
            fat_suffix = ""
        sf_text = (
            f"[color=#{sta_color}]{t('stamina_label')} {f.stamina}/100[/color]   "
            f"[color=#{fat_color}]{t('fatigue_label')} {f.fatigue}/100[/color]"
            f"{fat_suffix}"
        )
        sf_lbl = AutoShrinkLabel(
            text=sf_text, font_size="11sp", markup=True, color=TEXT_SECONDARY,
            size_hint_y=None, height=dp(28), halign="center",
        )
        bind_text_wrap(sf_lbl)
        self._make_help_tappable(sf_lbl)
        grid.add_widget(sf_lbl)

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
                btn_color=ACCENT_GOLD if auto_on else BTN_PRIMARY,
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

