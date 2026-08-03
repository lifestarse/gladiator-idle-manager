# Build: 67
"""
Gladiator Idle Manager — roguelike-manager.
Permadeath resets the run. Stats distributed manually. Fighter classes.
"""

import logging
import os
from kivy.app import App

_log = logging.getLogger(__name__)
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import (NumericProperty, StringProperty, ListProperty,
                             BooleanProperty, DictProperty)
from kivy.utils import platform
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle

from game.engine import GameEngine
from game.constants import FEATURE_UNLOCKS
from game.models import fmt_num
from game.theme import *
from game.theme import popup_color
from game.localization import (t, init_language, set_language, get_language,
                               get_requested_language)
from game.localization import _BUNDLED_FONT_FILES, _register_fonts
from game.widgets import AutoShrinkLabel, MinimalButton
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager
from game.leaderboard import leaderboard_manager
from game.ui_helpers import bind_text_wrap

from game.screens.shared import _safe_clear
from game.screens.arena import ArenaScreen
from game.screens.roster import RosterScreen
from game.screens.forge import ForgeScreen
from game.screens.expedition import ExpeditionScreen
from game.screens.lore import LoreScreen
from game.screens.more import MoreScreen
from game.screens.scripts import ScriptsScreen, ScriptEditorScreen

# Window.size only on desktop — crashes Android
if platform not in ("android", "ios"):
    Window.size = (360, 640)
Window.clearcolor = BG_DARK

# Register fonts. PixelFont carries headers/numbers; BodyFont (DroidSans)
# carries long descriptions — PressStart2P at small sizes turns paragraph
# text into a wall of noise. The files come from game.localization, which
# re-registers the same table on every set_language(): a second list of file
# names here would win at import and lose on the first language switch.
_register_fonts(_BUNDLED_FONT_FILES)


class SwipeScreenManager(ScreenManager):
    """ScreenManager — swipe disabled, navigation via NavBar only."""
    pass


# ============================================================
#  APP
# ============================================================

