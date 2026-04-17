# Build: 61
"""
Gladiator Idle Manager — roguelike-manager.
Permadeath resets the run. Stats distributed manually. Fighter classes.
"""

import os
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.utils import platform
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle

from game.engine import GameEngine
from game.models import fmt_num
from game.theme import *
from game.theme import popup_color
from game.localization import t, init_language, set_language, get_language
from game.widgets import AutoShrinkLabel, MinimalButton
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager
from game.leaderboard import leaderboard_manager
from game.ui_helpers import bind_text_wrap

from game.screens.shared import _safe_clear, SCREEN_ORDER
from game.screens.arena import ArenaScreen
from game.screens.roster import RosterScreen
from game.screens.forge import ForgeScreen
from game.screens.expedition import ExpeditionScreen
from game.screens.lore import LoreScreen
from game.screens.more import MoreScreen

# Window.size only on desktop — crashes Android
if platform not in ("android", "ios"):
    Window.size = (360, 640)
Window.clearcolor = BG_DARK

# Register pixel font
from kivy.core.text import LabelBase
LabelBase.register(name='PixelFont', fn_regular='fonts/PressStart2P-Regular.ttf')


class SwipeScreenManager(ScreenManager):
    """ScreenManager — swipe disabled, navigation via NavBar only."""
    pass


# ============================================================
#  APP
# ============================================================

