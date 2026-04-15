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


class CloudSaveManager:
    """Google Drive cloud save via REST API."""

    def __init__(self):
        self._token = None
        self._file_id = None
        self._initialized = False
        self._signing_in = False
        self.last_sync_status = "Not connected"
        self.user_email = ""
        self._java = {}
        self._gso = None
        self.on_auto_connected = None  # callback for silent sign-in

    def init(self):
        """Load Google classes and try silent sign-in (all on main thread).
        Deferred to avoid crash during app startup."""
        if platform != "android":
            self.last_sync_status = "Desktop mode"
            return False
        # Defer init to next frame to avoid crash during startup
        Clock.schedule_once(self._deferred_init, 1.0)
        return False

    def _deferred_init(self, dt):
        """Actual init — runs after app is fully started."""
        try:
            from jnius import autoclass
            self._java["PythonActivity"] = autoclass("org.kivy.android.PythonActivity")
            self._java["GoogleSignIn"] = autoclass(
                "com.google.android.gms.auth.api.signin.GoogleSignIn"
            )
            self._java["GoogleSignInOptions"] = autoclass(
                "com.google.android.gms.auth.api.signin.GoogleSignInOptions"
            )
            self._java["GSOBuilder"] = autoclass(
                "com.google.android.gms.auth.api.signin.GoogleSignInOptions$Builder"
            )
            self._java["Scope"] = autoclass(
                "com.google.android.gms.common.api.Scope"
            )
            self._java["GoogleAuthUtil"] = autoclass(
                "com.google.android.gms.auth.GoogleAuthUtil"
            )
            print("[CloudSave] Google Play Services classes loaded")

            # Build GSO on main thread
            self._gso = self._build_gso()

            # Check last signed-in account (main thread)
            self._check_existing_account()
        except Exception as exc:
            _log.info("[CloudSave] Google Play Services not available: %s", exc)
            self.last_sync_status = "Not available"

    def _build_gso(self):
        """Build GoogleSignInOptions with Drive scope (must run on main thread)."""
        GSO = self._java["GoogleSignInOptions"]
        GSOBuilder = self._java["GSOBuilder"]
        Scope = self._java["Scope"]

        drive_scope = Scope("https://www.googleapis.com/auth/drive.appdata")
        return (
            GSOBuilder(GSO.DEFAULT_SIGN_IN)
            .requestEmail()
            .requestScopes(drive_scope)
            .build()
        )

    def _check_existing_account(self):
        """Check if user is already signed in (main thread)."""
        try:
            GoogleSignIn = self._java["GoogleSignIn"]
            activity = self._java["PythonActivity"].mActivity
            account = GoogleSignIn.getLastSignedInAccount(activity)
            if account is not None:
                self.user_email = account.getEmail() or ""
                # Get token in background (only uses GoogleAuthUtil — already loaded)
                threading.Thread(
                    target=self._fetch_token, args=(account,), daemon=True
                ).start()
            else:
                self.last_sync_status = "Sign-in required"
        except Exception as exc:
            _log.info("[CloudSave] Account check failed: %s", exc)
            self.last_sync_status = "Sign-in required"

    def _fetch_token(self, account, on_success=None):
        """Get OAuth2 token (background thread — only uses pre-loaded classes)."""
        try:
            GoogleAuthUtil = self._java["GoogleAuthUtil"]
            activity = self._java["PythonActivity"].mActivity
            scope = "oauth2:https://www.googleapis.com/auth/drive.appdata"
            token = GoogleAuthUtil.getToken(activity, account.getAccount(), scope)
            self._token = token
            self._initialized = True
            email = account.getEmail() or ""
            _log.info("[CloudSave] Got auth token for %s", email)
            if on_success:
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: on_success(), 0)
            Clock.schedule_once(lambda dt: self._set_status("Connected"), 0)
            if self.on_auto_connected:
                Clock.schedule_once(lambda dt: self.on_auto_connected(), 0.5)
        except Exception as exc:
            _log.info("[CloudSave] Token error: %s", exc)
            Clock.schedule_once(
                lambda dt: self._set_status("Token error"), 0
            )

    def sign_in(self, on_success=None, on_failure=None):
        """Start interactive Google Sign-In (main thread for intent, bg for token)."""
        if platform != "android" or not self._java or not self._gso:
            if on_failure:
                on_failure("Not available")
            return

        if self._signing_in:
            return
        self._signing_in = True

        try:
            GoogleSignIn = self._java["GoogleSignIn"]
            activity = self._java["PythonActivity"].mActivity
            client = GoogleSignIn.getClient(activity, self._gso)

            # Launch sign-in intent (non-blocking, on main thread)
            sign_in_intent = client.getSignInIntent()
            activity.startActivityForResult(sign_in_intent, 9001)

            # Poll on main thread via Clock — avoids background thread + sleep
            _attempts = [0]

            def _check_sign_in(dt):
                _attempts[0] += 1
                if _attempts[0] > 30:
                    Clock.unschedule(_check_sign_in)
                    self._signing_in = False
                    self._set_status("Sign-in timeout")
                    if on_failure:
                        on_failure("Timeout")
                    return
                try:
                    acc = GoogleSignIn.getLastSignedInAccount(activity)
                    if acc is not None:
                        Clock.unschedule(_check_sign_in)
                        self.user_email = acc.getEmail() or ""
                        self._signing_in = False
                        threading.Thread(
                            target=self._fetch_token, args=(acc, on_success),
                            daemon=True
                        ).start()
                except Exception as _e:
                    _log.warning("Sign-in poll error: %s", _e)

            Clock.schedule_interval(_check_sign_in, 1.0)

        except Exception as exc:
            self._signing_in = False
            err_msg = str(exc)
            _log.info("[CloudSave] Sign-in error: %s", err_msg)
            self.last_sync_status = f"Failed: {err_msg}"
            if on_failure:
                on_failure(err_msg)

    def _set_status(self, status):
        self.last_sync_status = status

    def _api_headers(self):
        return {"Authorization": f"Bearer {self._token}"}

    def _find_save_file(self):
        """Find save file ID in appDataFolder."""
        if self._file_id:
            return self._file_id
        try:
            params = urlencode({
                "spaces": "appDataFolder",
                "q": f"name='{CLOUD_SAVE_FILENAME}'",
                "fields": "files(id,name)",
                "pageSize": "1",
            })
            req = Request(
                f"{DRIVE_FILES_URL}?{params}",
                headers=self._api_headers(),
            )
            resp = urlopen(req, timeout=15, context=_ssl_ctx)
            data = json.loads(resp.read().decode("utf-8"))
            files = data.get("files", [])
            if files:
                self._file_id = files[0]["id"]
                return self._file_id
        except Exception as exc:
            _log.info("[CloudSave] Find file error: %s", exc)
        return None

    def upload_save(self, save_data, on_done=None):
        """Upload save to Drive appDataFolder."""
        if not self._initialized or not self._token:
            self.last_sync_status = "Not connected"
            if on_done:
                on_done(False, "Not connected")
            return

        def _do_upload():
            try:
                content = json.dumps(save_data).encode("utf-8")
                file_id = self._find_save_file()

                if file_id:
                    req = Request(
                        f"{DRIVE_UPLOAD_URL}/{file_id}?uploadType=media",
                        data=content,
                        headers={
                            **self._api_headers(),
                            "Content-Type": "application/json",
                        },
                        method="PATCH",
                    )
                    urlopen(req, timeout=30, context=_ssl_ctx)
                else:
                    boundary = "gladiator_boundary_123"
                    metadata = json.dumps({
                        "name": CLOUD_SAVE_FILENAME,
                        "parents": ["appDataFolder"],
                    }).encode("utf-8")

                    body = (
                        f"--{boundary}\r\n"
                        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                    ).encode() + metadata + (
                        f"\r\n--{boundary}\r\n"
                        f"Content-Type: application/json\r\n\r\n"
                    ).encode() + content + f"\r\n--{boundary}--".encode()

                    req = Request(
                        f"{DRIVE_UPLOAD_URL}?uploadType=multipart&fields=id",
                        data=body,
                        headers={
                            **self._api_headers(),
                            "Content-Type": f"multipart/related; boundary={boundary}",
                        },
                    )
                    resp = urlopen(req, timeout=30, context=_ssl_ctx)
                    result = json.loads(resp.read().decode("utf-8"))
                    self._file_id = result.get("id")

                ts = time.strftime("%H:%M:%S")
                Clock.schedule_once(
                    lambda dt: self._set_status(f"Saved {ts}"), 0
                )
                if on_done:
                    Clock.schedule_once(lambda dt: on_done(True, "Saved!"), 0)

            except Exception as exc:
                err = str(exc)
                _log.info("[CloudSave] Upload error: %s", exc)
                Clock.schedule_once(
                    lambda dt: self._set_status("Upload failed"), 0
                )
                if on_done:
                    Clock.schedule_once(lambda dt, e=err: on_done(False, e), 0)

        threading.Thread(target=_do_upload, daemon=True).start()

    def download_save(self, on_done=None):
        """Download save from Drive."""
        if not self._initialized or not self._token:
            if on_done:
                on_done(False, "Not connected")
            return

        def _do_download():
            try:
                file_id = self._find_save_file()
                if not file_id:
                    if on_done:
                        Clock.schedule_once(
                            lambda dt: on_done(False, "No cloud save found"), 0
                        )
                    return

                req = Request(
                    f"{DRIVE_FILES_URL}/{file_id}?alt=media",
                    headers=self._api_headers(),
                )
                resp = urlopen(req, timeout=30, context=_ssl_ctx)
                data = json.loads(resp.read().decode("utf-8"))

                ts = time.strftime("%H:%M:%S")
                Clock.schedule_once(
                    lambda dt: self._set_status(f"Loaded {ts}"), 0
                )
                if on_done:
                    Clock.schedule_once(lambda dt, d=data: on_done(True, d), 0)

            except Exception as exc:
                err = str(exc)
                _log.info("[CloudSave] Download error: %s", exc)
                Clock.schedule_once(
                    lambda dt: self._set_status("Download failed"), 0
                )
                if on_done:
                    Clock.schedule_once(lambda dt, e=err: on_done(False, e), 0)

        threading.Thread(target=_do_download, daemon=True).start()

    def sign_out(self, on_done=None):
        """Sign out of Google account."""
        if platform != "android" or not self._java or not self._gso:
            self._token = None
            self._initialized = False
            self.user_email = ""
            self.last_sync_status = "Sign-in required"
            if on_done:
                on_done()
            return
        try:
            GoogleSignIn = self._java["GoogleSignIn"]
            activity = self._java["PythonActivity"].mActivity
            client = GoogleSignIn.getClient(activity, self._gso)
            client.signOut()
        except Exception as exc:
            _log.info("[CloudSave] Sign-out error: %s", exc)
        self._token = None
        self._initialized = False
        self._file_id = None
        self.user_email = ""
        self.last_sync_status = "Sign-in required"
        if on_done:
            Clock.schedule_once(lambda dt: on_done(), 0)

    @property
    def is_connected(self):
        return self._initialized


# Singleton
cloud_save_manager = CloudSaveManager()
