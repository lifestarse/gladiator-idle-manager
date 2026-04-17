# Build: 11
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.properties import StringProperty, ListProperty
from kivy.metrics import dp, sp
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton
from game.models import fmt_num, SHARD_TIERS
from game.theme import *
from game.theme import popup_color
from game.localization import t
from game.achievements import ACHIEVEMENTS
from game.story import STORY_CHAPTERS
from game.ui_helpers import (
    refresh_achievement_grid,
    refresh_diamond_shop_grid,
    grid_batch,
    bind_text_wrap,
)


# Star-imports skip underscore names. Build __all__ dynamically from
# everything imported above so mixin files see BaseScreen, App, etc.
# `_m` is explicitly added (underscore names are skipped by the filter).
import game.theme as _theme_mod  # noqa: F401
import game.models as _m  # module alias for dynamic wire-data refs
__all__ = [n for n in list(globals().keys())
           if not n.startswith('__') and n != 'annotations']
