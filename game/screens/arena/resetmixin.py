# Build: 1
"""ArenaScreen _ResetMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _ResetMixin:
    def _check_pending_reset(self):
        engine = App.get_running_app().engine
        if engine.pending_reset and not getattr(self, '_reset_popup_open', False):
            self._show_reset_popup(engine)

    def _show_reset_popup(self, engine):
        self._reset_popup_open = True
        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=[dp(16), dp(12)])
        content.add_widget(AutoShrinkLabel(
            text=t("all_fighters_dead"), font_size="11sp", bold=True,
            color=ACCENT_RED, size_hint_y=None, height=dp(40),
        ))
        content.add_widget(AutoShrinkLabel(
            text=t("run_ended", n=engine.run_number), font_size="11sp",
            color=TEXT_PRIMARY, size_hint_y=None, height=dp(34),
        ))
        content.add_widget(AutoShrinkLabel(
            text=t("reached_tier_kills", tier=engine.run_max_tier, kills=engine.run_kills),
            font_size="11sp", color=ACCENT_GOLD, size_hint_y=None, height=dp(34),
        ))
        lost_lbl = AutoShrinkLabel(
            text=t("gold_equip_lost"),
            font_size="11sp", color=TEXT_SECONDARY, size_hint_y=None, height=dp(70),
            halign="center", valign="middle",
        )
        bind_text_wrap(lost_lbl)
        content.add_widget(lost_lbl)

        restart_btn = MinimalButton(
            text=t("new_run"), btn_color=ACCENT_RED, font_size=10,
            size_hint_y=None, height=dp(52),
        )
        content.add_widget(restart_btn)

        popup = Popup(
            title=t("permadeath"), title_color=ACCENT_RED, title_size="11sp",
            content=content, size_hint=(0.9, None), height=dp(380),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_RED, auto_dismiss=False,
        )

        def on_restart(inst):
            popup.dismiss()
            self._reset_popup_open = False
            engine.execute_pending_reset()
            # Navigate to Roster hire view instead of separate popup
            app = App.get_running_app()
            app.sm.current = "roster"
            roster_scr = app.sm.get_screen("roster")
            roster_scr.hire()

        restart_btn.bind(on_press=on_restart)
        popup.open()

    def _show_boss_revenge_popup(self, boss_name):
        content = BoxLayout(orientation="vertical", spacing=dp(16), padding=dp(20))
        revenge_lbl = AutoShrinkLabel(
            text=t("boss_revenge"), font_size="11sp", bold=True,
            color=ACCENT_RED, halign="center", valign="middle",
            size_hint_y=0.6,
        )
        bind_text_wrap(revenge_lbl)
        content.add_widget(revenge_lbl)
        sub_lbl = AutoShrinkLabel(
            text=t("boss_revenge_sub"), font_size="11sp",
            color=TEXT_SECONDARY, halign="center", valign="middle",
            size_hint_y=0.4,
        )
        bind_text_wrap(sub_lbl)
        content.add_widget(sub_lbl)
        popup = Popup(
            title=boss_name,
            content=content,
            size_hint=(0.95, 0.5),
            title_size=sp(12),
            background_color=popup_color(BG_CARD),
            title_color=popup_color(ACCENT_RED),
            separator_color=popup_color(ACCENT_RED),
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), POPUP_DISMISS_DELAY)

    def _check_tutorial(self):
        engine = App.get_running_app().engine
        step = engine.get_pending_tutorial()
        if step:
            App.get_running_app().show_tutorial(step)
