# Build: 1
"""Mutator registry — loads mutator definitions and computes reward multipliers."""

import logging

_log = logging.getLogger(__name__)


class MutatorRegistry:
    def __init__(self):
        self._mutators = {}  # id -> dict

    def load(self, mutator_list):
        """Load mutators from a list of dicts (each must have 'id')."""
        self._mutators = {m["id"]: m for m in mutator_list}
        _log.info("[MutatorRegistry] Loaded %d mutators", len(self._mutators))

    def get(self, mutator_id) -> dict | None:
        return self._mutators.get(mutator_id)

    def get_all(self) -> list:
        return list(self._mutators.values())

    def get_all_negative(self) -> list:
        return [m for m in self._mutators.values() if m["type"] == "negative"]

    def get_all_positive(self) -> list:
        return [m for m in self._mutators.values() if m["type"] == "positive"]

    def calc_reward_multiplier(self, active_ids: list) -> float:
        """Calculate combined reward multiplier from active mutators."""
        mult = 1.0
        for mid in active_ids:
            m = self.get(mid)
            if m:
                mult *= m["reward_mult"]
        return mult

    def has_effect(self, active_ids: list, effect_key: str) -> bool:
        """Check if any active mutator has a specific effect key."""
        for mid in active_ids:
            m = self.get(mid)
            if m and effect_key in m.get("effect", {}):
                return True
        return False

    def get_effect_value(self, active_ids: list, effect_key: str, default=None):
        """Get the value of a specific effect from active mutators.

        For multiplicative effects, returns the product of all matching values.
        For boolean effects, returns True if any mutator has it.
        """
        for mid in active_ids:
            m = self.get(mid)
            if m and effect_key in m.get("effect", {}):
                return m["effect"][effect_key]
        return default


mutator_registry = MutatorRegistry()
