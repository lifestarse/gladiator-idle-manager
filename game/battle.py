# Build: 23
"""
Turn-based battle system with luck-based combat.

Two battle modes:
1. Auto-Battle (The Pit) -- all available fighters vs waves of enemies
2. Boss Challenge -- turn-by-turn tactical boss fight with skip option

Combat is luck-heavy: crits deal scaling damage, dodges negate hits entirely.
A weak but agile assassin can outperform a strong brute through fortunate rolls.
"""

import random
from collections import namedtuple
from enum import Enum, auto
from game.models import ENCHANTMENT_TYPES, fmt_num
from game.constants import (
    DAMAGE_VARIANCE_LOW, DAMAGE_VARIANCE_HIGH, DEFENSE_DIVISOR,
)
from game.localization import t

# Shorthand for fmt_num in battle messages
_fn = fmt_num


# --- Outcome contract between BattleManager and the engine ---
# Exposed by do_turn() and do_full_battle(). Lets callers (GameEngine,
# future headless sim / tests) read results without reaching into
# BattleManager.state. All fields are computed from state at return time.
BattleResult = namedtuple("BattleResult", [
    "outcome",          # "ongoing" | "victory" | "defeat"
    "is_boss",          # bool
    "gold_earned",      # int
    "enemies_killed",   # int (enemies with hp <= 0)
    "survivors",        # list[Enemy] — enemies with hp > 0 (for revenge)
    "turn_number",      # int — for battle log
    "player_fighters",  # list[Fighter] — for battle log
    "enemies",          # list[Enemy] — for battle log
])


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
                 is_dodge=False, skill_type=""):
        self.event_type = event_type
        self.attacker = attacker
        self.defender = defender
        self.damage = damage
        self.message = message
        self.is_kill = is_kill
        self.is_crit = is_crit
        self.is_boss = is_boss
        self.is_dodge = is_dodge
        # For event_type=="skill" only: which skill type fired. Used by
        # _skill_activation_phase to collapse identical skill activations
        # from many fighters in one turn into a single summary event —
        # otherwise 1000 fighters all rallying on turn 1 emits 1000
        # near-identical lines and buries actual combat events under them.
        self.skill_type = skill_type


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
        # Lazy snapshot of fighter combat stats (attack/defense/max_hp/crit/
        # dodge/crit_mult/damage_reduction) keyed by id(fighter). Fighter
        # stats are the result of heavy property chains (equipment loops +
        # perk lookups); they're invariant during a battle except when an
        # injury is added via handle_fighter_death, which invalidates the
        # entry. Biggest win is in boss fights: same 1000 fighters attack
        # the same boss for 40+ turns, previously recomputing stats every
        # single attack.
        self.fighter_stat_cache: dict = {}
        # Scalar running total of team atk_bonus_pct. Previously recomputed
        # via sum(genexpr) on every single player attack — in a 1000-fighter
        # battle where every merc rallies, that's 1M iterations/turn burning
        # ~50% of battle CPU. Maintained incrementally by _execute_skill
        # (buff add) and _tick_skill_buffs (expiry).
        self.team_atk_bonus_pct: float = 0.0
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
                    damage_mult=1.0, atk_cache=None, def_cache=None):
    """Resolve a single attack: crit -> damage -> dodge -> event.
    Returns (BattleEvent, actual_damage, is_crit).

    atk_cache / def_cache: optional pre-computed stat snapshots from
    BattleManager._fighter_stats. When provided, skips the heavy property
    chains on Fighter (equipment loops + perk lookups). Enemies use plain
    attributes so they don't need caching — callers typically pass
    atk_cache for player attacks and def_cache for enemy attacks.
    """
    # --- Attacker stats ---
    if atk_cache is not None:
        atk_crit_chance = atk_cache['crit_chance']
        atk_attack = atk_cache['attack']
        atk_crit_mult = atk_cache['crit_mult']
    else:
        atk_crit_chance = attacker.crit_chance
        atk_attack = attacker.attack
        atk_crit_mult = attacker.crit_mult

    is_crit = force_crit or random.random() < atk_crit_chance
    variance = random.uniform(DAMAGE_VARIANCE_LOW, DAMAGE_VARIANCE_HIGH)
    raw = int(max(1, int(atk_attack * variance)) * damage_mult)
    if is_crit:
        raw = int(raw * atk_crit_mult)

    # --- Defender: dodge + defense reduction + apply damage ---
    # Replicates CombatUnit.take_damage inline so we can consult def_cache
    # without reading the heavy properties every call. Bit-identical to
    # the original formula.
    if def_cache is not None:
        def_dodge = def_cache['dodge_chance']
        def_defense = def_cache['defense']
        if random.random() < def_dodge:
            actual = 0
        else:
            reduction = def_defense / (def_defense + DEFENSE_DIVISOR)
            reduced = max(1, int(raw * (1 - reduction)))
            defender.hp = max(0, defender.hp - reduced)
            actual = reduced
    else:
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

    def _fighter_stats(self, fighter):
        """Return (cached) combat-stat snapshot for a Fighter.

        All values come from the Fighter's property chain (attack, defense,
        crit_chance, dodge_chance, crit_mult, max_hp, damage_reduction) —
        each of which walks the equipment dict + perk tree + injuries list.
        Cached per battle; invalidated via `_invalidate_fighter_stats` when
        the fighter's injuries change (permadeath-survived hit).
        """
        cache = self.state.fighter_stat_cache
        key = id(fighter)
        stats = cache.get(key)
        if stats is None:
            # Also snapshot the per-attack perk lookups (lifesteal_pct,
            # on_kill_heal_pct). Previously those called get_perk_effects
            # on every single attack / kill — with 1000 fighters and 44
            # turns that's ~42k + ~1k calls through the perk iteration.
            gpe = getattr(fighter, 'get_perk_effects', lambda x: 0)
            stats = {
                'attack': fighter.attack,
                'defense': fighter.defense,
                'crit_chance': fighter.crit_chance,
                'crit_mult': fighter.crit_mult,
                'dodge_chance': fighter.dodge_chance,
                'max_hp': fighter.max_hp,
                'damage_reduction': getattr(fighter, 'damage_reduction', 0),
                'lifesteal_pct': gpe('lifesteal_pct'),
                'on_kill_heal_pct': gpe('on_kill_heal_pct'),
                'regen_per_turn_pct': gpe('regen_per_turn_pct'),
            }
            cache[key] = stats
        return stats

    def _invalidate_fighter_stats(self, fighter):
        """Drop the cached stat snapshot for a fighter (e.g. after injury)."""
        self.state.fighter_stat_cache.pop(id(fighter), None)

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
        # Perk: regen_per_turn for fighters. Read max_hp via the cache —
        # profiler showed direct access here was the single biggest
        # remaining boss-fight cost (1000 fighters × 44 turns = 45000 hits
        # on the expensive property chain).
        for fighter in s.player_fighters:
            if not fighter.alive or fighter.hp <= 0:
                continue
            stats = self._fighter_stats(fighter)
            regen = stats['regen_per_turn_pct']
            if regen <= 0:
                continue
            mh = stats['max_hp']
            if fighter.hp >= mh:
                continue
            heal = max(1, int(mh * regen))
            fighter.hp = min(mh, fighter.hp + heal)
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
        """Auto-activate fighter skills when off cooldown.

        Collects the phase's skill events into a local buffer so we can
        collapse identical skill activations (e.g. 1000 fighters rallying
        the same turn) into one summary line before forwarding to the
        main event stream. Without this, big battles produced a log full
        of 'X uses Rally!' × 1000 that exhausted the 500-line cap before
        any actual combat event got through.
        """
        s = self.state
        phase_events = []
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
            self._execute_skill(fighter, ss, phase_events)
            ss.cooldown_remaining = ss.skill_def["cooldown"]

        events.extend(self._collapse_skill_events(phase_events))

    # Map skill_type -> (l10n_key_for_summary, which params from _execute_skill
    # to feed into t()). "stun_enemy" is deliberately absent: it targets a
    # specific enemy, collapsing multiple stuns loses information (which
    # enemies got stunned). Those pass through as individual events.
    _SKILL_SUMMARY_KEYS = {
        "buff_team_atk":         ("skill_rally_many",       ("pct",)),
        "guaranteed_crit_dodge": ("skill_shadowstep_many",  ()),
        "multi_attack":          ("skill_frenzy_many",      ()),
        "team_damage_reduction": ("skill_shield_wall_many", ("pct",)),
        "heal_team":             ("skill_heal_team_many",   ()),
    }

    @classmethod
    def _collapse_skill_events(cls, phase_events):
        """Group events by skill_type and replace N same-type events with
        one name-less summary line ("160 fighters rally! Team ATK +15%!").

        Single occurrences (n == 1) and events without a skill_type tag
        pass through unchanged — a single activation still reads
        "Vorn uses Rally!". Only bulk activations get summarized. Order
        is preserved by flushing accumulated buckets whenever an
        untagged/non-collapsible event arrives.
        """
        if not phase_events:
            return phase_events
        out = []
        buckets = {}    # skill_type -> [events]
        order = []      # insertion order of skill_types in this phase

        def flush():
            for key in order:
                evs = buckets[key]
                if len(evs) == 1:
                    out.append(evs[0])
                    continue
                out.append(cls._make_skill_summary(key, evs))
            buckets.clear()
            order.clear()

        for ev in phase_events:
            key = getattr(ev, 'skill_type', '') or None
            # stun_enemy: keep per-target; don't collapse (different defenders)
            if not key or key == "stun_enemy":
                flush()
                out.append(ev)
                continue
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(ev)
        flush()
        return out

    @classmethod
    def _make_skill_summary(cls, skill_type, evs):
        """Build one summary event for N activations of the same skill.

        Uses a dedicated l10n key (*_many) that takes {n} and effect
        params instead of {fighter} — so users see "160 fighters rally!"
        rather than the earlier misleading "160× Vorn uses Rally!" which
        read as though one fighter activated it 160 times.
        """
        first = evs[0]
        n = len(evs)
        summary_info = cls._SKILL_SUMMARY_KEYS.get(skill_type)
        if summary_info is not None:
            key, param_names = summary_info
            kwargs = {"n": n}
            for p in param_names:
                # pct was stashed on the BattleEvent by _execute_skill; if
                # missing for some reason, localization will just render
                # the placeholder literal. Either way, not a crash.
                kwargs[p] = getattr(first, f"_skill_{p}", 0)
            message = t(key, **kwargs)
            # If the l10n key is missing (returns the key itself), fall
            # back to a plain count-prefix so the log stays readable.
            if message == key:
                message = f"{n}× {first.message}"
        else:
            message = f"{n}× {first.message}"
        return BattleEvent(
            event_type=first.event_type,
            message=message,
            skill_type=skill_type,
        )

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
            s.team_atk_bonus_pct += params["atk_bonus_pct"]
            pct = int(params["atk_bonus_pct"] * 100)
            ev = BattleEvent("skill", attacker=fighter.name,
                skill_type=skill_type,
                message=t("skill_rally", fighter=fighter.name, skill=skill["name"], pct=pct))
            ev._skill_pct = pct  # read by _make_skill_summary on collapse
            events.append(ev)

        elif skill_type == "guaranteed_crit_dodge":
            ss.guaranteed_crit = True
            ss.dodge_next_attack = True
            events.append(BattleEvent("skill", attacker=fighter.name,
                skill_type=skill_type,
                message=t("skill_shadowstep", fighter=fighter.name)))

        elif skill_type == "multi_attack":
            ss.extra_attacks = params["extra_attacks"]
            ss.extra_attack_mult = params["damage_mult"]
            events.append(BattleEvent("skill", attacker=fighter.name,
                skill_type=skill_type,
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
            pct = int(params["reduction_pct"] * 100)
            ev = BattleEvent("skill", attacker=fighter.name,
                skill_type=skill_type,
                message=t("skill_shield_wall", fighter=fighter.name, pct=pct))
            ev._skill_pct = pct
            events.append(ev)

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
                skill_type=skill_type,
                message=t("skill_net_throw", fighter=fighter.name, target=target.name)))

        elif skill_type == "heal_team":
            heal_pct = params["heal_pct"]
            for f in s.player_fighters:
                if f.alive and f.hp > 0:
                    heal = max(1, int(f.max_hp * heal_pct))
                    f.hp = min(f.max_hp, f.hp + heal)
            events.append(BattleEvent("skill", attacker=fighter.name,
                skill_type=skill_type,
                message=t("skill_heal_team", fighter=fighter.name, skill=skill["name"])))

    def _tick_skill_buffs(self):
        """Decrement durations of team buffs and shield after the turn resolves."""
        s = self.state
        # Team ATK buffs — keep scalar running total in sync with the list
        # to avoid the O(N) sum(genexpr) hot path every attack.
        remaining = []
        expired_atk_bonus = 0.0
        for buff in s.team_buffs:
            buff["turns_left"] -= 1
            if buff["turns_left"] > 0:
                remaining.append(buff)
            elif buff["type"] == "atk_bonus_pct":
                expired_atk_bonus += buff["value"]
        if expired_atk_bonus:
            s.team_atk_bonus_pct = max(0.0, s.team_atk_bonus_pct - expired_atk_bonus)
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
            # Rally: team ATK buff — O(1) scalar read, maintained by
            # _execute_skill / _tick_skill_buffs.
            if s.team_atk_bonus_pct:
                atk_mult += s.team_atk_bonus_pct

            atk_cache = self._fighter_stats(fighter)
            ev, actual, is_crit = _resolve_attack(
                fighter, target, is_boss=s.is_boss_fight,
                force_crit=force_crit, damage_mult=atk_mult,
                atk_cache=atk_cache)
            events.append(ev)

            if actual > 0:
                # Perk: lifesteal (cached)
                ls_pct = atk_cache['lifesteal_pct']
                if ls_pct > 0:
                    heal = max(1, int(actual * ls_pct))
                    fighter.hp = min(atk_cache['max_hp'], fighter.hp + heal)

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
                        # Stats may have changed via injury — drop cache entry.
                        self._invalidate_fighter_stats(fighter)
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

                # Perk: on_kill_heal (cached)
                okh_pct = atk_cache['on_kill_heal_pct']
                if okh_pct > 0:
                    mh = atk_cache['max_hp']
                    heal = max(1, int(mh * okh_pct))
                    fighter.hp = min(mh, fighter.hp + heal)

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
                        damage_mult=ss.extra_attack_mult * atk_mult,
                        atk_cache=atk_cache)
                    events.append(ev2)
                    if actual2 > 0:
                        ls_pct = atk_cache['lifesteal_pct']
                        if ls_pct > 0:
                            heal = max(1, int(actual2 * ls_pct))
                            fighter.hp = min(atk_cache['max_hp'], fighter.hp + heal)
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
                def_cache = self._fighter_stats(target)
                # Perk: damage_reduction + Shield Wall (multiplicative)
                dr = def_cache['damage_reduction']
                shield_dr = s.team_shield["reduction_pct"] if s.team_shield else 0
                combined_dr = 1 - (1 - dr) * (1 - shield_dr)
                hp_before = target.hp
                ev, actual, is_crit = _resolve_attack(
                    enemy, target, is_boss=s.is_boss_fight,
                    def_cache=def_cache)
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
                self._invalidate_fighter_stats(target)
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

    def _build_result(self):
        """Snapshot current battle state as a BattleResult."""
        s = self.state
        if s.phase == BattlePhase.VICTORY:
            outcome = "victory"
        elif s.phase == BattlePhase.DEFEAT:
            outcome = "defeat"
        else:
            outcome = "ongoing"
        return BattleResult(
            outcome=outcome,
            is_boss=s.is_boss_fight,
            gold_earned=s.gold_earned,
            enemies_killed=sum(1 for e in s.enemies if e.hp <= 0),
            survivors=[e for e in s.enemies if e.hp > 0],
            turn_number=s.turn_number,
            player_fighters=list(s.player_fighters),
            enemies=list(s.enemies),
        )

    def do_turn(self):
        """Execute one turn. Returns (events, result).

        events: list[BattleEvent] for animation.
        result: BattleResult describing current outcome (ongoing/victory/defeat).
        """
        s = self.state
        events = self._do_turn_events()
        return events, self._build_result()

    def _do_turn_events(self):
        """Internal: run one turn, return events only.

        Kept separate so do_turn can wrap with the result snapshot.
        """
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

    # Cap on skip-mode battle length. Turn-based (not event-based!) — a
    # 1000-vs-1000 battle legitimately emits thousands of events in a single
    # turn (one per attack), so the old 200-event cap was tripping on huge
    # legit battles. Turns, by contrast, don't scale with participant count:
    # any natural battle ends in 2-20 turns regardless of N. 500 is three
    # orders of magnitude beyond anything observed in real play, so it only
    # catches genuine stuck-loop bugs.
    MAX_SKIP_BATTLE_TURNS = 500

    def do_full_battle(self):
        """Run entire battle instantly (skip mode). Returns (events, result)."""
        all_events = []
        start_turn = self.state.turn_number
        while self.state.phase not in (BattlePhase.VICTORY, BattlePhase.DEFEAT,
                                        BattlePhase.IDLE):
            events = self._do_turn_events()
            all_events.extend(events)
            if self.state.turn_number - start_turn > self.MAX_SKIP_BATTLE_TURNS:
                # Stuck-loop safety: force-terminate by KO'ing every still-
                # standing fighter through handle_fighter_death (same path the
                # natural defeat uses), so injuries/permadeaths are applied
                # consistently. Previously this branch just stamped DEFEAT on
                # the phase and returned — fighters who still had HP > 0 kept
                # their pristine state and the user saw "some of my 1000
                # fighters walked away uninjured from a total defeat".
                self._force_defeat_cleanup(all_events)
                break
        return all_events, self._build_result()

    def _force_defeat_cleanup(self, events):
        """End an overrunning battle as a defeat, with injury/death parity.

        For every fighter still standing (alive + hp > 0), drop their HP to
        0 and route them through engine.handle_fighter_death so they receive
        either an injury or permadeath, exactly like a fighter who took a
        killing blow in the final turn. Then emit the 'defeat' event and
        heal the survivors (alive=True ones) — same as _enemy_attack_phase's
        natural defeat tail.
        """
        from game.data_loader import data_loader
        s = self.state
        for f in s.player_fighters:
            if f.alive and f.hp > 0:
                f.hp = 0
                died_forever, injury_id = self.engine.handle_fighter_death(f)
                self._invalidate_fighter_stats(f)
                if died_forever:
                    events.append(BattleEvent(
                        "death", defender=f.name, is_kill=True,
                        message=t("fallen_forever", name=f.name),
                    ))
                else:
                    inj_name = data_loader.injuries_by_id.get(
                        injury_id, {}).get("name", "?")
                    events.append(BattleEvent(
                        "death", defender=f.name,
                        message=t("knocked_out_injury",
                                  name=f.name, injury=inj_name),
                    ))
        s.phase = BattlePhase.DEFEAT
        events.append(BattleEvent("defeat", message=t("battle_all_down")))
        for f in s.player_fighters:
            if f.alive:
                f.heal()

    @property
    def is_active(self):
        return self.state.phase not in (BattlePhase.IDLE, BattlePhase.VICTORY,
                                         BattlePhase.DEFEAT)
