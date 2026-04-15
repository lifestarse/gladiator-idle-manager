# Build: 7
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty, BooleanProperty
from kivy.metrics import dp, sp
from kivy.core.window import Window
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard
from game.achievements import DIAMOND_BUNDLES
from game.models import fmt_num
from game.theme import *
from game.theme import popup_color
from game.localization import t, set_language, get_language
from game.ui_helpers import (
    _batch_fill_grid,
    bind_text_wrap,
)
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager
from game.leaderboard import leaderboard_manager


class MoreScreen(BaseScreen):
    cloud_status = StringProperty("Not connected")
    ads_status = StringProperty("Active")
    ads_hidden = BooleanProperty(False)
    google_btn_text = StringProperty("")
    google_signed_in = BooleanProperty(False)

    def on_enter(self):
        self.refresh_more()

    def refresh_more(self):
        engine = App.get_running_app().engine
        self._update_top_bar()
        self.cloud_status = cloud_save_manager.last_sync_status
        self.ads_status = t("status_removed") if engine.ads_removed else t("status_active")
        self.ads_hidden = engine.ads_removed
        # Update google button state
        if cloud_save_manager.is_connected and cloud_save_manager.user_email:
            self.google_signed_in = True
            self.google_btn_text = t("signed_in_as", email=cloud_save_manager.user_email)
        else:
            self.google_signed_in = False
            self.google_btn_text = t("sign_in_google")
        # Hide ads_box when ads are removed
        ads_box = self.ids.get("ads_box")
        if ads_box:
            if engine.ads_removed:
                ads_box.opacity = 0
                ads_box.disabled = True
                ads_box.size_hint_y = None
                ads_box.height = 0
            else:
                ads_box.opacity = 1
                ads_box.disabled = False
                ads_box.size_hint_y = None
                ads_box.height = dp(60)
        self._refresh_diamond_bundles()

    def _refresh_diamond_bundles(self):
        grid = self.ids.get("diamond_bundles_grid")
        if not grid:
            return
        # Static data — build once, reuse forever
        if getattr(self, '_bundle_cards', None):
            _batch_fill_grid(grid, self._bundle_cards)
            return
        cards = []
        for bundle in DIAMOND_BUNDLES:
            row = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(48),
                           padding=[dp(10), dp(4)], spacing=dp(6))
            row.border_color = ACCENT_CYAN
            bonus = bundle.get("bonus", "")
            label_text = f"{bundle['diamonds']} {bonus}" if bonus else f"{bundle['diamonds']}"
            # Left side: quantity + gem icon (number-then-icon, matching top-bar pattern)
            left_box = BoxLayout(orientation="horizontal", size_hint_x=0.5, spacing=dp(4))
            left_box.add_widget(row._make_label(label_text, sp(11), True, ACCENT_CYAN, "left", 1))
            left_box.add_widget(Image(
                source="sprites/icons/ic_gem.png", fit_mode="contain",
                size_hint=(None, 1), width=dp(18),
            ))
            row.add_widget(left_box)
            buy_btn = MinimalButton(
                text=t("buy_btn"), font_size=11, size_hint_x=0.5,
                btn_color=ACCENT_CYAN, text_color=BG_DARK,
            )
            def _buy(inst, bid=bundle["id"]):
                self.buy_diamonds(bid)
            buy_btn.bind(on_press=_buy)
            row.add_widget(buy_btn)
            cards.append(row)
        self._bundle_cards = cards
        _batch_fill_grid(grid, cards)

    def buy_diamonds(self, bundle_id):
        app = App.get_running_app()
        engine = app.engine
        def on_success():
            result = engine.purchase_diamonds(bundle_id)
            engine.save()
            self.refresh_more()
            app.update_top_bar()
            if result.message:
                app.show_toast(result.message)
        iap_manager.purchase(bundle_id, on_success)

    def buy_remove_ads(self):
        engine = App.get_running_app().engine
        def on_success():
            engine.purchase_remove_ads()
            ad_manager.hide_banner()
            engine.save()
            self.refresh_more()
        iap_manager.purchase("remove_ads", on_success)

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
        if cloud_save_manager.is_connected:
            return
        def on_success():
            self.cloud_status = t("cloud_connected")
            self.refresh_more()
            self._auto_sync_on_login()
        def on_failure(reason):
            self.cloud_status = t("cloud_failed", reason=reason)
        cloud_save_manager.sign_in(on_success, on_failure)

    def _auto_sync_on_login(self):
        engine = App.get_running_app().engine
        self.cloud_status = t("sync") + "..."
        def on_done(success, result):
            if success and isinstance(result, dict):
                engine.load(data=result)
                engine.save()
                self._restart_app()
            elif not success and result == "No cloud save found":
                save_data = engine.save()
                cloud_save_manager.upload_save(save_data, self._on_initial_upload)
            else:
                self.cloud_status = t("signed_in_as", email=cloud_save_manager.user_email)
        cloud_save_manager.download_save(on_done)

    def _on_initial_upload(self, success, msg):
        self.cloud_status = t("signed_in_as", email=cloud_save_manager.user_email)
        self._restart_app()

    def _restart_app(self):
        """Restart the app after first Google sign-in."""
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            pm = activity.getPackageManager()
            intent = pm.getLaunchIntentForPackage(activity.getPackageName())
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            activity.startActivity(intent)
            activity.finish()
        except Exception:
            # Desktop fallback — just stop the app
            App.get_running_app().stop()

    def cloud_sign_out(self):
        def on_done():
            self.refresh_more()
        cloud_save_manager.sign_out(on_done)

    def cloud_upload(self):
        self._confirm_action(
            t("confirm_save_to_cloud"),
            self._do_cloud_upload,
        )

    def _do_cloud_upload(self):
        engine = App.get_running_app().engine
        save_data = engine.save()
        self.cloud_status = t("upload") + "..."
        def on_done(success, msg):
            self.cloud_status = t("cloud_uploaded") if success else t("cloud_failed", reason=msg)
        cloud_save_manager.upload_save(save_data, on_done)

    def cloud_download(self):
        self._confirm_action(
            t("confirm_load_from_cloud"),
            self._do_cloud_download,
        )

    def _do_cloud_download(self):
        engine = App.get_running_app().engine
        self.cloud_status = t("download") + "..."
        def on_done(success, result):
            if success and isinstance(result, dict):
                engine.load(data=result)
                engine.save()
                self.cloud_status = t("cloud_loaded")
                self._restart_app()
            else:
                self.cloud_status = t("cloud_failed", reason=result)
        cloud_save_manager.download_save(on_done)

    def _confirm_action(self, message, on_confirm):
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))
        msg_lbl = AutoShrinkLabel(
            text=message, font_size="11sp", color=TEXT_SECONDARY,
            halign="center", valign="middle",
            size_hint_y=1,
        )
        bind_text_wrap(msg_lbl)
        content.add_widget(msg_lbl)
        btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(12))
        popup = Popup(
            title=t("cloud_save"),
            content=content,
            size_hint=(0.88, 0.35),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_GOLD),
            separator_color=popup_color(ACCENT_GOLD),
            auto_dismiss=True,
        )
        cancel_btn = MinimalButton(
            text=t("cancel"), btn_color=TEXT_SECONDARY, font_size=sp(11),
        )
        cancel_btn.bind(on_press=lambda *a: popup.dismiss())
        confirm_btn = MinimalButton(
            text=t("confirm"), btn_color=ACCENT_GREEN, text_color=BG_DARK,
            font_size=sp(11),
        )
        def _on_confirm(*a):
            popup.dismiss()
            on_confirm()
        confirm_btn.bind(on_press=_on_confirm)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)
        popup.open()

    def show_leaderboard(self):
        """Open Play Games fullscreen leaderboard. Sign in first if needed."""
        engine = App.get_running_app().engine

        try:
            engine.submit_scores()
        except Exception:
            pass

        if leaderboard_manager.is_ready:
            leaderboard_manager.show_all_leaderboards(
                on_failure=lambda err: self._leaderboard_error(err),
            )
        else:
            # Sign in first, then show leaderboard
            def _after_sign_in(success):
                if success:
                    leaderboard_manager.show_all_leaderboards(
                        on_failure=lambda err: self._leaderboard_error(err),
                    )
                else:
                    self._leaderboard_error("Sign-in failed")

            leaderboard_manager.sign_in_interactive(callback=_after_sign_in)

    def _leaderboard_error(self, err):
        """Show a brief error toast when Play Games leaderboard fails."""
        content = AutoShrinkLabel(text=f"Play Games: {err}", font_size="11sp",
                       color=TEXT_SECONDARY)
        bind_text_wrap(content)
        popup = Popup(
            title=t("leaderboard_title"),
            content=content,
            size_hint=(0.85, 0.3),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_GOLD),
            separator_color=popup_color(ACCENT_GOLD),
        )
        popup.open()

    def submit_scores(self):
        App.get_running_app().engine.submit_scores()

    def show_help(self):
        """Show help popup with all game mechanics explained."""
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        content = BoxLayout(orientation="vertical", size_hint_y=None,
                            padding=[dp(12), dp(8)], spacing=dp(6))
        content.bind(minimum_height=content.setter("height"))

        sections = t("help_sections")
        for title, body in sections:
            content.add_widget(AutoShrinkLabel(
                text=title, font_size="11sp", bold=True,
                color=ACCENT_GOLD, halign="left",
                size_hint_y=None, height=dp(28),
            ))
            lbl = AutoShrinkLabel(
                text=body, font_size="11sp",
                color=TEXT_SECONDARY, halign="left", valign="top",
                markup=True, size_hint_y=None,
            )
            lbl.bind(width=lambda inst, w: setattr(inst, 'text_size', (w, None)))
            lbl.bind(texture_size=lambda inst, ts: setattr(inst, 'height', ts[1] + dp(8)))
            content.add_widget(lbl)

        scroll.add_widget(content)
        popup = Popup(
            title=t("help_title"),
            title_color=popup_color(ACCENT_GOLD),
            title_size=sp(12),
            content=scroll,
            size_hint=(0.95, 0.85),
            background_color=popup_color(BG_CARD),
            separator_color=popup_color(ACCENT_GOLD),
            auto_dismiss=True,
        )
        popup.open()

    def show_language_picker(self):
        languages = [("English", "en"), ("Русский", "ru")]
        current = get_language()
        content = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        popup = Popup(
            title=t("language"),
            content=content,
            size_hint=(0.85, 0.4),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_GOLD),
            separator_color=popup_color(ACCENT_GOLD),
        )
        for name, code in languages:
            is_current = code == current
            btn = MinimalButton(
                text=f"{'> ' if is_current else ''}{name}",
                size_hint_y=None, height=dp(44),
                btn_color=ACCENT_GOLD if is_current else ACCENT_BLUE,
                font_size=sp(9),
            )
            btn.bind(on_press=lambda inst, c=code, p=popup: self._set_language(c, p))
            content.add_widget(btn)
        popup.open()

    def _set_language(self, lang_code, popup):
        popup.dismiss()
        set_language(lang_code)
        from game.data_loader import data_loader
        from game.engine import GameEngine
        data_loader._loaded = False
        data_loader.load_all()
        data_loader.apply_translations(lang_code)
        GameEngine._wire_data()
        App.get_running_app().engine.save()
        App.get_running_app()._init_locale_strings()
        self.refresh_more()
