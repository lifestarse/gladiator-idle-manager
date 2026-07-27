# Build: 4
"""BattleManager _PlayerAttackPhaseMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import (BattlePhase, BattleEvent, EnemyStatusTracker,
                      SkillState, BattleState)
from ._enchantments import (_init_enemy_status, _trigger_enchantment,
                             _process_status_ticks)
from ._resolve import _resolve_attack


class _PlayerAttackPhaseMixin:
    def _pa_acquire_target(self, s):
        # None → nothing left to swing at, caller stops the phase.
        target = s.current_enemy
        if not target or target.hp <= 0:
            if not s.next_alive_enemy():
                return None
            target = s.current_enemy
        if not target:
            return None
        return target

    def _pa_attack_modifiers(self, s, fighter):
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
        return ss, force_crit, atk_mult

    def _pa_apply_lifesteal(self, fighter, atk_cache, damage):
        # Perk: lifesteal (cached)
        ls_pct = atk_cache['lifesteal_pct']
        if ls_pct > 0:
            heal = max(1, int(damage * ls_pct))
            fighter.hp = min(atk_cache['max_hp'], fighter.hp + heal)

    def _pa_build_enchantment(self, s, fighter, target, events):
        # Enchantment buildup on hit
        weapon = fighter.equipment.get("weapon")
        eid = id(target)
        if not weapon or eid not in s.enemy_status:
            return
        ench_id = weapon.get("enchantment")
        if not ench_id or ench_id not in ENCHANTMENT_TYPES:
            return
        ench = ENCHANTMENT_TYPES[ench_id]
        tracker = s.enemy_status[eid]
        tracker.status_buildup[ench_id] = tracker.status_buildup.get(ench_id, 0) + ench["buildup_per_hit"]
        if tracker.status_buildup[ench_id] >= ench["threshold"]:
            tracker.status_buildup[ench_id] = 0
            events.extend(_trigger_enchantment(s, target, ench_id, ench,
                                               attacker=fighter))
            self.engine.total_enchantment_procs += 1

    def _pa_award_kill(self, s, fighter, target, atk_cache, events):
        events.append(BattleEvent(
            "death", defender=target.name, is_kill=True,
            message=t("battle_destroyed", target=target.name),
            is_boss=s.is_boss_fight,
        ))
        reward = target.gold_reward
        gold_bonus = atk_cache['bonus_gold_pct']
        if gold_bonus > 0:
            reward = int(reward * (1 + gold_bonus))
        s.gold_earned += reward
        self.engine.award_gold(reward)
        target._kill_awarded = True
        fighter.kills += 1

    def _pa_apply_on_kill_heal(self, fighter, atk_cache):
        # Perk: on_kill_heal (cached)
        okh_pct = atk_cache['on_kill_heal_pct']
        if okh_pct > 0:
            mh = atk_cache['max_hp']
            heal = max(1, int(mh * okh_pct))
            fighter.hp = min(mh, fighter.hp + heal)

    def _pa_boss_hit_retaliation(self, s, fighter, target, actual, events):
        # Boss modifiers: on hit (target survived the blow).
        # True → thorns killed the attacker.
        if not (self._mod_handler and actual > 0 and getattr(target, 'modifiers', None)):
            return False
        tracker = s.enemy_status.get(id(target))
        if not tracker:
            return False
        events.extend(self._mod_handler.on_boss_hit(
            target, tracker, fighter, actual))
        # Thorns may have killed the attacker
        if fighter.hp > 0:
            return False
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
        return True

    def _pa_frenzy_attacks(self, s, fighter, ss, atk_mult, atk_cache, events):
        # Frenzy: extra attacks on same or next target
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
                self._pa_apply_lifesteal(fighter, atk_cache, actual2)
            if target.hp <= 0:
                self._pa_award_kill(s, fighter, target, atk_cache, events)
                if not s.any_enemies_alive():
                    break
                s.next_alive_enemy()
        ss.extra_attacks = 0

    def _player_attack_phase(self, events):
        """All fighters attack enemies.

        Returns True if all enemies are dead (victory via combat)."""
        s = self.state
        for i, fighter in enumerate(s.player_fighters):
            if not fighter.alive or fighter.hp <= 0:
                continue

            target = self._pa_acquire_target(s)
            if not target:
                break

            ss, force_crit, atk_mult = self._pa_attack_modifiers(s, fighter)
            atk_cache = self._fighter_stats(fighter)
            ev, actual, is_crit = _resolve_attack(
                fighter, target, is_boss=s.is_boss_fight,
                force_crit=force_crit, damage_mult=atk_mult,
                atk_cache=atk_cache)
            events.append(ev)

            if actual > 0:
                self._pa_apply_lifesteal(fighter, atk_cache, actual)
                self._pa_build_enchantment(s, fighter, target, events)

            if target.hp <= 0:
                # Death first: a corpse doesn't retaliate (no on_boss_hit),
                # and the kill must be paid before any early exit below.
                self._pa_award_kill(s, fighter, target, atk_cache, events)
                self._pa_apply_on_kill_heal(fighter, atk_cache)
                if not s.any_enemies_alive():
                    break
                s.next_alive_enemy()
            elif self._pa_boss_hit_retaliation(s, fighter, target, actual, events):
                # Only this fighter falls — the rest of the squad
                # still takes their swings this turn.
                continue

            if ss and ss.extra_attacks > 0:
                self._pa_frenzy_attacks(s, fighter, ss, atk_mult, atk_cache, events)

        # Check victory
        if not s.any_enemies_alive():
            self._declare_victory(events)
            return True
        return False
