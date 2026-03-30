# Build: 4
"""Centralized data loader — singleton that loads all JSON data at startup."""

import json
import os
import logging
from collections import defaultdict

_log = logging.getLogger(__name__)


def _data_dir():
    """Return absolute path to data/ directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
    )


class DataLoader:
    """Singleton that reads every JSON in data/ once and exposes typed accessors."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._normals_by_tier = {}
            cls._instance._bosses_by_tier = {}
            cls._instance._expeditions = []
        return cls._instance

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

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

        self._enemies_by_tier = self._build_tier_index(self._enemies)
        self._normals_by_tier, self._bosses_by_tier = self._split_enemies(
            self._enemies_by_tier
        )
        self._mutators = self._load_keyed(base, "mutators.json", "mutators")
        self._expeditions = self._load_list(base, "expeditions.json", "expeditions")

        self._loaded = True
        _log.info("[DataLoader] All data loaded successfully")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_json(path):
        """Read a JSON file, return parsed object or None on failure."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            _log.warning("[DataLoader] File not found: %s", path)
        except json.JSONDecodeError as exc:
            _log.warning("[DataLoader] Bad JSON in %s: %s", path, exc)
        return None

    def _load_names(self, base):
        """Flatten fighter_names.json into a single list of strings."""
        data = self._read_json(os.path.join(base, "fighter_names.json"))
        if not data:
            return []
        names = []
        for group in data.get("names", {}).values():
            if isinstance(group, list):
                names.extend(group)
        return names

    @staticmethod
    def _normalize_item(item):
        """Normalize JSON item fields to match the engine's expected keys.

        JSON uses base_str/base_agi/base_vit; engine expects str/agi/vit.
        Also supports legacy base_atk/base_def/base_hp format.
        """
        if "base_str" in item and "str" not in item:
            item = dict(item)
            item["str"] = item.pop("base_str")
            item["agi"] = item.pop("base_agi", 0)
            item["vit"] = item.pop("base_vit", 0)
        elif "base_atk" in item and "atk" not in item:
            item = dict(item)
            item["str"] = item.pop("base_atk")
            item["agi"] = item.pop("base_def", 0)
            item["vit"] = item.pop("base_hp", 0)
        return item

    def _load_items(self, base, filename):
        """Load a file whose top-level key is 'items' → list[dict]."""
        data = self._read_json(os.path.join(base, filename))
        if not data:
            return []
        return [self._normalize_item(i) for i in data.get("items", [])]

    def _load_list(self, base, filename, key):
        """Load a file and return data[key] as a list."""
        data = self._read_json(os.path.join(base, filename))
        if not data:
            return []
        return data.get(key, [])

    def _load_keyed(self, base, filename, key):
        """Load data and return as dict keyed by id.

        Handles two formats:
        - Already a dict keyed by id  → return as-is
        - A list of dicts with 'id'   → convert to dict
        """
        data = self._read_json(os.path.join(base, filename))
        if not data:
            return {}
        section = data.get(key, {})
        if isinstance(section, dict):
            return section
        # list of dicts → convert
        result = {}
        for item in section:
            item_id = item.get("id") if isinstance(item, dict) else None
            if item_id is not None:
                result[item_id] = item
            else:
                _log.warning("[DataLoader] Item without 'id' in %s: %s", filename, item)
        return result

    def _load_fighter_classes(self, base):
        """Load fighter_classes.json and normalize 'description' → 'desc' for class level."""
        data = self._read_json(os.path.join(base, "fighter_classes.json"))
        if not data:
            return {}
        classes = data.get("classes", {})
        for cls_data in classes.values():
            # Normalize top-level: code expects "desc", JSON has "description"
            if "description" in cls_data and "desc" not in cls_data:
                cls_data["desc"] = cls_data.pop("description")
        return classes

    @staticmethod
    def _build_tier_index(enemies):
        """Group enemies list by their 'tier' field."""
        by_tier = defaultdict(list)
        for enemy in enemies:
            tier = enemy.get("tier", 0)
            by_tier[tier].append(enemy)
        return dict(by_tier)

    @staticmethod
    def _split_enemies(by_tier):
        """Split enemies_by_tier into normals and bosses dicts."""
        normals = {}
        bosses = {}
        for tier, entries in by_tier.items():
            n = [e for e in entries if not e.get("is_boss", False)]
            b = [e for e in entries if e.get("is_boss", False)]
            if n:
                normals[tier] = n
            if b:
                bosses[tier] = b
        return normals, bosses

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

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
    def achievements_data(self) -> list:
        return self._achievements

    @property
    def injuries(self) -> list:
        return self._injuries

    @property
    def injuries_by_id(self) -> dict:
        return getattr(self, '_injuries_by_id', {})

    def pick_random_injury(self, existing_ids=None):
        """Pick a random injury weighted by chance_weight, avoiding duplicates."""
        import random
        pool = self._injuries
        if existing_ids:
            filtered = [inj for inj in pool if inj["id"] not in existing_ids]
            if filtered:
                pool = filtered
        weights = [inj.get("chance_weight", 10) for inj in pool]
        chosen = random.choices(pool, weights=weights, k=1)[0]
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


# Module-level convenience instance
data_loader = DataLoader()
