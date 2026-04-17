# Build: 1
"""GameEngine _PersistenceMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _PersistenceMixin:
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

    def load(self, data=None):
        if data is None:
            save_path = self.SAVE_PATH
            if not os.path.exists(save_path):
                self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]
                self._spawn_enemy()
                return
            try:
                with open(save_path, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                # Corrupted save — try backup
                backup_path = save_path + ".bak"
                if os.path.exists(backup_path):
                    try:
                        with open(backup_path, "r") as f:
                            data = json.load(f)
                    except (json.JSONDecodeError, ValueError):
                        data = None
                if not data:
                    self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]
                    self._spawn_enemy()
                    return
        try:
            self._apply_save_data(data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ENGINE] CRITICAL: load() failed: {e}. Backing up corrupt save and starting fresh.")
            # Move the corrupt save aside so the next save() writes a clean file
            # instead of leaving the user stuck in read-only mode forever.
            try:
                sp = self.SAVE_PATH
                if os.path.exists(sp):
                    corrupt_path = sp + ".corrupt"
                    if os.path.exists(corrupt_path):
                        os.remove(corrupt_path)
                    os.rename(sp, corrupt_path)
                    print(f"[ENGINE] Corrupt save moved to {corrupt_path}")
            except Exception as _bak_exc:
                print(f"[ENGINE] Could not back up corrupt save: {_bak_exc}")
            self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]
            self._spawn_enemy()

    def _apply_save_data(self, data):
        # Schema migration: absent version = pre-versioning (v0).
        # Run registered migrations sequentially until we reach the current
        # schema. Keeps old saves loadable after format changes.
        version = data.get("schema_version", 0)
        while version < CURRENT_SAVE_VERSION:
            migrate = _SAVE_MIGRATIONS.get(version)
            if migrate is None:
                break  # no migration registered — trust .get() defaults below
            data = migrate(data)
            version += 1

        self.gold = data.get("gold", 100)
        self.active_fighter_idx = data.get("active_fighter_idx", 0)
        self.arena_tier = data.get("arena_tier", 1)
        self.wins = data.get("wins", 0)
        self.total_wins = data.get("total_wins", 0)
        self.total_deaths = data.get("total_deaths", 0)
        self.graveyard = data.get("graveyard", [])
        self.expedition_log = data.get("expedition_log", [])
        self.battle_log = data.get("battle_log", [])
        self.event_log = data.get("event_log", [])
        self.surgeon_uses = data.get("surgeon_uses", 0)
        self.total_gold_earned = data.get("total_gold_earned", 0.0)

        # Run tracking
        self.run_number = data.get("run_number", 1)
        self.run_kills = data.get("run_kills", 0)
        self.run_max_tier = data.get("run_max_tier", 1)

        # Persistent
        self.best_record_tier = data.get("best_record_tier", 0)
        self.best_record_kills = data.get("best_record_kills", 0)
        self.total_runs = data.get("total_runs", 0)
        self.diamonds = data.get("diamonds", 0)
        self.achievements_unlocked = data.get("achievements_unlocked", [])
        self.bosses_killed = data.get("bosses_killed", 0)
        self.story_chapter = data.get("story_chapter", 0)
        self.quests_completed = data.get("quests_completed", [])
        self.tutorial_shown = data.get("tutorial_shown", [])
        self.extra_expedition_slots = data.get("extra_expedition_slots", 0)
        self.fastest_t15_time = data.get("fastest_t15_time", 0)
        self.run_start_time = data.get("run_start_time", 0.0)
        self.ads_removed = data.get("ads_removed", False)
        self.active_mutators = data.get("active_mutators", [])

        # Achievement counters
        self.total_enchantments_applied = data.get("total_enchantments_applied", 0)
        self.total_enchantment_procs = data.get("total_enchantment_procs", 0)
        self.total_gold_spent_equipment = data.get("total_gold_spent_equipment", 0)
        self.total_injuries_healed = data.get("total_injuries_healed", 0)
        self.total_expeditions_completed = data.get("total_expeditions_completed", 0)
        self.lore_unlocked = data.get("lore_unlocked", [])

        saved_lang = data.get("language")
        if saved_lang:
            set_language(saved_lang)
            # Apply data-level translations (achievements, expeditions, etc.)
            # from data/languages/data_{lang}.json, then re-wire so models
            # see the translated names/descs.
            data_loader.apply_translations(saved_lang)
            self._wire_data()

        self.inventory = data.get("inventory", [])
        shards_raw = data.get("shards", {})
        if shards_raw:
            try:
                self.shards = {int(k): v for k, v in shards_raw.items()}
            except (ValueError, TypeError):
                _log.warning("[ENGINE] Corrupted shard keys, resetting to defaults")
                self.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        else:
            self.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        fighters_data = data.get("fighters", [])
        self.fighters = [Fighter.from_dict(fd) for fd in fighters_data]
        # Refresh all items from JSON templates (updates stats from data files)
        self._migrate_all_items()
        if not self.fighters or not any(f.alive for f in self.fighters):
            self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]

        self.battle_mgr = BattleManager(self)
        self.check_expeditions()
        self._spawn_enemy()

    def get_save_data_json(self) -> str:
        return json.dumps(self.save())
