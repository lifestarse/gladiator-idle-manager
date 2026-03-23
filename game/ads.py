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

import time
from kivy.utils import platform

# --- AdMob Unit IDs ---
# TEST IDs (safe for development). Replace before release!
ADMOB_APP_ID = "ca-app-pub-3940256099942544~3347511713"  # test
BANNER_ID = "ca-app-pub-3940256099942544/6300978111"      # test banner
INTERSTITIAL_ID = "ca-app-pub-3940256099942544/1033173712"  # test interstitial
REWARDED_ID = "ca-app-pub-3940256099942544/5224354917"      # test rewarded

# Set to True after replacing with real IDs
USING_REAL_ADS = False


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
                        self._cb()

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
            # Fallback: give reward anyway during development
            if on_reward_callback:
                on_reward_callback()

    def is_rewarded_loaded(self):
        if not self._initialized:
            return True  # stub always "loaded"
        return True  # KivMob auto-loads


# Singleton
ad_manager = AdManager()
