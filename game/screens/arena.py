# Build: 4
import math
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.metrics import dp, sp
from kivy.core.window import Window
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, FloatingText, BaseCard
from game.models import fmt_num
from game.theme import *
from game.theme import popup_color
from game.constants import (
    HEAL_GOLD_PER_HP, BATTLE_AUTO_INTERVAL, POPUP_DISMISS_DELAY,
)
from kivy.animation import Animation
from game.battle import BattlePhase
from game.localization import t
from game.ads import ad_manager
from game.leaderboard import leaderboard_manager
from game.ui_helpers import (
    refresh_battle_log,
    build_fighter_pit_card, build_enemy_hp_row,
    update_fighter_pit_card, update_enemy_hp_row,
    flash_hp_bar,
    bind_text_wrap,
)
from game.screens.shared import _safe_clear, _safe_rebind, _play_hit_sound


class ArenaScreen(BaseScreen):
    tier_text = StringProperty("TIER 1")
    battle_status = StringProperty("")
    battle_log_text = StringProperty("")
    player_summary = StringProperty("")
    enemy_summary = StringProperty("")
    arena_mode = StringProperty("common")
    arena_view = StringProperty("battle")  # "battle" or "enemy_detail"
    is_fighting = BooleanProperty(False)
    player_hp_pct = NumericProperty(1.0)
    enemy_hp_pct = NumericProperty(1.0)
    best_text = StringProperty("Best: ---")
    run_text = StringProperty("Run #1 \u00b7 0 kills")

    def on_enter(self):
        app = App.get_running_app()
        if not app or not app.root:
            return
        self.refresh_ui()
        self._check_tutorial()
        self._check_pending_reset()

    def refresh_ui(self):
        engine = App.get_running_app().engine
        self._update_top_bar()
        self.tier_text = f"TIER {engine.arena_tier}"
        if not self.battle_status:
            self.battle_status = ""

        # Record & run
        if engine.best_record_tier > 0:
            self.best_text = f"Best: T{engine.best_record_tier} \u00b7 {engine.best_record_kills} kills"
        else:
            self.best_text = "Best: ---"
        self.run_text = f"Run #{engine.run_number} \u00b7 {engine.run_kills} kills"

        fighters = [f for f in engine.fighters if f.available]
        self.player_summary = t("fighters_ready", n=len(fighters))

        if engine.battle_active:
            s = engine.battle_mgr.state
            alive_f = sum(1 for f in s.player_fighters if f.alive and f.hp > 0)
            alive_e = sum(1 for e in s.enemies if e.hp > 0)
            self.player_summary = t("fighters_alive", n=alive_f)
            self.enemy_summary = t("enemies_left", n=alive_e)
            total_hp = sum(max(0, f.hp) for f in s.player_fighters if f.alive)
            total_max = sum(f.max_hp for f in s.player_fighters if f.alive) or 1
            self.player_hp_pct = total_hp / total_max
            total_ehp = sum(max(0, e.hp) for e in s.enemies)
            total_emax = sum(e.max_hp for e in s.enemies) or 1
            self.enemy_hp_pct = total_ehp / total_emax
        else:
            self.player_hp_pct = 1.0
            self.enemy_hp_pct = 1.0
            e = engine.current_enemy
            self.enemy_summary = f"{e.name} T{e.tier}" if e else ""

        self._refresh_battle_panels(engine)

    def _refresh_battle_panels(self, engine):
        fg = self.ids.get("battle_fighters_grid")
        eg = self.ids.get("battle_enemies_grid")
        hb = self.ids.get("heal_btn_box")
        if not fg or not eg:
            return

        if engine.battle_active:
            s = engine.battle_mgr.state
            fighters_list = [f for f in s.player_fighters if f.alive and f.hp > 0]
            alive_enemies = list(s.enemies)

            # Fast path: if cached widgets match, update in-place
            if self._try_fast_update(fighters_list, alive_enemies, engine):
                return

            # Slow path: full rebuild (battle start, fighter/enemy count changed)
            fg.clear_widgets()
            eg.clear_widgets()
            if hb:
                hb.clear_widgets()
            self._fighter_bar_map = {}
            self._enemy_bar_map = {}
            self._cached_fighter_names = []
            self._cached_enemy_names = []

            heal_btn = self._build_heal_btn(fighters_list, self._heal_all_battle)
            if hb:
                hb.add_widget(heal_btn)
            self._cached_heal_btn = heal_btn

            for i, f in enumerate(fighters_list):
                card = build_fighter_pit_card(
                    f, on_tap=lambda w, idx=i: self.heal_fighter(idx),
                )
                self._fighter_bar_map[f.name] = card
                self._cached_fighter_names.append(f.name)
                fg.add_widget(card)

            for e in alive_enemies:
                row = build_enemy_hp_row(
                    e, show_stats=True,
                    on_tap=lambda w, en=e: self._show_enemy_popup(en),
                )
                self._enemy_bar_map[e.name] = row
                self._cached_enemy_names.append(e.name)
                eg.add_widget(row)
        else:
            # Outside battle — always rebuild (runs rarely, ~1/s via idle_tick)
            fg.clear_widgets()
            eg.clear_widgets()
            if hb:
                hb.clear_widgets()
            self._fighter_bar_map = {}
            self._enemy_bar_map = {}
            self._cached_fighter_names = []
            self._cached_enemy_names = []

            fighters_list = [f for f in engine.fighters if f.available]
            heal_btn = self._build_heal_btn(fighters_list, self._heal_all_outside)
            if hb:
                hb.add_widget(heal_btn)

            for idx_f, f in enumerate(fighters_list):
                card = build_fighter_pit_card(
                    f, on_tap=lambda w, fi=idx_f: self._heal_outside_battle(fi),
                )
                self._fighter_bar_map[f.name] = card
                fg.add_widget(card)

            e = engine.current_enemy
            if e:
                row = build_enemy_hp_row(
                    e, show_stats=True,
                    on_tap=lambda w, en=e: self._show_enemy_popup(en),
                )
                self._enemy_bar_map[e.name] = row
                eg.add_widget(row)

    def _try_fast_update(self, fighters_list, alive_enemies, engine):
        """Update existing widgets in-place. Returns True if successful."""

        cached_f = getattr(self, "_cached_fighter_names", [])
        cached_e = getattr(self, "_cached_enemy_names", [])
        current_f = [f.name for f in fighters_list]
        current_e = [e.name for e in alive_enemies]

        if cached_f != current_f or cached_e != current_e:
            return False

        # Update heal button
        heal_btn = getattr(self, "_cached_heal_btn", None)
        if heal_btn:
            any_damaged = any(f.hp < f.max_hp for f in fighters_list)
            total_heal_cost = engine.get_hp_heal_cost(fighters_list)
            can_heal = total_heal_cost > 0 and engine.gold > 0 and any_damaged
            heal_btn.text = t("heal_all_cost", cost=f"{fmt_num(total_heal_cost)}") if any_damaged else t("heal_all")
            heal_btn.btn_color = ACCENT_GREEN if can_heal else BTN_DISABLED
            heal_btn.text_color = BG_DARK if can_heal else TEXT_MUTED

        # Update fighter cards
        for f in fighters_list:
            card = self._fighter_bar_map.get(f.name)
            if card:
                update_fighter_pit_card(card, f)

        # Update enemy HP bars
        for e in alive_enemies:
            row = self._enemy_bar_map.get(e.name)
            if row:
                update_enemy_hp_row(row, e)

        return True

    def _heal_single_fighter(self, fighter_idx, in_battle):
        """Heal a single fighter's HP. Works both in and outside battle."""
        engine = App.get_running_app().engine
        if in_battle:
            if not engine.battle_active:
                return
            fighters = engine.battle_mgr.state.player_fighters
        else:
            if engine.battle_active:
                return
            fighters = engine.fighters
        if not (0 <= fighter_idx < len(fighters)):
            return
        f = fighters[fighter_idx]
        if not (f.alive and f.hp > 0 and f.hp < f.max_hp):
            return
        missing = f.max_hp - f.hp
        cost = math.ceil(missing / HEAL_GOLD_PER_HP)
        if engine.gold >= cost:
            engine.gold -= cost
            f.hp = f.max_hp
        elif engine.gold > 0:
            heal_hp = int(engine.gold * HEAL_GOLD_PER_HP)
            engine.gold = 0
            f.hp = min(f.max_hp, f.hp + heal_hp)
        else:
            App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(cost)))
            return
        self.battle_status = f"Healed {f.name}"
        if not in_battle:
            engine.save()
        self.refresh_ui()

    def heal_fighter(self, fighter_idx):
        self._heal_single_fighter(fighter_idx, in_battle=True)

    def _heal_outside_battle(self, fighter_idx):
        self._heal_single_fighter(fighter_idx, in_battle=False)

    def _heal_all(self, in_battle):
        """Heal all fighters' HP. Works both in and outside battle."""
        engine = App.get_running_app().engine
        if in_battle:
            if not engine.battle_active:
                return
            fighters = engine.battle_mgr.state.player_fighters
        else:
            if engine.battle_active:
                return
            fighters = [f for f in engine.fighters if f.available]
        total_cost = engine.get_hp_heal_cost(fighters)
        healed, spent = engine.heal_all_hp(fighters)
        if healed > 0:
            self.battle_status = f"Healed {healed} fighters (-{spent}g)"
            self.refresh_ui()
        elif total_cost > 0:
            App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(total_cost)))

    def _heal_all_battle(self):
        self._heal_all(in_battle=True)

    def _heal_all_outside(self):
        self._heal_all(in_battle=False)

    def _build_heal_btn(self, fighters_list, callback):
        """Build the Heal All button with correct cost/state for given fighters."""
        engine = App.get_running_app().engine
        any_damaged = any(f.hp < f.max_hp for f in fighters_list)
        total_heal_cost = engine.get_hp_heal_cost(fighters_list)
        can_heal = total_heal_cost > 0 and engine.gold > 0 and any_damaged
        btn = MinimalButton(
            text=t("heal_all_cost", cost=fmt_num(total_heal_cost)) if any_damaged else t("heal_all"),
            btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
            text_color=BG_DARK if can_heal else TEXT_MUTED,
            font_size=16, size_hint_y=None, height=dp(40),
            icon_source="icons/ic_gold.png",
        )
        btn.bind(on_press=lambda inst: callback())
        return btn

    def _show_enemy_popup(self, enemy):
        """Show enemy stats as inline view replacing battle UI."""
        self.arena_view = "enemy_detail"
        grid = self.ids.get("enemy_detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        is_boss = getattr(enemy, 'is_boss', False)
        border = ACCENT_PURPLE if is_boss else ACCENT_RED
        name_prefix = "BOSS: " if is_boss else ""

        def _lbl(text, size=sp(16), bold=False, color=None):
            lbl = AutoShrinkLabel(
                text=text, font_size=size, bold=bold,
                color=color or border,
                halign="center", valign="middle",
                size_hint_y=None, height=dp(32),
            )
            bind_text_wrap(lbl)
            return lbl

        grid.add_widget(_lbl(f"{name_prefix}{enemy.name}", sp(26), bold=True))
        grid.add_widget(_lbl(f"Tier {enemy.tier}", sp(14), color=TEXT_MUTED))
        grid.add_widget(_lbl(
            f"HP  {fmt_num(enemy.max_hp)}", sp(18), bold=True))
        grid.add_widget(_lbl(
            f"ATK  {fmt_num(enemy.attack)}    DEF  {fmt_num(enemy.defense)}", sp(18), bold=True))
        grid.add_widget(_lbl(
            f"CRIT  {enemy.crit_chance * 100:.0f}%    DODGE  {enemy.dodge_chance * 100:.0f}%",
            sp(15), color=TEXT_SECONDARY))
        grid.add_widget(_lbl(
            f"REWARD  {fmt_num(enemy.gold_reward)} G", sp(15), color=ACCENT_GREEN))

        # Back button at bottom
        back_btn = MinimalButton(
            text=t("back_btn"), btn_color=BTN_PRIMARY, font_size=16,
            size_hint_y=None, height=dp(38),
        )
        back_btn.bind(on_press=lambda inst: self._close_enemy_detail())
        grid.add_widget(back_btn)

    def _close_enemy_detail(self):
        self.arena_view = "battle"

    def on_back_pressed(self):
        if self.arena_view != "battle":
            self._close_enemy_detail()
            return True
        return False

    def _flash_damage(self, defender_name, is_player):
        """Flash the HP bar of a damaged unit."""
        bar_map = self._fighter_bar_map if is_player else self._enemy_bar_map
        if hasattr(self, '_fighter_bar_map') and defender_name in bar_map:
            flash_hp_bar(bar_map[defender_name])

    def _fade_log(self):
        """Fade out battle log after a delay."""
        log_lbl = self.ids.get("battle_log_label")
        if log_lbl:
            Animation.cancel_all(log_lbl, "opacity")
            log_lbl.opacity = 1
            anim = Animation(opacity=0, duration=1.5, t="in_cubic")
            Clock.unschedule(self._start_log_fade)
            Clock.schedule_once(self._start_log_fade, 3.0)

    def _start_log_fade(self, dt=0):
        log_lbl = self.ids.get("battle_log_label")
        if log_lbl:
            Animation(opacity=0, duration=1.5, t="in_cubic").start(log_lbl)

    def _schedule_status_fade(self):
        """Fade out the battle_status label after 3 seconds."""
        Clock.unschedule(self._do_status_fade)
        Clock.schedule_once(self._do_status_fade, 3.0)

    def _do_status_fade(self, dt=0):
        self.battle_status = ""

    def _check_pending_reset(self):
        engine = App.get_running_app().engine
        if engine.pending_reset and not getattr(self, '_reset_popup_open', False):
            self._show_reset_popup(engine)

    def _show_reset_popup(self, engine):
        self._reset_popup_open = True
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=[dp(16), dp(12)])
        content.add_widget(AutoShrinkLabel(
            text=t("all_fighters_dead"), font_size="22sp", bold=True,
            color=ACCENT_RED, size_hint_y=None, height=dp(40),
        ))
        content.add_widget(AutoShrinkLabel(
            text=t("run_ended", n=engine.run_number), font_size="18sp",
            color=TEXT_PRIMARY, size_hint_y=None, height=dp(34),
        ))
        content.add_widget(AutoShrinkLabel(
            text=t("reached_tier_kills", tier=engine.run_max_tier, kills=engine.run_kills),
            font_size="18sp", color=ACCENT_GOLD, size_hint_y=None, height=dp(34),
        ))
        lost_lbl = AutoShrinkLabel(
            text=t("gold_equip_lost"),
            font_size="16sp", color=TEXT_SECONDARY, size_hint_y=None, height=dp(70),
            halign="center", valign="middle",
        )
        bind_text_wrap(lost_lbl)
        content.add_widget(lost_lbl)

        restart_btn = MinimalButton(
            text=t("new_run"), btn_color=ACCENT_RED, font_size=20,
            size_hint_y=None, height=dp(52),
        )
        content.add_widget(restart_btn)

        popup = Popup(
            title=t("permadeath"), title_color=ACCENT_RED, title_size="16sp",
            content=content, size_hint=(0.9, None), height=dp(380),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_RED, auto_dismiss=False,
        )

        def on_restart(inst):
            popup.dismiss()
            self._reset_popup_open = False
            engine.execute_pending_reset()
            App.get_running_app().show_class_selection()

        restart_btn.bind(on_press=on_restart)
        popup.open()

    def start_auto_battle(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        self.is_fighting = True
        if self.arena_mode == "boss":
            events = engine.start_boss_fight()
            self.battle_status = t("boss_challenge")
        else:
            # Check if boss is lurking in regular battle
            has_boss = (engine.current_enemy
                        and getattr(engine.current_enemy, 'is_boss', False))
            events = engine.start_auto_battle()
            self.battle_status = t("auto_battle")
            if has_boss:
                self._show_boss_revenge_popup(engine.current_enemy.name)
        self._display_events(events)
        Clock.schedule_interval(self._auto_turn, BATTLE_AUTO_INTERVAL)

    def _show_boss_revenge_popup(self, boss_name):
        content = BoxLayout(orientation="vertical", spacing=dp(16), padding=dp(20))
        revenge_lbl = AutoShrinkLabel(
            text=t("boss_revenge"), font_size="22sp", bold=True,
            color=ACCENT_RED, halign="center", valign="middle",
            size_hint_y=0.6,
        )
        bind_text_wrap(revenge_lbl)
        content.add_widget(revenge_lbl)
        sub_lbl = AutoShrinkLabel(
            text=t("boss_revenge_sub"), font_size="18sp",
            color=TEXT_SECONDARY, halign="center", valign="middle",
            size_hint_y=0.4,
        )
        bind_text_wrap(sub_lbl)
        content.add_widget(sub_lbl)
        popup = Popup(
            title=boss_name,
            content=content,
            size_hint=(0.95, 0.5),
            title_size=sp(28),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_RED),
            separator_color=popup_color(ACCENT_RED),
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), POPUP_DISMISS_DELAY)

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
            self.arena_mode = "common"
            self.is_fighting = False
            self.battle_log_text = ""
            self.battle_status = f"{t('victory')} +{fmt_num(state.gold_earned)}"
            self._spawn_float(f"+{fmt_num(state.gold_earned)}", ACCENT_GOLD)
            self._schedule_status_fade()
            if engine.should_show_interstitial():
                ad_manager.show_interstitial()
            # Submit to leaderboard every 10 wins
            if engine.wins % 10 == 0:
                leaderboard_manager.submit_all(
                    best_tier=engine.best_record_tier,
                    total_kills=engine.wins,
                    strongest_gladiator_kills=engine.best_record_kills,
                    prestige_level=engine.prestige_level,
                    fastest_t15=engine.fastest_t15_time,
                )
        elif state.phase == BattlePhase.DEFEAT:
            Clock.unschedule(self._auto_turn)
            self.arena_mode = "common"
            self.is_fighting = False
            self.battle_log_text = ""
            self.battle_status = t("defeat")
            self._spawn_float(t("defeat"), ACCENT_RED)
            self._schedule_status_fade()
            Clock.schedule_once(lambda dt: self._check_pending_reset(), 1.0)

    def _display_events(self, events):
        lines = []
        for ev in events[-6:]:
            if ev.is_crit:
                lines.append(f"[CRIT] {ev.message}")
            elif ev.is_kill:
                lines.append(f"[KILL] {ev.message}")
            elif getattr(ev, "is_dodge", False) or (ev.damage == 0 and "DODGE" in ev.message):
                lines.append(f"[DODGE] {ev.message}")
            else:
                lines.append(ev.message)

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

        self.battle_log_text = "\n".join(lines)
        # Show log then schedule fade
        log_lbl = self.ids.get("battle_log_label")
        if log_lbl:
            Animation.cancel_all(log_lbl, "opacity")
            log_lbl.opacity = 1
            Clock.unschedule(self._start_log_fade)
            Clock.schedule_once(self._start_log_fade, 3.0)
        refresh_battle_log(self)

    def _spawn_float(self, text, color):
        arena = self.ids.get("arena_zone")
        if arena:
            ft = FloatingText(
                text=text, font_size="24sp", bold=True, color=color,
                center_x=arena.center_x, y=arena.center_y,
                size_hint=(None, None),
            )
            arena.add_widget(ft)

    def _check_tutorial(self):
        engine = App.get_running_app().engine
        step = engine.get_pending_tutorial()
        if step:
            App.get_running_app().show_tutorial(step)
