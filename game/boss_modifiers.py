# Build: 5
"""Boss modifier effects — hooks into battle phases."""

import random
from game.models import fmt_num
from game.localization import t

IMPLEMENTED_MODIFIERS = {"regeneration", "enrage", "thorns", "shield", "berserk"}

# Which modifiers actually do work in each hook. Other modifiers on the
# boss are no-ops in that hook, so we can skip iterating them. At 1000
# fighters × 40 turns that's ~42k calls to on_boss_hit, each iterating 3
# modifiers where 2 did nothing — 80k wasted dispatch checks before.
_HOOK_MODIFIERS = {
    "on_turn_start":       {"regeneration", "berserk"},
    "on_boss_hit":         {"thorns", "shield"},
    "on_boss_attack_pre":  {"enrage"},
}


class BossModifierHandler:
    """Processes boss modifier effects during battle.

    All per-boss state lives in EnemyStatusTracker.modifier_state.
    """

    def __init__(self, modifier_defs: dict):
        self._defs = modifier_defs

    # --- Assignment ---

    def assign_modifiers(self, boss, arena_tier: int):
        """Pick 1-3 random modifiers based on tier (only implemented ones)."""
        available = [k for k in self._defs if k in IMPLEMENTED_MODIFIERS]
        if not available:
            return
        count = min(len(available), 1 + arena_tier // 6)
        count = min(count, 3)
        boss.modifiers = random.sample(available, count)

    # --- Hook: start of turn (status tick phase) ---

    def on_turn_start(self, boss, tracker, turn_number):
        """Called each turn. Handles regeneration, berserk, shield countdown."""
        from game.battle import BattleEvent
        events = []
        active_hooks = _HOOK_MODIFIERS["on_turn_start"]
        for mod_id in getattr(boss, 'modifiers', []):
            if mod_id not in active_hooks:
                continue
            mod = self._defs.get(mod_id)
            if not mod:
                continue
            params = mod.get("params", {})

            if mod_id == "regeneration":
                heal = max(1, int(boss.max_hp * params.get("heal_pct", 0.03)))
                old_hp = boss.hp
                boss.hp = min(boss.max_hp, boss.hp + heal)
                actual = boss.hp - old_hp
                if actual > 0:
                    events.append(BattleEvent(
                        "status", defender=boss.name,
                        message=t("boss_regenerate", boss=boss.name, hp=fmt_num(actual)),
                        is_boss=True,
                    ))

            elif mod_id == "berserk":
                state = tracker.modifier_state.setdefault("berserk", {"stacks": 0})
                state["stacks"] += 1
                bonus_pct = params.get("atk_bonus_per_turn_pct", 0.05)
                bonus = int(tracker.original_attack * bonus_pct * state["stacks"])
                boss.attack = tracker.original_attack + bonus
                events.append(BattleEvent(
                    "status", defender=boss.name,
                    message=t("boss_rage", boss=boss.name, pct=int(bonus_pct * state['stacks'] * 100)),
                    is_boss=True,
                ))

            # shield countdown handled in on_boss_hit

        return events

    # --- Hook: after player hits boss ---

    def on_boss_hit(self, boss, tracker, attacker, damage):
        """Called after fighter deals damage to boss. Handles thorns, shield."""
        from game.battle import BattleEvent
        events = []
        active_hooks = _HOOK_MODIFIERS["on_boss_hit"]
        for mod_id in getattr(boss, 'modifiers', []):
            if mod_id not in active_hooks:
                continue  # regeneration/enrage/berserk don't fire on hit
            mod = self._defs.get(mod_id)
            if not mod:
                continue
            params = mod.get("params", {})

            if mod_id == "shield":
                # Shield active? Heal back part of the damage, then decrement
                state = tracker.modifier_state.setdefault(
                    "shield", {"hits_left": params.get("duration_turns", 3)}
                )
                if state.get("hits_left", 0) > 0:
                    reduction_pct = params.get("damage_reduction_pct", 0.30)
                    restored = max(1, int(damage * reduction_pct))
                    boss.hp = min(boss.max_hp, boss.hp + restored)
                    state["hits_left"] -= 1
                    if state["hits_left"] > 0:
                        events.append(BattleEvent(
                            "status", defender=boss.name,
                            message=t("boss_shield_absorb", dmg=fmt_num(restored), left=state['hits_left']),
                            is_boss=True,
                        ))
                    else:
                        events.append(BattleEvent(
                            "status", defender=boss.name,
                            message=t("boss_shield_shatter", dmg=fmt_num(restored)),
                            is_boss=True,
                        ))

            elif mod_id == "thorns":
                reflect_pct = params.get("reflect_pct", 0.15)
                reflect = max(1, int(damage * reflect_pct))
                attacker.hp = max(0, attacker.hp - reflect)
                events.append(BattleEvent(
                    "status", attacker=boss.name, defender=attacker.name,
                    damage=reflect,
                    message=t("boss_thorns", attacker=attacker.name, dmg=fmt_num(reflect)),
                    is_boss=True,
                ))

        return events

    # --- Hook: before boss attacks ---

    def on_boss_attack_pre(self, boss, tracker):
        """Called before boss damage roll. Returns stat overrides dict."""
        overrides = {}
        active_hooks = _HOOK_MODIFIERS["on_boss_attack_pre"]
        for mod_id in getattr(boss, 'modifiers', []):
            if mod_id not in active_hooks:
                continue
            mod = self._defs.get(mod_id)
            if not mod:
                continue
            params = mod.get("params", {})

            if mod_id == "enrage":
                threshold = params.get("hp_threshold_pct", 0.5)
                if boss.hp / max(1, boss.max_hp) <= threshold:
                    bonus = params.get("atk_bonus_pct", 0.20)
                    base = overrides.get("attack", boss.attack)
                    overrides["attack"] = int(base * (1 + bonus))

        return overrides
