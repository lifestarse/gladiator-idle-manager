# Build: 1
"""GladiatorIdleApp core."""
from game.app._shared import *  # noqa: F401,F403
from game.app.appnavmixin import _AppNavMixin
from game.app.appuimixin import _AppUiMixin
from game.app.applocalemixin import _AppLocaleMixin


class GladiatorIdleApp(App, _AppNavMixin, _AppUiMixin, _AppLocaleMixin):
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

    top_gold = StringProperty("0")

    top_diamonds = StringProperty("0")

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

    lbl_back_btn = StringProperty("")

    lbl_boss = StringProperty("")

    lbl_next = StringProperty("")

    lbl_skip = StringProperty("")

    lbl_achievements = StringProperty("")

    lbl_diamond_shop = StringProperty("")

    lbl_stats = StringProperty("")

    lbl_quests = StringProperty("")

    lbl_tab_missions = StringProperty("")

    lbl_tab_hunts = StringProperty("")

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

    lbl_tab_weapon = StringProperty("")

    lbl_tab_armor = StringProperty("")

    lbl_tab_accessory = StringProperty("")

    lbl_tab_enchant = StringProperty("")

    lbl_common = StringProperty("")

    lbl_help = StringProperty("")

    lbl_buy_diamonds = StringProperty("")

    toast_message = StringProperty("")

    def build(self):
        init_language()
        self._init_locale_strings()
        self.engine = GameEngine()
        self.engine.load()
        # Re-apply locale strings after load restores saved language
        self._init_locale_strings()

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
                if leaderboard_manager.is_ready:
                    self.engine.submit_scores()
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

        # NoTransition — instant tab switch (standard for mobile bottom nav).
        # Was FadeTransition(duration=0.2) which added 200ms perceived lag.
        sm = SwipeScreenManager(transition=NoTransition())
        sm.add_widget(ArenaScreen(name="arena"))
        sm.add_widget(RosterScreen(name="roster"))
        sm.add_widget(ForgeScreen(name="forge"))
        sm.add_widget(ExpeditionScreen(name="expedition"))
        sm.add_widget(LoreScreen(name="lore"))
        sm.add_widget(MoreScreen(name="more"))
        self.sm = sm
        self._nav_history = []
        self._current_screen = "arena"
        self._going_back = False
        sm.bind(current=self._on_screen_change)
        Window.bind(on_keyboard=self._on_keyboard)

        from game.widgets import NavBar
        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)
        root.add_widget(NavBar())

        self._setup_toast()
        Clock.schedule_interval(self._idle_tick, 1.0)
        Clock.schedule_interval(self._auto_save, 30.0)

        return root

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
        # Drain notification queue
        if self.engine.pending_notifications:
            msg = self.engine.pending_notifications.pop(0)
            self.show_toast(msg, duration=3.0)
        # Skip UI refresh if engine state hasn't changed since last refresh
        if not self.engine._ui_dirty:
            return
        scr = self.sm.current_screen
        if self._any_scroll_active(scr):
            return
        self.engine._ui_dirty = False
        # Skip ArenaScreen refresh during battle — _auto_turn already does it
        if hasattr(scr, "refresh_ui") and self.engine.battle_active:
            return
        for attr in ("refresh_ui", "refresh_roster", "refresh_forge",
                     "refresh_expeditions", "refresh_lore", "refresh_more"):
            if hasattr(scr, attr):
                getattr(scr, attr)()
                break

    def _auto_save(self, dt):
        save_data = self.engine.save()
        if cloud_save_manager.is_connected:
            cloud_save_manager.upload_save(save_data)

    def on_pause(self):
        self.engine.save()
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        save_data = self.engine.save()
        if cloud_save_manager.is_connected:
            cloud_save_manager.upload_save(save_data)
