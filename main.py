# Build: 63
"""Thin entrypoint shim; real App lives in game.app package."""
import game.kivy_input_shim  # noqa: F401  — must precede any kivy import
from game.app import GladiatorIdleApp

if __name__ == "__main__":
    GladiatorIdleApp().run()
