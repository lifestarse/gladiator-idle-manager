# Build: 1
"""ArenaScreen _EffectsMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


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
