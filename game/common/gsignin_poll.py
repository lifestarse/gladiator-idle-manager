# Build: 1
"""Shared Clock-based poll for Google Sign-In result.

Both CloudSaveManager (Drive appData OAuth) and LeaderboardManager
(Play Games SSO) need the same post-intent poll: they `startActivityForResult`
a sign-in Intent, then wait for the account to appear via
`GoogleSignIn.getLastSignedInAccount()`. A background thread + sleep would
block the app teardown / pause path; using Kivy's Clock keeps the poll on
the main thread and lets it unschedule cleanly when the user backs out.

The two callers differ only in what they do on success (fetch Drive token
vs. stash `self._account`), so this helper takes `on_found` / `on_timeout`
callbacks and nothing more. Each caller owns its own `self._signing_in`
flag — the helper is stateless, which keeps it safe to import from either
side without a back-reference cycle.
"""
import logging

from kivy.clock import Clock

_log = logging.getLogger(__name__)


def poll_signed_in_account(google_sign_in, activity, on_found, on_timeout,
                           max_attempts=30, interval=1.0, label="SignIn"):
    """Poll `getLastSignedInAccount(activity)` via Clock until non-None.

    Args:
      google_sign_in: GoogleSignIn Java class (``self._java["GoogleSignIn"]``).
      activity: Android activity (``self._java["PythonActivity"].mActivity``).
      on_found(account): fired on the main thread with the signed-in account.
      on_timeout(): fired on the main thread if no account appears in time.
      max_attempts: number of poll ticks before giving up (default 30).
      interval: seconds between polls (default 1.0 → ~30 s total).
      label: short tag included in poll-error logs so you can tell
        "CloudSave" vs "Leaderboard" apart in logcat.

    Returns nothing. Use `Clock.unschedule` inside callbacks only if you need
    to stop early — normal flow schedules exactly one interval and cancels
    itself on success / timeout / exception.
    """
    attempts = [0]

    def _tick(dt):
        attempts[0] += 1
        if attempts[0] > max_attempts:
            Clock.unschedule(_tick)
            on_timeout()
            return
        try:
            acc = google_sign_in.getLastSignedInAccount(activity)
        except Exception as exc:
            # jnius can raise if the sign-in intent hasn't finished yet;
            # keep polling — a single hiccup shouldn't abort the whole wait.
            _log.warning("[%s] Sign-in poll error: %s", label, exc)
            return
        if acc is not None:
            Clock.unschedule(_tick)
            on_found(acc)

    Clock.schedule_interval(_tick, interval)
