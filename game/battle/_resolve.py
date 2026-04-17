# Build: 1
"""Attack resolution (_resolve_attack)."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import BattleEvent


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
