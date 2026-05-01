# Build: 1
"""Widgets — SafeTextInput.

Stock Kivy TextInput shows selection drag handles + a cut/copy/paste bubble.
On Android these are attached directly to the Window (not the widget tree),
so when the host popup or screen is dismissed before the user explicitly
clears the selection, the bubble + handles stay visible on top of the next
screen — they look like a stray "Copy" button and two blue droplets.

`SafeTextInput` simply turns those off. Copy/paste flows that need clipboard
access (e.g. import/export script JSON) ship dedicated buttons next to the
input, so nothing functional is lost.
"""
from kivy.uix.textinput import TextInput


class SafeTextInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.setdefault("use_handles", False)
        kwargs.setdefault("use_bubble", False)
        super().__init__(**kwargs)
