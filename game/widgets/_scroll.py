# Build: 3
"""Widgets — ScrollSafeButtonMixin, _FatBarScrollMixin, TouchScrollView, TouchRecycleView."""
from ._imports import *  # noqa: F401,F403
from ._imports import _SCROLL_THRESHOLD  # noqa: F401


class ScrollSafeButtonMixin:
    """Mixin that prevents button presses during/after scrolling.

    Records touch_down position, cancels press visual + ungrabs once the
    finger moves past threshold, and suppresses on_release on touch_up
    if the touch turned out to be a scroll gesture.
    """

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.ud.setdefault('_btn_origin', {})[id(self)] = touch.pos
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        # Cancel "stuck selected" state when ScrollView gave up the
        # touch after scroll_timeout but the finger then started moving.
        origin = touch.ud.get('_btn_origin', {}).get(id(self))
        if origin:
            dx = abs(touch.pos[0] - origin[0])
            dy = abs(touch.pos[1] - origin[1])
            if dx > _SCROLL_THRESHOLD or dy > _SCROLL_THRESHOLD:
                if getattr(self, 'state', None) == 'down':
                    self.state = 'normal'
                if touch.grab_current is self:
                    touch.ungrab(self)
                touch.ud['_btn_origin'].pop(id(self), None)
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        origin = touch.ud.get('_btn_origin', {}).get(id(self))
        if origin and self.collide_point(*touch.pos):
            dx = abs(touch.pos[0] - origin[0])
            dy = abs(touch.pos[1] - origin[1])
            if dx > _SCROLL_THRESHOLD or dy > _SCROLL_THRESHOLD:
                touch.ud['_btn_origin'].pop(id(self), None)
                return True
        return super().on_touch_up(touch)


class _FatBarScrollMixin:
    """Fat scrollbar with on-press widening for fast scrolling on mobile.

    Default bar_width is dp(8) — visibly wider than Kivy's 2px default so
    the user can see and tap the bar. The inactive colour is forced to a
    still-visible alpha so it doesn't fade out between scrolls.

    When the user touches within a generous hit zone on the right edge,
    the bar grows to dp(20) for the duration of the drag — finger-friendly
    fast-scroll target. Returns to dp(8) on release.

    Applied via multiple inheritance to both TouchScrollView and
    TouchRecycleView; both expose the same `bar_width` /
    `bar_inactive_color` API, so a single implementation covers both.
    """
    _IDLE_BAR = dp(8)
    _ACTIVE_BAR = dp(20)
    # Extra padding around the bar so finger taps don't have to land
    # exactly on the 8-pixel column.
    _HIT_PADDING = dp(16)

    def __init__(self, **kwargs):
        kwargs.setdefault('bar_width', self._IDLE_BAR)
        # Keep the bar visible when idle (default fades it out after
        # scroll stops — hard to find again on long lists).
        kwargs.setdefault('bar_inactive_color', (0.7, 0.7, 0.7, 0.45))
        super().__init__(**kwargs)

    def _is_bar_grab(self, touch):
        """True if the touch started in the (widened) scrollbar hit zone
        on the right edge. We use the active bar width plus padding so
        users can grab without hitting the bar pixel-perfectly."""
        if not self.collide_point(*touch.pos):
            return False
        hit_zone = self._ACTIVE_BAR + self._HIT_PADDING
        return touch.x >= self.right - hit_zone

    def on_touch_down(self, touch):
        if getattr(self, 'disabled', False) and self.collide_point(*touch.pos):
            return True
        if self._is_bar_grab(touch):
            self.bar_width = self._ACTIVE_BAR
            # Tag this touch so the matching release knows to shrink
            # without relying on mouse position.
            touch.ud['_fatbar_target'] = self
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.ud.get('_fatbar_target') is self:
            self.bar_width = self._IDLE_BAR
            touch.ud.pop('_fatbar_target', None)
        return super().on_touch_up(touch)


class TouchScrollView(_FatBarScrollMixin, ScrollView):
    """ScrollView that blocks all touches when disabled=True, and has a
    finger-friendly scrollbar via _FatBarScrollMixin."""
    pass


class TouchRecycleView(_FatBarScrollMixin, RecycleView):
    """RecycleView that blocks all touches when disabled=True, and has a
    finger-friendly scrollbar via _FatBarScrollMixin."""
    pass
