# Build: 11
"""GladiatorIdleApp core."""
from game.app._shared import *  # noqa: F401,F403
from game.app._shared import _log
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

    # Stylized header for the Scripts screen. Matches the pattern of every
    # other screen so the TopBar shows "С К Р И П Т Ы" / "S C R I P T S"
    # in the same spaced-caps style as title_pit / title_lore / etc.
    title_scripts = StringProperty("")

    # Toolbar button labels for the Scripts screen — bound from kv so the
    # buttons follow language changes the same way every other screen does.
    scr_new_btn = StringProperty("")
    scr_tmpl_btn = StringProperty("")
    scr_export_all_btn = StringProperty("")
    scr_import_btn = StringProperty("")
    scr_run_btn = StringProperty("")
    scr_log_btn = StringProperty("")
    scr_tab_all = StringProperty("")
    scr_tab_running = StringProperty("")
    scr_stop_btn = StringProperty("")
    scr_undo_btn = StringProperty("")
    scr_redo_btn = StringProperty("")
    scr_online_btn = StringProperty("")

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

    lbl_scripts = StringProperty("")

    lbl_restore_purchases = StringProperty("")

    lbl_cloud_save = StringProperty("")

    lbl_sign_in_google = StringProperty("")

    lbl_sign_out_google = StringProperty("")

    lbl_save_to_cloud = StringProperty("")

    lbl_load_from_cloud = StringProperty("")

    lbl_language = StringProperty("")

    lbl_change_language = StringProperty("")

    lbl_sound_volume = StringProperty("")

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

        # Load per-screen KV files (split from gladiatoridle.kv in Wave 6).
        from kivy.lang import Builder
        import os as _os
        _kv_dir = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))), "kv")
        for _fn in (
            "nav_bar.kv", "arena_screen.kv", "roster_screen.kv",
            "forge_screen.kv", "expedition_screen.kv",
            "lore_screen.kv", "more_screen.kv", "scripts_screen.kv",
        ):
            Builder.load_file(_os.path.join(_kv_dir, _fn))
        init_language()
        self._init_locale_strings()
        self.engine = GameEngine()
        self.engine.load()
        # Re-apply locale strings after load restores saved language
        self._init_locale_strings()

        # Wire In-App Review prompt to fire on the player's first
        # successful forge purchase. Lazy import keeps pyjnius out of
        # desktop test paths (the play package gracefully no-ops if
        # jnius is unavailable, but the import alone is wasted there).
        try:
            from game.play import maybe_show_review as _maybe_review
            self.engine.subscribe_first_purchase(_maybe_review)
        except Exception as _e:
            _log.warning("[app] couldn't wire In-App Review hook: %s", _e)

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
                _log.info("[Leaderboard] Startup init suppressed: %s", exc)
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
                        _log.info("[UI] Set decorFitsSystemWindows=True")
                        # SDL2 forces SCREEN_ORIENTATION_FULL_SENSOR at startup,
                        # which ignores the Android rotation-lock toggle. Reset
                        # to FULL_USER so the manifest's `fullUser` actually wins
                        # and the game respects the system auto-rotate setting.
                        ActivityInfo = autoclass("android.content.pm.ActivityInfo")
                        activity.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_FULL_USER)
                        _log.info("[UI] Set requestedOrientation=FULL_USER")
                    except Exception as e2:
                        _log.warning("[UI] Window fix error: %s", e2)

                _fix_window()
            except Exception as e:
                _log.warning("[UI] Edge-to-edge fix error: %s", e)

        # NoTransition — instant tab switch (standard for mobile bottom nav).
        # Was FadeTransition(duration=0.2) which added 200ms perceived lag.
        sm = SwipeScreenManager(transition=NoTransition())
        sm.add_widget(ArenaScreen(name="arena"))
        sm.add_widget(RosterScreen(name="roster"))
        sm.add_widget(ForgeScreen(name="forge"))
        sm.add_widget(ExpeditionScreen(name="expedition"))
        sm.add_widget(LoreScreen(name="lore"))
        sm.add_widget(MoreScreen(name="more"))
        sm.add_widget(ScriptsScreen(name="scripts"))
        sm.add_widget(ScriptEditorScreen(name="script_editor"))
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

        # First-run only: block with a mandatory language picker before the
        # player sees the game. Scheduled for next frame so the popup opens
        # against a fully-attached window.
        Clock.schedule_once(self._maybe_show_language_picker, 0)

        # Remote content: clear the safe-mode marker only after the app has
        # survived several seconds of real running. Doing it inline at the end
        # of build() would certify a patch that crashes on the first frame.
        # Then warm the cache for the NEXT launch — never for this one.
        def _remote_content_settled(dt):
            try:
                from game.remote_content import confirm_healthy, sync_async
                confirm_healthy()
                sync_async(get_language())
            except Exception as exc:
                _log.info("[remote] post-startup step suppressed: %s", exc)

        Clock.schedule_once(_remote_content_settled, 6.0)

        return root

    def _on_cloud_auto_connected(self):
        """Auto-sync on silent sign-in at startup."""
        # Token fetch is async — if user already sat on More screen when
        # it resolved, cloud_status is still the stale "Not connected"
        # default. Refresh it now so the label reflects reality.
        scr = self.sm.current_screen if self.sm else None
        if scr is not None and hasattr(scr, "refresh_more"):
            scr.refresh_more()

        engine = self.engine
        synced = getattr(engine, "cloud_sync_enabled", False)

        def on_done(success, result):
            if success and isinstance(result, dict):
                from game.cloud_save import resolve_auto_sync
                # Fresh install with nothing to lose → adopt the cloud and
                # persist that this device is now synced.
                if resolve_auto_sync(engine, result) == "load":
                    engine.load(data=result)
                    engine.cloud_sync_enabled = True
                    engine.save()
                    engine._ui_dirty = True
                    cloud_save_manager.enable_autosync_uploads()
                    _log.info("[CloudSave] First launch — adopted cloud save")
                elif synced:
                    # Returning device that already owns the cloud. Never
                    # auto-load (that was the rollback bug) and never blindly
                    # upload. Cross-device guard: if the cloud was advanced
                    # on ANOTHER device (cloud saved_at newer than ours),
                    # hold auto-upload so we don't clobber that newer save,
                    # and tell the user they can pull it. Otherwise this
                    # device holds the latest → resume auto-backup.
                    cloud_ts = result.get("saved_at", 0) or 0
                    local_ts = getattr(engine, "last_saved_at", 0) or 0
                    if cloud_ts > local_ts:
                        engine.pending_notifications.append(t("cloud_newer_available"))
                        _log.info("[CloudSave] Cloud newer (other device) — auto-upload held")
                    else:
                        cloud_save_manager.enable_autosync_uploads()
                        _log.info("[CloudSave] Resumed cloud auto-backup for this device")
                else:
                    _log.info("[CloudSave] Local save present, device not synced — no action")
            elif not success and result == "No cloud save found":
                if synced:
                    # This device was synced but the cloud file is gone —
                    # re-seed it from local (creation, not overwrite).
                    cloud_save_manager.enable_autosync_uploads()
                    _log.info("[CloudSave] Cloud missing — will re-create from local")
                else:
                    # Never auto-create from the silent path for an unsynced
                    # device; wait for an explicit sync.
                    _log.info("[CloudSave] No cloud save; awaiting explicit sync")
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
                     "refresh_expeditions", "refresh_lore", "refresh_more",
                     "refresh_scripts"):
            if hasattr(scr, attr):
                getattr(scr, attr)()
                break

    def _auto_save(self, dt):
        # Async: JSON serialization + disk write happen on a worker thread.
        # Main-thread stall was the ~100-300ms CPU spike every 30s once the
        # battle_log grew past a few hundred KB.
        self.engine.save_async()
        # Only stream to the cloud once the user has consciously synced this
        # device. Being signed in is NOT consent: an unconditional upload
        # here let a fresh/lesser local save overwrite a real cloud save
        # every 30s and permanently destroy progress.
        if cloud_save_manager.is_connected and cloud_save_manager.autosync_uploads:
            cloud_save_manager.upload_save(self.engine._build_save_data())

    def on_pause(self):
        self.engine.save()
        return True

    def on_resume(self):
        pass

    def on_stop(self):
        save_data = self.engine.save()
        if cloud_save_manager.is_connected:
            cloud_save_manager.upload_save(save_data)
