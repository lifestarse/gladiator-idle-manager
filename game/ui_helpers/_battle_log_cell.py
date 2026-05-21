# Build: 4
"""BattleLogCardView — battle log RV cell."""
from ._imports import *  # noqa: F401,F403

class BattleLogCardView(RecycleDataViewBehavior, BoxLayout):
    """Battle log entry — 78dp vertical BaseCard with 2 text rows.

    Uses plain Kivy Label, NOT AutoShrinkLabel. AutoShrinkLabel's
    on_text cascade (reset font_size → recompute texture → _check_fit
    → maybe shrink → texture redraw) is catastrophic for huge strings
    like "fighter1, fighter2, ..., fighter1000" (~10k chars) — Kivy
    has to render the whole thing once before shrinking. For 20
    visible rows × 2 such labels = 40 giant text renders per layout
    pass. Plain Label with `shorten=True` clips at card width instead.
    Name-list preview is also capped to 5 names + "+N" in the data
    layer (_show_battle_log's _preview helper).
    """

    def __init__(self, **kwargs):
        from game.widgets import BaseCard
        from kivy.uix.label import Label as _Label
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(78))
        super().__init__(**kwargs)
        self._log_idx = -1
        self._lore_screen = None

        self._card = BaseCard(
            orientation="vertical", size_hint_y=1,
            padding=[dp(8), dp(4)], spacing=dp(2),
        )

        def _mk_label(size_hint_x, font_size, bold=False, color=TEXT_SECONDARY,
                      halign="left"):
            lbl = _Label(font_size=font_size, bold=bold,
                         color=list(color), halign=halign, valign="middle",
                         font_name='PixelFont',
                         size_hint_x=size_hint_x, shorten=True,
                         shorten_from='right')
            lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            return lbl

        # Row 1: [result] [tier] [gold] [time]
        row1 = BoxLayout(size_hint_y=0.5, spacing=dp(2))
        self._result_lbl = _mk_label(0.35, sp(7), bold=True)
        self._tier_lbl   = _mk_label(0.12, sp(7), bold=True, color=ACCENT_GOLD)
        self._gold_lbl   = _mk_label(0.23, sp(7), bold=True, color=ACCENT_GOLD)
        self._time_lbl   = _mk_label(0.30, sp(6),            color=TEXT_MUTED,
                                      halign="right")
        for lbl in (self._result_lbl, self._tier_lbl,
                    self._gold_lbl, self._time_lbl):
            row1.add_widget(lbl)
        self._card.add_widget(row1)

        # Row 2: fighters vs enemies (names are pre-capped upstream)
        row2 = BoxLayout(size_hint_y=0.5, spacing=dp(2))
        self._fighters_lbl = _mk_label(0.45, sp(6))
        self._vs_lbl       = _mk_label(0.10, sp(6), color=TEXT_MUTED,
                                        halign="center")
        self._vs_lbl.text = "vs"
        self._enemies_lbl  = _mk_label(0.45, sp(6))
        row2.add_widget(self._fighters_lbl)
        row2.add_widget(self._vs_lbl)
        row2.add_widget(self._enemies_lbl)
        self._card.add_widget(row2)
        self.add_widget(self._card)

        # BaseCard is already ButtonBehavior+ScrollSafeButtonMixin, so on_release
        # fires only on a real tap (blocked when user scrolls >12px). Previously
        # this was _bind_long_tap which duplicated the touch-handler work on
        # every frame during scroll — redundant for a ButtonBehavior widget.
        self._card.bind(on_release=lambda *a: self._on_tap())

    def refresh_view_attrs(self, rv, index, data):
        self._log_idx = data.get('log_idx', -1)
        self._lore_screen = data.get('_lore')
        color = list(data.get('result_color', TEXT_PRIMARY))
        self._card.border_color = color

        self._result_lbl.text = data.get('result_text', '')
        self._result_lbl.color = color
        self._tier_lbl.text = data.get('tier_text', '')
        self._gold_lbl.text = data.get('gold_text', '')
        self._time_lbl.text = data.get('time_text', '')
        self._fighters_lbl.text = data.get('fighters_text', '')
        self._enemies_lbl.text = data.get('enemies_text', '')

    def _on_tap(self):
        if self._lore_screen and self._log_idx >= 0:
            self._lore_screen._show_battle_detail(self._log_idx)
