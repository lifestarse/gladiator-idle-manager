# Build: 11
"""game.ads — AdMob via a thin pyjnius/Java bridge (split from game/ads.py).

The KivMob backend died with Play Services Ads v20+ (legacy rewarded API
removed; Google stopped serving ads to v19). This package talks to
play-services-ads 24.x through java_src/com/gladiator/ads/AdsBridge.java —
see NOTE(ads) in buildozer.spec for the build wiring.

Public surface (unchanged from the KivMob era): AdManager, ad_manager,
ADMOB_APP_ID / BANNER_ID / INTERSTITIAL_ID / REWARDED_ID, USING_REAL_ADS.
"""
from ._shared import (  # noqa: F401
    ADMOB_APP_ID,
    BANNER_ID,
    INTERSTITIAL_ID,
    REWARDED_ID,
    USING_REAL_ADS,
)
from ._core import AdManager  # noqa: F401

# Singleton
ad_manager = AdManager()
