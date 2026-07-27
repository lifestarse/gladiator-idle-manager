# Build: 1
"""Compile data/item_passives.json into COMPILED_PASSIVES.

Policy on bad input: WARN AND DROP, never raise. This runs inside
DataLoader/_wire_data on a shipped game, and the definitions can arrive from a
remote balance patch — the same reasoning as _validate_ids in
game/data_loader/_shared.py, which also only warns. A malformed entry costing
one item its passive is a bug report; a malformed entry crashing startup is a
dead install that no patch can reach.

Only STRUCTURE is validated here. Whether a number is well-balanced is a
different question, answered by the budget checks and the simulation.
"""
from ._registry import (CATEGORY_STATIC, COMPILED_PASSIVES, PASSIVE_KINDS,
                        PassiveSpec, static_effect_for)
from ._shared import *  # noqa: F401,F403
from ._shared import _log, PASSIVE_KEY_SEPARATOR, PASSIVE_MAX_PER_ITEM

# Default when an entry omits "cond". The condition vocabulary itself arrives
# with the triggered kinds; statics are unconditional by construction, so the
# only legal value at this stage is the default.
COND_ALWAYS = "always"


def _parse_key(key):
    """Split "<item_id>#<n>" into (item_id, n). Returns None if malformed."""
    item_id, sep, tail = str(key).rpartition(PASSIVE_KEY_SEPARATOR)
    if not sep or not item_id or not tail.isdigit():
        return None
    return item_id, int(tail)


def _check_params(key, kind_def, entry):
    """Return the validated param dict, or None with a warning logged.

    Rejects undeclared params rather than ignoring them: a typo'd param name
    would otherwise leave the passive silently running on its default.
    """
    params = {}
    for name, (low, high) in kind_def.params.items():
        if name not in entry:
            _log.warning("[passives] %s: missing required param %r", key, name)
            return None
        value = entry[name]
        # bool is a subclass of int — True would quietly become 1.0. Same trap
        # game/remote_content/gamedata.py:_reject_reason guards against.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _log.warning("[passives] %s: param %r must be a number, got %r",
                         key, name, value)
            return None
        if not low <= value <= high:
            _log.warning("[passives] %s: param %r = %r outside [%s, %s]",
                         key, name, value, low, high)
            return None
        params[name] = value

    reserved = {"item", "kind", "trigger", "cond", "cond_value"}
    extra = set(entry) - reserved - set(kind_def.params)
    if extra:
        _log.warning("[passives] %s: undeclared params %s for kind %r",
                     key, sorted(extra), kind_def.kind)
        return None
    return params


def _compile_entry(key, entry, slot_by_item):
    """Build one PassiveSpec, or return None with a warning logged."""
    if not isinstance(entry, dict):
        _log.warning("[passives] %s: entry must be an object", key)
        return None
    parsed = _parse_key(key)
    if parsed is None:
        _log.warning("[passives] %r: key must be \"<item_id>%s<n>\"",
                     key, PASSIVE_KEY_SEPARATOR)
        return None
    key_item, _index = parsed

    item_id = entry.get("item")
    if item_id != key_item:
        _log.warning("[passives] %s: \"item\" is %r but the key says %r",
                     key, item_id, key_item)
        return None
    if item_id not in slot_by_item:
        # Not shouted about: a definition file may legitimately mention content
        # a future build adds, the same tolerance apply_patch has.
        _log.info("[passives] %s: no such item, skipped", key)
        return None

    kind_def = PASSIVE_KINDS.get(entry.get("kind"))
    if kind_def is None:
        _log.warning("[passives] %s: unknown kind %r", key, entry.get("kind"))
        return None

    slot = slot_by_item[item_id]
    if slot not in kind_def.slots:
        _log.warning("[passives] %s: kind %r is not allowed on slot %r "
                     "(allowed: %s)", key, kind_def.kind, slot,
                     sorted(kind_def.slots))
        return None

    trigger = entry.get("trigger")
    if kind_def.category == CATEGORY_STATIC and trigger is not None:
        _log.warning("[passives] %s: static kind must not carry a trigger",
                     key)
        return None
    if kind_def.category != CATEGORY_STATIC and not trigger:
        _log.warning("[passives] %s: triggered kind needs a trigger", key)
        return None

    cond = entry.get("cond", COND_ALWAYS)
    if cond != COND_ALWAYS:
        _log.warning("[passives] %s: unknown condition %r", key, cond)
        return None
    cond_value = entry.get("cond_value", 0)
    if isinstance(cond_value, bool) or not isinstance(cond_value, (int, float)):
        _log.warning("[passives] %s: cond_value must be a number", key)
        return None

    params = _check_params(key, kind_def, entry)
    if params is None:
        return None

    return PassiveSpec(
        key=key, item_id=item_id, kind=kind_def.kind, kind_def=kind_def,
        trigger=trigger, cond=cond, cond_value=float(cond_value),
        params=params, static_effect=static_effect_for(kind_def, params),
    )


def slot_index(item_lists):
    """{item id: slot} over every equipment list the loader exposes."""
    index = {}
    for items in item_lists:
        for item in items:
            item_id = item.get("id")
            if item_id:
                index[item_id] = item.get("slot", "")
    return index


def compile_all(definitions, slot_by_item):
    """{item id: tuple[PassiveSpec, ...]} in `#n` order.

    Ordering is by the numeric suffix, not by dict insertion order: the JSON
    is hand-authored and a reordered file must not change dispatch order or
    the trigger sequence a player sees.
    """
    by_item = {}
    if not isinstance(definitions, dict):
        if definitions:
            _log.warning("[passives] definitions must be an object keyed "
                         "\"<item_id>%s<n>\"", PASSIVE_KEY_SEPARATOR)
        return by_item

    for key in sorted(definitions):
        spec = _compile_entry(key, definitions[key], slot_by_item)
        if spec is not None:
            by_item.setdefault(spec.item_id, []).append(spec)

    compiled = {}
    for item_id, specs in by_item.items():
        specs.sort(key=lambda s: s.index)
        indexes = [s.index for s in specs]
        if len(set(indexes)) != len(indexes):
            _log.warning("[passives] %s: duplicate index in %s", item_id,
                         indexes)
        if len(specs) > PASSIVE_MAX_PER_ITEM:
            _log.warning("[passives] %s: %d passives exceeds the cap of %d, "
                         "keeping the first %d", item_id, len(specs),
                         PASSIVE_MAX_PER_ITEM, PASSIVE_MAX_PER_ITEM)
            specs = specs[:PASSIVE_MAX_PER_ITEM]
        compiled[item_id] = tuple(specs)
    return compiled


def install(definitions, slot_by_item):
    """Compile and publish into COMPILED_PASSIVES, IN PLACE.

    In place because consumers capture the dict object at import time —
    game/models/fighterperksmixin.py among them. Rebinding would leave them
    reading an empty dict forever, which is exactly the achievements bug
    recorded at game/engine/wiringmixin.py:62.
    """
    compiled = compile_all(definitions, slot_by_item)
    COMPILED_PASSIVES.clear()
    COMPILED_PASSIVES.update(compiled)
    return COMPILED_PASSIVES
