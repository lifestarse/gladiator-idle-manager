# Build: 1
from kivy.app import App
from kivy.properties import StringProperty, ListProperty, BooleanProperty
from game.base_screen import BaseScreen
from game.localization import t
from game.ui_helpers import refresh_expedition_grid


class ExpeditionScreen(BaseScreen):
    expeditions_data = ListProperty()
    status_data = ListProperty()
    log_text = StringProperty("")
    fighters_for_send = ListProperty()
    expedition_tab = StringProperty("hunts")
    has_active_missions = BooleanProperty(False)

    def set_expedition_tab(self, tab):
        self.expedition_tab = tab
        self.refresh_expeditions()

    def on_enter(self):
        self.refresh_expeditions()

    def refresh_expeditions(self):
        engine = App.get_running_app().engine
        self._update_top_bar()
        self.expeditions_data = engine.get_expeditions()
        self.status_data = engine.get_expedition_status()
        self.has_active_missions = any(f.on_expedition for f in engine.fighters)
        if not self.has_active_missions and self.expedition_tab == "missions":
            self.expedition_tab = "hunts"
        self.log_text = "\n".join(engine.expedition_log[-5:]) if engine.expedition_log else t("no_expeditions_log")
        self.fighters_for_send = [
            {"name": f.name, "level": f.level, "index": i}
            for i, f in enumerate(engine.fighters)
            if f.available
        ]
        refresh_expedition_grid(self)

    def send(self, fighter_idx, expedition_id):
        App.get_running_app().engine.send_on_expedition(fighter_idx, expedition_id)
        self.refresh_expeditions()
