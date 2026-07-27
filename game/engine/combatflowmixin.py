# Build: 3
"""GameEngine _CombatFlowMixin — driving battles: start, stop, turns, skip."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _CombatFlowMixin:
    # state_lock in the battle entry points below: the arena screen drives
    # turns from the Kivy main thread while the async script worker fires
    # actions (start_arena_battle → battle_skip, bench/equip/…) from its
    # daemon thread — the same fighters/gold/battle_mgr state on both
    # sides. RLock — scripted battles re-enter these methods on a thread
    # that already holds the lock via the interpreter's action op.

    def start_auto_battle(self):
        with self.state_lock:
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
            - Gold banked from kills made during this battle is forfeited.
              ``award_gold`` pays out per kill as the battle runs, so without
              this the arena STOP button would be a risk-free exploit: clear
              most of a wave, flee before the losing turn, keep the payout.
              Fleeing costs you the purse — that is the price of escaping a
              fight the roster was losing. The amount is stashed in
              ``last_flee_forfeit`` for the UI to report. Lifetime counters
              (``total_gold_earned``) are left alone: the gold *was* earned,
              it was then forfeited, and rolling back a lifetime stat would
              retroactively un-fire achievements.
            - ``_current_battle_messages`` is cleared (so the next
              ``_record_battle`` doesn't carry over the cancelled fight's
              log lines).
            - Preview enemies are re-rolled so the UI shows the upcoming
              fight rather than the cancelled one. Skipped if a boss is
              currently staged or revenge enemies are queued — those are
              special cases that own their preview.
        """
        with self.state_lock:
            forfeit = getattr(self.battle_mgr.state, 'gold_earned', 0)
            if not self.battle_mgr.cancel():
                return False
            self.last_flee_forfeit = min(forfeit, self.gold)
            self.gold = max(0, self.gold - forfeit)
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
        with self.state_lock:
            self._current_battle_messages = []
            events = self.battle_mgr.start_boss_fight()
            self._collect_events(events)
            return events

    def battle_next_turn(self):
        with self.state_lock:
            events, result = self.battle_mgr.do_turn()
            self._collect_events(events)
            self._post_battle_check(result)
            return events

    def battle_skip(self):
        with self.state_lock:
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
