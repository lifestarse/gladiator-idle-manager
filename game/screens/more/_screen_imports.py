# Build: 10
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.properties import StringProperty, BooleanProperty
from kivy.metrics import dp, sp
from kivy.core.window import Window
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard
from game.achievements import DIAMOND_BUNDLES
from game.models import fmt_num
from game.theme import *
from game.theme import popup_color
from game.localization import t, set_language, get_language
from game.ui_helpers import (
    _batch_fill_grid,
    bind_text_wrap,
)
from game.ads import ad_manager
from game.iap import iap_manager, PRODUCTS
from game.cloud_save import cloud_save_manager
from game.leaderboard import leaderboard_manager


# Star-imports skip underscore names. Build __all__ dynamically from
# everything imported above so mixin files see BaseScreen, App, etc.
# `_m` is explicitly added (underscore names are skipped by the filter).
import game.theme as _theme_mod  # noqa: F401
import game.models as _m  # module alias for dynamic wire-data refs
__all__ = [n for n in list(globals().keys())
           if not n.startswith('__') and n != 'annotations']
