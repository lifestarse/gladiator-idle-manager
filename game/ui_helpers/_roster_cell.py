# Build: 6
"""ui_helpers._roster_cell — RosterCardView (list row) + callbacks."""
from game.widgets import PixelBadge

from ._imports import *  # noqa: F401,F403
from ._layouts import _bind_long_tap
from ._widgets import _CLASS_COLORS


# ============================================================
#  ROSTER CARD VIEW (RecycleView viewclass)
# ============================================================

_roster_callbacks = {}
"""Callbacks registered by RosterScreen.on_enter.
Keys: 'show_detail', 'dismiss' → callable(fighter_index: int)
"""

_DEAD_CARD_BG = (0.15, 0.08, 0.08, 1)
_HP_NUM_W = 56
_LV_W = 44
_AWAY_W = 54


class RosterCardView(RecycleDataViewBehavior, CardWidget):
    """RecycleView viewclass for roster cards.

    A small pool of these is kept alive by RecycleView (only visible rows
    + a buffer).  refresh_view_attrs() updates visuals in-place so no
    widget construction happens during scrolling.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(84))
        kwargs.setdefault('padding', [dp(8), dp(8)])
        kwargs.setdefault('spacing', dp(8))
        super().__init__(**kwargs)
        self._fighter_index = 0
        self._dismiss_cb = None

        # Avatar
        self._avatar = GladiatorAvatar(
            fighter_class="mercenary",
            accent_color=list(ACCENT_GREEN),
            tier=1,
            size_hint=(None, 1),
            width=dp(52),
        )

        col = BoxLayout(orientation="vertical", spacing=dp(6),
                        padding=[0, dp(4)])

        top_row = BoxLayout(size_hint_y=None, height=dp(26), spacing=dp(6))
        self._name_lbl = AutoShrinkLabel(
            font_size="11sp", bold=True, color=list(TEXT_PRIMARY),
            halign="left", valign="middle", single_line=True,
        )
        self._name_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        # Plus indicator — available stat/perk points
        self._plus_icon = Image(
            source="icons/ic_plus.png", fit_mode="contain",
            size_hint=(None, None), width=dp(18), height=dp(18),
            pos_hint={'center_y': 0.5}, opacity=0,
        )
        self._level_lbl = AutoShrinkLabel(
            font_size="10sp", bold=True, color=list(ACCENT_GOLD),
            halign="right", valign="middle", single_line=True,
            size_hint_x=None, width=dp(_LV_W),
        )
        self._level_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        top_row.add_widget(self._name_lbl)
        top_row.add_widget(self._plus_icon)
        top_row.add_widget(self._level_lbl)

        hp_row = BoxLayout(size_hint_y=None, height=dp(18), spacing=dp(6))
        self._bar = MinimalBar(
            size_hint=(1, None), height=dp(12),
            pos_hint={'center_y': 0.5},
        )
        self._hp_lbl = AutoShrinkLabel(
            font_size="10sp", bold=True, color=(1, 0.3, 0.3, 1),
            halign="right", valign="middle", single_line=True,
            size_hint_x=None, width=dp(_HP_NUM_W),
        )
        self._hp_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        hp_row.add_widget(self._bar)
        hp_row.add_widget(self._hp_lbl)

        col.add_widget(top_row)
        col.add_widget(hp_row)

        # Third slot (dismiss btn / away badge / empty)
        self._dismiss_btn = MinimalButton(
            text="X", btn_color=list(ACCENT_RED), font_size=11,
            size_hint_x=None, width=dp(36),
        )
        self._away_badge = PixelBadge(
            font_size="9sp", color=list(ACCENT_CYAN),
            badge_color=list(ACCENT_CYAN),
            halign="center", valign="middle",
            size_hint=(None, None), width=dp(_AWAY_W), height=dp(22),
            pos_hint={'center_y': 0.5},
        )
        self._away_badge.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self._empty_lbl = Label(size_hint_x=None, width=0)
        self._slot = 'empty'

        self.add_widget(self._avatar)
        self.add_widget(col)
        self.add_widget(self._empty_lbl)

        # Long-tap opens fighter detail popup
        _bind_long_tap(self, lambda w: self._on_tap())

    def _on_tap(self):
        cb = _roster_callbacks.get('show_detail')
        if cb:
            cb(self._fighter_index)

    def _set_slot(self, slot):
        """Swap the last element (dismiss/away/empty) in the card row."""
        if self._slot == slot:
            return
        if self._slot == 'dismiss':
            self.remove_widget(self._dismiss_btn)
        elif self._slot == 'away':
            self.remove_widget(self._away_badge)
        else:
            self.remove_widget(self._empty_lbl)
        if slot == 'dismiss':
            self.add_widget(self._dismiss_btn)
        elif slot == 'away':
            self.add_widget(self._away_badge)
        else:
            self.add_widget(self._empty_lbl)
        self._slot = slot

    def refresh_view_attrs(self, rv, index, data):
        """Called by RecycleView when this instance is (re)assigned to a row."""
        same_fighter = self._fighter_index == data['index']
        self._fighter_index = data['index']

        # Avatar sprite by class
        fc = data.get('fighter_class', 'mercenary')
        self._avatar.fighter_class = fc
        self._avatar.accent_color = list(_CLASS_COLORS.get(fc, ACCENT_GREEN))
        self._avatar.tier = data.get('level', 1)
        self._avatar.is_wounded = bool(data.get('injuries', 0))

        # Card background — directly update canvas Color objects
        if not data['alive']:
            self._bg_color.rgba = list(_DEAD_CARD_BG)
            self._br_color.rgba = list(ACCENT_RED)
        else:
            self._bg_color.rgba = list(BG_CARD)
            self._br_color.rgba = list(DIVIDER)

        # Name label
        if not data['alive']:
            self._name_lbl.text = f"{data['name']} [{t('dead_tag')}]"
            self._name_lbl.color = list(ACCENT_RED)
        elif data['on_expedition']:
            self._name_lbl.text = data['name']
            self._name_lbl.color = list(ACCENT_CYAN)
        else:
            self._name_lbl.text = data['name']
            self._name_lbl.color = list(TEXT_PRIMARY)

        # Level label
        self._level_lbl.text = f"LV {data['level']}"

        # Third slot
        if not data['alive']:
            self._set_slot('dismiss')
            if self._dismiss_cb is not None:
                self._dismiss_btn.unbind(on_press=self._dismiss_cb)
            idx = data['index']
            self._dismiss_cb = lambda inst, i=idx: (
                _roster_callbacks.get('dismiss') and _roster_callbacks['dismiss'](i)
            )
            self._dismiss_btn.bind(on_press=self._dismiss_cb)
        elif data['on_expedition']:
            self._set_slot('away')
            self._away_badge.text = t('away_tag')
        else:
            self._set_slot('empty')

        # Plus icon — available upgrades
        has_upgrades = data['alive'] and (
            data.get('unused_points', 0) > 0 or data.get('perk_points', 0) > 0
        )
        self._plus_icon.opacity = 1 if has_upgrades else 0

        # HP bar + number ("hp" key is max HP, "current_hp" is live value)
        max_hp = max(1, data.get('hp', 1))
        cur_hp = max(0, data.get('current_hp', max_hp))
        hp_pct = cur_hp / max_hp if data['alive'] else 0
        is_low = hp_pct < LOW_HP_THRESHOLD
        self._bar.bar_color = list(
            HP_PLAYER if hp_pct >= HP_MID_THRESHOLD
            else HP_MID if not is_low else HP_ENEMY)
        self._bar.bg_color = list(HP_PLAYER_BG)
        if same_fighter:
            self._bar.value = hp_pct  # animate delta on the same fighter
        else:
            self._bar.set_immediate(hp_pct)  # pooled rebind: no ghost anim
        self._hp_lbl.text = fmt_num(cur_hp)
        self._hp_lbl.color = list(ACCENT_RED) if is_low else (1, 0.3, 0.3, 1)
        # Do NOT call super().refresh_view_attrs — it would auto-setattr all data
        # keys onto this widget, overwriting CardWidget.active etc.
        # refresh_view_layout is still inherited from RecycleDataViewBehavior.
