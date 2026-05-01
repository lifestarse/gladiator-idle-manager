# Build: 1
"""Shared imports for game.ui_helpers submodules.

Every auto-split submodule pulls the same 22-line block of Kivy widgets /
game widgets / theme / localization / models. Centralised here so a Kivy
API or widget rename propagates in one file instead of 18.
"""
from contextlib import contextmanager  # noqa: F401
import time  # noqa: F401

from kivy.uix.widget import Widget  # noqa: F401
from kivy.uix.boxlayout import BoxLayout  # noqa: F401
from kivy.uix.relativelayout import RelativeLayout  # noqa: F401
from kivy.uix.label import Label  # noqa: F401
from kivy.uix.image import Image  # noqa: F401
from kivy.uix.popup import Popup  # noqa: F401
from kivy.graphics import Color, RoundedRectangle  # noqa: F401
from kivy.metrics import dp, sp  # noqa: F401
from kivy.uix.recycleview.views import RecycleDataViewBehavior  # noqa: F401

from game.widgets import (  # noqa: F401
    CardWidget, MinimalButton, MinimalBar, AutoShrinkLabel, GladiatorAvatar,
)
from game.theme import *  # noqa: F401,F403
from game.models import RARITY_COLORS, fmt_num  # noqa: F401
from game.slots import SLOTS  # noqa: F401
from game.localization import t  # noqa: F401
from game.constants import LOW_HP_THRESHOLD  # noqa: F401
