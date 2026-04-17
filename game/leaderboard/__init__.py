# Build: 1
"""LeaderboardManager split package."""
from ._core import LeaderboardManager  # noqa: F401
from ._shared import *  # noqa: F401,F403




# Singleton
leaderboard_manager = LeaderboardManager()
