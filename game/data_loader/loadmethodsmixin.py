# Build: 1
"""DataLoader _LoadMethodsMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _data_dir, _log


class _LoadMethodsMixin:
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
        """
        if "base_str" in item and "str" not in item:
            item = dict(item)
            item["str"] = item.pop("base_str")
            item["agi"] = item.pop("base_agi", 0)
            item["vit"] = item.pop("base_vit", 0)
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
