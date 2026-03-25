# Build: 1
"""
Google Play Games Services leaderboard integration.

Uses polling instead of PythonJavaClass callbacks to avoid
SIGBUS crashes in jnius when GMS callbacks fire on non-Python threads.
"""

import threading
import time as _time
from kivy.utils import platform
from kivy.clock import Clock

# Leaderboard IDs from Play Console
LEADERBOARD_BEST_TIER = "CgkIt_-bs_YQEAIQAQ"
LEADERBOARD_TOTAL_KILLS = "CgkIt_-bs_YQEAIQAg"
LEADERBOARD_STRONGEST_GLADIATOR = "CgkIt_-bs_YQEAIQAw"

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
        print(f"[Leaderboard] ClassLoader fix failed: {exc}")


class LeaderboardManager:

    def __init__(self):
        self._initialized = False
        self._java = {}
        self._account = None
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
                print(f"[Leaderboard] Account check failed: {exc}")
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
            print(f"[Leaderboard] Init failed: {exc}")
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

            # Poll for result in background
            def _poll():
                GoogleSignIn = self._java["GoogleSignIn"]
                act = self._java["PythonActivity"].mActivity
                for _ in range(30):
                    _time.sleep(1)
                    try:
                        acc = GoogleSignIn.getLastSignedInAccount(act)
                        if acc is not None:
                            self._account = acc
                            self._initialized = True
                            Clock.schedule_once(
                                lambda dt: setattr(self, 'status', 'Play Games ready'), 0
                            )
                            print("[Leaderboard] Sign-in success (poll)")
                            if callback:
                                Clock.schedule_once(lambda dt: callback(True), 0)
                            return
                    except Exception:
                        pass

                Clock.schedule_once(
                    lambda dt: setattr(self, 'status', 'Sign-in timeout'), 0
                )
                if callback:
                    Clock.schedule_once(lambda dt: callback(False), 0)

            threading.Thread(target=_poll, daemon=True).start()

        except Exception as exc:
            print(f"[Leaderboard] Interactive sign-in error: {exc}")
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
                except Exception:
                    pass

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
            print(f"[Leaderboard] Get client error: {exc}")
            return None

    def submit_score(self, leaderboard_id, score):
        if not self._initialized or not leaderboard_id:
            return

        def _do(dt):
            try:
                _fix_classloader()
                client = self._get_client()
                if client is None:
                    return
                client.submitScore(leaderboard_id, int(score))
                print(f"[Leaderboard] Submitted {score} to {leaderboard_id}")
            except Exception as exc:
                print(f"[Leaderboard] Submit error: {exc}")

        Clock.schedule_once(_do, 0)

    def submit_all(self, best_tier=0, total_kills=0, strongest_gladiator_kills=0):
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

                # Poll task completion in background thread
                def _poll_task():
                    for _ in range(100):  # 10 seconds max
                        _time.sleep(0.1)
                        try:
                            if task.isComplete():
                                if task.isSuccessful():
                                    intent = task.getResult()
                                    Clock.schedule_once(
                                        lambda dt, i=intent: self._launch_intent(i), 0
                                    )
                                else:
                                    exc = task.getException()
                                    err = str(exc) if exc else "Unknown error"
                                    print(f"[Leaderboard] Task failed: {err}")
                                    Clock.schedule_once(
                                        lambda dt: setattr(self, 'status', f'Error: {err}'), 0
                                    )
                                    if on_failure:
                                        Clock.schedule_once(
                                            lambda dt, e=err: on_failure(e), 0
                                        )
                                return
                        except Exception as e:
                            print(f"[Leaderboard] Poll error: {e}")
                            break

                    print("[Leaderboard] Task timeout")
                    if on_failure:
                        Clock.schedule_once(
                            lambda dt: on_failure("Timeout"), 0
                        )

                threading.Thread(target=_poll_task, daemon=True).start()

            except Exception as exc:
                err_msg = str(exc)
                print(f"[Leaderboard] Show error: {err_msg}")
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
            print(f"[Leaderboard] Launch error: {e}")
            self.status = f"Error: {e}"

    def show_all_leaderboards(self, on_failure=None):
        self.show_leaderboard(None, on_failure=on_failure)


# Singleton
leaderboard_manager = LeaderboardManager()
