# Build: 1
"""Unit tests for the game.ads package state machine (Java shim faked).

Device-only behavior (UMP consent form, real ad serving, reward payout UI)
is out of scope — these cover the pure-Python dispatch logic and the audit
invariant: on android a reward is granted ONLY by an "earned" event.
"""


class _FakeBridge:
    """Stands in for the jnius AdsBridge class (static-method surface)."""

    def __init__(self, can_request=True, rewarded_loaded=False,
                 interstitial_loaded=False):
        self.calls = []
        self.can_request = can_request
        self.rewarded_loaded = rewarded_loaded
        self.interstitial_loaded = interstitial_loaded

    def gatherConsent(self, activity, listener):
        self.calls.append("gatherConsent")

    def canRequestAds(self, activity):
        self.calls.append("canRequestAds")
        return self.can_request

    def initMobileAds(self, activity):
        self.calls.append("initMobileAds")

    def loadBanner(self, activity, unit_id):
        self.calls.append("loadBanner")

    def setBannerVisible(self, activity, visible):
        self.calls.append(("setBannerVisible", bool(visible)))

    def loadInterstitial(self, activity, unit_id):
        self.calls.append("loadInterstitial")

    def isInterstitialLoaded(self):
        return self.interstitial_loaded

    def showInterstitial(self, activity):
        self.calls.append("showInterstitial")

    def loadRewarded(self, activity, unit_id):
        self.calls.append("loadRewarded")

    def isRewardedLoaded(self):
        return self.rewarded_loaded

    def showRewarded(self, activity):
        self.calls.append("showRewarded")


def _android_manager(monkeypatch, **bridge_kwargs):
    import game.ads._core as ads_core
    monkeypatch.setattr(ads_core, "platform", "android")
    mgr = ads_core.AdManager()
    mgr._bridge = _FakeBridge(**bridge_kwargs)
    mgr._activity = object()
    return mgr


# ---------- Consent chain ----------

def test_consent_denied_blocks_mobile_ads_init(monkeypatch):
    mgr = _android_manager(monkeypatch, can_request=False)
    mgr._on_ad_event("consent", "ready")
    assert "initMobileAds" not in mgr._bridge.calls
    assert mgr._initialized is False


def test_consent_ready_inits_then_preloads(monkeypatch):
    mgr = _android_manager(monkeypatch, can_request=True)
    mgr._on_ad_event("consent", "ready")
    assert "initMobileAds" in mgr._bridge.calls
    mgr._on_ad_event("init", "complete")
    assert mgr._initialized is True
    assert "loadInterstitial" in mgr._bridge.calls
    assert "loadRewarded" in mgr._bridge.calls
    assert "loadBanner" not in mgr._bridge.calls  # banner not requested yet


def test_consent_update_error_still_uses_cached_consent(monkeypatch):
    # Offline launch: UMP update fails but a cached consent answer allows
    # ads — the chain must proceed to MobileAds init.
    mgr = _android_manager(monkeypatch, can_request=True)
    mgr._on_ad_event("consent", "update_error:network")
    assert "initMobileAds" in mgr._bridge.calls


# ---------- Banner ----------

def test_banner_requested_before_init_shows_after_init(monkeypatch):
    mgr = _android_manager(monkeypatch)
    mgr.show_banner()  # not initialized yet — only records the wish
    assert "loadBanner" not in mgr._bridge.calls
    mgr._on_ad_event("init", "complete")
    assert "loadBanner" in mgr._bridge.calls


def test_banner_load_respects_remove_ads_bought_mid_flight(monkeypatch):
    mgr = _android_manager(monkeypatch)
    mgr._initialized = True
    mgr.show_banner()
    mgr.hide_banner()  # remove_ads purchased while request in flight
    mgr._on_ad_event("banner", "loaded")
    assert ("setBannerVisible", False) in mgr._bridge.calls
    assert ("setBannerVisible", True) not in mgr._bridge.calls


# ---------- Rewarded: the audit invariant ----------

def test_rewarded_grants_only_on_earned_and_only_once(monkeypatch):
    mgr = _android_manager(monkeypatch, rewarded_loaded=True)
    mgr._initialized = True
    calls = []
    mgr.show_rewarded(lambda: calls.append(1))
    assert "showRewarded" in mgr._bridge.calls
    assert calls == []  # nothing granted at show time
    mgr._on_ad_event("rewarded", "earned:5")
    assert calls == [1]
    mgr._on_ad_event("rewarded", "dismissed")  # follows "earned" on device
    assert calls == [1]  # no double grant
    assert "loadRewarded" in mgr._bridge.calls  # next one preloads


def test_rewarded_dismissed_early_never_grants(monkeypatch):
    mgr = _android_manager(monkeypatch, rewarded_loaded=True)
    mgr._initialized = True
    calls = []
    mgr.show_rewarded(lambda: calls.append(1))
    mgr._on_ad_event("rewarded", "dismissed")
    assert calls == []
    assert mgr._rewarded_callback is None


def test_rewarded_not_loaded_never_grants(monkeypatch):
    mgr = _android_manager(monkeypatch, rewarded_loaded=False)
    mgr._initialized = True
    calls = []
    mgr.show_rewarded(lambda: calls.append(1))
    assert calls == []
    assert "showRewarded" not in mgr._bridge.calls


def test_is_rewarded_loaded_desktop_false():
    import game.ads._core as ads_core
    assert ads_core.AdManager().is_rewarded_loaded() is False


# ---------- Interstitial / retry backoff ----------

def test_interstitial_shows_only_when_loaded(monkeypatch):
    mgr = _android_manager(monkeypatch, interstitial_loaded=False)
    mgr._initialized = True
    mgr.show_interstitial()
    assert "showInterstitial" not in mgr._bridge.calls
    mgr._bridge.interstitial_loaded = True
    mgr.show_interstitial()
    assert "showInterstitial" in mgr._bridge.calls


def test_interstitial_dismissed_preloads_next(monkeypatch):
    mgr = _android_manager(monkeypatch)
    mgr._initialized = True
    mgr._on_ad_event("interstitial", "dismissed")
    assert "loadInterstitial" in mgr._bridge.calls


def test_load_failure_backoff_doubles_and_resets(monkeypatch):
    from game.ads._shared import RETRY_DELAY_INITIAL
    mgr = _android_manager(monkeypatch)
    mgr._initialized = True
    mgr._on_ad_event("rewarded", "load_failed:3")
    assert mgr._retry_delays["rewarded"] == RETRY_DELAY_INITIAL * 2
    mgr._on_ad_event("rewarded", "load_failed:3")
    assert mgr._retry_delays["rewarded"] == RETRY_DELAY_INITIAL * 4
    mgr._on_ad_event("rewarded", "loaded")
    assert "rewarded" not in mgr._retry_delays
