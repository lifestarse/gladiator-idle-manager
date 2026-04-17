# Build: 1
"""GameEngine _ProgressionMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _ProgressionMixin:
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
