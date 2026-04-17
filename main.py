# Build: 62
"""Thin entrypoint shim; real App lives in game.app package."""
from game.app import GladiatorIdleApp

if __name__ == "__main__":
    GladiatorIdleApp().run()
