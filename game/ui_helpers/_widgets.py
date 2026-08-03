# Build: 4
"""ui_helpers._widgets — widget factories: buttons, popups, labels, icons."""
from ._imports import *  # noqa: F401,F403


_CLASS_COLORS = {
    "mercenary": ACCENT_GREEN,
    "assassin": ACCENT_RED,
    "tank": ACCENT_BLUE,
    "berserker": ACCENT_RED,
    "retiarius": ACCENT_CYAN,
    "medicus": ACCENT_PURPLE,
}


_ITEM_ICON_SLOTS = ("weapon", "armor", "accessory", "relic")
_EMPTY_STATE_ICON_ALPHA = 0.35


def build_empty_state(text, icon_src="sprites/icons/ic_swords.png",
                      height=None):
    """Centered dimmed icon + muted caption — replaces bare grey strings
    for empty lists ("no eligible fighters", empty inventory, ...)."""
    if height is None:
        height = dp(72)
    box = BoxLayout(orientation="vertical", size_hint_y=None, height=height,
                    spacing=dp(4), padding=[0, dp(4)])
    ico = Image(source=icon_src, fit_mode="contain",
                size_hint=(1, None), height=height * 0.45,
                color=[1, 1, 1, _EMPTY_STATE_ICON_ALPHA])
    lbl = AutoShrinkLabel(
        text=text, font_size="10sp", color=list(TEXT_MUTED),
        halign="center", valign="top",
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    box.add_widget(ico)
    box.add_widget(lbl)
    return box


def item_icon_source(slot, rarity):
    """Sprite path for an item card icon, or '' when no art exists.

    The sprites/items/ set shipped with the game but was never shown in
    the forge/inventory lists.
    """
    if slot in _ITEM_ICON_SLOTS and rarity:
        import os
        path = os.path.join("sprites", "items", f"{slot}_{rarity}.png")
        return path if os.path.exists(path) else ""
    return ""


def bind_text_wrap(label):
    """Make a Kivy Label wrap text to its widget size. Call after construction."""
    label.bind(size=lambda w, s: setattr(w, "text_size", s))


def build_back_btn(callback):
    """Standard back button used across all detail views."""
    btn = MinimalButton(
        text=t("back_btn"), variant="secondary", btn_color=ACCENT_BLUE,
        text_color=TEXT_PRIMARY, font_size=11,
        size_hint_y=None, height=dp(48),
    )
    btn.bind(on_press=lambda *a: callback())
    return btn


def make_styled_popup(title, content, size_hint=(0.92, 0.75)):
    """Popup styled with game theme colours."""
    return Popup(
        title=title, content=content,
        size_hint=size_hint,
        title_size=sp(12),
        background_color=popup_color(BG_CARD),
        title_color=popup_color(ACCENT_GOLD),
        separator_color=popup_color(ACCENT_GOLD),
    )


def make_dynamic_label(text, font_size="11sp", color=TEXT_SECONDARY,
                       padding=dp(16), halign="left"):
    """Label that auto-wraps and auto-sizes height to content."""
    lbl = AutoShrinkLabel(
        text=text, font_size=font_size, color=color,
        size_hint_y=None, halign=halign, valign="top", markup=True,
    )
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - padding, None)))
    lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)))
    return lbl


def build_tab_row(tabs, current, on_select, active_color=None, inactive_color=None,
                  height=None, font_size=10, chip_colors=None):
    """Build a horizontal row of tab chips (adaptive: fills or scrolls).

    Args:
        tabs: list of (value, display_text) pairs
        current: currently active value
        on_select: callable(value) called when a tab is pressed
        active_color: RGBA accent for the active chip (default: ACCENT_RED)
        inactive_color: kept for backward compat, unused (ghost chips now)
        height: row height (default: dp(36))
        font_size: chip font size
        chip_colors: optional {value: rgba} per-chip accent (e.g. rarity)
    Returns:
        ChipRow widget (never clips labels — scrolls when too wide)
    """
    from game.widgets import ChipRow
    row = ChipRow(height=height if height is not None else dp(36))
    row.set_chips(tabs, current, on_select, active_color=active_color,
                  chip_colors=chip_colors, font_size=font_size)
    return row


def _auto_text_size(label):
    bind_text_wrap(label)
    return label


def _diamond_label(amount, font_size="12sp", color=ACCENT_CYAN):
    """BoxLayout with number + diamond icon (icon to the right), vertically centered."""
    from kivy.uix.anchorlayout import AnchorLayout
    anchor = AnchorLayout(size_hint=(1, 1), anchor_x="center", anchor_y="center")
    box = BoxLayout(
        orientation="horizontal", size_hint=(None, None),
        spacing=0, height=dp(28),
    )
    box.bind(minimum_width=box.setter("width"))
    lbl = AutoShrinkLabel(
        text=str(amount), font_size=font_size, bold=True,
        color=color, halign="right", valign="middle",
        size_hint_x=None,
    )
    lbl.bind(texture_size=lbl.setter("size"))
    box.add_widget(lbl)
    box.add_widget(Image(
        source="sprites/icons/ic_gem.png", fit_mode="contain",
        size_hint=(None, None), width=dp(18), height=dp(18),
    ))
    anchor.add_widget(box)
    return anchor
