"""Core game engine — battles, economy, ads, IAP, cloud save."""

import json
import os
import random
import time

from game.models import (
    Fighter, Enemy, ALL_FORGE_ITEMS,
    EXPEDITIONS, RELICS, DifficultyScaler,
    get_dynamic_shop_items,
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

        # Economy tracking — for inflation
        self.idle_purchases: dict[str, int] = {}  # item_id -> times bought
        self.surgeon_uses = 0
        self.total_gold_earned = 0.0

        # Monetization state
        self.ads_removed = False
        self.vip_idle_boost = False  # 1.5x passive income
        self.rewarded_ad_bonus_until = 0.0  # timestamp: 2x gold until this time
        self.ad_watches_today = 0
        self.last_ad_day = ""

    # --- aliases ---
    @property
    def gladiators(self):
        return self.fighters

    @property
    def active_gladiator_idx(self):
        return self.active_fighter_idx

    @active_gladiator_idx.setter
    def active_gladiator_idx(self, val):
        self.active_fighter_idx = val

    # --- Effective idle rate (with IAP multiplier) ---

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

    def hire_gladiator(self):
        alive_count = len([f for f in self.fighters if f.alive])
        cost = DifficultyScaler.hire_cost(alive_count)
        if self.gold >= cost:
            self.gold -= cost
            f = Fighter()
            self.fighters.append(f)
            return f"Recruited {f.name}! (next: {DifficultyScaler.hire_cost(alive_count + 1)}g)"
        return f"Need {cost}g to recruit!"

    @property
    def hire_cost(self):
        alive_count = len([f for f in self.fighters if f.alive])
        return DifficultyScaler.hire_cost(alive_count)

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
            return f"{f.name} trained to Lv.{f.level}!"
        return "Not enough gold!"

    def dismiss_dead(self, index):
        if index < len(self.fighters) and not self.fighters[index].alive:
            self.fighters.pop(index)
            if self.active_fighter_idx >= len(self.fighters):
                self.active_fighter_idx = max(0, len(self.fighters) - 1)

    # --- Battle system ---

    def _spawn_enemy(self):
        self.current_enemy = Enemy(tier=self.arena_tier)

    def do_battle_tick(self) -> str:
        fighter = self.get_active_gladiator()
        if not fighter:
            return "No fighters available!"

        if not self.current_enemy or self.current_enemy.hp <= 0:
            self._spawn_enemy()

        enemy = self.current_enemy
        log_lines = []

        # Player attacks
        raw = fighter.deal_damage()
        actual = enemy.take_damage(raw)
        log_lines.append(f"{fighter.name} hits {enemy.name} for {actual}")

        if enemy.hp <= 0:
            reward = enemy.gold_reward
            # Rewarded ad bonus
            if time.time() < self.rewarded_ad_bonus_until:
                reward = int(reward * 2)
            self.gold += reward
            self.total_gold_earned += reward
            self.wins += 1
            fighter.kills += 1
            # Tier up every 3 wins (faster progression = harder faster)
            if self.wins % 3 == 0:
                self.arena_tier += 1
            log_lines.append(f"Victory! +{reward} gold")
            # Heal only 15% after win (was 25%)
            fighter.hp = min(fighter.hp + fighter.max_hp // 7, fighter.max_hp)
            self._spawn_enemy()
            return "\n".join(log_lines)

        # Enemy attacks
        raw = enemy.deal_damage()
        actual = fighter.take_damage(raw)
        log_lines.append(f"{enemy.name} hits {fighter.name} for {actual}")

        if fighter.hp <= 0:
            died = fighter.check_permadeath()
            if died:
                self.total_deaths += 1
                self.graveyard.append({
                    "name": fighter.name,
                    "level": fighter.level,
                    "kills": fighter.kills,
                })
                log_lines.append(f"{fighter.name} has FALLEN forever! (RIP)")
                self.get_active_gladiator()
            else:
                log_lines.append(
                    f"{fighter.name} barely survived! Injury #{fighter.injuries} "
                    f"(death risk: {fighter.death_chance:.0%})"
                )
                fighter.heal()
            self._spawn_enemy()

        return "\n".join(log_lines)

    # --- Forge / Equipment ---

    def get_forge_items(self):
        return [
            {**item, "affordable": self.gold >= item["cost"]}
            for item in ALL_FORGE_ITEMS
        ]

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
        result = []
        for exp in EXPEDITIONS:
            result.append({
                **exp,
                "affordable": True,
                "duration_text": self._fmt_duration(exp["duration"]),
            })
        return result

    def send_on_expedition(self, fighter_idx, expedition_id):
        if fighter_idx >= len(self.fighters):
            return "Invalid fighter"
        f = self.fighters[fighter_idx]
        if not f.alive:
            return f"{f.name} is dead"
        if f.on_expedition:
            return f"{f.name} is already on expedition"
        exp = next((e for e in EXPEDITIONS if e["id"] == expedition_id), None)
        if not exp:
            return "Unknown expedition"
        if f.level < exp["min_level"]:
            return f"Need Lv.{exp['min_level']}+ ({f.name} is Lv.{f.level})"
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
                    self.graveyard.append({
                        "name": f.name, "level": f.level, "kills": f.kills,
                    })
                    msg = f"{f.name} was KILLED during {exp['name']}!"
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
                msg_parts.append(f"Found relic: {relic['name']} [{rarity}]!")

            if random.random() < exp["danger"] * 0.5:
                f.injuries += 1
                msg_parts.append(f"Got injured (injuries: {f.injuries})")

            f.heal()
            msg = " ".join(msg_parts)
            results.append(msg)
            self.expedition_log.append(msg)
        return results

    def get_expedition_status(self):
        now = time.time()
        statuses = []
        for f in self.fighters:
            if not f.on_expedition or not f.alive:
                continue
            remaining = max(0, f.expedition_end - now)
            exp = next((e for e in EXPEDITIONS if e["id"] == f.expedition_id), None)
            statuses.append({
                "fighter_name": f.name,
                "expedition_name": exp["name"] if exp else "?",
                "remaining": remaining,
                "remaining_text": self._fmt_duration(int(remaining)),
            })
        return statuses

    def _fmt_duration(self, seconds):
        if seconds >= 3600:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
        if seconds >= 60:
            return f"{seconds // 60}m {seconds % 60}s"
        return f"{seconds}s"

    # --- Idle income ---

    def idle_tick(self, dt):
        self.gold += self.effective_idle_rate * dt
        self.total_gold_earned += self.effective_idle_rate * dt
        self.check_expeditions()

    def calculate_offline_earnings(self, last_time):
        now = time.time()
        elapsed = min(now - last_time, 3600 * 8)
        return self.effective_idle_rate * elapsed

    # --- Market (dynamic pricing) ---

    def get_shop_items(self):
        items = get_dynamic_shop_items(
            self.arena_tier, self.idle_purchases, self.surgeon_uses
        )
        return [{**item, "affordable": self.gold >= item["cost"]} for item in items]

    def buy_item(self, item_id):
        items = get_dynamic_shop_items(
            self.arena_tier, self.idle_purchases, self.surgeon_uses
        )
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
            if f:
                f.heal()
        if "base_attack" in effect:
            f = self.get_active_gladiator()
            if f:
                f.base_attack += effect["base_attack"]
        if "base_defense" in effect:
            f = self.get_active_gladiator()
            if f:
                f.base_defense += effect["base_defense"]
        if "cure_injury" in effect:
            f = self.get_active_gladiator()
            if f and f.injuries > 0:
                f.injuries = max(0, f.injuries - effect["cure_injury"])
                self.surgeon_uses += 1

        return f"Bought {item['name']}!"

    # --- Ads ---

    def should_show_interstitial(self):
        """Show interstitial ad every 5 fights (if ads not removed)."""
        if self.ads_removed:
            return False
        return self.wins > 0 and self.wins % 5 == 0

    def should_show_banner(self):
        return not self.ads_removed

    def on_rewarded_ad_watched(self):
        """Player watched rewarded ad — 2x gold for 60 seconds."""
        self.rewarded_ad_bonus_until = time.time() + 60
        today = time.strftime("%Y-%m-%d")
        if self.last_ad_day != today:
            self.ad_watches_today = 0
            self.last_ad_day = today
        self.ad_watches_today += 1
        return "2x gold for 60 seconds!"

    def can_watch_rewarded_ad(self):
        """Limit to 10 rewarded ads per day."""
        today = time.strftime("%Y-%m-%d")
        if self.last_ad_day != today:
            return True
        return self.ad_watches_today < 10

    def get_rewarded_ad_time_left(self):
        remaining = self.rewarded_ad_bonus_until - time.time()
        if remaining <= 0:
            return ""
        return f"2x GOLD: {int(remaining)}s"

    # --- IAP ---

    def purchase_remove_ads(self):
        """IAP: Remove ads for 100 UAH."""
        self.ads_removed = True
        return "Ads removed!"

    def purchase_vip_idle(self):
        """IAP: 1.5x passive income permanently."""
        self.vip_idle_boost = True
        return "VIP: 1.5x idle income activated!"

    def restore_purchases(self, purchase_ids: list[str]):
        """Restore IAP from store receipts."""
        for pid in purchase_ids:
            if pid == "remove_ads":
                self.ads_removed = True
            elif pid == "vip_idle":
                self.vip_idle_boost = True

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
            "ads_removed": self.ads_removed,
            "vip_idle_boost": self.vip_idle_boost,
            "rewarded_ad_bonus_until": self.rewarded_ad_bonus_until,
            "ad_watches_today": self.ad_watches_today,
            "last_ad_day": self.last_ad_day,
            "last_save_time": time.time(),
        }
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)
        return data  # return for cloud save

    def load(self, data=None):
        """Load from dict (cloud) or local file."""
        if data is None:
            if not os.path.exists(SAVE_PATH):
                self.fighters = [Fighter(name="Vorn")]
                self._spawn_enemy()
                return
            with open(SAVE_PATH, "r") as f:
                data = json.load(f)

        self.gold = data.get("gold", 100)
        self.idle_gold_rate = data.get("idle_gold_rate", 1.0)
        self.active_fighter_idx = data.get("active_fighter_idx",
                                           data.get("active_gladiator_idx", 0))
        self.arena_tier = data.get("arena_tier", 1)
        self.wins = data.get("wins", 0)
        self.total_deaths = data.get("total_deaths", 0)
        self.graveyard = data.get("graveyard", [])
        self.expedition_log = data.get("expedition_log", [])
        self.idle_purchases = data.get("idle_purchases", {})
        self.surgeon_uses = data.get("surgeon_uses", 0)
        self.total_gold_earned = data.get("total_gold_earned", 0.0)
        self.ads_removed = data.get("ads_removed", False)
        self.vip_idle_boost = data.get("vip_idle_boost", False)
        self.rewarded_ad_bonus_until = data.get("rewarded_ad_bonus_until", 0.0)
        self.ad_watches_today = data.get("ad_watches_today", 0)
        self.last_ad_day = data.get("last_ad_day", "")

        fighters_data = data.get("fighters", data.get("gladiators", []))
        self.fighters = [Fighter.from_dict(fd) for fd in fighters_data]

        if not self.fighters or not any(f.alive for f in self.fighters):
            self.fighters = [Fighter(name="Vorn")]

        self.check_expeditions()

        last_save = data.get("last_save_time", time.time())
        offline_gold = self.calculate_offline_earnings(last_save)
        if offline_gold > 0:
            self.gold += offline_gold

        self._spawn_enemy()

    def get_save_data_json(self) -> str:
        """Get save data as JSON string for cloud upload."""
        return json.dumps(self.save())
