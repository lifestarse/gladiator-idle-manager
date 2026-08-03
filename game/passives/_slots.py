# Build: 1
"""Passive slot arithmetic — count, unlock thresholds, unlock predicate.

An item's passive slot count equals its rarity rank (common 1 ... legendary 5),
and slot #n activates once the item is upgraded to (n + 1) *
PASSIVE_SLOT_UNLOCK_STEP. Both facts are DERIVED, never stored:

* the slot index is the ``#n`` suffix already parsed by PassiveSpec.index, so
  data/item_passives.json needs no extra field, and a remote patch (which can
  rewrite that file wholesale) cannot desync a stored threshold from the
  rarity's slot count — a formula cannot drift;
* the slot count reuses RARITY_MAX_UPGRADE through get_max_upgrade, so
  ``RARITY_MAX_UPGRADE[r] == PASSIVE_SLOT_UNLOCK_STEP * slot_count(r)`` holds
  for every rarity (asserted by tests/test_item_passives.py) and each rarity's
  last slot unlocks exactly at its own upgrade cap.

These three helpers are the single source of the unlock rule: the effect gate
in game/models/fighterperksmixin.py, the compile-time dead-slot check in
_validate.py and every card/marker renderer in _render.py all call them —
nothing re-derives a threshold.
"""
from ._shared import *  # noqa: F401,F403
from ._shared import PASSIVE_SLOT_UNLOCK_STEP


def unlock_threshold(index):
    """Upgrade level at which slot `index` (the 0-based `#n`) activates."""
    return (index + 1) * PASSIVE_SLOT_UNLOCK_STEP


def slot_count(item):
    """Passive slot count for `item` — its rarity rank, 1..5.

    Only reads ``item["rarity"]``, so a minimal ``{"rarity": ...}`` dict is a
    legitimate argument where no full item exists (the validator has just the
    rarity string).
    """
    # Deferred: game.models.fighterperksmixin imports this package at module
    # scope, and importing game.models._helpers here would execute the
    # game.models package __init__ and close that cycle (see
    # memory/architecture/import-cycles.md). By the time anyone counts slots,
    # game.models is long imported. Same pattern as COMPILED_PASSIVES in
    # _render.py.
    from game.models._helpers import get_max_upgrade

    return get_max_upgrade(item) // PASSIVE_SLOT_UNLOCK_STEP


def is_unlocked(spec, item):
    """True if `item` is upgraded far enough for `spec`'s slot to be active.

    Gates on spec.index, not on list position — robust to index holes in
    mid-patch data. Called from Fighter.get_perk_effects on the stat hot path:
    one dict .get and one int compare, no allocation.
    """
    return item.get("upgrade_level", 0) >= unlock_threshold(spec.index)
