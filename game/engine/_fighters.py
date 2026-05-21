# Build: 2
"""GameEngine _FightersMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _FightersMixin:
    def get_active_gladiator(self) -> Fighter | None:
        alive = [f for f in self.fighters if f.available]
        if not alive:
            return None
        self.active_fighter_idx = min(self.active_fighter_idx, len(self.fighters) - 1)
        f = self.fighters[self.active_fighter_idx]
        if f.available:
            return f
        for i, f in enumerate(self.fighters):
            if f.available:
                self.active_fighter_idx = i
                return f
        return None

    @property
    def hire_cost(self):
        alive_count = len([f for f in self.fighters if f.alive])
        if alive_count == 0:
            return 0
        return DifficultyScaler.hire_cost(alive_count)

    def hire_gladiator(self, fighter_class="mercenary"):
        """Hire a new fighter of given class."""
        cost = self.hire_cost
        if self.gold >= cost:
            self.gold -= cost
            f = Fighter(fighter_class=fighter_class)
            self.fighters.append(f)
            self._log_event("hire", name=f.name, cls=f.class_name, gold=cost)
            self._mark_dirty()
            return Result(True, t("recruited_msg", name=f.name, cls=f.class_name))
        return Result(False, t("need_gold", cost=fmt_num(cost)), "not_enough_gold")

    def upgrade_gladiator(self, index):
        if index >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[index]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        cost = f.upgrade_cost
        if self.gold >= cost:
            self.gold -= cost
            f.level_up()
            self._log_event("level_up", name=f.name, lv=f.level, gold=cost)
            if f.auto_distribute_enabled:
                self._auto_distribute_fighter(f)
            self._mark_dirty()
            return Result(True, t("reached_level", name=f.name, lv=f.level, pts=f.points_per_level))
        return Result(False, t("not_enough_gold", need=fmt_num(cost - self.gold)), "not_enough_gold")

    def distribute_stat(self, fighter_idx, stat_name):
        """Distribute 1 unused point to a stat."""
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if f.unused_points <= 0:
            return Result(False, t("no_unused_points"), "no_points")
        if f.distribute_point(stat_name):
            return Result(True, t("stat_distributed", name=f.name, stat=stat_name.upper(), pts=f.unused_points))
        return Result(False, "", "invalid")

    def unlock_perk(self, fighter_idx, perk_id):
        """Unlock a perk for a fighter. Returns Result."""
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if perk_id in f.unlocked_perks:
            return Result(False, t("perk_already_unlocked"), "already_unlocked")
        # Find perk in any class
        perk = None
        perk_class = None
        for cls_id, cls_data in _m.FIGHTER_CLASSES.items():
            for p in cls_data.get("perk_tree", []):
                if p["id"] == perk_id:
                    perk = p
                    perk_class = cls_id
                    break
            if perk:
                break
        if not perk:
            return Result(False, t("invalid_perk"), "invalid_perk")
        cost = perk["cost"]
        if perk_class != f.fighter_class:
            cost = int(cost * perk.get("cross_class_cost_mult", 2.0))
        if f.perk_points < cost:
            return Result(False, t("not_enough_perk_points"), "not_enough_points")
        old_max = f.max_hp
        f.perk_points -= cost
        f.unlocked_perks.append(perk_id)
        hp_gain = f.max_hp - old_max
        if hp_gain > 0:
            f.hp = min(f.hp + hp_gain, f.max_hp)
        self._log_event("perk", name=f.name, perk=perk["name"])
        self.save()
        self._mark_dirty()
        return Result(True, t("perk_unlocked_msg", name=f.name, perk=perk["name"]))

    def dismiss_dead(self, index):
        if index < len(self.fighters) and not self.fighters[index].alive:
            f = self.fighters[index]
            for slot in EQUIPMENT_SLOTS:
                item = f.equipment.get(slot)
                if item:
                    self.inventory.append(dict(item))
            self.fighters.pop(index)
            if self.active_fighter_idx >= len(self.fighters):
                self.active_fighter_idx = max(0, len(self.fighters) - 1)

    def dismiss_fighter(self, index):
        """Dismiss a living fighter. Equipment returned to inventory."""
        if index < 0 or index >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[index]
        name = f.name
        for slot in EQUIPMENT_SLOTS:
            item = f.equipment.get(slot)
            if item:
                self.inventory.append(dict(item))
        self.graveyard.append({
            "name": name, "class": f.fighter_class,
            "level": f.level, "kills": f.kills, "cause": "dismissed",
        })
        self.fighters.pop(index)
        if self.active_fighter_idx >= len(self.fighters):
            self.active_fighter_idx = max(0, len(self.fighters) - 1)
        self._log_event("dismiss", name=name, lv=f.level)
        self.save()
        return Result(True, t("fighter_dismissed", name=name), "dismissed")

    def rename_fighter(self, fighter_idx, new_name):
        """Rename a fighter. Costs 25 diamonds (Identity Scroll)."""
        new_name = new_name.strip()
        if not new_name or fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        if self.diamonds < RENAME_COST_DIAMONDS:
            return Result(False, t("not_enough_diamonds"), "not_enough_diamonds")
        self.diamonds -= RENAME_COST_DIAMONDS
        old_name = self.fighters[fighter_idx].name
        self.fighters[fighter_idx].name = new_name
        self.save()
        return Result(True, t("renamed_msg", old=old_name, new=new_name))

    def _auto_unlock_perks(self, f):
        """Spend perk_points on own-class perks: lowest tier first, then cost.

        Cross-class perks are skipped (2x cost makes them a poor auto pick;
        the player can still take them manually). Returns list of unlocked
        perk dicts so the caller can log each one.
        """
        cls_data = _m.FIGHTER_CLASSES.get(f.fighter_class, {})
        tree = cls_data.get("perk_tree", [])
        if not tree:
            return []
        locked = [p for p in tree if p["id"] not in f.unlocked_perks]
        locked.sort(key=lambda p: (p.get("tier", 99), p.get("cost", 99)))
        unlocked = []
        for perk in locked:
            cost = perk.get("cost", 1)
            if f.perk_points < cost:
                continue
            old_max = f.max_hp
            f.perk_points -= cost
            f.unlocked_perks.append(perk["id"])
            hp_gain = f.max_hp - old_max
            if hp_gain > 0:
                f.hp = min(f.hp + hp_gain, f.max_hp)
            unlocked.append(perk)
        return unlocked

    def _auto_distribute_fighter(self, f):
        """Apply class-profile auto-distribution to one fighter.

        Stats first, then perks. Does NOT save — caller is responsible
        (level_up wraps in _mark_dirty; the manual toggle saves explicitly).
        Returns (stats_spent, perks_unlocked_list).
        """
        stats_spent = f.auto_distribute_stats()
        perks = self._auto_unlock_perks(f)
        for perk in perks:
            self._log_event("perk", name=f.name, perk=perk["name"])
        return stats_spent, perks

    def set_auto_distribute(self, fighter_idx, enabled):
        """Toggle auto-distribute on a fighter.

        Turning ON immediately spends current unused_points + perk_points
        according to the class profile (so the player sees instant effect),
        then persists the flag.
        """
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        f.auto_distribute_enabled = bool(enabled)
        if f.auto_distribute_enabled and f.alive:
            self._auto_distribute_fighter(f)
        self.save()
        return Result(True, "")
