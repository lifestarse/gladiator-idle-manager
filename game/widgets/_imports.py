# Build: 1
"""Shared Kivy + theme imports for game.widgets submodules.

Every widget file (_buttons, _scroll, _labels, _bars, _avatar, _nav, _cards)
pulled the same 20-line Kivy/theme import block. Centralised here so a Kivy
API or theme-colour rename happens in one file instead of seven.
"""
import os  # noqa: F401

from kivy.uix.widget import Widget  # noqa: F401
from kivy.uix.boxlayout import BoxLayout  # noqa: F401
from kivy.uix.scrollview import ScrollView  # noqa: F401
from kivy.uix.recycleview import RecycleView  # noqa: F401
from kivy.uix.label import Label  # noqa: F401
from kivy.uix.image import Image  # noqa: F401
from kivy.uix.behaviors import ButtonBehavior  # noqa: F401
from kivy.graphics import (  # noqa: F401
    Color, RoundedRectangle, Rectangle, Line, Ellipse,
    PushMatrix, PopMatrix, Rotate,
)
from kivy.properties import (  # noqa: F401
    NumericProperty, StringProperty, ListProperty, BooleanProperty,
)
from kivy.animation import Animation  # noqa: F401
from kivy.clock import Clock  # noqa: F401
from kivy.metrics import dp, sp  # noqa: F401

from game.theme import *  # noqa: F401,F403

# Shared threshold used by multiple widgets to decide whether a touch move
# counts as a scroll (cancel tap) rather than a button press.
_SCROLL_THRESHOLD = 12  # px
