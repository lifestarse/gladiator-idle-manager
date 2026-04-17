# Build: 1
"""BattleManager _SkillsMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import (BattlePhase, BattleEvent, EnemyStatusTracker,
                      SkillState, BattleState)
from ._enchantments import (_init_enemy_status, _trigger_enchantment,
                             _process_status_ticks)
from ._resolve import _resolve_attack


class _SkillsMixin:
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
