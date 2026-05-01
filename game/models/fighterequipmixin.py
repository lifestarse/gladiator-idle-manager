# Build: 3
"""Fighter _FighterEquipMixin — equip/unequip + item stat totals."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler


class _FighterEquipMixin:
    def _relic_bonus(self, stat):
        """Relic upgrade bonus for str/agi/vit: equal split."""
        item = self.equipment.get("relic")
        if not item:
            return 0
        return item.get(stat, 0)

    def item_total_stats(self, slot):
        """Return total (str, agi, vit) an equipped item gives."""
        item = self.equipment.get(slot)
        if not item:
            return 0, 0, 0
        return item.get("str", 0), item.get("agi", 0), item.get("vit", 0)

    def _equip_stat(self, stat):
        """Sum base equipment stats only (no upgrade bonuses).

        All upgrade bonuses are now applied directly to final stats:
        weapon → ATK, armor → DEF, accessory → HP, relic → all three.
        See weapon_upgrade_atk, armor_upgrade_def, accessory_upgrade_hp, relic_upgrade_*.
        """
        total = 0
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if item:
                total += item.get(stat, 0)
        return total

    @property
    def equip_str(self):
        return self._equip_stat("str")

    @property
    def equip_agi(self):
        return self._equip_stat("agi")

    @property
    def equip_vit(self):
        return self._equip_stat("vit")

    @property
    def upgrade_cost(self):
        return DifficultyScaler.upgrade_cost(self.level)

    def equip_item(self, item):
        """Equip item, returns the old item (or None) for inventory.
        Heals HP by the net HP gain from the new item (outside battle)."""
        slot = item["slot"]
        old = self.equipment.get(slot)
        old_max = self.max_hp
        self.equipment[slot] = item
        new_max = self.max_hp
        hp_gain = new_max - old_max
        if hp_gain > 0:
            self.hp = min(self.hp + hp_gain, new_max)
        elif self.hp > new_max:
            self.hp = new_max
        return old

    def unequip_item(self, slot):
        """Remove item from slot, cap HP to new max. Returns removed item."""
        old = self.equipment.get(slot)
        if not old:
            return None
        self.equipment[slot] = None
        if self.hp > self.max_hp:
            self.hp = self.max_hp
        return old
