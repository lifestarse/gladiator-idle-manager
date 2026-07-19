# Build: 2
"""CloudSaveManager split package."""
from ._core import CloudSaveManager, resolve_auto_sync  # noqa: F401
from ._shared import *  # noqa: F401,F403




# Singleton
cloud_save_manager = CloudSaveManager()
