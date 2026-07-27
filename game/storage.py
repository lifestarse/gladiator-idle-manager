# Build: 2
"""Writable per-user storage location — the one place that knows where it is.

Desktop: the user's home directory (where ~/.gladiator_idle_save.json lives).
Android: ``android.storage.app_storage_path()`` — the app's private files dir.

HOME on a real Android device points at /data, which the app cannot write, so
any ``Path.home()``-based path fails there with EACCES (seen in 1.9.45: the
remote-content cache manifest tried /data/.gladiator_content_manifest.json).
Every module that writes a dot-file "next to the save" must build its path
through :func:`user_data_dir` instead of ``Path.home()`` / ``expanduser``.

Android is detected via the ANDROID_ARGUMENT environment variable (set by the
python-for-android bootstrap; it is exactly what kivy.utils.platform checks)
rather than by importing Kivy: importing Kivy has side effects — it parses
sys.argv and prints usage/exits on options it does not know — and this module
is reached at import time by headless CLI tools (scripts/publish_content.py)
that have their own argv. ``android.storage`` is a p4a module, not Kivy, so
the device branch stays Kivy-free too.
"""
from __future__ import annotations

import os
from pathlib import Path


def user_data_dir() -> Path:
    """Directory for the save, caches and markers. Writable on every platform.

    The desktop branch goes through ``Path.home()`` deliberately: tests
    isolate the filesystem by monkeypatching ``pathlib.Path.home``, and this
    keeps that single patch point effective for everything built on top.
    """
    if "ANDROID_ARGUMENT" in os.environ:
        from android.storage import app_storage_path  # noqa
        return Path(app_storage_path())
    return Path.home()
