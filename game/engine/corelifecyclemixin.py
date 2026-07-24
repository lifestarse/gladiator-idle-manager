# Build: 1
"""GameEngine _CoreLifecycleMixin — roguelike reset, idle tick, dirty flags."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _CoreLifecycleMixin:
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
