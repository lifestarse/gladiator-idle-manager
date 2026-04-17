# Build: 1
"""MoreScreen _LeaderboardMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _LeaderboardMixin:
    def show_leaderboard(self):
        """Open Play Games fullscreen leaderboard. Sign in first if needed."""
        engine = App.get_running_app().engine

        try:
            engine.submit_scores()
        except Exception:
            pass

        if leaderboard_manager.is_ready:
            leaderboard_manager.show_all_leaderboards(
                on_failure=lambda err: self._leaderboard_error(err),
            )
        else:
            # Sign in first, then show leaderboard
            def _after_sign_in(success):
                if success:
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
