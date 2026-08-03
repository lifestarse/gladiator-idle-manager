# Build: 6
"""Fighter _FighterPerksMixin — perk effect aggregation + active skill lookup."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler
from ._combat import CombatUnit
from ._data import FIGHTER_NAMES, FIGHTER_CLASSES

# Imported here rather than in _imports.py: this is the only consumer in the
# package, so the dependency stays visible where it is used. Safe direction —
# game.passives reaches only game.constants, game.slots and game.localization,
# none of which import game.models. Captured by reference and mutated in place
# by GameEngine._wire_data, so this binding never goes stale.
from game.passives import COMPILED_PASSIVES, is_unlocked


class _FighterPerksMixin:
    def get_perk_effects(self, effect_type):
        """Sum effect values of given type from every source the fighter has:
        the class passive ability, unlocked perks, and equipped-item passives.

        Override semantic: if any source declares `{effect_type}_upgrade`,
        its value REPLACES the entire base sum. Used by perks that
        upgrade a passive (Resurgence: Field Surgery 3% → 5%; Riposte:
        Net Mastery 50% → 75%) — without this, the upgrade variant was a
        type mismatch and silently did nothing. Multiple upgrades in the
        same chain pick the largest value.

        Equipment is the third source and it is intentionally routed through
        the same `_consume`. Static item passives name an existing effect type,
        so folding them in here makes every downstream consumer item-aware at
        once — the derived stats in fighterstatsmixin, `reduce_injury_severity`
        in _fighter.py, and the five perk-derived keys snapshotted by
        BattleManager._fighter_stats — with no per-consumer wiring and no new
        code in the battle loop.
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

        # Equipped-item passives. Guarded by the emptiness check because this
        # method is called from every stat property, and stat properties are
        # read at UI rate across the whole roster: with no passives compiled
        # (a data file that failed to load) the cost stays a single dict test.
        # Slot order is EQUIPMENT_SLOTS, which is list(SLOTS.keys()) and so
        # deterministic — required, since a sum of floats is order-sensitive.
        # is_unlocked gates each spec on THIS item instance's upgrade_level:
        # slot #n activates only from +(n+1)*PASSIVE_SLOT_UNLOCK_STEP, and a
        # locked slot must contribute nothing. Battle is covered through the
        # same gate — BattleManager._fighter_stats snapshots via this method.
        if COMPILED_PASSIVES:
            for slot in EQUIPMENT_SLOTS:
                item = self.equipment.get(slot)
                if not item:
                    continue
                for spec in COMPILED_PASSIVES.get(item.get("id", ""), ()):
                    if (spec.static_effect is not None
                            and is_unlocked(spec, item)):
                        _consume(spec.static_effect)

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
