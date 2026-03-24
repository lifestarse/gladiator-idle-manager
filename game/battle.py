"""
Turn-based battle system with animated phases.

Two battle modes:
1. Auto-Battle (The Pit) — all available fighters vs waves of enemies
2. Boss Challenge — turn-by-turn tactical boss fight with skip option

Battle flows as a state machine:
  IDLE -> STARTING -> TURN_PLAYER -> TURN_ENEMY -> (NEXT_TURN | VICTORY | DEFEAT)
"""

import random
from enum import Enum, auto


class BattlePhase(Enum):
    IDLE = auto()
    STARTING = auto()         # intro animation
    TURN_PLAYER = auto()      # player's fighter attacks
    TURN_ENEMY = auto()       # enemy attacks
    TURN_RESOLVE = auto()     # resolve damage, check deaths
    VICTORY = auto()
    DEFEAT = auto()
    BOSS_INTRO = auto()       # boss special intro


class BattleEvent:
    """Single event in the battle log (for animation)."""
    def __init__(self, event_type, attacker="", defender="", damage=0,
                 message="", is_kill=False, is_crit=False, is_boss=False):
        self.event_type = event_type  # "attack", "death", "victory", "boss_intro", "heal"
        self.attacker = attacker
        self.defender = defender
        self.damage = damage
        self.message = message
        self.is_kill = is_kill
        self.is_crit = is_crit
        self.is_boss = is_boss


class BattleState:
    """Tracks state of an ongoing battle."""

    def __init__(self):
        self.phase = BattlePhase.IDLE
        self.turn_number = 0
        self.player_fighters = []    # list of Fighter refs (alive, not on expedition)
        self.current_fighter_idx = 0
        self.enemies = []            # list of Enemy refs
        self.current_enemy_idx = 0
        self.events: list[BattleEvent] = []
        self.is_boss_fight = False
        self.boss_defeated = False
        self.all_defeated = False
        self.gold_earned = 0
        self.skip_mode = False

    @property
    def current_fighter(self):
        if 0 <= self.current_fighter_idx < len(self.player_fighters):
            f = self.player_fighters[self.current_fighter_idx]
            if f.alive and f.hp > 0:
                return f
        return None

    @property
    def current_enemy(self):
        if 0 <= self.current_enemy_idx < len(self.enemies):
            e = self.enemies[self.current_enemy_idx]
            if e.hp > 0:
                return e
        return None

    def next_alive_fighter(self):
        """Move to next alive fighter. Returns False if none left."""
        for i in range(len(self.player_fighters)):
            idx = (self.current_fighter_idx + 1 + i) % len(self.player_fighters)
            f = self.player_fighters[idx]
            if f.alive and f.hp > 0:
                self.current_fighter_idx = idx
                return True
        return False

    def next_alive_enemy(self):
        """Move to next alive enemy. Returns False if none left."""
        for i in range(len(self.enemies)):
            idx = (self.current_enemy_idx + 1 + i) % len(self.enemies)
            if self.enemies[idx].hp > 0:
                self.current_enemy_idx = idx
                return True
        return False

    def any_fighters_alive(self):
        return any(f.alive and f.hp > 0 for f in self.player_fighters)

    def any_enemies_alive(self):
        return any(e.hp > 0 for e in self.enemies)


class BattleManager:
    """Manages turn-based battles with event generation for animation."""

    def __init__(self, engine):
        self.engine = engine
        self.state = BattleState()

    def start_auto_battle(self):
        """Start auto-battle: all fighters vs wave of enemies."""
        fighters = [f for f in self.engine.fighters
                    if f.alive and not f.on_expedition]
        if not fighters:
            return [BattleEvent("message", message="No fighters available!")]

        from game.models import Enemy
        # Spawn enemies = number of fighters (wave)
        num_enemies = max(1, len(fighters))
        enemies = [Enemy(tier=self.engine.arena_tier) for _ in range(num_enemies)]

        self.state = BattleState()
        self.state.player_fighters = fighters
        self.state.enemies = enemies
        self.state.phase = BattlePhase.STARTING
        self.state.is_boss_fight = False

        return [BattleEvent("message", message=f"BATTLE START! {len(fighters)}v{len(enemies)}")]

    def start_boss_fight(self):
        """Start boss challenge: all fighters vs 1 mega-boss."""
        fighters = [f for f in self.engine.fighters
                    if f.alive and not f.on_expedition]
        if not fighters:
            return [BattleEvent("message", message="No fighters available!")]

        from game.models import Enemy, DifficultyScaler
        boss_tier = self.engine.arena_tier + 2
        boss = Enemy(tier=boss_tier)
        # Boss has 3x HP and 1.5x stats
        boss.max_hp = int(boss.max_hp * 3)
        boss.hp = boss.max_hp
        boss.attack = int(boss.attack * 1.5)
        boss.defense = int(boss.defense * 1.3)
        boss.gold_reward = int(boss.gold_reward * 5)
        boss.name = f"BOSS: {boss.name}"

        self.state = BattleState()
        self.state.player_fighters = fighters
        self.state.enemies = [boss]
        self.state.phase = BattlePhase.BOSS_INTRO
        self.state.is_boss_fight = True

        return [BattleEvent("boss_intro", message=f"{boss.name} appears! HP: {boss.hp}",
                            is_boss=True)]

    def do_turn(self) -> list[BattleEvent]:
        """Execute one turn of combat. Returns list of events for animation."""
        s = self.state
        events = []

        if s.phase in (BattlePhase.IDLE, BattlePhase.VICTORY, BattlePhase.DEFEAT):
            return events

        if s.phase in (BattlePhase.STARTING, BattlePhase.BOSS_INTRO):
            s.phase = BattlePhase.TURN_PLAYER
            s.turn_number = 1
            events.append(BattleEvent("message", message=f"Turn {s.turn_number}"))
            return events

        # --- All fighters attack ---
        for i, fighter in enumerate(s.player_fighters):
            if not fighter.alive or fighter.hp <= 0:
                continue

            # Pick target: current enemy or first alive
            target = s.current_enemy
            if not target or target.hp <= 0:
                if not s.next_alive_enemy():
                    break
                target = s.current_enemy
            if not target:
                break

            # Attack
            is_crit = random.random() < 0.15
            raw = fighter.deal_damage()
            if is_crit:
                raw = int(raw * 1.8)
            actual = target.take_damage(raw)

            event = BattleEvent(
                "attack", attacker=fighter.name, defender=target.name,
                damage=actual, is_crit=is_crit,
                message=f"{fighter.name} {'CRIT! ' if is_crit else ''}hits {target.name} for {actual}"
            )
            events.append(event)

            if target.hp <= 0:
                events.append(BattleEvent(
                    "death", defender=target.name, is_kill=True,
                    message=f"{target.name} destroyed!",
                    is_boss=s.is_boss_fight,
                ))
                reward = target.gold_reward
                s.gold_earned += reward
                self.engine.gold += reward
                self.engine.total_gold_earned += reward
                fighter.kills += 1

                if not s.any_enemies_alive():
                    break
                s.next_alive_enemy()

        # Check victory
        if not s.any_enemies_alive():
            s.phase = BattlePhase.VICTORY
            self.engine.wins += len(s.enemies)
            if self.engine.wins % 3 == 0:
                self.engine.arena_tier += 1
            # Heal fighters partially
            for f in s.player_fighters:
                if f.alive:
                    f.hp = min(f.hp + f.max_hp // 7, f.max_hp)
            events.append(BattleEvent(
                "victory", message=f"VICTORY! +{s.gold_earned}g",
                damage=s.gold_earned,
            ))
            return events

        # --- All enemies attack ---
        for enemy in s.enemies:
            if enemy.hp <= 0:
                continue

            # Pick a random alive fighter
            alive_fighters = [f for f in s.player_fighters if f.alive and f.hp > 0]
            if not alive_fighters:
                break
            target = random.choice(alive_fighters)

            is_crit = random.random() < 0.10
            raw = enemy.deal_damage()
            if is_crit:
                raw = int(raw * 1.8)
            actual = target.take_damage(raw)

            events.append(BattleEvent(
                "attack", attacker=enemy.name, defender=target.name,
                damage=actual, is_crit=is_crit,
                message=f"{enemy.name} {'CRIT! ' if is_crit else ''}hits {target.name} for {actual}"
            ))

            if target.hp <= 0:
                # Permadeath check
                died_forever = target.check_permadeath()
                if died_forever:
                    self.engine.total_deaths += 1
                    self.engine.graveyard.append({
                        "name": target.name,
                        "level": target.level,
                        "kills": target.kills,
                    })
                    events.append(BattleEvent(
                        "death", defender=target.name, is_kill=True,
                        message=f"{target.name} has FALLEN FOREVER!",
                    ))
                else:
                    events.append(BattleEvent(
                        "death", defender=target.name,
                        message=f"{target.name} knocked out! Injury #{target.injuries}",
                    ))

        # Check defeat
        if not s.any_fighters_alive():
            s.phase = BattlePhase.DEFEAT
            events.append(BattleEvent(
                "defeat", message="ALL FIGHTERS DOWN!",
            ))
            # Heal survivors for next battle
            for f in s.player_fighters:
                if f.alive:
                    f.heal()
            return events

        # Next turn
        s.turn_number += 1
        events.append(BattleEvent("message", message=f"Turn {s.turn_number}"))
        return events

    def do_full_battle(self) -> list[BattleEvent]:
        """Run entire battle instantly (skip mode). Returns all events."""
        all_events = []
        while self.state.phase not in (BattlePhase.VICTORY, BattlePhase.DEFEAT,
                                        BattlePhase.IDLE):
            events = self.do_turn()
            all_events.extend(events)
            if len(all_events) > 200:  # safety limit
                break
        return all_events

    @property
    def is_active(self):
        return self.state.phase not in (BattlePhase.IDLE, BattlePhase.VICTORY,
                                         BattlePhase.DEFEAT)
