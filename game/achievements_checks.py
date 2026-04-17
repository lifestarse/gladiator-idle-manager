# Build: 1
"""Achievement condition-checker builder (split from achievements.py)."""
import logging

def _build_check(condition):
    """Convert a JSON condition dict into a callable check(engine) -> bool."""
    ctype = condition.get("type", "")
    val = condition.get("value")

    # Simple engine attribute >= value
    _ATTR_GTE = {
        "wins_gte": "total_wins",
        "bosses_killed_gte": "bosses_killed",
        "tier_gte": "arena_tier",
        "total_gold_gte": "total_gold_earned",
        "total_deaths_gte": "total_deaths",
        "story_chapter_gte": "story_chapter",
        "runs_completed_gte": "total_runs",
        "expeditions_completed_gte": lambda e: getattr(e, "total_expeditions_completed", 0),
        "lore_entries_gte": lambda e: len(getattr(e, "lore_unlocked", [])),
        "injuries_healed_gte": lambda e: getattr(e, "total_injuries_healed", 0),
        "enchantments_applied_gte": lambda e: getattr(e, "total_enchantments_applied", 0),
        "enchantment_procs_gte": lambda e: getattr(e, "total_enchantment_procs", 0),
        "gold_spent_equipment_gte": lambda e: getattr(e, "total_gold_spent_equipment", 0),
    }

    if ctype in _ATTR_GTE:
        getter = _ATTR_GTE[ctype]
        if callable(getter):
            return lambda e, g=getter, v=val: g(e) >= v
        return lambda e, a=getter, v=val: getattr(e, a, 0) >= v

    if ctype == "fighters_alive_gte":
        return lambda e, v=val: len([f for f in e.fighters if f.alive]) >= v

    if ctype == "fighter_level_gte":
        return lambda e, v=val: any(f.level >= v for f in e.fighters if f.alive)

    if ctype == "fighter_injuries_gte":
        return lambda e, v=val: any(f.injury_count >= v for f in e.fighters if f.alive)

    if ctype == "unique_classes_gte":
        return lambda e, v=val: len({
            f.fighter_class for f in e.fighters if f.alive and f.fighter_class
        }) >= v

    if ctype == "has_class":
        return lambda e, v=val: any(
            f.fighter_class == v for f in e.fighters if f.alive
        )

    if ctype == "fighter_perks_gte":
        return lambda e, v=val: any(
            len(getattr(f, "unlocked_perks", [])) >= v for f in e.fighters if f.alive
        )

    if ctype == "fighter_perk_tree_maxed":
        return lambda e: any(
            getattr(f, "perk_tree_maxed", False) for f in e.fighters if f.alive
        )

    if ctype == "has_equipped_item":
        return lambda e: any(
            any(f.equipment.get(s) for s in ["weapon", "armor", "accessory"])
            for f in e.fighters if f.alive
        )

    if ctype == "has_equipped_rarity":
        return lambda e, v=val: any(
            any(
                f.equipment.get(s, {}).get("rarity") == v
                if f.equipment.get(s) else False
                for s in ["weapon", "armor", "accessory"]
            )
            for f in e.fighters if f.alive
        )

    if ctype == "relics_collected_gte":
        return lambda e, v=val: (
            sum(1 for f in e.fighters if f.equipment.get("relic")) +
            sum(1 for i in e.inventory if i.get("slot") == "relic")
        ) >= v

    if ctype == "has_permanent_injury":
        return lambda e: any(
            getattr(f, "has_permanent_injury", False)
            for f in e.fighters if f.alive
        )

    if ctype == "expedition_completed_specific":
        return lambda e, v=val: any(
            v.replace("_", " ").lower() in log.lower() and "returned" in log.lower()
            for log in e.expedition_log
        )

    _log.warning("Unknown achievement condition type: %s", ctype)
    return lambda e: False
