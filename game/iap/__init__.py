# Build: 5
"""game.iap — split from 29KB monolith."""
from ._core import IAPManager  # noqa: F401
from ._shared import *  # noqa: F401,F403




# Singleton
iap_manager = IAPManager()
