# Build: 1
"""CloudSaveManager core."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log
from .cloudauthmixin import _CloudAuthMixin
from .cloudiomixin import _CloudIOMixin


class CloudSaveManager(_CloudAuthMixin, _CloudIOMixin):
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

    def _set_status(self, status):
        self.last_sync_status = status

    def _api_headers(self):
        return {"Authorization": f"Bearer {self._token}"}
