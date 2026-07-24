# Build: 1
"""Widgets — ChipRow: adaptive tab/filter chip row (fills or scrolls)."""
from kivy.core.window import Window
from kivy.effects.scroll import ScrollEffect

from ._imports import *  # noqa: F401,F403
from ._buttons import MinimalButton
from ._labels import measure_text

_CHIP_PAD_DP = 14        # horizontal padding inside one chip
_CHIP_MIN_W_DP = 44
_CHIP_SPACING_DP = 4
_ROW_SIDE_PAD_DP = 2
_ROW_EDGE_MARGIN_DP = 28  # assumed screen side margins when own width unknown
_DARK_TEXT = (0.12, 0.09, 0.06, 1)
_LIGHT_FILL_LUMA = 0.55


def _luma(color):
    r, g, b = color[0], color[1], color[2]
    return 0.299 * r + 0.587 * g + 0.114 * b


class ChipRow(ScrollView):
    """Horizontal chip row that never clips its labels.

    If every chip fits at natural width the chips stretch to fill the row
    (segmented-control look). If not, the row scrolls horizontally with
    content-sized chips — replacing the old fixed BoxLayout tabs whose
    labels overlapped ("CommonUncommon…") once translations got long.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(36))
        kwargs.setdefault('do_scroll_x', True)
        kwargs.setdefault('do_scroll_y', False)
        kwargs.setdefault('bar_width', 0)
        kwargs.setdefault('effect_cls', ScrollEffect)
        super().__init__(**kwargs)
        self._box = BoxLayout(spacing=dp(_CHIP_SPACING_DP), size_hint=(None, 1),
                              padding=[dp(_ROW_SIDE_PAD_DP), 0])
        self.add_widget(self._box)

    def set_chips(self, chips, current, on_select, active_color=None,
                  chip_colors=None, font_size=10, avail_width=None):
        """Rebuild the row.

        chips: list of (value, label) pairs.
        current: value of the active chip.
        on_select: callable(value).
        chip_colors: optional {value: rgba} — per-chip accent (e.g. rarity
            colours); used as fill when active and border tint when not.
        """
        if active_color is None:
            active_color = ACCENT_RED
        chip_colors = chip_colors or {}
        if avail_width is None:
            avail_width = self.width if self.width > 1 else (
                Window.width - dp(_ROW_EDGE_MARGIN_DP))

        self._box.clear_widgets()
        widths = [
            max(dp(_CHIP_MIN_W_DP),
                measure_text(str(label), sp(font_size), bold=True)
                + dp(_CHIP_PAD_DP) * 2)
            for _value, label in chips
        ]
        total = (sum(widths) + dp(_CHIP_SPACING_DP) * max(0, len(chips) - 1)
                 + dp(_ROW_SIDE_PAD_DP) * 2)
        fits = total <= avail_width
        self._box.width = avail_width if fits else total

        active_btn = None
        for (value, label), nat_w in zip(chips, widths):
            active = (value == current)
            accent = chip_colors.get(
                value, active_color if active else TEXT_SECONDARY)
            btn = MinimalButton(
                text=str(label), font_size=font_size,
                variant='primary' if active else 'ghost',
                btn_color=list(accent),
            )
            if active and _luma(accent) > _LIGHT_FILL_LUMA:
                btn.text_color = list(_DARK_TEXT)
            if fits:
                btn.size_hint_x = 1
            else:
                btn.size_hint_x = None
                btn.width = nat_w
            btn.bind(on_press=lambda inst, v=value: on_select(v))
            self._box.add_widget(btn)
            if active:
                active_btn = btn
        if not fits and active_btn is not None:
            Clock.schedule_once(
                lambda dt, b=active_btn: b.parent and self.scroll_to(
                    b, padding=dp(10), animate=False), 0)
