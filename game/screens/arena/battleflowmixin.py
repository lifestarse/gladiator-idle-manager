# Build: 4
"""ArenaScreen _BattleFlowMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _BattleFlowMixin:
    def _turn_interval(self):
        """Seconds between auto turns — base interval over speed multiplier.

        Falls back to x1 for a speed the account has not unlocked, so a
        persisted multiplier can never outrun the level gate.
        """
        engine = App.get_running_app().engine
        speed = getattr(engine, 'battle_speed', 1)
        if speed not in self._allowed_speeds():
            speed = 1
        return BATTLE_AUTO_INTERVAL / speed

    def toggle_auto_battle(self):
        """One button, two states: start the auto battle / flee from it.

        A tap aimed at STOP can land just after the battle resolved on that
        same Clock tick (the flip to is_fighting=False happens before touch
        dispatch in the frame loop) — at x4 that window is hit routinely.
        Without the guard the tap would take the start branch and launch the
        next fight, which on the defeat path means charging straight into
        the revenge wave the player was trying to escape.
        """
        if self.is_fighting:
            self.stop_battle()
            return
        since_end = Clock.get_time() - self._battle_end_time
        if since_end < BATTLE_END_TAP_GUARD:
            return
        self.start_auto_battle()

    def stop_battle(self):
        """Flee: cancel the in-progress battle. Damage stays and the gold
        banked during the fight is forfeited — see stop_auto_battle."""
        engine = App.get_running_app().engine
        Clock.unschedule(self._auto_turn)
        if engine.battle_active and engine.stop_auto_battle():
            lost = getattr(engine, 'last_flee_forfeit', 0)
            if lost > 0:
                self._ticker(t("battle_fled_cost", g=fmt_num(lost)),
                             ACCENT_RED)
                self._spawn_float(f"-{fmt_num(lost)} G", ACCENT_RED)
            else:
                self._ticker(t("battle_fled"), ACCENT_RED)
        self.is_fighting = False
        self._battle_end_time = Clock.get_time()
        self.refresh_ui()

    def _allowed_speeds(self):
        """Speed multipliers the account level has unlocked. x1 is free."""
        engine = App.get_running_app().engine
        return [s for s in BATTLE_SPEED_OPTIONS
                if s == 1 or engine.is_unlocked(f"battle_speed_x{s}")]

    def cycle_battle_speed(self):
        """x1 → x2 → x4 → x1 across unlocked speeds only. Persisted;
        reschedules a running battle so the change is felt immediately."""
        engine = App.get_running_app().engine
        opts = self._allowed_speeds()
        if len(opts) == 1:
            nxt = next((s for s in BATTLE_SPEED_OPTIONS if s > 1), None)
            if nxt is not None:
                App.get_running_app().show_toast(t(
                    "feature_locked",
                    n=engine.unlock_level_for(f"battle_speed_x{nxt}")))
            return
        cur = getattr(engine, 'battle_speed', 1)
        idx = opts.index(cur) if cur in opts else 0
        engine.battle_speed = opts[(idx + 1) % len(opts)]
        self.speed_text = f"x{engine.battle_speed}"
        if self.is_fighting and engine.battle_active:
            Clock.unschedule(self._auto_turn)
            Clock.schedule_interval(self._auto_turn, self._turn_interval())
        engine.save_async()

    def start_auto_battle(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        # No available fighters: bail before flipping is_fighting / scheduling
        # the turn loop. The kv-side button is greyed out via
        # has_available_fighters, but a stale tap (e.g. via shortcut) could
        # still land here; show a toast so the user knows why nothing
        # happened instead of silently no-op'ing.
        if not any(f.available for f in engine.fighters):
            self._spawn_float(t("battle_no_fighters"), ACCENT_RED)
            return
        self.is_fighting = True
        if self.arena_mode == "boss":
            events = engine.start_boss_fight()
            self._ticker(t("boss_challenge"), ACCENT_RED)
        else:
            # Check if boss is lurking in regular battle
            has_boss = (engine.current_enemy
                        and getattr(engine.current_enemy, 'is_boss', False))
            events = engine.start_auto_battle()
            self._ticker(t("auto_battle"), ACCENT_GOLD)
            if has_boss:
                self._show_boss_revenge_popup(engine.current_enemy.name)
        self._display_events(events)
        Clock.schedule_interval(self._auto_turn, self._turn_interval())

    def toggle_arena_mode(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        if not engine.is_unlocked("arena_boss"):
            App.get_running_app().show_toast(
                t("feature_locked", n=engine.unlock_level_for("arena_boss")))
            return
        if self.arena_mode == "common":
            self.arena_mode = "boss"
            engine.spawn_boss_enemy()
        else:
            self.arena_mode = "common"
            engine._spawn_enemy()
        self.refresh_ui()

    def next_turn(self):
        engine = App.get_running_app().engine
        if not engine.battle_active:
            return
        events = engine.battle_next_turn()
        self._display_events(events)
        self._check_battle_end(engine)
        self.refresh_ui()

    def skip_battle(self):
        engine = App.get_running_app().engine
        if not engine.battle_active:
            return
        Clock.unschedule(self._auto_turn)
        events = engine.battle_skip()
        self._display_events(events)
        self._check_battle_end(engine)
        self.refresh_ui()

    def _auto_turn(self, dt):
        engine = App.get_running_app().engine
        if not engine.battle_active:
            Clock.unschedule(self._auto_turn)
            # Battle ended outside our control (a squad script cancelled it
            # from the worker thread). Clear the flag or the action button
            # stays stuck showing STOP for a fight that no longer exists.
            self.is_fighting = False
            self._check_pending_reset()
            return
        events = engine.battle_next_turn()
        self._display_events(events)
        self._check_battle_end(engine)
        self.refresh_ui()

    def _check_battle_end(self, engine):
        state = engine.battle_mgr.state
        if state.phase == BattlePhase.VICTORY:
            Clock.unschedule(self._auto_turn)
            self.is_fighting = False
            self._battle_end_time = Clock.get_time()
            self._victory_flash()
            if state.is_boss_fight:
                # Boss down → tier already advanced by _declare_victory;
                # engine.arena_tier is the NEW tier. The big moment gets
                # a popup instead of a transient banner — but a Popup is
                # window-level, so defer it when the player has navigated
                # away mid-fight (the battle Clock keeps running). Same
                # deferral shape as the pending-reset popup.
                if App.get_running_app().sm.current == self.name:
                    self._show_tier_up_popup(engine.arena_tier,
                                             state.gold_earned)
                else:
                    self._pending_tier_up = (engine.arena_tier,
                                             state.gold_earned)
            else:
                # Victory == full clear, so kills = enemy count.
                self._show_victory_banner(state.gold_earned,
                                          len(state.enemies))
            # Re-spawn enemy matching current mode
            if self.arena_mode == "boss":
                engine.spawn_boss_enemy()
            else:
                engine._spawn_enemy()
            if engine.should_show_interstitial():
                ad_manager.show_interstitial()
            if engine.wins % 10 == 0:
                engine.submit_scores()
        elif state.phase == BattlePhase.DEFEAT:
            Clock.unschedule(self._auto_turn)
            self.is_fighting = False
            self._battle_end_time = Clock.get_time()
            self._defeat_flash()
            self._spawn_float(t("defeat"), ACCENT_RED)
            Clock.schedule_once(lambda dt: self._check_pending_reset(), 1.0)

    def _display_events(self, events):
        for ev in events[-6:]:
            # Kill/skill messages go to the divider ticker — the old
            # centre-screen floats rendered on top of the unit cards.
            if ev.event_type == "skill":
                self._ticker(ev.message, ACCENT_CYAN)
            elif ev.is_kill:
                self._ticker(ev.message, ACCENT_RED)

            # Boss intro — dramatic banner with the boss name. The engine
            # emitted this event all along; the UI just ignored it.
            if ev.event_type == "boss_intro":
                bm = getattr(App.get_running_app().engine,
                             "battle_mgr", None)
                enemies = getattr(getattr(bm, "state", None), "enemies", [])
                boss_name = enemies[0].name if enemies else ""
                self._show_boss_banner(boss_name)

            # Animate attacker sprite on attack
            if ev.event_type == "attack" and ev.damage > 0 and ev.attacker:
                widget = self._find_unit_view(ev.attacker, is_player=not ev.is_boss)
                if widget is not None:
                    self._set_sprite_frame(widget, "attack", revert_delay=0.3)

            # Damage number + HP bar flash on the defender's card
            if ev.event_type == "attack" and ev.damage > 0 and ev.defender:
                is_player = any(
                    f.name == ev.defender
                    for f in getattr(
                        getattr(App.get_running_app().engine, "battle_mgr", None),
                        "state", type("", (), {"player_fighters": []})
                    ).player_fighters
                    if hasattr(f, "name")
                )
                self._spawn_damage(ev.defender, is_player, ev.damage,
                                   is_crit=getattr(ev, "is_crit", False))
                self._flash_damage(ev.defender, is_player)

            # Play sword sound on attack
            if ev.event_type == "attack" and ev.damage > 0:
                _play_hit_sound()
