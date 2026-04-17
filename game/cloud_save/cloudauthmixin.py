# Build: 1
"""CloudSaveManager _CloudAuthMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log


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
