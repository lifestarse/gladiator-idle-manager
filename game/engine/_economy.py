# Build: 1
"""GameEngine _EconomyMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _EconomyMixin:
    def get_shop_items(self):
        items = get_dynamic_shop_items(self.arena_tier, self.surgeon_uses)
        return [{**item, "affordable": self.gold >= item["cost"]} for item in items]

    def buy_item(self, item_id):
        items = get_dynamic_shop_items(self.arena_tier, self.surgeon_uses)
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            return Result(False, t("item_not_found"), "not_found")
        if self.gold < item["cost"]:
            return Result(False, t("not_enough_gold", need=fmt_num(item["cost"] - self.gold)), "not_enough_gold")
        self.gold -= item["cost"]
        effect = item["effect"]
        if "heal" in effect:
            f = self.get_active_gladiator()
            if f: f.heal()
        if "base_attack" in effect:
            f = self.get_active_gladiator()
            if f: f.base_attack += effect["base_attack"]
        if "base_defense" in effect:
            f = self.get_active_gladiator()
            if f: f.base_defense += effect["base_defense"]
        if "cure_injury" in effect:
            f = self.get_active_gladiator()
            if f and f.injuries:
                count = effect["cure_injury"]
                for _ in range(count):
                    idx = f.cheapest_healable_injury_idx()
                    if idx >= 0:
                        f.injuries.pop(idx)
                if f.hp > f.max_hp:
                    f.hp = f.max_hp
                self.surgeon_uses += 1
        return Result(True, t("bought_msg", name=item['name']))

    def get_diamond_shop(self):
        result = []
        for item in DIAMOND_SHOP:
            iid = item["id"]
            if iid == "heal_all_injuries_diamond":
                total = sum(f.injury_count for f in self.fighters if f.alive)
                cost = max(10, total * 10)
                result.append({**item, "cost": cost, "affordable": self.diamonds >= cost and total > 0})
            elif iid == "revive_token":
                dead_count = sum(1 for f in self.fighters if not f.alive)
                cost = max(100, dead_count * 100)
                result.append({**item, "cost": cost, "affordable": self.diamonds >= cost and dead_count > 0})
            elif iid == "extra_expedition_slot":
                cost = EXPEDITION_SLOT_BASE_COST * (2 ** self.extra_expedition_slots)
                n = self.extra_expedition_slots
                desc = item["desc"] + f" [{t('level_n', n=n)}]" if n > 0 else item["desc"]
                result.append({**item, "cost": cost, "desc": desc,
                               "affordable": self.diamonds >= cost})
            else:
                result.append({**item, "affordable": self.diamonds >= item["cost"]})
        return result

    def buy_diamond_item(self, item_id):
        item = next((i for i in DIAMOND_SHOP if i["id"] == item_id), None)
        if not item:
            return Result(False, t("not_found_err"), "not_found")

        if item_id == "name_change":
            # Special: don't charge yet — UI will show popup, then call rename_fighter
            return Result(True, "", "name_change")

        if item_id == "revive_token":
            dead = [f for f in self.fighters if not f.alive]
            if not dead:
                return Result(False, t("no_dead_fighters"), "no_dead")
            cost = max(100, len(dead) * 100)
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            names = []
            for f in dead:
                f.alive = True
                f.injuries = []
                f.hp = f.max_hp
                names.append(f.name)
            self.save()
            return Result(True, t("revived_all_msg", n=len(names)))

        if item_id == "heal_all_injuries_diamond":
            total_injuries = sum(f.injury_count for f in self.fighters if f.alive)
            if total_injuries == 0:
                return Result(False, t("no_injuries"), "no_injuries")
            cost = max(10, total_injuries * 10)
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            for f in self.fighters:
                if f.alive and f.injuries:
                    f.injuries = []
                    if f.hp > f.max_hp:
                        f.hp = f.max_hp
            self.save()
            return Result(True, t("all_injuries_healed", n=total_injuries))

        if item_id == "extra_expedition_slot":
            cost = EXPEDITION_SLOT_BASE_COST * (2 ** self.extra_expedition_slots)
            if self.diamonds < cost:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= cost
            self.extra_expedition_slots += 1
            self.save()
            return Result(True, t("expedition_slots", n=1 + self.extra_expedition_slots))

        if item_id == "golden_armor":
            if self.diamonds < item["cost"]:
                return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
            self.diamonds -= item["cost"]
            legendary_ids = ["blade_of_ruin", "dragonscale", "crown_of_ash"]
            for lid in legendary_ids:
                itm = next((i for i in _m.ALL_FORGE_ITEMS if i["id"] == lid), None)
                if itm:
                    self.inventory.append(dict(itm))
            self.save()
            return Result(True, t("golden_set_bought"))

        # Generic fallback
        if self.diamonds < item["cost"]:
            return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
        self.diamonds -= item["cost"]
        self.save()
        return Result(True, t("bought_msg", name=item['name']))

    def get_diamond_bundles(self):
        return DIAMOND_BUNDLES

    def should_show_interstitial(self):
        if self.ads_removed:
            return False
        return self.wins > 0 and self.wins % 5 == 0

    def should_show_banner(self):
        return not self.ads_removed

    def purchase_remove_ads(self):
        self.ads_removed = True

    def purchase_diamonds(self, bundle_id):
        bundle = next((b for b in DIAMOND_BUNDLES if b["id"] == bundle_id), None)
        if bundle:
            self.diamonds += bundle["diamonds"]
            return Result(True, t("diamonds_earned", n=bundle['diamonds']))
        return Result(False, "", "not_found")

    def restore_purchases(self, purchase_ids: list[str]):
        for pid in purchase_ids:
            if pid == "remove_ads": self.ads_removed = True
