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
    death_risk_text = StringProperty("")
    injuries_text = StringProperty("")

    def on_enter(self):
        self.refresh_ui()

    def refresh_ui(self):
        engine = App.get_running_app().engine
        g = engine.get_active_gladiator()
        e = engine.current_enemy
        self.gold_text = f"{engine.gold:,.0f}"
        self.wins_text = f"{engine.wins}"
        self.idle_rate_text = f"+{engine.idle_gold_rate:.1f}/s"
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
        if "Victory" in result:
            gold_part = result.split("+")[-1].split(" ")[0] if "+" in result else ""
            if gold_part:
                self._spawn_float(f"+{gold_part}", ACCENT_GOLD)
        elif "FALLEN" in result:
            self._spawn_float("PERMADEATH!", ACCENT_RED)
        elif "survived" in result.lower():
            self._spawn_float("INJURED!", (1, 0.6, 0.2, 1))

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
                "name": f.name,
                "level": f.level,
                "atk": f.attack,
                "def": f.defense,
                "hp": f.max_hp,
                "cost": f.upgrade_cost,
                "index": i,
                "active": i == engine.active_fighter_idx,
                "alive": f.alive,
                "injuries": f.injuries,
                "kills": f.kills,
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
        result = App.get_running_app().engine.send_on_expedition(fighter_idx, expedition_id)
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
        self.idle_rate_text = f"+{engine.idle_gold_rate:.1f} gold/sec"
        self.items_data = engine.get_shop_items()
        refresh_shop_grid(self)

    def buy(self, item_id):
        App.get_running_app().engine.buy_item(item_id)
        self.refresh_shop()


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

        sm = ScreenManager(transition=FadeTransition(duration=0.2))
        sm.add_widget(ArenaScreen(name="arena"))
        sm.add_widget(RosterScreen(name="roster"))
        sm.add_widget(ForgeScreen(name="forge"))
        sm.add_widget(ExpeditionScreen(name="expedition"))
        sm.add_widget(ShopScreen(name="shop"))

        Clock.schedule_interval(self._idle_tick, 1.0)
        Clock.schedule_interval(self._auto_save, 30.0)
        return sm

    def _idle_tick(self, dt):
        self.engine.idle_tick(dt)
        scr = self.root.current_screen
        if hasattr(scr, "refresh_ui"):
            scr.refresh_ui()
        elif hasattr(scr, "refresh_roster"):
            scr.refresh_roster()
        elif hasattr(scr, "refresh_forge"):
            scr.refresh_forge()
        elif hasattr(scr, "refresh_expeditions"):
            scr.refresh_expeditions()
        elif hasattr(scr, "refresh_shop"):
            scr.refresh_shop()

    def _auto_save(self, dt):
        self.engine.save()

    def on_stop(self):
        self.engine.save()


if __name__ == "__main__":
    GladiatorIdleApp().run()
