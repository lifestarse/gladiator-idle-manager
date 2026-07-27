# Build: 15
"""GameEngine core — construction + data wiring. Inherits mixins.

Events/lifecycle methods live in coreeventsmixin.py / corelifecyclemixin.py;
this module keeps __init__ so the full engine state inventory stays in one
place.
"""
import threading

from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module
from game.scripting import ScriptManager
from game.engine.coreeventsmixin import _CoreEventsMixin
from game.engine.corelifecyclemixin import _CoreLifecycleMixin
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


class GameEngine(
    _CoreEventsMixin, _CoreLifecycleMixin,
    _FightersMixin, _CombatMixin, _ForgeMixin, _ExpeditionsMixin,
    _HealingMixin, _ProgressionMixin, _EconomyMixin, _PersistenceMixin,
    _WiringMixin,
):
    def __init__(self, save_path=None):
        # Allow callers (tests, headless sims) to override. Default is computed
        # lazily so importing this module doesn't require Kivy.
        self.SAVE_PATH = save_path if save_path is not None else _default_save_path()

        # Cross-thread state guard. ScriptManager.run_on_demand_async runs
        # the interpreter on a daemon thread that mutates engine state; the
        # Kivy main thread mutates it from idle_tick / battle turns / save
        # snapshots. Both sides take this RLock around each state-touching
        # operation (interpreter ops on the worker side; idle_tick,
        # battle_* entry points and _build_save_data on the main side).
        # RLock because the synchronous trigger path (idle_tick → on_tick →
        # interpreter) re-enters on the same thread. UI button handlers
        # stay lock-free by design: they are single short engine calls, and
        # the automated high-frequency mutators are the race surface that
        # matters.
        self.state_lock = threading.RLock()

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
        self.shards = default_shards()

        # Notification queue — drained by UI layer each tick
        self.pending_notifications: list[str] = []

        # True only when load() finds no save file at all (brand-new
        # install). The App layer uses this to show a mandatory language
        # picker before the player sees anything else.
        self._is_first_launch = False
        # True when an existing save could not be read AND could not be
        # quarantined aside, or when external (cloud) data failed to apply.
        # save()/save_async() refuse to run while set, so a broken load can
        # never overwrite the player's real save file with fresh-start data.
        self._load_failed = False
        # Save-issue toast keys already shown this session (anti-spam;
        # see _PersistenceWriteMixin._notify_save_issue).
        self._save_issues_notified = set()
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
