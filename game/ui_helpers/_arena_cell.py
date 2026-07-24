# Build: 4
"""ui_helpers._arena_cell — ArenaUnitCardView for fighters + enemies."""
from kivy.animation import Animation

from game.widgets import PixelBadge

from ._imports import *  # noqa: F401,F403
from ._layouts import _bind_long_tap
from ._widgets import _CLASS_COLORS


# ============================================================
#  ARENA UNIT CARD VIEW (RecycleView viewclass — fighters AND enemies)
# ============================================================

_arena_callbacks = {}
"""Callbacks registered by ArenaScreen.on_enter.
Keys:
  'fighter_tap' → callable(roster_index: int)
  'enemy_tap'   → callable(enemy_name: str)
"""

_DEAD_CARD_BG = (0.15, 0.08, 0.08, 1)
_HP_NUM_W = 56
_LV_W = 44
_BADGE_W = 54


class ArenaUnitCardView(RecycleDataViewBehavior, CardWidget):
    """One viewclass for both fighters and enemies in the arena.

    RecycleView keeps a small pool alive — only visible rows are real
    widgets. Data dict shape: see _fighter_to_arena_data /
    _enemy_to_arena_data below.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(84))
        kwargs.setdefault('padding', [dp(8), dp(8)])
        kwargs.setdefault('spacing', dp(8))
        super().__init__(**kwargs)
        self._role = 'fighter'
        self._unit_name = ''
        self._unit_index = 0

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
        self._skill_badge = PixelBadge(
            font_size="9sp", color=list(TEXT_MUTED),
            halign="center", valign="middle",
            size_hint_x=None, width=0, opacity=0,
        )
        self._skill_badge.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self._level_lbl = AutoShrinkLabel(
            font_size="10sp", bold=True, color=list(ACCENT_GOLD),
            halign="right", valign="middle", single_line=True,
            size_hint_x=None, width=dp(_LV_W),
        )
        self._level_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        top_row.add_widget(self._name_lbl)
        top_row.add_widget(self._skill_badge)
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

        self.add_widget(self._avatar)
        self.add_widget(col)

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
        same_unit = (self._unit_name == data.get('name', '')
                     and self._role == role)
        self._role = role
        self._unit_index = data.get('index', 0)
        self._unit_name = data.get('name', '')

        alive = data.get('alive', True)
        hp = max(0, data.get('hp', 0))
        max_hp = data.get('max_hp', 1)
        hp_pct = hp / max(1, max_hp)
        is_low = hp_pct < LOW_HP_THRESHOLD
        is_boss = data.get('is_boss', False)

        fc = data.get('fighter_class', 'mercenary') or 'mercenary'
        self._avatar.fighter_class = fc
        self._avatar.tier = data.get('tier', 1)
        self._avatar.enemy_role = data.get('enemy_role', 'soldier') or 'soldier'
        self._avatar.sprite_kind = (
            'boss' if (role == 'enemy' and is_boss)
            else 'enemy' if role == 'enemy' else 'fighter')
        self._avatar.accent_color = list(
            _CLASS_COLORS.get(fc, ACCENT_RED if role == 'enemy' else ACCENT_GREEN)
        )
        self._avatar.is_wounded = not alive or hp <= 0

        # Card background/border depend on role + alive state.
        if role == 'enemy':
            self._bg_color.rgba = list(BG_CARD)
            self._br_color.rgba = list(ACCENT_GOLD if is_boss else ACCENT_RED)
            self._name_lbl.color = list(ACCENT_RED)
        elif not alive or hp <= 0:
            self._bg_color.rgba = list(_DEAD_CARD_BG)
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
            ready = skill_text == "RDY"
            self._skill_badge.color = list(ACCENT_CYAN if ready else TEXT_MUTED)
            self._skill_badge.badge_color = list(
                ACCENT_CYAN if ready else DIVIDER)
            self._skill_badge.width = dp(_BADGE_W)
            self._skill_badge.opacity = 1
        else:
            self._skill_badge.text = ""
            self._skill_badge.width = 0
            self._skill_badge.opacity = 0

        # HP bar: green→amber→red for fighters, red family for enemies.
        if role == 'enemy':
            fill, bg = HP_ENEMY, HP_ENEMY_BG
        else:
            fill = (HP_PLAYER if hp_pct >= HP_MID_THRESHOLD
                    else HP_MID if not is_low else HP_ENEMY)
            bg = HP_PLAYER_BG
        self._bar.bar_color = list(fill)
        self._bar.bg_color = list(bg)
        if same_unit:
            self._bar.value = hp_pct  # animate delta on the same unit
        else:
            Animation.cancel_all(self._bar, '_display_value')
            self._bar.value = hp_pct
            self._bar._display_value = hp_pct  # pooled rebind: no ghost anim
        self._hp_lbl.text = fmt_num(hp)
        self._hp_lbl.color = list(ACCENT_RED) if is_low else (1, 0.3, 0.3, 1)
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
        'enemy_role': '',
        'is_boss': False,
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
        'enemy_role': getattr(enemy, 'role', 'soldier'),
        'is_boss': bool(getattr(enemy, 'is_boss', False)),
        'skill_text': None,
    }


def find_arena_view_by_name(rv, unit_name, role=None):
    """Return the visible ArenaUnitCardView matching name, or None.

    Used by ArenaScreen._flash_damage / _set_sprite_frame; off-screen
    units intentionally skip animations.
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
