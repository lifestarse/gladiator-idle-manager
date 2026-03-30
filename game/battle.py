# Build: 12
"""
Turn-based battle system with luck-based combat.

Two battle modes:
1. Auto-Battle (The Pit) -- all available fighters vs waves of enemies
2. Boss Challenge -- turn-by-turn tactical boss fight with skip option

Combat is luck-heavy: crits deal scaling damage, dodges negate hits entirely.
A weak but agile assassin can outperform a strong brute through fortunate rolls.
"""

import random
from enum import Enum, auto
from game.models import ENCHANTMENT_TYPES, fmt_num
from game.localization import t


class BattlePhase(Enum):
    IDLE = auto()
    STARTING = auto()
    TURN_PLAYER = auto()
    TURN_ENEMY = auto()
    TURN_RESOLVE = auto()
    VICTORY = auto()
    DEFEAT = auto()
    BOSS_INTRO = auto()


class BattleEvent:
    """Single event in the battle log (for animation)."""
    def __init__(self, event_type, attacker="", defender="", damage=0,
                 message="", is_kill=False, is_crit=False, is_boss=False,
                 is_dodge=False):
        self.event_type = event_type
        self.attacker = attacker
        self.defender = defender
        self.damage = damage
        self.message = message
        self.is_kill = is_kill
        self.is_crit = is_crit
        self.is_boss = is_boss
        self.is_dodge = is_dodge


class EnemyStatusTracker:
    """Tracks status effect state for a single enemy during battle."""
    def __init__(self, original_attack, original_defense=0):
        self.status_buildup = {}  # dynamic: populated on first hit per enchantment
        self.active_effects = []  # list of active status effect dicts
        self.original_attack = original_attack
        self.original_defense = original_defense
        self.skip_next_turn = False  # paralyze flag


class BattleState:
    """Tracks state of an ongoing battle."""

    def __init__(self):
        self.phase = BattlePhase.IDLE
        self.turn_number = 0
        self.player_fighters = []
        self.current_fighter_idx = 0
        self.enemies = []
        self.current_enemy_idx = 0
        self.events = []
        self.is_boss_fight = False
        self.boss_defeated = False
        self.all_defeated = False
        self.gold_earned = 0
        self.skip_mode = False
        self.enemy_status: dict = {}

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
        for i in range(len(self.player_fighters)):
            idx = (self.current_fighter_idx + 1 + i) % len(self.player_fighters)
            f = self.player_fighters[idx]
            if f.alive and f.hp > 0:
                self.current_fighter_idx = idx
                return True
        return False

    def next_alive_enemy(self):
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


def _init_enemy_status(state, enemy):
    """Initialize status effect tracking for an enemy in BattleState."""
    state.enemy_status[id(enemy)] = EnemyStatusTracker(enemy.attack, getattr(enemy, 'defense', 0))


def _trigger_enchantment(state, target, ench_id, ench):
    """Trigger an enchantment effect on a target. Returns list of BattleEvents."""
    events = []
    tracker = state.enemy_status[id(target)]
    effect = ench["effect"]

    if effect == "burst":
        # bleeding, burn
        dmg = max(1, int(target.max_hp * ench["burst_pct"]))
        target.hp = max(0, target.hp - dmg)
        name = ench.get("name", ench_id).upper()
        events.append(BattleEvent("status", defender=target.name, damage=dmg,
            message=f"{name}! {target.name} -{fmt_num(dmg)}HP!"))

    elif effect == "burst_debuff":
        # frostbite
        dmg = max(1, int(target.max_hp * ench["burst_pct"]))
        target.hp = max(0, target.hp - dmg)
        reduction = ench.get("atk_reduction_pct", ench.get("reduction_pct", 0.2))
        target.attack = int(tracker.original_attack * (1 - reduction))
        tracker.active_effects.append({
            "type": "atk_debuff",
            "turns_left": ench["debuff_turns"],
        })
        events.append(BattleEvent("status", defender=target.name, damage=dmg,
            message=f"FROSTBITE! {target.name} -{fmt_num(dmg)}HP, ATK down!"))

    elif effect == "dot":
        # poison
        tracker.active_effects.append({
            "type": "poison_dot",
            "turns_left": ench["dot_turns"],
            "dot_pct": ench["dot_pct"],
        })
        events.append(BattleEvent("status", defender=target.name,
            message=f"POISON! {target.name} poisoned {ench['dot_turns']}t!"))

    elif effect == "skip_turn":
        # paralyze
        tracker.skip_next_turn = True
        events.append(BattleEvent("status", defender=target.name,
            message=f"PARALYZE! {target.name} stunned!"))

    elif effect == "def_reduction":
        # corruption
        reduction = ench.get("reduction_pct", 0.3)
        target.defense = int(tracker.original_defense * (1 - reduction))
        tracker.active_effects.append({
            "type": "def_debuff",
            "turns_left": ench.get("debuff_turns", 3),
        })
        events.append(BattleEvent("status", defender=target.name,
            message=f"CORRUPTION! {target.name} DEF down!"))

    elif effect == "chain_burst":
        # lightning — hit target + all other alive enemies
        dmg = max(1, int(target.max_hp * ench["burst_pct"]))
        target.hp = max(0, target.hp - dmg)
        events.append(BattleEvent("status", defender=target.name, damage=dmg,
            message=f"LIGHTNING! {target.name} -{fmt_num(dmg)}HP!"))
        for other in state.enemies:
            if other is not target and other.hp > 0:
                chain_dmg = max(1, int(other.max_hp * ench["burst_pct"]))
                other.hp = max(0, other.hp - chain_dmg)
                events.append(BattleEvent("status", defender=other.name, damage=chain_dmg,
                    message=f"CHAIN! {other.name} -{fmt_num(chain_dmg)}HP!"))

    elif effect == "atk_reduction":
        # weaken
        reduction = ench.get("reduction_pct", 0.25)
        target.attack = int(tracker.original_attack * (1 - reduction))
        tracker.active_effects.append({
            "type": "atk_debuff",
            "turns_left": ench.get("debuff_turns", 4),
        })
        events.append(BattleEvent("status", defender=target.name,
            message=f"WEAKEN! {target.name} ATK down!"))

    elif effect == "lifesteal":
        # drain — heal the attacker
        heal_pct = ench.get("heal_pct", 0.1)
        for fighter in state.player_fighters:
            if fighter.alive and fighter.hp > 0:
                weapon = fighter.equipment.get("weapon")
                if weapon and weapon.get("enchantment") == ench_id:
                    heal = max(1, int(fighter.max_hp * heal_pct))
                    fighter.hp = min(fighter.max_hp, fighter.hp + heal)
                    events.append(BattleEvent("status", defender=target.name,
                        message=f"DRAIN! {fighter.name} +{fmt_num(heal)}HP!"))
                    break

    elif effect == "burst_conditional":
        # holy_fire — more damage vs bosses
        if getattr(target, 'is_boss', False):
            pct = ench.get("burst_pct_boss", 0.25)
        else:
            pct = ench.get("burst_pct_normal", 0.10)
        dmg = max(1, int(target.max_hp * pct))
        target.hp = max(0, target.hp - dmg)
        events.append(BattleEvent("status", defender=target.name, damage=dmg,
            message=f"HOLY FIRE! {target.name} -{fmt_num(dmg)}HP!"))

    return events


def _process_status_ticks(state):
    """Process DOT/debuff ticks on all enemies. Returns list of BattleEvents."""
    events = []
    for enemy in state.enemies:
        if enemy.hp <= 0:
            continue
        eid = id(enemy)
        if eid not in state.enemy_status:
            continue
        tracker = state.enemy_status[eid]
        remaining = []
        for eff in tracker.active_effects:
            eff["turns_left"] -= 1
            if eff["type"] == "poison_dot":
                dot_dmg = max(1, int(enemy.max_hp * eff["dot_pct"]))
                enemy.hp = max(0, enemy.hp - dot_dmg)
                events.append(BattleEvent("status", defender=enemy.name, damage=dot_dmg,
                    message=f"POISON: {enemy.name} -{fmt_num(dot_dmg)}HP!"))
            if eff["turns_left"] > 0:
                remaining.append(eff)
            else:
                # Restore stats when debuffs expire
                if eff["type"] == "atk_debuff":
                    enemy.attack = tracker.original_attack
                    events.append(BattleEvent("status", defender=enemy.name,
                        message=f"{enemy.name} ATK restored!"))
                elif eff["type"] == "def_debuff":
                    enemy.defense = tracker.original_defense
                    events.append(BattleEvent("status", defender=enemy.name,
                        message=f"{enemy.name} DEF restored!"))
        tracker.active_effects = remaining
    return events


def _resolve_attack(attacker, defender, is_boss=False):
    """Resolve a single attack: crit -> damage -> dodge -> event.
    Returns (BattleEvent, actual_damage, is_crit)."""
    is_crit = random.random() < attacker.crit_chance
    raw = attacker.deal_damage()
    if is_crit:
        raw = int(raw * attacker.crit_mult)
    actual = defender.take_damage(raw)
    if actual == 0:
        ev = BattleEvent(
            "attack", attacker=attacker.name, defender=defender.name,
            damage=0, is_dodge=True,
            message=f"{defender.name} DODGED {attacker.name}'s attack!"
        )
    else:
        ev = BattleEvent(
            "attack", attacker=attacker.name, defender=defender.name,
            damage=actual, is_crit=is_crit,
            message=f"{attacker.name} {'CRIT! ' if is_crit else ''}hits {defender.name} for {fmt_num(actual)}"
        )
    return ev, actual, is_crit


class BattleManager:
    """Manages turn-based battles with luck-based combat."""

    def __init__(self, engine):
        self.engine = engine
        self.state = BattleState()

    def start_auto_battle(self):
        fighters = [f for f in self.engine.fighters
                    if f.available]
        if not fighters:
            return [BattleEvent("message", message="No fighters available!")]

        from game.models import Enemy
        from game.data_loader import data_loader
        import random as _rand
        num_enemies = max(1, len(fighters))
        # First enemy is the previewed current_enemy, rest are new
        enemies = []
        boss_revenge = False
        if self.engine.current_enemy:
            if getattr(self.engine.current_enemy, 'is_boss', False):
                boss_revenge = True
            enemies.append(self.engine.current_enemy)
        tier = self.engine.arena_tier
        normals = data_loader.normals_by_tier.get(tier)
        while len(enemies) < num_enemies:
            if normals:
                template = _rand.choice(normals)
                enemies.append(Enemy.from_template(template, tier))
            else:
                enemies.append(Enemy(tier=tier))

        self.state = BattleState()
        self.state.player_fighters = fighters
        self.state.enemies = enemies
        self.state.phase = BattlePhase.STARTING
        self.state.is_boss_fight = False
        for e in enemies:
            _init_enemy_status(self.state, e)

        events = []
        if boss_revenge:
            events.append(BattleEvent("message", message=t("boss_revenge")))
        events.append(BattleEvent("message", message=f"BATTLE START! {len(fighters)}v{len(enemies)}"))
        return events

    def start_boss_fight(self):
        fighters = [f for f in self.engine.fighters
                    if f.available]
        if not fighters:
            return [BattleEvent("message", message="No fighters available!")]

        boss = self.engine.current_enemy

        self.state = BattleState()
        self.state.player_fighters = fighters
        self.state.enemies = [boss]
        self.state.phase = BattlePhase.BOSS_INTRO
        self.state.is_boss_fight = True
        _init_enemy_status(self.state, boss)

        return [BattleEvent("boss_intro", message=f"{boss.name} appears! HP: {fmt_num(boss.hp)}",
                            is_boss=True)]

    def _declare_victory(self, events):
        """Mark battle as won, heal fighters, emit victory event."""
        s = self.state
        s.phase = BattlePhase.VICTORY
        self.engine.wins += len(s.enemies)
        if s.is_boss_fight:
            self.engine.arena_tier += 1
        for f in s.player_fighters:
            if f.alive:
                f.hp = f.max_hp
        events.append(BattleEvent(
            "victory", message=f"VICTORY! +{fmt_num(s.gold_earned)}g",
            damage=s.gold_earned,
        ))

    def _status_tick_phase(self, events):
        """Process status effect ticks (DOT/debuffs) and check for status kills.

        Returns True if all enemies are dead (victory via status effects)."""
        s = self.state
        status_events = _process_status_ticks(s)
        events.extend(status_events)
        # Perk: regen_per_turn for fighters
        for fighter in s.player_fighters:
            if not fighter.alive or fighter.hp <= 0 or fighter.hp >= fighter.max_hp:
                continue
            regen = getattr(fighter, 'get_perk_effects', lambda x: 0)("regen_per_turn_pct")
            if regen > 0:
                heal = max(1, int(fighter.max_hp * regen))
                fighter.hp = min(fighter.max_hp, fighter.hp + heal)
        # Check if any enemy died from status effects
        for enemy in s.enemies:
            if enemy.hp <= 0 and hasattr(enemy, '_status_killed'):
                continue
            if enemy.hp <= 0 and id(enemy) in s.enemy_status:
                enemy._status_killed = True
                events.append(BattleEvent(
                    "death", defender=enemy.name, is_kill=True,
                    message=f"{enemy.name} killed by status!",
                    is_boss=s.is_boss_fight,
                ))
                reward = enemy.gold_reward
                s.gold_earned += reward
                self.engine.award_gold(reward)
        if not s.any_enemies_alive():
            self._declare_victory(events)
            return True
        return False

    def _player_attack_phase(self, events):
        """All fighters attack enemies.

        Returns True if all enemies are dead (victory via combat)."""
        s = self.state
        for i, fighter in enumerate(s.player_fighters):
            if not fighter.alive or fighter.hp <= 0:
                continue

            target = s.current_enemy
            if not target or target.hp <= 0:
                if not s.next_alive_enemy():
                    break
                target = s.current_enemy
            if not target:
                break

            ev, actual, is_crit = _resolve_attack(fighter, target, is_boss=s.is_boss_fight)
            events.append(ev)

            if actual > 0:
                # Perk: lifesteal
                ls_pct = getattr(fighter, 'get_perk_effects', lambda x: 0)("lifesteal_pct")
                if ls_pct > 0:
                    heal = max(1, int(actual * ls_pct))
                    fighter.hp = min(fighter.max_hp, fighter.hp + heal)

                # Enchantment buildup on hit
                weapon = fighter.equipment.get("weapon")
                eid = id(target)
                if weapon and eid in s.enemy_status:
                    ench_id = weapon.get("enchantment")
                    if ench_id and ench_id in ENCHANTMENT_TYPES:
                        ench = ENCHANTMENT_TYPES[ench_id]
                        tracker = s.enemy_status[eid]
                        tracker.status_buildup[ench_id] = tracker.status_buildup.get(ench_id, 0) + ench["buildup_per_hit"]
                        if tracker.status_buildup[ench_id] >= ench["threshold"]:
                            tracker.status_buildup[ench_id] = 0
                            events.extend(_trigger_enchantment(s, target, ench_id, ench))

            if target.hp <= 0:
                events.append(BattleEvent(
                    "death", defender=target.name, is_kill=True,
                    message=f"{target.name} destroyed!",
                    is_boss=s.is_boss_fight,
                ))
                reward = target.gold_reward
                s.gold_earned += reward
                self.engine.award_gold(reward)
                fighter.kills += 1

                # Perk: on_kill_heal
                okh_pct = getattr(fighter, 'get_perk_effects', lambda x: 0)("on_kill_heal_pct")
                if okh_pct > 0:
                    heal = max(1, int(fighter.max_hp * okh_pct))
                    fighter.hp = min(fighter.max_hp, fighter.hp + heal)

                if not s.any_enemies_alive():
                    break
                s.next_alive_enemy()

        # Check victory
        if not s.any_enemies_alive():
            self._declare_victory(events)
            return True
        return False

    def _enemy_attack_phase(self, events):
        """All enemies attack fighters.

        Returns True if all fighters are dead (defeat)."""
        s = self.state
        for enemy in s.enemies:
            if enemy.hp <= 0:
                continue

            # Paralyze: skip this enemy's turn
            eid = id(enemy)
            if eid in s.enemy_status:
                tracker = s.enemy_status[eid]
                if tracker.skip_next_turn:
                    tracker.skip_next_turn = False
                    events.append(BattleEvent("status", defender=enemy.name,
                        message=f"{enemy.name} is paralyzed!"))
                    continue

            alive_fighters = [f for f in s.player_fighters if f.alive and f.hp > 0]
            if not alive_fighters:
                break
            target = random.choice(alive_fighters)

            # Perk: damage_reduction — save HP, undo full hit, apply reduced
            dr = getattr(target, 'damage_reduction', 0)
            hp_before = target.hp
            ev, actual, is_crit = _resolve_attack(enemy, target, is_boss=s.is_boss_fight)
            if dr > 0 and actual > 0:
                reduced = max(1, int(actual * (1 - dr)))
                # Undo the full hit, apply reduced damage instead
                target.hp = max(0, hp_before - reduced)
                actual = reduced
                ev = BattleEvent(
                    "attack", attacker=enemy.name, defender=target.name,
                    damage=actual, is_crit=is_crit,
                    message=f"{enemy.name} {'CRIT! ' if is_crit else ''}hits {target.name} for {fmt_num(actual)}"
                )
            events.append(ev)

            if actual == 0:
                continue

            if target.hp <= 0:
                died_forever, injury_id = self.engine.handle_fighter_death(target)
                if died_forever:
                    events.append(BattleEvent(
                        "death", defender=target.name, is_kill=True,
                        message=t("fallen_forever", name=target.name),
                    ))
                else:
                    from game.data_loader import data_loader
                    inj_name = data_loader.injuries_by_id.get(injury_id, {}).get("name", "?")
                    events.append(BattleEvent(
                        "death", defender=target.name,
                        message=t("knocked_out_injury", name=target.name, injury=inj_name),
                    ))

        # Check defeat
        if not s.any_fighters_alive():
            s.phase = BattlePhase.DEFEAT
            events.append(BattleEvent(
                "defeat", message="ALL FIGHTERS DOWN!",
            ))
            for f in s.player_fighters:
                if f.alive:
                    f.heal()
            return True
        return False

    def do_turn(self):
        """Execute one turn. Returns list of events for animation."""
        s = self.state
        events = []

        if s.phase in (BattlePhase.IDLE, BattlePhase.VICTORY, BattlePhase.DEFEAT):
            return events

        if s.phase in (BattlePhase.STARTING, BattlePhase.BOSS_INTRO):
            s.phase = BattlePhase.TURN_PLAYER
            s.turn_number = 1
            events.append(BattleEvent("message", message=f"Turn {s.turn_number}"))
            return events

        # --- Status effect ticks (DOT/debuffs) ---
        if self._status_tick_phase(events):
            return events

        # --- All fighters attack ---
        if self._player_attack_phase(events):
            return events

        # --- All enemies attack ---
        if self._enemy_attack_phase(events):
            return events

        s.turn_number += 1
        events.append(BattleEvent("message", message=f"Turn {s.turn_number}"))
        return events

    def do_full_battle(self):
        """Run entire battle instantly (skip mode)."""
        all_events = []
        while self.state.phase not in (BattlePhase.VICTORY, BattlePhase.DEFEAT,
                                        BattlePhase.IDLE):
            events = self.do_turn()
            all_events.extend(events)
            if len(all_events) > 200:
                break
        return all_events

    @property
    def is_active(self):
        return self.state.phase not in (BattlePhase.IDLE, BattlePhase.VICTORY,
                                         BattlePhase.DEFEAT)
