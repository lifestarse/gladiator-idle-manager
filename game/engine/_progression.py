# Build: 2
"""GameEngine _ProgressionMixin — extracted from monolithic engine.py.

Also home to the player account level: XP, level-ups and the feature-unlock
gate. Distinct from Fighter.level (bought with gold, per fighter) and from
arena_tier (advanced by beating bosses) — this one is account-wide and
decides which parts of the game are available at all.
"""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _ProgressionMixin:
    # ------------------------------------------------------------------
    #  Player account level
    # ------------------------------------------------------------------

    def xp_for_level(self, level):
        """Total XP required to advance FROM `level` to level+1.

        Geometric curve: each level costs PLAYER_XP_EXPO times the previous.
        Returns 0 at PLAYER_MAX_LEVEL and above — the cap is terminal, not a
        wall the player keeps paying into.
        """
        if level >= PLAYER_MAX_LEVEL:
            return 0
        return int(PLAYER_XP_BASE * (PLAYER_XP_EXPO ** (level - 1)))

    @property
    def player_xp_to_next(self):
        """XP still needed for the next level (0 when capped)."""
        need = self.xp_for_level(self.player_level)
        return max(0, need - self.player_xp) if need else 0

    @property
    def player_level_pct(self):
        """Progress through the current level, 0.0..1.0 (1.0 when capped)."""
        need = self.xp_for_level(self.player_level)
        if not need:
            return 1.0
        return max(0.0, min(1.0, self.player_xp / need))

    def award_player_xp(self, amount):
        """Add XP and roll over any levels gained. Returns levels gained.

        Rolls over in a loop rather than once: a single large award (a boss
        kill on a fresh account) can legitimately cross two levels, and
        dropping the overflow would silently eat progress.
        """
        if amount <= 0 or self.player_level >= PLAYER_MAX_LEVEL:
            return 0
        self.player_xp += int(amount)
        gained = 0
        while self.player_level < PLAYER_MAX_LEVEL:
            need = self.xp_for_level(self.player_level)
            if not need or self.player_xp < need:
                break
            self.player_xp -= need
            self.player_level += 1
            gained += 1
        if self.player_level >= PLAYER_MAX_LEVEL:
            # Cap reached: park XP at 0 so the UI bar reads "full", not a
            # meaningless overflow number that keeps growing forever.
            self.player_xp = 0
        if gained:
            self.pending_level_ups.extend(
                range(self.player_level - gained + 1, self.player_level + 1))
            _log.info("[PROGRESSION] player level %d (+%d)",
                      self.player_level, gained)
        self._mark_dirty()
        return gained

    def is_unlocked(self, feature):
        """True if `feature` is available at the current player level.

        Features absent from FEATURE_UNLOCKS are always available — the
        table lists gates, not an allowlist, so adding a screen does not
        require touching it.
        """
        return self.player_level >= FEATURE_UNLOCKS.get(feature, 0)

    def unlock_level_for(self, feature):
        """Level at which `feature` unlocks (0 = never gated)."""
        return FEATURE_UNLOCKS.get(feature, 0)

    def next_unlock(self):
        """The nearest still-locked feature as (name, level), or None.

        Drives the arena's "next unlock" hook — the genre-standard carrot
        that tells the player what the next level actually buys them.
        """
        pending = [(lvl, name) for name, lvl in FEATURE_UNLOCKS.items()
                   if self.player_level < lvl]
        if not pending:
            return None
        lvl, name = min(pending)
        return name, lvl

    def take_pending_level_ups(self):
        """Drain the level-up queue for the UI to celebrate. Idempotent."""
        levels = list(self.pending_level_ups)
        self.pending_level_ups = []
        return levels
    def unlock_lore(self, entry_id):
        """Unlock a lore entry by id. Returns True if newly unlocked."""
        if entry_id not in self.lore_unlocked:
            self.lore_unlocked.append(entry_id)
            self._mark_dirty()
            self.save()
            return True
        return False

    def check_achievements(self):
        newly = []
        for ach in _ach_module.ACHIEVEMENTS:
            if ach["id"] in self.achievements_unlocked:
                continue
            try:
                if ach["check"](self):
                    self.achievements_unlocked.append(ach["id"])
                    self.diamonds += ach["diamonds"]
                    self.award_player_xp(PLAYER_XP_PER_ACHIEVEMENT)
                    newly.append(ach)
                    self.pending_notifications.append(
                        t("achievement_unlocked", name=ach['name'], diamonds=ach['diamonds'])
                    )
            except Exception as e:
                _log.warning("Achievement check failed [%s]: %s", ach.get("id"), e)
        self.check_quests()
        return newly

    def check_quests(self):
        changed = False
        newly_completed = []
        # Keep looping while chapters unlock (cascade)
        progress = True
        while progress:
            progress = False
            for ch_idx, chapter in enumerate(STORY_CHAPTERS):
                if ch_idx > self.story_chapter:
                    break
                for quest in chapter["quests"]:
                    if quest["id"] in self.quests_completed:
                        continue
                    try:
                        if quest["check"](self):
                            self.quests_completed.append(quest["id"])
                            changed = True
                            newly_completed.append(quest)
                            reward = quest.get("reward", {})
                            diamonds = reward.get("diamonds", 0)
                            if diamonds:
                                self.pending_notifications.append(
                                    t("quest_completed", name=quest.get("name", "Quest"), diamonds=diamonds)
                                )
                            if "diamonds" in reward:
                                self.diamonds += reward["diamonds"]
                            if "shards" in reward:
                                for tier, count in reward["shards"].items():
                                    self.shards[tier] = self.shards.get(tier, 0) + count
                    except Exception as e:
                        _log.warning("Quest check failed [%s]: %s", quest.get("id"), e)
                all_done = all(q["id"] in self.quests_completed for q in chapter["quests"])
                if all_done and ch_idx == self.story_chapter:
                    self.story_chapter += 1
                    changed = True
                    progress = True  # re-scan for newly unlocked chapters
        if changed:
            self.save()
        return newly_completed

    def get_achievements(self):
        return [
            {**ach, "unlocked": ach["id"] in self.achievements_unlocked, "check": None}
            for ach in _ach_module.ACHIEVEMENTS
        ]

    def get_pending_tutorial(self):
        return get_pending_tutorial(self)

    def mark_tutorial_shown(self, step_id):
        if step_id not in self.tutorial_shown:
            self.tutorial_shown.append(step_id)
