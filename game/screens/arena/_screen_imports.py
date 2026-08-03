# Build: 25
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.metrics import dp, sp
from kivy.core.window import Window
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, FloatingText, BaseCard
from game.models import fmt_num, fmt_def
from game.theme import *
from game.theme import popup_color
from game.constants import (
    BATTLE_AUTO_INTERVAL, POPUP_DISMISS_DELAY,
    BATTLE_SPEED_OPTIONS, BATTLE_END_TAP_GUARD,
    FEATURE_UNLOCKS,
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
    make_styled_popup,
)
from game.screens.shared import _safe_clear, _safe_rebind, _play_hit_sound


# Star-imports skip underscore names. Build __all__ dynamically from
# everything imported above so mixin files see BaseScreen, App, etc.
# `_m` is explicitly added (underscore names are skipped by the filter).
import game.theme as _theme_mod  # noqa: F401
import game.models as _m  # module alias for dynamic wire-data refs
__all__ = [n for n in list(globals().keys())
           if not n.startswith('__') and n != 'annotations']
