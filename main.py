"""
Gladiator Idle Manager — hyper-casual idle game.
Minimalist geometric style inspired by The Tower.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.core.window import Window
from kivy.animation import Animation

from game.engine import GameEngine
from game.theme import *
from game.widgets import (
    MinimalBar, GladiatorAvatar, MinimalButton,
    CardWidget, NavButton, FloatingText,
)
from game.ui_helpers import refresh_roster_grid, refresh_shop_grid

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
        # Spawn floating text for gold on victory
        if "Victory" in result:
            gold_part = result.split("+")[-1].split(" ")[0] if "+" in result else ""
            if gold_part:
                self._spawn_float(f"+{gold_part}", ACCENT_GOLD)
        elif "defeated" in result.lower():
            self._spawn_float("DEFEATED", ACCENT_RED)

    def _spawn_float(self, text, color):
        arena = self.ids.get("arena_zone")
        if arena:
            ft = FloatingText(
                text=text,
                font_size="20sp",
                bold=True,
                color=color,
                center_x=arena.center_x,
                y=arena.center_y,
                size_hint=(None, None),
            )
            arena.add_widget(ft)


class RosterScreen(Screen):
    gladiators_data = ListProperty()
    gold_text = StringProperty("0")

    def on_enter(self):
        self.refresh_roster()

    def refresh_roster(self):
        engine = App.get_running_app().engine
        self.gold_text = f"{engine.gold:,.0f}"
        self.gladiators_data = [
            {
                "name": g.name,
                "level": g.level,
                "atk": g.attack,
                "def": g.defense,
                "hp": g.max_hp,
                "cost": g.upgrade_cost,
                "index": i,
                "active": i == engine.active_gladiator_idx,
            }
            for i, g in enumerate(engine.gladiators)
        ]
        refresh_roster_grid(self)

    def upgrade(self, index):
        engine = App.get_running_app().engine
        engine.upgrade_gladiator(index)
        self.refresh_roster()

    def set_active(self, index):
        engine = App.get_running_app().engine
        engine.active_gladiator_idx = index
        self.refresh_roster()

    def hire(self):
        engine = App.get_running_app().engine
        engine.hire_gladiator()
        self.refresh_roster()


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
        engine = App.get_running_app().engine
        engine.buy_item(item_id)
        self.refresh_shop()


class GladiatorIdleApp(App):
    # Expose theme colors to KV
    bg_dark = ListProperty(BG_DARK)
    bg_card = ListProperty(BG_CARD)
    bg_elevated = ListProperty(BG_ELEVATED)
    accent_gold = ListProperty(ACCENT_GOLD)
    accent_green = ListProperty(ACCENT_GREEN)
    accent_red = ListProperty(ACCENT_RED)
    accent_blue = ListProperty(ACCENT_BLUE)
    accent_cyan = ListProperty(ACCENT_CYAN)
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
        elif hasattr(scr, "refresh_shop"):
            scr.refresh_shop()

    def _auto_save(self, dt):
        self.engine.save()

    def on_stop(self):
        self.engine.save()


if __name__ == "__main__":
    GladiatorIdleApp().run()
