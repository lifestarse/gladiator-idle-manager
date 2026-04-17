# Build: 1
"""GameEngine _ExpeditionsMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _ExpeditionsMixin:
    def get_expeditions(self):
        return [{**exp, "affordable": True, "duration_text": self._fmt_duration(exp["duration"])} for exp in _m.EXPEDITIONS]

    def send_on_expedition(self, fighter_idx, expedition_id):
        if fighter_idx >= len(self.fighters):
            return Result(False, "", "invalid")
        f = self.fighters[fighter_idx]
        if not f.alive:
            return Result(False, t("fighter_dead", name=f.name), "fighter_dead")
        if f.on_expedition:
            return Result(False, t("already_on_expedition", name=f.name), "already_on_expedition")
        on_exp_count = sum(1 for fi in self.fighters if fi.on_expedition)
        max_slots = 1 + self.extra_expedition_slots
        if on_exp_count >= max_slots:
            return Result(False, t("max_expeditions", n=max_slots), "max_expeditions")
        exp = next((e for e in _m.EXPEDITIONS if e["id"] == expedition_id), None)
        if not exp:
            return Result(False, "", "invalid")
        if f.level < exp["min_level"]:
            return Result(False, t("need_level", lv=exp['min_level']), "need_level")
        f.on_expedition = True
        f.expedition_id = expedition_id
        f.expedition_end = time.time() + exp["duration"]
        self._log_event("expedition_send", fighter=f.name, exp=exp["name"])
        if self.active_fighter_idx < len(self.fighters) and self.fighters[self.active_fighter_idx] == f:
            self.get_active_gladiator()
        return Result(True, t("departed_msg", name=f.name, exp=exp['name']))

    def check_expeditions(self):
        results = []
        now = time.time()
        for f in self.fighters:
            if not f.on_expedition or not f.alive:
                continue
            if now < f.expedition_end:
                continue
            exp = next((e for e in _m.EXPEDITIONS if e["id"] == f.expedition_id), None)
            if not exp:
                f.on_expedition = False
                f.expedition_id = None
                continue
            f.on_expedition = False
            f.expedition_id = None
            f.expedition_end = 0.0
            self.total_expeditions_completed += 1
            if random.random() < exp["danger"]:
                died, inj_id = f.check_permadeath()
                if died:
                    self.total_deaths += 1
                    self.graveyard.append({"name": f.name, "level": f.level, "kills": f.kills})
                    msg = f"{f.name} KILLED during {exp['name']}!"
                    results.append(msg)
                    self.expedition_log.append(msg)
                    # Check all dead
                    if not any(fi.alive for fi in self.fighters):
                        self._pending_reset = True
                    continue
                else:
                    inj_name = data_loader.injuries_by_id.get(inj_id, {}).get("name", "?")
                    msg_parts_pre = [t("suffered_injury", injury=inj_name)]
            else:
                msg_parts_pre = []
            shard_info = _m.SHARD_TIERS.get(exp["id"])
            if shard_info:
                tier = shard_info["tier"]
                amount = random.randint(1, 10)
                self.shards[tier] = self.shards.get(tier, 0) + amount
                _key = f"shard_tier_{tier}_name"
                _translated = t(_key)
                shard_display = _translated if _translated != _key else shard_info['name']
                msg_parts = [t("expedition_returned_shard",
                               fighter=f.name, exp=exp['name'],
                               n=amount, shard=shard_display)]
            else:
                msg_parts = [t("expedition_returned",
                               fighter=f.name, exp=exp['name'])]
            if random.random() < exp["relic_chance"]:
                rarity = random.choice(exp["relic_pool"])
                relic_template = random.choice(_m.RELICS[rarity])
                relic = dict(relic_template)
                self.inventory.append(relic)
                msg_parts.append(t("found_relic_msg", name=relic['name'], rarity=rarity))
            if random.random() < exp["danger"] * 0.5:
                existing_ids = {inj["id"] for inj in f.injuries}
                extra_inj_id = data_loader.pick_random_injury(existing_ids)
                f.injuries.append({"id": extra_inj_id})
                extra_name = data_loader.injuries_by_id.get(extra_inj_id, {}).get("name", "?")
                msg_parts.append(t("injured_expedition", injury=extra_name))
            msg_parts.extend(msg_parts_pre)
            f.heal()
            msg = " ".join(msg_parts)
            results.append(msg)
            self.expedition_log.append(msg)
        if results:
            for msg in results:
                self.pending_notifications.append(msg)
            self._mark_dirty()
        return results

    def get_expedition_status(self):
        now = time.time()
        return [
            {
                "fighter_name": f.name,
                "expedition_name": next((e["name"] for e in _m.EXPEDITIONS if e["id"] == f.expedition_id), "?"),
                "remaining": max(0, f.expedition_end - now),
                "remaining_text": self._fmt_duration(int(max(0, f.expedition_end - now))),
            }
            for f in self.fighters if f.on_expedition and f.alive
        ]

    def _fmt_duration(self, seconds):
        if seconds >= 3600:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
        if seconds >= 60:
            return f"{seconds // 60}m {seconds % 60}s"
        return f"{seconds}s"
