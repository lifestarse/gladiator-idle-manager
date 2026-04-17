# Build: 1
"""_PersistenceMixin _PersistenceReadMixin."""
# Build: 1
"""GameEngine _PersistenceMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION


from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION

class _PersistenceReadMixin:
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
