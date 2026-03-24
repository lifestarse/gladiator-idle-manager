"""Core game engine — battles, economy, diamonds, achievements, story."""

import json
import os
import random
import time

from game.models import (
    Fighter, Enemy, ALL_FORGE_ITEMS,
    EXPEDITIONS, RELICS, DifficultyScaler,
    get_dynamic_shop_items,
)
from game.battle import BattleManager, BattlePhase
from game.achievements import ACHIEVEMENTS, DIAMOND_SHOP, DIAMOND_BUNDLES
from game.story import (
    STORY_CHAPTERS, TUTORIAL_STEPS,
    get_current_chapter, get_pending_tutorial,
)

SAVE_PATH = os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")


class GameEngine:

    def __init__(self):
        self.gold = 100.0
        self.idle_gold_rate = 1.0
        self.fighters: list[Fighter] = []
        self.active_fighter_idx = 0
        self.arena_tier = 1
        self.wins = 0
        self.total_deaths = 0
        self.graveyard: list[dict] = []
        self.current_enemy: Enemy | None = None
        self.last_tick_time = time.time()
        self.expedition_log: list[str] = []

        # Economy tracking
        self.idle_purchases: dict[str, int] = {}
        self.surgeon_uses = 0
        self.total_gold_earned = 0.0

        # Diamonds & achievements
        self.diamonds = 0
        self.achievements_unlocked: list[str] = []
        self.bosses_killed = 0

        # Story & tutorial
        self.story_chapter = 0  # index into STORY_CHAPTERS (0 = Ch1 active)
        self.tutorial_shown: list[str] = []

        # Battle manager
        self.battle_mgr = BattleManager(self)

        # Monetization
        self.ads_removed = False
        self.vip_idle_boost = False
        self.rewarded_ad_bonus_until = 0.0
        self.ad_watches_today = 0
        self.last_ad_day = ""

        # Diamond shop tracking
        self.extra_expedition_slots = 0
        self.war_drums_until = 0.0

    # --- Backward compat ---
    @property
    def gladiators(self):
        return self.fighters

    @property
    def active_gladiator_idx(self):
        return self.active_fighter_idx

    @active_gladiator_idx.setter
    def active_gladiator_idx(self, val):
        self.active_fighter_idx = val

    @property
    def effective_idle_rate(self):
        rate = self.idle_gold_rate
        if self.vip_idle_boost:
            rate *= 1.5
        if time.time() < self.rewarded_ad_bonus_until:
            rate *= 2.0
        return rate

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

    def hire_gladiator(self):
        cost = self.hire_cost
        if self.gold >= cost:
            self.gold -= cost
            f = Fighter()
            self.fighters.append(f)
            self.check_achievements()
            return f"Recruited {f.name}!"
        return f"Need {cost}g!"

    def upgrade_gladiator(self, index):
        if index >= len(self.fighters):
            return "Invalid fighter"
        f = self.fighters[index]
        if not f.alive:
            return f"{f.name} is dead..."
        if self.gold >= f.upgrade_cost:
            self.gold -= f.upgrade_cost
            f.level += 1
            f.hp = f.max_hp
            self.check_achievements()
            return f"{f.name} trained to Lv.{f.level}!"
        return "Not enough gold!"

    def dismiss_dead(self, index):
        if index < len(self.fighters) and not self.fighters[index].alive:
            self.fighters.pop(index)
            if self.active_fighter_idx >= len(self.fighters):
                self.active_fighter_idx = max(0, len(self.fighters) - 1)

    # --- Battle (turn-based) ---

    def _spawn_enemy(self):
        self.current_enemy = Enemy(tier=self.arena_tier)

    def start_auto_battle(self):
        """Start animated auto-battle with all fighters."""
        events = self.battle_mgr.start_auto_battle()
        return events

    def start_boss_fight(self):
        """Start boss challenge."""
        events = self.battle_mgr.start_boss_fight()
        return events

    def battle_next_turn(self):
        """Advance battle by one turn. Returns events for UI animation."""
        events = self.battle_mgr.do_turn()
        if self.battle_mgr.state.phase == BattlePhase.VICTORY:
            if self.battle_mgr.state.is_boss_fight:
                self.bosses_killed += 1
            self.check_achievements()
        return events

    def battle_skip(self):
        """Skip to end of battle instantly."""
        events = self.battle_mgr.do_full_battle()
        if self.battle_mgr.state.phase == BattlePhase.VICTORY:
            if self.battle_mgr.state.is_boss_fight:
                self.bosses_killed += 1
            self.check_achievements()
        return events

    @property
    def battle_active(self):
        return self.battle_mgr.is_active

    # --- Legacy single-tick battle (for backward compat) ---

    def do_battle_tick(self) -> str:
        fighter = self.get_active_gladiator()
        if not fighter:
            return "No fighters available!"
        if not self.current_enemy or self.current_enemy.hp <= 0:
            self._spawn_enemy()
        enemy = self.current_enemy
        log = []
        raw = fighter.deal_damage()
        actual = enemy.take_damage(raw)
        log.append(f"{fighter.name} hits {enemy.name} for {actual}")
        if enemy.hp <= 0:
            reward = enemy.gold_reward
            if time.time() < self.rewarded_ad_bonus_until:
                reward = int(reward * 2)
            self.gold += reward
            self.total_gold_earned += reward
            self.wins += 1
            fighter.kills += 1
            if self.wins % 3 == 0:
                self.arena_tier += 1
            log.append(f"Victory! +{reward} gold")
            fighter.hp = min(fighter.hp + fighter.max_hp // 7, fighter.max_hp)
            self._spawn_enemy()
            self.check_achievements()
            return "\n".join(log)
        raw = enemy.deal_damage()
        actual = fighter.take_damage(raw)
        log.append(f"{enemy.name} hits {fighter.name} for {actual}")
        if fighter.hp <= 0:
            died = fighter.check_permadeath()
            if died:
                self.total_deaths += 1
                self.graveyard.append({"name": fighter.name, "level": fighter.level, "kills": fighter.kills})
                log.append(f"{fighter.name} has FALLEN forever!")
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
        item = next((i for i in ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item:
            return "Item not found"
        if self.gold < item["cost"]:
            return "Not enough gold"
        fighter = self.get_active_gladiator()
        if not fighter:
            return "No active fighter"
        self.gold -= item["cost"]
        fighter.equip_item(dict(item))
        self.check_achievements()
        return f"Equipped {item['name']} on {fighter.name}!"

    def equip_item_on(self, fighter_idx, item_id):
        item = next((i for i in ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item or fighter_idx >= len(self.fighters):
            return "Invalid"
        f = self.fighters[fighter_idx]
        if not f.alive:
            return "Fighter is dead"
        if self.gold < item["cost"]:
            return "Not enough gold"
        self.gold -= item["cost"]
        f.equip_item(dict(item))
        return f"Equipped {item['name']} on {f.name}!"

    # --- Expeditions ---

    def get_expeditions(self):
        return [{**exp, "affordable": True, "duration_text": self._fmt_duration(exp["duration"])} for exp in EXPEDITIONS]

    def send_on_expedition(self, fighter_idx, expedition_id):
        if fighter_idx >= len(self.fighters):
            return "Invalid fighter"
        f = self.fighters[fighter_idx]
        if not f.alive:
            return f"{f.name} is dead"
        if f.on_expedition:
            return f"{f.name} already on expedition"
        # Check expedition slot limit
        on_exp_count = sum(1 for fi in self.fighters if fi.on_expedition)
        max_slots = 1 + self.extra_expedition_slots
        if on_exp_count >= max_slots:
            return f"Max {max_slots} expedition(s) at once!"
        exp = next((e for e in EXPEDITIONS if e["id"] == expedition_id), None)
        if not exp:
            return "Unknown expedition"
        if f.level < exp["min_level"]:
            return f"Need Lv.{exp['min_level']}+"
        f.on_expedition = True
        f.expedition_id = expedition_id
        f.expedition_end = time.time() + exp["duration"]
        if self.fighters[self.active_fighter_idx] == f:
            self.get_active_gladiator()
        return f"{f.name} departed for {exp['name']}!"

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

    # --- Idle ---

    def idle_tick(self, dt):
        self.gold += self.effective_idle_rate * dt
        self.total_gold_earned += self.effective_idle_rate * dt
        self.check_expeditions()

    def calculate_offline_earnings(self, last_time):
        elapsed = min(time.time() - last_time, 3600 * 8)
        return self.effective_idle_rate * elapsed

    # --- Market ---

    def get_shop_items(self):
        items = get_dynamic_shop_items(self.arena_tier, self.idle_purchases, self.surgeon_uses)
        return [{**item, "affordable": self.gold >= item["cost"]} for item in items]

    def buy_item(self, item_id):
        items = get_dynamic_shop_items(self.arena_tier, self.idle_purchases, self.surgeon_uses)
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return "Item not found"
        if self.gold < item["cost"]:
            return "Not enough gold"
        self.gold -= item["cost"]
        effect = item["effect"]
        if "idle_gold_rate" in effect:
            self.idle_gold_rate += effect["idle_gold_rate"]
            self.idle_purchases[item_id] = self.idle_purchases.get(item_id, 0) + 1
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
        return f"Bought {item['name']}!"

    # --- Achievements ---

    def check_achievements(self):
        """Check all achievements and award diamonds for newly unlocked ones."""
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
            {**ach, "unlocked": ach["id"] in self.achievements_unlocked,
             "check": None}  # remove lambda for serialization
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
            return "Not enough diamonds"
        self.diamonds -= item["cost"]

        if item_id == "revive_token":
            dead = [f for f in self.fighters if not f.alive]
            if dead:
                revived = dead[0]
                revived.alive = True
                revived.injuries = 0
                revived.hp = revived.max_hp
                return f"Revived {revived.name}!"
            return "No dead fighters to revive"

        elif item_id == "instant_heal_all":
            for f in self.fighters:
                if f.alive:
                    f.heal()
            return "All fighters healed!"

        elif item_id == "double_exp_1h":
            self.war_drums_until = time.time() + 3600
            return "War Drums active for 1 hour!"

        elif item_id == "extra_expedition_slot":
            self.extra_expedition_slots += 1
            return f"Expedition slots: {1 + self.extra_expedition_slots}!"

        elif item_id == "golden_armor":
            f = self.get_active_gladiator()
            if f:
                golden = {"id": "golden_set", "name": "Golden War Set", "slot": "weapon",
                          "rarity": "legendary", "atk": 20, "def": 20, "hp": 40, "cost": 0}
                f.equip_item(golden)
                return f"Golden War Set equipped on {f.name}!"
            return "No active fighter"

        elif item_id == "skip_tier":
            self.arena_tier += 1
            self._spawn_enemy()
            return f"Advanced to tier {self.arena_tier}!"

        elif item_id == "name_change":
            return "Use SQUAD to rename (feature coming)"

        return f"Bought {item['name']}!"

    def get_diamond_bundles(self):
        return DIAMOND_BUNDLES

    # --- Story & Tutorial ---

    def get_current_story(self):
        return get_current_chapter(self.story_chapter)

    def get_pending_tutorial(self):
        return get_pending_tutorial(self)

    def mark_tutorial_shown(self, step_id):
        if step_id not in self.tutorial_shown:
            self.tutorial_shown.append(step_id)

    def start_story_boss(self):
        """Start the current chapter's story boss fight."""
        chapter = self.get_current_story()
        if not chapter:
            return None, "Story complete!"
        fighters = [f for f in self.fighters if f.alive and not f.on_expedition]
        if not fighters:
            return None, "No fighters!"
        boss = Enemy(tier=self.arena_tier + chapter["boss_tier_bonus"])
        boss.max_hp = int(boss.max_hp * chapter["boss_hp_mult"])
        boss.hp = boss.max_hp
        boss.attack = int(boss.attack * 1.5)
        boss.defense = int(boss.defense * 1.3)
        boss.gold_reward = int(boss.gold_reward * 5)
        boss.name = chapter["boss_name"]

        from game.battle import BattleState, BattlePhase as BP
        self.battle_mgr.state = BattleState()
        self.battle_mgr.state.player_fighters = fighters
        self.battle_mgr.state.enemies = [boss]
        self.battle_mgr.state.phase = BP.BOSS_INTRO
        self.battle_mgr.state.is_boss_fight = True

        return chapter, f"{boss.name} appears!"

    def complete_story_chapter(self):
        """Called when story boss is defeated."""
        chapter = self.get_current_story()
        if chapter:
            self.diamonds += chapter.get("reward_diamonds", 100)
            self.story_chapter += 1
            self.check_achievements()
            return chapter["completion"]
        return []

    # --- Ads ---

    def should_show_interstitial(self):
        if self.ads_removed:
            return False
        return self.wins > 0 and self.wins % 5 == 0

    def should_show_banner(self):
        return not self.ads_removed

    def on_rewarded_ad_watched(self):
        self.rewarded_ad_bonus_until = time.time() + 60
        today = time.strftime("%Y-%m-%d")
        if self.last_ad_day != today:
            self.ad_watches_today = 0
            self.last_ad_day = today
        self.ad_watches_today += 1
        return "2x gold for 60 seconds!"

    def can_watch_rewarded_ad(self):
        today = time.strftime("%Y-%m-%d")
        if self.last_ad_day != today:
            return True
        return self.ad_watches_today < 10

    def get_rewarded_ad_time_left(self):
        remaining = self.rewarded_ad_bonus_until - time.time()
        return f"2x GOLD: {int(remaining)}s" if remaining > 0 else ""

    # --- IAP ---

    def purchase_remove_ads(self):
        self.ads_removed = True

    def purchase_vip_idle(self):
        self.vip_idle_boost = True

    def purchase_diamonds(self, bundle_id):
        bundle = next((b for b in DIAMOND_BUNDLES if b["id"] == bundle_id), None)
        if bundle:
            self.diamonds += bundle["diamonds"]
            return f"+{bundle['diamonds']} diamonds!"
        return "Unknown bundle"

    def restore_purchases(self, purchase_ids: list[str]):
        for pid in purchase_ids:
            if pid == "remove_ads": self.ads_removed = True
            elif pid == "vip_idle": self.vip_idle_boost = True

    # --- Save / Load ---

    def save(self):
        data = {
            "gold": self.gold,
            "idle_gold_rate": self.idle_gold_rate,
            "active_fighter_idx": self.active_fighter_idx,
            "arena_tier": self.arena_tier,
            "wins": self.wins,
            "total_deaths": self.total_deaths,
            "graveyard": self.graveyard,
            "fighters": [f.to_dict() for f in self.fighters],
            "expedition_log": self.expedition_log[-20:],
            "idle_purchases": self.idle_purchases,
            "surgeon_uses": self.surgeon_uses,
            "total_gold_earned": self.total_gold_earned,
            "diamonds": self.diamonds,
            "achievements_unlocked": self.achievements_unlocked,
            "bosses_killed": self.bosses_killed,
            "story_chapter": self.story_chapter,
            "tutorial_shown": self.tutorial_shown,
            "extra_expedition_slots": self.extra_expedition_slots,
            "war_drums_until": self.war_drums_until,
            "ads_removed": self.ads_removed,
            "vip_idle_boost": self.vip_idle_boost,
            "rewarded_ad_bonus_until": self.rewarded_ad_bonus_until,
            "ad_watches_today": self.ad_watches_today,
            "last_ad_day": self.last_ad_day,
            "last_save_time": time.time(),
        }
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)
        return data

    def load(self, data=None):
        if data is None:
            if not os.path.exists(SAVE_PATH):
                self.fighters = [Fighter(name="Vorn")]
                self._spawn_enemy()
                return
            with open(SAVE_PATH, "r") as f:
                data = json.load(f)

        self.gold = data.get("gold", 100)
        self.idle_gold_rate = data.get("idle_gold_rate", 1.0)
        self.active_fighter_idx = data.get("active_fighter_idx", data.get("active_gladiator_idx", 0))
        self.arena_tier = data.get("arena_tier", 1)
        self.wins = data.get("wins", 0)
        self.total_deaths = data.get("total_deaths", 0)
        self.graveyard = data.get("graveyard", [])
        self.expedition_log = data.get("expedition_log", [])
        self.idle_purchases = data.get("idle_purchases", {})
        self.surgeon_uses = data.get("surgeon_uses", 0)
        self.total_gold_earned = data.get("total_gold_earned", 0.0)
        self.diamonds = data.get("diamonds", 0)
        self.achievements_unlocked = data.get("achievements_unlocked", [])
        self.bosses_killed = data.get("bosses_killed", 0)
        self.story_chapter = data.get("story_chapter", 0)
        self.tutorial_shown = data.get("tutorial_shown", [])
        self.extra_expedition_slots = data.get("extra_expedition_slots", 0)
        self.war_drums_until = data.get("war_drums_until", 0.0)
        self.ads_removed = data.get("ads_removed", False)
        self.vip_idle_boost = data.get("vip_idle_boost", False)
        self.rewarded_ad_bonus_until = data.get("rewarded_ad_bonus_until", 0.0)
        self.ad_watches_today = data.get("ad_watches_today", 0)
        self.last_ad_day = data.get("last_ad_day", "")

        fighters_data = data.get("fighters", data.get("gladiators", []))
        self.fighters = [Fighter.from_dict(fd) for fd in fighters_data]
        if not self.fighters or not any(f.alive for f in self.fighters):
            self.fighters = [Fighter(name="Vorn")]

        self.battle_mgr = BattleManager(self)
        self.check_expeditions()
        last_save = data.get("last_save_time", time.time())
        offline_gold = self.calculate_offline_earnings(last_save)
        if offline_gold > 0:
            self.gold += offline_gold
        self._spawn_enemy()

    def get_save_data_json(self) -> str:
        return json.dumps(self.save())
