# Build: 1
"""BattleManager _SupportPhasesMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import (BattlePhase, BattleEvent, EnemyStatusTracker,
                      SkillState, BattleState)
from ._enchantments import (_init_enemy_status, _trigger_enchantment,
                             _process_status_ticks)
from ._resolve import _resolve_attack


class _SupportPhasesMixin:
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
