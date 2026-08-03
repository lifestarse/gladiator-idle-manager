# Build: 16
"""GameEngine _PersistenceReadMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION
from game.engine.persistencerecovery import quarantine_primary, read_save_with_fallback

# What a downloaded data_<lang>.json can throw at the translation overlay: a
# section of the wrong type (AttributeError, TypeError), a structure the
# overlay does not match (KeyError, IndexError, ValueError), or a file the
# device refuses to read (OSError).
TRANSLATION_OVERLAY_FAULTS = (AttributeError, TypeError, KeyError, IndexError,
                              ValueError, OSError)


class _PersistenceReadMixin:
    def load(self, data=None):
        from_disk = data is None
        if from_disk:
            # Candidate fallback (primary → .tmp → .bak) + quarantine of an
            # unreadable primary live in persistencerecovery. A missing
            # primary is NOT a fresh install if .tmp/.bak still hold the
            # player's progress — old builds' backup rotation could crash
            # in exactly that state.
            data, first_launch, load_failed = read_save_with_fallback(self.SAVE_PATH)
            self._is_first_launch = first_launch
            if load_failed:
                # Broken primary is still in place — save() must not
                # overwrite it (surfaced to the user as save_blocked_toast).
                self._load_failed = True
            if data is None:
                self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]
                self._spawn_enemy()
                return
        try:
            self._apply_save_data(data)
        except Exception as e:
            _log.exception(
                "[ENGINE] CRITICAL: load() failed: %s. Starting fresh.", e,
            )
            if from_disk:
                # Parsed but failed to apply — quarantine so the next save()
                # writes a clean file instead of leaving the user stuck in
                # read-only mode forever. If even the quarantine fails, the
                # broken file is still in place: block saves over it.
                if not quarantine_primary(self.SAVE_PATH):
                    self._load_failed = True
            else:
                # External data (cloud download). The on-disk save was never
                # touched and is very likely fine — never let the
                # half-applied fresh state below autosave over it.
                self._load_failed = True
            self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]
            self._spawn_enemy()

    def _apply_save_data(self, data):
        data = self._applysave_migrate(data)
        self._applysave_run_state(data)
        self._applysave_persistent_state(data)
        self._applysave_clamped_settings(data)
        self._applysave_counters(data)
        self._applysave_language(data)
        self._applysave_roster(data)
        self._applysave_scripts(data)

        self.battle_mgr = BattleManager(self)
        self.check_expeditions()
        self._spawn_enemy()

    def _applysave_migrate(self, data):
        # Schema migration: absent version = pre-versioning (v0).
        # Run registered migrations sequentially until we reach the current
        # schema. Keeps old saves loadable after format changes.
        version = data.get("schema_version", 0)
        if version > CURRENT_SAVE_VERSION:
            # Player downgraded the client (or save is from a future build).
            # We can't migrate backwards; fall through to .get() defaults and
            # warn so the user sees why some fields reset.
            _log.warning(
                "[ENGINE] save schema_version=%d newer than supported %d; "
                "loading with best-effort defaults.",
                version, CURRENT_SAVE_VERSION,
            )
        while version < CURRENT_SAVE_VERSION:
            migrate = _SAVE_MIGRATIONS.get(version)
            if migrate is None:
                break  # no migration registered — trust .get() defaults below
            data = migrate(data)
            version += 1
        return data

    def _applysave_run_state(self, data):
        self.last_saved_at = data.get("saved_at", 0.0)
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

    def _applysave_persistent_state(self, data):
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
        # Old saves default to False; on next purchase they'll fire the
        # In-App Review prompt (one-time). If the player already bought
        # things before this code shipped, they get one extra prompt.
        self._review_shown_after_first_purchase = data.get(
            "review_shown_after_first_purchase", False)
        self.active_mutators = data.get("active_mutators", [])

    def _applysave_clamped_settings(self, data):
        # Clamp to [0,1] — guard against tampered/corrupt saves writing
        # arbitrary floats that would saturate audio backends.
        try:
            vol = float(data.get("sound_volume", 1.0))
        except (TypeError, ValueError):
            vol = 1.0
        self.sound_volume = max(0.0, min(1.0, vol))
        # Snap to the allowed multiplier set — guard against tampered saves
        # writing arbitrary values that would race the battle Clock.
        try:
            speed = int(data.get("battle_speed", 1))
        except (TypeError, ValueError):
            speed = 1
        self.battle_speed = speed if speed in BATTLE_SPEED_OPTIONS else 1
        # Player account level. Saves written before the level system shipped
        # have no key and start at level 1 — features gate back on until the
        # player earns them (deliberate: "everyone from scratch").
        try:
            lvl = int(data.get("player_level", 1))
        except (TypeError, ValueError):
            lvl = 1
        self.player_level = max(1, min(PLAYER_MAX_LEVEL, lvl))
        try:
            pxp = int(data.get("player_xp", 0))
        except (TypeError, ValueError):
            pxp = 0
        self.player_xp = max(0, pxp)
        self.pending_level_ups = []

    def _applysave_counters(self, data):
        self.total_enchantments_applied = data.get("total_enchantments_applied", 0)
        self.total_enchantment_procs = data.get("total_enchantment_procs", 0)
        self.total_gold_spent_equipment = data.get("total_gold_spent_equipment", 0)
        self.total_injuries_healed = data.get("total_injuries_healed", 0)
        self.total_expeditions_completed = data.get("total_expeditions_completed", 0)
        self.completed_expedition_ids = data.get("completed_expedition_ids", [])
        self.cloud_sync_enabled = data.get("cloud_sync_enabled", False)
        self.lore_unlocked = data.get("lore_unlocked", [])

    def _applysave_language(self, data):
        saved_lang = data.get("language")
        if saved_lang:
            set_language(saved_lang)
        lang = saved_lang or get_language()
        if lang != "en":
            # Apply data-level translations (achievements, expeditions, etc.)
            # from data/languages/data_{lang}.json, then re-wire so models
            # see the translated names/descs.
            #
            # The file is downloaded content, so its shape is not this build's
            # to guarantee. Anything raising here would reach load()'s blanket
            # handler and QUARANTINE a healthy save — the price of a bad pack
            # must be English game text, never the player's run. Same reason
            # the font lookup in localization._apply_language_font is guarded.
            try:
                data_loader.apply_translations(lang)
            except TRANSLATION_OVERLAY_FAULTS as exc:
                _log.warning(
                    "[ENGINE] translation overlay for %r failed, keeping "
                    "English game text: %s", lang, exc)
            self._wire_data()

    def _applysave_roster(self, data):
        self.inventory = data.get("inventory", [])
        shards_raw = data.get("shards", {})
        self.shards = default_shards()
        if isinstance(shards_raw, dict) and shards_raw:
            try:
                self.shards = {int(k): v for k, v in shards_raw.items()}
            except (ValueError, TypeError):
                _log.warning("[ENGINE] Corrupted shard keys, resetting to defaults")
        elif shards_raw:
            # Tampered saves can store anything here (list, string, …); an
            # exception escaping _apply_save_data would make load() wipe the
            # whole state and quarantine the save, so degrade to defaults.
            _log.warning(
                "[ENGINE] Corrupted shards (%s), resetting to defaults",
                type(shards_raw).__name__)
        fighters_data = data.get("fighters", [])
        self.fighters = [Fighter.from_dict(fd) for fd in fighters_data]
        # Refresh all items from JSON templates (updates stats from data files)
        self._migrate_all_items()
        if not self.fighters or not any(f.alive for f in self.fighters):
            self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]

    def _applysave_scripts(self, data):
        # Squad scripting — load programs + persistent globals (missing key → empty).
        # Legacy saves without "scripts" get the built-in example seeded once.
        try:
            from game.scripting import ScriptManager
            self.scripts = ScriptManager.from_dict(data.get("scripts"))
        except Exception as e:
            _log.warning("[ENGINE] failed to load scripts, starting fresh: %s", e)
            from game.scripting import ScriptManager
            self.scripts = ScriptManager()
        self.scripts.seed_examples_if_needed()
