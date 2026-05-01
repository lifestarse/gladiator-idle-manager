# Build: 2
"""_ActionsBuildMixin — fighter detail action buttons (train/skills/perks/etc).

Split from fighterbuildmixin.py to keep both files under the 10KB src
limit (CLAUDE.md). Renders the bottom-of-detail control stack: kills
label, injuries entry, bench toggle, skills/perk-tree links, train
button, dismiss.
"""
from ._screen_imports import *  # noqa: F401,F403


class _ActionsBuildMixin:

    _TRAIN_HOLD_DELAY = 0.35
    _TRAIN_HOLD_INTERVAL = 0.10

    def _wire_hold_to_train_level(self, btn, fighter, fighter_idx, engine):
        """Press-and-hold repeat for the Train (level-up) button.

        Each tick spends gold for one level via engine.upgrade_gladiator.
        Stops when not_enough_gold or fighter unavailable. During hold we
        update only the button text (lv/cost) and the top-bar gold readout
        in place; full ATK/DEF/HP refresh runs once on release. Slower
        interval (100ms) than stat-add: each level is a meaningful
        commitment of gold.
        """
        state = {"hold_event": None, "delay_event": None, "dirty": False}

        def _patch_btn():
            if not fighter.available:
                return
            cost = fighter.upgrade_cost
            can_train = engine.gold >= cost
            btn.text = t("train_btn", lv=fighter.level + 1, cost=fmt_num(cost))
            btn.btn_color = ACCENT_GOLD if can_train else BTN_DISABLED
            btn.text_color = BG_DARK if can_train else TEXT_MUTED
            self.gold_text = fmt_num(engine.gold)

        def _tick(dt):
            result = engine.upgrade_gladiator(fighter_idx)
            if not result.ok:
                _stop()
                return False
            state["dirty"] = True
            _patch_btn()
            return True

        def _start_repeat(dt):
            state["delay_event"] = None
            state["hold_event"] = Clock.schedule_interval(
                _tick, self._TRAIN_HOLD_INTERVAL,
            )

        def _stop():
            if state["delay_event"]:
                state["delay_event"].cancel()
                state["delay_event"] = None
            if state["hold_event"]:
                state["hold_event"].cancel()
                state["hold_event"] = None

        def _on_press(_inst):
            result = engine.upgrade_gladiator(fighter_idx)
            if not result.ok:
                if result.message:
                    App.get_running_app().show_toast(result.message)
                return
            state["dirty"] = True
            _patch_btn()
            state["delay_event"] = Clock.schedule_once(
                _start_repeat, self._TRAIN_HOLD_DELAY,
            )

        def _on_release(_inst):
            _stop()
            if state["dirty"]:
                state["dirty"] = False
                self.refresh_roster()
                self.show_fighter_detail(fighter_idx)

        btn.bind(on_press=_on_press, on_release=_on_release)

    def _build_fighter_actions(self, grid, f, index, engine):
        """Add kills label, injuries button, and action buttons to detail grid."""
        grid.add_widget(AutoShrinkLabel(
            text=t("kills_label", n=f.kills), font_size="11sp", color=TEXT_MUTED,
            size_hint_y=None, height=dp(32), halign="center",
        ))

        if f.injury_count > 0:
            inj_btn = MinimalButton(
                text=f"{t('injuries_tab')} ({f.injury_count})  —  {t('death_risk')}: {f.death_chance:.0%}",
                font_size=11, btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(48),
            )
            inj_btn.bind(on_press=lambda inst, idx=index: self._show_injuries_view(idx))
            grid.add_widget(inj_btn)

        if f.alive and not f.on_expedition:
            benched = not f.is_active
            bench_btn = MinimalButton(
                text=t("activate_btn") if benched else t("bench_btn"),
                font_size=11,
                btn_color=ACCENT_GOLD if benched else BTN_PRIMARY,
                text_color=BG_DARK if benched else TEXT_PRIMARY,
                size_hint_y=None, height=dp(48),
            )
            def _toggle_bench(inst, idx=index):
                fi = engine.fighters[idx]
                fi.is_active = not fi.is_active
                engine.refresh_arena_preview()
                engine._mark_dirty()
                self.refresh_roster()
                self.show_fighter_detail(idx)
            bench_btn.bind(on_press=_toggle_bench)
            grid.add_widget(bench_btn)

        skills_btn = MinimalButton(
            text=t("skills_btn"), font_size=11,
            btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(48),
        )
        skills_btn.bind(on_press=lambda inst, idx=index: self._show_skills_view(idx))
        grid.add_widget(skills_btn)

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
            self._wire_hold_to_train_level(train_btn, f, index, engine)
            grid.add_widget(train_btn)

        dismiss_btn = MinimalButton(
            text=t("dismiss_btn"), font_size=11,
            btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(48),
        )
        dismiss_btn.bind(on_press=lambda inst, idx=index: self._confirm_dismiss(idx))
        grid.add_widget(dismiss_btn)
