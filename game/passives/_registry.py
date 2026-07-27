# Build: 2
"""Registry of passive-effect KINDS, and the compiled per-item lookup.

A "kind" is a mechanic (`lifesteal_pct`, `thorns_reflect`, ...) declared once,
in code, with its slot charter and its parameter ranges. A "spec" is one
instance of a kind bound to one item with concrete numbers, compiled from
data/item_passives.json. Items name kinds; they never define mechanics.

Dispatch style follows the one real callable registry the codebase already
has — BUILTIN_ACTIONS in game/scripting/builtins.py — rather than the three
flat if/elif chains (game/battle/_enchantments.py:35,
game/battle/_manager_skills.py:98, game/battle/_boss_modifiers.py). Ten
enchantment branches are readable; the ~35 kinds this is sized for would not be.
"""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from ._shared import *  # noqa: F401,F403
from ._shared import _log, SLOTS

# Category tells the consumer which machinery reads the kind, and it is what
# decides whether `trigger` is required or forbidden.
#   STATIC    — folded into Fighter.get_perk_effects; no battle-loop cost.
#   TRIGGERED — dispatched from a battle hook (added in a later stage).
CATEGORY_STATIC = "static"
CATEGORY_TRIGGERED = "triggered"
CATEGORIES = (CATEGORY_STATIC, CATEGORY_TRIGGERED)


@dataclass(frozen=True)
class PassiveKind:
    """Declaration of one mechanic.

    kind:         registry key, and the value items put in their "kind" field.
    category:     CATEGORY_STATIC or CATEGORY_TRIGGERED.
    effect_type:  STATIC only — the get_perk_effects() effect type this feeds.
                  Reusing that name is the whole point: every existing consumer
                  of the effect type picks the item up with no further wiring.
    slots:        which equipment slots may carry this kind. The precedent is
                  SlotDef.can_enchant (game/slots.py) — slot policy belongs in
                  a declaration, not in scattered `if slot == "weapon"` checks.
    params:       {param name: (low, high)} — the authoritative schema. A param
                  outside its range is a broken definition, not a balance
                  choice, and compile_all drops it.
    l10n:         en.json key for the player-facing rule line.
    l10n_args:    ((template kwarg, param name, multiplier), ...) — explicit so
                  a percent-shaped param can render as "6%" while the stored
                  value stays 0.06. No implicit name mangling.
    """
    kind: str
    category: str
    slots: frozenset
    params: Mapping[str, Tuple[float, float]]
    l10n: str
    l10n_args: Tuple[Tuple[str, str, float], ...] = ()
    effect_type: Optional[str] = None
    trigger: Optional[str] = None
    notes: str = ""


@dataclass(frozen=True)
class PassiveSpec:
    """One kind bound to one item with concrete numbers.

    `key` ("rusty_blade#0") is both the remote-patch address and the namespace
    for any per-battle counter, so two passives of the same kind on one item
    can never share state.

    `static_effect` is pre-built at compile time: get_perk_effects is called
    from every stat property, so the hot path must not construct dicts.
    """
    key: str
    item_id: str
    kind: str
    kind_def: PassiveKind
    trigger: Optional[str]
    cond: str
    cond_value: float
    params: Mapping[str, float]
    static_effect: Optional[Mapping[str, float]] = None

    @property
    def index(self):
        """The `#n` suffix — compilation and dispatch order."""
        _, _, tail = self.key.rpartition(PASSIVE_KEY_SEPARATOR)
        return int(tail)


# kind -> PassiveKind. Populated at import time by the _kinds_* modules.
PASSIVE_KINDS: dict = {}

# kind -> get_perk_effects effect type, for the static subset only. Kept as a
# separate flat map because Fighter.get_perk_effects reads it on a hot path and
# should not have to look through PassiveKind objects.
STATIC_EFFECT_KINDS: dict = {}

# item id -> tuple[PassiveSpec, ...] in `#n` order.
#
# Mutated IN PLACE by GameEngine._wire_data (.clear() + .update()), never
# rebound — the same contract every collection in game/models/_data.py has.
# Submodules and consumers capture this object at import time; a rebind would
# leave them looking at an empty dict. See CLAUDE.md and the achievements
# regression documented at game/engine/wiringmixin.py:62.
COMPILED_PASSIVES: dict = {}


def register_kind(kind_def):
    """Register a PassiveKind. Raises on a duplicate or malformed declaration.

    Loud at import time on purpose — a duplicate kind means two mechanics are
    fighting over one name, and every item naming it would silently get
    whichever module imported last. Same guard style as register_migration in
    game/engine/_shared.py:48.
    """
    if not isinstance(kind_def, PassiveKind):
        raise TypeError(f"expected PassiveKind, got {type(kind_def).__name__}")
    if kind_def.kind in PASSIVE_KINDS:
        raise ValueError(f"duplicate passive kind {kind_def.kind!r}")
    if kind_def.category not in CATEGORIES:
        raise ValueError(f"{kind_def.kind!r}: unknown category "
                         f"{kind_def.category!r}, expected one of {CATEGORIES}")
    unknown = set(kind_def.slots) - set(SLOTS)
    if unknown:
        raise ValueError(f"{kind_def.kind!r}: unknown slots {sorted(unknown)}")
    if not kind_def.slots:
        raise ValueError(f"{kind_def.kind!r}: declares no slots, so no item "
                         "could ever carry it")
    if kind_def.category == CATEGORY_STATIC:
        if not kind_def.effect_type:
            raise ValueError(f"{kind_def.kind!r}: static kinds must name the "
                             "get_perk_effects effect_type they feed")
        if kind_def.trigger:
            raise ValueError(f"{kind_def.kind!r}: static kinds are resolved at "
                             "stat-read time and must not declare a trigger")
    elif not kind_def.trigger:
        raise ValueError(f"{kind_def.kind!r}: triggered kinds must declare "
                         "their hook")
    for name, bounds in kind_def.params.items():
        if (not isinstance(bounds, tuple) or len(bounds) != 2
                or bounds[0] > bounds[1]):
            raise ValueError(f"{kind_def.kind!r}: param {name!r} needs a "
                             f"(low, high) range, got {bounds!r}")
    for kwarg, param, _mult in kind_def.l10n_args:
        if param not in kind_def.params:
            raise ValueError(f"{kind_def.kind!r}: l10n_args maps {kwarg!r} to "
                             f"undeclared param {param!r}")

    PASSIVE_KINDS[kind_def.kind] = kind_def
    if kind_def.category == CATEGORY_STATIC:
        STATIC_EFFECT_KINDS[kind_def.kind] = kind_def.effect_type
    return kind_def


def static_effect_for(kind_def, params):
    """Pre-built get_perk_effects payload for a static kind, or None.

    Static kinds carry exactly one numeric param named "value" so they can map
    onto the perk effect shape {"type": ..., "value": ...} without a per-kind
    adapter.
    """
    if kind_def.category != CATEGORY_STATIC:
        return None
    return MappingProxyType({"type": kind_def.effect_type,
                             "value": params["value"]})
