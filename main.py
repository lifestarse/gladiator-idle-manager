"""
Gladiator Idle Manager — roguelike-manager.
Permadeath resets the run. Stats distributed manually. Fighter classes.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.core.window import Window

from game.engine import GameEngine
from game.models import FIGHTER_CLASSES
from game.theme import *
from game.widgets import (
    MinimalBar, GladiatorAvatar, MinimalButton,
    CardWidget, NavButton, FloatingText,
)
from game.ui_helpers import (
    refresh_roster_grid, refresh_shop_grid,
    refresh_forge_grid, refresh_expedition_grid,
    refresh_battle_log, refresh_achievement_grid,
    refresh_diamond_shop_grid,
)
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager

Window.size = (360, 640)
Window.clearcolor = BG_DARK


# ============================================================
#  ARENA / BATTLE (THE PIT)
# ============================================================

class ArenaScreen(Screen):
    gold_text = StringProperty("0")
    diamond_text = StringProperty("0")
    wins_text = StringProperty("0")
    tier_text = StringProperty("TIER 1")
    idle_rate_text = StringProperty("0.0/s")
    ad_bonus_text = StringProperty("")
    battle_status = StringProperty("Ready to fight")
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
        self.gold_text = f"{engine.gold:,.0f}"
        self.diamond_text = f"{engine.diamonds}"
        self.wins_text = f"{engine.wins}W"
        self.tier_text = f"TIER {engine.arena_tier}"
        self.idle_rate_text = f"+{engine.effective_idle_rate:.1f}/s"
        self.ad_bonus_text = engine.get_rewarded_ad_time_left()

        # Record & run
        if engine.best_record_tier > 0:
            self.record_text = f"Best: T{engine.best_record_tier} / {engine.best_record_kills} kills"
        else:
            self.record_text = "Best: ---"
        self.run_text = f"Run #{engine.run_number}  |  T{engine.run_max_tier}  |  {engine.run_kills} kills"

        fighters = [f for f in engine.fighters if f.alive and not f.on_expedition]
        self.player_summary = f"{len(fighters)} fighters ready"

        if engine.battle_active:
            s = engine.battle_mgr.state
            alive_f = sum(1 for f in s.player_fighters if f.alive and f.hp > 0)
            alive_e = sum(1 for e in s.enemies if e.hp > 0)
            self.player_summary = f"{alive_f} fighters alive"
            self.enemy_summary = f"{alive_e} enemies left"
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

    def _check_pending_reset(self):
        engine = App.get_running_app().engine
        if engine.pending_reset:
            self._show_reset_popup(engine)

    def _show_reset_popup(self, engine):
        content = BoxLayout(orientation="vertical", spacing=10, padding=[16, 12])
        content.add_widget(Label(
            text="ALL FIGHTERS DEAD!", font_size="18sp", bold=True,
            color=ACCENT_RED, size_hint_y=None, height=35,
        ))
        content.add_widget(Label(
            text=f"Run #{engine.run_number} ended.", font_size="13sp",
            color=TEXT_PRIMARY, size_hint_y=None, height=25,
        ))
        content.add_widget(Label(
            text=f"Reached Tier {engine.run_max_tier}  |  {engine.run_kills} kills",
            font_size="13sp", color=ACCENT_GOLD, size_hint_y=None, height=25,
        ))
        content.add_widget(Label(
            text="Gold and equipment are lost.\nDiamonds and achievements persist.",
            font_size="11sp", color=TEXT_SECONDARY, size_hint_y=None, height=40,
            text_size=(280, None), halign="center",
        ))

        restart_btn = MinimalButton(
            text="NEW RUN", btn_color=ACCENT_RED, font_size=15,
            size_hint_y=None, height=48,
        )
        content.add_widget(restart_btn)

        popup = Popup(
            title="PERMADEATH", title_color=ACCENT_RED, title_size="16sp",
            content=content, size_hint=(0.9, None), height=280,
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
        self.battle_status = "AUTO BATTLE!"
        self._display_events(events)
        Clock.schedule_interval(self._auto_turn, 0.8)

    def start_boss_fight(self):
        engine = App.get_running_app().engine
        if engine.battle_active:
            return
        events = engine.start_boss_fight()
        self.battle_status = "BOSS CHALLENGE!"
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
            self.battle_status = f"VICTORY! +{state.gold_earned}g"
            self._spawn_float(f"+{state.gold_earned}g", ACCENT_GOLD)
            if engine.should_show_interstitial():
                ad_manager.show_interstitial()
        elif state.phase == BattlePhase.DEFEAT:
            Clock.unschedule(self._auto_turn)
            self.battle_status = "DEFEAT!"
            self._spawn_float("DEFEATED!", ACCENT_RED)
            Clock.schedule_once(lambda dt: self._check_pending_reset(), 1.0)

    def _display_events(self, events):
        lines = []
        for ev in events[-6:]:
            if ev.is_crit:
                lines.append(f"[CRIT] {ev.message}")
            elif ev.is_kill:
                lines.append(f"[KILL] {ev.message}")
            elif ev.damage == 0 and "DODGE" in ev.message:
                lines.append(f"[DODGE] {ev.message}")
            else:
                lines.append(ev.message)
        self.battle_log_text = "\n".join(lines)
        refresh_battle_log(self)

    def watch_ad(self):
        engine = App.get_running_app().engine
        if not engine.can_watch_rewarded_ad():
            self.battle_status = "Daily ad limit reached (10/day)"
            return
        ad_manager.show_rewarded(on_reward_callback=self._on_ad_reward)

    def _on_ad_reward(self):
        engine = App.get_running_app().engine
        msg = engine.on_rewarded_ad_watched()
        self.battle_status = msg
        self.refresh_ui()

    def _spawn_float(self, text, color):
        arena = self.ids.get("arena_zone")
        if arena:
            ft = FloatingText(
                text=text, font_size="20sp", bold=True, color=color,
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

    def on_enter(self):
        self.refresh_roster()

    def refresh_roster(self):
        engine = App.get_running_app().engine
        self.gold_text = f"{engine.gold:,.0f}"
        deaths = engine.total_deaths
        self.graveyard_text = f"Fallen: {deaths}" if deaths > 0 else ""
        self.gladiators_data = [
            {
                "name": f.name, "level": f.level,
                "fighter_class": f.class_name,
                "str": f.strength, "agi": f.agility, "vit": f.vitality,
                "unused_points": f.unused_points,
                "atk": f.attack, "def": f.defense, "hp": f.max_hp,
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


# ============================================================
#  FORGE (ANVIL)
# ============================================================

class ForgeScreen(Screen):
    gold_text = StringProperty("0")
    forge_items = ListProperty()
    active_fighter_text = StringProperty("")

    def on_enter(self):
        self.refresh_forge()

    def refresh_forge(self):
        engine = App.get_running_app().engine
        self.gold_text = f"{engine.gold:,.0f}"
        self.forge_items = engine.get_forge_items()
        f = engine.get_active_gladiator()
        if f:
            equip_names = []
            for slot in ["weapon", "armor", "accessory"]:
                item = f.equipment.get(slot)
                equip_names.append(item["name"] if item else "---")
            self.active_fighter_text = (
                f"{f.name} [{f.class_name}] Lv.{f.level}  |  "
                f"W: {equip_names[0]}  A: {equip_names[1]}  R: {equip_names[2]}"
            )
        else:
            self.active_fighter_text = "No active fighter"
        refresh_forge_grid(self)

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
        self.gold_text = f"{engine.gold:,.0f}"
        self.expeditions_data = engine.get_expeditions()
        self.status_data = engine.get_expedition_status()
        self.log_text = "\n".join(engine.expedition_log[-5:]) if engine.expedition_log else "No expeditions yet"
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
    story_title = StringProperty("")
    story_text = StringProperty("")
    story_boss_text = StringProperty("")
    story_available = StringProperty("false")
    achievements_data = ListProperty()
    diamond_shop_data = ListProperty()

    def on_enter(self):
        self.refresh_lore()

    def refresh_lore(self):
        engine = App.get_running_app().engine
        self.diamond_text = f"{engine.diamonds}"

        chapter = engine.get_current_story()
        if chapter:
            self.story_title = f"Ch.{chapter['chapter']}: {chapter['title']}"
            self.story_text = "\n".join(chapter["intro"])
            self.story_boss_text = f"Boss: {chapter['boss_name']} (Tier +{chapter['boss_tier_bonus']})"
            can_fight = engine.arena_tier >= chapter["unlock_tier"]
            self.story_available = "true" if can_fight else "false"
            if not can_fight:
                self.story_boss_text += f"\nUnlocks at Tier {chapter['unlock_tier']}"
        else:
            self.story_title = "Story Complete!"
            self.story_text = "You have conquered all challenges."
            self.story_boss_text = ""
            self.story_available = "false"

        self.achievements_data = engine.get_achievements()
        refresh_achievement_grid(self)
        self.diamond_shop_data = engine.get_diamond_shop()
        refresh_diamond_shop_grid(self)

    def fight_story_boss(self):
        engine = App.get_running_app().engine
        chapter, msg = engine.start_story_boss()
        if chapter:
            App.get_running_app().root.current = "arena"
            arena = App.get_running_app().root.get_screen("arena")
            arena.battle_status = f"STORY BOSS: {chapter['boss_name']}!"
            arena.refresh_ui()
        else:
            self.story_boss_text = msg

    def buy_diamond_item(self, item_id):
        engine = App.get_running_app().engine
        msg = engine.buy_diamond_item(item_id)
        self.story_boss_text = msg
        self.refresh_lore()


# ============================================================
#  MORE (Market + Settings)
# ============================================================

class MoreScreen(Screen):
    gold_text = StringProperty("0")
    idle_rate_text = StringProperty("")
    items_data = ListProperty()
    cloud_status = StringProperty("Not connected")
    ads_status = StringProperty("Active")
    vip_status = StringProperty("Not purchased")

    def on_enter(self):
        self.refresh_more()

    def refresh_more(self):
        engine = App.get_running_app().engine
        self.gold_text = f"{engine.gold:,.0f}"
        self.idle_rate_text = f"+{engine.effective_idle_rate:.1f} gold/sec"
        if engine.vip_idle_boost:
            self.idle_rate_text += " (VIP 1.5x)"
        self.items_data = engine.get_shop_items()
        self.cloud_status = cloud_save_manager.last_sync_status
        self.ads_status = "Removed" if engine.ads_removed else "Active"
        self.vip_status = "Active (1.5x)" if engine.vip_idle_boost else "Not purchased"
        refresh_shop_grid(self)

    def buy(self, item_id):
        App.get_running_app().engine.buy_item(item_id)
        self.refresh_more()

    def buy_remove_ads(self):
        engine = App.get_running_app().engine
        def on_success():
            engine.purchase_remove_ads()
            ad_manager.hide_banner()
            engine.save()
            self.refresh_more()
        iap_manager.purchase("remove_ads", on_success)

    def buy_vip_idle(self):
        engine = App.get_running_app().engine
        def on_success():
            engine.purchase_vip_idle()
            engine.save()
            self.refresh_more()
        iap_manager.purchase("vip_idle", on_success)

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
        def on_success():
            self.cloud_status = "Connected!"
        def on_failure(reason):
            self.cloud_status = f"Failed: {reason}"
        cloud_save_manager.sign_in(on_success, on_failure)

    def cloud_upload(self):
        engine = App.get_running_app().engine
        save_data = engine.save()
        def on_done(success, msg):
            self.cloud_status = msg if isinstance(msg, str) else "Uploaded!"
        cloud_save_manager.upload_save(save_data, on_done)

    def cloud_download(self):
        engine = App.get_running_app().engine
        def on_done(success, result):
            if success and isinstance(result, dict):
                engine.load(data=result)
                engine.save()
                self.cloud_status = "Loaded from cloud!"
            else:
                self.cloud_status = f"Failed: {result}"
        cloud_save_manager.download_save(on_done)

    def cloud_sync(self):
        engine = App.get_running_app().engine
        local_data = engine.save()
        def on_done(action, data):
            if action == "downloaded" and data:
                engine.load(data=data)
                engine.save()
                self.cloud_status = "Synced (cloud was newer)"
            elif action == "uploaded":
                self.cloud_status = "Synced (uploaded local)"
            else:
                self.cloud_status = f"Sync: {action}"
        cloud_save_manager.sync_save(local_data, on_done)


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

    def build(self):
        self.engine = GameEngine()
        self.engine.load()

        ad_manager.init()
        iap_manager.init()
        cloud_save_manager.init()

        if self.engine.should_show_banner():
            ad_manager.show_banner()

        sm = ScreenManager(transition=FadeTransition(duration=0.2))
        sm.add_widget(ArenaScreen(name="arena"))
        sm.add_widget(RosterScreen(name="roster"))
        sm.add_widget(ForgeScreen(name="forge"))
        sm.add_widget(ExpeditionScreen(name="expedition"))
        sm.add_widget(LoreScreen(name="lore"))
        sm.add_widget(MoreScreen(name="more"))

        Clock.schedule_interval(self._idle_tick, 1.0)
        Clock.schedule_interval(self._auto_save, 30.0)
        return sm

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

    def on_stop(self):
        self.engine.save()

    def show_class_selection(self):
        """Show popup to choose fighter class before hiring."""
        content = BoxLayout(orientation="vertical", spacing=8, padding=[12, 10])

        content.add_widget(Label(
            text="Choose a starter class:", font_size="14sp",
            color=ACCENT_GOLD, size_hint_y=None, height=30,
        ))

        for cls_id, cls_data in FIGHTER_CLASSES.items():
            row = BoxLayout(size_hint_y=None, height=60, spacing=6)

            info = BoxLayout(orientation="vertical", size_hint_x=0.65)
            info.add_widget(Label(
                text=cls_data["name"], font_size="14sp", bold=True,
                color=ACCENT_GREEN if cls_id == "mercenary" else
                      ACCENT_RED if cls_id == "assassin" else ACCENT_BLUE,
                halign="left", text_size=(200, None),
                size_hint_y=0.5,
            ))
            stat_line = f"STR {cls_data['base_str']}  AGI {cls_data['base_agi']}  VIT {cls_data['base_vit']}"
            info.add_widget(Label(
                text=stat_line, font_size="10sp", color=TEXT_SECONDARY,
                halign="left", text_size=(200, None),
                size_hint_y=0.25,
            ))
            info.add_widget(Label(
                text=cls_data["desc"], font_size="9sp", color=TEXT_MUTED,
                halign="left", text_size=(200, None),
                size_hint_y=0.25,
            ))

            btn = MinimalButton(
                text="SELECT", font_size=12, size_hint_x=0.35,
                btn_color=ACCENT_GOLD, text_color=BG_DARK,
            )

            row.add_widget(info)
            row.add_widget(btn)
            content.add_widget(row)

            # Bind must capture cls_id
            btn.bind(on_press=lambda inst, cid=cls_id: self._hire_with_class(cid))

        popup = Popup(
            title="Recruit Fighter",
            title_color=ACCENT_GOLD, title_size="16sp",
            content=content,
            size_hint=(0.9, None), height=320,
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
            content.add_widget(Label(
                text=line, font_size="13sp", color=TEXT_PRIMARY,
                text_size=(300, None), halign="left", size_hint_y=None, height=30,
            ))
        close_btn = MinimalButton(
            text="GOT IT", btn_color=ACCENT_GOLD, text_color=BG_DARK,
            font_size=14, size_hint_y=None, height=44,
        )
        content.add_widget(close_btn)
        popup = Popup(
            title=step["title"], title_color=ACCENT_GOLD, title_size="16sp",
            content=content, size_hint=(0.85, None),
            height=min(100 + len(step["lines"]) * 35, 350),
            background_color=(0.08, 0.08, 0.11, 0.95),
            separator_color=ACCENT_GOLD,
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def show_story_completion(self, completion_lines):
        content = BoxLayout(orientation="vertical", spacing=8, padding=[16, 12])
        for line in completion_lines:
            content.add_widget(Label(
                text=line, font_size="13sp", color=ACCENT_GOLD,
                text_size=(300, None), halign="center", size_hint_y=None, height=30,
            ))
        close_btn = MinimalButton(
            text="CONTINUE", btn_color=ACCENT_GREEN, text_color=BG_DARK,
            font_size=14, size_hint_y=None, height=44,
        )
        content.add_widget(close_btn)
        popup = Popup(
            title="Chapter Complete!", title_color=ACCENT_GOLD, title_size="18sp",
            content=content, size_hint=(0.85, None),
            height=min(100 + len(completion_lines) * 35, 350),
            background_color=(0.08, 0.08, 0.11, 0.95),
            separator_color=ACCENT_GOLD,
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()


if __name__ == "__main__":
    GladiatorIdleApp().run()
