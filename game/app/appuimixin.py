# Build: 1
"""App _AppUiMixin."""
from game.app._shared import *  # noqa: F401,F403


class _AppUiMixin:
    def update_top_bar(self):
        engine = self.engine
        self.top_gold = fmt_num(engine.gold)
        self.top_diamonds = fmt_num(engine.diamonds)

    def show_toast(self, msg, duration=2.5):
        """Show a brief error/info notification at the bottom of the screen."""
        self.toast_message = str(msg)
        Clock.unschedule(self._clear_toast)
        Clock.schedule_once(self._clear_toast, duration)

    def _clear_toast(self, *a):
        self.toast_message = ""

    def _setup_toast(self):
        """Create a floating toast Label attached to the Window."""
        lbl = AutoShrinkLabel(
            text="",
            size_hint=(None, None),
            font_size="13sp",
            bold=True,
            color=(1, 1, 1, 1),
            halign="center",
            valign="middle",
            opacity=0,
        )

        def _redraw(lbl, *a):
            w = min(Window.width * 0.85, dp(320))
            lbl.size = (w, dp(44))
            lbl.center_x = Window.width / 2
            lbl.y = Window.height * 0.07
            lbl.text_size = (w - dp(16), None)
            lbl.canvas.before.clear()
            if lbl.opacity > 0:
                with lbl.canvas.before:
                    Color(0.85, 0.25, 0.1, 0.93)
                    RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(10)])

        def _on_toast(app, val):
            lbl.text = val
            lbl.opacity = 1 if val else 0
            _redraw(lbl)

        self.bind(toast_message=_on_toast)
        lbl.bind(pos=_redraw, size=_redraw)
        Window.bind(size=lambda *a: _redraw(lbl))
        _redraw(lbl)
        Clock.schedule_once(lambda *a: Window.add_widget(lbl), 0)

    @staticmethod
    def _any_scroll_active(screen):
        """Return True if any ScrollView is being touched or still scrolling.

        Caches ScrollView references per screen to avoid O(N) tree walk
        on every tick (N = total widgets on screen, can be 400+ on forge).
        """
        from kivy.uix.scrollview import ScrollView
        svs = getattr(screen, '_cached_scrollviews', None)
        if svs is None:
            svs = [w for w in screen.walk() if isinstance(w, ScrollView)]
            screen._cached_scrollviews = svs
        for sv in svs:
            if sv._touch is not None:
                return True
            ey = getattr(sv, 'effect_y', None)
            if ey and abs(getattr(ey, 'velocity', 0)) > 5:
                return True
        return False

    def show_tutorial(self, step):
        self.engine.mark_tutorial_shown(step["id"])
        if not self.root:
            return
        arena = self.sm.get_screen("arena")
        arena.arena_view = "tutorial"
        grid = arena.ids.get("enemy_detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        # Title
        title_lbl = AutoShrinkLabel(
            text=step["title"], font_size="21sp", bold=True,
            color=ACCENT_GOLD, halign="center",
            size_hint_y=None, height=dp(36),
        )
        bind_text_wrap(title_lbl)
        grid.add_widget(title_lbl)

        # Lines
        for line in step["lines"]:
            lbl = AutoShrinkLabel(
                text=line, font_size="18sp", color=TEXT_PRIMARY,
                halign="left", size_hint_y=None, height=dp(40),
            )
            bind_text_wrap(lbl)
            grid.add_widget(lbl)

        # Close button
        close_btn = MinimalButton(
            text=t("got_it"), btn_color=ACCENT_GOLD, text_color=BG_DARK,
            font_size=19, size_hint_y=None, height=dp(48),
        )
        close_btn.bind(on_press=lambda inst: setattr(arena, 'arena_view', 'battle'))
        grid.add_widget(close_btn)
