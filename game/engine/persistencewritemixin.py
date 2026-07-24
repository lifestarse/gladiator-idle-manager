# Build: 10
"""GameEngine _PersistenceWriteMixin — save-to-disk + async save worker."""
import shutil
import threading

from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION


class _PersistenceWriteMixin:
    def _write_save_to_disk(self, data):
        """Serialize `data` and atomically replace the save file. I/O only;
        may be called from a background thread via save_async().

        Durability contract:
          * The primary file NEVER disappears. The backup is a COPY of the
            primary — earlier builds MOVED it (os.replace primary→.bak)
            before the final publish, leaving a kill-window with no primary
            on disk; load() then reported a fresh install and the player
            lost everything (persistencerecovery.py now also covers saves
            stranded by old builds).
          * The tmp file is flushed + fsync'd before the atomic os.replace,
            so a power cut cannot publish an empty/truncated primary.
          * A failed .bak copy is non-fatal (Windows lock contention): we
            lose one rotation cycle's backup, never the save itself.
          * os.replace (not os.rename) for the final step: on Windows
            os.rename raises WinError 183 when the target exists.
        """
        save_path = self.SAVE_PATH
        tmp_path = save_path + ".tmp"
        # encoding='utf-8' for symmetry with the read side (see
        # persistencerecovery.try_read_save for why that side needs it).
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(save_path):
            backup_path = save_path + ".bak"
            try:
                shutil.copyfile(save_path, backup_path)
            except OSError as exc:
                _log.debug("[ENGINE] backup rotation failed (non-fatal): %s", exc)
        os.replace(tmp_path, save_path)

    def _notify_save_issue(self, key):
        """Queue a user-visible toast for a save problem (App._idle_tick
        drains pending_notifications into show_toast).

        Once per key per session: a full disk would otherwise re-toast on
        every 30s autosave. May be called from the save worker thread —
        list.append is atomic under the GIL, and the worst race outcome is
        one duplicate toast.
        """
        notified = getattr(self, "_save_issues_notified", None)
        if notified is None:
            self._save_issues_notified = notified = set()
        if key in notified:
            return
        notified.add(key)
        self.pending_notifications.append(t(key))

    def save(self):
        # Don't overwrite real save with fresh-start data after failed load
        if getattr(self, '_load_failed', False):
            _log.warning("[ENGINE] save() BLOCKED — load had failed")
            self._notify_save_issue("save_blocked_toast")
            return {}
        # NOTE: _migrate_all_items is NOT called here. It replaces items in
        # inventory/equipment with fresh dicts (dict(template) + preserved
        # upgrade_level/enchantment). That detaches any open UI reference
        # (e.g. the forge upgrade button holds `w=item` in its closure) —
        # subsequent in-place upgrades then mutate a stale detached dict
        # while save() writes the new dict from inventory, losing the
        # latest change. Migration only happens on load().
        data = self._build_save_data()
        try:
            self._write_save_to_disk(data)
        except (OSError, TypeError, ValueError) as e:
            # Surface instead of crashing the caller — on_pause() runs
            # this, and an exception there kills the app mid-backgrounding.
            # The snapshot is still returned (cloud upload paths can use
            # it), but the user must learn the local write did not land.
            _log.exception("[ENGINE] save() failed: %s", e)
            self._notify_save_issue("save_failed_toast")
        return data

    def save_async(self, on_done=None):
        """Save without blocking the main thread.

        Snapshot assembly (fighter.to_dict, list copies) still runs on the
        caller's thread to avoid races with gameplay mutation, but the
        expensive bit — JSON serialization + atomic file write — runs on a
        daemon worker thread.

        Coalescing: if the user triggers save_async() rapidly (e.g. bulk
        IAP purchases), only the most recent snapshot is persisted. Older
        pending snapshots are dropped before they hit disk — no point
        writing state that's already stale, and it prevents the file-access
        collisions we saw when each call spawned its own thread.

        `on_done(ok)` (optional) is invoked on the worker thread when the
        write this particular call was queued for completes. If the call
        was coalesced away by a later save_async(), the prior callback is
        still fired with the outcome of the merged (latest) write.
        """
        if getattr(self, '_load_failed', False):
            self._notify_save_issue("save_blocked_toast")
            return
        data = self._build_save_data()

        if self._save_async_lock is None:
            # Double-checked; instance init can race on first call in theory,
            # but the lock only protects the pending slot / worker handle so
            # a single extra Lock() is harmless.
            self._save_async_lock = threading.Lock()

        with self._save_async_lock:
            # Chain callbacks if a save is already pending so every caller
            # hears back when their coalesced write lands.
            if self._save_async_pending is not None:
                prev_data, prev_cb = self._save_async_pending
                if prev_cb is not None and on_done is not None:
                    chained_prev = prev_cb
                    chained_new = on_done
                    def _both(ok, a=chained_prev, b=chained_new):
                        try: a(ok)
                        except Exception as e: _log.warning("[ENGINE] save cb: %s", e)
                        try: b(ok)
                        except Exception as e: _log.warning("[ENGINE] save cb: %s", e)
                    on_done = _both
                elif prev_cb is not None and on_done is None:
                    on_done = prev_cb
            self._save_async_pending = (data, on_done)

            worker = self._save_async_worker
            if worker is None or not worker.is_alive():
                self._save_async_worker = threading.Thread(
                    target=self._save_async_loop, daemon=True)
                self._save_async_worker.start()

    def _save_async_loop(self):
        """Worker: drains the pending slot until empty. Idle-exits so we
        don't keep a thread around forever when the user isn't saving."""
        while True:
            with self._save_async_lock:
                pending = self._save_async_pending
                self._save_async_pending = None
                if pending is None:
                    # No more work; clear worker handle so the next
                    # save_async spawns a fresh thread.
                    self._save_async_worker = None
                    return

            data, cb = pending
            ok = False
            try:
                self._write_save_to_disk(data)
                ok = True
            except Exception as e:
                _log.warning("[ENGINE] save_async failed: %s", e)
                self._notify_save_issue("save_failed_toast")

            if cb is not None:
                try:
                    cb(ok)
                except Exception as e:
                    _log.warning("[ENGINE] save_async on_done failed: %s", e)

    def get_save_data_json(self) -> str:
        return json.dumps(self.save())
