# Build: 12
"""GameEngine core — lifecycle, tick, data wiring. Inherits mixins."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module
from game.scripting import ScriptManager
from game.engine._fighters import _FightersMixin
from game.engine._combat import _CombatMixin
from game.engine._forge import _ForgeMixin
from game.engine._expeditions import _ExpeditionsMixin
from game.engine._healing import _HealingMixin
from game.engine._progression import _ProgressionMixin
from game.engine._economy import _EconomyMixin
from game.engine._persistence import _PersistenceMixin
from game.engine.wiringmixin import _WiringMixin


def _default_save_path():
    """Default save location. Kept lazy so engine.py can be imported headless."""
    try:
        from kivy.utils import platform
    except ImportError:
        return os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")
    if platform == "android":
        from android.storage import app_storage_path  # noqa
        return os.path.join(app_storage_path(), ".gladiator_idle_save.json")
    return os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")


class GameEngine(_FightersMixin, _CombatMixin, _ForgeMixin, _ExpeditionsMixin, _HealingMixin, _ProgressionMixin, _EconomyMixin, _PersistenceMixin, _WiringMixin):
    def __init__(self, save_path=None):
        # Allow callers (tests, headless sims) to override. Default is computed
        # lazily so importing this module doesn't require Kivy.
        self.SAVE_PATH = save_path if save_path is not None else _default_save_path()
        # --- Load data from JSON files ---
        data_loader.load_all()
        self._wire_data()

        # --- Run state (resets on permadeath) ---
        self.gold = STARTING_GOLD
        self.fighters: list[Fighter] = []
        self.active_fighter_idx = 0
        self.arena_tier = 1
        self.wins = 0
        self.total_wins = 0
        self.total_deaths = 0
        self.graveyard: list[dict] = []
        self.current_enemy: Enemy | None = None  # first preview enemy
        self.preview_enemies: list[Enemy] = []
        self._revenge_common: list[Enemy] = []  # survivors from lost common fight
        self._revenge_boss: list[Enemy] = []    # survivor boss from lost boss fight
        self.expedition_log: list[str] = []
        self.surgeon_uses = 0
        self.total_gold_earned = 0.0

        # --- Run tracking ---
        self.run_number = 1
        self.run_kills = 0
        self.run_max_tier = 1

        # --- Persistent (survive permadeath) ---
        self.best_record_tier = 0
        self.best_record_kills = 0
        self.total_runs = 0
        self.diamonds = 0
        self.achievements_unlocked: list[str] = []
        self.bosses_killed = 0
        self.story_chapter = 0
        self.quests_completed: list[str] = []
        self.tutorial_shown: list[str] = []
        self.extra_expedition_slots = 0
        self.fastest_t15_time = 0  # seconds, 0 = not achieved

        # Achievement counters (persistent, survive permadeath)
        self.total_enchantments_applied = 0
        self.total_enchantment_procs = 0
        self.total_gold_spent_equipment = 0
        self.total_injuries_healed = 0
        self.total_expeditions_completed = 0
        # Distinct expedition ids ever completed alive (for
        # expedition_completed_specific achievements; locale-independent).
        self.completed_expedition_ids: list[str] = []
        self.lore_unlocked: list[str] = []
        self.run_start_time = 0.0  # timestamp when current run started

        # Inventory: list of item dicts (unequipped equipment)
        self.inventory: list[dict] = []

        # Metal shards (expedition currency for weapon upgrades)
        self.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        # Notification queue — drained by UI layer each tick
        self.pending_notifications: list[str] = []

        # True only when load() finds no save file at all (brand-new
        # install). The App layer uses this to show a mandatory language
        # picker before the player sees anything else.
        self._is_first_launch = False
        # Wall-clock time of the newest save this engine state descends
        # from (stamped on save, restored on load). 0.0 = never saved.
        self.last_saved_at = 0.0
        # Persisted: this device/save has been consciously synced to the
        # cloud at least once (adopted the cloud save, or manual up/down).
        # When True, autosave resumes streaming to the cloud on every
        # launch. A fresh install starts False, so it can never clobber a
        # real cloud save with an empty one. See [[gladiator-cloud-sync-incident]].
        self.cloud_sync_enabled = False

        # Dirty flags — batch achievement checks and UI refreshes.
        # Set by _mark_dirty() from state-changing methods; consumed by idle_tick.
        self._ach_dirty = False
        self._ui_dirty = True  # start dirty so first refresh runs

        # Battle history (persistent, survives permadeath)
        self.battle_log: list[dict] = []

        # Unified event log — all important game events
        self.event_log: list[dict] = []

        # Battle-end subscribers: callables(result, participants, skipped)
        self._battle_end_subscribers: list = []

        # Battle manager
        self.battle_mgr = BattleManager(self)

        # Mutators for current run
        self.active_mutators: list[str] = []

        # Monetization
        self.ads_removed = False

        # In-app review trigger — fires once, after the user's first
        # successful forge purchase. Tracked here so a re-install with
        # a restored save doesn't re-prompt (Play Core also rate-limits
        # internally, but we want to be polite at our layer too).
        self._review_shown_after_first_purchase = False
        # App-level subscribers (set in game/app on startup): callables()
        # invoked once when the flag flips False -> True.
        self._on_first_purchase_subscribers: list = []

        # Audio settings — global sound volume (0.0..1.0). Read by
        # game/screens/shared.py::_play_hit_sound, set from the More tab slider.
        self.sound_volume = 1.0

        # Stamina/fatigue + injury auto-heal: drive off battle_end events.
        self.subscribe_battle_end(self._on_battle_end_stamina_fatigue)

        # Squad scripting (rule processor with variables, loops, conditions).
        # Subscribed AFTER stamina/fatigue so scripts see post-battle state.
        self.scripts = ScriptManager()
        # Seed the built-in example program("bench tired") for brand-new
        # engines (no save). The seeding flag is persisted, so existing
        # players who delete/edit it never see it re-appear.
        self.scripts.seed_examples_if_needed()
        self.subscribe_battle_end(self._on_battle_end_scripts)

    def subscribe_first_purchase(self, cb) -> None:
        """Register a no-arg callable to fire once on the player's first
        successful forge purchase. Used by the App layer to trigger the
        Play In-App Review prompt without dragging pyjnius into engine."""
        if cb not in self._on_first_purchase_subscribers:
            self._on_first_purchase_subscribers.append(cb)

    def _maybe_emit_first_purchase(self) -> None:
        """Forge methods call this after a successful purchase. Idempotent:
        only the first call (when the flag is still False) fires
        subscribers and flips the flag. Subsequent purchases are no-ops."""
        if self._review_shown_after_first_purchase:
            return
        self._review_shown_after_first_purchase = True
        for cb in list(self._on_first_purchase_subscribers):
            try:
                cb()
            except Exception as exc:
                _log.warning("[engine] first-purchase subscriber failed: %s", exc)

    def _on_battle_end_scripts(self, result, participants, skipped):
        # Re-entrancy guard: a script reacting to on_battle_end can call
        # start_arena_battle, which (via builtins._start_arena_battle's
        # battle_skip) resolves the new battle synchronously and fires
        # _emit_battle_end again from inside our own callback. Without this
        # guard, a "farm to X gold" pattern would recurse straight into a
        # RecursionError instead of farming one battle per natural Arena tick.
        # With the guard, scripted battles fire-and-forget: the inner battle
        # still resolves (gold/wins/loss recorded), but its on_battle_end
        # event is swallowed so we don't pile programs on top of each other.
        if getattr(self, "_on_battle_end_running", False):
            return
        self._on_battle_end_running = True
        try:
            self.scripts.on_battle_end(self)
        except Exception as e:
            _log.exception("[ENGINE] scripts.on_battle_end failed: %s", e)
        finally:
            self._on_battle_end_running = False

    @staticmethod
    def _on_battle_end_stamina_fatigue(result, participants, skipped):
        for f in participants:
            if f.alive:
                f.apply_battle_fought()
        for f in skipped:
            if f.alive:
                f.apply_battle_skipped()

    def subscribe_battle_end(self, callback):
        """Register callback(result, participants, skipped) fired once per arena battle end.

        skipped = roster fighters that did not participate (benched, on
        expedition, dead, or simply not chosen for this fight).
        """
        self._battle_end_subscribers.append(callback)

    def _emit_battle_end(self, result):
        participants = list(result.player_fighters)
        participant_ids = {id(f) for f in participants}
        skipped = [f for f in self.fighters if id(f) not in participant_ids]
        for cb in self._battle_end_subscribers:
            cb(result, participants, skipped)

    def _log_event(self, event_type: str, **data):
        """Append an event to the unified event log."""
        import time as _time
        self.event_log.append({
            "t": int(_time.time()),
            "type": event_type,
            **data,
        })
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]

    def submit_scores(self):
        """Submit all leaderboard scores from current engine state."""
        from game.leaderboard import leaderboard_manager
        leaderboard_manager.submit_all(
            best_tier=max(self.best_record_tier, self.arena_tier),
            # Lifetime kills, not self.wins — wins is the per-run counter
            # (reset on roguelike reset), which turned the TOTAL_KILLS
            # board into "best single run".
            total_kills=self.total_wins,
            strongest_gladiator_kills=self.best_record_kills,
        )

    def roguelike_reset(self):
        """Full run reset on permadeath. Persistent stats survive."""
        # Update records
        if self.arena_tier > self.best_record_tier:
            self.best_record_tier = self.arena_tier
        if self.run_kills > self.best_record_kills:
            self.best_record_kills = self.run_kills
        self.total_runs += 1

        # Reset run state — full wipe including inventory
        self.gold = STARTING_GOLD
        self.inventory = []
        self.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        self.fighters = []
        self.active_fighter_idx = 0
        self.arena_tier = 1
        self.wins = 0
        self.current_enemy = None
        self.preview_enemies = []
        self._revenge_common = []
        self._revenge_boss = []
        self.expedition_log = []
        self.surgeon_uses = 0
        self.run_number += 1
        self.run_kills = 0
        self.run_max_tier = 1
        self.active_mutators = []
        self.run_start_time = time.time()

        # Reset battle
        self.battle_mgr = BattleManager(self)

        # Spawn fresh enemy
        self._spawn_enemy()

        self._mark_dirty()
        self.save()

    # Effectively unlimited — previous 1500-line head+tail truncation dropped
    # the middle of long battles. The detail view uses a RecycleView so even
    # 100k lines render fine (only visible rows are instantiated).
    MAX_BATTLE_LOG_LINES = 1_000_000

    BATTLE_LOG_HEAD = 500_000

    BATTLE_LOG_TAIL = 499_999

    @property
    def battle_active(self):
        return self.battle_mgr.is_active

    @property
    def pending_reset(self):
        return getattr(self, "_pending_reset", False)

    def execute_pending_reset(self):
        """Called by UI after showing defeat. Performs roguelike reset."""
        self._pending_reset = False
        self.roguelike_reset()

    def _mark_dirty(self):
        """Flag state as changed — defers achievement check + UI refresh to next tick."""
        self._ach_dirty = True
        self._ui_dirty = True

    def idle_tick(self, dt):
        exp_results = self.check_expeditions()
        # Batch: evaluate achievements at most once per idle tick
        if self._ach_dirty:
            self._ach_dirty = False
            self.check_achievements()
        # Squad scripts on_tick trigger (per-program interval gates inside).
        try:
            self.scripts.on_tick(self, dt)
        except Exception as e:
            _log.exception("[ENGINE] scripts.on_tick failed: %s", e)
        return exp_results

    _save_async_lock = None           # threading.Lock; lazy-init

    _save_async_pending = None        # (data_dict, on_done) | None

    _save_async_worker = None         # threading.Thread | None
