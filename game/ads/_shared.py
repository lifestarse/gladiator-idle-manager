# Build: 2
"""Shared ad constants + helpers for the game.ads package."""

import logging

from kivy.clock import Clock  # noqa: F401  (re-exported for sibling modules)
from kivy.utils import platform  # noqa: F401

_log = logging.getLogger(__name__)

# --- AdMob Unit IDs ---
# All IDs are real production units from AdMob console (publisher
# 9899076646540406). The _is_test_id guard below still blocks any future
# accidental regressions to Google's test publisher.
ADMOB_APP_ID = "ca-app-pub-9899076646540406~3867094053"
BANNER_ID = "ca-app-pub-9899076646540406/9566843992"
INTERSTITIAL_ID = "ca-app-pub-9899076646540406/4588376646"
REWARDED_ID = "ca-app-pub-9899076646540406/7192144243"

# Google's test publisher — used to block accidental shipping of test ads.
_GOOGLE_TEST_PUBLISHER = "ca-app-pub-3940256099942544"

# Real ads enabled for banner
USING_REAL_ADS = True

# Master kill-switch (2026-07-25, owner decision): ads are pointless with no
# audience, so the whole stack is dark — AdManager.init() returns before any
# MobileAds/UMP/bridge activity and every show/load path stays a no-op.
# Re-enable by flipping this to True; the Java shim, gradle deps and
# APPLICATION_ID stay wired (see NOTE(ads) in buildozer.spec — do NOT strip
# them, the coupled removal is the dangerous change). Desktop rewarded stub
# behavior is unaffected (it never depended on init()).
ADS_ENABLED = False

# Failure-retry backoff for ad loads (seconds): doubles per consecutive
# failure so a no-fill/no-network device doesn't hammer the ad server.
RETRY_DELAY_INITIAL = 15.0
RETRY_DELAY_MAX = 300.0

# Java shim compiled into the APK from java_src/ (buildozer android.add_src).
# It exists because the GMA SDK load callbacks are abstract classes, which
# pyjnius cannot implement. See NOTE(ads) in buildozer.spec.
ADS_BRIDGE_CLASS = "com.gladiator.ads.AdsBridge"
ADS_CALLBACK_INTERFACE = "com/gladiator/ads/AdsCallback"


def _is_test_id(unit_id):
    """True if the ad unit ID belongs to Google's test publisher."""
    return bool(unit_id) and _GOOGLE_TEST_PUBLISHER in unit_id
