# Build: 1
"""GameEngine _WiringMixin."""
# Build: 1
"""GameEngine core — lifecycle, tick, data wiring. Inherits mixins."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module
from game.engine._fighters import _FightersMixin
from game.engine._combat import _CombatMixin
from game.engine._forge import _ForgeMixin
from game.engine._expeditions import _ExpeditionsMixin
from game.engine._healing import _HealingMixin
from game.engine._progression import _ProgressionMixin
from game.engine._economy import _EconomyMixin
from game.engine._persistence import _PersistenceMixin


def _default_save_path():
    """Default save location. Kept lazy so engine.py can be imported headless."""
    try:
        from kivy.utils import platform
    except ImportError:
        return os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")
    if platform == "android":
        from android.storage import app_storage_path  # noqa
        return os.path.join(app_storage_path(), ".gladiator_idle_save.json")
    return os.path.join(os.path.expanduser("~"), ".gladiator_idle_save.json")


from game.engine._shared import _m, _log, _ach_module

class _WiringMixin:
    @staticmethod
    def _wire_data():
        """Override hardcoded module-level data in models.py with JSON data.

        Mutates dicts/lists IN-PLACE (.clear() + .update()/.extend()) rather
        than rebinding module attributes. This is required because
        game.models is now a package: submodules like game.models._fighter
        do `from ._data import *` which captures object references; in-place
        mutation keeps those references valid, rebinds would not.
        """
        import game.models as m
        dl = data_loader

        def _replace_list(lst, new_items):
            lst.clear()
            lst.extend(new_items)

        def _replace_dict(d, new_d):
            d.clear()
            d.update(new_d)

        _WiringMixin._template_by_id = {i["id"]: i for i in (
            dl.weapons + dl.armor + dl.accessories + dl.relics
        )} if (dl.weapons or dl.armor or dl.accessories or dl.relics) else {}
        if dl.fighter_names:
            _replace_list(m.FIGHTER_NAMES, dl.fighter_names)
        if dl.weapons:
            _replace_list(m.FORGE_WEAPONS, dl.weapons)
        if dl.armor:
            _replace_list(m.FORGE_ARMOR, dl.armor)
        if dl.accessories:
            _replace_list(m.FORGE_ACCESSORIES, dl.accessories)
        if dl.weapons or dl.armor or dl.accessories:
            _replace_list(m.ALL_FORGE_ITEMS,
                          m.FORGE_WEAPONS + m.FORGE_ARMOR + m.FORGE_ACCESSORIES)
        if dl.relics:
            rebuilt = {}
            for r in dl.relics:
                rebuilt.setdefault(r.get("rarity", "common"), []).append(r)
            _replace_dict(m.RELICS, rebuilt)
        if dl.enchantments:
            _replace_dict(m.ENCHANTMENT_TYPES, dl.enchantments)
        if dl.fighter_classes:
            _replace_dict(m.FIGHTER_CLASSES, dl.fighter_classes)
            m.Fighter.invalidate_perks_map_cache()
        if dl.mutators:
            mutator_registry.load(list(dl.mutators.values()))
        if dl.expeditions:
            _replace_list(m.EXPEDITIONS, dl.expeditions)
            _replace_dict(m.SHARD_TIERS, {
                e["id"]: {"tier": e["shard_tier"], "name": e["shard_name"]}
                for e in dl.expeditions if "shard_tier" in e
            })
        if dl.achievements_data:
            _ach_module.ACHIEVEMENTS = build_achievements_from_json(dl.achievements_data)

    @staticmethod
    def _find_template(item):
        """Find JSON template by id — O(1) via cached lookup dict."""
        iid = item.get("id")
        if iid:
            return getattr(_WiringMixin, '_template_by_id', {}).get(iid)
        return None

    @staticmethod
    def _migrate_item(item):
        """Refresh item from JSON template, preserving player data (upgrades, enchantments)."""
        if not item or not isinstance(item, dict):
            return item
        template = _WiringMixin._find_template(item)
        if template:
            upgrade_level = item.get("upgrade_level", 0)
            enchantment = item.get("enchantment")
            item = dict(template)
            item["upgrade_level"] = upgrade_level
            if enchantment:
                item["enchantment"] = enchantment
            return item
        return item

    def _migrate_all_items(self):
        """Migrate all inventory + fighter equipment to current JSON format."""
        self.inventory = [self._migrate_item(i) for i in self.inventory]
        for f in self.fighters:
            for slot in ("weapon", "armor", "accessory", "relic"):
                eq = f.equipment.get(slot)
                if eq:
                    f.equipment[slot] = self._migrate_item(eq)

    def check_t15_clear(self):
        """Record fastest T15 clear time if this is a new best.
        Called after boss victory; arena_tier is already incremented."""
        if self.arena_tier >= 15 and self.run_start_time > 0:
            elapsed = int(time.time() - self.run_start_time)
            if self.fastest_t15_time == 0 or elapsed < self.fastest_t15_time:
                self.fastest_t15_time = elapsed
                self.pending_notifications.append(
                    t("new_record_t15", time=self._fmt_time(elapsed))
                )

    @staticmethod
    def _fmt_time(seconds):
        """Format seconds as M:SS or H:MM:SS."""
        if seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d}"
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h}:{m:02d}:{s:02d}"
