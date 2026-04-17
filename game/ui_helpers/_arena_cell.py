# Build: 1
"""Auto-generated submodule of game.ui_helpers package."""
from contextlib import contextmanager
import time

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from game.widgets import CardWidget, MinimalButton, MinimalBar, AutoShrinkLabel, GladiatorAvatar
from game.theme import *
from game.models import RARITY_COLORS, fmt_num
from game.slots import SLOTS
from game.localization import t
from game.constants import LOW_HP_THRESHOLD
from ._common import _CLASS_COLORS, _bind_long_tap, _icon_label


# ============================================================
#  ARENA UNIT CARD VIEW (RecycleView viewclass — fighters AND enemies)
# ============================================================

_arena_callbacks = {}
"""Callbacks registered by ArenaScreen.on_enter.
Keys:
  'fighter_tap' → callable(roster_index: int)
  'enemy_tap'   → callable(enemy_name: str)
"""


class ArenaUnitCardView(RecycleDataViewBehavior, CardWidget):
    """One viewclass for both fighters and enemies in the arena.

    Before this existed, ArenaScreen._refresh_battle_panels built a fresh
    CardWidget per unit (10+ widgets each) every time count changed. With
    dozens of fighters and enemies that was visibly laggy. RecycleView
    keeps a small pool of these alive — only visible rows are real
    widgets, regardless of total N.

    Data dict shape (see _fighter_to_arena_data / _enemy_to_arena_data):
      role:          "fighter" | "enemy"
      index:         int — roster index for fighters, enemy list index for enemies
      name:          str (used by arena flash/sprite lookup too)
      alive:         bool
      hp, max_hp:    int
      level:         int | None
      tier:          int
      fighter_class: str (for GladiatorAvatar sprite)
      skill_text:    str | None  (fighter-only, e.g. "RDY" / "3")
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(84))
        kwargs.setdefault('padding', [dp(8), dp(10)])
        kwargs.setdefault('spacing', dp(6))
        super().__init__(**kwargs)
        self._role = 'fighter'
        self._unit_name = ''
        self._unit_index = 0

        ROW_H = dp(56)

        self._avatar = GladiatorAvatar(
            fighter_class="mercenary",
            accent_color=list(ACCENT_GREEN),
            tier=1,
            size_hint=(None, None),
            width=dp(48), height=dp(52),
        )
        self._name_lbl = AutoShrinkLabel(
            font_size="12sp", bold=True, color=list(TEXT_PRIMARY),
            halign="left", size_hint_x=None, width=dp(130),
            size_hint_y=None, height=ROW_H,
        )
        self._name_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self._level_lbl = AutoShrinkLabel(
            font_size="11sp", bold=True, color=list(ACCENT_GOLD),
            halign="left", size_hint_x=None, width=dp(56),
            size_hint_y=None, height=ROW_H,
        )
        self._level_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        # Skill badge — fighter-only; collapsed to width 0 when empty.
        self._skill_badge = AutoShrinkLabel(
            font_size="11sp", bold=True, color=list(TEXT_MUTED),
            halign="center", size_hint_x=None, width=0,
            size_hint_y=None, height=ROW_H, opacity=0,
        )
        self._skill_badge.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self._spacer = Label(size_hint_x=1)
        self._stat_box = BoxLayout(
            orientation="horizontal", spacing=dp(2),
            size_hint_x=None, width=dp(94),
            size_hint_y=None, height=ROW_H,
        )
        self._hp_row = _icon_label(
            "sprites/icons/ic_hp.png", 0, (1, 0.3, 0.3, 1),
            font_size="11sp", height=ROW_H,
        )
        self._stat_box.add_widget(self._hp_row)

        self.add_widget(self._avatar)
        self.add_widget(self._name_lbl)
        self.add_widget(self._level_lbl)
        self.add_widget(self._skill_badge)
        self.add_widget(self._spacer)
        self.add_widget(self._stat_box)

        _bind_long_tap(self, lambda w: self._on_tap())

    # --- Exposed for ArenaScreen flash/sprite lookups ---
    @property
    def unit_name(self):
        return self._unit_name

    @property
    def role(self):
        return self._role

    # Arena code reaches into ._bar for flash_hp_bar; expose the avatar too.
    @property
    def sprite_target(self):
        return self._avatar

    def _on_tap(self):
        if self._role == 'fighter':
            cb = _arena_callbacks.get('fighter_tap')
            if cb:
                cb(self._unit_index)
        else:
            cb = _arena_callbacks.get('enemy_tap')
            if cb:
                cb(self._unit_name)

    def refresh_view_attrs(self, rv, index, data):
        """Bind this pooled widget to a new unit row."""
        role = data.get('role', 'fighter')
        self._role = role
        self._unit_index = data.get('index', 0)
        self._unit_name = data.get('name', '')

        alive = data.get('alive', True)
        hp = max(0, data.get('hp', 0))
        max_hp = data.get('max_hp', 1)
        hp_pct = hp / max(1, max_hp)
        is_low = hp_pct < LOW_HP_THRESHOLD

        # Avatar (shared sprite path logic for both roles)
        fc = data.get('fighter_class', 'mercenary') or 'mercenary'
        self._avatar.fighter_class = fc
        self._avatar.tier = data.get('tier', 1)
        self._avatar.accent_color = list(
            _CLASS_COLORS.get(fc, ACCENT_RED if role == 'enemy' else ACCENT_GREEN)
        )
        self._avatar.is_wounded = not alive or hp <= 0

        # Card background/border depend on role + alive state.
        if role == 'enemy':
            self._bg_color.rgba = list(BG_CARD)
            self._br_color.rgba = list(ACCENT_RED)
            self._name_lbl.color = list(ACCENT_RED)
        elif not alive or hp <= 0:
            self._bg_color.rgba = (0.15, 0.08, 0.08, 1)
            self._br_color.rgba = list(ACCENT_RED)
            self._name_lbl.color = list(ACCENT_RED)
        else:
            self._bg_color.rgba = list(BG_CARD)
            self._br_color.rgba = list(DIVIDER)
            self._name_lbl.color = list(TEXT_PRIMARY)

        self._name_lbl.text = data.get('name', '?')

        lvl = data.get('level')
        self._level_lbl.text = f"LV {lvl}" if lvl is not None else ""

        # Skill badge — only fighters show it. width=0 for enemies collapses it.
        skill_text = data.get('skill_text')
        if role == 'fighter' and skill_text:
            self._skill_badge.text = skill_text
            self._skill_badge.color = list(ACCENT_CYAN if skill_text == "RDY" else TEXT_MUTED)
            self._skill_badge.width = dp(40)
            self._skill_badge.opacity = 1
        else:
            self._skill_badge.text = ""
            self._skill_badge.width = 0
            self._skill_badge.opacity = 0

        self._hp_row.children[0].text = fmt_num(hp)
        self._hp_row.children[0].color = list(ACCENT_RED) if is_low else (1, 0.3, 0.3, 1)
        # Do NOT chain to super().refresh_view_attrs (same reason as RosterCardView).


def _fighter_to_arena_data(fighter, roster_index, skill_text=None):
    """Turn a Fighter into the dict shape ArenaUnitCardView expects."""
    return {
        'role': 'fighter',
        'index': roster_index,
        'name': fighter.name,
        'alive': bool(fighter.alive and fighter.hp > 0),
        'hp': max(0, fighter.hp),
        'max_hp': fighter.max_hp,
        'level': getattr(fighter, 'level', 1),
        'tier': getattr(fighter, 'tier', 1),
        'fighter_class': getattr(fighter, 'fighter_class', 'mercenary'),
        'skill_text': skill_text,
    }


def _enemy_to_arena_data(enemy, enemy_index):
    """Turn an Enemy into the dict shape ArenaUnitCardView expects."""
    return {
        'role': 'enemy',
        'index': enemy_index,
        'name': enemy.name,
        'alive': enemy.hp > 0,
        'hp': max(0, enemy.hp),
        'max_hp': enemy.max_hp,
        'level': getattr(enemy, 'level', None),
        'tier': getattr(enemy, 'tier', 1),
        'fighter_class': getattr(enemy, 'fighter_class', 'mercenary'),
        'skill_text': None,
    }


def find_arena_view_by_name(rv, unit_name, role=None):
    """Walk the RV layout manager's live views and return one matching name.

    Used by ArenaScreen._flash_damage / _set_sprite_frame. Only visible
    (on-screen) views are returned — off-screen units don't animate, which
    is fine because the user can't see them anyway.
    """
    if rv is None:
        return None
    lm = getattr(rv, 'layout_manager', None)
    if lm is None:
        return None
    for view in getattr(lm, 'children', []):
        if not isinstance(view, ArenaUnitCardView):
            continue
        if view._unit_name != unit_name:
            continue
        if role is not None and view._role != role:
            continue
        return view
    return None
