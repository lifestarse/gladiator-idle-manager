"""
Gladiator Idle Manager — hyper-casual idle game.
Minimalist geometric style inspired by The Tower.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.core.window import Window

from game.engine import GameEngine
from game.theme import *
from game.widgets import (
    MinimalBar, GladiatorAvatar, MinimalButton,
    CardWidget, NavButton, FloatingText,
)
from game.ui_helpers import (
    refresh_roster_grid, refresh_shop_grid,
    refresh_forge_grid, refresh_expedition_grid,
)
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager

Window.size = (360, 640)
Window.clearcolor = BG_DARK


class ArenaScreen(Screen):
    gold_text = StringProperty("0")
    gladiator_name = StringProperty("")
    gladiator_hp_text = StringProperty("")
    gladiator_level = StringProperty("")
    enemy_name = StringProperty("")
    enemy_hp_text = StringProperty("")
    enemy_tier = StringProperty("")
    battle_log = StringProperty("Tap FIGHT to begin")
    player_hp_pct = NumericProperty(1.0)
    enemy_hp_pct = NumericProperty(1.0)
    wins_text = StringProperty("0")
    idle_rate_text = StringProperty("0.0/s")
    injuries_text = StringProperty("")
    death_risk_text = StringProperty("")
    ad_bonus_text = StringProperty("")

    def on_enter(self):
        self.refresh_ui()

    def refresh_ui(self):
        engine = App.get_running_app().engine
        g = engine.get_active_gladiator()
        e = engine.current_enemy
        self.gold_text = f"{engine.gold:,.0f}"
        self.wins_text = f"{engine.wins}"
        self.idle_rate_text = f"+{engine.effective_idle_rate:.1f}/s"
        self.ad_bonus_text = engine.get_rewarded_ad_time_left()
        if g:
            self.gladiator_name = g.name
            self.gladiator_hp_text = f"{max(0, g.hp)}/{g.max_hp}"
            self.gladiator_level = f"LV {g.level}"
            self.player_hp_pct = max(0, g.hp / g.max_hp)
            self.injuries_text = f"Injuries: {g.injuries}" if g.injuries > 0 else ""
            self.death_risk_text = f"Death risk: {g.death_chance:.0%}" if g.injuries > 0 else ""
        else:
            self.gladiator_name = "NO FIGHTERS"
            self.gladiator_hp_text = ""
            self.gladiator_level = ""
            self.player_hp_pct = 0
            self.injuries_text = ""
            self.death_risk_text = ""
        if e:
            self.enemy_name = e.name
            self.enemy_hp_text = f"{max(0, e.hp)}/{e.max_hp}"
            self.enemy_tier = f"TIER {e.tier}"
            self.enemy_hp_pct = max(0, e.hp / e.max_hp)

    def fight(self):
        engine = App.get_running_app().engine
        result = engine.do_battle_tick()
        self.battle_log = result
        self.refresh_ui()

        # Show interstitial ad after certain wins
        if engine.should_show_interstitial():
            ad_manager.show_interstitial()

        if "Victory" in result:
            gold_part = result.split("+")[-1].split(" ")[0] if "+" in result else ""
            if gold_part:
                self._spawn_float(f"+{gold_part}", ACCENT_GOLD)
        elif "FALLEN" in result:
            self._spawn_float("PERMADEATH!", ACCENT_RED)
        elif "survived" in result.lower():
            self._spawn_float("INJURED!", (1, 0.6, 0.2, 1))

    def watch_ad(self):
        engine = App.get_running_app().engine
        if not engine.can_watch_rewarded_ad():
            self.battle_log = "Daily ad limit reached (10/day)"
            return
        ad_manager.show_rewarded(on_reward_callback=self._on_ad_reward)

    def _on_ad_reward(self):
        engine = App.get_running_app().engine
        msg = engine.on_rewarded_ad_watched()
        self.battle_log = msg
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
                "name": f.name, "level": f.level, "atk": f.attack,
                "def": f.defense, "hp": f.max_hp, "cost": f.upgrade_cost,
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
        App.get_running_app().engine.hire_gladiator()
        self.refresh_roster()

    def dismiss(self, index):
        App.get_running_app().engine.dismiss_dead(index)
        self.refresh_roster()


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
                f"{f.name} Lv.{f.level}  |  "
                f"W: {equip_names[0]}  A: {equip_names[1]}  R: {equip_names[2]}"
            )
        else:
            self.active_fighter_text = "No active fighter"
        refresh_forge_grid(self)

    def buy(self, item_id):
        App.get_running_app().engine.buy_forge_item(item_id)
        self.refresh_forge()


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


class ShopScreen(Screen):
    gold_text = StringProperty("0")
    idle_rate_text = StringProperty("")
    items_data = ListProperty()

    def on_enter(self):
        self.refresh_shop()

    def refresh_shop(self):
        engine = App.get_running_app().engine
        self.gold_text = f"{engine.gold:,.0f}"
        self.idle_rate_text = f"+{engine.effective_idle_rate:.1f} gold/sec"
        if engine.vip_idle_boost:
            self.idle_rate_text += " (VIP 1.5x)"
        self.items_data = engine.get_shop_items()
        refresh_shop_grid(self)

    def buy(self, item_id):
        App.get_running_app().engine.buy_item(item_id)
        self.refresh_shop()


class SettingsScreen(Screen):
    """Settings — IAP, cloud save, restore purchases."""
    cloud_status = StringProperty("Not connected")
    ads_status = StringProperty("Active")
    vip_status = StringProperty("Not purchased")

    def on_enter(self):
        self.refresh_settings()

    def refresh_settings(self):
        engine = App.get_running_app().engine
        self.cloud_status = cloud_save_manager.last_sync_status
        self.ads_status = "Removed" if engine.ads_removed else "Active"
        self.vip_status = "Active (1.5x)" if engine.vip_idle_boost else "Not purchased"

    def buy_remove_ads(self):
        engine = App.get_running_app().engine
        def on_success():
            engine.purchase_remove_ads()
            ad_manager.hide_banner()
            engine.save()
            self.refresh_settings()
        iap_manager.purchase("remove_ads", on_success)

    def buy_vip_idle(self):
        engine = App.get_running_app().engine
        def on_success():
            engine.purchase_vip_idle()
            engine.save()
            self.refresh_settings()
        iap_manager.purchase("vip_idle", on_success)

    def restore_purchases(self):
        engine = App.get_running_app().engine
        def on_restored(product_keys):
            engine.restore_purchases(product_keys)
            if engine.ads_removed:
                ad_manager.hide_banner()
            engine.save()
            self.refresh_settings()
        iap_manager.restore_purchases(on_restored)

    def cloud_sign_in(self):
        def on_success():
            self.cloud_status = "Connected!"
            self.refresh_settings()
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
                engine.save()  # save locally too
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

        # Init monetization
        ad_manager.init()
        iap_manager.init()
        cloud_save_manager.init()

        # Show banner if ads not removed
        if self.engine.should_show_banner():
            ad_manager.show_banner()

        sm = ScreenManager(transition=FadeTransition(duration=0.2))
        sm.add_widget(ArenaScreen(name="arena"))
        sm.add_widget(RosterScreen(name="roster"))
        sm.add_widget(ForgeScreen(name="forge"))
        sm.add_widget(ExpeditionScreen(name="expedition"))
        sm.add_widget(ShopScreen(name="shop"))
        sm.add_widget(SettingsScreen(name="settings"))

        Clock.schedule_interval(self._idle_tick, 1.0)
        Clock.schedule_interval(self._auto_save, 30.0)
        return sm

    def _idle_tick(self, dt):
        self.engine.idle_tick(dt)
        scr = self.root.current_screen
        for attr in ("refresh_ui", "refresh_roster", "refresh_forge",
                     "refresh_expeditions", "refresh_shop", "refresh_settings"):
            if hasattr(scr, attr):
                getattr(scr, attr)()
                break

    def _auto_save(self, dt):
        self.engine.save()

    def on_stop(self):
        self.engine.save()


if __name__ == "__main__":
    GladiatorIdleApp().run()
