# Build: 3
"""MoreScreen _LeaderboardMixin — extracted from monolithic screen."""
import logging

from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import

_log = logging.getLogger(__name__)


class _LeaderboardMixin:
    def show_leaderboard(self):
        """Open Play Games fullscreen leaderboard. Sign in first if needed."""
        engine = App.get_running_app().engine

        # Don't block UI if score submission crashes (network, jnius, sign-out
        # race). The leaderboard popup still opens; the user just sees stale
        # scores until the next successful submit. Log so we can diagnose
        # reports from the field.
        try:
            engine.submit_scores()
        except Exception as exc:
            _log.warning("[Leaderboard] submit_scores before show failed: %s", exc)

        if leaderboard_manager.is_ready:
            leaderboard_manager.show_all_leaderboards(
                on_failure=lambda err: self._leaderboard_error(err),
            )
        else:
            # Sign in first, then submit scores and show leaderboard.
            # Submitting before sign-in is a no-op (_initialized=False), so
            # the very first open would otherwise show a user with no score.
            def _after_sign_in(success):
                if success:
                    try:
                        engine.submit_scores()
                    except Exception as exc:
                        _log.warning("[Leaderboard] submit_scores after sign-in failed: %s", exc)
                    leaderboard_manager.show_all_leaderboards(
                        on_failure=lambda err: self._leaderboard_error(err),
                    )
                else:
                    self._leaderboard_error("Sign-in failed")

            leaderboard_manager.sign_in_interactive(callback=_after_sign_in)

    def _leaderboard_error(self, err):
        """Show a brief error toast when Play Games leaderboard fails."""
        content = AutoShrinkLabel(text=f"Play Games: {err}", font_size="11sp",
                       color=TEXT_SECONDARY)
        bind_text_wrap(content)
        popup = Popup(
            title=t("leaderboard_title"),
            content=content,
            size_hint=(0.85, 0.3),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_GOLD),
            separator_color=popup_color(ACCENT_GOLD),
        )
        popup.open()

    def submit_scores(self):
        App.get_running_app().engine.submit_scores()
