# Build: 52
"""Core game engine — roguelike manager with permadeath reset."""

import json
import logging
import math
import os
import random
import time

_log = logging.getLogger(__name__)

import game.models as _m
from game.models import (
    Fighter, Enemy, Boss, FIGHTER_CLASSES,
    DifficultyScaler, EQUIPMENT_SLOTS,
    get_upgrade_tier, item_display_name, get_max_upgrade,
    get_dynamic_shop_items, fmt_num, get_boss_name, Result,
)
from game.localization import t, get_language, set_language
from game.battle import BattleManager, BattlePhase
from game.achievements import ACHIEVEMENTS, DIAMOND_SHOP, DIAMOND_BUNDLES, build_achievements_from_json
import game.achievements as _ach_module
from game.constants import (
    STARTING_GOLD, RENAME_COST_DIAMONDS, EXPEDITION_SLOT_BASE_COST,
    HP_HEAL_TIER_MULT, HP_HEAL_DIVISOR, INJURY_HEAL_BASE_COST,
)
from game.story import TUTORIAL_STEPS, STORY_CHAPTERS, get_pending_tutorial
from game.data_loader import data_loader
from game.mutators import mutator_registry

def _get_save_path():
    from kivy.utils import platform
    if platform == "android":
        from android.storage import app_storage_path  # noqa
        return os.path.join(app_storage_path(), ".gladiator_idle_save.json")
    return os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")

SAVE_PATH = _get_save_path()


class GameEngine:

    def __init__(self):
        self.SAVE_PATH = SAVE_PATH  # instance-level, overridable for tests
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
        """Override hardcoded module-level data in models.py with JSON data."""
        import game.models as m
        dl = data_loader
        # Build O(1) lookup dict for _find_template (was O(130) linear scan)
        GameEngine._template_by_id = {i["id"]: i for i in (
            dl.weapons + dl.armor + dl.accessories
        )} if dl.weapons else {}
        if dl.fighter_names:
            m.FIGHTER_NAMES = dl.fighter_names
        if dl.weapons:
            m.FORGE_WEAPONS = dl.weapons
        if dl.armor:
            m.FORGE_ARMOR = dl.armor
        if dl.accessories:
            m.FORGE_ACCESSORIES = dl.accessories
        if dl.weapons or dl.armor or dl.accessories:
            m.ALL_FORGE_ITEMS = m.FORGE_WEAPONS + m.FORGE_ARMOR + m.FORGE_ACCESSORIES
        if dl.relics:
            # Rebuild RELICS dict grouped by rarity
            m.RELICS = {}
            for r in dl.relics:
                rarity = r.get("rarity", "common")
                m.RELICS.setdefault(rarity, []).append(r)
        if dl.enchantments:
            m.ENCHANTMENT_TYPES = dl.enchantments
        if dl.fighter_classes:
            m.FIGHTER_CLASSES = dl.fighter_classes
        if dl.mutators:
            mutator_registry.load(list(dl.mutators.values()))
        if dl.expeditions:
            m.EXPEDITIONS = dl.expeditions
            m.SHARD_TIERS = {
                e["id"]: {"tier": e["shard_tier"], "name": e["shard_name"]}
                for e in dl.expeditions if "shard_tier" in e
            }
        if dl.achievements_data:
            _ach_module.ACHIEVEMENTS = build_achievements_from_json(dl.achievements_data)

    # --- Item migration (old saves: atk/def/hp → str/agi/vit) ---

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

    # --- Roguelike reset ---

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

    # --- Properties ---


    # --- Fighter management ---

    def get_active_gladiator(self) -> Fighter | None:
        alive = [f for f in self.fighters if f.available]
        if not alive:
            return None
        self.active_fighter_idx = min(self.active_fighter_idx, len(self.fighters) - 1)
        f = self.fighters[self.active_fighter_idx]
        if f.available:
            return f
        for i, f in enumerate(self.fighters):
            if f.available:
                self.active_fighter_idx = i
                return f
        return None

    @property
    def hire_cost(self):
        alive_count = len([f for f in self.fighters if f.alive])
        if alive_count == 0:
            return 0
        return DifficultyScaler.hire_cost(alive_count)

    def hire_gladiator(self, fighter_class="mercenary"):
        """Hire a new fighter of given class."""
        cost = self.hire_cost
        if self.gold >= cost:
            self.gold -= cost
            f = Fighter(fighter_class=fighter_class)
            self.fighters.append(f)
            self._log_event("hire", name=f.name, cls=f.class_name, gold=cost)
            self._mark_dirty()
            return Result(True, t("recruited_msg", name=f.name, cls=f.class_name))
        return Result(False, t("need_gold", cost=fmt_num(cost)), "not_enough_gold")

    def upgrade_gladiator(self, index):
        if index >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[index]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        cost = f.upgrade_cost
        if self.gold >= cost:
            self.gold -= cost
            f.level_up()
            self._log_event("level_up", name=f.name, lv=f.level, gold=cost)
            self._mark_dirty()
            return Result(True, t("reached_level", name=f.name, lv=f.level, pts=f.points_per_level))
        return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")

    def distribute_stat(self, fighter_idx, stat_name):
        """Distribute 1 unused point to a stat."""
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if f.unused_points <= 0:
            return Result(False, t("no_unused_points"), "no_points")
        if f.distribute_point(stat_name):
            return Result(True, t("stat_distributed", name=f.name, stat=stat_name.upper(), pts=f.unused_points))
        return Result(False, "", "invalid")

    def unlock_perk(self, fighter_idx, perk_id):
        """Unlock a perk for a fighter. Returns Result."""
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if perk_id in f.unlocked_perks:
            return Result(False, t("perk_already_unlocked"), "already_unlocked")
        # Find perk in any class
        perk = None
        perk_class = None
        for cls_id, cls_data in _m.FIGHTER_CLASSES.items():
            for p in cls_data.get("perk_tree", []):
                if p["id"] == perk_id:
                    perk = p
                    perk_class = cls_id
                    break
            if perk:
                break
        if not perk:
            return Result(False, t("invalid_perk"), "invalid_perk")
        cost = perk["cost"]
        if perk_class != f.fighter_class:
            cost = int(cost * perk.get("cross_class_cost_mult", 2.0))
        if f.perk_points < cost:
            return Result(False, t("not_enough_perk_points"), "not_enough_points")
        old_max = f.max_hp
        f.perk_points -= cost
        f.unlocked_perks.append(perk_id)
        hp_gain = f.max_hp - old_max
        if hp_gain > 0:
            f.hp = min(f.hp + hp_gain, f.max_hp)
        self._log_event("perk", name=f.name, perk=perk["name"])
        self.save()
        self._mark_dirty()
        return Result(True, t("perk_unlocked_msg", name=f.name, perk=perk["name"]))

    def dismiss_dead(self, index):
        if index < len(self.fighters) and not self.fighters[index].alive:
            f = self.fighters[index]
            for slot in EQUIPMENT_SLOTS:
                item = f.equipment.get(slot)
                if item:
                    self.inventory.append(dict(item))
            self.fighters.pop(index)
            if self.active_fighter_idx >= len(self.fighters):
                self.active_fighter_idx = max(0, len(self.fighters) - 1)

    def dismiss_fighter(self, index):
        """Dismiss a living fighter. Equipment returned to inventory."""
        if index < 0 or index >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[index]
        name = f.name
        for slot in EQUIPMENT_SLOTS:
            item = f.equipment.get(slot)
            if item:
                self.inventory.append(dict(item))
        self.graveyard.append({
            "name": name, "class": f.fighter_class,
            "level": f.level, "kills": f.kills, "cause": "dismissed",
        })
        self.fighters.pop(index)
        if self.active_fighter_idx >= len(self.fighters):
            self.active_fighter_idx = max(0, len(self.fighters) - 1)
        self._log_event("dismiss", name=name, lv=f.level)
        self.save()
        return Result(True, t("fighter_dismissed", name=name), "dismissed")

    # --- Battle (turn-based) ---

    def _spawn_enemy(self):
        if self._revenge_common:
            self.preview_enemies = self._revenge_common
            self.current_enemy = self._revenge_common[0]
            return
        num = max(1, sum(1 for f in self.fighters if f.available))
        tier = self.arena_tier
        normals = data_loader.normals_by_tier.get(tier)
        enemies = []
        for _ in range(num):
            if normals:
                template = random.choice(normals)
                enemies.append(Enemy.from_template(template, tier))
            else:
                enemies.append(Enemy(tier=tier))
        self.preview_enemies = enemies
        self.current_enemy = enemies[0] if enemies else None

    def award_gold(self, amount):
        self.gold += amount
        self.total_gold_earned += amount

    def handle_fighter_death(self, fighter):
        """Check permadeath, update graveyard. Returns (died, injury_id)."""
        died, injury_id = fighter.check_permadeath()
        if died:
            self.total_deaths += 1
            self.graveyard.append({
                "name": fighter.name,
                "level": fighter.level,
                "kills": fighter.kills,
            })
        return died, injury_id

    def spawn_boss_enemy(self):
        """Spawn a boss-tier enemy as current_enemy (no battle start)."""
        if self._revenge_boss:
            self.preview_enemies = self._revenge_boss
            self.current_enemy = self._revenge_boss[0]
            return
        bosses = data_loader.bosses_by_tier.get(self.arena_tier)
        if bosses:
            template = random.choice(bosses)
            boss = Boss.from_template(template, self.arena_tier)
        else:
            boss = Boss(self.arena_tier)
        from game.boss_modifiers import BossModifierHandler
        BossModifierHandler(data_loader.boss_modifiers).assign_modifiers(boss, self.arena_tier)
        self.preview_enemies = [boss]
        self.current_enemy = boss

    def start_auto_battle(self):
        self._current_battle_messages = []
        events = self.battle_mgr.start_auto_battle()
        self._collect_events(events)
        return events

    def start_boss_fight(self):
        self._current_battle_messages = []
        events = self.battle_mgr.start_boss_fight()
        self._collect_events(events)
        return events

    def battle_next_turn(self):
        events = self.battle_mgr.do_turn()
        self._collect_events(events)
        self._post_battle_check()
        return events

    def battle_skip(self):
        events = self.battle_mgr.do_full_battle()
        self._collect_events(events)
        self._post_battle_check()
        return events

    def _collect_events(self, events):
        """Accumulate battle event messages for the log."""
        buf = getattr(self, '_current_battle_messages', None)
        if buf is None:
            self._current_battle_messages = buf = []
        for ev in events:
            if ev.message:
                buf.append(ev.message)

    def _post_battle_check(self):
        """After battle turn: check permadeath → roguelike reset.
        Note: wins, arena_tier, gold, fighter.kills and HP reset are
        already handled inside BattleManager.do_turn(). Here we only
        update run-level stats and spawn next enemy."""
        state = self.battle_mgr.state
        if state.phase == BattlePhase.VICTORY:
            if state.is_boss_fight:
                self.bosses_killed += 1
                self.check_t15_clear()
            self.run_kills += len([e for e in state.enemies if e.hp <= 0])
            if self.arena_tier > self.run_max_tier:
                self.run_max_tier = self.arena_tier
            self._record_battle(state, "V")
            # Clear revenge for the mode that was just won
            if state.is_boss_fight:
                self._revenge_boss = []
            else:
                self._revenge_common = []
            # Note: enemy re-spawn handled by ArenaScreen._check_battle_end()
            # which knows the current arena_mode (common vs boss)
            self._mark_dirty()

        # Check if all fighters are dead → roguelike reset
        if state.phase == BattlePhase.DEFEAT:
            self._record_battle(state, "D")
            # Revenge: surviving enemies carry over with their current HP
            survivors = [e for e in state.enemies if e.hp > 0]
            is_boss = state.is_boss_fight
            if survivors:
                if is_boss:
                    self._revenge_boss = survivors
                else:
                    self._revenge_common = survivors
                self.preview_enemies = survivors
                self.current_enemy = survivors[0]
            else:
                if is_boss:
                    self._revenge_boss = []
                else:
                    self._revenge_common = []
                self._spawn_enemy()
            for f in self.fighters:
                if f.alive:
                    f.hp = f.max_hp
            all_dead = not any(f.alive for f in self.fighters)
            if all_dead:
                # Defer reset so UI can show defeat screen first
                self._pending_reset = True

    def _record_battle(self, state, result):
        """Append full battle log to persistent history."""
        messages = getattr(self, '_current_battle_messages', [])
        self.battle_log.append({
            "t": int(time.time()),
            "tier": self.arena_tier,
            "boss": state.is_boss_fight,
            "r": result,
            "g": state.gold_earned,
            "turns": state.turn_number,
            "f": [f.name for f in state.player_fighters],
            "e": [e.name for e in state.enemies],
            "log": messages,
        })
        self._current_battle_messages = []
        if len(self.battle_log) > 100:
            self.battle_log = self.battle_log[-100:]
        r_label = "victory" if result == "V" else "defeat"
        self._log_event("battle", result=r_label, tier=self.arena_tier,
                        boss=state.is_boss_fight, gold=state.gold_earned)

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

    # --- Forge ---

    def get_forge_items(self):
        return [{**item, "affordable": self.gold >= item["cost"]} for item in _m.ALL_FORGE_ITEMS]

    def buy_forge_item(self, item_id):
        """Buy item from forge → goes to inventory."""
        item = next((i for i in _m.ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item:
            return Result(False, t("item_not_found"), "not_found")
        if self.gold < item["cost"]:
            return Result(False, t("not_enough_gold", need=fmt_num(item["cost"] - self.gold)), "not_enough_gold")
        self.gold -= item["cost"]
        self.total_gold_spent_equipment += item["cost"]
        self.inventory.append(dict(item))
        self._log_event("buy", item=item["name"], gold=item["cost"])
        self.save()
        self._mark_dirty()
        return Result(True, t("bought_msg", name=item['name']))

    def equip_item_on(self, fighter_idx, item_id):
        item = next((i for i in _m.ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item or fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        if self.battle_active:
            return Result(False, t("not_in_battle"), "not_in_battle")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if self.gold < item["cost"]:
            return Result(False, t("not_enough_gold", need=fmt_num(item["cost"] - self.gold)), "not_enough_gold")
        self.gold -= item["cost"]
        self.total_gold_spent_equipment += item["cost"]
        old = f.equip_item(dict(item))
        if old:
            self.inventory.append(dict(old))
        self._log_event("equip", item=item["name"], fighter=f.name, gold=item["cost"])
        self.save()
        self._mark_dirty()
        return Result(True, t("equipped_msg", item=item['name'], name=f.name))

    def equip_from_inventory(self, fighter_idx, inv_index):
        """Equip item from inventory onto a fighter. Old item goes to inventory."""
        if fighter_idx >= len(self.fighters) or inv_index >= len(self.inventory):
            return Result(False, "", "invalid")
        if self.battle_active:
            return Result(False, t("not_in_battle"), "not_in_battle")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, "", "fighter_dead")
        item = self.inventory.pop(inv_index)
        old = f.equip_item(dict(item))
        if old:
            self.inventory.append(dict(old))
        self._log_event("equip", item=item["name"], fighter=f.name)
        self.save()
        return Result(True, t("equipped_msg", item=item['name'], name=f.name))

    def unequip_from_fighter(self, fighter_idx, slot):
        """Unequip item from fighter slot → inventory. Blocked during battle."""
        if self.battle_active:
            return Result(False, t("not_in_battle"), "not_in_battle")
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        old = f.unequip_item(slot)
        if old:
            self.inventory.append(dict(old))
        self.save()
        return Result(True, "ok")

    def sell_inventory_item(self, inv_index):
        """Sell an item from inventory for half its cost."""
        if inv_index >= len(self.inventory):
            return 0
        item = self.inventory.pop(inv_index)
        sell_price = item.get("cost", 0) // 2
        self.gold += sell_price
        self._log_event("sell", item=item.get("name", "?"), gold=sell_price)
        self.save()
        return sell_price

    def get_inventory_count(self, item_id):
        """Count how many of an item are in inventory."""
        return sum(1 for i in self.inventory if i.get("id") == item_id)

    def find_inventory_index(self, item_id):
        """Find the inventory index for an item id with highest upgrade_level, or -1."""
        best_idx = -1
        best_lvl = -1
        for idx, item in enumerate(self.inventory):
            if item.get("id") == item_id:
                lvl = item.get("upgrade_level", 0)
                if lvl > best_lvl:
                    best_lvl = lvl
                    best_idx = idx
        return best_idx

    # --- Expeditions ---

    def get_expeditions(self):
        return [{**exp, "affordable": True, "duration_text": self._fmt_duration(exp["duration"])} for exp in _m.EXPEDITIONS]

    def send_on_expedition(self, fighter_idx, expedition_id):
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if f.on_expedition:
            return Result(False, t("already_on_expedition", name=f.name), "already_on_expedition")
        on_exp_count = sum(1 for fi in self.fighters if fi.on_expedition)
        max_slots = 1 + self.extra_expedition_slots
        if on_exp_count >= max_slots:
            return Result(False, t("max_expeditions", n=max_slots), "max_expeditions")
        exp = next((e for e in _m.EXPEDITIONS if e["id"] == expedition_id), None)
        if not exp:
            return Result(False, "", "invalid")
        if f.level < exp["min_level"]:
            return Result(False, t("need_level", lv=exp['min_level']), "need_level")
        f.on_expedition = True
        f.expedition_id = expedition_id
        f.expedition_end = time.time() + exp["duration"]
        self._log_event("expedition_send", fighter=f.name, exp=exp["name"])
        if self.active_fighter_idx < len(self.fighters) and self.fighters[self.active_fighter_idx] == f:
            self.get_active_gladiator()
        return Result(True, t("departed_msg", name=f.name, exp=exp['name']))

    def check_expeditions(self):
        results = []
        now = time.time()
        for f in self.fighters:
            if not f.on_expedition or not f.alive:
                continue
            if now < f.expedition_end:
                continue
            exp = next((e for e in _m.EXPEDITIONS if e["id"] == f.expedition_id), None)
            if not exp:
                f.on_expedition = False
                f.expedition_id = None
                continue
            f.on_expedition = False
            f.expedition_id = None
            f.expedition_end = 0.0
            self.total_expeditions_completed += 1
            if random.random() < exp["danger"]:
                died, inj_id = f.check_permadeath()
                if died:
                    self.total_deaths += 1
                    self.graveyard.append({"name": f.name, "level": f.level, "kills": f.kills})
                    msg = f"{f.name} KILLED during {exp['name']}!"
                    results.append(msg)
                    self.expedition_log.append(msg)
                    # Check all dead
                    if not any(fi.alive for fi in self.fighters):
                        self._pending_reset = True
                    continue
                else:
                    inj_name = data_loader.injuries_by_id.get(inj_id, {}).get("name", "?")
                    msg_parts_pre = [t("suffered_injury", injury=inj_name)]
            else:
                msg_parts_pre = []
            shard_info = _m.SHARD_TIERS.get(exp["id"])
            if shard_info:
                tier = shard_info["tier"]
                amount = random.randint(1, 10)
                self.shards[tier] = self.shards.get(tier, 0) + amount
                _key = f"shard_tier_{tier}_name"
                _translated = t(_key)
                shard_display = _translated if _translated != _key else shard_info['name']
                msg_parts = [t("expedition_returned_shard",
                               fighter=f.name, exp=exp['name'],
                               n=amount, shard=shard_display)]
            else:
                msg_parts = [t("expedition_returned",
                               fighter=f.name, exp=exp['name'])]
            if random.random() < exp["relic_chance"]:
                rarity = random.choice(exp["relic_pool"])
                relic_template = random.choice(_m.RELICS[rarity])
                relic = dict(relic_template)
                self.inventory.append(relic)
                msg_parts.append(t("found_relic_msg", name=relic['name'], rarity=rarity))
            if random.random() < exp["danger"] * 0.5:
                existing_ids = {inj["id"] for inj in f.injuries}
                extra_inj_id = data_loader.pick_random_injury(existing_ids)
                f.injuries.append({"id": extra_inj_id})
                extra_name = data_loader.injuries_by_id.get(extra_inj_id, {}).get("name", "?")
                msg_parts.append(t("injured_expedition", injury=extra_name))
            msg_parts.extend(msg_parts_pre)
            f.heal()
            msg = " ".join(msg_parts)
            results.append(msg)
            self.expedition_log.append(msg)
        if results:
            for msg in results:
                self.pending_notifications.append(msg)
            self._mark_dirty()
        return results

    def get_expedition_status(self):
        now = time.time()
        return [
            {
                "fighter_name": f.name,
                "expedition_name": next((e["name"] for e in _m.EXPEDITIONS if e["id"] == f.expedition_id), "?"),
                "remaining": max(0, f.expedition_end - now),
                "remaining_text": self._fmt_duration(int(max(0, f.expedition_end - now))),
            }
            for f in self.fighters if f.on_expedition and f.alive
        ]

    def _fmt_duration(self, seconds):
        if seconds >= 3600:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
        if seconds >= 60:
            return f"{seconds // 60}m {seconds % 60}s"
        return f"{seconds}s"

    # --- Idle (minimal in roguelike) ---

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

    def get_heal_cost(self):
        return DifficultyScaler.heal_cost(self.arena_tier)

    def get_hp_heal_cost(self, fighters=None):
        """Total cost to heal HP of all fighters, scaling with arena tier."""
        if fighters is None:
            fighters = [f for f in self.fighters if f.available]
        total_missing = sum(max(0, f.max_hp - f.hp) for f in fighters if f.alive and f.hp > 0)
        if total_missing <= 0:
            return 0
        tier_mult = HP_HEAL_TIER_MULT ** (self.arena_tier - 1)
        return math.ceil(total_missing / HP_HEAL_DIVISOR * tier_mult)

    def heal_all_hp(self, fighters=None):
        """Heal all fighters to full HP. If not enough gold, spend all and heal partially.
        Returns (healed_count, gold_spent)."""
        if fighters is None:
            fighters = [f for f in self.fighters if f.available]
        damaged = [f for f in fighters if f.alive and f.hp > 0 and f.hp < f.max_hp]
        if not damaged:
            return 0, 0
        total_missing = sum(f.max_hp - f.hp for f in damaged)
        tier_mult = HP_HEAL_TIER_MULT ** (self.arena_tier - 1)
        full_cost = math.ceil(total_missing / HP_HEAL_DIVISOR * tier_mult)
        if self.gold >= full_cost:
            self.gold -= full_cost
            for f in damaged:
                f.hp = f.max_hp
            self.save()
            return len(damaged), full_cost
        # Partial heal: spend all gold
        available_hp = int(self.gold * HP_HEAL_DIVISOR / tier_mult)
        spent = int(self.gold)
        self.gold = 0
        healed = 0
        # Heal most damaged first
        damaged.sort(key=lambda f: f.max_hp - f.hp, reverse=True)
        for f in damaged:
            if available_hp <= 0:
                break
            missing = f.max_hp - f.hp
            heal_amount = min(missing, available_hp)
            f.hp += heal_amount
            available_hp -= heal_amount
            healed += 1
        self.save()
        return healed, spent

    # --- Item upgrade & enchantment ---

    def upgrade_item(self, item_dict):
        """Upgrade any equipment item by +1. Returns Result."""
        max_lvl = get_max_upgrade(item_dict)
        current = item_dict.get("upgrade_level", 0)
        if current >= max_lvl:
            return Result(False, t("max_upgrade_reached"), "max_level")
        target = current + 1
        tier, count = get_upgrade_tier(target)
        if item_dict.get("slot") == "relic":
            count *= 10
        have = self.shards.get(tier, 0)
        if have < count:
            return Result(False, t("not_enough_shards", tier=tier, need=count, have=have), "not_enough_shards")
        self.shards[tier] -= count
        # Adjust fighter HP if this item is equipped and grants HP
        owner = None
        for f in self.fighters:
            for slot in EQUIPMENT_SLOTS:
                if f.equipment.get(slot) is item_dict:
                    owner = f
                    break
            if owner:
                break
        old_max = owner.max_hp if owner else 0
        item_dict["upgrade_level"] = target
        if owner:
            hp_gain = owner.max_hp - old_max
            if hp_gain > 0:
                owner.hp = min(owner.hp + hp_gain, owner.max_hp)
        self._log_event("upgrade", item=item_dict.get("name", "?"), lv=target)
        self.save()
        return Result(True, t("weapon_upgraded", name=item_dict.get("name", "?"), level=target))

    def enchant_weapon(self, weapon_dict, enchantment_id):
        """Apply enchantment to a weapon. Returns Result."""
        ench = _m.ENCHANTMENT_TYPES.get(enchantment_id)
        if not ench:
            return Result(False, t("invalid_enchantment"), "invalid_enchantment")
        if weapon_dict.get("slot") != "weapon":
            return Result(False, t("only_weapons"), "wrong_slot")
        gold_cost = ench["cost_gold"]
        shard_tier = ench["cost_shard_tier"]
        shard_count = ench["cost_shard_count"]
        if self.gold < gold_cost:
            return Result(False, t("not_enough_gold", need=fmt_num(gold_cost - self.gold)), "not_enough_gold")
        have = self.shards.get(shard_tier, 0)
        if have < shard_count:
            return Result(False, t("not_enough_shards", tier=shard_tier, need=shard_count, have=have), "not_enough_shards")
        self.gold -= gold_cost
        self.shards[shard_tier] -= shard_count
        weapon_dict["enchantment"] = enchantment_id
        self.total_enchantments_applied += 1
        self._log_event("enchant", item=weapon_dict.get("name", "?"), ench=ench["name"], gold=gold_cost)
        self.save()
        self._mark_dirty()
        return Result(True, t("weapon_enchanted", name=weapon_dict.get("name", "?"), ench=ench["name"]))

    # --- Injury healing ---

    def heal_fighter_injury(self, fighter_idx, injury_idx=None):
        """Heal one injury from fighter. Heals cheapest non-permanent by default."""
        if 0 <= fighter_idx < len(self.fighters):
            f = self.fighters[fighter_idx]
            if not f.injuries:
                return Result(False, t("no_injuries"), "no_injuries")
            if injury_idx is None:
                injury_idx = f.cheapest_healable_injury_idx()
            if injury_idx < 0:
                return Result(False, t("no_healable_injuries"), "permanent_only")
            cost = f.get_injury_heal_cost(injury_idx)
            if cost < 0:
                return Result(False, t("no_healable_injuries"), "permanent_injury")
            if self.gold < cost:
                return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
            self.gold -= cost
            removed = f.injuries.pop(injury_idx)
            self.total_injuries_healed += 1
            if f.hp > f.max_hp:
                f.hp = f.max_hp
            inj_name = data_loader.injuries_by_id.get(removed["id"], {}).get("name", "?")
            self._log_event("heal", fighter=f.name, injury=inj_name, gold=cost)
            self.save()
            self._mark_dirty()
            return Result(True, t("healed_injury_msg", name=f.name, injury=inj_name, cost=fmt_num(cost)))
        return Result(False, t("invalid_fighter_err"), "invalid_fighter")

    def heal_fighter_all_injuries_cost(self, fighter_idx):
        """Total gold cost to heal all non-permanent injuries of one fighter."""
        if fighter_idx >= len(self.fighters):
            return 0
        f = self.fighters[fighter_idx]
        total = 0
        for i in range(len(f.injuries)):
            cost = f.get_injury_heal_cost(i)
            if cost > 0:
                total += cost
        return total

    def heal_fighter_all_injuries(self, fighter_idx):
        """Heal all non-permanent injuries of one fighter. Returns Result."""
        cost = self.heal_fighter_all_injuries_cost(fighter_idx)
        if cost <= 0:
            return Result(False, t("no_injuries"), "no_injuries")
        if self.gold < cost:
            return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
        f = self.fighters[fighter_idx]
        self.gold -= cost
        keep = []
        healed = 0
        for inj in f.injuries:
            data = f._get_injury_data(inj["id"])
            if data.get("heal_cost_multiplier", 1) == 0:
                keep.append(inj)
            else:
                healed += 1
        f.injuries = keep
        self.total_injuries_healed += healed
        if f.hp > f.max_hp:
            f.hp = f.max_hp
        self.save()
        self._mark_dirty()
        return Result(True, t("healed_all_injuries_msg", n=healed, cost=fmt_num(cost)))

    def heal_all_injuries_cost(self):
        """Total gold cost to heal ALL non-permanent injuries from ALL fighters."""
        total = 0
        for f in self.fighters:
            if f.alive:
                for i in range(len(f.injuries)):
                    cost = f.get_injury_heal_cost(i)
                    if cost > 0:
                        total += cost
        return total

    def heal_all_injuries(self):
        """Heal all non-permanent injuries from all fighters. Returns Result."""
        cost = self.heal_all_injuries_cost()
        if cost <= 0:
            return Result(False, t("no_injuries"), "no_injuries")
        if self.gold < cost:
            return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
        self.gold -= cost
        healed = 0
        for f in self.fighters:
            if f.alive:
                keep = []
                for inj in f.injuries:
                    data = f._get_injury_data(inj["id"])
                    if data.get("heal_cost_multiplier", 1) == 0:
                        keep.append(inj)  # permanent stays
                    else:
                        healed += 1
                f.injuries = keep
                if f.hp > f.max_hp:
                    f.hp = f.max_hp
        self.total_injuries_healed += healed
        self.save()
        self._mark_dirty()
        return Result(True, t("healed_all_injuries_msg", n=healed, cost=fmt_num(cost)))

    # --- Market (consumables only, no idle boosts) ---

    def get_shop_items(self):
        items = get_dynamic_shop_items(self.arena_tier, self.surgeon_uses)
        return [{**item, "affordable": self.gold >= item["cost"]} for item in items]

    def buy_item(self, item_id):
        items = get_dynamic_shop_items(self.arena_tier, self.surgeon_uses)
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return Result(False, t("item_not_found"), "not_found")
        if self.gold < item["cost"]:
            return Result(False, t("not_enough_gold", need=fmt_num(item["cost"] - self.gold)), "not_enough_gold")
        self.gold -= item["cost"]
        effect = item["effect"]
        if "heal" in effect:
            f = self.get_active_gladiator()
            if f: f.heal()
        if "base_attack" in effect:
            f = self.get_active_gladiator()
            if f: f.base_attack += effect["base_attack"]
        if "base_defense" in effect:
            f = self.get_active_gladiator()
            if f: f.base_defense += effect["base_defense"]
        if "cure_injury" in effect:
            f = self.get_active_gladiator()
            if f and f.injuries:
                count = effect["cure_injury"]
                for _ in range(count):
                    idx = f.cheapest_healable_injury_idx()
                    if idx >= 0:
                        f.injuries.pop(idx)
                if f.hp > f.max_hp:
                    f.hp = f.max_hp
                self.surgeon_uses += 1
        return Result(True, t("bought_msg", name=item['name']))

    # --- Lore ---

    def unlock_lore(self, entry_id):
        """Unlock a lore entry by id. Returns True if newly unlocked."""
        if entry_id not in self.lore_unlocked:
            self.lore_unlocked.append(entry_id)
            self._mark_dirty()
            self.save()
            return True
        return False

    # --- Achievements ---

    def check_achievements(self):
        newly = []
        for ach in _ach_module.ACHIEVEMENTS:
            if ach["id"] in self.achievements_unlocked:
                continue
            try:
                if ach["check"](self):
                    self.achievements_unlocked.append(ach["id"])
                    self.diamonds += ach["diamonds"]
                    newly.append(ach)
                    self.pending_notifications.append(
                        t("achievement_unlocked", name=ach['name'], diamonds=ach['diamonds'])
                    )
            except Exception as e:
                _log.warning("Achievement check failed [%s]: %s", ach.get("id"), e)
        self.check_quests()
        return newly

    def check_quests(self):
        changed = False
        newly_completed = []
        # Keep looping while chapters unlock (cascade)
        progress = True
        while progress:
            progress = False
            for ch_idx, chapter in enumerate(STORY_CHAPTERS):
                if ch_idx > self.story_chapter:
                    break
                for quest in chapter["quests"]:
                    if quest["id"] in self.quests_completed:
                        continue
                    try:
                        if quest["check"](self):
                            self.quests_completed.append(quest["id"])
                            changed = True
                            newly_completed.append(quest)
                            reward = quest.get("reward", {})
                            diamonds = reward.get("diamonds", 0)
                            if diamonds:
                                self.pending_notifications.append(
                                    t("quest_completed", name=quest.get("name", "Quest"), diamonds=diamonds)
                                )
                            if "diamonds" in reward:
                                self.diamonds += reward["diamonds"]
                            if "shards" in reward:
                                for tier, count in reward["shards"].items():
                                    self.shards[tier] = self.shards.get(tier, 0) + count
                    except Exception as e:
                        _log.warning("Quest check failed [%s]: %s", quest.get("id"), e)
                all_done = all(q["id"] in self.quests_completed for q in chapter["quests"])
                if all_done and ch_idx == self.story_chapter:
                    self.story_chapter += 1
                    changed = True
                    progress = True  # re-scan for newly unlocked chapters
        if changed:
            self.save()
        return newly_completed

    def get_achievements(self):
        return [
            {**ach, "unlocked": ach["id"] in self.achievements_unlocked, "check": None}
            for ach in _ach_module.ACHIEVEMENTS
        ]

    # --- Diamond shop ---

    def get_diamond_shop(self):
        result = []
        for item in DIAMOND_SHOP:
            iid = item["id"]
            if iid == "heal_all_injuries_diamond":
                total = sum(f.injury_count for f in self.fighters if f.alive)
                cost = max(10, total * 10)
                result.append({**item, "cost": cost, "affordable": self.diamonds >= cost and total > 0})
            elif iid == "revive_token":
                dead_count = sum(1 for f in self.fighters if not f.alive)
                cost = max(100, dead_count * 100)
                result.append({**item, "cost": cost, "affordable": self.diamonds >= cost and dead_count > 0})
            elif iid == "extra_expedition_slot":
                cost = EXPEDITION_SLOT_BASE_COST * (2 ** self.extra_expedition_slots)
                n = self.extra_expedition_slots
                desc = item["desc"] + f" [{t('level_n', n=n)}]" if n > 0 else item["desc"]
                result.append({**item, "cost": cost, "desc": desc,
                               "affordable": self.diamonds >= cost})
            else:
                result.append({**item, "affordable": self.diamonds >= item["cost"]})
        return result

    def buy_diamond_item(self, item_id):
        item = next((i for i in DIAMOND_SHOP if i["id"] == item_id), None)
        if not item:
            return Result(False, t("not_found_err"), "not_found")

        if item_id == "name_change":
            # Special: don't charge yet — UI will show popup, then call rename_fighter
            return Result(True, "", "name_change")

        if item_id == "revive_token":
            dead = [f for f in self.fighters if not f.alive]
            if not dead:
                return Result(False, t("no_dead_fighters"), "no_dead")
            cost = max(100, len(dead) * 100)
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            names = []
            for f in dead:
                f.alive = True
                f.injuries = []
                f.hp = f.max_hp
                names.append(f.name)
            self.save()
            return Result(True, t("revived_all_msg", n=len(names)))

        if item_id == "heal_all_injuries_diamond":
            total_injuries = sum(f.injury_count for f in self.fighters if f.alive)
            if total_injuries == 0:
                return Result(False, t("no_injuries"), "no_injuries")
            cost = max(10, total_injuries * 10)
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            for f in self.fighters:
                if f.alive and f.injuries:
                    f.injuries = []
                    if f.hp > f.max_hp:
                        f.hp = f.max_hp
            self.save()
            return Result(True, t("all_injuries_healed", n=total_injuries))

        if item_id == "extra_expedition_slot":
            cost = EXPEDITION_SLOT_BASE_COST * (2 ** self.extra_expedition_slots)
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            self.extra_expedition_slots += 1
            self.save()
            return Result(True, t("expedition_slots", n=1 + self.extra_expedition_slots))

        if item_id == "golden_armor":
            if self.diamonds < item["cost"]:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= item["cost"]
            legendary_ids = ["blade_of_ruin", "dragonscale", "crown_of_ash"]
            for lid in legendary_ids:
                itm = next((i for i in _m.ALL_FORGE_ITEMS if i["id"] == lid), None)
                if itm:
                    self.inventory.append(dict(itm))
            self.save()
            return Result(True, t("golden_set_bought"))

        # Generic fallback
        if self.diamonds < item["cost"]:
            return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
        self.diamonds -= item["cost"]
        self.save()
        return Result(True, t("bought_msg", name=item['name']))

    def rename_fighter(self, fighter_idx, new_name):
        """Rename a fighter. Costs 25 diamonds (Identity Scroll)."""
        new_name = new_name.strip()
        if not new_name or fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        if self.diamonds < RENAME_COST_DIAMONDS:
            return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
        self.diamonds -= RENAME_COST_DIAMONDS
        old_name = self.fighters[fighter_idx].name
        self.fighters[fighter_idx].name = new_name
        self.save()
        return Result(True, t("renamed_msg", old=old_name, new=new_name))

    def get_diamond_bundles(self):
        return DIAMOND_BUNDLES

    # --- Story & Tutorial ---

    def get_pending_tutorial(self):
        return get_pending_tutorial(self)

    def mark_tutorial_shown(self, step_id):
        if step_id not in self.tutorial_shown:
            self.tutorial_shown.append(step_id)

    # --- Ads ---

    def should_show_interstitial(self):
        if self.ads_removed:
            return False
        return self.wins > 0 and self.wins % 5 == 0

    def should_show_banner(self):
        return not self.ads_removed


    # --- IAP ---

    def purchase_remove_ads(self):
        self.ads_removed = True

    def purchase_diamonds(self, bundle_id):
        bundle = next((b for b in DIAMOND_BUNDLES if b["id"] == bundle_id), None)
        if bundle:
            self.diamonds += bundle["diamonds"]
            return Result(True, t("diamonds_earned", n=bundle['diamonds']))
        return Result(False, "", "not_found")

    def restore_purchases(self, purchase_ids: list[str]):
        for pid in purchase_ids:
            if pid == "remove_ads": self.ads_removed = True

    # --- Save / Load ---

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
        data = {
            "gold": self.gold,
            "active_fighter_idx": self.active_fighter_idx,
            "arena_tier": self.arena_tier,
            "wins": self.wins,
            "total_wins": self.total_wins,
            "total_deaths": self.total_deaths,
            "graveyard": self.graveyard,
            "fighters": [f.to_dict() for f in self.fighters],
            "expedition_log": self.expedition_log[-20:],
            "battle_log": self.battle_log[-200:],
            "event_log": self.event_log[-200:],
            "surgeon_uses": self.surgeon_uses,
            "total_gold_earned": self.total_gold_earned,
            # Run tracking
            "run_number": self.run_number,
            "run_kills": self.run_kills,
            "run_max_tier": self.run_max_tier,
            # Persistent
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
            # Achievement counters
            "total_enchantments_applied": self.total_enchantments_applied,
            "total_enchantment_procs": self.total_enchantment_procs,
            "total_gold_spent_equipment": self.total_gold_spent_equipment,
            "total_injuries_healed": self.total_injuries_healed,
            "total_expeditions_completed": self.total_expeditions_completed,
            "lore_unlocked": self.lore_unlocked,
        }
        # Atomic write: save to temp file, then rename to avoid corruption
        save_path = self.SAVE_PATH
        tmp_path = save_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f)
        # Replace old save atomically
        if os.path.exists(save_path):
            backup_path = save_path + ".bak"
            try:
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(save_path, backup_path)
            except OSError:
                pass
        os.rename(tmp_path, save_path)
        return data

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
