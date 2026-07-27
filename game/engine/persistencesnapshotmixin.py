# Build: 5
"""GameEngine _PersistenceSnapshotMixin — save-state snapshot assembly."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION


class _PersistenceSnapshotMixin:
    def _build_save_data(self):
        """Assemble the save-state dict. Main-thread-safe; no I/O.

        Split out so `save` can serialize synchronously and `save_async`
        can ship the dict off to a background thread for the expensive
        JSON dump + disk write. Both paths must see an identical state
        snapshot, so we eagerly flatten mutable structures here.

        Runs under state_lock: the async script runner mutates engine
        state from a worker thread between its own lock acquisitions, and
        a snapshot taken mid-mutation (e.g. gold deducted, item not yet in
        inventory) would persist a torn state. RLock — the sync trigger
        path may already hold it via idle_tick.
        """
        with self.state_lock:
            # Stamped into the snapshot AND onto the engine so cloud
            # auto-sync can compare "how fresh is my local state" vs a
            # downloaded save.
            now = time.time()
            self.last_saved_at = now
            return {
                "schema_version": CURRENT_SAVE_VERSION,
                "saved_at": now,
                "gold": self.gold,
                "active_fighter_idx": self.active_fighter_idx,
                "arena_tier": self.arena_tier,
                "wins": self.wins,
                "total_wins": self.total_wins,
                "total_deaths": self.total_deaths,
                # list() copies: same worker-thread-dump race as battle_log
                # below — a main-thread append during save_async's json.dump
                # fails the save with "changed size during iteration".
                "graveyard": list(self.graveyard),
                "fighters": [f.to_dict() for f in self.fighters],
                "expedition_log": self.expedition_log[-20:],
                # Shallow-copy each battle entry so a concurrent write to
                # the original during a background save can't corrupt the
                # snapshot. Also trims legacy oversize logs inline.
                "battle_log": [
                    self._trim_battle_log_entry(entry)
                    for entry in self.battle_log[-200:]
                ],
                "event_log": self.event_log[-EVENT_LOG_MAX:],
                "surgeon_uses": self.surgeon_uses,
                "total_gold_earned": self.total_gold_earned,
                "run_number": self.run_number,
                "run_kills": self.run_kills,
                "run_max_tier": self.run_max_tier,
                "best_record_tier": self.best_record_tier,
                "best_record_kills": self.best_record_kills,
                "total_runs": self.total_runs,
                "diamonds": self.diamonds,
                "achievements_unlocked": self.achievements_unlocked,
                "bosses_killed": self.bosses_killed,
                "story_chapter": self.story_chapter,
                "quests_completed": self.quests_completed,
                "tutorial_shown": self.tutorial_shown,
                "extra_expedition_slots": self.extra_expedition_slots,
                "fastest_t15_time": self.fastest_t15_time,
                "run_start_time": self.run_start_time,
                "ads_removed": self.ads_removed,
                "review_shown_after_first_purchase": self._review_shown_after_first_purchase,
                "active_mutators": list(self.active_mutators),
                "inventory": [dict(i) if isinstance(i, dict) else i
                              for i in self.inventory],
                "shards": self.shards,
                # Requested, not active: while the chosen language's pack is
                # still missing (offline first launch after an update), the
                # active language is the "en" fallback and saving that would
                # erase the player's real choice.
                "language": get_requested_language(),
                "total_enchantments_applied": self.total_enchantments_applied,
                "total_enchantment_procs": self.total_enchantment_procs,
                "total_gold_spent_equipment": self.total_gold_spent_equipment,
                "total_injuries_healed": self.total_injuries_healed,
                "total_expeditions_completed": self.total_expeditions_completed,
                "completed_expedition_ids": self.completed_expedition_ids,
                "cloud_sync_enabled": self.cloud_sync_enabled,
                "lore_unlocked": self.lore_unlocked,
                "scripts": self.scripts.to_dict() if hasattr(self, "scripts") else {},
                "sound_volume": self.sound_volume,
                "battle_speed": self.battle_speed,
                "player_level": self.player_level,
                "player_xp": self.player_xp,
            }
