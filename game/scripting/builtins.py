# Build: 3
"""Registries of read-only fields and side-effect actions exposed to scripts.

All callables receive the live engine for side effects. They MUST be:
- Idempotent (re-applying yields no change after the first effect).
- No-op when preconditions fail (e.g. start_arena_battle while battle_active).
- Robust to optional engine APIs (use getattr with sensible fallbacks) so
  this module does not hard-couple to PR1/PR2 not-yet-merged code.
"""
from __future__ import annotations
from typing import Callable, Any


# ---------- field accessors ----------

def _hp_pct(f) -> float:
    max_hp = max(1, getattr(f, "max_hp", 1))
    return max(0.0, getattr(f, "hp", 0) / max_hp * 100.0)


def _has_any_injury(f) -> bool:
    inj = getattr(f, "injuries", None)
    if inj is None:
        return False
    try:
        return len(inj) > 0
    except TypeError:
        return bool(inj)


def _has_slot(f, slot: str) -> bool:
    """True iff the fighter has something in `slot`. Works for both
    fighter.equipment dict and direct slot attributes (test stubs)."""
    eq = getattr(f, "equipment", None)
    if isinstance(eq, dict):
        return eq.get(slot) is not None
    return getattr(f, slot, None) is not None


BUILTIN_FIELDS: dict[str, Callable[[Any], Any]] = {
    # numeric
    "hp":         lambda f: getattr(f, "hp", 0),
    "max_hp":     lambda f: getattr(f, "max_hp", 0),
    "hp_pct":     _hp_pct,
    "fatigue":    lambda f: getattr(f, "fatigue", 0),
    "stamina":    lambda f: getattr(f, "stamina", 100),
    "level":      lambda f: getattr(f, "level", 1),
    "strength":   lambda f: getattr(f, "strength", 0),
    "agility":    lambda f: getattr(f, "agility", 0),
    "vitality":   lambda f: getattr(f, "vitality", 0),
    # bool
    "is_active":      lambda f: bool(getattr(f, "is_active", True)),
    "is_exhausted":   lambda f: bool(getattr(f, "is_exhausted", False)),
    "available":      lambda f: bool(getattr(f, "available", True)),
    "alive":          lambda f: bool(getattr(f, "alive", True)),
    "has_any_injury": _has_any_injury,
    "has_weapon":     lambda f: _has_slot(f, "weapon"),
    "has_armor":      lambda f: _has_slot(f, "armor"),
    "has_accessory":  lambda f: _has_slot(f, "accessory"),
    "has_relic":      lambda f: _has_slot(f, "relic"),
    # str
    "name":         lambda f: getattr(f, "name", ""),
    "fighter_class": lambda f: getattr(f, "fighter_class", ""),
}


def _count_inventory_slot(engine, slot: str) -> int:
    inv = getattr(engine, "inventory", []) or []
    return sum(1 for it in inv if isinstance(it, dict) and it.get("slot") == slot)


def _engine_field(engine, name: str):
    if name == "available_count":
        return sum(1 for f in getattr(engine, "fighters", []) if getattr(f, "available", True))
    if name == "active_count":
        return sum(1 for f in getattr(engine, "fighters", []) if getattr(f, "is_active", True))
    if name == "fighter_count":
        return len(getattr(engine, "fighters", []))
    if name == "inventory_size":
        return len(getattr(engine, "inventory", []) or [])
    if name == "inv_weapons":     return _count_inventory_slot(engine, "weapon")
    if name == "inv_armor":       return _count_inventory_slot(engine, "armor")
    if name == "inv_accessories": return _count_inventory_slot(engine, "accessory")
    if name == "inv_relics":      return _count_inventory_slot(engine, "relic")
    return getattr(engine, name)


BUILTIN_ENGINE_FIELDS = {
    "gold", "diamonds", "victories", "current_tier", "battle_active",
    "expedition_active", "fighter_count", "active_count", "available_count",
    "current_floor",
    "inventory_size", "inv_weapons", "inv_armor", "inv_accessories", "inv_relics",
}


# ---------- value-returning calls ----------

def _len(args):
    if len(args) != 1:
        raise ValueError("len() takes exactly 1 arg")
    a = args[0]
    if a is None:
        return 0
    return len(a)


def _min(args):
    if len(args) < 1:
        raise ValueError("min() takes at least 1 arg")
    return min(args)


def _max(args):
    if len(args) < 1:
        raise ValueError("max() takes at least 1 arg")
    return max(args)


def _abs(args):
    if len(args) != 1:
        raise ValueError("abs() takes exactly 1 arg")
    return abs(args[0])


BUILTIN_CALLS: dict[str, Callable[[list], Any]] = {
    "len": _len,
    "min": _min,
    "max": _max,
    "abs": _abs,
}


# ---------- side-effect actions ----------

def _bench(engine, fighter):
    if fighter is None:
        return
    if getattr(fighter, "is_active", True):
        fighter.is_active = False


def _activate(engine, fighter):
    if fighter is None:
        return
    if not getattr(fighter, "is_active", True):
        fighter.is_active = True


def _unequip_all(engine, fighter):
    if fighter is None:
        return
    fn = getattr(engine, "unequip_all", None)
    if callable(fn):
        fn(fighter)
        return
    # Fallback: clear known equip slots if they exist as attributes.
    for slot in ("weapon", "armor", "accessory", "relic"):
        if hasattr(fighter, slot):
            setattr(fighter, slot, None)


def _unequip_slot(engine, fighter, slot):
    if fighter is None or not isinstance(slot, str):
        return
    fn = getattr(engine, "unequip_slot", None)
    if callable(fn):
        fn(fighter, slot)
        return
    if hasattr(fighter, slot):
        setattr(fighter, slot, None)


def _start_arena_battle(engine):
    if getattr(engine, "battle_active", False):
        return
    fn = getattr(engine, "start_auto_battle", None)
    if callable(fn):
        fn()


def _stop_arena_battle(engine):
    fn = getattr(engine, "stop_auto_battle", None) or getattr(engine, "stop_battle", None)
    if callable(fn):
        fn()


def _start_expedition(engine, tier):
    try:
        tier = int(tier)
    except (TypeError, ValueError):
        return
    if getattr(engine, "expedition_active", False):
        return
    fn = getattr(engine, "start_expedition", None)
    if callable(fn):
        fn(tier)


def _stop_expedition(engine):
    fn = getattr(engine, "stop_expedition", None)
    if callable(fn):
        fn()


def _spawn_boss(engine):
    if getattr(engine, "battle_active", False):
        return
    fn = getattr(engine, "spawn_boss_enemy", None) or getattr(engine, "spawn_boss", None)
    if callable(fn):
        fn()


def _log(engine, message):
    fn = getattr(engine, "log_event", None) or getattr(engine, "add_event", None)
    if callable(fn):
        try:
            fn(str(message))
        except Exception:
            pass


# ---------- forge / inventory side-effects ----------

_VALID_SLOTS = ("weapon", "armor", "accessory", "relic")


def _find_fighter_idx(engine, fighter):
    if fighter is None:
        return -1
    fs = getattr(engine, "fighters", []) or []
    for i, f in enumerate(fs):
        if f is fighter:
            return i
    return -1


def _buy_item(engine, slot):
    """Buy the cheapest *affordable* forge item with matching slot.

    No-op if `slot` invalid, no affordable items, or required engine
    methods are unavailable. Item lands in `engine.inventory`.
    """
    if slot not in _VALID_SLOTS:
        return
    get_items = getattr(engine, "get_forge_items", None)
    buy_fn = getattr(engine, "buy_forge_item", None)
    if not callable(get_items) or not callable(buy_fn):
        return
    try:
        items = get_items()
    except Exception:
        return
    affordable = [
        i for i in items
        if isinstance(i, dict)
        and i.get("slot") == slot
        and i.get("affordable")
    ]
    if not affordable:
        return
    cheapest = min(affordable, key=lambda i: i.get("cost", 0))
    try:
        buy_fn(cheapest["id"])
    except Exception:
        pass


def _equip_best(engine, fighter, slot):
    """Equip best inventory item of `slot` onto fighter (battle-blocked).

    Heuristic: highest (cost, upgrade_level) wins. No-op if no candidate,
    fighter not in roster, battle in progress, or engine API absent.
    """
    if fighter is None or slot not in _VALID_SLOTS:
        return
    if getattr(engine, "battle_active", False):
        return
    fidx = _find_fighter_idx(engine, fighter)
    if fidx < 0:
        return
    inv = getattr(engine, "inventory", None) or []
    best_idx = -1
    best_score = (-1, -1)
    for idx, it in enumerate(inv):
        if not isinstance(it, dict) or it.get("slot") != slot:
            continue
        score = (it.get("cost", 0), it.get("upgrade_level", 0))
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_idx < 0:
        return
    fn = getattr(engine, "equip_from_inventory", None)
    if callable(fn):
        try:
            fn(fidx, best_idx)
        except Exception:
            pass


# ---------- fighter management actions ----------

_VALID_CLASSES = ("mercenary", "assassin", "tank", "berserker", "retiarius", "medicus")

# Defensive cap on train_to: a runaway state (e.g. infinite gold + buggy
# upgrade_gladiator that never increments level) must not deadlock the
# script. Real cost growth puts even infinite gold well below this in
# practice, so the cap only fires when something is wrong.
_TRAIN_TO_HARD_CAP = 200


def _hire(engine, class_id):
    """Hire a fighter of `class_id`. Engine handles cost / log / save.

    No-op when class invalid, gold insufficient, or engine API absent.
    """
    if not isinstance(class_id, str) or class_id not in _VALID_CLASSES:
        return
    fn = getattr(engine, "hire_gladiator", None)
    if not callable(fn):
        return
    try:
        fn(class_id)
    except Exception:
        pass


def _train_to(engine, fighter, target_level):
    """Level a fighter up to `target_level` via repeated upgrade_gladiator.

    Stops on: target reached, upgrade_gladiator returns not-ok (typically
    not_enough_gold / fighter_dead), missing API, or hard iteration cap.
    Idempotent: if level is already >= target, does nothing.
    """
    if fighter is None:
        return
    try:
        target = int(target_level)
    except (TypeError, ValueError):
        return
    if target < 1:
        return
    fidx = _find_fighter_idx(engine, fighter)
    if fidx < 0:
        return
    fn = getattr(engine, "upgrade_gladiator", None)
    if not callable(fn):
        return
    iters = 0
    while iters < _TRAIN_TO_HARD_CAP:
        if getattr(fighter, "level", 1) >= target:
            return
        try:
            result = fn(fidx)
        except Exception:
            return
        if not getattr(result, "ok", False):
            return
        iters += 1


def _give_item(engine, fighter, item_id):
    """Buy `item_id` from forge and equip it on `fighter` atomically.

    Wraps engine.equip_item_on which handles gold / battle / dead-fighter
    preconditions. No-op when fighter missing, item_id falsy/non-string,
    or API absent.
    """
    if fighter is None or not isinstance(item_id, str) or not item_id:
        return
    fidx = _find_fighter_idx(engine, fighter)
    if fidx < 0:
        return
    fn = getattr(engine, "equip_item_on", None)
    if not callable(fn):
        return
    try:
        fn(fidx, item_id)
    except Exception:
        pass


def _forge_upgrade(engine, fighter, slot):
    """Upgrade the item currently equipped in `slot` on `fighter` (uses shards).

    No-op if nothing equipped in that slot, battle in progress, or upgrade
    API not present. The engine's upgrade_item handles shard cost / max-level
    and is itself a no-op when not enough shards.
    """
    if fighter is None or slot not in _VALID_SLOTS:
        return
    if getattr(engine, "battle_active", False):
        return
    eq = getattr(fighter, "equipment", None)
    item = eq.get(slot) if isinstance(eq, dict) else getattr(fighter, slot, None)
    if not item:
        return
    fn = getattr(engine, "upgrade_item", None)
    if callable(fn):
        try:
            fn(item)
        except Exception:
            pass


# Each entry:
#   fn           — callable(engine, *args)
#   args         — (min, max) arg-count
#   fighter_arg  — first arg is a Fighter (palette pre-fills with LocalVar("f"))
#   default_args — optional list of default Expression values for the palette
#                  to drop in when adding the block. Falls back to Const(0).
def _ast_const_str(value):
    # Avoid a hard import of Const at module top to dodge circular imports.
    from .ast_nodes import Const
    return Const(value)


BUILTIN_ACTIONS: dict[str, dict] = {
    "bench":              {"fn": _bench,              "args": (1, 1), "fighter_arg": True},
    "activate":           {"fn": _activate,           "args": (1, 1), "fighter_arg": True},
    "unequip_all":        {"fn": _unequip_all,        "args": (1, 1), "fighter_arg": True},
    "unequip_slot":       {"fn": _unequip_slot,       "args": (2, 2), "fighter_arg": True,
                           "default_args_after_fighter": [_ast_const_str("weapon")]},
    "start_arena_battle": {"fn": _start_arena_battle, "args": (0, 0), "fighter_arg": False},
    "stop_arena_battle":  {"fn": _stop_arena_battle,  "args": (0, 0), "fighter_arg": False},
    "start_expedition":   {"fn": _start_expedition,   "args": (1, 1), "fighter_arg": False,
                           "default_args": [_ast_const_str(1)]},
    "stop_expedition":    {"fn": _stop_expedition,    "args": (0, 0), "fighter_arg": False},
    "spawn_boss":         {"fn": _spawn_boss,         "args": (0, 0), "fighter_arg": False},
    "log":                {"fn": _log,                "args": (1, 1), "fighter_arg": False,
                           "default_args": [_ast_const_str("hello")]},
    "buy_item":           {"fn": _buy_item,           "args": (1, 1), "fighter_arg": False,
                           "default_args": [_ast_const_str("weapon")]},
    "equip_best":         {"fn": _equip_best,         "args": (2, 2), "fighter_arg": True,
                           "default_args_after_fighter": [_ast_const_str("weapon")]},
    "forge_upgrade":      {"fn": _forge_upgrade,      "args": (2, 2), "fighter_arg": True,
                           "default_args_after_fighter": [_ast_const_str("weapon")]},
    "hire":               {"fn": _hire,               "args": (1, 1), "fighter_arg": False,
                           "default_args": [_ast_const_str("mercenary")]},
    "train_to":           {"fn": _train_to,           "args": (2, 2), "fighter_arg": True,
                           "default_args_after_fighter": [_ast_const_str(10)]},
    "give_item":          {"fn": _give_item,          "args": (2, 2), "fighter_arg": True,
                           "default_args_after_fighter": [_ast_const_str("")]},
}
