"""
Gladiator Idle Manager — hyper-casual idle game.
Built with Kivy for cross-platform mobile deployment.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty
from kivy.core.window import Window

from game.engine import GameEngine
from game.ui_helpers import refresh_roster_grid, refresh_shop_grid

# Mobile-friendly window size for desktop testing
Window.size = (360, 640)


class ArenaScreen(Screen):
    """Main screen — arena with auto-battles and idle income."""

    gold_text = StringProperty("0")
    gladiator_name = StringProperty("")
    gladiator_hp = StringProperty("")
    enemy_name = StringProperty("")
    enemy_hp = StringProperty("")
    battle_log = StringProperty("Tap [Fight!] to begin...")
    player_hp_pct = NumericProperty(1.0)
    enemy_hp_pct = NumericProperty(1.0)

    def on_enter(self):
        self.refresh_ui()

    def refresh_ui(self):
        engine = App.get_running_app().engine
        g = engine.get_active_gladiator()
        e = engine.current_enemy

        self.gold_text = f"{engine.gold:,.0f}"
        if g:
            self.gladiator_name = g.name
            self.gladiator_hp = f"{g.hp}/{g.max_hp}"
            self.player_hp_pct = max(0, g.hp / g.max_hp)
        if e:
            self.enemy_name = e.name
            self.enemy_hp = f"{e.hp}/{e.max_hp}"
            self.enemy_hp_pct = max(0, e.hp / e.max_hp)

    def fight(self):
        engine = App.get_running_app().engine
        result = engine.do_battle_tick()
        self.battle_log = result
        self.refresh_ui()


class RosterScreen(Screen):
    """Gladiator roster — hire, upgrade, manage fighters."""

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
        msg = engine.upgrade_gladiator(index)
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
    """Shop — buy boosts and equipment."""

    gold_text = StringProperty("0")
    idle_rate_text = StringProperty("")
    items_data = ListProperty()

    def on_enter(self):
        self.refresh_shop()

    def refresh_shop(self):
        engine = App.get_running_app().engine
        self.gold_text = f"{engine.gold:,.0f}"
        self.idle_rate_text = f"Idle income: {engine.idle_gold_rate:.1f} gold/sec"
        self.items_data = engine.get_shop_items()
        refresh_shop_grid(self)

    def buy(self, item_id):
        engine = App.get_running_app().engine
        engine.buy_item(item_id)
        self.refresh_shop()


class GladiatorIdleApp(App):
    """Main application."""

    def build(self):
        self.engine = GameEngine()
        self.engine.load()

        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(ArenaScreen(name="arena"))
        sm.add_widget(RosterScreen(name="roster"))
        sm.add_widget(ShopScreen(name="shop"))

        # Idle gold tick every second
        Clock.schedule_interval(self._idle_tick, 1.0)
        # Auto-save every 30 seconds
        Clock.schedule_interval(self._auto_save, 30.0)

        return sm

    def _idle_tick(self, dt):
        self.engine.idle_tick(dt)
        current = self.root.current_screen
        if hasattr(current, "refresh_ui"):
            current.refresh_ui()
        if hasattr(current, "refresh_roster"):
            current.refresh_roster()
        if hasattr(current, "refresh_shop"):
            current.refresh_shop()

    def _auto_save(self, dt):
        self.engine.save()

    def on_stop(self):
        self.engine.save()


if __name__ == "__main__":
    GladiatorIdleApp().run()
