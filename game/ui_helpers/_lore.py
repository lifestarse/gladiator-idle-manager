# Build: 7
"""ui_helpers._lore — achievements list (AchievementCardView + RV refresh).

build_achievement_card() and the legacy lore_grid branch of
refresh_achievement_grid() were removed in the 2026-08 redesign wave 0
cleanup: achievements_rv is always present in kv/lore_screen.kv, so the
fallback never ran. (lore_grid itself is alive — stats/quests/diamond shop
render into it.)
"""
from ._imports import *  # noqa: F401,F403
from ._widgets import _auto_text_size, _diamond_label


# ============================================================
#  ACHIEVEMENTS (LoreScreen)
# ============================================================

# ------------------------------------------------------------------
#  Achievement RecycleView viewclass — name + desc + reward indicator.
#  Horizontal layout, 75dp. Widgets pre-created; refresh_view_attrs
#  swaps the reward slot (DONE label vs diamond icon) based on unlocked.
# ------------------------------------------------------------------

class AchievementCardView(RecycleDataViewBehavior, BoxLayout):
    """RecycleView viewclass for achievements list."""

    def __init__(self, **kwargs):
        from game.widgets import BaseCard
        from kivy.uix.anchorlayout import AnchorLayout
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(75))
        super().__init__(**kwargs)

        self._card = BaseCard(
            orientation="horizontal", size_hint_y=1,
            padding=[dp(10), dp(6)], spacing=dp(8),
        )

        # Info column: name + desc
        self._info = BoxLayout(orientation="vertical",
                               size_hint_x=0.7, spacing=dp(4))
        self._name_lbl = _auto_text_size(AutoShrinkLabel(
            font_size="11sp", bold=True,
            halign="left", size_hint_y=0.5,
        ))
        self._desc_lbl = _auto_text_size(AutoShrinkLabel(
            font_size="10sp", color=list(TEXT_MUTED),
            halign="left", size_hint_y=0.5,
        ))
        self._info.add_widget(self._name_lbl)
        self._info.add_widget(self._desc_lbl)
        self._card.add_widget(self._info)

        # Reward column: DONE label OR diamond count — pre-create both, swap.
        self._reward_slot = AnchorLayout(
            size_hint_x=0.3, anchor_x="center", anchor_y="center",
        )
        self._done_lbl = AutoShrinkLabel(
            text=t("done_label"), font_size="12sp", bold=True,
            color=list(ACCENT_GREEN), halign="center", valign="middle",
            size_hint=(1, 1),
        )
        # Diamond reward (constructed on demand; re-created for each card
        # since _diamond_label may include inline Image widgets).
        self._diamond_widget = None
        self._card.add_widget(self._reward_slot)
        self.add_widget(self._card)

    def refresh_view_attrs(self, rv, index, data):
        unlocked = data.get('unlocked', False)
        if unlocked:
            # Lit violet + gold frame — the old olive-khaki fill was the one
            # surface in the game outside the indigo palette.
            self._card.border_color = list(ACCENT_GOLD)
            self._card.card_color = list(BG_CARD_ACTIVE)
            name_color = list(ACCENT_GOLD)
        else:
            self._card.border_color = list(DIVIDER)
            self._card.card_color = list(BG_CARD)
            name_color = list(TEXT_SECONDARY)

        self._name_lbl.text = data.get('name', '')
        self._name_lbl.color = name_color
        self._desc_lbl.text = data.get('desc', '')

        # Swap reward slot content
        self._reward_slot.clear_widgets()
        if unlocked:
            if self._done_lbl.parent:
                self._done_lbl.parent.remove_widget(self._done_lbl)
            self._reward_slot.add_widget(self._done_lbl)
        else:
            # Re-create diamond label (it contains an Image child that
            # can't be reparented cleanly between refreshes)
            self._diamond_widget = _diamond_label(data.get('diamonds', 0))
            self._reward_slot.add_widget(self._diamond_widget)


def _achievement_to_rv_data(ach):
    """Convert achievement dict to AchievementCardView data dict."""
    return {
        'name': ach.get('name', ''),
        'desc': ach.get('desc', ''),
        'diamonds': ach.get('diamonds', 0),
        'unlocked': ach.get('unlocked', False),
    }


def refresh_achievement_grid(lore_screen):
    """Populate the achievements RecycleView (achievements_rv)."""
    rv = lore_screen.ids.get("achievements_rv")
    if rv is None:
        return
    rv.data = [_achievement_to_rv_data(a) for a in lore_screen.achievements_data]
