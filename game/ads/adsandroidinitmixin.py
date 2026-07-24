# Build: 1
"""AdManager _AdsAndroidInitMixin — UMP consent → MobileAds init → preload.

Init chain (all async; every event arrives through _AdsListener.onAdEvent
on the Android UI thread and is re-scheduled onto the Kivy thread):

    init() → AdsBridge.gatherConsent()
        → "consent" ready/…error    (UMP form is shown here when required)
        → canRequestAds()? → AdsBridge.initMobileAds()
        → "init" complete → preload interstitial/rewarded (+banner if wanted)

Consent degrades safely: if the UMP info update fails (e.g. offline), an
answer cached by UMP from an earlier session still allows ads
(canRequestAds() stays true); with no cached answer, ads simply stay off
for this session and the game runs ad-free. The GDPR form itself must be
configured in the AdMob console and can only be verified on a real device.
"""
from ._shared import (
    ADS_BRIDGE_CLASS,
    ADS_CALLBACK_INTERFACE,
    Clock,
    RETRY_DELAY_INITIAL,
    RETRY_DELAY_MAX,
    _log,
)


class _AdsAndroidInitMixin:
    def _init_android(self):
        """Wire the Java shim and start the consent → init chain."""
        from jnius import autoclass

        self._bridge = autoclass(ADS_BRIDGE_CLASS)
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        self._activity = PythonActivity.mActivity
        self._listener = self._make_listener()
        _log.info("[AdManager] Gathering UMP consent...")
        self._bridge.gatherConsent(self._activity, self._listener)

    def _make_listener(self):
        """One PythonJavaClass funnel for every Java-side ad event."""
        from jnius import PythonJavaClass, java_method

        manager = self

        class _AdsListener(PythonJavaClass):
            __javainterfaces__ = [ADS_CALLBACK_INTERFACE]
            __javacontext__ = "app"

            @java_method("(Ljava/lang/String;Ljava/lang/String;)V")
            def onAdEvent(self_inner, event, data):
                # Android UI thread → Kivy thread; never touch Kivy here.
                Clock.schedule_once(
                    lambda dt: manager._on_ad_event(event, data), 0
                )

        return _AdsListener()

    # --- Event dispatch (runs on the Kivy thread) ---

    def _on_ad_event(self, event, data):
        _log.info("[AdManager] event=%s data=%s", event, data)
        handler = getattr(self, "_on_%s_event" % event, None)
        if handler is None:
            _log.warning("[AdManager] Unknown ad event: %s", event)
            return
        handler(data)

    def _on_consent_event(self, data):
        if not data.startswith("ready"):
            _log.warning("[AdManager] UMP consent flow issue: %s", data)
        try:
            allowed = bool(self._bridge.canRequestAds(self._activity))
        except Exception as e:
            # JNI boundary: any Java-side failure means "no consent".
            _log.warning("[AdManager] canRequestAds failed: %s", e)
            allowed = False
        if not allowed:
            # No fresh or cached consent → GMA must not start this session.
            _log.warning("[AdManager] No ad consent — ads stay disabled")
            return
        self._bridge.initMobileAds(self._activity)

    def _on_init_event(self, data):
        self._initialized = True
        _log.info("[AdManager] Mobile Ads initialized — preloading")
        self._load_interstitial_android()
        self._load_rewarded_android()
        if self._banner_wanted:
            self._show_banner_android()

    # --- Load-failure backoff ---

    def _retry_later(self, kind, reload_fn):
        delay = self._retry_delays.get(kind, RETRY_DELAY_INITIAL)
        self._retry_delays[kind] = min(delay * 2, RETRY_DELAY_MAX)
        _log.info("[AdManager] %s load failed — retry in %.0fs", kind, delay)
        Clock.schedule_once(lambda dt: reload_fn(), delay)

    def _reset_retry(self, kind):
        self._retry_delays.pop(kind, None)
