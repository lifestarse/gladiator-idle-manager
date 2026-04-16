# Build: 21
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

# Shorthand for fmt_num in battle messages
_fn = fmt_num


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
        self.modifier_state = {}    # boss modifier per-fight state


class SkillState:
    """Tracks per-fighter active skill cooldown and transient flags for one battle."""
    def __init__(self, skill_def):
        self.skill_def = skill_def
        self.cooldown_remaining = 0       # 0 = ready to fire
        self.guaranteed_crit = False      # Shadowstep: force next crit
        self.dodge_next_attack = False    # Shadowstep: auto-dodge next hit
        self.extra_attacks = 0            # Frenzy: remaining bonus swings this turn
        self.extra_attack_mult = 1.0      # Frenzy: damage multiplier for bonus swings


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
        # Active skill system
        self.skill_states: dict = {}    # id(fighter) -> SkillState
        self.team_buffs: list = []      # active team-wide buffs [{type, value, turns_left}]
        self.team_shield = None         # Shield Wall: {reduction_pct, turns_left} or None
        self.enemy_stuns: dict = {}     # id(enemy) -> stun_turns_remaining

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
            message=t("battle_burst", name=name, target=target.name, dmg=_fn(dmg))))

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
            message=t("battle_frostbite", target=target.name, dmg=_fn(dmg))))

    elif effect == "dot":
        # poison
        tracker.active_effects.append({
            "type": "poison_dot",
            "turns_left": ench["dot_turns"],
            "dot_pct": ench["dot_pct"],
        })
        events.append(BattleEvent("status", defender=target.name,
            message=t("battle_poison_apply", target=target.name, turns=ench["dot_turns"])))

    elif effect == "skip_turn":
        # paralyze
        tracker.skip_next_turn = True
        events.append(BattleEvent("status", defender=target.name,
            message=t("battle_paralyze", target=target.name)))

    elif effect == "def_reduction":
        # corruption
        reduction = ench.get("reduction_pct", 0.3)
        target.defense = int(tracker.original_defense * (1 - reduction))
        tracker.active_effects.append({
            "type": "def_debuff",
            "turns_left": ench.get("debuff_turns", 3),
        })
        events.append(BattleEvent("status", defender=target.name,
            message=t("battle_corruption", target=target.name)))

    elif effect == "chain_burst":
        # lightning — hit target + all other alive enemies
        dmg = max(1, int(target.max_hp * ench["burst_pct"]))
        target.hp = max(0, target.hp - dmg)
        events.append(BattleEvent("status", defender=target.name, damage=dmg,
            message=t("battle_lightning", target=target.name, dmg=_fn(dmg))))
        for other in state.enemies:
            if other is not target and other.hp > 0:
                chain_dmg = max(1, int(other.max_hp * ench["burst_pct"]))
                other.hp = max(0, other.hp - chain_dmg)
                events.append(BattleEvent("status", defender=other.name, damage=chain_dmg,
                    message=t("battle_chain", target=other.name, dmg=_fn(chain_dmg))))

    elif effect == "atk_reduction":
        # weaken
        reduction = ench.get("reduction_pct", 0.25)
        target.attack = int(tracker.original_attack * (1 - reduction))
        tracker.active_effects.append({
            "type": "atk_debuff",
            "turns_left": ench.get("debuff_turns", 4),
        })
        events.append(BattleEvent("status", defender=target.name,
            message=t("battle_weaken", target=target.name)))

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
                        message=t("battle_drain", fighter=fighter.name, heal=_fn(heal))))
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
            message=t("battle_holy_fire", target=target.name, dmg=_fn(dmg))))

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
                    message=t("battle_poison_tick", target=enemy.name, dmg=_fn(dot_dmg))))
            if eff["turns_left"] > 0:
                remaining.append(eff)
            else:
                # Restore stats when debuffs expire
                if eff["type"] == "atk_debuff":
                    enemy.attack = tracker.original_attack
                    events.append(BattleEvent("status", defender=enemy.name,
                        message=t("battle_atk_restored", target=enemy.name)))
                elif eff["type"] == "def_debuff":
                    enemy.defense = tracker.original_defense
                    events.append(BattleEvent("status", defender=enemy.name,
                        message=t("battle_def_restored", target=enemy.name)))
        tracker.active_effects = remaining
    return events


def _resolve_attack(attacker, defender, is_boss=False, force_crit=False,
                    damage_mult=1.0):
    """Resolve a single attack: crit -> damage -> dodge -> event.
    Returns (BattleEvent, actual_damage, is_crit)."""
    is_crit = force_crit or random.random() < attacker.crit_chance
    raw = int(attacker.deal_damage() * damage_mult)
    if is_crit:
        raw = int(raw * attacker.crit_mult)
    actual = defender.take_damage(raw)
    if actual == 0:
        ev = BattleEvent(
            "attack", attacker=attacker.name, defender=defender.name,
            damage=0, is_dodge=True,
            message=t("battle_dodge", defender=defender.name, attacker=attacker.name),
        )
    else:
        msg_key = "battle_crit_hit" if is_crit else "battle_hit"
        ev = BattleEvent(
            "attack", attacker=attacker.name, defender=defender.name,
            damage=actual, is_crit=is_crit,
            message=t(msg_key, attacker=attacker.name, defender=defender.name, dmg=_fn(actual)),
        )
    return ev, actual, is_crit


class BattleManager:
    """Manages turn-based battles with luck-based combat."""

    def __init__(self, engine):
        self.engine = engine
        self.state = BattleState()
        self._mod_handler = None

    def _init_mod_handler(self):
        from game.boss_modifiers import BossModifierHandler
        from game.data_loader import data_loader
        self._mod_handler = BossModifierHandler(data_loader.boss_modifiers)

    def start_auto_battle(self):
        fighters = [f for f in self.engine.fighters
                    if f.available]
        if not fighters:
            return [BattleEvent("message", message=t("battle_no_fighters"))]

        from game.models import Enemy
        from game.data_loader import data_loader
        import random as _rand
        # Use all preview enemies (already pre-spawned to match fighter count)
        enemies = list(self.engine.preview_enemies)
        boss_revenge = any(getattr(e, 'is_boss', False) for e in enemies)
        # Fallback: if preview is empty or count mismatch, fill up
        num_enemies = max(1, len(fighters))
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
        for f in fighters:
            skill = getattr(f, 'get_active_skill', lambda: None)()
            if skill:
                self.state.skill_states[id(f)] = SkillState(skill)
        for e in enemies:
            _init_enemy_status(self.state, e)
        if any(getattr(e, 'modifiers', None) for e in enemies):
            self._init_mod_handler()

        events = []
        if boss_revenge:
            events.append(BattleEvent("message", message=t("boss_revenge")))
        events.append(BattleEvent("message", message=t("battle_start", n=len(fighters), m=len(enemies))))
        return events

    def start_boss_fight(self):
        fighters = [f for f in self.engine.fighters
                    if f.available]
        if not fighters:
            return [BattleEvent("message", message=t("battle_no_fighters"))]

        boss = self.engine.current_enemy

        self.state = BattleState()
        self.state.player_fighters = fighters
        self.state.enemies = [boss]
        self.state.phase = BattlePhase.BOSS_INTRO
        self.state.is_boss_fight = True
        for f in fighters:
            skill = getattr(f, 'get_active_skill', lambda: None)()
            if skill:
                self.state.skill_states[id(f)] = SkillState(skill)
        _init_enemy_status(self.state, boss)
        if getattr(boss, 'modifiers', None):
            self._init_mod_handler()

        mod_names = ""
        if getattr(boss, 'modifiers', None):
            from game.data_loader import data_loader
            names = [data_loader.boss_modifiers.get(m, {}).get("name", m) for m in boss.modifiers]
            mod_names = f"\n[{', '.join(names)}]"
        return [BattleEvent("boss_intro",
                            message=t("battle_boss_appears", name=boss.name, hp=_fn(boss.hp), mods=mod_names),
                            is_boss=True)]

    def _declare_victory(self, events):
        """Mark battle as won, heal fighters, emit victory event."""
        s = self.state
        s.phase = BattlePhase.VICTORY
        self.engine.wins += len(s.enemies)
        self.engine.total_wins += len(s.enemies)
        if s.is_boss_fight:
            self.engine.arena_tier += 1
        for f in s.player_fighters:
            if f.alive:
                f.hp = f.max_hp
        events.append(BattleEvent(
            "victory", message=t("battle_victory", gold=_fn(s.gold_earned)),
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
        # Boss modifiers: turn start
        if self._mod_handler and s.is_boss_fight:
            for enemy in s.enemies:
                if enemy.hp <= 0 or not getattr(enemy, 'modifiers', None):
                    continue
                tracker = s.enemy_status.get(id(enemy))
                if tracker:
                    events.extend(self._mod_handler.on_turn_start(
                        enemy, tracker, s.turn_number))

        # Check if any enemy died from status effects
        for enemy in s.enemies:
            if enemy.hp <= 0 and hasattr(enemy, '_status_killed'):
                continue
            if enemy.hp <= 0 and id(enemy) in s.enemy_status:
                enemy._status_killed = True
                events.append(BattleEvent(
                    "death", defender=enemy.name, is_kill=True,
                    message=t("battle_killed_by_status", target=enemy.name),
                    is_boss=s.is_boss_fight,
                ))
                reward = enemy.gold_reward
                s.gold_earned += reward
                self.engine.award_gold(reward)
        if not s.any_enemies_alive():
            self._declare_victory(events)
            return True
        return False

    def _skill_activation_phase(self, events):
        """Auto-activate fighter skills when off cooldown."""
        s = self.state
        for fighter in s.player_fighters:
            if not fighter.alive or fighter.hp <= 0:
                continue
            ss = s.skill_states.get(id(fighter))
            if not ss:
                continue
            if ss.cooldown_remaining > 0:
                ss.cooldown_remaining -= 1
                continue
            # Skill is ready — fire it
            self._execute_skill(fighter, ss, events)
            ss.cooldown_remaining = ss.skill_def["cooldown"]

    def _execute_skill(self, fighter, ss, events):
        """Dispatch skill execution by skill_type."""
        s = self.state
        skill = ss.skill_def
        skill_type = skill["skill_type"]
        params = skill.get("params", {})

        if skill_type == "buff_team_atk":
            s.team_buffs.append({
                "type": "atk_bonus_pct",
                "value": params["atk_bonus_pct"],
                "turns_left": params["duration"],
            })
            events.append(BattleEvent("skill", attacker=fighter.name,
                message=t("skill_rally", fighter=fighter.name, skill=skill["name"], pct=int(params["atk_bonus_pct"]*100))))

        elif skill_type == "guaranteed_crit_dodge":
            ss.guaranteed_crit = True
            ss.dodge_next_attack = True
            events.append(BattleEvent("skill", attacker=fighter.name,
                message=t("skill_shadowstep", fighter=fighter.name)))

        elif skill_type == "multi_attack":
            ss.extra_attacks = params["extra_attacks"]
            ss.extra_attack_mult = params["damage_mult"]
            events.append(BattleEvent("skill", attacker=fighter.name,
                message=t("skill_frenzy", fighter=fighter.name)))

        elif skill_type == "team_damage_reduction":
            if s.team_shield and s.team_shield["turns_left"] > 0:
                # Shield already active — hold skill, don't waste cooldown
                ss.cooldown_remaining = 0
                return
            s.team_shield = {
                "reduction_pct": params["reduction_pct"],
                "turns_left": params["duration"],
            }
            events.append(BattleEvent("skill", attacker=fighter.name,
                message=t("skill_shield_wall", fighter=fighter.name, pct=int(params["reduction_pct"]*100))))

        elif skill_type == "stun_enemy":
            # Target first alive enemy not already stunned
            target = None
            for e in s.enemies:
                if e.hp > 0 and s.enemy_stuns.get(id(e), 0) <= 0:
                    target = e
                    break
            if not target:
                # All alive enemies already stunned — hold skill
                ss.cooldown_remaining = 0
                return
            s.enemy_stuns[id(target)] = params["stun_turns"]
            events.append(BattleEvent("skill", attacker=fighter.name,
                defender=target.name,
                message=t("skill_net_throw", fighter=fighter.name, target=target.name)))

        elif skill_type == "heal_team":
            heal_pct = params["heal_pct"]
            for f in s.player_fighters:
                if f.alive and f.hp > 0:
                    heal = max(1, int(f.max_hp * heal_pct))
                    f.hp = min(f.max_hp, f.hp + heal)
            events.append(BattleEvent("skill", attacker=fighter.name,
                message=t("skill_heal_team", fighter=fighter.name, skill=skill["name"])))

    def _tick_skill_buffs(self):
        """Decrement durations of team buffs and shield after the turn resolves."""
        s = self.state
        # Team ATK buffs
        remaining = []
        for buff in s.team_buffs:
            buff["turns_left"] -= 1
            if buff["turns_left"] > 0:
                remaining.append(buff)
        s.team_buffs = remaining
        # Shield Wall
        if s.team_shield:
            s.team_shield["turns_left"] -= 1
            if s.team_shield["turns_left"] <= 0:
                s.team_shield = None

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

            # Skill modifiers for this fighter's attack
            ss = s.skill_states.get(id(fighter))
            force_crit = False
            atk_mult = 1.0
            if ss and ss.guaranteed_crit:
                force_crit = True
                ss.guaranteed_crit = False
            # Rally: team ATK buff
            atk_bonus = sum(b["value"] for b in s.team_buffs
                            if b["type"] == "atk_bonus_pct")
            if atk_bonus > 0:
                atk_mult += atk_bonus

            ev, actual, is_crit = _resolve_attack(
                fighter, target, is_boss=s.is_boss_fight,
                force_crit=force_crit, damage_mult=atk_mult)
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
                            self.engine.total_enchantment_procs += 1

            # Boss modifiers: on hit
            if self._mod_handler and actual > 0 and getattr(target, 'modifiers', None):
                tracker = s.enemy_status.get(id(target))
                if tracker:
                    events.extend(self._mod_handler.on_boss_hit(
                        target, tracker, fighter, actual))
                    # Thorns may have killed the attacker
                    if fighter.hp <= 0:
                        died_forever, injury_id = self.engine.handle_fighter_death(fighter)
                        if died_forever:
                            events.append(BattleEvent(
                                "death", defender=fighter.name, is_kill=True,
                                message=t("fallen_forever", name=fighter.name),
                            ))
                        else:
                            from game.data_loader import data_loader
                            inj_name = data_loader.injuries_by_id.get(injury_id, {}).get("name", "?")
                            events.append(BattleEvent(
                                "death", defender=fighter.name,
                                message=t("knocked_out_injury", name=fighter.name, injury=inj_name),
                            ))
                        break

            if target.hp <= 0:
                events.append(BattleEvent(
                    "death", defender=target.name, is_kill=True,
                    message=t("battle_destroyed", target=target.name),
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

            # Frenzy: extra attacks on same or next target
            if ss and ss.extra_attacks > 0:
                for _ in range(ss.extra_attacks):
                    target = s.current_enemy
                    if not target or target.hp <= 0:
                        if not s.next_alive_enemy():
                            break
                        target = s.current_enemy
                    if not target or target.hp <= 0:
                        break
                    ev2, actual2, _ = _resolve_attack(
                        fighter, target, is_boss=s.is_boss_fight,
                        damage_mult=ss.extra_attack_mult * atk_mult)
                    events.append(ev2)
                    if actual2 > 0:
                        ls_pct = getattr(fighter, 'get_perk_effects', lambda x: 0)("lifesteal_pct")
                        if ls_pct > 0:
                            heal = max(1, int(actual2 * ls_pct))
                            fighter.hp = min(fighter.max_hp, fighter.hp + heal)
                    if target.hp <= 0:
                        events.append(BattleEvent(
                            "death", defender=target.name, is_kill=True,
                            message=t("battle_destroyed", target=target.name),
                            is_boss=s.is_boss_fight))
                        reward = target.gold_reward
                        s.gold_earned += reward
                        self.engine.award_gold(reward)
                        fighter.kills += 1
                        if not s.any_enemies_alive():
                            break
                        s.next_alive_enemy()
                ss.extra_attacks = 0

        # Check victory
        if not s.any_enemies_alive():
            self._declare_victory(events)
            return True
        return False

    def _enemy_attack_phase(self, events):
        """All enemies attack fighters.

        Returns True if all fighters are dead (defeat)."""
        s = self.state
        # Build alive_fighters ONCE (was O(N²) — rebuilt per enemy).
        # Maintained via swap-pop when a fighter dies mid-phase.
        alive_fighters = [f for f in s.player_fighters if f.alive and f.hp > 0]
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
                        message=t("battle_is_paralyzed", target=enemy.name)))
                    continue

            # Net Throw stun: skip this enemy's turn
            if s.enemy_stuns.get(eid, 0) > 0:
                s.enemy_stuns[eid] -= 1
                events.append(BattleEvent("status", defender=enemy.name,
                    message=t("battle_is_ensnared", target=enemy.name)))
                continue

            if not alive_fighters:
                break
            # O(1) target pick; swap-pop at end of attack if target died
            target_idx = random.randrange(len(alive_fighters))
            target = alive_fighters[target_idx]

            # Shadowstep: auto-dodge next attack
            tgt_ss = s.skill_states.get(id(target))
            if tgt_ss and tgt_ss.dodge_next_attack:
                tgt_ss.dodge_next_attack = False
                events.append(BattleEvent("attack", attacker=enemy.name,
                    defender=target.name, damage=0, is_dodge=True,
                    message=t("battle_shadowstep_dodge", defender=target.name, attacker=enemy.name)))
                continue

            # Boss modifiers: pre-attack (temp ATK override)
            _atk_backup = None
            if self._mod_handler and getattr(enemy, 'modifiers', None):
                tracker = s.enemy_status.get(eid)
                if tracker:
                    overrides = self._mod_handler.on_boss_attack_pre(enemy, tracker)
                    if 'attack' in overrides:
                        _atk_backup = enemy.attack
                        enemy.attack = overrides['attack']

            try:
                # Perk: damage_reduction + Shield Wall (multiplicative)
                dr = getattr(target, 'damage_reduction', 0)
                shield_dr = s.team_shield["reduction_pct"] if s.team_shield else 0
                combined_dr = 1 - (1 - dr) * (1 - shield_dr)
                hp_before = target.hp
                ev, actual, is_crit = _resolve_attack(enemy, target, is_boss=s.is_boss_fight)
                if combined_dr > 0 and actual > 0:
                    reduced = max(1, int(actual * (1 - combined_dr)))
                    target.hp = max(0, hp_before - reduced)
                    actual = reduced
                    msg_key = "battle_crit_hit" if is_crit else "battle_hit"
                    ev = BattleEvent(
                        "attack", attacker=enemy.name, defender=target.name,
                        damage=actual, is_crit=is_crit,
                        message=t(msg_key, attacker=enemy.name, defender=target.name, dmg=_fn(actual)),
                    )
                events.append(ev)
            finally:
                if _atk_backup is not None:
                    enemy.attack = _atk_backup

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
                # O(1) swap-pop — target is out of the alive list for this turn
                alive_fighters[target_idx] = alive_fighters[-1]
                alive_fighters.pop()

        # Check defeat
        if not s.any_fighters_alive():
            s.phase = BattlePhase.DEFEAT
            events.append(BattleEvent(
                "defeat", message=t("battle_all_down"),
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
            events.append(BattleEvent("message", message=t("battle_turn", n=s.turn_number)))
            return events

        # --- Status effect ticks (DOT/debuffs) ---
        if self._status_tick_phase(events):
            return events

        # --- Active skills fire ---
        self._skill_activation_phase(events)

        # --- All fighters attack ---
        if self._player_attack_phase(events):
            return events

        # --- All enemies attack ---
        if self._enemy_attack_phase(events):
            return events

        # --- Tick down skill buff durations ---
        self._tick_skill_buffs()

        s.turn_number += 1
        events.append(BattleEvent("message", message=t("battle_turn", n=s.turn_number)))
        return events

    def do_full_battle(self):
        """Run entire battle instantly (skip mode)."""
        all_events = []
        while self.state.phase not in (BattlePhase.VICTORY, BattlePhase.DEFEAT,
                                        BattlePhase.IDLE):
            events = self.do_turn()
            all_events.extend(events)
            if len(all_events) > 200:
                # Safety cap — force defeat to prevent zombie battle
                if self.state.phase not in (BattlePhase.VICTORY, BattlePhase.DEFEAT):
                    self.state.phase = BattlePhase.DEFEAT
                    all_events.append(BattleEvent("defeat", message=t("battle_all_down")))
                break
        return all_events

    @property
    def is_active(self):
        return self.state.phase not in (BattlePhase.IDLE, BattlePhase.VICTORY,
                                         BattlePhase.DEFEAT)
