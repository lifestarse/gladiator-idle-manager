# Build: 1
"""LeaderboardManager core."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fix_classloader, _log
from .leadersubmitmixin import _LeaderSubmitMixin
from .leaderviewmixin import _LeaderViewMixin


class LeaderboardManager(_LeaderSubmitMixin, _LeaderViewMixin):
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
