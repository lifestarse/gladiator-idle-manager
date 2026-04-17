# Build: 21
import math
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.metrics import dp, sp
from kivy.core.window import Window
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, FloatingText, BaseCard
from game.models import fmt_num
from game.theme import *
from game.theme import popup_color
from game.constants import (
    HEAL_GOLD_PER_HP, BATTLE_AUTO_INTERVAL, POPUP_DISMISS_DELAY,
    HP_HEAL_TIER_MULT,
)
from kivy.animation import Animation
from game.battle import BattlePhase
from game.localization import t
from game.ads import ad_manager
from game.ui_helpers import (
    _arena_callbacks, _fighter_to_arena_data, _enemy_to_arena_data,
    find_arena_view_by_name,
    flash_hp_bar,
    bind_text_wrap,
)
from game.screens.shared import _safe_clear, _safe_rebind, _play_hit_sound


# Star-imports skip underscore names. Build __all__ dynamically from
# everything imported above so mixin files see BaseScreen, App, etc.
# `_m` is explicitly added (underscore names are skipped by the filter).
import game.theme as _theme_mod  # noqa: F401
import game.models as _m  # module alias for dynamic wire-data refs
__all__ = [n for n in list(globals().keys())
           if not n.startswith('__') and n != 'annotations']
