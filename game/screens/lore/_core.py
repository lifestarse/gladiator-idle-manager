# Build: 4
"""LoreScreen core — lifecycle + small methods."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m
from .logsmixin import _LogsMixin
from .statsquestsmixin import _StatsQuestsMixin
from .diamondsmixin import _DiamondsMixin
from .event_logs_mixin import _EventLogsMixin


class LoreScreen(BaseScreen, _LogsMixin, _StatsQuestsMixin, _DiamondsMixin, _EventLogsMixin):
    achievements_data = ListProperty()

    diamond_shop_data = ListProperty()

    lore_tab = StringProperty("achievements")

    lore_subview = StringProperty("")       # "" = none, "blog_list", "blog_detail"

    lore_back_text = StringProperty("")

    battle_log_count = StringProperty("")

    event_log_count = StringProperty("")

    def on_enter(self):
        self.refresh_lore()

    def set_lore_tab(self, tab):
        self.lore_subview = ""
        self.lore_tab = tab
        grid = self._get_grid("lore_grid")
        if grid:
            grid._dshop_key = None
        self.refresh_lore()

    def _rebuild_lore_tabs(self):
        """Tabs live in a ChipRow (scrolls when labels don't fit) instead of
        four fixed kv buttons that clipped to 'ACHIEVEMEN / DIAMOND SHO'."""
        box = self.ids.get("lore_tabs_box")
        if box is None:
            return
        tabs = [
            ("achievements", t("achievements_label")),
            ("shop", t("diamond_shop_label")),
            ("quests", t("quests_label")),
            ("stats", t("stats_label")),
        ]
        key = (self.lore_tab, tuple(label for _v, label in tabs))
        if key == getattr(self, "_lore_tabs_key", None) and box.children:
            return
        self._lore_tabs_key = key
        box.clear_widgets()
        box.add_widget(build_tab_row(
            tabs, self.lore_tab, self.set_lore_tab,
            active_color=ACCENT_GOLD, height=dp(40), font_size=10,
        ))

    def refresh(self):
        """BaseScreen per-tick entry point."""
        self.refresh_lore()

    def refresh_lore(self):
        self._rebuild_lore_tabs()
        if self.lore_subview:
            return
        engine = App.get_running_app().engine
        self._update_top_bar()
        if self.lore_tab == "achievements":
            self.achievements_data = engine.get_achievements()
            refresh_achievement_grid(self)
        elif self.lore_tab == "shop":
            self.diamond_shop_data = engine.get_diamond_shop()
            refresh_diamond_shop_grid(self)
        elif self.lore_tab == "quests":
            self._refresh_quests_grid()
        elif self.lore_tab == "stats":
            self.battle_log_count = f"{t('battle_log_btn')} ({len(engine.battle_log)})"
            self.event_log_count = f"{t('event_log_btn')} ({len(engine.event_log)})"
            self._refresh_stats_grid()

    def _close_subview(self):
        self.lore_subview = ""
        self.refresh_lore()

    def on_back_pressed(self):
        if self.lore_subview == "blog_detail":
            self._show_battle_log()
            return True
        if self.lore_subview == "event_detail":
            self._show_event_log()
            return True
        if self.lore_subview:
            self._close_subview()
            return True
        return False
