# Build: 59
"""
Gladiator Idle Manager — roguelike-manager.
Permadeath resets the run. Stats distributed manually. Fighter classes.
"""

import os
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.utils import platform
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle

from game.engine import GameEngine
from game.models import fmt_num
from game.theme import *
from game.theme import popup_color
from game.localization import t, init_language, set_language, get_language
from game.widgets import AutoShrinkLabel, MinimalButton
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager
from game.leaderboard import leaderboard_manager
from game.ui_helpers import bind_text_wrap

from game.screens.shared import _safe_clear, SCREEN_ORDER
from game.screens.arena import ArenaScreen
from game.screens.roster import RosterScreen
from game.screens.forge import ForgeScreen
from game.screens.expedition import ExpeditionScreen
from game.screens.lore import LoreScreen
from game.screens.more import MoreScreen

# Window.size only on desktop — crashes Android
if platform not in ("android", "ios"):
    Window.size = (360, 640)
Window.clearcolor = BG_DARK

# Register pixel font
from kivy.core.text import LabelBase
LabelBase.register(name='PixelFont', fn_regular='fonts/PressStart2P-Regular.ttf')


class SwipeScreenManager(ScreenManager):
    """ScreenManager — swipe disabled, navigation via NavBar only."""
    pass


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

    # Global top bar values
    top_gold = StringProperty("0")
    top_diamonds = StringProperty("0")

    def update_top_bar(self):
        engine = self.engine
        self.top_gold = fmt_num(engine.gold)
        self.top_diamonds = fmt_num(engine.diamonds)

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

    def _navigate_to_forge(self, state):
        """Set ForgeScreen pending state and navigate (or refresh if already there)."""
        fs = self.sm.get_screen("forge")
        fs._pending_state = state
        if self.sm.current == "forge":
            fs._apply_pending_state()
        else:
            # Mark cross-screen entry depth so back unwinds correctly
            fs._cross_screen_pending = True
            if state.get('eq_detail_fighter', -1) >= 0 or state.get('inv_detail_idx', -1) >= 0:
                fs._entry_depth = 2   # item detail
            elif '_preview_item' in state:
                fs._entry_depth = 3   # shop preview
            elif state.get('show_inventory'):
                fs._entry_depth = 4   # inventory
            else:
                fs._entry_depth = 5   # shop tab
            self.sm.current = "forge"

    def open_equipped_detail(self, fighter_idx, slot):
        """Navigate to ForgeScreen and open equipped item detail — works from any screen."""
        self._navigate_to_forge({
            'show_inventory': True,
            'eq_detail_fighter': fighter_idx,
            'eq_detail_slot': slot,
        })

    def open_item_detail(self, inv_idx):
        """Navigate to ForgeScreen and open item detail — works from any screen."""
        self._navigate_to_forge({
            'show_inventory': True,
            'inv_detail_idx': inv_idx,
        })

    def open_forge_tab(self, slot):
        """Navigate to ForgeScreen shop with the given tab selected."""
        self._navigate_to_forge({'forge_tab': slot})

    def open_inventory_tab(self, tab, equip_filter="all"):
        """Navigate to ForgeScreen inventory with the given tab filter."""
        self._navigate_to_forge({
            'show_inventory': True,
            'inventory_tab': tab,
            'inventory_equip_filter': equip_filter,
        })

    def open_shop_preview(self, item):
        """Navigate to ForgeScreen and show read-only item preview."""
        self._navigate_to_forge({'_preview_item': item})

    def show_toast(self, msg, duration=2.5):
        """Show a brief error/info notification at the bottom of the screen."""
        self.toast_message = str(msg)
        Clock.unschedule(self._clear_toast)
        Clock.schedule_once(self._clear_toast, duration)

    def _clear_toast(self, *a):
        self.toast_message = ""

    def _setup_toast(self):
        """Create a floating toast Label attached to the Window."""
        lbl = AutoShrinkLabel(
            text="",
            size_hint=(None, None),
            font_size="13sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
            opacity=0,
        )

        def _redraw(lbl, *a):
            w = min(Window.width * 0.85, dp(320))
            lbl.size = (w, dp(44))
            lbl.center_x = Window.width / 2
            lbl.y = Window.height * 0.07
            lbl.text_size = (w - dp(16), None)
            lbl.canvas.before.clear()
            if lbl.opacity > 0:
                with lbl.canvas.before:
                    Color(0.85, 0.25, 0.1, 0.93)
                    RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(10)])

        def _on_toast(app, val):
            lbl.text = val
            lbl.opacity = 1 if val else 0
            _redraw(lbl)

        self.bind(toast_message=_on_toast)
        lbl.bind(pos=_redraw, size=_redraw)
        Window.bind(size=lambda *a: _redraw(lbl))
        _redraw(lbl)
        Clock.schedule_once(lambda *a: Window.add_widget(lbl), 0)

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
        self.lbl_back_btn = t("back_btn")
        self.lbl_boss = t("btn_boss")
        self.lbl_next = t("btn_next")
        self.lbl_skip = t("btn_skip")
        self.lbl_achievements = t("achievements_label")
        self.lbl_diamond_shop = t("diamond_shop_label")
        self.lbl_stats = t("stats_label")
        self.lbl_quests = t("quests_label")
        self.lbl_tab_missions = t("tab_missions")
        self.lbl_tab_hunts = t("tab_hunts")
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
        self.lbl_tab_weapon = t("tab_weapon")
        self.lbl_tab_armor = t("tab_armor")
        self.lbl_tab_accessory = t("tab_accessory")
        self.lbl_tab_enchant = t("tab_enchant")
        self.lbl_common = t("btn_common")
        self.lbl_help = t("help_title")
        self.lbl_buy_diamonds = t("buy_diamonds_label")

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

        sm = SwipeScreenManager(transition=FadeTransition(duration=0.2))
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

    @staticmethod
    def _any_scroll_active(screen):
        """Return True if any ScrollView is being touched or still scrolling."""
        from kivy.uix.scrollview import ScrollView
        for w in screen.walk():
            if isinstance(w, ScrollView):
                if w._touch is not None:
                    return True
                # Check momentum/kinetic scrolling
                ey = getattr(w, 'effect_y', None)
                if ey and abs(getattr(ey, 'velocity', 0)) > 5:
                    return True
        return False

    def _idle_tick(self, dt):
        self.engine.idle_tick(dt)
        # Drain notification queue
        if self.engine.pending_notifications:
            msg = self.engine.pending_notifications.pop(0)
            self.show_toast(msg, duration=3.0)
        scr = self.sm.current_screen
        if self._any_scroll_active(scr):
            return
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

    def _on_screen_change(self, sm, new_screen):
        """Track navigation history whenever the active screen changes."""
        if self._going_back:
            self._going_back = False
        elif new_screen != self._current_screen:
            # Save current screen + its view state
            state = self._get_screen_state(self._current_screen)
            self._nav_history.append((self._current_screen, state))
        self._current_screen = new_screen

    def _get_screen_state(self, screen_name):
        """Snapshot the current view state of a screen."""
        scr = self.sm.get_screen(screen_name)
        if hasattr(scr, 'get_nav_state'):
            return scr.get_nav_state()
        return {}

    def _restore_screen_state(self, screen_name, state):
        """Restore a screen's view state from snapshot."""
        scr = self.sm.get_screen(screen_name)
        if hasattr(scr, 'restore_nav_state') and state:
            scr.restore_nav_state(state)

    def _on_keyboard(self, window, key, scancode, codepoint, modifier):
        """Handle Android back button (key 27) and desktop Escape."""
        if key == 27:
            self.go_back()
            return True  # always consume; prevent Android from exiting
        return False

    def go_back(self):
        """Navigate one step back: first within a screen, then to previous tab."""
        scr = self.sm.current_screen
        if hasattr(scr, "on_back_pressed") and scr.on_back_pressed():
            return  # screen handled it internally
        if self._nav_history:
            prev_name, prev_state = self._nav_history.pop()
            self._going_back = True
            self._restore_screen_state(prev_name, prev_state)
            self.sm.current = prev_name

    def show_tutorial(self, step):
        self.engine.mark_tutorial_shown(step["id"])
        if not self.root:
            return
        arena = self.sm.get_screen("arena")
        arena.arena_view = "tutorial"
        grid = arena.ids.get("enemy_detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        # Title
        title_lbl = AutoShrinkLabel(
            text=step["title"], font_size="21sp", bold=True,
            color=ACCENT_GOLD, halign="center",
            size_hint_y=None, height=dp(36),
        )
        bind_text_wrap(title_lbl)
        grid.add_widget(title_lbl)

        # Lines
        for line in step["lines"]:
            lbl = AutoShrinkLabel(
                text=line, font_size="18sp", color=TEXT_PRIMARY,
                halign="left", size_hint_y=None, height=dp(40),
            )
            bind_text_wrap(lbl)
            grid.add_widget(lbl)

        # Close button
        close_btn = MinimalButton(
            text=t("got_it"), btn_color=ACCENT_GOLD, text_color=BG_DARK,
            font_size=19, size_hint_y=None, height=dp(48),
        )
        close_btn.bind(on_press=lambda inst: setattr(arena, 'arena_view', 'battle'))
        grid.add_widget(close_btn)


if __name__ == "__main__":
    GladiatorIdleApp().run()
