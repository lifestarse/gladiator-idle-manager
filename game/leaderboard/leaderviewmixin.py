# Build: 3
"""LeaderboardManager _LeaderViewMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fix_classloader, _log


class _LeaderViewMixin:
    def show_leaderboard(self, leaderboard_id=None, on_failure=None):
        """Show Play Games leaderboard UI (fullscreen).

        Args:
            leaderboard_id: Optional specific leaderboard ID.  None shows all.
            on_failure: Called with an error string on failure.
        """
        if not self._initialized:
            _log.info("[Leaderboard] Not initialised")
            if on_failure:
                Clock.schedule_once(lambda dt: on_failure("Not signed in"), 0)
            return

        self._show_leaderboard_poll(leaderboard_id, on_failure)

    def _show_leaderboard_poll(self, leaderboard_id=None, on_failure=None):
        """Show leaderboard using task.isComplete() polling."""
        def _do(dt):
            self._lbview_request_intent(leaderboard_id, on_failure)

        Clock.schedule_once(_do, 0)

    def _lbview_request_intent(self, leaderboard_id, on_failure):
        try:
            _fix_classloader()
            client = self._get_client()
            if client is None:
                _log.info("[Leaderboard] No client for show")
                self.status = "Not connected"
                if on_failure:
                    on_failure("Not connected")
                return

            if leaderboard_id:
                task = client.getLeaderboardIntent(leaderboard_id)
            else:
                task = client.getAllLeaderboardsIntent()

            self._lbview_poll_task(task, on_failure)

        except Exception as exc:
            err_msg = str(exc)
            _log.info("[Leaderboard] Show error: %s", err_msg)
            self.status = f"Error: {err_msg}"

    def _lbview_poll_task(self, task, on_failure):
        # Poll task completion on main thread via Clock
        _ticks = [0]

        def _check_task(dt):
            _ticks[0] += 1
            if _ticks[0] > 100:  # 10 seconds max
                Clock.unschedule(_check_task)
                _log.info("[Leaderboard] Task timeout")
                if on_failure:
                    on_failure("Timeout")
                return
            try:
                if not task.isComplete():
                    return
                Clock.unschedule(_check_task)
                self._lbview_deliver_result(task, on_failure)
            except Exception as e:
                Clock.unschedule(_check_task)
                _log.info("[Leaderboard] Poll error: %s", e)

        Clock.schedule_interval(_check_task, 0.1)

    def _lbview_deliver_result(self, task, on_failure):
        if task.isSuccessful():
            self._launch_intent(task.getResult())
            return
        exc = task.getException()
        err = str(exc) if exc else "Unknown error"
        _log.info("[Leaderboard] Task failed: %s", err)
        self.status = f"Error: {err}"
        if on_failure:
            on_failure(err)

    def _launch_intent(self, intent):
        """Launch leaderboard intent on main thread."""
        try:
            activity = self._java["PythonActivity"].mActivity
            activity.startActivityForResult(intent, RC_LEADERBOARD)
            self.status = "Showing leaderboard"
            _log.info("[Leaderboard] Showing leaderboard UI")
        except Exception as e:
            _log.info("[Leaderboard] Launch error: %s", e)
            self.status = f"Error: {e}"

    def show_all_leaderboards(self, on_failure=None):
        self.show_leaderboard(None, on_failure=on_failure)
