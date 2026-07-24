# Build: 1
"""GameEngine _CombatFlowMixin — driving battles: start, stop, turns, skip."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _CombatFlowMixin:
    def start_auto_battle(self):
        self._current_battle_messages = []
        events = self.battle_mgr.start_auto_battle()
        self._collect_events(events)
        return events

    def stop_auto_battle(self):
        """Cancel the in-progress battle. See ``BattleManager.cancel`` for
        full semantics: no rewards, no log entry, partial damage stays.

        Returns True if a battle was cancelled, False if no battle was active
        (call was a no-op). The return value lets scripts and tests verify
        the cancel actually happened.

        Side effects on engine state:
            - ``_current_battle_messages`` is cleared (so the next
              ``_record_battle`` doesn't carry over the cancelled fight's
              log lines).
            - Preview enemies are re-rolled so the UI shows the upcoming
              fight rather than the cancelled one. Skipped if a boss is
              currently staged or revenge enemies are queued — those are
              special cases that own their preview.
        """
        if not self.battle_mgr.cancel():
            return False
        self._current_battle_messages = []
        # Refresh preview unless something stage-owned (boss / revenge) is
        # holding it — same guard used in refresh_arena_preview.
        if (self.current_enemy is None
                or not getattr(self.current_enemy, "is_boss", False)) \
                and not self._revenge_common and not self._revenge_boss:
            self._spawn_enemy()
        self._mark_dirty()
        return True

    def start_boss_fight(self):
        self._current_battle_messages = []
        events = self.battle_mgr.start_boss_fight()
        self._collect_events(events)
        return events

    def battle_next_turn(self):
        events, result = self.battle_mgr.do_turn()
        self._collect_events(events)
        self._post_battle_check(result)
        return events

    def battle_skip(self):
        events, result = self.battle_mgr.do_full_battle()
        self._collect_events(events)
        self._post_battle_check(result)
        return events

    def _collect_events(self, events):
        """Accumulate battle event messages for the log."""
        buf = getattr(self, '_current_battle_messages', None)
        if buf is None:
            self._current_battle_messages = buf = []
        for ev in events:
            if ev.message:
                buf.append(ev.message)
