# Build: 6
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
LEADERBOARD_FASTEST_T15 = "TBD_FASTEST_T15"

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


class LeaderboardManager:

    def __init__(self):
        self._initialized = False
        self._java = {}
        self._account = None
        self._signing_in = False
        self.status = ""

    def init(self):
        """Initialise Play Games Services.

        Completely optional — the app runs fine without it.  Every path that
        touches Java is wrapped in try/except so a missing APP_ID, a missing
        Play Games SDK class, or any jnius issue cannot crash the game.
        """
        if platform != "android":
            self.status = "Desktop mode"
            return
        try:
            from jnius import autoclass

            self._java["PythonActivity"] = autoclass(
                "org.kivy.android.PythonActivity"
            )
            self._java["GoogleSignIn"] = autoclass(
                "com.google.android.gms.auth.api.signin.GoogleSignIn"
            )
            self._java["GoogleSignInOptions"] = autoclass(
                "com.google.android.gms.auth.api.signin.GoogleSignInOptions"
            )
            self._java["GoogleSignInOptionsBuilder"] = autoclass(
                "com.google.android.gms.auth.api.signin.GoogleSignInOptions$Builder"
            )

            _fix_classloader()

            # Check for an existing sign-in without triggering any callback.
            # getLastSignedInAccount() is safe — it never fires callbacks on
            # non-Python threads and does not require the APP_ID to be set.
            try:
                activity = self._java["PythonActivity"].mActivity
                account = self._java["GoogleSignIn"].getLastSignedInAccount(activity)
                if account is not None:
                    self._account = account
                    self._initialized = True
                    self.status = "Play Games ready"
                    print("[Leaderboard] Already signed in")
                else:
                    # Not an error — user just hasn't signed in yet.
                    self.status = "Sign-in required"
                    print("[Leaderboard] No existing account — sign-in required")
            except Exception as exc:
                _log.info("[Leaderboard] Account check failed: %s", exc)
                self.status = "Not available"
                return

            # Try to load PlayGames class (may not exist on older GMS)
            try:
                self._java["PlayGames"] = autoclass(
                    "com.google.android.gms.games.PlayGames"
                )
            except Exception:
                print("[Leaderboard] PlayGames class not available")

        except Exception as exc:
            _log.info("[Leaderboard] Init failed: %s", exc)
            self.status = "Not available"

    @property
    def is_ready(self):
        return self._initialized

    def sign_in_interactive(self, callback=None):
        """Launch interactive Google Sign-In, poll for result."""
        if platform != "android":
            if callback:
                callback(False)
            return

        if self._initialized and self._account is not None:
            if callback:
                callback(True)
            return

        if self._signing_in:
            print("[Leaderboard] Sign-in already in progress, skipping")
            return

        self._signing_in = True
        try:
            activity = self._java["PythonActivity"].mActivity
            DEFAULT_GAMES_SIGN_IN = self._java[
                "GoogleSignInOptions"
            ].DEFAULT_GAMES_SIGN_IN
            gso = (
                self._java["GoogleSignInOptionsBuilder"](DEFAULT_GAMES_SIGN_IN)
                .build()
            )
            client = self._java["GoogleSignIn"].getClient(activity, gso)
            intent = client.getSignInIntent()
            activity.startActivityForResult(intent, RC_SIGN_IN)
            self.status = "Signing in..."
            print("[Leaderboard] Interactive sign-in launched")

            # Poll on main thread via Clock — avoids background thread + sleep
            GoogleSignIn = self._java["GoogleSignIn"]
            act = self._java["PythonActivity"].mActivity
            _attempts = [0]

            def _check_sign_in(dt):
                _attempts[0] += 1
                if _attempts[0] > 30:
                    Clock.unschedule(_check_sign_in)
                    self._signing_in = False
                    self.status = "Sign-in timeout"
                    if callback:
                        callback(False)
                    return
                try:
                    acc = GoogleSignIn.getLastSignedInAccount(act)
                    if acc is not None:
                        Clock.unschedule(_check_sign_in)
                        self._account = acc
                        self._initialized = True
                        self.status = "Play Games ready"
                        self._signing_in = False
                        print("[Leaderboard] Sign-in success (poll)")
                        if callback:
                            callback(True)
                except Exception as _e:
                    _log.warning("Sign-in poll error: %s", _e)

            Clock.schedule_interval(_check_sign_in, 1.0)

        except Exception as exc:
            self._signing_in = False
            _log.info("[Leaderboard] Interactive sign-in error: %s", exc)
            self.status = "Sign-in failed"
            if callback:
                callback(False)

    def _get_client(self):
        """Get LeaderboardsClient."""
        if not self._initialized:
            return None
        try:
            activity = self._java["PythonActivity"].mActivity

            # Try PlayGames API first
            if "PlayGames" in self._java:
                try:
                    return self._java["PlayGames"].getLeaderboardsClient(activity)
                except Exception as _e:
                    _log.warning("Suppressed exception: %s", _e)

            # Fallback
            from jnius import autoclass
            Games = autoclass("com.google.android.gms.games.Games")
            account = self._account
            if account is None:
                account = self._java["GoogleSignIn"].getLastSignedInAccount(activity)
                if account is not None:
                    self._account = account
            if account is None:
                return None
            return Games.getLeaderboardsClient(activity, account)
        except Exception as exc:
            _log.info("[Leaderboard] Get client error: %s", exc)
            return None

    def submit_score(self, leaderboard_id, score):
        if not self._initialized or not leaderboard_id:
            _log.info("[Leaderboard] Submit skipped: initialized=%s", self._initialized)
            return

        def _do(dt):
            try:
                _fix_classloader()
                client = self._get_client()
                if client is None:
                    return
                client.submitScore(leaderboard_id, int(score))
                _log.info("[Leaderboard] Submitted %s to %s", score, leaderboard_id)
            except Exception as exc:
                _log.info("[Leaderboard] Submit error: %s", exc)

        Clock.schedule_once(_do, 0)

    def submit_all(self, best_tier=0, total_kills=0, strongest_gladiator_kills=0,
                    fastest_t15=0):
        if not self._initialized:
            return
        if best_tier > 0:
            self.submit_score(LEADERBOARD_BEST_TIER, best_tier)
        if total_kills > 0:
            self.submit_score(LEADERBOARD_TOTAL_KILLS, total_kills)
        if strongest_gladiator_kills > 0:
            self.submit_score(
                LEADERBOARD_STRONGEST_GLADIATOR, strongest_gladiator_kills
            )
        if fastest_t15 > 0:
            self.submit_score(LEADERBOARD_FASTEST_T15, fastest_t15)

    def show_leaderboard(self, leaderboard_id=None, on_failure=None):
        """Show Play Games leaderboard UI (fullscreen).

        Args:
            leaderboard_id: Optional specific leaderboard ID.  None shows all.
            on_failure: Called with an error string on failure.
        """
        if not self._initialized:
            print("[Leaderboard] Not initialised")
            if on_failure:
                Clock.schedule_once(lambda dt: on_failure("Not signed in"), 0)
            return

        self._show_leaderboard_poll(leaderboard_id, on_failure)

    def _show_leaderboard_poll(self, leaderboard_id=None, on_failure=None):
        """Show leaderboard using task.isComplete() polling."""
        def _do(dt):
            try:
                _fix_classloader()
                client = self._get_client()
                if client is None:
                    print("[Leaderboard] No client for show")
                    self.status = "Not connected"
                    if on_failure:
                        on_failure("Not connected")
                    return

                if leaderboard_id:
                    task = client.getLeaderboardIntent(leaderboard_id)
                else:
                    task = client.getAllLeaderboardsIntent()

                # Poll task completion on main thread via Clock
                _ticks = [0]

                def _check_task(dt):
                    _ticks[0] += 1
                    if _ticks[0] > 100:  # 10 seconds max
                        Clock.unschedule(_check_task)
                        print("[Leaderboard] Task timeout")
                        if on_failure:
                            on_failure("Timeout")
                        return
                    try:
                        if task.isComplete():
                            Clock.unschedule(_check_task)
                            if task.isSuccessful():
                                self._launch_intent(task.getResult())
                            else:
                                exc = task.getException()
                                err = str(exc) if exc else "Unknown error"
                                _log.info("[Leaderboard] Task failed: %s", err)
                                self.status = f"Error: {err}"
                                if on_failure:
                                    on_failure(err)
                    except Exception as e:
                        Clock.unschedule(_check_task)
                        _log.info("[Leaderboard] Poll error: %s", e)

                Clock.schedule_interval(_check_task, 0.1)

            except Exception as exc:
                err_msg = str(exc)
                _log.info("[Leaderboard] Show error: %s", err_msg)
                self.status = f"Error: {err_msg}"

        Clock.schedule_once(_do, 0)

    def _launch_intent(self, intent):
        """Launch leaderboard intent on main thread."""
        try:
            activity = self._java["PythonActivity"].mActivity
            activity.startActivityForResult(intent, RC_LEADERBOARD)
            self.status = "Showing leaderboard"
            print("[Leaderboard] Showing leaderboard UI")
        except Exception as e:
            _log.info("[Leaderboard] Launch error: %s", e)
            self.status = f"Error: {e}"

    def show_all_leaderboards(self, on_failure=None):
        self.show_leaderboard(None, on_failure=on_failure)


# Singleton
leaderboard_manager = LeaderboardManager()
