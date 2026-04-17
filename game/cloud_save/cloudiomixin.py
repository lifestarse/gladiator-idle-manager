# Build: 1
"""CloudSaveManager _CloudIOMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _log


class _CloudIOMixin:
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
