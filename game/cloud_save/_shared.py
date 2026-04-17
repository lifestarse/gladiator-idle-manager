# Build: 4
"""
Google Drive cloud save — works on Android via Google Sign-In + REST API.

All Java (pyjnius) calls happen on the main thread.
Only HTTP requests (Drive API) run in background threads.
"""

import logging

_log = logging.getLogger(__name__)
import json
import time
import ssl
import threading
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from kivy.utils import platform
from kivy.clock import Clock

# Build SSL context. certifi is a required dependency (see buildozer.spec) — it
# provides a CA bundle for Android, where Python can't reliably find system certs.
# If certifi is missing, fall back to system certs; do NOT disable verification,
# since this path transmits the Google OAuth token and cloud save data.
try:
    import certifi
    _ssl_ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _ssl_ctx = ssl.create_default_context()

CLOUD_SAVE_FILENAME = "gladiator_idle_save.json"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"


