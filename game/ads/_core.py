# Build: 2
"""AdManager core — public API, desktop stub, android gating.

Android specifics live in _AdsAndroidMixin (consent/init chain + shim
calls). Invariants preserved from the 2026-07-24 audit fixes:

* a rewarded reward is NEVER granted on android without a watched ad;
* init() is a crash boundary — ads degrade to disabled, never kill launch;
* the desktop stub simulates rewarded success for local testing.
"""
from ._shared import (
    ADS_ENABLED,
    INTERSTITIAL_ID,
    REWARDED_ID,
    _is_test_id,
    _log,
    platform,
)
from .adsandroidmixin import _AdsAndroidMixin


class AdManager(_AdsAndroidMixin):
    """Manages all ad operations. Java shim on Android, stub elsewhere."""

    def __init__(self):
        self._initialized = False
        self._bridge = None       # jnius AdsBridge class (android only)
        self._activity = None     # PythonActivity.mActivity
        self._listener = None     # strong ref — pyjnius proxy must not GC
        self._rewarded_callback = None
        self._banner_wanted = False
        self._retry_delays = {}   # ad kind -> next backoff delay (seconds)

    def init(self):
        """Initialize ads. Call once at app start."""
        if not ADS_ENABLED:
            _log.info(
                "[AdManager] Ads disabled by config (ADS_ENABLED=False)"
            )
            self._initialized = False
            return
        if platform != "android":
            _log.info("[AdManager] Not on Android — ads disabled (stub mode)")
            self._initialized = False
            return
        try:
            self._init_android()
        except Exception as e:
            # Broad on purpose: this is the app-startup crash boundary.
            # The Java shim can be absent (built without android.add_src)
            # and Play Services can be broken/outdated — that surfaces as
            # JNI errors, not ImportError. Ads must degrade to disabled,
            # never kill launch.
            _log.exception("[AdManager] Ads init failed — ads disabled: %s", e)
            self._initialized = False

    # --- Banner ---

    def show_banner(self):
        self._banner_wanted = True
        if self._initialized and self._bridge is not None:
            self._show_banner_android()
        # else: the init chain shows it once "init complete" arrives.

    def hide_banner(self):
        self._banner_wanted = False
        if self._initialized and self._bridge is not None:
            self._hide_banner_android()

    # --- Interstitial ---

    def show_interstitial(self):
        if _is_test_id(INTERSTITIAL_ID):
            _log.warning(
                "[AdManager] Interstitial skipped: INTERSTITIAL_ID is a "
                "Google test ID. Create a real ad unit in AdMob and update "
                "game/ads/_shared.py before release."
            )
            return
        if not self._initialized or self._bridge is None:
            return
        self._show_interstitial_android()

    # --- Rewarded Video ---

    def load_rewarded(self):
        """Explicit rewarded preload; the android init chain auto-preloads."""
        if self._initialized and self._bridge is not None:
            self._load_rewarded_android()

    def show_rewarded(self, on_reward_callback):
        """
        Show rewarded video. on_reward_callback() fires only when the user
        actually earns the reward (watches the ad through).
        """
        if _is_test_id(REWARDED_ID):
            _log.warning(
                "[AdManager] Rewarded skipped: REWARDED_ID is a Google test "
                "ID. Create a real ad unit in AdMob and update "
                "game/ads/_shared.py before release."
            )
            return
        if not self._initialized:
            if platform == "android":
                # Ads SDK missing/uninitialized on a real device: no ad →
                # no reward, ever (the free-2x-gold audit fix).
                _log.warning(
                    "[AdManager] Rewarded unavailable (not initialized) — "
                    "no reward granted"
                )
                return
            # Stub: just give reward on desktop for testing
            _log.info("[AdManager] Stub: rewarded ad simulated")
            if on_reward_callback:
                on_reward_callback()
            return
        self._show_rewarded_android(on_reward_callback)

    def is_rewarded_loaded(self):
        if not self._initialized or self._bridge is None:
            return False  # no ads on desktop / uninitialised
        try:
            return bool(self._bridge.isRewardedLoaded())
        except Exception as e:
            # JNI boundary: a broken getter must read as "not loaded".
            _log.warning("[Ads] is_rewarded_loaded error: %s", e)
            return False
