# Build: 5
"""
Gladiator Idle Manager — roguelike-manager.
Permadeath resets the run. Stats distributed manually. Fighter classes.
"""

import os
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.utils import platform
from kivy.metrics import dp, sp
from kivy.core.window import Window

from game.engine import GameEngine
from game.models import FIGHTER_CLASSES, fmt_num
from game.theme import *
from game.localization import t, init_language, set_language, get_language
from game.widgets import (
    MinimalBar, GladiatorAvatar, MinimalButton,
    CardWidget, NavButton, FloatingText,
)
from game.ui_helpers import (
    refresh_roster_grid,
    refresh_forge_grid, refresh_expedition_grid,
    refresh_battle_log, refresh_achievement_grid,
    refresh_diamond_shop_grid,
    build_enemy_hp_row,
)
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager
from game.leaderboard import leaderboard_manager

# Window.size only on desktop — crashes Android
if platform not in ("android", "ios"):
    Window.size = (360, 640)
Window.clearcolor = BG_DARK

# Icons are PNG sprites in icons/ — no font hacking needed

# --- Sword hit sound ---
_hit_sound = None

def _play_hit_sound():
    global _hit_sound
    try:
        if _hit_sound is None:
            from kivy.core.audio import SoundLoader
            _hit_sound = SoundLoader.load("sounds/hit.wav")
        if _hit_sound:
            _hit_sound.volume = 0.4
            _hit_sound.play()
    except Exception:
        pass


SCREEN_ORDER = ["arena", "roster", "forge", "expedition", "lore", "more"]


class SwipeScreenManager(ScreenManager):
    """ScreenManager with horizontal swipe to switch tabs."""

    _swipe_start_x = 0
    _swipe_start_y = 0
    SWIPE_MIN_DX = dp(80)
    SWIPE_MAX_DY_RATIO = 0.5  # max dy/dx to keep it horizontal

    def on_touch_down(self, touch):
        self._swipe_start_x = touch.x
        self._swipe_start_y = touch.y
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        dx = touch.x - self._swipe_start_x
        dy = touch.y - self._swipe_start_y
        adx = abs(dx)
        ady = abs(dy)
        if adx > self.SWIPE_MIN_DX and (ady / adx if adx else 999) < self.SWIPE_MAX_DY_RATIO:
            try:
                idx = SCREEN_ORDER.index(self.current)
            except ValueError:
                return super().on_touch_up(touch)
            if dx < 0 and idx < len(SCREEN_ORDER) - 1:
                self.transition = SlideTransition(direction="left", duration=0.2)
                self.current = SCREEN_ORDER[idx + 1]
                self.transition = NoTransition()
                return True
            elif dx > 0 and idx > 0:
                self.transition = SlideTransition(direction="right", duration=0.2)
                self.current = SCREEN_ORDER[idx - 1]
                self.transition = NoTransition()
                return True
        return super().on_touch_up(touch)


# ============================================================
#  ARENA / BATTLE (THE PIT)
# ============================================================

class ArenaScreen(Screen):
    gold_text = StringProperty("0")
    diamond_text = StringProperty("0")
    wins_text = StringProperty("0")
    tier_text = StringProperty("TIER 1")
    battle_status = StringProperty("")
    battle_log_text = StringProperty("")
    player_summary = StringProperty("")
    enemy_summary = StringProperty("")
    player_hp_pct = NumericProperty(1.0)
    enemy_hp_pct = NumericProperty(1.0)
    record_text = StringProperty("Best: ---")
    run_text = StringProperty("Run #1")

    def on_enter(self):
        self.refresh_ui()
        self._check_tutorial()
        self._check_pending_reset()

    def refresh_ui(self):
        engine = App.get_running_app().engine
        self.gold_text = fmt_num(engine.gold)
        self.diamond_text = fmt_num(engine.diamonds)
        self.wins_text = f"{engine.wins}W"
        self.tier_text = f"TIER {engine.arena_tier}"
        if not self.battle_status:
            self.battle_status = t("ready_to_fight")

        # Record & run
        if engine.best_record_tier > 0:
            self.record_text = f"Best: T{engine.best_record_tier} / {engine.best_record_kills} kills"
        else:
            self.record_text = "Best: ---"
        self.run_text = f"Run #{engine.run_number}  |  T{engine.run_max_tier}  |  {engine.run_kills} kills"

        fighters = [f for f in engine.fighters if f.alive and not f.on_expedition]
        self.player_summary = t("fighters_ready", n=len(fighters))

        if engine.battle_active:
            s = engine.battle_mgr.state
            alive_f = sum(1 for f in s.player_fighters if f.alive and f.hp > 0)
            alive_e = sum(1 for e in s.enemies if e.hp > 0)
            self.player_summary = t("fighters_alive", n=alive_f)
            self.enemy_summary = t("enemies_left", n=alive_e)
            if s.player_fighters:
                total_hp = sum(max(0, f.hp) for f in s.player_fighters if f.alive)
                total_max = sum(f.max_hp for f in s.player_fighters if f.alive) or 1
                self.player_hp_pct = total_hp / total_max
            if s.enemies:
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
        from game.ui_helpers import build_fighter_pit_card, build_enemy_hp_row
        fg = self.ids.get("battle_fighters_grid")
        eg = self.ids.get("battle_enemies_grid")
        if not fg or not eg:
            return

        fg.clear_widgets()
        eg.clear_widgets()
        self._fighter_bar_map = {}
        self._enemy_bar_map = {}

        # Heal All button at top of ally panel
        heal_cost = engine.heal_all_injuries_cost() if not engine.battle_active else 0
        any_damaged = False

        if engine.battle_active:
            s = engine.battle_mgr.state
            fighters_list = [f for f in s.player_fighters if f.alive]
            any_damaged = any(f.hp < f.max_hp for f in fighters_list)

            # Heal All button (heals HP in battle)
            total_heal_cost = engine.get_heal_cost() * sum(1 for f in fighters_list if f.hp < f.max_hp)
            can_heal = engine.gold >= engine.get_heal_cost() and any_damaged
            heal_btn = MinimalButton(
                text=t("heal_all_cost", cost=f"{fmt_num(total_heal_cost)}g") if any_damaged else t("heal_all"),
                btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
                text_color=BG_DARK if can_heal else TEXT_MUTED,
                font_size=16, size_hint_y=None, height=dp(40),
            )
            if can_heal:
                heal_btn.bind(on_press=lambda inst: self._heal_all_battle())
            fg.add_widget(heal_btn)

            # Fighter cards
            for i, f in enumerate(fighters_list):
                card = build_fighter_pit_card(
                    f, on_tap=lambda w, idx=i: self.heal_fighter(idx),
                )
                self._fighter_bar_map[f.name] = card
                fg.add_widget(card)

            # Enemy HP bars
            for e in s.enemies:
                if e.hp <= 0:
                    continue
                row = build_enemy_hp_row(
                    e, show_stats=True,
                    on_tap=lambda w, en=e: self._show_enemy_popup(en),
                )
                self._enemy_bar_map[e.name] = row
                eg.add_widget(row)
        else:
            fighters_list = [f for f in engine.fighters if f.alive and not f.on_expedition]
            any_damaged = any(f.hp < f.max_hp for f in fighters_list)

            # Heal All button (heals HP outside battle)
            total_heal_cost = engine.get_heal_cost() * sum(1 for f in fighters_list if f.hp < f.max_hp)
            can_heal = engine.gold >= engine.get_heal_cost() and any_damaged
            heal_btn = MinimalButton(
                text=t("heal_all_cost", cost=f"{fmt_num(total_heal_cost)}g") if any_damaged else t("heal_all"),
                btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
                text_color=BG_DARK if can_heal else TEXT_MUTED,
                font_size=16, size_hint_y=None, height=dp(40),
            )
            if can_heal:
                heal_btn.bind(on_press=lambda inst: self._heal_all_outside())
            fg.add_widget(heal_btn)

            # Fighter cards
            for idx_f, f in enumerate(fighters_list):
                card = build_fighter_pit_card(
                    f, on_tap=lambda w, fi=idx_f: self._heal_outside_battle(fi),
                )
                self._fighter_bar_map[f.name] = card
                fg.add_widget(card)

            # Enemy preview
            e = engine.current_enemy
            if e:
                row = build_enemy_hp_row(
                    e, show_stats=True,
                    on_tap=lambda w, en=e: self._show_enemy_popup(en),
                )
                self._enemy_bar_map[e.name] = row
                eg.add_widget(row)

    def heal_fighter(self, fighter_idx):
        engine = App.get_running_app().engine
        if not engine.battle_active:
            return
        s = engine.battle_mgr.state
        if 0 <= fighter_idx < len(s.player_fighters):
            f = s.player_fighters[fighter_idx]
            cost = engine.get_heal_cost()
            if engine.gold >= cost and f.alive and f.hp > 0 and f.hp < f.max_hp:
                engine.gold -= cost
                heal_amount = f.max_hp // 3
                f.hp = min(f.max_hp, f.hp + heal_amount)
                self.battle_status = f"Healed {f.name} +{heal_amount}HP"
                self.refresh_ui()

    def _heal_outside_battle(self, fighter_idx):
        """Heal a fighter's HP outside of battle (tap in PIT idle view)."""
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        fighters = engine.fighters
        if 0 <= fighter_idx < len(fighters):
            f = fighters[fighter_idx]
            cost = engine.get_heal_cost()
            if engine.gold >= cost and f.alive and f.hp > 0 and f.hp < f.max_hp:
                engine.gold -= cost
                heal_amount = f.max_hp // 3
                f.hp = min(f.max_hp, f.hp + heal_amount)
                self.battle_status = f"Healed {f.name} +{heal_amount}HP"
                engine.save()
                self.refresh_ui()

    def _heal_all_battle(self):
        """Heal all fighters' HP during battle."""
        engine = App.get_running_app().engine
        if not engine.battle_active:
            return
        s = engine.battle_mgr.state
        cost = engine.get_heal_cost()
        healed = 0
        for f in s.player_fighters:
            if f.alive and f.hp > 0 and f.hp < f.max_hp and engine.gold >= cost:
                engine.gold -= cost
                heal_amount = f.max_hp // 3
                f.hp = min(f.max_hp, f.hp + heal_amount)
                healed += 1
        if healed > 0:
            self.battle_status = f"Healed {healed} fighters"
            self.refresh_ui()

    def _heal_all_outside(self):
        """Heal all fighters' HP outside battle."""
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        cost = engine.get_heal_cost()
        healed = 0
        for f in engine.fighters:
            if f.alive and not f.on_expedition and f.hp < f.max_hp and engine.gold >= cost:
                engine.gold -= cost
                heal_amount = f.max_hp // 3
                f.hp = min(f.max_hp, f.hp + heal_amount)
                healed += 1
        if healed > 0:
            self.battle_status = f"Healed {healed} fighters"
            engine.save()
            self.refresh_ui()

    def _show_enemy_popup(self, enemy):
        """Show a popup with detailed enemy stats."""
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.metrics import sp, dp

        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))

        hp_pct = max(0, enemy.hp) / max(1, enemy.max_hp) * 100

        lines = [
            f"[b]{enemy.name}[/b]",
            f"Tier {enemy.tier}",
            "",
            f"HP: {max(0, enemy.hp)} / {enemy.max_hp}  ({hp_pct:.0f}%)",
            f"ATK: {enemy.attack}",
            f"DEF: {enemy.defense}",
            f"CRIT: {enemy.crit_chance * 100:.0f}%",
            f"DODGE: {enemy.dodge_chance * 100:.0f}%",
            f"REWARD: {enemy.gold_reward}g",
        ]

        info = Label(
            text="\n".join(lines),
            font_size=sp(20),
            markup=True,
            color=TEXT_PRIMARY,
            halign="center", valign="middle",
        )
        info.bind(size=lambda w, s: setattr(w, "text_size", s))
        content.add_widget(info)

        popup = Popup(
            title=enemy.name,
            title_size=sp(22),
            content=content,
            size_hint=(0.85, 0.5),
            background_color=BG_CARD,
        )
        popup.open()

    def _flash_damage(self, defender_name, is_player):
        """Flash the HP bar of a damaged unit."""
        from game.ui_helpers import flash_hp_bar
        bar_map = self._fighter_bar_map if is_player else self._enemy_bar_map
        if hasattr(self, '_fighter_bar_map') and defender_name in bar_map:
            flash_hp_bar(bar_map[defender_name])

    def _fade_log(self):
        """Fade out battle log after a delay."""
        log_lbl = self.ids.get("battle_log_label")
        if log_lbl:
            from kivy.animation import Animation
            Animation.cancel_all(log_lbl, "opacity")
            log_lbl.opacity = 1
            anim = Animation(opacity=0, duration=1.5, t="in_cubic")
            Clock.unschedule(self._start_log_fade)
            Clock.schedule_once(self._start_log_fade, 3.0)

    def _start_log_fade(self, dt=0):
        log_lbl = self.ids.get("battle_log_label")
        if log_lbl:
            from kivy.animation import Animation
            Animation(opacity=0, duration=1.5, t="in_cubic").start(log_lbl)

    def _schedule_status_fade(self):
        """Fade out the battle_status label after 3 seconds."""
        Clock.unschedule(self._do_status_fade)
        Clock.schedule_once(self._do_status_fade, 3.0)

    def _do_status_fade(self, dt=0):
        self.battle_status = ""

    def _check_pending_reset(self):
        engine = App.get_running_app().engine
        if engine.pending_reset:
            self._show_reset_popup(engine)

    def _show_reset_popup(self, engine):
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=[dp(16), dp(12)])
        content.add_widget(Label(
            text=t("all_fighters_dead"), font_size="22sp", bold=True,
            color=ACCENT_RED, size_hint_y=None, height=dp(40),
        ))
        content.add_widget(Label(
            text=t("run_ended", n=engine.run_number), font_size="18sp",
            color=TEXT_PRIMARY, size_hint_y=None, height=dp(34),
        ))
        content.add_widget(Label(
            text=t("reached_tier_kills", tier=engine.run_max_tier, kills=engine.run_kills),
            font_size="18sp", color=ACCENT_GOLD, size_hint_y=None, height=dp(34),
        ))
        lost_lbl = Label(
            text=t("gold_equip_lost"),
            font_size="16sp", color=TEXT_SECONDARY, size_hint_y=None, height=dp(70),
            halign="center",
        )
        lost_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
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
            engine.execute_pending_reset()
            App.get_running_app().show_class_selection()

        restart_btn.bind(on_press=on_restart)
        popup.open()

    def start_auto_battle(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        events = engine.start_auto_battle()
        self.battle_status = t("auto_battle")
        self._display_events(events)
        Clock.schedule_interval(self._auto_turn, 0.8)

    def start_boss_fight(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        events = engine.start_boss_fight()
        self.battle_status = t("boss_challenge")
        self._display_events(events)

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
        from game.battle import BattlePhase
        state = engine.battle_mgr.state
        if state.phase == BattlePhase.VICTORY:
            Clock.unschedule(self._auto_turn)
            self.battle_status = f"{t('victory')} +{fmt_num(state.gold_earned)}g"
            self._spawn_float(f"+{fmt_num(state.gold_earned)}g", ACCENT_GOLD)
            self._schedule_status_fade()
            if engine.should_show_interstitial():
                ad_manager.show_interstitial()
            # Submit to leaderboard every 10 wins
            if engine.wins % 10 == 0:
                leaderboard_manager.submit_all(
                    best_tier=engine.best_record_tier,
                    total_kills=engine.wins,
                    strongest_gladiator_kills=engine.best_record_kills,
                )
        elif state.phase == BattlePhase.DEFEAT:
            Clock.unschedule(self._auto_turn)
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
            from kivy.animation import Animation
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


# ============================================================
#  ROSTER (SQUAD) — with stat distribution
# ============================================================

class RosterScreen(Screen):
    gladiators_data = ListProperty()
    gold_text = StringProperty("0")
    graveyard_text = StringProperty("")
    hire_cost_text = StringProperty("")
    heal_all_text = StringProperty("")
    heal_all_enabled = StringProperty("false")

    def on_enter(self):
        self.refresh_roster()

    def refresh_roster(self):
        engine = App.get_running_app().engine
        self.gold_text = fmt_num(engine.gold)
        deaths = engine.total_deaths
        self.graveyard_text = t("fallen", n=deaths) if deaths > 0 else ""
        self.gladiators_data = [
            {
                "name": f.name, "level": f.level,
                "fighter_class": f.class_name,
                "str": f.strength, "agi": f.agility, "vit": f.vitality,
                "unused_points": f.unused_points,
                "atk": f.attack, "def": f.defense, "hp": f.max_hp,
                "current_hp": f.hp,
                "crit": f.crit_chance, "dodge": f.dodge_chance,
                "cost": f.upgrade_cost,
                "index": i, "active": i == engine.active_fighter_idx,
                "alive": f.alive, "injuries": f.injuries, "kills": f.kills,
                "death_chance": f.death_chance,
                "on_expedition": f.on_expedition,
                "weapon": f.equipment.get("weapon"),
                "armor": f.equipment.get("armor"),
                "accessory": f.equipment.get("accessory"),
                "relics": len(f.relics),
            }
            for i, f in enumerate(engine.fighters)
        ]
        self.hire_cost_text = t("recruit_btn", cost=f"{fmt_num(engine.hire_cost)}g")
        heal_cost = engine.heal_all_injuries_cost()
        has_injuries = heal_cost > 0
        can_afford = engine.gold >= heal_cost and has_injuries
        self.heal_all_text = t("heal_all_injuries_cost", cost=f"{fmt_num(heal_cost)}g") if has_injuries else t("heal_all_injuries")
        self.heal_all_enabled = "true" if can_afford else "false"
        refresh_roster_grid(self)

    def upgrade(self, index):
        App.get_running_app().engine.upgrade_gladiator(index)
        self.refresh_roster()

    def set_active(self, index):
        App.get_running_app().engine.active_fighter_idx = index
        self.refresh_roster()

    def hire(self):
        App.get_running_app().show_class_selection()

    def dismiss(self, index):
        App.get_running_app().engine.dismiss_dead(index)
        self.refresh_roster()

    def add_str(self, index):
        App.get_running_app().engine.distribute_stat(index, "strength")
        self.refresh_roster()

    def add_agi(self, index):
        App.get_running_app().engine.distribute_stat(index, "agility")
        self.refresh_roster()

    def add_vit(self, index):
        App.get_running_app().engine.distribute_stat(index, "vitality")
        self.refresh_roster()

    def heal_all_injuries(self):
        engine = App.get_running_app().engine
        success, msg = engine.heal_all_injuries()
        self.refresh_roster()

    def show_fighter_detail(self, index):
        from game.models import FORGE_WEAPONS, FORGE_ARMOR, FORGE_ACCESSORIES, RARITY_COLORS
        engine = App.get_running_app().engine
        if index < 0 or index >= len(engine.fighters):
            return
        f = engine.fighters[index]
        from kivy.uix.scrollview import ScrollView

        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=[dp(12), dp(8)])

        # Header: name [class] Lv.X
        content.add_widget(Label(
            text=f"{f.name}  [{f.class_name}]  Lv.{f.level}", font_size="20sp", bold=True,
            color=ACCENT_GOLD, size_hint_y=None, height=dp(32),
            halign="center",
        ))

        # Stats: ATK, DEF, HP, Crit%, Dodge%
        stats_text = (
            f"ATK {f.attack}   DEF {f.defense}   HP {f.hp}/{f.max_hp}\n"
            f"Crit {f.crit_chance:.0%}   Dodge {f.dodge_chance:.0%}   Power {f.power_rating}"
        )
        stats_lbl = Label(
            text=stats_text, font_size="15sp",
            color=TEXT_SECONDARY, size_hint_y=None, height=dp(40),
            halign="center",
        )
        stats_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        content.add_widget(stats_lbl)

        # STR / AGI / VIT with + buttons
        stat_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        has_pts = f.unused_points > 0 and f.alive and not f.on_expedition
        for stat_name, stat_val, color, stat_key in [
            ("STR", f.strength, ACCENT_RED, "strength"),
            ("AGI", f.agility, ACCENT_GREEN, "agility"),
            ("VIT", f.vitality, ACCENT_BLUE, "vitality"),
        ]:
            cell = BoxLayout(spacing=dp(2))
            lbl = Label(text=f"{stat_name} {stat_val}", font_size="15sp",
                        color=color, halign="center", bold=True)
            lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            cell.add_widget(lbl)
            if has_pts:
                btn = MinimalButton(text="+", btn_color=color, text_color=BG_DARK,
                                    font_size=16, size_hint_x=0.4)

                def _add(inst, sk=stat_key, idx=index):
                    engine.distribute_stat(idx, sk)
                    engine.save()
                    popup.dismiss()
                    self.refresh_roster()
                    self.show_fighter_detail(idx)
                btn.bind(on_press=_add)
                cell.add_widget(btn)
            stat_row.add_widget(cell)
        content.add_widget(stat_row)

        if has_pts:
            content.add_widget(Label(
                text=f"{f.unused_points} pts", font_size="14sp",
                color=ACCENT_GOLD, size_hint_y=None, height=dp(20), halign="center",
            ))

        # Equipment slots — tap to open equipment popup
        for slot, icon_src, items_list in [
            ("weapon", "icons/ic_weapon.png", FORGE_WEAPONS),
            ("armor", "icons/ic_armor.png", FORGE_ARMOR),
            ("accessory", "icons/ic_accessory.png", FORGE_ACCESSORIES),
        ]:
            eq_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
            from kivy.uix.image import Image
            ico = Image(source=icon_src, fit_mode="contain",
                        size_hint=(None, 1), width=dp(28))
            eq_row.add_widget(ico)

            item = f.equipment.get(slot)
            if item:
                rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
                eq_lbl = Label(text=item["name"], font_size="15sp", bold=True,
                               color=rcolor, halign="left")
            else:
                eq_lbl = Label(text="--- empty ---", font_size="15sp",
                               color=TEXT_MUTED, halign="left")
            eq_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            eq_row.add_widget(eq_lbl)

            if f.alive and not f.on_expedition:
                eq_btn = MinimalButton(text=slot.upper(), btn_color=BTN_PRIMARY,
                                       font_size=13, size_hint_x=0.3)

                def _open_eq(inst, s=slot, il=items_list, idx=index):
                    popup.dismiss()
                    self._show_equipment_popup(idx, s, il)
                eq_btn.bind(on_press=_open_eq)
                eq_row.add_widget(eq_btn)
            content.add_widget(eq_row)

        # Injuries + death risk
        if f.injuries > 0:
            injury_text = f"Injuries: {f.injuries}   Death Risk: {f.death_chance:.0%}"
            content.add_widget(Label(
                text=injury_text, font_size="15sp", color=ACCENT_RED,
                size_hint_y=None, height=dp(24), halign="center",
            ))

        # Kills + relics
        meta_parts = [f"Kills: {f.kills}"]
        if f.relics:
            meta_parts.append(f"Relics: {len(f.relics)}")
        content.add_widget(Label(
            text="  ".join(meta_parts), font_size="14sp", color=TEXT_MUTED,
            size_hint_y=None, height=dp(20), halign="center",
        ))

        # Action buttons row
        btn_row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))

        # Train button
        if f.alive and not f.on_expedition:
            cost = f.upgrade_cost
            can_train = engine.gold >= cost
            train_btn = MinimalButton(
                text=t("train_btn", lv=f.level + 1, cost=f"{fmt_num(cost)}g"),
                btn_color=ACCENT_GOLD if can_train else BTN_DISABLED,
                text_color=BG_DARK if can_train else TEXT_MUTED,
                font_size=15,
            )

            def _train(inst, idx=index):
                engine.upgrade_gladiator(idx)
                popup.dismiss()
                self.refresh_roster()
                self.show_fighter_detail(idx)
            if can_train:
                train_btn.bind(on_press=_train)
            btn_row.add_widget(train_btn)

        # Heal injury button
        if f.injuries > 0:
            heal_cost = f.get_injury_heal_cost()
            can_heal = engine.gold >= heal_cost
            heal_btn = MinimalButton(
                text=f"{t('heal_btn')} ({fmt_num(heal_cost)}g)",
                btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
                text_color=BG_DARK if can_heal else TEXT_MUTED,
                font_size=15,
            )

            def on_heal(inst, idx=index):
                success, msg = engine.heal_fighter_injury(idx)
                if success:
                    popup.dismiss()
                    self.refresh_roster()
                    self.show_fighter_detail(idx)
            if can_heal:
                heal_btn.bind(on_press=on_heal)
            btn_row.add_widget(heal_btn)

        content.add_widget(btn_row)

        popup = Popup(
            title=f"{f.name}", title_color=ACCENT_GOLD, title_size="16sp",
            content=content, size_hint=(0.94, None), height=dp(500),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_GOLD,
        )
        popup.open()

    def _show_equipment_popup(self, fighter_idx, slot, items_list):
        """Popup showing all items for a slot — buy or equip from inventory."""
        from game.models import RARITY_COLORS
        engine = App.get_running_app().engine
        f = engine.fighters[fighter_idx]
        from kivy.uix.scrollview import ScrollView

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False,
                            scroll_distance=dp(20), scroll_timeout=150)
        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            padding=[dp(8), dp(6)], size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # Currently equipped
        current = f.equipment.get(slot)
        if current:
            rcolor = RARITY_COLORS.get(current.get("rarity", "common"), TEXT_PRIMARY)
            content.add_widget(Label(
                text=f"Equipped: {current['name']}", font_size="16sp",
                color=rcolor, bold=True, size_hint_y=None, height=dp(30),
                halign="center",
            ))

        for item in items_list:
            row = BoxLayout(size_hint_y=None, height=dp(60), spacing=dp(6),
                            padding=[dp(4), dp(2)])
            rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)

            # Item info
            info = BoxLayout(orientation="vertical", size_hint_x=0.55, spacing=0)
            info.add_widget(Label(
                text=item["name"], font_size="15sp", bold=True, color=rcolor,
                halign="left", size_hint_y=0.5,
            ))
            stats_parts = []
            if item["atk"] > 0:
                stats_parts.append(f"+{item['atk']}ATK")
            if item["def"] > 0:
                stats_parts.append(f"+{item['def']}DEF")
            if item["hp"] > 0:
                stats_parts.append(f"+{item['hp']}HP")
            stat_lbl = Label(
                text=" ".join(stats_parts), font_size="13sp",
                color=ACCENT_GREEN, halign="left", size_hint_y=0.5,
            )
            stat_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            info.add_widget(stat_lbl)
            row.add_widget(info)

            # Inventory count
            inv_count = engine.get_inventory_count(item["id"])

            if inv_count > 0:
                # Show count + EQUIP button
                row.add_widget(Label(
                    text=f"x{inv_count}", font_size="14sp", color=ACCENT_GOLD,
                    size_hint_x=0.15, halign="center",
                ))
                equip_btn = MinimalButton(
                    text=t("equip_btn"), font_size=14, size_hint_x=0.3,
                    btn_color=ACCENT_GREEN, text_color=BG_DARK,
                )

                def _equip(inst, iid=item["id"], idx=fighter_idx):
                    inv_idx = engine.find_inventory_index(iid)
                    if inv_idx >= 0:
                        engine.equip_from_inventory(idx, inv_idx)
                        equip_popup.dismiss()
                        self.refresh_roster()
                        self.show_fighter_detail(idx)
                equip_btn.bind(on_press=_equip)
                row.add_widget(equip_btn)
            else:
                # BUY button
                affordable = engine.gold >= item["cost"]
                buy_btn = MinimalButton(
                    text=f"{fmt_num(item['cost'])}g", font_size=14, size_hint_x=0.35,
                    btn_color=rcolor if affordable else BTN_DISABLED,
                    text_color=TEXT_PRIMARY if affordable else TEXT_MUTED,
                )

                def _buy(inst, iid=item["id"], idx=fighter_idx, s=slot, il=items_list):
                    engine.buy_forge_item(iid)
                    equip_popup.dismiss()
                    self.refresh_roster()
                    self._show_equipment_popup(idx, s, il)
                if affordable:
                    buy_btn.bind(on_press=_buy)
                row.add_widget(buy_btn)

            content.add_widget(row)

        scroll.add_widget(content)

        equip_popup = Popup(
            title=f"{slot.upper()} — {f.name}",
            title_color=ACCENT_GOLD, title_size="16sp",
            content=scroll, size_hint=(0.94, 0.7),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_GOLD,
        )
        equip_popup.open()


# ============================================================
#  FORGE (ANVIL)
# ============================================================

class ForgeScreen(Screen):
    gold_text = StringProperty("0")
    forge_items = ListProperty()
    show_inventory = BooleanProperty(False)
    inventory_btn_text = StringProperty("")

    def on_enter(self):
        self.show_inventory = False
        self.refresh_forge()

    def refresh_forge(self):
        engine = App.get_running_app().engine
        self.gold_text = fmt_num(engine.gold)
        self.forge_items = engine.get_forge_items()
        inv_count = len(engine.inventory)
        self.inventory_btn_text = t("inventory_count", n=inv_count) if inv_count > 0 else t("inventory_label")
        if self.show_inventory:
            self._refresh_inventory_grid()
        else:
            refresh_forge_grid(self)

    def toggle_inventory(self):
        self.show_inventory = not self.show_inventory
        self.refresh_forge()

    def _refresh_inventory_grid(self):
        from game.models import RARITY_COLORS
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        grid.clear_widgets()
        engine = App.get_running_app().engine
        if not engine.inventory:
            grid.add_widget(Label(
                text="Inventory is empty", font_size="16sp",
                color=TEXT_MUTED, size_hint_y=None, height=dp(60),
                halign="center",
            ))
            return
        for inv_idx, item in enumerate(engine.inventory):
            row = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(6),
                            padding=[dp(8), dp(4)])
            rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)

            info = BoxLayout(orientation="vertical", size_hint_x=0.55)
            info.add_widget(Label(
                text=item.get("name", "?"), font_size="16sp", bold=True,
                color=rcolor, halign="left", size_hint_y=0.5,
            ))
            slot_text = item.get("slot", "?").upper()
            stats_parts = []
            if item.get("atk", 0) > 0:
                stats_parts.append(f"+{item['atk']}ATK")
            if item.get("def", 0) > 0:
                stats_parts.append(f"+{item['def']}DEF")
            if item.get("hp", 0) > 0:
                stats_parts.append(f"+{item['hp']}HP")
            info.add_widget(Label(
                text=f"{slot_text}  {' '.join(stats_parts)}", font_size="13sp",
                color=TEXT_MUTED, halign="left", size_hint_y=0.5,
            ))
            row.add_widget(info)

            sell_price = item.get("cost", 0) // 2
            sell_btn = MinimalButton(
                text=f"SELL {fmt_num(sell_price)}g", font_size=14,
                btn_color=ACCENT_GOLD, text_color=BG_DARK,
                size_hint_x=0.35,
            )

            def _sell(inst, idx=inv_idx):
                engine.sell_inventory_item(idx)
                self.refresh_forge()
            sell_btn.bind(on_press=_sell)
            row.add_widget(sell_btn)

            # Wrap in a CardWidget for visual consistency
            from game.widgets import CardWidget as CW
            card = CW(orientation="horizontal", size_hint_y=None, height=dp(70),
                       padding=[0, 0])
            card.border_color = rcolor
            card.add_widget(row)
            grid.add_widget(card)

    def buy(self, item_id):
        App.get_running_app().engine.buy_forge_item(item_id)
        self.refresh_forge()


# ============================================================
#  EXPEDITIONS (HUNTS)
# ============================================================

class ExpeditionScreen(Screen):
    gold_text = StringProperty("0")
    expeditions_data = ListProperty()
    status_data = ListProperty()
    log_text = StringProperty("")
    fighters_for_send = ListProperty()

    def on_enter(self):
        self.refresh_expeditions()

    def refresh_expeditions(self):
        engine = App.get_running_app().engine
        self.gold_text = fmt_num(engine.gold)
        self.expeditions_data = engine.get_expeditions()
        self.status_data = engine.get_expedition_status()
        self.log_text = "\n".join(engine.expedition_log[-5:]) if engine.expedition_log else t("no_expeditions_log")
        self.fighters_for_send = [
            {"name": f.name, "level": f.level, "index": i}
            for i, f in enumerate(engine.fighters)
            if f.alive and not f.on_expedition
        ]
        refresh_expedition_grid(self)

    def send(self, fighter_idx, expedition_id):
        App.get_running_app().engine.send_on_expedition(fighter_idx, expedition_id)
        self.refresh_expeditions()


# ============================================================
#  LORE (Story + Achievements + Diamond Shop)
# ============================================================

class LoreScreen(Screen):
    diamond_text = StringProperty("0")
    achievements_data = ListProperty()
    diamond_shop_data = ListProperty()

    def on_enter(self):
        self.refresh_lore()

    def refresh_lore(self):
        engine = App.get_running_app().engine
        self.diamond_text = f"{engine.diamonds}"
        self.achievements_data = engine.get_achievements()
        refresh_achievement_grid(self)
        self.diamond_shop_data = engine.get_diamond_shop()
        refresh_diamond_shop_grid(self)

    def buy_diamond_item(self, item_id):
        engine = App.get_running_app().engine
        engine.buy_diamond_item(item_id)
        self.refresh_lore()


# ============================================================
#  MORE (Market + Settings)
# ============================================================

class MoreScreen(Screen):
    gold_text = StringProperty("0")
    cloud_status = StringProperty("Not connected")
    ads_status = StringProperty("Active")
    google_btn_text = StringProperty("")
    google_signed_in = BooleanProperty(False)

    def on_enter(self):
        self.refresh_more()

    def refresh_more(self):
        engine = App.get_running_app().engine
        self.gold_text = fmt_num(engine.gold)
        self.cloud_status = cloud_save_manager.last_sync_status
        self.ads_status = t("status_removed") if engine.ads_removed else t("status_active")
        # Update google button state
        if cloud_save_manager.is_connected and cloud_save_manager.user_email:
            self.google_signed_in = True
            self.google_btn_text = t("signed_in_as", email=cloud_save_manager.user_email)
        else:
            self.google_signed_in = False
            self.google_btn_text = t("sign_in_google")
        # Hide ads_box when ads are removed
        ads_box = self.ids.get("ads_box")
        if ads_box:
            if engine.ads_removed:
                ads_box.opacity = 0
                ads_box.disabled = True
                ads_box.size_hint_y = None
                ads_box.height = 0
            else:
                ads_box.opacity = 1
                ads_box.disabled = False
                ads_box.size_hint_y = None
                ads_box.height = dp(60)

    def buy_remove_ads(self):
        engine = App.get_running_app().engine
        def on_success():
            engine.purchase_remove_ads()
            ad_manager.hide_banner()
            engine.save()
            self.refresh_more()
        iap_manager.purchase("remove_ads", on_success)

    def restore_purchases(self):
        engine = App.get_running_app().engine
        def on_restored(product_keys):
            engine.restore_purchases(product_keys)
            if engine.ads_removed:
                ad_manager.hide_banner()
            engine.save()
            self.refresh_more()
        iap_manager.restore_purchases(on_restored)

    def cloud_sign_in(self):
        if cloud_save_manager.is_connected:
            return
        def on_success():
            self.cloud_status = t("cloud_connected")
            self.refresh_more()
            self._auto_sync_on_login()
        def on_failure(reason):
            self.cloud_status = t("cloud_failed", reason=reason)
        cloud_save_manager.sign_in(on_success, on_failure)

    def _auto_sync_on_login(self):
        engine = App.get_running_app().engine
        self.cloud_status = t("sync") + "..."
        def on_done(success, result):
            if success and isinstance(result, dict):
                engine.load(data=result)
                engine.save()
                self.cloud_status = t("signed_in_as", email=cloud_save_manager.user_email)
            elif not success and result == "No cloud save found":
                save_data = engine.save()
                cloud_save_manager.upload_save(save_data, self._on_initial_upload)
            else:
                self.cloud_status = t("signed_in_as", email=cloud_save_manager.user_email)
        cloud_save_manager.download_save(on_done)

    def _on_initial_upload(self, success, msg):
        self.cloud_status = t("signed_in_as", email=cloud_save_manager.user_email)

    def cloud_sign_out(self):
        def on_done():
            self.refresh_more()
        cloud_save_manager.sign_out(on_done)

    def cloud_upload(self):
        self._confirm_action(
            t("confirm_save_to_cloud"),
            self._do_cloud_upload,
        )

    def _do_cloud_upload(self):
        engine = App.get_running_app().engine
        save_data = engine.save()
        self.cloud_status = t("upload") + "..."
        def on_done(success, msg):
            self.cloud_status = t("cloud_uploaded") if success else t("cloud_failed", reason=msg)
        cloud_save_manager.upload_save(save_data, on_done)

    def cloud_download(self):
        self._confirm_action(
            t("confirm_load_from_cloud"),
            self._do_cloud_download,
        )

    def _do_cloud_download(self):
        engine = App.get_running_app().engine
        self.cloud_status = t("download") + "..."
        def on_done(success, result):
            if success and isinstance(result, dict):
                engine.load(data=result)
                engine.save()
                self.cloud_status = t("cloud_loaded")
            else:
                self.cloud_status = t("cloud_failed", reason=result)
        cloud_save_manager.download_save(on_done)

    def _confirm_action(self, message, on_confirm):
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))
        content.add_widget(Label(
            text=message, font_size=sp(16), color=TEXT_SECONDARY,
            halign="center", valign="middle",
            text_size=(dp(260), None), size_hint_y=1,
        ))
        btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(12))
        popup = Popup(
            title=t("cloud_save"),
            content=content,
            size_hint=(0.88, 0.35),
            background_color=list(BG_CARD)[:3] + [1],
            title_color=list(ACCENT_GOLD)[:3] + [1],
            separator_color=list(ACCENT_GOLD)[:3] + [1],
            auto_dismiss=True,
        )
        cancel_btn = MinimalButton(
            text=t("cancel"), btn_color=TEXT_SECONDARY, font_size=sp(15),
        )
        cancel_btn.bind(on_press=lambda *a: popup.dismiss())
        confirm_btn = MinimalButton(
            text=t("confirm"), btn_color=ACCENT_GREEN, text_color=BG_DARK,
            font_size=sp(15),
        )
        def _on_confirm(*a):
            popup.dismiss()
            on_confirm()
        confirm_btn.bind(on_press=_on_confirm)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)
        popup.open()

    def show_leaderboard(self):
        """Open Play Games fullscreen leaderboard. Sign in first if needed."""
        engine = App.get_running_app().engine

        # Submit scores before showing
        try:
            leaderboard_manager.submit_all(
                best_tier=engine.best_record_tier,
                total_kills=engine.wins,
                strongest_gladiator_kills=engine.best_record_kills,
            )
        except Exception:
            pass

        if leaderboard_manager.is_ready:
            leaderboard_manager.show_all_leaderboards(
                on_failure=lambda err: self._leaderboard_error(err),
            )
        else:
            # Sign in first, then show leaderboard
            def _after_sign_in(success):
                if success:
                    leaderboard_manager.show_all_leaderboards(
                        on_failure=lambda err: self._leaderboard_error(err),
                    )
                else:
                    self._leaderboard_error("Sign-in failed")

            leaderboard_manager.sign_in_interactive(callback=_after_sign_in)

    def _leaderboard_error(self, err):
        """Show a brief error toast when Play Games leaderboard fails."""
        from kivy.uix.label import Label as _Lbl
        content = _Lbl(text=f"Play Games: {err}", font_size=sp(15),
                       color=TEXT_SECONDARY)
        popup = Popup(
            title=t("leaderboard_title"),
            content=content,
            size_hint=(0.8, 0.25),
            background_color=list(BG_CARD)[:3] + [1],
            title_color=list(ACCENT_GOLD)[:3] + [1],
            separator_color=list(ACCENT_GOLD)[:3] + [1],
        )
        popup.open()

    def submit_scores(self):
        engine = App.get_running_app().engine
        leaderboard_manager.submit_all(
            best_tier=engine.best_record_tier,
            total_kills=engine.wins,
            strongest_gladiator_kills=engine.best_record_kills,
        )

    def show_language_picker(self):
        languages = [
            ("English", "en"), ("Русский", "ru"), ("Español", "es"),
            ("Deutsch", "de"), ("Français", "fr"), ("Português", "pt"),
            ("日本語", "ja"), ("한국어", "ko"), ("中文", "zh"),
        ]
        current = get_language()
        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        popup = Popup(
            title=t("language"),
            content=content,
            size_hint=(0.85, 0.7),
            background_color=list(BG_CARD)[:3] + [1],
            title_color=list(ACCENT_GOLD)[:3] + [1],
            separator_color=list(ACCENT_GOLD)[:3] + [1],
        )
        for name, code in languages:
            is_current = code == current
            btn = MinimalButton(
                text=f"{'> ' if is_current else ''}{name}",
                size_hint_y=None,
                height=dp(44),
            )
            btn.btn_color = ACCENT_GOLD if is_current else ACCENT_BLUE
            btn.font_size = sp(17)
            btn.bind(on_press=lambda inst, c=code, p=popup: self._set_language(c, p))
            content.add_widget(btn)
        popup.open()

    def _set_language(self, lang_code, popup):
        popup.dismiss()
        set_language(lang_code)
        App.get_running_app()._init_locale_strings()
        self.refresh_more()


# ============================================================
#  APP
# ============================================================

class GladiatorIdleApp(App):
    bg_dark = ListProperty(BG_DARK)
    bg_card = ListProperty(BG_CARD)
    bg_elevated = ListProperty(BG_ELEVATED)
    accent_gold = ListProperty(ACCENT_GOLD)
    accent_green = ListProperty(ACCENT_GREEN)
    accent_red = ListProperty(ACCENT_RED)
    accent_blue = ListProperty(ACCENT_BLUE)
    accent_cyan = ListProperty(ACCENT_CYAN)
    accent_purple = ListProperty(ACCENT_PURPLE)
    text_primary = ListProperty(TEXT_PRIMARY)
    text_secondary = ListProperty(TEXT_SECONDARY)
    text_muted = ListProperty(TEXT_MUTED)
    nav_bg = ListProperty(NAV_BG)
    divider = ListProperty(DIVIDER)

    # Localized strings for KV bindings
    nav_pit = StringProperty("")
    nav_squad = StringProperty("")
    nav_anvil = StringProperty("")
    nav_hunts = StringProperty("")
    nav_lore = StringProperty("")
    nav_more = StringProperty("")
    title_pit = StringProperty("")
    title_squad = StringProperty("")
    title_anvil = StringProperty("")
    title_hunts = StringProperty("")
    title_lore = StringProperty("")
    title_more = StringProperty("")
    lbl_vs = StringProperty("")
    lbl_auto = StringProperty("")
    lbl_boss = StringProperty("")
    lbl_next = StringProperty("")
    lbl_skip = StringProperty("")
    lbl_achievements = StringProperty("")
    lbl_diamond_shop = StringProperty("")
    lbl_restore_purchases = StringProperty("")
    lbl_cloud_save = StringProperty("")
    lbl_sign_in_google = StringProperty("")
    lbl_sign_out_google = StringProperty("")
    lbl_save_to_cloud = StringProperty("")
    lbl_load_from_cloud = StringProperty("")
    lbl_language = StringProperty("")
    lbl_change_language = StringProperty("")
    lbl_heal_all_injuries = StringProperty("")
    lbl_recruit_fighter = StringProperty("")
    lbl_remove_ads = StringProperty("")
    lbl_remove_ads_buy = StringProperty("")
    lbl_leaderboard = StringProperty("")
    lbl_view_leaderboard = StringProperty("")

    def _init_locale_strings(self):
        self.nav_pit = t("nav_pit")
        self.nav_squad = t("nav_squad")
        self.nav_anvil = t("nav_anvil")
        self.nav_hunts = t("nav_hunts")
        self.nav_lore = t("nav_lore")
        self.nav_more = t("nav_more")
        self.title_pit = t("title_pit")
        self.title_squad = t("title_squad")
        self.title_anvil = t("title_anvil")
        self.title_hunts = t("title_hunts")
        self.title_lore = t("title_lore")
        self.title_more = t("title_more")
        self.lbl_vs = t("vs")
        self.lbl_auto = t("btn_auto")
        self.lbl_boss = t("btn_boss")
        self.lbl_next = t("btn_next")
        self.lbl_skip = t("btn_skip")
        self.lbl_achievements = t("achievements_label")
        self.lbl_diamond_shop = t("diamond_shop_label")
        self.lbl_restore_purchases = t("restore_purchases")
        self.lbl_cloud_save = t("cloud_save")
        self.lbl_sign_in_google = t("sign_in_google")
        self.lbl_sign_out_google = t("sign_out_google")
        self.lbl_save_to_cloud = t("save_to_cloud")
        self.lbl_load_from_cloud = t("load_from_cloud")
        self.lbl_language = t("language")
        self.lbl_change_language = t("change_language")
        self.lbl_heal_all_injuries = t("heal_all_injuries")
        self.lbl_recruit_fighter = t("recruit_fighter_btn")
        self.lbl_remove_ads = t("remove_ads_label")
        self.lbl_remove_ads_buy = t("remove_ads_buy")
        self.lbl_leaderboard = t("leaderboard_title")
        self.lbl_view_leaderboard = t("view_leaderboard")

    def build(self):
        init_language()
        self._init_locale_strings()
        self.engine = GameEngine()
        self.engine.load()

        ad_manager.init()
        iap_manager.init()
        cloud_save_manager.on_auto_connected = self._on_cloud_auto_connected
        cloud_save_manager.init()
        # Leaderboard init is fully optional — deferred and wrapped so any
        # Play Games failure (missing APP_ID, no account, jnius crash) is
        # silently logged and never propagates to the game.
        def _safe_leaderboard_init(dt):
            try:
                leaderboard_manager.init()
            except Exception as exc:
                print(f"[Leaderboard] Startup init suppressed: {exc}")
        Clock.schedule_once(_safe_leaderboard_init, 5.0)

        if self.engine.should_show_banner():
            ad_manager.show_banner()

        # Fix edge-to-edge on Android SDK 35
        if platform == "android":
            try:
                from jnius import autoclass, cast
                from android.runnable import run_on_ui_thread

                @run_on_ui_thread
                def _fix_window():
                    try:
                        PythonActivity = autoclass("org.kivy.android.PythonActivity")
                        activity = PythonActivity.mActivity
                        window = activity.getWindow()
                        # Dark color as signed int: 0xFF0D0D0F = -16249585
                        dark_color = -16249585
                        window.setStatusBarColor(dark_color)
                        window.setNavigationBarColor(dark_color)
                        window.setDecorFitsSystemWindows(True)
                        print("[UI] Set decorFitsSystemWindows=True")
                    except Exception as e2:
                        print(f"[UI] Window fix error: {e2}")

                _fix_window()
            except Exception as e:
                print(f"[UI] Edge-to-edge fix error: {e}")

        sm = SwipeScreenManager(transition=NoTransition())
        sm.add_widget(ArenaScreen(name="arena"))
        sm.add_widget(RosterScreen(name="roster"))
        sm.add_widget(ForgeScreen(name="forge"))
        sm.add_widget(ExpeditionScreen(name="expedition"))
        sm.add_widget(LoreScreen(name="lore"))
        sm.add_widget(MoreScreen(name="more"))

        Clock.schedule_interval(self._idle_tick, 1.0)
        Clock.schedule_interval(self._auto_save, 30.0)

        # DEBUG: FPS counter overlay (prints to logcat)
        def _log_fps(dt):
            print(f"[FPS] {Clock.get_fps():.1f}")
        Clock.schedule_interval(_log_fps, 2.0)

        return sm

    def _on_cloud_auto_connected(self):
        """Auto-sync on silent sign-in at startup."""
        def on_done(success, result):
            if success and isinstance(result, dict):
                self.engine.load(data=result)
                self.engine.save()
                print("[CloudSave] Auto-loaded cloud save on startup")
            elif not success and result == "No cloud save found":
                save_data = self.engine.save()
                cloud_save_manager.upload_save(save_data)
                print("[CloudSave] No cloud save — uploaded local on startup")
        cloud_save_manager.download_save(on_done)

    def _idle_tick(self, dt):
        self.engine.idle_tick(dt)
        scr = self.root.current_screen
        for attr in ("refresh_ui", "refresh_roster", "refresh_forge",
                     "refresh_expeditions", "refresh_lore", "refresh_more"):
            if hasattr(scr, attr):
                getattr(scr, attr)()
                break

    def _auto_save(self, dt):
        self.engine.save()
        if cloud_save_manager.is_connected:
            cloud_save_manager.upload_save(self.engine.save())

    def on_stop(self):
        self.engine.save()
        if cloud_save_manager.is_connected:
            cloud_save_manager.upload_save(self.engine.save())

    def show_class_selection(self):
        """Show popup to choose fighter class before hiring."""
        content = BoxLayout(orientation="vertical", spacing=8, padding=[12, 10])

        content.add_widget(Label(
            text=t("choose_class"), font_size="19sp",
            color=ACCENT_GOLD, size_hint_y=None, height=dp(30),
        ))

        for cls_id, cls_data in FIGHTER_CLASSES.items():
            row = BoxLayout(size_hint_y=None, height=dp(110), spacing=dp(6))

            info = BoxLayout(orientation="vertical", size_hint_x=0.65, spacing=dp(2))
            name_lbl = Label(
                text=cls_data["name"], font_size="19sp", bold=True,
                color=ACCENT_GREEN if cls_id == "mercenary" else
                      ACCENT_RED if cls_id == "assassin" else ACCENT_BLUE,
                halign="left",
                size_hint_y=None, height=dp(30),
            )
            name_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            info.add_widget(name_lbl)
            stat_line = f"STR {cls_data['base_str']}  AGI {cls_data['base_agi']}  VIT {cls_data['base_vit']}"
            stat_lbl = Label(
                text=stat_line, font_size="15sp", color=TEXT_SECONDARY,
                halign="left",
                size_hint_y=None, height=dp(24),
            )
            stat_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            info.add_widget(stat_lbl)
            desc_lbl = Label(
                text=cls_data["desc"], font_size="15sp", color=TEXT_MUTED,
                halign="left",
                size_hint_y=None, height=dp(40),
            )
            desc_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            info.add_widget(desc_lbl)

            btn = MinimalButton(
                text=t("btn_select"), font_size=17, size_hint_x=0.35,
                btn_color=ACCENT_GOLD, text_color=BG_DARK,
            )

            row.add_widget(info)
            row.add_widget(btn)
            content.add_widget(row)

            # Bind must capture cls_id
            btn.bind(on_press=lambda inst, cid=cls_id: self._hire_with_class(cid))

        popup = Popup(
            title=t("recruit_fighter"),
            title_color=ACCENT_GOLD, title_size="16sp",
            content=content,
            size_hint=(0.9, None), height=dp(500),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_GOLD,
        )
        self._class_popup = popup
        popup.open()

    def _hire_with_class(self, class_id):
        if hasattr(self, '_class_popup'):
            self._class_popup.dismiss()
        self.engine.hire_gladiator(class_id)
        scr = self.root.current_screen
        if hasattr(scr, "refresh_roster"):
            scr.refresh_roster()
        elif hasattr(scr, "refresh_ui"):
            scr.refresh_ui()

    def show_tutorial(self, step):
        self.engine.mark_tutorial_shown(step["id"])
        content = BoxLayout(orientation="vertical", spacing=8, padding=[16, 12])
        for line in step["lines"]:
            lbl = Label(
                text=line, font_size="18sp", color=TEXT_PRIMARY,
                halign="left", size_hint_y=None, height=dp(40),
            )
            lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
            content.add_widget(lbl)
        close_btn = MinimalButton(
            text=t("got_it"), btn_color=ACCENT_GOLD, text_color=BG_DARK,
            font_size=19, size_hint_y=None, height=dp(48),
        )
        content.add_widget(close_btn)
        popup = Popup(
            title=step["title"], title_color=ACCENT_GOLD, title_size="16sp",
            content=content, size_hint=(0.85, None),
            height=dp(min(120 + len(step["lines"]) * 40, 400)),
            background_color=(0.08, 0.08, 0.11, 0.95),
            separator_color=ACCENT_GOLD,
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()


if __name__ == "__main__":
    GladiatorIdleApp().run()
