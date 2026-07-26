# Build: 5
"""EventLogCardView — event log RV cell (clickable)."""
from ._imports import *  # noqa: F401,F403

class EventLogCardView(RecycleDataViewBehavior, BoxLayout):
    """Event log entry — 48dp vertical BaseCard with 2 text rows.

    Plain Label with shorten=True (not AutoShrinkLabel) — same reason
    as BattleLogCardView: AutoShrinkLabel's text-fit cascade is
    expensive when strings are long.

    Tap opens a detail view for the event (routes to
    LoreScreen._show_event_detail).
    """

    def __init__(self, **kwargs):
        from game.widgets import BaseCard
        from kivy.uix.label import Label as _Label
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(48))
        super().__init__(**kwargs)
        self._log_idx = -1
        self._lore_screen = None

        self._card = BaseCard(
            orientation="vertical", size_hint_y=1,
            padding=[dp(8), dp(4)], spacing=dp(1),
        )

        def _mk(size_hint, font_size, bold=False, color=TEXT_SECONDARY,
                halign="left"):
            kw = dict(font_size=font_size, bold=bold, color=list(color),
                       halign=halign, valign="middle",
                       font_name='PixelFont', shorten=True,
                       shorten_from='right')
            if isinstance(size_hint, tuple):
                kw['size_hint'] = size_hint
            else:
                kw['size_hint_x'] = size_hint
            lbl = _Label(**kw)
            lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            return lbl

        # Row 1: label + time
        row1 = BoxLayout(size_hint_y=0.45, spacing=dp(2))
        self._label_lbl = _mk(0.70, sp(7), bold=True)
        self._time_lbl  = _mk(0.30, sp(6), color=TEXT_MUTED, halign="right")
        row1.add_widget(self._label_lbl)
        row1.add_widget(self._time_lbl)
        self._card.add_widget(row1)

        # Row 2: detail. size_hint_x=1, not None — None makes Kivy fall back
        # to Widget.width (100px), so the detail text was shorten-ellipsised
        # to a fixed 100px sliver regardless of screen width.
        self._detail_lbl = _mk(1, sp(6))
        self._detail_lbl.size_hint_y = 0.55
        self._card.add_widget(self._detail_lbl)
        self.add_widget(self._card)

        self._card.bind(on_release=lambda *a: self._on_tap())

    def refresh_view_attrs(self, rv, index, data):
        self._log_idx = data.get('log_idx', -1)
        self._lore_screen = data.get('_lore')
        color = list(data.get('color', TEXT_PRIMARY))
        self._card.border_color = color
        self._label_lbl.text = data.get('label', '')
        self._label_lbl.color = color
        self._time_lbl.text = data.get('time_text', '')
        self._detail_lbl.text = data.get('detail', '')

    def _on_tap(self):
        if self._lore_screen and self._log_idx >= 0:
            self._lore_screen._show_event_detail(self._log_idx)
