# Build: 3
"""MoreScreen core — lifecycle + small methods."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m
from .iapmixin import _IapMixin
from .cloudmixin import _CloudMixin
from .leaderboardmixin import _LeaderboardMixin
from .helpmixin import _HelpMixin
from kivy.properties import NumericProperty
from game.screens.shared import apply_sound_volume


class MoreScreen(BaseScreen, _IapMixin, _CloudMixin, _LeaderboardMixin, _HelpMixin):
    cloud_status = StringProperty("Not connected")

    ads_status = StringProperty("Active")

    ads_hidden = BooleanProperty(False)

    google_btn_text = StringProperty("")

    google_signed_in = BooleanProperty(False)

    # Mirrors engine.sound_volume — used to seed the Slider on enter so the
    # widget shows the persisted value. Slider edits go through
    # _on_volume_change → engine + apply_sound_volume; we do NOT bind the
    # slider's value back into this property to avoid a re-entry loop.
    sound_volume = NumericProperty(1.0)

    def on_enter(self):
        self.refresh_more()

    def refresh(self):
        """BaseScreen per-tick entry point."""
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
        # Seed slider from persisted engine value
        self.sound_volume = float(getattr(engine, "sound_volume", 1.0))
        self._refresh_diamond_bundles()

    def _on_volume_change(self, value):
        """Slider callback — persist new volume and update any live sound."""
        try:
            v = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return
        engine = App.get_running_app().engine
        if abs(getattr(engine, "sound_volume", 1.0) - v) < 1e-4:
            return
        engine.sound_volume = v
        apply_sound_volume(v)
        engine.save_async()
