# Build: 4
"""MoreScreen _CloudMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _CloudMixin:
    def cloud_sign_in(self):
        if cloud_save_manager.is_connected:
            return
        def on_success():
            self.cloud_status = t("cloud_connected")
            self.refresh_more()
            self._auto_sync_on_login()
        def on_failure(error_key):
            # error_key is a localization key from cloud_save.classify_signin_error
            # (e.g. "cloud_err_cancelled"). Show a clear popup with Retry so the
            # user knows what happened and how to recover.
            msg = t(error_key) if error_key.startswith("cloud_err_") else error_key
            self.cloud_status = msg
            self._show_signin_error(msg)
        cloud_save_manager.sign_in(on_success, on_failure)

    def _auto_sync_on_login(self):
        engine = App.get_running_app().engine
        self.cloud_status = t("sync") + "..."
        def on_done(success, result):
            if success and isinstance(result, dict):
                engine.load(data=result)
                engine.save()
                engine._ui_dirty = True
                self.refresh_more()
                self.cloud_status = t("cloud_loaded")
            elif not success and result == "No cloud save found":
                save_data = engine.save()
                cloud_save_manager.upload_save(save_data, self._on_initial_upload)
            else:
                self.cloud_status = t("signed_in_as", email=cloud_save_manager.user_email)
        cloud_save_manager.download_save(on_done)

    def _on_initial_upload(self, success, msg):
        self.cloud_status = t("signed_in_as", email=cloud_save_manager.user_email)
        App.get_running_app().engine._ui_dirty = True
        self.refresh_more()

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

    def _show_signin_error(self, message):
        """Popup explaining a Google sign-in failure with a Retry button."""
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(16))
        msg_lbl = AutoShrinkLabel(
            text=message, font_size="11sp", color=TEXT_PRIMARY,
            halign="center", valign="middle",
            size_hint_y=1,
        )
        bind_text_wrap(msg_lbl)
        content.add_widget(msg_lbl)
        btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(12))
        popup = Popup(
            title=t("cloud_err_title"),
            content=content,
            size_hint=(0.88, 0.40),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_RED),
            separator_color=popup_color(ACCENT_RED),
            auto_dismiss=True,
        )
        cancel_btn = MinimalButton(
            text=t("cancel"), btn_color=TEXT_SECONDARY, font_size=11,
        )
        cancel_btn.bind(on_press=lambda *a: popup.dismiss())
        retry_btn = MinimalButton(
            text=t("retry"), btn_color=ACCENT_GREEN, text_color=BG_DARK,
            font_size=11,
        )
        def _on_retry(*a):
            popup.dismiss()
            self.cloud_sign_in()
        retry_btn.bind(on_press=_on_retry)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(retry_btn)
        content.add_widget(btn_row)
        popup.open()

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
            text=t("cancel"), btn_color=TEXT_SECONDARY, font_size=11,
        )
        cancel_btn.bind(on_press=lambda *a: popup.dismiss())
        confirm_btn = MinimalButton(
            text=t("confirm"), btn_color=ACCENT_GREEN, text_color=BG_DARK,
            font_size=11,
        )
        def _on_confirm(*a):
            popup.dismiss()
            on_confirm()
        confirm_btn.bind(on_press=_on_confirm)
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)
        popup.open()
