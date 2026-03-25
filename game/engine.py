# Build: 4
"""Core game engine — roguelike manager with permadeath reset."""

import json
import os
import random
import time

from game.models import (
    Fighter, Enemy, ALL_FORGE_ITEMS, FIGHTER_CLASSES,
    EXPEDITIONS, RELICS, DifficultyScaler,
    get_dynamic_shop_items, fmt_num,
)
from game.localization import t
from game.battle import BattleManager, BattlePhase
from game.achievements import ACHIEVEMENTS, DIAMOND_SHOP, DIAMOND_BUNDLES
from game.story import TUTORIAL_STEPS, get_pending_tutorial

def _get_save_path():
    from kivy.utils import platform
    if platform == "android":
        from android.storage import app_storage_path  # noqa
        return os.path.join(app_storage_path(), ".gladiator_idle_save.json")
    return os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")

SAVE_PATH = _get_save_path()


class GameEngine:

    def __init__(self):
        # --- Run state (resets on permadeath) ---
        self.gold = 100.0
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
        self.tutorial_shown: list[str] = []
        self.extra_expedition_slots = 0
        self.war_drums_until = 0.0

        # Inventory: list of item dicts (unequipped equipment)
        self.inventory: list[dict] = []

        # Battle manager
        self.battle_mgr = BattleManager(self)

        # Monetization
        self.ads_removed = False

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
        self.gold = 100.0
        self.inventory = []
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
        alive = [f for f in self.fighters if f.alive and not f.on_expedition]
        if not alive:
            return None
        self.active_fighter_idx = min(self.active_fighter_idx, len(self.fighters) - 1)
        f = self.fighters[self.active_fighter_idx]
        if f.alive and not f.on_expedition:
            return f
        for i, f in enumerate(self.fighters):
            if f.alive and not f.on_expedition:
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
            return t("recruited_msg", name=f.name, cls=f.class_name)
        return t("need_gold", cost=f"{fmt_num(cost)}g")

    def upgrade_gladiator(self, index):
        if index >= len(self.fighters):
            return ""
        f = self.fighters[index]
        if not f.alive:
            return t("fighter_dead", name=f.name)
        if self.gold >= f.upgrade_cost:
            self.gold -= f.upgrade_cost
            f.level_up()
            self.check_achievements()
            return t("reached_level", name=f.name, lv=f.level, pts=f.points_per_level)
        return t("not_enough_gold")

    def distribute_stat(self, fighter_idx, stat_name):
        """Distribute 1 unused point to a stat."""
        if fighter_idx >= len(self.fighters):
            return ""
        f = self.fighters[fighter_idx]
        if not f.alive:
            return t("fighter_dead", name=f.name)
        if f.unused_points <= 0:
            return t("no_unused_points")
        if f.distribute_point(stat_name):
            return t("stat_distributed", name=f.name, stat=stat_name.upper(), pts=f.unused_points)
        return ""

    def dismiss_dead(self, index):
        if index < len(self.fighters) and not self.fighters[index].alive:
            self.fighters.pop(index)
            if self.active_fighter_idx >= len(self.fighters):
                self.active_fighter_idx = max(0, len(self.fighters) - 1)

    # --- Battle (turn-based) ---

    def _spawn_enemy(self):
        self.current_enemy = Enemy(tier=self.arena_tier)

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
        """After battle turn: check permadeath → roguelike reset."""
        state = self.battle_mgr.state
        if state.phase == BattlePhase.VICTORY:
            self.wins += 1
            if state.is_boss_fight:
                self.bosses_killed += 1
                self.arena_tier += 1
            self.run_kills += len([e for e in state.enemies if e.hp <= 0])
            if self.arena_tier > self.run_max_tier:
                self.run_max_tier = self.arena_tier
            for f in self.fighters:
                if f.alive:
                    f.hp = f.max_hp
            # Spawn a fresh enemy at the current tier so the preview is correct
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

    # --- Legacy single-tick battle ---

    def do_battle_tick(self) -> str:
        fighter = self.get_active_gladiator()
        if not fighter:
            return t("no_fighters")
        if not self.current_enemy or self.current_enemy.hp <= 0:
            self._spawn_enemy()
        enemy = self.current_enemy
        log = []
        raw = fighter.deal_damage()
        # Crit check using fighter stats
        is_crit = random.random() < fighter.crit_chance
        if is_crit:
            raw = int(raw * fighter.crit_mult)
        actual = enemy.take_damage(raw)
        if actual == 0:
            log.append(f"{enemy.name} DODGED {fighter.name}'s attack!")
            # Enemy still attacks
        else:
            crit_tag = "CRIT! " if is_crit else ""
            log.append(f"{crit_tag}{fighter.name} hits {enemy.name} for {actual}")
        if actual > 0 and enemy.hp <= 0:
            reward = enemy.gold_reward
            self.gold += reward
            self.total_gold_earned += reward
            self.wins += 1
            self.run_kills += 1
            fighter.kills += 1
            log.append(f"Victory! +{reward} gold")
            for f in self.fighters:
                if f.alive:
                    f.hp = f.max_hp
            self._spawn_enemy()
            self.check_achievements()
            return "\n".join(log)
        # Enemy attacks back
        e_crit = random.random() < enemy.crit_chance
        raw = enemy.deal_damage()
        if e_crit:
            raw = int(raw * 1.8)
        actual = fighter.take_damage(raw)
        if actual == 0:
            log.append(f"{fighter.name} DODGED!")
        else:
            crit_tag = "CRIT! " if e_crit else ""
            log.append(f"{crit_tag}{enemy.name} hits {fighter.name} for {actual}")
        if fighter.hp <= 0:
            died = fighter.check_permadeath()
            if died:
                self.total_deaths += 1
                self.graveyard.append({"name": fighter.name, "level": fighter.level, "kills": fighter.kills})
                # Save equipment to inventory
                for slot in ["weapon", "armor", "accessory"]:
                    item = fighter.equipment.get(slot)
                    if item:
                        self.inventory.append(dict(item))
                        fighter.equipment[slot] = None
                log.append(f"{fighter.name} has FALLEN forever!")
                # Check if all dead → trigger reset
                if not any(f.alive for f in self.fighters):
                    log.append("ALL FIGHTERS DEAD! Run over.")
                    self._pending_reset = True
                else:
                    self.get_active_gladiator()
            else:
                log.append(f"{fighter.name} survived! Injury #{fighter.injuries}")
                fighter.heal()
            self._spawn_enemy()
            self.check_achievements()
        return "\n".join(log)

    # --- Forge ---

    def get_forge_items(self):
        return [{**item, "affordable": self.gold >= item["cost"]} for item in ALL_FORGE_ITEMS]

    def buy_forge_item(self, item_id):
        """Buy item from forge → goes to inventory."""
        item = next((i for i in ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item:
            return t("item_not_found")
        if self.gold < item["cost"]:
            return t("not_enough_gold")
        self.gold -= item["cost"]
        self.inventory.append(dict(item))
        self.save()
        self.check_achievements()
        return f"Bought {item['name']}"

    def equip_item_on(self, fighter_idx, item_id):
        item = next((i for i in ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item or fighter_idx >= len(self.fighters):
            return ""
        f = self.fighters[fighter_idx]
        if not f.alive:
            return t("fighter_dead", name=f.name)
        if self.gold < item["cost"]:
            return t("not_enough_gold")
        self.gold -= item["cost"]
        old = f.equip_item(dict(item))
        if old:
            self.inventory.append(dict(old))
        self.save()
        return t("equipped_msg", item=item['name'], name=f.name)

    def equip_from_inventory(self, fighter_idx, inv_index):
        """Equip item from inventory onto a fighter. Old item goes to inventory."""
        if fighter_idx >= len(self.fighters) or inv_index >= len(self.inventory):
            return ""
        f = self.fighters[fighter_idx]
        if not f.alive:
            return ""
        item = self.inventory.pop(inv_index)
        old = f.equip_item(dict(item))
        if old:
            self.inventory.append(dict(old))
        self.save()
        return t("equipped_msg", item=item['name'], name=f.name)

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
        """Find the first inventory index for an item id, or -1."""
        for idx, item in enumerate(self.inventory):
            if item.get("id") == item_id:
                return idx
        return -1

    # --- Expeditions ---

    def get_expeditions(self):
        return [{**exp, "affordable": True, "duration_text": self._fmt_duration(exp["duration"])} for exp in EXPEDITIONS]

    def send_on_expedition(self, fighter_idx, expedition_id):
        if fighter_idx >= len(self.fighters):
            return ""
        f = self.fighters[fighter_idx]
        if not f.alive:
            return t("fighter_dead", name=f.name)
        if f.on_expedition:
            return t("already_on_expedition", name=f.name)
        on_exp_count = sum(1 for fi in self.fighters if fi.on_expedition)
        max_slots = 1 + self.extra_expedition_slots
        if on_exp_count >= max_slots:
            return t("max_expeditions", n=max_slots)
        exp = next((e for e in EXPEDITIONS if e["id"] == expedition_id), None)
        if not exp:
            return ""
        if f.level < exp["min_level"]:
            return t("need_level", lv=exp['min_level'])
        f.on_expedition = True
        f.expedition_id = expedition_id
        f.expedition_end = time.time() + exp["duration"]
        if self.fighters[self.active_fighter_idx] == f:
            self.get_active_gladiator()
        return t("departed_msg", name=f.name, exp=exp['name'])

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
                    # Save equipment to inventory
                    for slot in ["weapon", "armor", "accessory"]:
                        item = f.equipment.get(slot)
                        if item:
                            self.inventory.append(dict(item))
                            f.equipment[slot] = None
                    msg = f"{f.name} KILLED during {exp['name']}!"
                    results.append(msg)
                    self.expedition_log.append(msg)
                    # Check all dead
                    if not any(fi.alive for fi in self.fighters):
                        self._pending_reset = True
                    continue
                else:
                    f.injuries += 1
            gold = random.randint(*exp["gold_range"])
            self.gold += gold
            self.total_gold_earned += gold
            msg_parts = [f"{f.name} returned from {exp['name']}! +{gold}g"]
            if random.random() < exp["relic_chance"]:
                rarity = random.choice(exp["relic_pool"])
                relic_template = random.choice(RELICS[rarity])
                relic = {**relic_template, "rarity": rarity}
                f.add_relic(relic)
                msg_parts.append(f"Found: {relic['name']} [{rarity}]")
            if random.random() < exp["danger"] * 0.5:
                f.injuries += 1
                msg_parts.append(f"Injured ({f.injuries})")
            f.heal()
            msg = " ".join(msg_parts)
            results.append(msg)
            self.expedition_log.append(msg)
        if results:
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
        self.check_expeditions()

    def get_heal_cost(self):
        return DifficultyScaler.heal_cost(self.arena_tier)

    # --- Injury healing ---

    def heal_fighter_injury(self, index):
        """Heal one injury from fighter at index. Returns (success, message)."""
        if 0 <= index < len(self.fighters):
            f = self.fighters[index]
            if f.injuries <= 0:
                return False, "No injuries"
            cost = f.get_injury_heal_cost()
            if self.gold < cost:
                return False, "Not enough gold"
            self.gold -= cost
            f.injuries -= 1
            f.injuries_healed += 1
            self.save()
            return True, f"Healed {f.name} (-1 injury, cost {cost}g)"
        return False, "Invalid fighter"

    def heal_all_injuries_cost(self):
        """Total cost to heal ALL injuries from ALL fighters."""
        total = 0
        for f in self.fighters:
            if f.alive:
                for i in range(f.injuries):
                    total += 50 * (1 + f.injuries_healed + i) * max(1, f.level)
        return total

    def heal_all_injuries(self):
        """Heal all injuries from all fighters. Returns (success, message)."""
        cost = self.heal_all_injuries_cost()
        if cost <= 0:
            return False, "No injuries to heal"
        if self.gold < cost:
            return False, "Not enough gold"
        self.gold -= cost
        healed = 0
        for f in self.fighters:
            if f.alive:
                while f.injuries > 0:
                    f.injuries -= 1
                    f.injuries_healed += 1
                    healed += 1
        self.save()
        return True, f"Healed {healed} injuries for {cost}g"

    # --- Market (consumables only, no idle boosts) ---

    def get_shop_items(self):
        items = get_dynamic_shop_items(self.arena_tier, self.surgeon_uses)
        return [{**item, "affordable": self.gold >= item["cost"]} for item in items]

    def buy_item(self, item_id):
        items = get_dynamic_shop_items(self.arena_tier, self.surgeon_uses)
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return t("item_not_found")
        if self.gold < item["cost"]:
            return t("not_enough_gold")
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
        return t("bought_msg", name=item['name'])

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
            except Exception:
                pass
        return newly

    def get_achievements(self):
        return [
            {**ach, "unlocked": ach["id"] in self.achievements_unlocked, "check": None}
            for ach in ACHIEVEMENTS
        ]

    # --- Diamond shop ---

    def get_diamond_shop(self):
        return [{**item, "affordable": self.diamonds >= item["cost"]} for item in DIAMOND_SHOP]

    def buy_diamond_item(self, item_id):
        item = next((i for i in DIAMOND_SHOP if i["id"] == item_id), None)
        if not item:
            return "Not found"
        if self.diamonds < item["cost"]:
            return t("not_enough_diamonds")
        self.diamonds -= item["cost"]

        if item_id == "revive_token":
            dead = [f for f in self.fighters if not f.alive]
            if dead:
                revived = dead[0]
                revived.alive = True
                revived.injuries = 0
                revived.hp = revived.max_hp
                return t("revived_msg", name=revived.name)
            return t("no_dead_fighters")
        elif item_id == "instant_heal_all":
            for f in self.fighters:
                if f.alive:
                    f.heal()
            return t("healed_all")
        elif item_id == "double_exp_1h":
            self.war_drums_until = time.time() + 3600
            return t("war_drums")
        elif item_id == "extra_expedition_slot":
            self.extra_expedition_slots += 1
            return t("expedition_slots", n=1 + self.extra_expedition_slots)
        elif item_id == "golden_armor":
            f = self.get_active_gladiator()
            if f:
                golden = {"id": "golden_set", "name": "Golden War Set", "slot": "weapon",
                          "rarity": "legendary", "atk": 20, "def": 20, "hp": 40, "cost": 0}
                f.equip_item(golden)
                return t("golden_set_equipped", name=f.name)
            return t("no_active_fighter")
        elif item_id == "skip_tier":
            self.arena_tier += 1
            if self.arena_tier > self.run_max_tier:
                self.run_max_tier = self.arena_tier
            self._spawn_enemy()
            return t("tier_advanced", tier=self.arena_tier)
        elif item_id == "name_change":
            return t("bought_msg", name=item['name'])
        return t("bought_msg", name=item['name'])

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
            return t("diamonds_earned", n=bundle['diamonds'])
        return ""

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
            "tutorial_shown": self.tutorial_shown,
            "extra_expedition_slots": self.extra_expedition_slots,
            "war_drums_until": self.war_drums_until,
            "ads_removed": self.ads_removed,
            "inventory": self.inventory,
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
        self.tutorial_shown = data.get("tutorial_shown", [])
        self.extra_expedition_slots = data.get("extra_expedition_slots", 0)
        self.war_drums_until = data.get("war_drums_until", 0.0)
        self.ads_removed = data.get("ads_removed", False)

        self.inventory = data.get("inventory", [])
        fighters_data = data.get("fighters", data.get("gladiators", []))
        self.fighters = [Fighter.from_dict(fd) for fd in fighters_data]
        if not self.fighters or not any(f.alive for f in self.fighters):
            self.fighters = [Fighter(name="Vorn", fighter_class="mercenary")]

        self.battle_mgr = BattleManager(self)
        self.check_expeditions()
        self._spawn_enemy()

    def get_save_data_json(self) -> str:
        return json.dumps(self.save())
