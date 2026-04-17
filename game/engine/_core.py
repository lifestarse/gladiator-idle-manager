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


class GameEngine(_FightersMixin, _CombatMixin, _ForgeMixin, _ExpeditionsMixin, _HealingMixin, _ProgressionMixin, _EconomyMixin, _PersistenceMixin):
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

    @staticmethod
    def _wire_data():
        """Override hardcoded module-level data in models.py with JSON data.

        Mutates dicts/lists IN-PLACE (.clear() + .update()/.extend()) rather
        than rebinding module attributes. This is required because
        game.models is now a package: submodules like game.models._fighter
        do `from ._data import *` which captures object references; in-place
        mutation keeps those references valid, rebinds would not.
        """
        import game.models as m
        dl = data_loader

        def _replace_list(lst, new_items):
            lst.clear()
            lst.extend(new_items)

        def _replace_dict(d, new_d):
            d.clear()
            d.update(new_d)

        GameEngine._template_by_id = {i["id"]: i for i in (
            dl.weapons + dl.armor + dl.accessories + dl.relics
        )} if (dl.weapons or dl.armor or dl.accessories or dl.relics) else {}
        if dl.fighter_names:
            _replace_list(m.FIGHTER_NAMES, dl.fighter_names)
        if dl.weapons:
            _replace_list(m.FORGE_WEAPONS, dl.weapons)
        if dl.armor:
            _replace_list(m.FORGE_ARMOR, dl.armor)
        if dl.accessories:
            _replace_list(m.FORGE_ACCESSORIES, dl.accessories)
        if dl.weapons or dl.armor or dl.accessories:
            _replace_list(m.ALL_FORGE_ITEMS,
                          m.FORGE_WEAPONS + m.FORGE_ARMOR + m.FORGE_ACCESSORIES)
        if dl.relics:
            rebuilt = {}
            for r in dl.relics:
                rebuilt.setdefault(r.get("rarity", "common"), []).append(r)
            _replace_dict(m.RELICS, rebuilt)
        if dl.enchantments:
            _replace_dict(m.ENCHANTMENT_TYPES, dl.enchantments)
        if dl.fighter_classes:
            _replace_dict(m.FIGHTER_CLASSES, dl.fighter_classes)
            m.Fighter.invalidate_perks_map_cache()
        if dl.mutators:
            mutator_registry.load(list(dl.mutators.values()))
        if dl.expeditions:
            _replace_list(m.EXPEDITIONS, dl.expeditions)
            _replace_dict(m.SHARD_TIERS, {
                e["id"]: {"tier": e["shard_tier"], "name": e["shard_name"]}
                for e in dl.expeditions if "shard_tier" in e
            })
        if dl.achievements_data:
            _ach_module.ACHIEVEMENTS = build_achievements_from_json(dl.achievements_data)

    @staticmethod
    def _find_template(item):
        """Find JSON template by id — O(1) via cached lookup dict."""
        iid = item.get("id")
        if iid:
            return getattr(GameEngine, '_template_by_id', {}).get(iid)
        return None

    @staticmethod
    def _migrate_item(item):
        """Refresh item from JSON template, preserving player data (upgrades, enchantments)."""
        if not item or not isinstance(item, dict):
            return item
        template = GameEngine._find_template(item)
        if template:
            upgrade_level = item.get("upgrade_level", 0)
            enchantment = item.get("enchantment")
            item = dict(template)
            item["upgrade_level"] = upgrade_level
            if enchantment:
                item["enchantment"] = enchantment
            return item
        return item

    def _migrate_all_items(self):
        """Migrate all inventory + fighter equipment to current JSON format."""
        self.inventory = [self._migrate_item(i) for i in self.inventory]
        for f in self.fighters:
            for slot in ("weapon", "armor", "accessory", "relic"):
                eq = f.equipment.get(slot)
                if eq:
                    f.equipment[slot] = self._migrate_item(eq)

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

    def check_t15_clear(self):
        """Record fastest T15 clear time if this is a new best.
        Called after boss victory; arena_tier is already incremented."""
        if self.arena_tier >= 15 and self.run_start_time > 0:
            elapsed = int(time.time() - self.run_start_time)
            if self.fastest_t15_time == 0 or elapsed < self.fastest_t15_time:
                self.fastest_t15_time = elapsed
                self.pending_notifications.append(
                    t("new_record_t15", time=self._fmt_time(elapsed))
                )

    @staticmethod
    def _fmt_time(seconds):
        """Format seconds as M:SS or H:MM:SS."""
        if seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d}"
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}:{m:02d}:{s:02d}"

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
