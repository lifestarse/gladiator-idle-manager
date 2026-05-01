# Build: 8
"""
Google Play Games Services leaderboard integration.

Uses polling instead of PythonJavaClass callbacks to avoid
SIGBUS crashes in jnius when GMS callbacks fire on non-Python threads.
"""

import logging

_log = logging.getLogger(__name__)
import threading
import time as _time
from kivy.utils import platform
from kivy.clock import Clock

# Leaderboard IDs from Play Console
LEADERBOARD_BEST_TIER = "CgkIt_-bs_YQEAIQAQ"
LEADERBOARD_TOTAL_KILLS = "CgkIt_-bs_YQEAIQAg"
LEADERBOARD_STRONGEST_GLADIATOR = "CgkIt_-bs_YQEAIQAw"
# NOTE: Fastest T15 leaderboard has no Play Console ID yet — it's an
# in-game personal-best stat only. If/when a real ID is provisioned, add
# a LEADERBOARD_FASTEST_T15 constant and a branch in submit_all().

RC_SIGN_IN = 9001
RC_LEADERBOARD = 9002


def _fix_classloader():
    """Fix pyjnius ClassLoader issue."""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        Thread = autoclass("java.lang.Thread")
        ct = Thread.currentThread()
        ct.setContextClassLoader(activity.getClassLoader())
    except Exception as exc:
        _log.info("[Leaderboard] ClassLoader fix failed: %s", exc)


