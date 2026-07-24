# Build: 2
"""ArenaScreen _EffectsMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import

# Damage numbers cycle through these (x, y) offsets (dp) so rapid hits
# on the same unit don't stack into one unreadable pile.
_DMG_JITTER_DP = ((0, 0), (14, 12), (-12, 6), (24, 18), (-22, 12), (8, 22))
_TICKER_HOLD = 1.8
_TICKER_FADE = 0.7


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
        arena = self.ids.get("arena_zone")
        if not arena:
            return
        from kivy.graphics import Color as GColor, Rectangle as GRect
        with arena.canvas.after:
            flash_c = GColor(0.93, 0.78, 0.18, 0.25)
            flash_r = GRect(pos=arena.pos, size=arena.size)

        def _fade(dt):
            flash_c.a -= 0.05
            if flash_c.a <= 0:
                Clock.unschedule(_fade)
                arena.canvas.after.remove(flash_c)
                arena.canvas.after.remove(flash_r)
        Clock.schedule_interval(_fade, 0.05)
