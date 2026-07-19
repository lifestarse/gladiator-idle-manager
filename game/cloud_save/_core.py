# Build: 4
"""CloudSaveManager core."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log
from .cloudauthmixin import _CloudAuthMixin
from .cloudiomixin import _CloudIOMixin


def resolve_auto_sync(engine, cloud_data) -> str:
    """Decide what the SILENT startup auto-sync may do. Returns "load" | "skip".

    Hard rule: automatic sync NEVER overwrites either side without the
    user's consent. The only automatic action is pulling the cloud save
    onto a device that has nothing to lose — a fresh install / reinstall
    with no local save. In every other case we do nothing and leave both
    copies intact; conflicts are resolved explicitly (login confirmation
    or the manual Upload / Download buttons).

    Why not "upload when local is newer": a fresh install has a newer
    saved_at than a real cloud save, so timestamp-newness is NOT progress.
    Auto-uploading on that basis destroys the real cloud save. That is the
    exact bug this function used to cause; it must never upload.
    """
    if getattr(engine, "_is_first_launch", False):
        return "load"
    return "skip"


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
        # Continuous 30s autosave uploads stay OFF until the user has
        # consciously synced this device (adopted the cloud save, or used
        # the manual Upload/Download button). Being merely signed in must
        # NOT let a fresh/lesser local save stream up over a real cloud
        # save — that is what silently destroyed progress before.
        self.autosync_uploads = False

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
            _log.info("[CloudSave] Google Play Services classes loaded")

            # Build GSO on main thread
            self._gso = self._build_gso()

            # Check last signed-in account (main thread)
            self._check_existing_account()
        except Exception as exc:
            _log.info("[CloudSave] Google Play Services not available: %s", exc)
            self.last_sync_status = "Not available"

    def enable_autosync_uploads(self):
        """Arm continuous autosave→cloud uploads. Call ONLY from a path
        where the user consciously chose to sync this device (adopted the
        cloud save, kept-and-uploaded local, or hit the manual buttons)."""
        self.autosync_uploads = True

    def _set_status(self, status):
        self.last_sync_status = status

    def _api_headers(self):
        return {"Authorization": f"Bearer {self._token}"}
