# Build: 1
"""Enchantment trigger and status-tick logic."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import BattlePhase, BattleEvent, EnemyStatusTracker


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
