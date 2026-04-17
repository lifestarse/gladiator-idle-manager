# Build: 1
"""ArenaScreen _BattleFlowMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _BattleFlowMixin:
    def start_auto_battle(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        self.is_fighting = True
        if self.arena_mode == "boss":
            events = engine.start_boss_fight()
            self._spawn_float(t("boss_challenge"), ACCENT_RED)
        else:
            # Check if boss is lurking in regular battle
            has_boss = (engine.current_enemy
                        and getattr(engine.current_enemy, 'is_boss', False))
            events = engine.start_auto_battle()
            self._spawn_float(t("auto_battle"), ACCENT_GOLD)
            if has_boss:
                self._show_boss_revenge_popup(engine.current_enemy.name)
        self._display_events(events)
        Clock.schedule_interval(self._auto_turn, BATTLE_AUTO_INTERVAL)

    def toggle_arena_mode(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
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
            self._spawn_float(f"{t('victory')} +{fmt_num(state.gold_earned)}", ACCENT_GOLD)
            self._victory_flash()
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
            self._spawn_float(t("defeat"), ACCENT_RED)
            Clock.schedule_once(lambda dt: self._check_pending_reset(), 1.0)

    def _display_events(self, events):
        for ev in events[-6:]:
            # Floating text for key events
            if ev.event_type == "skill":
                self._spawn_float(ev.message, ACCENT_CYAN)
            elif ev.is_kill:
                self._spawn_float(ev.message, ACCENT_RED)

            # Animate attacker sprite on attack
            if ev.event_type == "attack" and ev.damage > 0 and ev.attacker:
                widget = self._find_unit_view(ev.attacker, is_player=not ev.is_boss)
                if widget is not None:
                    self._set_sprite_frame(widget, "attack", revert_delay=0.3)

            # Flash HP bar of defender on hit
            if ev.event_type == "attack" and ev.damage > 0 and ev.defender:
                is_player = any(
                    f.name == ev.defender
                    for f in getattr(
                        getattr(App.get_running_app().engine, "battle_mgr", None),
                        "state", type("", (), {"player_fighters": []})
                    ).player_fighters
                    if hasattr(f, "name")
                )
                self._flash_damage(ev.defender, is_player)

            # Play sword sound on attack
            if ev.event_type == "attack" and ev.damage > 0:
                _play_hit_sound()
