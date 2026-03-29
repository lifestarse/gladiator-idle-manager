# Build: 2
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
        self._lore = self._load_list(base, "lore.json", "entries")
        self._fighter_classes = self._load_keyed(base, "fighter_classes.json", "classes")
        self._enemies = self._load_list(base, "enemies.json", "enemies")
        self._boss_modifiers = self._load_keyed(base, "boss_modifiers.json", "modifiers")

        self._enemies_by_tier = self._build_tier_index(self._enemies)
        self._mutators = self._load_keyed(base, "mutators.json", "mutators")

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

    def _load_items(self, base, filename):
        """Load a file whose top-level key is 'items' → list[dict]."""
        data = self._read_json(os.path.join(base, filename))
        if not data:
            return []
        return data.get("items", [])

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

    @staticmethod
    def _build_tier_index(enemies):
        """Group enemies list by their 'tier' field."""
        by_tier = defaultdict(list)
        for enemy in enemies:
            tier = enemy.get("tier", 0)
            by_tier[tier].append(enemy)
        return dict(by_tier)

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
    def boss_modifiers(self) -> dict:
        return self._boss_modifiers

    @property
    def mutators(self) -> dict:
        return self._mutators


# Module-level convenience instance
data_loader = DataLoader()
