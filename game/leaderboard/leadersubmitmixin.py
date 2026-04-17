# Build: 1
"""LeaderboardManager _LeaderSubmitMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fix_classloader, _log


class _LeaderSubmitMixin:
    def submit_score(self, leaderboard_id, score):
        if not self._initialized or not leaderboard_id or leaderboard_id.startswith("TBD"):
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
