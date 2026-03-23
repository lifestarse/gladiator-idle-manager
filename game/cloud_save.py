"""
Google Drive cloud save module.

Flow:
1. User signs in with Google (via oauth2)
2. Save: upload JSON to appDataFolder on Google Drive
3. Load: download latest save from appDataFolder
4. Sync: compare timestamps, use newest

Setup for Android:
- Enable Google Drive API in Google Cloud Console
- Add google-services.json to your buildozer project
- pip install google-auth google-auth-oauthlib google-api-python-client

The appDataFolder is a hidden folder only your app can access.
"""

import json
import os
import time
from kivy.utils import platform

# Save file name on Google Drive
CLOUD_SAVE_FILENAME = "gladiator_idle_save.json"

# OAuth2 scopes needed
SCOPES = ["https://www.googleapis.com/auth/drive.appdata"]

# Client ID — replace with your own from Google Cloud Console
CLIENT_ID = "YOUR_CLIENT_ID.apps.googleusercontent.com"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"


class CloudSaveManager:
    """Google Drive cloud save using appDataFolder."""

    def __init__(self):
        self._service = None
        self._credentials = None
        self._initialized = False
        self._file_id = None  # Drive file ID of the save
        self.last_sync_status = "Not connected"

    def init(self):
        """Initialize Google Drive API. Must be called after Google Sign-In."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            # Check for stored credentials
            token_path = os.path.join(
                os.path.expanduser("~"), ".gladiator_drive_token.json"
            )

            if os.path.exists(token_path):
                self._credentials = Credentials.from_authorized_user_file(
                    token_path, SCOPES
                )
                if self._credentials and self._credentials.valid:
                    self._service = build("drive", "v3",
                                          credentials=self._credentials)
                    self._initialized = True
                    self.last_sync_status = "Connected"
                    print("[CloudSave] Connected to Google Drive")
                    return True

            self.last_sync_status = "Sign-in required"
            return False

        except ImportError:
            print("[CloudSave] google-api-python-client not installed")
            self.last_sync_status = "Not available"
            return False
        except Exception as e:
            print(f"[CloudSave] Init error: {e}")
            self.last_sync_status = f"Error: {e}"
            return False

    def sign_in(self, on_success=None, on_failure=None):
        """
        Start Google OAuth2 sign-in flow.
        On Android, uses Google Sign-In SDK.
        On desktop, uses local server flow.
        """
        try:
            if platform == "android":
                self._android_sign_in(on_success, on_failure)
            else:
                self._desktop_sign_in(on_success, on_failure)
        except Exception as e:
            self.last_sync_status = f"Sign-in failed: {e}"
            if on_failure:
                on_failure(str(e))

    def _desktop_sign_in(self, on_success, on_failure):
        """OAuth2 flow for desktop testing."""
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                SCOPES,
            )
            self._credentials = flow.run_local_server(port=0)

            # Save token
            token_path = os.path.join(
                os.path.expanduser("~"), ".gladiator_drive_token.json"
            )
            with open(token_path, "w") as f:
                f.write(self._credentials.to_json())

            from googleapiclient.discovery import build
            self._service = build("drive", "v3",
                                  credentials=self._credentials)
            self._initialized = True
            self.last_sync_status = "Connected"

            if on_success:
                on_success()

        except Exception as e:
            self.last_sync_status = f"Sign-in failed: {e}"
            if on_failure:
                on_failure(str(e))

    def _android_sign_in(self, on_success, on_failure):
        """Google Sign-In on Android via pyjnius."""
        try:
            from jnius import autoclass
            # Use Android GoogleSignIn API
            # This requires google-services.json in your project
            print("[CloudSave] Android sign-in — implement with GoogleSignIn SDK")
            # Placeholder — full implementation needs Activity result handling
            if on_failure:
                on_failure("Android sign-in not yet configured")
        except Exception as e:
            if on_failure:
                on_failure(str(e))

    def upload_save(self, save_data: dict, on_done=None):
        """Upload save to Google Drive appDataFolder."""
        if not self._initialized or not self._service:
            self.last_sync_status = "Not connected"
            if on_done:
                on_done(False, "Not connected")
            return

        try:
            from googleapiclient.http import MediaInMemoryUpload

            content = json.dumps(save_data).encode("utf-8")
            media = MediaInMemoryUpload(content, mimetype="application/json")

            # Check if file already exists
            self._find_save_file()

            if self._file_id:
                # Update existing
                self._service.files().update(
                    fileId=self._file_id,
                    media_body=media,
                ).execute()
            else:
                # Create new
                metadata = {
                    "name": CLOUD_SAVE_FILENAME,
                    "parents": ["appDataFolder"],
                }
                result = self._service.files().create(
                    body=metadata,
                    media_body=media,
                    fields="id",
                ).execute()
                self._file_id = result.get("id")

            self.last_sync_status = f"Saved at {time.strftime('%H:%M:%S')}"
            if on_done:
                on_done(True, "Saved!")

        except Exception as e:
            self.last_sync_status = f"Upload failed: {e}"
            if on_done:
                on_done(False, str(e))

    def download_save(self, on_done=None):
        """
        Download save from Google Drive.
        on_done(success: bool, data: dict | str)
        """
        if not self._initialized or not self._service:
            if on_done:
                on_done(False, "Not connected")
            return

        try:
            self._find_save_file()
            if not self._file_id:
                if on_done:
                    on_done(False, "No cloud save found")
                return

            content = self._service.files().get_media(
                fileId=self._file_id
            ).execute()

            data = json.loads(content.decode("utf-8"))
            self.last_sync_status = f"Loaded at {time.strftime('%H:%M:%S')}"
            if on_done:
                on_done(True, data)

        except Exception as e:
            self.last_sync_status = f"Download failed: {e}"
            if on_done:
                on_done(False, str(e))

    def sync_save(self, local_data: dict, on_done=None):
        """
        Smart sync: compare local and cloud timestamps, use newest.
        on_done(action: str, data: dict | None)
          action: "uploaded" | "downloaded" | "no_change" | "error"
        """
        if not self._initialized:
            if on_done:
                on_done("error", None)
            return

        def _on_download(success, result):
            if not success:
                # No cloud save — upload local
                self.upload_save(local_data, lambda ok, msg:
                    on_done("uploaded", local_data) if on_done else None)
                return

            cloud_data = result
            local_time = local_data.get("last_save_time", 0)
            cloud_time = cloud_data.get("last_save_time", 0)

            if cloud_time > local_time:
                # Cloud is newer — use it
                self.last_sync_status = "Loaded from cloud"
                if on_done:
                    on_done("downloaded", cloud_data)
            else:
                # Local is newer — upload
                self.upload_save(local_data, lambda ok, msg:
                    on_done("uploaded", local_data) if on_done else None)

        self.download_save(_on_download)

    def _find_save_file(self):
        """Find existing save file ID in appDataFolder."""
        if self._file_id:
            return
        try:
            results = self._service.files().list(
                spaces="appDataFolder",
                q=f"name='{CLOUD_SAVE_FILENAME}'",
                fields="files(id, name)",
                pageSize=1,
            ).execute()
            files = results.get("files", [])
            if files:
                self._file_id = files[0]["id"]
        except Exception:
            pass

    @property
    def is_connected(self):
        return self._initialized


# Singleton
cloud_save_manager = CloudSaveManager()
