# Build: 1
"""Writable per-user storage location — the one place that knows where it is.

Desktop: the user's home directory (where ~/.gladiator_idle_save.json lives).
Android: ``android.storage.app_storage_path()`` — the app's private files dir.

HOME on a real Android device points at /data, which the app cannot write, so
any ``Path.home()``-based path fails there with EACCES (seen in 1.9.45: the
remote-content cache manifest tried /data/.gladiator_content_manifest.json).
Every module that writes a dot-file "next to the save" must build its path
through :func:`user_data_dir` instead of ``Path.home()`` / ``expanduser``.

Kivy is imported lazily so headless tools and tests can import path-building
code without a Kivy install — the same rule the save path in
game/engine/_core.py has always followed.
"""
from __future__ import annotations

from pathlib import Path


def user_data_dir() -> Path:
    """Directory for the save, caches and markers. Writable on every platform.

    The desktop branch goes through ``Path.home()`` deliberately: tests
    isolate the filesystem by monkeypatching ``pathlib.Path.home``, and this
    keeps that single patch point effective for everything built on top.
    """
    try:
        from kivy.utils import platform
    except ImportError:
        return Path.home()
    if platform == "android":
        from android.storage import app_storage_path  # noqa
        return Path(app_storage_path())
    return Path.home()
