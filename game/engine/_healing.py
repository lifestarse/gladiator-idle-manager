# Build: 1
"""GameEngine _HealingMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _HealingMixin:
    def get_heal_cost(self):
        return DifficultyScaler.heal_cost(self.arena_tier)

    def get_hp_heal_cost(self, fighters=None):
        """Total cost to heal HP of all fighters, scaling with arena tier."""
        if fighters is None:
            fighters = [f for f in self.fighters if f.available]
        total_missing = sum(max(0, f.max_hp - f.hp) for f in fighters if f.alive and f.hp > 0)
        if total_missing <= 0:
            return 0
        tier_mult = HP_HEAL_TIER_MULT ** (self.arena_tier - 1)
        return math.ceil(total_missing / HP_HEAL_DIVISOR * tier_mult)

    def heal_all_hp(self, fighters=None):
        """Heal all fighters to full HP. If not enough gold, spend all and heal partially.
        Returns (healed_count, gold_spent)."""
        if fighters is None:
            fighters = [f for f in self.fighters if f.available]
        damaged = [f for f in fighters if f.alive and f.hp > 0 and f.hp < f.max_hp]
        if not damaged:
            return 0, 0
        total_missing = sum(f.max_hp - f.hp for f in damaged)
        tier_mult = HP_HEAL_TIER_MULT ** (self.arena_tier - 1)
        full_cost = math.ceil(total_missing / HP_HEAL_DIVISOR * tier_mult)
        if self.gold >= full_cost:
            self.gold -= full_cost
            for f in damaged:
                f.hp = f.max_hp
            self.save()
            return len(damaged), full_cost
        # Partial heal: spend all gold
        available_hp = int(self.gold * HP_HEAL_DIVISOR / tier_mult)
        spent = int(self.gold)
        self.gold = 0
        healed = 0
        # Heal most damaged first
        damaged.sort(key=lambda f: f.max_hp - f.hp, reverse=True)
        for f in damaged:
            if available_hp <= 0:
                break
            missing = f.max_hp - f.hp
            heal_amount = min(missing, available_hp)
            f.hp += heal_amount
            available_hp -= heal_amount
            healed += 1
        self.save()
        return healed, spent

    def heal_fighter_injury(self, fighter_idx, injury_idx=None):
        """Heal one injury from fighter. Heals cheapest non-permanent by default."""
        if 0 <= fighter_idx < len(self.fighters):
            f = self.fighters[fighter_idx]
            if not f.injuries:
                return Result(False, t("no_injuries"), "no_injuries")
            if injury_idx is None:
                injury_idx = f.cheapest_healable_injury_idx()
            if injury_idx < 0:
                return Result(False, t("no_healable_injuries"), "permanent_only")
            cost = f.get_injury_heal_cost(injury_idx)
            if cost < 0:
                return Result(False, t("no_healable_injuries"), "permanent_injury")
            if self.gold < cost:
                return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
            self.gold -= cost
            removed = f.injuries.pop(injury_idx)
            self.total_injuries_healed += 1
            if f.hp > f.max_hp:
                f.hp = f.max_hp
            inj_name = data_loader.injuries_by_id.get(removed["id"], {}).get("name", "?")
            self._log_event("heal", fighter=f.name, injury=inj_name, gold=cost)
            self.save()
            self._mark_dirty()
            return Result(True, t("healed_injury_msg", name=f.name, injury=inj_name, cost=fmt_num(cost)))
        return Result(False, t("invalid_fighter_err"), "invalid_fighter")

    def heal_fighter_all_injuries_cost(self, fighter_idx):
        """Total gold cost to heal all non-permanent injuries of one fighter."""
        if fighter_idx >= len(self.fighters):
            return 0
        f = self.fighters[fighter_idx]
        total = 0
        for i in range(len(f.injuries)):
            cost = f.get_injury_heal_cost(i)
            if cost > 0:
                total += cost
        return total

    def heal_fighter_all_injuries(self, fighter_idx):
        """Heal all non-permanent injuries of one fighter. Returns Result."""
        cost = self.heal_fighter_all_injuries_cost(fighter_idx)
        if cost <= 0:
            return Result(False, t("no_injuries"), "no_injuries")
        if self.gold < cost:
            return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
        f = self.fighters[fighter_idx]
        self.gold -= cost
        keep = []
        healed = 0
        for inj in f.injuries:
            data = f._get_injury_data(inj["id"])
            if data.get("heal_cost_multiplier", 1) == 0:
                keep.append(inj)
            else:
                healed += 1
        f.injuries = keep
        self.total_injuries_healed += healed
        if f.hp > f.max_hp:
            f.hp = f.max_hp
        self.save()
        self._mark_dirty()
        return Result(True, t("healed_all_injuries_msg", n=healed, cost=fmt_num(cost)))

    def heal_all_injuries_cost(self):
        """Total gold cost to heal ALL non-permanent injuries from ALL fighters."""
        total = 0
        for f in self.fighters:
            if f.alive:
                for i in range(len(f.injuries)):
                    cost = f.get_injury_heal_cost(i)
                    if cost > 0:
                        total += cost
        return total

    def heal_all_injuries(self):
        """Heal all non-permanent injuries from all fighters. Returns Result."""
        cost = self.heal_all_injuries_cost()
        if cost <= 0:
            return Result(False, t("no_injuries"), "no_injuries")
        if self.gold < cost:
            return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")
        self.gold -= cost
        healed = 0
        for f in self.fighters:
            if f.alive:
                keep = []
                for inj in f.injuries:
                    data = f._get_injury_data(inj["id"])
                    if data.get("heal_cost_multiplier", 1) == 0:
                        keep.append(inj)  # permanent stays
                    else:
                        healed += 1
                f.injuries = keep
                if f.hp > f.max_hp:
                    f.hp = f.max_hp
        self.total_injuries_healed += healed
        self.save()
        self._mark_dirty()
        return Result(True, t("healed_all_injuries_msg", n=healed, cost=fmt_num(cost)))
