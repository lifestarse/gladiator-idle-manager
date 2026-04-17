# Build: 1
"""GameEngine core — lifecycle, tick, data wiring. Inherits mixins."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module
from game.engine._fighters import _FightersMixin
from game.engine._combat import _CombatMixin
from game.engine._forge import _ForgeMixin
from game.engine._expeditions import _ExpeditionsMixin
from game.engine._healing import _HealingMixin
from game.engine._progression import _ProgressionMixin
from game.engine._economy import _EconomyMixin
from game.engine._persistence import _PersistenceMixin


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


from .wiringmixin import _WiringMixin

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
        self.lore_unlocked: list[str] = []
        self.run_start_time = 0.0  # timestamp when current run started

        # Inventory: list of item dicts (unequipped equipment)
        self.inventory: list[dict] = []

        # Metal shards (expedition currency for weapon upgrades)
        self.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        # Notification queue — drained by UI layer each tick
        self.pending_notifications: list[str] = []

        # Dirty flags — batch achievement checks and UI refreshes.
        # Set by _mark_dirty() from state-changing methods; consumed by idle_tick.
        self._ach_dirty = False
        self._ui_dirty = True  # start dirty so first refresh runs

        # Battle history (persistent, survives permadeath)
        self.battle_log: list[dict] = []

        # Unified event log — all important game events
        self.event_log: list[dict] = []

        # Battle manager
        self.battle_mgr = BattleManager(self)

        # Mutators for current run
        self.active_mutators: list[str] = []

        # Monetization
        self.ads_removed = False

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
            total_kills=self.wins,
            strongest_gladiator_kills=self.best_record_kills,
            fastest_t15=self.fastest_t15_time,
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

    MAX_BATTLE_LOG_LINES = 1500

    BATTLE_LOG_HEAD = 750    # opening: setup, skill summaries, first blood

    BATTLE_LOG_TAIL = 749    # climax: kills, deaths, victory/defeat

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
        return exp_results

    _save_async_lock = None           # threading.Lock; lazy-init

    _save_async_pending = None        # (data_dict, on_done) | None

    _save_async_worker = None         # threading.Thread | None
