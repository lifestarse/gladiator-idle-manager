# Build: 1
"""_PersistenceMixin _PersistenceWriteMixin."""
# Build: 1
"""GameEngine _PersistenceMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION


from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION

class _PersistenceWriteMixin:
    def _build_save_data(self):
        """Assemble the save-state dict. Main-thread-safe; no I/O.

        Split out so `save` can serialize synchronously and `save_async`
        can ship the dict off to a background thread for the expensive
        JSON dump + disk write. Both paths must see an identical state
        snapshot, so we eagerly flatten mutable structures here.
        """
        return {
            "schema_version": CURRENT_SAVE_VERSION,
            "gold": self.gold,
            "active_fighter_idx": self.active_fighter_idx,
            "arena_tier": self.arena_tier,
            "wins": self.wins,
            "total_wins": self.total_wins,
            "total_deaths": self.total_deaths,
            "graveyard": self.graveyard,
            "fighters": [f.to_dict() for f in self.fighters],
            "expedition_log": self.expedition_log[-20:],
            # Shallow-copy each battle entry so a concurrent write to the
            # original during a background save can't corrupt the snapshot.
            # Also trims legacy oversize logs inline.
            "battle_log": [
                self._trim_battle_log_entry(entry)
                for entry in self.battle_log[-200:]
            ],
            "event_log": self.event_log[-200:],
            "surgeon_uses": self.surgeon_uses,
            "total_gold_earned": self.total_gold_earned,
            "run_number": self.run_number,
            "run_kills": self.run_kills,
            "run_max_tier": self.run_max_tier,
            "best_record_tier": self.best_record_tier,
            "best_record_kills": self.best_record_kills,
            "total_runs": self.total_runs,
            "diamonds": self.diamonds,
            "achievements_unlocked": self.achievements_unlocked,
            "bosses_killed": self.bosses_killed,
            "story_chapter": self.story_chapter,
            "quests_completed": self.quests_completed,
            "tutorial_shown": self.tutorial_shown,
            "extra_expedition_slots": self.extra_expedition_slots,
            "fastest_t15_time": self.fastest_t15_time,
            "run_start_time": self.run_start_time,
            "ads_removed": self.ads_removed,
            "active_mutators": self.active_mutators,
            "inventory": self.inventory,
            "shards": self.shards,
            "language": get_language(),
            "total_enchantments_applied": self.total_enchantments_applied,
            "total_enchantment_procs": self.total_enchantment_procs,
            "total_gold_spent_equipment": self.total_gold_spent_equipment,
            "total_injuries_healed": self.total_injuries_healed,
            "total_expeditions_completed": self.total_expeditions_completed,
            "lore_unlocked": self.lore_unlocked,
        }

    def _write_save_to_disk(self, data):
        """Serialize `data` and atomically replace the save file. I/O only;
        may be called from a background thread via save_async()."""
        save_path = self.SAVE_PATH
        tmp_path = save_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        if os.path.exists(save_path):
            backup_path = save_path + ".bak"
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(save_path, backup_path)
            except OSError:
                pass
        os.rename(tmp_path, save_path)

    def save(self):
        # Don't overwrite real save with fresh-start data after failed load
        if getattr(self, '_load_failed', False):
            print(f"[ENGINE] save() BLOCKED — load had failed")
            return {}
        # NOTE: _migrate_all_items is NOT called here. It replaces items in
        # inventory/equipment with fresh dicts (dict(template) + preserved
        # upgrade_level/enchantment). That detaches any open UI reference
        # (e.g. the forge upgrade button holds `w=item` in its closure) —
        # subsequent in-place upgrades then mutate a stale detached dict
        # while save() writes the new dict from inventory, losing the
        # latest change. Migration only happens on load().
        data = self._build_save_data()
        self._write_save_to_disk(data)
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
            return
        data = self._build_save_data()

        import threading
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
                        except Exception as e: print(f"[ENGINE] save cb: {e}")
                        try: b(ok)
                        except Exception as e: print(f"[ENGINE] save cb: {e}")
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
                print(f"[ENGINE] save_async failed: {e}")

            if cb is not None:
                try:
                    cb(ok)
                except Exception as e:
                    print(f"[ENGINE] save_async on_done failed: {e}")

    def get_save_data_json(self) -> str:
        return json.dumps(self.save())
