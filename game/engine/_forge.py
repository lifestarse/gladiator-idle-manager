# Build: 1
"""GameEngine _ForgeMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _ForgeMixin:
    def get_forge_items(self):
        return [{**item, "affordable": self.gold >= item["cost"]} for item in _m.ALL_FORGE_ITEMS]

    def buy_forge_item(self, item_id):
        """Buy item from forge → goes to inventory."""
        item = next((i for i in _m.ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item:
            return Result(False, t("item_not_found"), "not_found")
        if self.gold < item["cost"]:
            return Result(False, t("not_enough_gold", need=fmt_num(item["cost"] - self.gold)), "not_enough_gold")
        self.gold -= item["cost"]
        self.total_gold_spent_equipment += item["cost"]
        self.inventory.append(dict(item))
        self._log_event("buy", item=item["name"], gold=item["cost"])
        self.save()
        self._mark_dirty()
        return Result(True, t("bought_msg", name=item['name']))

    def equip_item_on(self, fighter_idx, item_id):
        item = next((i for i in _m.ALL_FORGE_ITEMS if i["id"] == item_id), None)
        if not item or fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        if self.battle_active:
            return Result(False, t("not_in_battle"), "not_in_battle")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if self.gold < item["cost"]:
            return Result(False, t("not_enough_gold", need=fmt_num(item["cost"] - self.gold)), "not_enough_gold")
        self.gold -= item["cost"]
        self.total_gold_spent_equipment += item["cost"]
        old = f.equip_item(dict(item))
        if old:
            self.inventory.append(dict(old))
        self._log_event("equip", item=item["name"], fighter=f.name, gold=item["cost"])
        self.save()
        self._mark_dirty()
        return Result(True, t("equipped_msg", item=item['name'], name=f.name))

    def equip_from_inventory(self, fighter_idx, inv_index):
        """Equip item from inventory onto a fighter. Old item goes to inventory."""
        if fighter_idx >= len(self.fighters) or inv_index >= len(self.inventory):
            return Result(False, "", "invalid")
        if self.battle_active:
            return Result(False, t("not_in_battle"), "not_in_battle")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, "", "fighter_dead")
        item = self.inventory.pop(inv_index)
        old = f.equip_item(dict(item))
        if old:
            self.inventory.append(dict(old))
        self._log_event("equip", item=item["name"], fighter=f.name)
        self.save()
        return Result(True, t("equipped_msg", item=item['name'], name=f.name))

    def unequip_from_fighter(self, fighter_idx, slot):
        """Unequip item from fighter slot → inventory. Blocked during battle."""
        if self.battle_active:
            return Result(False, t("not_in_battle"), "not_in_battle")
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        old = f.unequip_item(slot)
        if old:
            self.inventory.append(dict(old))
        self.save()
        return Result(True, "ok")

    def sell_inventory_item(self, inv_index):
        """Sell an item from inventory for half its cost."""
        if inv_index >= len(self.inventory):
            return 0
        item = self.inventory.pop(inv_index)
        sell_price = item.get("cost", 0) // 2
        self.gold += sell_price
        self._log_event("sell", item=item.get("name", "?"), gold=sell_price)
        self.save()
        return sell_price

    def get_inventory_count(self, item_id):
        """Count how many of an item are in inventory."""
        return sum(1 for i in self.inventory if i.get("id") == item_id)

    def find_inventory_index(self, item_id):
        """Find the inventory index for an item id with highest upgrade_level, or -1."""
        best_idx = -1
        best_lvl = -1
        for idx, item in enumerate(self.inventory):
            if item.get("id") == item_id:
                lvl = item.get("upgrade_level", 0)
                if lvl > best_lvl:
                    best_lvl = lvl
                    best_idx = idx
        return best_idx

    def upgrade_item(self, item_dict):
        """Upgrade any equipment item by +1. Returns Result."""
        max_lvl = get_max_upgrade(item_dict)
        current = item_dict.get("upgrade_level", 0)
        if current >= max_lvl:
            return Result(False, t("max_upgrade_reached"), "max_level")
        target = current + 1
        tier, count = get_upgrade_tier(target)
        slot_def = SLOTS.get(item_dict.get("slot"))
        if slot_def:
            count *= slot_def.shard_multiplier
        have = self.shards.get(tier, 0)
        if have < count:
            return Result(False, t("not_enough_shards", tier=tier, need=count, have=have), "not_enough_shards")
        self.shards[tier] -= count
        # Adjust fighter HP if this item is equipped and grants HP
        owner = None
        for f in self.fighters:
            for slot in EQUIPMENT_SLOTS:
                if f.equipment.get(slot) is item_dict:
                    owner = f
                    break
            if owner:
                break
        old_max = owner.max_hp if owner else 0
        item_dict["upgrade_level"] = target
        if owner:
            hp_gain = owner.max_hp - old_max
            if hp_gain > 0:
                owner.hp = min(owner.hp + hp_gain, owner.max_hp)
        self._log_event("upgrade", item=item_dict.get("name", "?"), lv=target)
        self.save()
        return Result(True, t("weapon_upgraded", name=item_dict.get("name", "?"), level=target))

    def enchant_weapon(self, weapon_dict, enchantment_id):
        """Apply enchantment to a weapon. Returns Result."""
        ench = _m.ENCHANTMENT_TYPES.get(enchantment_id)
        if not ench:
            return Result(False, t("invalid_enchantment"), "invalid_enchantment")
        if weapon_dict.get("slot") != "weapon":
            return Result(False, t("only_weapons"), "wrong_slot")
        gold_cost = ench["cost_gold"]
        shard_tier = ench["cost_shard_tier"]
        shard_count = ench["cost_shard_count"]
        if self.gold < gold_cost:
            return Result(False, t("not_enough_gold", need=fmt_num(gold_cost - self.gold)), "not_enough_gold")
        have = self.shards.get(shard_tier, 0)
        if have < shard_count:
            return Result(False, t("not_enough_shards", tier=shard_tier, need=shard_count, have=have), "not_enough_shards")
        self.gold -= gold_cost
        self.shards[shard_tier] -= shard_count
        weapon_dict["enchantment"] = enchantment_id
        self.total_enchantments_applied += 1
        self._log_event("enchant", item=weapon_dict.get("name", "?"), ench=ench["name"], gold=gold_cost)
        self.save()
        self._mark_dirty()
        return Result(True, t("weapon_enchanted", name=weapon_dict.get("name", "?"), ench=ench["name"]))
