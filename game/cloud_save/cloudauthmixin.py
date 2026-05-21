# Build: 5
"""CloudSaveManager _CloudAuthMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log, _mask_email, classify_signin_error
from game.common import poll_signed_in_account


class _CloudAuthMixin:
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
                # Show "Connecting..." while OAuth token is fetched — otherwise
                # the More screen displays the stale "Not connected" default
                # for several seconds during the background token fetch.
                self.last_sync_status = "Connecting..."
                # Get token in background (only uses GoogleAuthUtil — already loaded)
                threading.Thread(
                    target=self._fetch_token, args=(account,), daemon=True
                ).start()
            else:
                self.last_sync_status = "Sign-in required"
        except Exception as exc:
            _log.info("[CloudSave] Account check failed: %s", exc)
            self.last_sync_status = "Sign-in required"

    def _fetch_token(self, account, on_success=None, on_failure=None):
        """Get OAuth2 token (background thread — only uses pre-loaded classes)."""
        try:
            GoogleAuthUtil = self._java["GoogleAuthUtil"]
            activity = self._java["PythonActivity"].mActivity
            scope = "oauth2:https://www.googleapis.com/auth/drive.appdata"
            token = GoogleAuthUtil.getToken(activity, account.getAccount(), scope)
            self._token = token
            self._initialized = True
            email = account.getEmail() or ""
            _log.info("[CloudSave] Got auth token for %s", _mask_email(email))
            if on_success:
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt: on_success(), 0)
            Clock.schedule_once(lambda dt: self._set_status("Connected"), 0)
            if self.on_auto_connected:
                Clock.schedule_once(lambda dt: self.on_auto_connected(), 0.5)
        except Exception as exc:
            err_key = classify_signin_error(exc)
            _log.info("[CloudSave] Token error (%s): %s", err_key, exc)
            Clock.schedule_once(
                lambda dt: self._set_status("Token error"), 0
            )
            if on_failure:
                Clock.schedule_once(lambda dt: on_failure(err_key), 0)

    def sign_in(self, on_success=None, on_failure=None):
        """Start interactive Google Sign-In (main thread for intent, bg for token)."""
        if platform != "android" or not self._java or not self._gso:
            if on_failure:
                on_failure("cloud_err_unavailable")
            return

        if self._signing_in:
            if on_failure:
                on_failure("cloud_err_in_progress")
            return
        self._signing_in = True

        try:
            GoogleSignIn = self._java["GoogleSignIn"]
            activity = self._java["PythonActivity"].mActivity
            client = GoogleSignIn.getClient(activity, self._gso)

            # Launch sign-in intent (non-blocking, on main thread)
            sign_in_intent = client.getSignInIntent()
            activity.startActivityForResult(sign_in_intent, 9001)

            def _on_found(acc):
                self.user_email = acc.getEmail() or ""
                self._signing_in = False
                threading.Thread(
                    target=self._fetch_token,
                    args=(acc, on_success, on_failure),
                    daemon=True,
                ).start()

            def _on_timeout():
                # Polling timed out without an account appearing. Most common
                # cause is the user dismissing the picker; less commonly a
                # silent failure inside Play Services. We can't tell apart
                # without onActivityResult, so report cancellation and let
                # the user retry.
                self._signing_in = False
                self._set_status("Sign-in cancelled")
                if on_failure:
                    on_failure("cloud_err_cancelled")

            poll_signed_in_account(
                google_sign_in=GoogleSignIn, activity=activity,
                on_found=_on_found, on_timeout=_on_timeout,
                label="CloudSave",
            )

        except Exception as exc:
            self._signing_in = False
            err_key = classify_signin_error(exc)
            _log.info("[CloudSave] Sign-in error (%s): %s", err_key, exc)
            self.last_sync_status = "Sign-in failed"
            if on_failure:
                on_failure(err_key)

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
