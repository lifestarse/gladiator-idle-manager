# Build: 1
"""Validate and apply a remote balance patch.

Text is forgiving — a bad string is ugly. Numbers are not: a mistyped cost can
hand every player infinite gold, and there is no way to take it back once saves
have absorbed it. So this module is deliberately narrow.

Three constraints, all enforced here:

* Only the fields in PATCHABLE may be touched. Identity and behaviour fields
  (id, slot, rarity, effect, severity, special_effect, ...) are not patchable
  at any price — changing "effect" reroutes code paths, changing "rarity"
  changes upgrade caps, and neither is balance.
* Only entries that already exist may be modified. A patch cannot add an item,
  an enemy or an expedition; new content needs new code paths and ships through
  Play.
* Every value must be a number inside its declared range. The ranges are the
  point: they are what turns "someone fat-fingered a zero" from an economy
  reset into a rejected key.

Descriptive text is NOT patchable here even though it lives in these files —
it goes through data/languages/data_XX.json and the language pipeline, which
already has its own gate.
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)

# section -> (data file, top-level key, {field: (low, high)})
#
# Ranges are generous enough for real rebalancing and tight enough that a typo
# lands outside them. They are bounds on sanity, not on design.
PATCHABLE = {
    "weapons": ("weapons.json", "items", {
        "cost": (0, 10_000_000),
        "base_str": (0, 1000), "base_agi": (0, 1000), "base_vit": (0, 1000),
    }),
    "armor": ("armor.json", "items", {
        "cost": (0, 10_000_000),
        "base_str": (0, 1000), "base_agi": (0, 1000), "base_vit": (0, 1000),
    }),
    "accessories": ("accessories.json", "items", {
        "cost": (0, 10_000_000),
        "base_str": (0, 1000), "base_agi": (0, 1000), "base_vit": (0, 1000),
    }),
    "relics": ("relics.json", "items", {
        "cost": (0, 10_000_000),
        "base_str": (0, 1000), "base_agi": (0, 1000), "base_vit": (0, 1000),
    }),
    "expeditions": ("expeditions.json", "expeditions", {
        "duration": (1, 604_800),          # one second to one week
        "danger": (0.0, 1.0),
        "min_level": (1, 1000),
        "relic_chance": (0.0, 1.0),
        "shard_tier": (1, 5),
    }),
    "enchantments": ("enchantments.json", "enchantments", {
        "cost_gold": (0, 10_000_000),
        "cost_shard_count": (0, 10_000),
        "cost_shard_tier": (1, 5),
        "threshold": (1, 100_000),
        "buildup_per_hit": (0, 100_000),
        "dot_pct": (0.0, 1.0), "dot_turns": (0, 100),
        "burst_pct": (0.0, 10.0),
        "burst_pct_boss": (0.0, 10.0), "burst_pct_normal": (0.0, 10.0),
        "heal_pct": (0.0, 10.0),
        "reduction_pct": (0.0, 1.0), "atk_reduction_pct": (0.0, 1.0),
        "debuff_turns": (0, 100), "skip_turns": (0, 100),
    }),
    "injuries": ("injuries.json", "injuries", {
        "chance_weight": (0, 10_000),
        "heal_cost_multiplier": (0.0, 1000.0),
    }),
    "enemies": ("enemies.json", "enemies", {
        # Enemies carry no stat fields — they are derived from tier, role and
        # stat_bias — so tier is the only balance lever here. role/stat_bias
        # select code paths and stay out.
        "tier": (1, 1000),
    }),
}

MAX_ENTRIES = 5000


def validate(patch):
    """Return (accepted, rejected).

    accepted: {section: {entry_id: {field: value}}}
    rejected: {"section.entry.field": reason}
    """
    accepted, rejected = {}, {}
    if not isinstance(patch, dict):
        return {}, {"<patch>": "not a JSON object"}

    count = 0
    for section, entries in patch.items():
        if section not in PATCHABLE:
            rejected[section] = "not a patchable section"
            continue
        if not isinstance(entries, dict):
            rejected[section] = "section must map entry ids to field objects"
            continue
        fields_spec = PATCHABLE[section][2]
        for entry_id, fields in entries.items():
            if not isinstance(fields, dict):
                rejected[f"{section}.{entry_id}"] = "entry must be an object"
                continue
            for field, value in fields.items():
                count += 1
                if count > MAX_ENTRIES:
                    rejected["<patch>"] = f"more than {MAX_ENTRIES} field writes"
                    return {}, rejected
                reason = _reject_reason(field, value, fields_spec)
                if reason:
                    rejected[f"{section}.{entry_id}.{field}"] = reason
                else:
                    accepted.setdefault(section, {}).setdefault(entry_id, {})[field] = value
    return accepted, rejected


def _reject_reason(field, value, fields_spec):
    if field not in fields_spec:
        return "field is not patchable"
    # bool is a subclass of int; True would silently become 1 in a cost field.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"must be a number, got {type(value).__name__}"
    low, high = fields_spec[field]
    if not low <= value <= high:
        return f"{value} outside allowed range [{low}, {high}]"
    return None


def _entries_of(node):
    """Yield (entry_id, entry_dict) for either shape data files come in.

    Items and enemies are lists of dicts carrying an "id"; enchantments and
    mutators are dicts keyed by id.
    """
    if isinstance(node, dict):
        for entry_id, entry in node.items():
            if isinstance(entry, dict):
                yield entry_id, entry
    elif isinstance(node, list):
        for entry in node:
            if isinstance(entry, dict) and "id" in entry:
                yield entry["id"], entry


def apply_patch(loader, patch):
    """Overlay a validated balance patch onto an already-loaded DataLoader.

    Must run after the raw files are read and BEFORE the tier indexes are
    built, because patching an enemy's tier moves it between pools.

    Returns the number of field writes applied.
    """
    accepted, rejected = validate(patch)
    if rejected:
        sample = list(rejected.items())[:3]
        _log.warning("[remote] balance patch: %d writes rejected, e.g. %s",
                     len(rejected), sample)

    # section -> the loaded attribute holding it
    targets = {
        "weapons": getattr(loader, "_weapons", None),
        "armor": getattr(loader, "_armor", None),
        "accessories": getattr(loader, "_accessories", None),
        "relics": getattr(loader, "_relics", None),
        "expeditions": getattr(loader, "_expeditions", None),
        "enchantments": getattr(loader, "_enchantments", None),
        "injuries": getattr(loader, "_injuries", None),
        "enemies": getattr(loader, "_enemies", None),
    }

    applied = 0
    for section, entries in accepted.items():
        node = targets.get(section)
        if node is None:
            continue
        by_id = dict(_entries_of(node))
        for entry_id, fields in entries.items():
            entry = by_id.get(entry_id)
            if entry is None:
                # Not an error worth shouting about: a patch may legitimately
                # mention content that a future build adds or an old one lacks.
                continue
            for field, value in fields.items():
                if field in entry:
                    entry[field] = value
                    applied += 1
    return applied
