# Build: 24
"""Core game engine — roguelike manager with permadeath reset."""

import json
import logging
import math
import os
import random
import time

_log = logging.getLogger(__name__)

from game.models import (
    Fighter, Enemy, ALL_FORGE_ITEMS, FIGHTER_CLASSES,
    EXPEDITIONS, RELICS, DifficultyScaler, EQUIPMENT_SLOTS,
    SHARD_TIERS, get_upgrade_tier,
    ENCHANTMENT_TYPES, item_display_name, get_max_upgrade,
    get_dynamic_shop_items, fmt_num, get_boss_name, Result,
)
from game.localization import t, get_language, set_language
from game.battle import BattleManager, BattlePhase
from game.achievements import ACHIEVEMENTS, DIAMOND_SHOP, DIAMOND_BUNDLES
from game.constants import (
    STARTING_GOLD, RENAME_COST_DIAMONDS, EXPEDITION_SLOT_BASE_COST,
    HP_HEAL_TIER_MULT, HP_HEAL_DIVISOR, INJURY_HEAL_BASE_COST,
)
from game.story import TUTORIAL_STEPS, STORY_CHAPTERS, get_pending_tutorial
from game.data_loader import data_loader

def _get_save_path():
    from kivy.utils import platform
    if platform == "android":
        from android.storage import app_storage_path  # noqa
        return os.path.join(app_storage_path(), ".gladiator_idle_save.json")
    return os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")

SAVE_PATH = _get_save_path()


class GameEngine:

    def __init__(self):
        # --- Load data from JSON files ---
        data_loader.load_all()
        self._wire_data()

        # --- Run state (resets on permadeath) ---
        self.gold = STARTING_GOLD
        self.fighters: list[Fighter] = []
        self.active_fighter_idx = 0
        self.arena_tier = 1
        self.wins = 0
        self.total_deaths = 0
        self.graveyard: list[dict] = []
        self.current_enemy: Enemy | None = None
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

        # Inventory: list of item dicts (unequipped equipment)
        self.inventory: list[dict] = []

        # Metal shards (expedition currency for weapon upgrades)
        self.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        # Notification queue — drained by UI layer each tick
        self.pending_notifications: list[str] = []

        # Battle manager
        self.battle_mgr = BattleManager(self)

        # Monetization
        self.ads_removed = False

    @staticmethod
    def _wire_data():
        """Override hardcoded module-level data in models.py with JSON data."""
        import game.models as m
        dl = data_loader
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
        self.expedition_log = []
        self.surgeon_uses = 0
        self.total_gold_earned = 0.0
        self.run_number += 1
        self.run_kills = 0
        self.run_max_tier = 1

        # Reset battle
        self.battle_mgr = BattleManager(self)

        # Spawn fresh enemy
        self._spawn_enemy()

        self.check_achievements()
        self.save()

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
        return DifficultyScaler.hire_cost(alive_count)

    def hire_gladiator(self, fighter_class="mercenary"):
        """Hire a new fighter of given class."""
        cost = self.hire_cost
        if self.gold >= cost:
            self.gold -= cost
            f = Fighter(fighter_class=fighter_class)
            self.fighters.append(f)
            self.check_achievements()
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
            self.check_achievements()
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

    def dismiss_dead(self, index):
        if index < len(self.fighters) and not self.fighters[index].alive:
            f = self.fighters[index]
            # Return equipment to inventory
            for slot in EQUIPMENT_SLOTS:
                item = f.equipment.get(slot)
                if item:
                    self.inventory.append(dict(item))
            self.fighters.pop(index)
            if self.active_fighter_idx >= len(self.fighters):
                self.active_fighter_idx = max(0, len(self.fighters) - 1)

    # --- Battle (turn-based) ---

    def _spawn_enemy(self):
        self.current_enemy = Enemy(tier=self.arena_tier)

    def award_gold(self, amount):
        self.gold += amount
        self.total_gold_earned += amount

    def handle_fighter_death(self, fighter):
        """Check permadeath, update graveyard. Returns True if died forever."""
        died = fighter.check_permadeath()
        if died:
            self.total_deaths += 1
            self.graveyard.append({
                "name": fighter.name,
                "level": fighter.level,
                "kills": fighter.kills,
            })
        return died

    def spawn_boss_enemy(self):
        """Spawn a boss-tier enemy as current_enemy (no battle start)."""
        self.current_enemy = Enemy.create_boss(self.arena_tier)

    def start_auto_battle(self):
        events = self.battle_mgr.start_auto_battle()
        return events

    def start_boss_fight(self):
        events = self.battle_mgr.start_boss_fight()
        return events

    def battle_next_turn(self):
        events = self.battle_mgr.do_turn()
        self._post_battle_check()
        return events

    def battle_skip(self):
        events = self.battle_mgr.do_full_battle()
        self._post_battle_check()
        return events

    def _post_battle_check(self):
        """After battle turn: check permadeath → roguelike reset.
        Note: wins, arena_tier, gold, fighter.kills and HP reset are
        already handled inside BattleManager.do_turn(). Here we only
        update run-level stats and spawn next enemy."""
        state = self.battle_mgr.state
        if state.phase == BattlePhase.VICTORY:
            if state.is_boss_fight:
                self.bosses_killed += 1
            self.run_kills += len([e for e in state.enemies if e.hp <= 0])
            if self.arena_tier > self.run_max_tier:
                self.run_max_tier = self.arena_tier
            # Heal all fighters at end of victorious battle
            for f in self.fighters:
                if f.alive:
                    f.heal()
            self._spawn_enemy()
            self.check_achievements()

        # Check if all fighters are dead → roguelike reset
        if state.phase == BattlePhase.DEFEAT:
            for f in self.fighters:
                if f.alive:
                    f.hp = f.max_hp
            all_dead = not any(f.alive for f in self.fighters)
            if all_dead:
                # Defer reset so UI can show defeat screen first
                self._pending_reset = True

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
        return [{**item, "affordable": self.gold >= item["cost"]} for item in ALL_FORGE_ITEMS]

    def buy_forge_item(self, item_id):
        """Buy item from forge → goes to inventory."""
        item = next((i for i in ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item:
            return Result(False, t("item_not_found"), "not_found")
        if self.gold < item["cost"]:
            return Result(False, t("not_enough_gold", need=fmt_num(item["cost"] - self.gold)), "not_enough_gold")
        self.gold -= item["cost"]
        self.inventory.append(dict(item))
        self.save()
        self.check_achievements()
        return Result(True, f"Bought {item['name']}")

    def equip_item_on(self, fighter_idx, item_id):
        item = next((i for i in ALL_FORGE_ITEMS if i["id"] == item_id), None)
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
        old = f.equip_item(dict(item))
        if old:
            self.inventory.append(dict(old))
        self.save()
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
        return [{**exp, "affordable": True, "duration_text": self._fmt_duration(exp["duration"])} for exp in EXPEDITIONS]

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
        exp = next((e for e in EXPEDITIONS if e["id"] == expedition_id), None)
        if not exp:
            return Result(False, "", "invalid")
        if f.level < exp["min_level"]:
            return Result(False, t("need_level", lv=exp['min_level']), "need_level")
        f.on_expedition = True
        f.expedition_id = expedition_id
        f.expedition_end = time.time() + exp["duration"]
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
            exp = next((e for e in EXPEDITIONS if e["id"] == f.expedition_id), None)
            if not exp:
                f.on_expedition = False
                f.expedition_id = None
                continue
            f.on_expedition = False
            f.expedition_id = None
            f.expedition_end = 0.0
            if random.random() < exp["danger"]:
                died = f.check_permadeath()
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
                    f.injuries += 1
            shard_info = SHARD_TIERS.get(exp["id"])
            if shard_info:
                tier = shard_info["tier"]
                amount = random.randint(1, 10)
                self.shards[tier] = self.shards.get(tier, 0) + amount
                msg_parts = [f"{f.name} returned from {exp['name']}! +{amount} {shard_info['name']}"]
            else:
                msg_parts = [f"{f.name} returned from {exp['name']}!"]
            if random.random() < exp["relic_chance"]:
                rarity = random.choice(exp["relic_pool"])
                relic_template = random.choice(RELICS[rarity])
                relic = dict(relic_template)
                self.inventory.append(relic)
                msg_parts.append(f"Found: {relic['name']} [{rarity}]")
            if random.random() < exp["danger"] * 0.5:
                f.injuries += 1
                msg_parts.append(f"Injured ({f.injuries})")
            f.heal()
            msg = " ".join(msg_parts)
            results.append(msg)
            self.expedition_log.append(msg)
        if results:
            for msg in results:
                self.pending_notifications.append(msg)
            self.check_achievements()
        return results

    def get_expedition_status(self):
        now = time.time()
        return [
            {
                "fighter_name": f.name,
                "expedition_name": next((e["name"] for e in EXPEDITIONS if e["id"] == f.expedition_id), "?"),
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

    def idle_tick(self, dt):
        exp_results = self.check_expeditions()
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
        self.save()
        return Result(True, t("weapon_upgraded", name=item_dict.get("name", "?"), level=target))

    def enchant_weapon(self, weapon_dict, enchantment_id):
        """Apply enchantment to a weapon. Returns Result."""
        ench = ENCHANTMENT_TYPES.get(enchantment_id)
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
        self.save()
        return Result(True, t("weapon_enchanted", name=weapon_dict.get("name", "?"), ench=ench["name"]))

    # --- Injury healing ---

    def heal_fighter_injury(self, fighter_idx):
        """Heal one injury from fighter at fighter_idx. Returns Result."""
        if 0 <= fighter_idx < len(self.fighters):
            f = self.fighters[fighter_idx]
            if f.injuries <= 0:
                return Result(False, "No injuries", "no_injuries")
            cost = f.get_injury_heal_cost()
            if self.gold < cost:
                return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
            self.gold -= cost
            f.injuries -= 1
            f.injuries_healed += 1
            self.save()
            return Result(True, f"Healed {f.name} (-1 injury, cost {cost}g)")
        return Result(False, "Invalid fighter", "invalid_fighter")

    def heal_all_injuries_cost(self):
        """Total gold cost to heal ALL injuries from ALL fighters."""
        total = 0
        for f in self.fighters:
            if f.alive:
                for i in range(f.injuries):
                    total += INJURY_HEAL_BASE_COST * (1 + f.injuries_healed + i) * max(1, f.level)
        return total

    def heal_all_injuries(self):
        """Heal all injuries from all fighters. Returns Result."""
        cost = self.heal_all_injuries_cost()
        if cost <= 0:
            return Result(False, "No injuries to heal", "no_injuries")
        if self.gold < cost:
            return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
        self.gold -= cost
        healed = 0
        for f in self.fighters:
            if f.alive:
                while f.injuries > 0:
                    f.injuries -= 1
                    f.injuries_healed += 1
                    healed += 1
        self.save()
        return Result(True, f"Healed {healed} injuries for {cost}")

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
            if f and f.injuries > 0:
                f.injuries = max(0, f.injuries - effect["cure_injury"])
                self.surgeon_uses += 1
        return Result(True, t("bought_msg", name=item['name']))

    # --- Achievements ---

    def check_achievements(self):
        newly = []
        for ach in ACHIEVEMENTS:
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
            for ach in ACHIEVEMENTS
        ]

    # --- Diamond shop ---

    def get_diamond_shop(self):
        result = []
        for item in DIAMOND_SHOP:
            iid = item["id"]
            if iid == "heal_all_injuries_diamond":
                total = sum(f.injuries for f in self.fighters if f.alive)
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
            return Result(False, "Not found", "not_found")

        if item_id == "name_change":
            # Special: don't charge yet — UI will show popup, then call rename_fighter
            return Result(True, "", "name_change")

        if item_id == "revive_token":
            dead = [f for f in self.fighters if not f.alive]
            if not dead:
                return Result(False, t("no_dead_fighters"), "no_dead")
            cost = len(dead) * 100
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            names = []
            for f in dead:
                f.alive = True
                f.injuries = 0
                f.hp = f.max_hp
                names.append(f.name)
            self.save()
            return Result(True, t("revived_all_msg", n=len(names)))

        if item_id == "heal_all_injuries_diamond":
            total_injuries = sum(f.injuries for f in self.fighters if f.alive)
            if total_injuries == 0:
                return Result(False, t("no_injuries"), "no_injuries")
            cost = total_injuries * 10
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            for f in self.fighters:
                if f.alive and f.injuries > 0:
                    f.injuries = 0
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
                itm = next((i for i in ALL_FORGE_ITEMS if i["id"] == lid), None)
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
        data = {
            "gold": self.gold,
            "active_fighter_idx": self.active_fighter_idx,
            "arena_tier": self.arena_tier,
            "wins": self.wins,
            "total_deaths": self.total_deaths,
            "graveyard": self.graveyard,
            "fighters": [f.to_dict() for f in self.fighters],
            "expedition_log": self.expedition_log[-20:],
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
            "ads_removed": self.ads_removed,
            "inventory": self.inventory,
            "shards": self.shards,
            "language": get_language(),
        }
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)
        return data

    def load(self, data=None):
        if data is None:
            if not os.path.exists(SAVE_PATH):
                self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]
                self._spawn_enemy()
                return
            with open(SAVE_PATH, "r") as f:
                data = json.load(f)

        self.gold = data.get("gold", 100)
        self.active_fighter_idx = data.get("active_fighter_idx", 0)
        self.arena_tier = data.get("arena_tier", 1)
        self.wins = data.get("wins", 0)
        self.total_deaths = data.get("total_deaths", 0)
        self.graveyard = data.get("graveyard", [])
        self.expedition_log = data.get("expedition_log", [])
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
        # war_drums_until removed — kept for backward compat on load
        self.ads_removed = data.get("ads_removed", False)

        saved_lang = data.get("language")
        if saved_lang:
            set_language(saved_lang)

        self.inventory = data.get("inventory", [])
        shards_raw = data.get("shards", {})
        self.shards = {int(k): v for k, v in shards_raw.items()} if shards_raw else {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        fighters_data = data.get("fighters", data.get("gladiators", []))
        self.fighters = [Fighter.from_dict(fd) for fd in fighters_data]
        # Migrate overflow relics from old save format
        for f in self.fighters:
            overflow = getattr(f, "_overflow_relics", [])
            if overflow:
                self.inventory.extend(overflow)
                f._overflow_relics = []
        if not self.fighters or not any(f.alive for f in self.fighters):
            self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]

        self.battle_mgr = BattleManager(self)
        self.check_expeditions()
        self._spawn_enemy()

    def get_save_data_json(self) -> str:
        return json.dumps(self.save())
