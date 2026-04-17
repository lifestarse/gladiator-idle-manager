# Build: 1
"""BattleManager _EnemyAttackPhaseMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import (BattlePhase, BattleEvent, EnemyStatusTracker,
                      SkillState, BattleState)
from ._enchantments import (_init_enemy_status, _trigger_enchantment,
                             _process_status_ticks)
from ._resolve import _resolve_attack


class _EnemyAttackPhaseMixin:
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
