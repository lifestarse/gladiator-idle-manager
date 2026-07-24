# Build: 1
"""AdManager _AdsAndroidShowMixin — banner/interstitial/rewarded via shim."""
from ._shared import (
    BANNER_ID,
    INTERSTITIAL_ID,
    REWARDED_ID,
    _log,
)


class _AdsAndroidShowMixin:
    # --- Banner ---

    def _show_banner_android(self):
        # The Java side is idempotent: it creates the AdView once, then only
        # toggles visibility / re-requests a failed load.
        self._bridge.loadBanner(self._activity, BANNER_ID)

    def _hide_banner_android(self):
        self._bridge.setBannerVisible(self._activity, False)

    def _on_banner_event(self, data):
        if data == "loaded":
            self._reset_retry("banner")
            # remove_ads may have been bought while the request was in
            # flight — the wanted flag decides, not the load result.
            self._bridge.setBannerVisible(self._activity, self._banner_wanted)
        elif data.startswith("load_failed") and self._banner_wanted:
            self._retry_later("banner", self._show_banner_android)

    # --- Interstitial ---

    def _load_interstitial_android(self):
        self._bridge.loadInterstitial(self._activity, INTERSTITIAL_ID)

    def _show_interstitial_android(self):
        try:
            if self._bridge.isInterstitialLoaded():
                self._bridge.showInterstitial(self._activity)
        except Exception as e:
            # JNI boundary: a broken show must never crash the battle flow.
            _log.warning("[AdManager] show_interstitial error: %s", e)

    def _on_interstitial_event(self, data):
        if data == "loaded":
            self._reset_retry("interstitial")
        elif data.startswith("load_failed"):
            self._retry_later("interstitial", self._load_interstitial_android)
        elif data == "dismissed" or data.startswith("show_failed"):
            # The one-shot ad object was spent (or lost) — preload the next.
            self._load_interstitial_android()

    # --- Rewarded ---

    def _load_rewarded_android(self):
        self._bridge.loadRewarded(self._activity, REWARDED_ID)

    def _show_rewarded_android(self, on_reward_callback):
        try:
            loaded = bool(self._bridge.isRewardedLoaded())
        except Exception as e:
            # JNI boundary: treat any failure as "no ad available".
            _log.warning("[AdManager] isRewardedLoaded error: %s", e)
            loaded = False
        if not loaded:
            # No ad → no reward (audit invariant). is_rewarded_loaded()
            # already reports False, so the UI should not even offer this.
            _log.warning("[AdManager] Rewarded not loaded — no reward granted")
            return
        self._rewarded_callback = on_reward_callback
        self._bridge.showRewarded(self._activity)

    def _on_rewarded_event(self, data):
        if data == "loaded":
            self._reset_retry("rewarded")
        elif data.startswith("load_failed"):
            self._retry_later("rewarded", self._load_rewarded_android)
        elif data.startswith("earned"):
            # The ONLY place a reward is ever granted on android: the user
            # watched the ad through ("earned" precedes "dismissed").
            cb = self._rewarded_callback
            self._rewarded_callback = None
            if cb:
                cb()
        elif data == "dismissed" or data.startswith("show_failed"):
            # Closed early / failed to show → callback dies unrewarded.
            self._rewarded_callback = None
            self._load_rewarded_android()
