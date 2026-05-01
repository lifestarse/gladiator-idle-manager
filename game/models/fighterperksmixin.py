# Build: 4
"""Fighter _FighterPerksMixin — perk effect aggregation + active skill lookup."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler
from ._combat import CombatUnit
from ._data import FIGHTER_NAMES, FIGHTER_CLASSES


class _FighterPerksMixin:
    def get_perk_effects(self, effect_type):
        """Sum unlocked perk effect values of given type, including passive.

        Override semantic: if any source declares `{effect_type}_upgrade`,
        its value REPLACES the entire base sum. Used by perks that
        upgrade a passive (Resurgence: Field Surgery 3% → 5%; Riposte:
        Net Mastery 50% → 75%) — without this, the upgrade variant was a
        type mismatch and silently did nothing. Multiple upgrades in the
        same chain pick the largest value.
        """
        base = 0.0
        upgrade = None
        upgrade_type = effect_type + "_upgrade"
        cls_data = FIGHTER_CLASSES.get(self.fighter_class, {})

        def _consume(eff):
            nonlocal base, upgrade
            t = eff.get("type")
            if t == effect_type:
                base += eff.get("value", 0)
            elif t == upgrade_type:
                v = eff.get("value", 0)
                if upgrade is None or v > upgrade:
                    upgrade = v

        passive = cls_data.get("passive_ability")
        if passive:
            _consume(passive.get("effect", {}))
        all_perks = self._get_all_perks_map()
        for pid in self.unlocked_perks:
            perk = all_perks.get(pid)
            if perk:
                _consume(perk.get("effect", {}))
        return upgrade if upgrade is not None else base

    def get_active_skill(self):
        """Return the active skill definition dict for this fighter's class, or None."""
        cls_data = FIGHTER_CLASSES.get(self.fighter_class, {})
        return cls_data.get("active_skill")

    def get_perk_effect_data(self, effect_type):
        """Get full effect dict for a perk effect type (for max_stacks etc)."""
        all_perks = self._get_all_perks_map()
        for pid in self.unlocked_perks:
            perk = all_perks.get(pid)
            if perk:
                eff = perk.get("effect", {})
                if eff.get("type") == effect_type:
                    return eff
        return None

    @classmethod
    def invalidate_perks_map_cache(cls):
        """Call after reloading FIGHTER_CLASSES (e.g. language switch)."""
        cls._cached_all_perks_map = None

    @property
    def perk_tree_maxed(self):
        """True if all perks of own class are unlocked."""
        cls_data = FIGHTER_CLASSES.get(self.fighter_class, {})
        tree = cls_data.get("perk_tree", [])
        if not tree:
            return False
        own_ids = {p["id"] for p in tree}
        return own_ids.issubset(set(self.unlocked_perks))
