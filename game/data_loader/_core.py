# Build: 5
"""DataLoader core."""
from ._shared import *  # noqa: F401,F403
from ._shared import _data_dir, _log
from .loadmethodsmixin import _LoadMethodsMixin
from .translationmixin import _TranslationMixin


class DataLoader(_LoadMethodsMixin, _TranslationMixin):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._normals_by_tier = {}
            cls._instance._bosses_by_tier = {}
            cls._instance._expeditions = []
        return cls._instance

    def load_all(self):
        """Load every data file. Safe to call multiple times (no-op after first)."""
        if self._loaded:
            return
        base = _data_dir()

        self._fighter_names = self._load_names(base)
        self._weapons = self._load_items(base, "weapons.json")
        self._armor = self._load_items(base, "armor.json")
        self._accessories = self._load_items(base, "accessories.json")
        self._relics = self._load_items(base, "relics.json")
        self._enchantments = self._load_keyed(base, "enchantments.json", "enchantments")
        self._achievements = self._load_list(base, "achievements.json", "achievements")
        self._injuries = self._load_list(base, "injuries.json", "injuries")
        self._injuries_by_id = {inj["id"]: inj for inj in self._injuries}
        self._lore = self._load_list(base, "lore.json", "entries")
        self._fighter_classes = self._load_fighter_classes(base)
        self._enemies = self._load_list(base, "enemies.json", "enemies")
        self._boss_modifiers = self._load_keyed(base, "boss_modifiers.json", "modifiers")
        # Read here, compiled later by GameEngine._wire_data — the compiler
        # needs the item slot of every referenced item to enforce the per-kind
        # slot charter, and it must see numbers AFTER the balance overlay below.
        self._item_passives = self._load_keyed(base, "item_passives.json",
                                               "passives")
        self._mutators = self._load_keyed(base, "mutators.json", "mutators")
        # Must be read BEFORE the overlay below: the overlay patches whatever
        # list self._expeditions holds at call time, and __new__ seeds it with
        # an empty placeholder — loading it after the overlay would silently
        # drop every expeditions patch into that discarded placeholder.
        self._expeditions = self._load_list(base, "expeditions.json", "expeditions")

        # Balance overlay goes here: after every raw file is read, before the
        # tier indexes are derived from them. Patching an enemy's tier has to
        # be visible to _build_tier_index or the enemy stays in its old pool.
        # Injuries are safe either way — _injuries_by_id above holds the same
        # dict objects the overlay mutates in place.
        try:
            from game.remote_content import patch_gamedata
            patch_gamedata(self)
        except Exception as exc:  # noqa: BLE001 - bundled data must still load
            _log.warning("[DataLoader] remote balance overlay skipped: %s", exc)

        self._enemies_by_tier = self._build_tier_index(self._enemies)
        self._normals_by_tier, self._bosses_by_tier = self._split_enemies(
            self._enemies_by_tier
        )

        self._loaded = True
        _log.info("[DataLoader] All data loaded successfully")

    @property
    def fighter_names(self) -> list:
        return self._fighter_names

    @property
    def weapons(self) -> list:
        return self._weapons

    @property
    def armor(self) -> list:
        return self._armor

    @property
    def accessories(self) -> list:
        return self._accessories

    @property
    def relics(self) -> list:
        return self._relics

    @property
    def all_forge_items(self) -> list:
        """Weapons + armor + accessories combined."""
        return self._weapons + self._armor + self._accessories

    @property
    def enchantments(self) -> dict:
        return self._enchantments

    @property
    def item_passives(self) -> dict:
        """Raw passive definitions keyed "<item_id>#<n>". Compiled in _wire_data."""
        return getattr(self, "_item_passives", {})

    @property
    def achievements_data(self) -> list:
        return self._achievements

    @property
    def injuries(self) -> list:
        return self._injuries

    @property
    def injuries_by_id(self) -> dict:
        return getattr(self, '_injuries_by_id', {})

    # Tier order from worst → least bad. Used to downgrade an injury one
    # step when reduce_injury_severity rolls successfully. "permanent" is
    # included even though the injury picker rarely lands on it; if a
    # design pass adds permanents to the pool, this stays correct.
    _SEVERITY_ORDER = ("permanent", "severe", "moderate", "minor")

    def pick_random_injury(self, existing_ids=None,
                           severity_reduction_chance=0.0):
        """Pick a random injury weighted by chance_weight, avoiding duplicates.

        If `severity_reduction_chance > 0`, with that probability the rolled
        injury is downgraded by one severity tier — re-rolled from the same
        pool but filtered to the lesser-severity bucket. Backs the Bone
        Setter (medicus) and Defy Death (berserker) perks. If the injury
        is already 'minor' or no lesser-tier injury exists in the pool,
        the original pick stands.
        """
        import random
        pool = self._injuries
        if existing_ids:
            filtered = [inj for inj in pool if inj["id"] not in existing_ids]
            if filtered:
                pool = filtered
        weights = [inj.get("chance_weight", 10) for inj in pool]
        chosen = random.choices(pool, weights=weights, k=1)[0]

        if severity_reduction_chance > 0 and random.random() < severity_reduction_chance:
            sev = chosen.get("severity", "minor")
            order = self._SEVERITY_ORDER
            if sev in order:
                idx = order.index(sev)
                if idx + 1 < len(order):
                    target_sev = order[idx + 1]
                    lesser = [inj for inj in pool if inj.get("severity") == target_sev]
                    if lesser:
                        weights2 = [inj.get("chance_weight", 10) for inj in lesser]
                        chosen = random.choices(lesser, weights=weights2, k=1)[0]
        return chosen["id"]

    @property
    def lore(self) -> list:
        return self._lore

    @property
    def fighter_classes(self) -> dict:
        return self._fighter_classes

    @property
    def enemies(self) -> list:
        return self._enemies

    @property
    def enemies_by_tier(self) -> dict:
        return self._enemies_by_tier

    @property
    def normals_by_tier(self) -> dict:
        return self._normals_by_tier

    @property
    def bosses_by_tier(self) -> dict:
        return self._bosses_by_tier

    @property
    def boss_modifiers(self) -> dict:
        return self._boss_modifiers

    @property
    def mutators(self) -> dict:
        return self._mutators

    @property
    def expeditions(self) -> list:
        return self._expeditions
