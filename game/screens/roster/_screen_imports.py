# Build: 32
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.metrics import dp, sp
from kivy.uix.image import Image as KvImage
from kivy.uix.scrollview import ScrollView
from kivy.effects.scroll import ScrollEffect
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard
import game.models as _m
from game.models import (
    fmt_num, RARITY_COLORS,
    FORGE_WEAPONS, FORGE_ARMOR, FORGE_ACCESSORIES,
    item_display_name,
)
from game.theme import *
from game.theme import popup_color
from game.localization import t
from game.ui_helpers import (
    refresh_roster_grid,
    build_item_info_card,
    _roster_callbacks,
    _perk_callbacks,
    bind_text_wrap,
    make_styled_popup,
)
from game.screens.shared import _safe_clear, _safe_rebind


