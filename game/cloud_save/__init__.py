# Build: 1
"""CloudSaveManager split package."""
from ._core import CloudSaveManager  # noqa: F401
from ._shared import *  # noqa: F401,F403




# Singleton
cloud_save_manager = CloudSaveManager()
