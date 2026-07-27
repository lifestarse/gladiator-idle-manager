# Build: 3
"""ArenaScreen _EffectsMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import

# Damage numbers cycle through these (x, y) offsets (dp) so rapid hits
# on the same unit don't stack into one unreadable pile.
_DMG_JITTER_DP = ((0, 0), (14, 12), (-12, 6), (24, 18), (-22, 12), (8, 22))
_TICKER_HOLD = 1.8
_TICKER_FADE = 0.7

# Center banner (victory / boss intro): fade-in, hold, fade-out timings.
_BANNER_FADE_IN = 0.18
_BANNER_FADE_OUT = 0.45
_BANNER_HOLD_VICTORY = 1.3
_BANNER_HOLD_BOSS = 1.6
_BANNER_MAX_WIDTH_DP = 320
_BANNER_BG_ALPHA = 0.96


class _EffectsMixin:
    def _find_unit_view(self, unit_name, is_player):
        """Locate the currently-visible ArenaUnitCardView for a unit, or None.

        RecycleView pool recycles widgets on scroll, so we can't cache a
        name→widget map like the old code did. We walk the visible views
        (always small — one screenful). Off-screen units intentionally skip
        flash/sprite animations since the user can't see them.
        """
        rv_id = "battle_fighters_rv" if is_player else "battle_enemies_rv"
        rv = self.ids.get(rv_id)
        role = "fighter" if is_player else "enemy"
        return find_arena_view_by_name(rv, unit_name, role=role)

    def _flash_damage(self, defender_name, is_player):
        """Flash the HP bar of a damaged unit + shake the card."""
        widget = self._find_unit_view(defender_name, is_player)
        if widget is None:
            return
        flash_hp_bar(widget)
        self._shake_widget(widget)
        self._set_sprite_frame(widget, "hurt", revert_delay=0.25)

    def _shake_widget(self, widget, intensity=None, duration=0.15):
        """Quick horizontal shake for hit reaction."""
        if intensity is None:
            intensity = dp(4)
        orig_x = widget.x
        anim = (
            Animation(x=orig_x + intensity, duration=duration / 4, t="out_sine") +
            Animation(x=orig_x - intensity, duration=duration / 4, t="out_sine") +
            Animation(x=orig_x + intensity / 2, duration=duration / 4, t="out_sine") +
            Animation(x=orig_x, duration=duration / 4, t="out_sine")
        )
        anim.start(widget)

    def _set_sprite_frame(self, widget, frame, revert_delay=0.3):
        """Set avatar sprite frame, revert to idle after delay."""
        for child in widget.walk():
            if hasattr(child, 'frame'):
                child.frame = frame
                Clock.schedule_once(
                    lambda dt, c=child: setattr(c, 'frame', 'idle'), revert_delay)
                break

    def _ticker(self, text, color):
        """Show a battle event in the divider lane between the two panels.

        Replaces the old centre-screen floats for kill/skill spam that used
        to render on top of the unit cards and made both unreadable.
        """
        lbl = self.ids.get("battle_ticker")
        if lbl is None:
            return
        lbl.text = text
        lbl.color = list(color)
        Animation.cancel_all(lbl, "opacity")
        lbl.opacity = 1
        anim = (Animation(opacity=1, duration=_TICKER_HOLD) +
                Animation(opacity=0, duration=_TICKER_FADE))
        anim.start(lbl)

    def _spawn_damage(self, defender_name, is_player, damage, is_crit=False):
        """Float a damage number just above the defender's card."""
        widget = self._find_unit_view(defender_name, is_player)
        arena = self.ids.get("arena_zone")
        if widget is None or arena is None:
            return
        self._dmg_counter = getattr(self, "_dmg_counter", 0) + 1
        jx, jy = _DMG_JITTER_DP[self._dmg_counter % len(_DMG_JITTER_DP)]
        wx, wy = widget.to_window(widget.center_x + widget.width * 0.18,
                                  widget.top - dp(10))
        ax, ay = arena.to_widget(wx, wy)
        ax, ay = ax + dp(jx), ay + dp(jy)
        if is_crit:
            color = list(ACCENT_GOLD)
        elif is_player:
            color = list(ACCENT_RED)
        else:
            color = list(TEXT_PRIMARY)
        ft = FloatingText(
            text=f"-{fmt_num(damage)}" + ("!" if is_crit else ""),
            font_size="13sp" if is_crit else "10sp", bold=True,
            color=color, size_hint=(None, None), size=(dp(90), dp(18)),
        )
        ft.center_x = ax
        ft.y = ay
        arena.add_widget(ft)

    def _spawn_float(self, text, color):
        arena = self.ids.get("arena_zone")
        if arena:
            # Remove finished floats from tracking
            self._active_floats = [f for f in self._active_floats
                                   if f.parent is not None]
            # Stack downward: each active float shifts new one by 30dp
            from kivy.metrics import dp
            offset = len(self._active_floats) * dp(30)
            ft = FloatingText(
                text=text, font_size="12sp", bold=True, color=color,
                center_x=arena.center_x,
                y=arena.center_y - offset,
                size_hint=(None, None),
            )
            arena.add_widget(ft)
            self._active_floats.append(ft)

    def _victory_flash(self):
        """Flash screen gold on victory."""
        self._screen_flash(ACCENT_GOLD, 0.25)

    def _defeat_flash(self):
        """Flash screen red on defeat — mirror of the victory flash."""
        self._screen_flash(ACCENT_RED, 0.22)

    def _screen_flash(self, color, alpha):
        """Full-zone color flash that fades out over ~alpha/0.05 * 50ms."""
        arena = self.ids.get("arena_zone")
        if not arena:
            return
        from kivy.graphics import Color as GColor, Rectangle as GRect
        with arena.canvas.after:
            flash_c = GColor(color[0], color[1], color[2], alpha)
            flash_r = GRect(pos=arena.pos, size=arena.size)

        def _fade(dt):
            flash_c.a -= 0.05
            if flash_c.a <= 0:
                Clock.unschedule(_fade)
                arena.canvas.after.remove(flash_c)
                arena.canvas.after.remove(flash_r)
        Clock.schedule_interval(_fade, 0.05)

    # ------------------------------------------------------------------
    #  Center banners — victory summary / boss intro.
    #  Non-blocking overlay cards (plain BoxLayout, no ButtonBehavior so
    #  they never swallow taps), auto-fade and self-remove like floats.
    # ------------------------------------------------------------------

    def _banner_row(self, text, font_size, color):
        lbl = AutoShrinkLabel(
            text=text, font_size=font_size, bold=True, color=list(color),
            halign="center", valign="middle", single_line=True,
            size_hint_y=None, height=dp(22),
        )
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        return lbl

    def _show_banner(self, rows, border_color, hold=_BANNER_HOLD_VICTORY):
        """Show a centered overlay card. rows = [(text, font_size, color)].

        A new banner replaces the previous one (no stacking) — same
        rationale as the ticker replacing centre-float spam.
        """
        arena = self.ids.get("arena_zone")
        if arena is None:
            return
        prev = getattr(self, "_banner_widget", None)
        if prev is not None and prev.parent:
            Animation.cancel_all(prev)
            prev.parent.remove_widget(prev)

        box = BoxLayout(
            orientation="vertical", size_hint=(None, None),
            padding=[dp(16), dp(10)], spacing=dp(4),
            pos_hint={'center_x': 0.5, 'center_y': 0.60},
        )
        box.width = min(arena.width * 0.86, dp(_BANNER_MAX_WIDTH_DP))
        from kivy.graphics import Color as GColor, Rectangle as GRect, \
            Line as GLine
        with box.canvas.before:
            box._bg_c = GColor(BG_ELEVATED[0], BG_ELEVATED[1],
                               BG_ELEVATED[2], _BANNER_BG_ALPHA)
            box._bg_r = GRect(pos=box.pos, size=box.size)
            box._br_c = GColor(*border_color)
            box._br_l = GLine(rectangle=(0, 0, 0, 0), width=1.2)

        def _sync_geom(w, *_):
            w._bg_r.pos = w.pos
            w._bg_r.size = w.size
            w._br_l.rectangle = (w.x, w.y, w.width, w.height)

        def _sync_alpha(w, val):
            # Explicit alpha multiply — same defensive pattern as the kv
            # ticker background (canvas.before alpha tied to opacity).
            w._bg_c.a = _BANNER_BG_ALPHA * val
            w._br_c.a = border_color[3] * val
        box.bind(pos=_sync_geom, size=_sync_geom, opacity=_sync_alpha)

        for row in rows:
            box.add_widget(self._banner_row(*row))
        box.height = (sum(c.height for c in box.children)
                      + dp(20) + dp(4) * max(0, len(rows) - 1))
        box.opacity = 0
        arena.add_widget(box)
        self._banner_widget = box

        anim = (Animation(opacity=1, duration=_BANNER_FADE_IN, t="out_cubic")
                + Animation(opacity=1, duration=hold)
                + Animation(opacity=0, duration=_BANNER_FADE_OUT,
                            t="out_cubic"))

        def _done(*_args):
            if box.parent:
                box.parent.remove_widget(box)
            if getattr(self, "_banner_widget", None) is box:
                self._banner_widget = None
        anim.bind(on_complete=_done)
        anim.start(box)

    def _show_victory_banner(self, gold, kills):
        """Victory summary for a common win: gold + kill count."""
        self._show_banner(
            [
                (t("victory"), "15sp", ACCENT_GOLD),
                (f"+{fmt_num(gold)} G", "13sp", TEXT_PRIMARY),
                (t("kills_label", n=kills), "10sp", TEXT_SECONDARY),
            ],
            border_color=list(ACCENT_GOLD),
            hold=_BANNER_HOLD_VICTORY,
        )

    def _show_boss_banner(self, boss_name):
        """Boss intro: short dramatic banner (name stays English by design)."""
        self._show_banner(
            [
                (t("boss_challenge"), "14sp", ACCENT_RED),
                (boss_name, "11sp", TEXT_PRIMARY),
            ],
            border_color=list(ACCENT_RED),
            hold=_BANNER_HOLD_BOSS,
        )

    def _show_level_up_banner(self, level):
        """Account level gained. Banner, not a popup: level-ups fire during
        farming and a modal per level would fight the auto-battle loop."""
        rows = [
            (t("level_up"), "15sp", ACCENT_CYAN),
            (f"LV {level}", "13sp", TEXT_PRIMARY),
        ]
        engine = App.get_running_app().engine
        just_opened = [name for name, lvl in FEATURE_UNLOCKS.items()
                       if lvl == level]
        if just_opened:
            rows.append((t(f"feature_{just_opened[0]}"), "10sp", ACCENT_GOLD))
        self._show_banner(rows, border_color=list(ACCENT_CYAN),
                          hold=_BANNER_HOLD_BOSS)

    def _show_tier_up_popup(self, new_tier, gold):
        """Boss defeated → arena tier advanced. The big moment gets a popup."""
        content = BoxLayout(orientation="vertical",
                            padding=[dp(12), dp(8)], spacing=dp(8))
        body = AutoShrinkLabel(
            text=t("tier_up_body", n=new_tier), font_size="11sp", bold=True,
            color=list(TEXT_PRIMARY), halign="center", valign="middle",
        )
        body.bind(size=lambda w, s: setattr(w, 'text_size', s))
        gold_lbl = AutoShrinkLabel(
            text=f"+{fmt_num(gold)} G", font_size="13sp", bold=True,
            color=list(ACCENT_GOLD), halign="center", valign="middle",
            single_line=True, size_hint_y=None, height=dp(24),
        )
        gold_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        cont_btn = MinimalButton(
            text=t("continue_btn"), btn_color=ACCENT_GOLD,
            text_color=BG_DARK, font_size=11,
            size_hint_y=None, height=dp(44),
        )
        content.add_widget(body)
        content.add_widget(gold_lbl)
        content.add_widget(cont_btn)
        popup = make_styled_popup(t("tier_up_title"), content,
                                  size_hint=(0.85, 0.40))
        cont_btn.bind(on_press=lambda inst: popup.dismiss())
        popup.open()
        # Auto-dismiss so an idle/AFK player isn't blocked mid-farm.
        Clock.schedule_once(lambda dt: popup.dismiss(),
                            POPUP_DISMISS_DELAY * 2)
