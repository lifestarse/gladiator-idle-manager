# Build: 6
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


def _mask_email(email):
    """Mask email for logs: "alice@example.com" -> "a***@example.com"."""
    if not email or "@" not in email:
        return "<empty>"
    local, _, domain = email.partition("@")
    if not local:
        return "***@" + domain
    return local[0] + "***@" + domain


# Google Sign-In ApiException status codes we recognize (see CommonStatusCodes
# and GoogleSignInStatusCodes). Returned as substrings inside Java exception
# messages, e.g. "ApiException: 12501: Sign in cancelled".
def classify_signin_error(exc):
    """Map a sign-in / token exception to a localization key.

    Returned key matches a translation entry in data/languages/{en,ru}.json.
    Order matters: more specific patterns first.
    """
    msg = str(exc).lower()
    name = type(exc).__name__.lower()
    if "12501" in msg or "cancel" in msg:
        return "cloud_err_cancelled"
    if "12502" in msg or "currently_in_progress" in msg or "in progress" in msg:
        return "cloud_err_in_progress"
    if "userrecoverable" in name or "userrecoverable" in msg:
        return "cloud_err_recoverable"
    if "developererror" in msg or "developer_error" in msg or " 10:" in msg:
        return "cloud_err_config"
    if "permission denied" in msg or "blocked" in msg or "security" in name:
        return "cloud_err_blocked"
    if (
        "network" in msg or "unreachable" in msg or "connection" in msg
        or "timeout" in msg or "timed out" in msg
        or "ioerror" in name or "ioexception" in msg or " 7:" in msg
    ):
        return "cloud_err_network"
    return "cloud_err_generic"


