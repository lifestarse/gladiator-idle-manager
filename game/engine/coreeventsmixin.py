# Build: 2
"""GameEngine _CoreEventsMixin — battle-end subscriptions, event log, leaderboards."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _CoreEventsMixin:
    def subscribe_first_purchase(self, cb) -> None:
        """Register a no-arg callable to fire once on the player's first
        successful forge purchase. Used by the App layer to trigger the
        Play In-App Review prompt without dragging pyjnius into engine."""
        if cb not in self._on_first_purchase_subscribers:
            self._on_first_purchase_subscribers.append(cb)

    def _maybe_emit_first_purchase(self) -> None:
        """Forge methods call this after a successful purchase. Idempotent:
        only the first call (when the flag is still False) fires
        subscribers and flips the flag. Subsequent purchases are no-ops."""
        if self._review_shown_after_first_purchase:
            return
        self._review_shown_after_first_purchase = True
        for cb in list(self._on_first_purchase_subscribers):
            try:
                cb()
            except Exception as exc:
                _log.warning("[engine] first-purchase subscriber failed: %s", exc)

    def _on_battle_end_scripts(self, result, participants, skipped):
        # Re-entrancy guard: a script reacting to on_battle_end can call
        # start_arena_battle, which (via builtins._start_arena_battle's
        # battle_skip) resolves the new battle synchronously and fires
        # _emit_battle_end again from inside our own callback. Without this
        # guard, a "farm to X gold" pattern would recurse straight into a
        # RecursionError instead of farming one battle per natural Arena tick.
        # With the guard, scripted battles fire-and-forget: the inner battle
        # still resolves (gold/wins/loss recorded), but its on_battle_end
        # event is swallowed so we don't pile programs on top of each other.
        if getattr(self, "_on_battle_end_running", False):
            return
        self._on_battle_end_running = True
        try:
            self.scripts.on_battle_end(self)
        except Exception as e:
            _log.exception("[ENGINE] scripts.on_battle_end failed: %s", e)
        finally:
            self._on_battle_end_running = False

    @staticmethod
    def _on_battle_end_stamina_fatigue(result, participants, skipped):
        for f in participants:
            if f.alive:
                f.apply_battle_fought()
        for f in skipped:
            if f.alive:
                f.apply_battle_skipped()

    def subscribe_battle_end(self, callback):
        """Register callback(result, participants, skipped) fired once per arena battle end.

        skipped = roster fighters that did not participate (benched, on
        expedition, dead, or simply not chosen for this fight).
        """
        self._battle_end_subscribers.append(callback)

    def _emit_battle_end(self, result):
        participants = list(result.player_fighters)
        participant_ids = {id(f) for f in participants}
        skipped = [f for f in self.fighters if id(f) not in participant_ids]
        for cb in self._battle_end_subscribers:
            cb(result, participants, skipped)

    def _log_event(self, event_type: str, **data):
        """Append an event to the unified event log."""
        import time as _time
        self.event_log.append({
            "t": int(_time.time()),
            "type": event_type,
            **data,
        })
        if len(self.event_log) > EVENT_LOG_MAX:
            self.event_log = self.event_log[-EVENT_LOG_MAX:]

    def submit_scores(self):
        """Submit all leaderboard scores from current engine state."""
        from game.leaderboard import leaderboard_manager
        leaderboard_manager.submit_all(
            best_tier=max(self.best_record_tier, self.arena_tier),
            # Lifetime kills, not self.wins — wins is the per-run counter
            # (reset on roguelike reset), which turned the TOTAL_KILLS
            # board into "best single run".
            total_kills=self.total_wins,
            strongest_gladiator_kills=self.best_record_kills,
        )
