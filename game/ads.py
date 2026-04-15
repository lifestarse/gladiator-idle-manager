# Build: 8
"""
Ad integration module — AdMob via KivMob.

Setup:
1. pip install kivmob
2. Replace AD unit IDs below with your real AdMob IDs
3. Banner shows on all screens (unless ads removed)
4. Interstitial shows every 5 fights
5. Rewarded video gives 2x gold for 60 seconds

For testing use Google's test ad unit IDs (already set below).
Replace with real IDs before publishing to stores.
"""

import logging
import time
from kivy.clock import Clock
from kivy.utils import platform

_log = logging.getLogger(__name__)

# --- AdMob Unit IDs ---
# All IDs are real production units from AdMob console (publisher 9899076646540406).
# The _is_test_id guard below still blocks any future accidental regressions
# to Google's test publisher (ca-app-pub-3940256099942544).
ADMOB_APP_ID = "ca-app-pub-9899076646540406~3867094053"
BANNER_ID = "ca-app-pub-9899076646540406/9566843992"
INTERSTITIAL_ID = "ca-app-pub-9899076646540406/4588376646"
REWARDED_ID = "ca-app-pub-9899076646540406/7192144243"

# Google's test publisher — used to block accidental shipping of test ads.
_GOOGLE_TEST_PUBLISHER = "ca-app-pub-3940256099942544"


def _is_test_id(unit_id):
    """True if the ad unit ID belongs to Google's test publisher."""
    return bool(unit_id) and _GOOGLE_TEST_PUBLISHER in unit_id


# Real ads enabled for banner
USING_REAL_ADS = True


class AdManager:
    """Manages all ad operations. Wraps KivMob for Android, stub for others."""

    def __init__(self):
        self._kivmob = None
        self._initialized = False
        self._rewarded_callback = None

    def init(self):
        """Initialize ads. Call once at app start."""
        if platform != "android":
            print("[AdManager] Not on Android — ads disabled (stub mode)")
            self._initialized = False
            return

        try:
            from kivmob import KivMob
            self._kivmob = KivMob(ADMOB_APP_ID)
            self._kivmob.new_banner(BANNER_ID, top_pos=False)
            self._kivmob.new_interstitial(INTERSTITIAL_ID)
            self._kivmob.request_banner()
            self._kivmob.request_interstitial()
            self._initialized = True
            print("[AdManager] Initialized with KivMob")
        except ImportError:
            print("[AdManager] KivMob not installed — ads disabled")
            self._initialized = False

    # --- Banner ---

    def show_banner(self):
        if self._initialized and self._kivmob:
            self._kivmob.show_banner()

    def hide_banner(self):
        if self._initialized and self._kivmob:
            self._kivmob.hide_banner()

    # --- Interstitial ---

    def show_interstitial(self):
        if _is_test_id(INTERSTITIAL_ID):
            _log.warning(
                "[AdManager] Interstitial skipped: INTERSTITIAL_ID is a Google test ID. "
                "Create a real ad unit in AdMob and update ads.py before release."
            )
            return
        if not self._initialized or not self._kivmob:
            return
        if self._kivmob.is_interstitial_loaded():
            self._kivmob.show_interstitial()
            # Pre-load next one
            self._kivmob.request_interstitial()

    # --- Rewarded Video ---

    def load_rewarded(self):
        if self._initialized and self._kivmob:
            # KivMob loads rewarded automatically, but we can re-request
            pass

    def show_rewarded(self, on_reward_callback):
        """
        Show rewarded video. on_reward_callback() is called if user
        watches the full video.
        """
        if _is_test_id(REWARDED_ID):
            _log.warning(
                "[AdManager] Rewarded skipped: REWARDED_ID is a Google test ID. "
                "Create a real ad unit in AdMob and update ads.py before release."
            )
            return
        if not self._initialized or not self._kivmob:
            # Stub: just give reward on desktop for testing
            print("[AdManager] Stub: rewarded ad simulated")
            if on_reward_callback:
                on_reward_callback()
            return

        self._rewarded_callback = on_reward_callback
        # KivMob rewarded ad flow
        try:
            from kivmob import RewardedListenerInterface
            from jnius import autoclass

            class RewardListener(RewardedListenerInterface):
                def __init__(self, callback):
                    super().__init__()
                    self._cb = callback

                def on_rewarded(self, reward_type, amount):
                    if self._cb:
                        Clock.schedule_once(lambda dt: self._cb(), 0)

                def on_rewarded_video_ad_closed(self):
                    pass

                def on_rewarded_video_ad_failed_to_load(self, error):
                    pass

                def on_rewarded_video_ad_loaded(self):
                    pass

                def on_rewarded_video_ad_opened(self):
                    pass

            self._kivmob.show_rewarded_ad(
                RewardListener(on_reward_callback)
            )
        except Exception as e:
            print(f"[AdManager] Rewarded ad error: {e}")

    def is_rewarded_loaded(self):
        if not self._initialized or not self._kivmob:
            return False  # no ads on desktop / uninitialised
        try:
            return self._kivmob.is_rewarded_ad_loaded()
        except Exception as e:
            _log.warning("[Ads] is_rewarded_loaded error: %s", e)
            return False


# Singleton
ad_manager = AdManager()
