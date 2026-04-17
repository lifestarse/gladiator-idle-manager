# Build: 1
"""BattleManager core — orchestrates turns and mixin phases."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import (BattlePhase, BattleEvent, EnemyStatusTracker,
                      SkillState, BattleState)
from ._enchantments import (_init_enemy_status, _trigger_enchantment,
                             _process_status_ticks)
from ._resolve import _resolve_attack
from ._manager_player_attack import _PlayerAttackPhaseMixin
from ._manager_enemy_attack import _EnemyAttackPhaseMixin
from ._manager_support import _SupportPhasesMixin
from ._manager_skills import _SkillsMixin
from ._manager_stats import _StatsMixin


class BattleManager(_PlayerAttackPhaseMixin, _EnemyAttackPhaseMixin, _SupportPhasesMixin, _SkillsMixin, _StatsMixin):
    # Cap on turn count for the "skip to end" path — prevents infinite battle
    # loops if both sides keep dodging / healing.
    MAX_SKIP_BATTLE_TURNS = 500

    def __init__(self, engine):
        self.engine = engine
        self.state = BattleState()
        self._mod_handler = None

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

    @property
    def is_active(self):
        return self.state.phase not in (BattlePhase.IDLE, BattlePhase.VICTORY,
                                         BattlePhase.DEFEAT)
