# Build: 19
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
    HP_HEAL_TIER_MULT,
)
from kivy.animation import Animation
from game.battle import BattlePhase
from game.localization import t
from game.ads import ad_manager
from game.ui_helpers import (
    build_fighter_pit_card, build_enemy_hp_row,
    update_fighter_pit_card, update_enemy_hp_row,
    flash_hp_bar,
    bind_text_wrap,
)
from game.screens.shared import _safe_clear, _safe_rebind, _play_hit_sound


class ArenaScreen(BaseScreen):
    tier_text = StringProperty("TIER 1")
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
        self.tier_text = t("arena_tier_top", n=engine.arena_tier)
        # Record & run
        if engine.best_record_tier > 0:
            self.best_text = t("arena_best_record",
                               tier=engine.best_record_tier,
                               kills=engine.best_record_kills)
        else:
            self.best_text = t("arena_best_none")
        self.run_text = t("arena_run_stats",
                          n=engine.run_number, kills=engine.run_kills)

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
            enemies = engine.preview_enemies
            if enemies:
                self.enemy_summary = f"{len(enemies)}x T{enemies[0].tier}"
            else:
                self.enemy_summary = ""

        self._refresh_battle_panels(engine)

    def _get_skill_text(self, fighter):
        """Return skill badge text: 'RDY', cooldown number, skill name, or None."""
        engine = App.get_running_app().engine
        skill = getattr(fighter, 'get_active_skill', lambda: None)()
        if not skill:
            return None
        bm = getattr(engine, 'battle_mgr', None)
        if not bm or not bm.is_active:
            return skill["name"][:3].upper()
        ss = bm.state.skill_states.get(id(fighter))
        if not ss:
            return None
        if ss.cooldown_remaining <= 0:
            return "RDY"
        return str(ss.cooldown_remaining)

    def _open_fighter_detail(self, fighter_idx):
        """Open fighter detail on roster screen — same as tapping in squad."""
        app = App.get_running_app()
        roster = app.sm.get_screen("roster")
        roster._pending_state = {'detail_index': fighter_idx}
        app.sm.current = "roster"

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
                real_battle_idx = i
                real_roster_idx = next(
                    (j for j, rf in enumerate(engine.fighters) if rf.name == f.name), -1
                )
                card = build_fighter_pit_card(
                    f, on_tap=lambda w, ri=real_roster_idx: self._open_fighter_detail(ri),
                    skill_text=self._get_skill_text(f),
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
            # Outside battle — use fast update if possible
            fighters_list = [f for f in engine.fighters if f.available]
            alive_enemies = list(engine.preview_enemies)
            if self._try_fast_update(fighters_list, alive_enemies, engine):
                return

            fg.clear_widgets()
            eg.clear_widgets()
            if hb:
                hb.clear_widgets()
            self._fighter_bar_map = {}
            self._enemy_bar_map = {}
            self._cached_fighter_names = []
            self._cached_enemy_names = []

            heal_btn = self._build_heal_btn(fighters_list, self._heal_all_outside)
            if hb:
                hb.add_widget(heal_btn)
            self._cached_heal_btn = heal_btn

            for idx_f, f in enumerate(fighters_list):
                real_idx = engine.fighters.index(f)
                card = build_fighter_pit_card(
                    f, on_tap=lambda w, fi=real_idx: self._open_fighter_detail(fi),
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

    def _try_fast_update(self, fighters_list, alive_enemies, engine):
        """Update existing widgets in-place. Returns True if successful."""

        cached_f = getattr(self, "_cached_fighter_names", [])
        cached_e = getattr(self, "_cached_enemy_names", [])
        current_f = [f.name for f in fighters_list]
        current_e = [e.name for e in alive_enemies]

        if cached_f != current_f or cached_e != current_e:
            return False

        # Update heal button — hide when all full HP
        heal_btn = getattr(self, "_cached_heal_btn", None)
        if heal_btn:
            any_damaged = any(f.hp < f.max_hp for f in fighters_list)
            total_heal_cost = engine.get_hp_heal_cost(fighters_list)
            can_heal = total_heal_cost > 0 and engine.gold > 0 and any_damaged
            heal_btn.text = t("heal_all_cost", cost=f"{fmt_num(total_heal_cost)}") if any_damaged else ""
            heal_btn.btn_color = ACCENT_GREEN if can_heal else BTN_DISABLED
            heal_btn.text_color = BG_DARK if can_heal else TEXT_MUTED
            heal_btn.height = dp(40) if any_damaged else 0
            heal_btn.opacity = 1 if any_damaged else 0
            heal_btn.icon_source = "sprites/icons/ic_gold.png" if any_damaged else ""

        # Update fighter cards
        for f in fighters_list:
            card = self._fighter_bar_map.get(f.name)
            if card:
                update_fighter_pit_card(card, f, skill_text=self._get_skill_text(f))

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
        tier_mult = HP_HEAL_TIER_MULT ** (engine.arena_tier - 1)
        cost = math.ceil(missing / HEAL_GOLD_PER_HP * tier_mult)
        if engine.gold >= cost:
            engine.gold -= cost
            f.hp = f.max_hp
        elif engine.gold > 0:
            heal_hp = int(engine.gold * HEAL_GOLD_PER_HP / tier_mult)
            engine.gold = 0
            f.hp = min(f.max_hp, f.hp + heal_hp)
        else:
            App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(cost)))
            return
        self._spawn_float(t("healed_name", name=f.name), ACCENT_GREEN)
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
            self._spawn_float(t("healed_amount", n=healed, g=spent), ACCENT_GREEN)
            self.refresh_ui()
        elif total_cost > 0:
            App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(total_cost)))

    def _heal_all_battle(self):
        self._heal_all(in_battle=True)

    def _heal_all_outside(self):
        self._heal_all(in_battle=False)

    def _build_heal_btn(self, fighters_list, callback):
        """Build the Heal All button. Hidden when all fighters are full HP."""
        engine = App.get_running_app().engine
        any_damaged = any(f.hp < f.max_hp for f in fighters_list)
        total_heal_cost = engine.get_hp_heal_cost(fighters_list)
        can_heal = total_heal_cost > 0 and engine.gold > 0 and any_damaged
        visible = any_damaged
        btn = MinimalButton(
            text=t("heal_all_cost", cost=fmt_num(total_heal_cost)) if any_damaged else "",
            btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
            text_color=BG_DARK if can_heal else TEXT_MUTED,
            font_size=11, size_hint_y=None,
            height=dp(40) if visible else 0,
            icon_source="sprites/icons/ic_gold.png" if visible else "",
        )
        btn.opacity = 1 if visible else 0
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
        name_prefix = ""  # boss name already includes "BOSS:" from models.py

        def _lbl(text, size=sp(8), bold=False, color=None):
            lbl = AutoShrinkLabel(
                text=text, font_size=size, bold=bold,
                color=color or border,
                halign="center", valign="middle",
                size_hint_y=None, height=dp(32),
            )
            bind_text_wrap(lbl)
            return lbl

        grid.add_widget(_lbl(f"{name_prefix}{enemy.name}", sp(13), bold=True))
        grid.add_widget(_lbl(t("arena_tier_enemy", n=enemy.tier), sp(7), color=TEXT_MUTED))
        grid.add_widget(_lbl(
            f"HP  {fmt_num(enemy.max_hp)}", sp(9), bold=True))
        grid.add_widget(_lbl(
            f"ATK  {fmt_num(enemy.attack)}    DEF  {fmt_num(enemy.defense)}", sp(9), bold=True))
        grid.add_widget(_lbl(
            f"CRIT  {enemy.crit_chance * 100:.0f}%    DODGE  {enemy.dodge_chance * 100:.0f}%",
            sp(8), color=TEXT_SECONDARY))
        grid.add_widget(_lbl(
            f"REWARD  {fmt_num(enemy.gold_reward)} G", sp(8), color=ACCENT_GREEN))

        # Boss modifiers
        mods = getattr(enemy, 'modifiers', [])
        if mods and is_boss:
            from game.data_loader import data_loader
            for mid in mods:
                mod_def = data_loader.boss_modifiers.get(mid, {})
                mod_name = mod_def.get("name", mid)
                mod_desc = mod_def.get("description", "")
                grid.add_widget(_lbl(
                    f"[{mod_name}] {mod_desc}", sp(7), color=ACCENT_PURPLE))


    def _close_enemy_detail(self):
        self.arena_view = "battle"

    def on_back_pressed(self):
        if self.arena_view != "battle":
            self._close_enemy_detail()
            return True
        return False

    def _flash_damage(self, defender_name, is_player):
        """Flash the HP bar of a damaged unit + shake the card."""
        bar_map = self._fighter_bar_map if is_player else self._enemy_bar_map
        if hasattr(self, '_fighter_bar_map') and defender_name in bar_map:
            widget = bar_map[defender_name]
            flash_hp_bar(widget)
            self._shake_widget(widget)
            self._set_sprite_frame(widget, "hurt", revert_delay=0.25)

    def _shake_widget(self, widget, intensity=None, duration=0.15):
        """Quick horizontal shake for hit reaction."""
        if intensity is None:
            intensity = dp(4)
        orig_x = widget.x
        anim = (
            Animation(x=orig_x + intensity, duration=duration / 4, t="out_sine") +
            Animation(x=orig_x - intensity, duration=duration / 4, t="out_sine") +
            Animation(x=orig_x + intensity / 2, duration=duration / 4, t="out_sine") +
            Animation(x=orig_x, duration=duration / 4, t="out_sine")
        )
        anim.start(widget)

    def _set_sprite_frame(self, widget, frame, revert_delay=0.3):
        """Set avatar sprite frame, revert to idle after delay."""
        for child in widget.walk():
            if hasattr(child, 'frame'):
                child.frame = frame
                Clock.schedule_once(
                    lambda dt, c=child: setattr(c, 'frame', 'idle'), revert_delay)
                break

    def _check_pending_reset(self):
        engine = App.get_running_app().engine
        if engine.pending_reset and not getattr(self, '_reset_popup_open', False):
            self._show_reset_popup(engine)

    def _show_reset_popup(self, engine):
        self._reset_popup_open = True
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=[dp(16), dp(12)])
        content.add_widget(AutoShrinkLabel(
            text=t("all_fighters_dead"), font_size="11sp", bold=True,
            color=ACCENT_RED, size_hint_y=None, height=dp(40),
        ))
        content.add_widget(AutoShrinkLabel(
            text=t("run_ended", n=engine.run_number), font_size="11sp",
            color=TEXT_PRIMARY, size_hint_y=None, height=dp(34),
        ))
        content.add_widget(AutoShrinkLabel(
            text=t("reached_tier_kills", tier=engine.run_max_tier, kills=engine.run_kills),
            font_size="11sp", color=ACCENT_GOLD, size_hint_y=None, height=dp(34),
        ))
        lost_lbl = AutoShrinkLabel(
            text=t("gold_equip_lost"),
            font_size="11sp", color=TEXT_SECONDARY, size_hint_y=None, height=dp(70),
            halign="center", valign="middle",
        )
        bind_text_wrap(lost_lbl)
        content.add_widget(lost_lbl)

        restart_btn = MinimalButton(
            text=t("new_run"), btn_color=ACCENT_RED, font_size=10,
            size_hint_y=None, height=dp(52),
        )
        content.add_widget(restart_btn)

        popup = Popup(
            title=t("permadeath"), title_color=ACCENT_RED, title_size="11sp",
            content=content, size_hint=(0.9, None), height=dp(380),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_RED, auto_dismiss=False,
        )

        def on_restart(inst):
            popup.dismiss()
            self._reset_popup_open = False
            engine.execute_pending_reset()
            # Navigate to Roster hire view instead of separate popup
            app = App.get_running_app()
            app.sm.current = "roster"
            roster_scr = app.sm.get_screen("roster")
            roster_scr.hire()

        restart_btn.bind(on_press=on_restart)
        popup.open()

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

    def _show_boss_revenge_popup(self, boss_name):
        content = BoxLayout(orientation="vertical", spacing=dp(16), padding=dp(20))
        revenge_lbl = AutoShrinkLabel(
            text=t("boss_revenge"), font_size="11sp", bold=True,
            color=ACCENT_RED, halign="center", valign="middle",
            size_hint_y=0.6,
        )
        bind_text_wrap(revenge_lbl)
        content.add_widget(revenge_lbl)
        sub_lbl = AutoShrinkLabel(
            text=t("boss_revenge_sub"), font_size="11sp",
            color=TEXT_SECONDARY, halign="center", valign="middle",
            size_hint_y=0.4,
        )
        bind_text_wrap(sub_lbl)
        content.add_widget(sub_lbl)
        popup = Popup(
            title=boss_name,
            content=content,
            size_hint=(0.95, 0.5),
            title_size=sp(12),
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
            self.is_fighting = False
            self._spawn_float(f"{t('victory')} +{fmt_num(state.gold_earned)}", ACCENT_GOLD)
            self._victory_flash()
            # Re-spawn enemy matching current mode
            if self.arena_mode == "boss":
                engine.spawn_boss_enemy()
            else:
                engine._spawn_enemy()
            self._cached_enemy_names = []
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
                atk_map = self._enemy_bar_map if ev.is_boss else self._fighter_bar_map
                if hasattr(self, '_fighter_bar_map') and ev.attacker in atk_map:
                    self._set_sprite_frame(atk_map[ev.attacker], "attack", revert_delay=0.3)

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

    _active_floats: list = []

    def _spawn_float(self, text, color):
        arena = self.ids.get("arena_zone")
        if arena:
            # Remove finished floats from tracking
            self._active_floats = [f for f in self._active_floats
                                   if f.parent is not None]
            # Stack downward: each active float shifts new one by 30dp
            from kivy.metrics import dp
            offset = len(self._active_floats) * dp(30)
            ft = FloatingText(
                text=text, font_size="12sp", bold=True, color=color,
                center_x=arena.center_x,
                y=arena.center_y - offset,
                size_hint=(None, None),
            )
            arena.add_widget(ft)
            self._active_floats.append(ft)

    def _victory_flash(self):
        """Flash screen gold on victory."""
        arena = self.ids.get("arena_zone")
        if not arena:
            return
        from kivy.graphics import Color as GColor, Rectangle as GRect
        with arena.canvas.after:
            flash_c = GColor(0.93, 0.78, 0.18, 0.25)
            flash_r = GRect(pos=arena.pos, size=arena.size)

        def _fade(dt):
            flash_c.a -= 0.05
            if flash_c.a <= 0:
                Clock.unschedule(_fade)
                arena.canvas.after.remove(flash_c)
                arena.canvas.after.remove(flash_r)
        Clock.schedule_interval(_fade, 0.05)

    def _check_tutorial(self):
        engine = App.get_running_app().engine
        step = engine.get_pending_tutorial()
        if step:
            App.get_running_app().show_tutorial(step)
