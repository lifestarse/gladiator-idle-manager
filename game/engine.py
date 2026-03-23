"""Core game engine — battles, idle income, progression."""

import json
import os
import time

from game.models import Gladiator, Enemy, SHOP_ITEMS

SAVE_PATH = os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")


class GameEngine:

    def __init__(self):
        self.gold = 100.0
        self.idle_gold_rate = 1.0  # gold per second
        self.gladiators: list[Gladiator] = []
        self.active_gladiator_idx = 0
        self.arena_tier = 1
        self.wins = 0
        self.current_enemy: Enemy | None = None
        self.last_tick_time = time.time()

    # --- Gladiator management ---

    def get_active_gladiator(self) -> Gladiator | None:
        if not self.gladiators:
            return None
        idx = min(self.active_gladiator_idx, len(self.gladiators) - 1)
        return self.gladiators[idx]

    def hire_gladiator(self):
        cost = 50 * (1 + len(self.gladiators))
        if self.gold >= cost:
            self.gold -= cost
            g = Gladiator()
            self.gladiators.append(g)
            return f"Hired {g.name}!"
        return "Not enough gold!"

    def upgrade_gladiator(self, index):
        if index >= len(self.gladiators):
            return "Invalid gladiator"
        g = self.gladiators[index]
        if self.gold >= g.upgrade_cost:
            self.gold -= g.upgrade_cost
            g.level += 1
            g.hp = g.max_hp
            return f"{g.name} upgraded to Lv.{g.level}!"
        return "Not enough gold!"

    # --- Battle system ---

    def _spawn_enemy(self):
        self.current_enemy = Enemy(tier=self.arena_tier)

    def do_battle_tick(self) -> str:
        gladiator = self.get_active_gladiator()
        if not gladiator:
            self.hire_gladiator()
            gladiator = self.get_active_gladiator()

        if not self.current_enemy or self.current_enemy.hp <= 0:
            self._spawn_enemy()

        enemy = self.current_enemy
        log_lines = []

        # Player attacks
        raw = gladiator.deal_damage()
        actual = enemy.take_damage(raw)
        log_lines.append(f"{gladiator.name} hits {enemy.name} for {actual} dmg")

        if enemy.hp <= 0:
            reward = enemy.gold_reward
            self.gold += reward
            self.wins += 1
            # Tier up every 5 wins
            if self.wins % 5 == 0:
                self.arena_tier += 1
            log_lines.append(f"Victory! +{reward} gold")
            gladiator.hp = min(gladiator.hp + gladiator.max_hp // 4, gladiator.max_hp)
            self._spawn_enemy()
            return "\n".join(log_lines)

        # Enemy attacks
        raw = enemy.deal_damage()
        actual = gladiator.take_damage(raw)
        log_lines.append(f"{enemy.name} hits {gladiator.name} for {actual} dmg")

        if gladiator.hp <= 0:
            log_lines.append(f"{gladiator.name} defeated! Healing...")
            gladiator.heal()
            self._spawn_enemy()

        return "\n".join(log_lines)

    # --- Idle income ---

    def idle_tick(self, dt):
        self.gold += self.idle_gold_rate * dt

    def calculate_offline_earnings(self, last_time):
        now = time.time()
        elapsed = min(now - last_time, 3600 * 8)  # Cap at 8 hours
        return self.idle_gold_rate * elapsed

    # --- Shop ---

    def get_shop_items(self):
        return [
            {**item, "affordable": self.gold >= item["cost"]}
            for item in SHOP_ITEMS
        ]

    def buy_item(self, item_id):
        item = next((i for i in SHOP_ITEMS if i["id"] == item_id), None)
        if not item:
            return "Item not found"
        if self.gold < item["cost"]:
            return "Not enough gold"

        self.gold -= item["cost"]
        effect = item["effect"]

        if "idle_gold_rate" in effect:
            self.idle_gold_rate += effect["idle_gold_rate"]
        if "heal" in effect:
            g = self.get_active_gladiator()
            if g:
                g.heal()
        if "base_attack" in effect:
            g = self.get_active_gladiator()
            if g:
                g.base_attack += effect["base_attack"]
        if "base_defense" in effect:
            g = self.get_active_gladiator()
            if g:
                g.base_defense += effect["base_defense"]

        return f"Bought {item['name']}!"

    # --- Save / Load ---

    def save(self):
        data = {
            "gold": self.gold,
            "idle_gold_rate": self.idle_gold_rate,
            "active_gladiator_idx": self.active_gladiator_idx,
            "arena_tier": self.arena_tier,
            "wins": self.wins,
            "gladiators": [g.to_dict() for g in self.gladiators],
            "last_save_time": time.time(),
        }
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)

    def load(self):
        if not os.path.exists(SAVE_PATH):
            # First launch — give starter gladiator
            self.gladiators = [Gladiator(name="Spartacus")]
            self._spawn_enemy()
            return

        with open(SAVE_PATH, "r") as f:
            data = json.load(f)

        self.gold = data.get("gold", 100)
        self.idle_gold_rate = data.get("idle_gold_rate", 1.0)
        self.active_gladiator_idx = data.get("active_gladiator_idx", 0)
        self.arena_tier = data.get("arena_tier", 1)
        self.wins = data.get("wins", 0)
        self.gladiators = [
            Gladiator.from_dict(gd) for gd in data.get("gladiators", [])
        ]

        if not self.gladiators:
            self.gladiators = [Gladiator(name="Spartacus")]

        # Offline earnings
        last_save = data.get("last_save_time", time.time())
        offline_gold = self.calculate_offline_earnings(last_save)
        if offline_gold > 0:
            self.gold += offline_gold

        self._spawn_enemy()
