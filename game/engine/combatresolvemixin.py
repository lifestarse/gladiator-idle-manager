# Build: 3
"""GameEngine _CombatResolveMixin — outcomes: rewards, permadeath, battle log."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _CombatResolveMixin:
    def award_gold(self, amount):
        self.gold += amount
        self.total_gold_earned += amount

    def handle_fighter_death(self, fighter):
        """Check permadeath, update graveyard. Returns (died, injury_id)."""
        died, injury_id = fighter.check_permadeath()
        if died:
            self.total_deaths += 1
            self.graveyard.append({
                "name": fighter.name,
                "level": fighter.level,
                "kills": fighter.kills,
            })
        return died, injury_id

    def _post_battle_check(self, result):
        """After battle turn: check permadeath → roguelike reset.

        Takes a BattleResult from BattleManager. Wins, arena_tier, gold,
        fighter.kills and HP reset are already handled inside
        BattleManager.do_turn(). Here we only update run-level stats and
        spawn next enemy.
        """
        if result.outcome == "victory":
            # Player XP: tier-scaled so grinding tier 1 can't reach the late
            # unlocks, plus a chunk for the boss that actually moved the tier.
            xp = PLAYER_XP_PER_ARENA_WIN + PLAYER_XP_PER_TIER * self.arena_tier
            if result.is_boss:
                self.bosses_killed += 1
                self.check_t15_clear()
                xp += PLAYER_XP_PER_BOSS_KILL
            self.award_player_xp(xp)
            self.run_kills += result.enemies_killed
            if self.arena_tier > self.run_max_tier:
                self.run_max_tier = self.arena_tier
            self._record_battle(result, "V")
            # Clear revenge for the mode that was just won
            if result.is_boss:
                self._revenge_boss = []
            else:
                self._revenge_common = []
            # Note: enemy re-spawn handled by ArenaScreen._check_battle_end()
            # which knows the current arena_mode (common vs boss)
            self._mark_dirty()

        # Check if all fighters are dead → roguelike reset
        if result.outcome == "defeat":
            self._record_battle(result, "D")
            # Revenge: surviving enemies carry over with their current HP
            survivors = result.survivors
            if survivors:
                if result.is_boss:
                    self._revenge_boss = survivors
                else:
                    self._revenge_common = survivors
                self.preview_enemies = survivors
                self.current_enemy = survivors[0]
            else:
                if result.is_boss:
                    self._revenge_boss = []
                else:
                    self._revenge_common = []
                self._spawn_enemy()
            for f in self.fighters:
                if f.alive:
                    f.hp = f.max_hp
            all_dead = not any(f.alive for f in self.fighters)
            if all_dead:
                # Defer reset so UI can show defeat screen first
                self._pending_reset = True

    def _record_battle(self, result, tag):
        """Append full battle log to persistent history."""
        messages = getattr(self, '_current_battle_messages', [])
        messages = self._truncate_battle_lines(messages)
        self.battle_log.append({
            "t": int(time.time()),
            "tier": self.arena_tier,
            "boss": result.is_boss,
            "r": tag,
            "g": result.gold_earned,
            "turns": result.turn_number,
            "f": [f.name for f in result.player_fighters],
            "e": [e.name for e in result.enemies],
            "log": messages,
        })
        self._current_battle_messages = []
        if len(self.battle_log) > 100:
            self.battle_log = self.battle_log[-100:]
        r_label = "victory" if tag == "V" else "defeat"
        # Roster fighters that sat this one out (benched, on expedition,
        # dead). Carried as a field on the "battle" event: a second
        # "battle_end" event used to be logged just for this, which made
        # every fight appear twice in the player-facing event log.
        skipped_names = [f.name for f in self.fighters
                         if f not in result.player_fighters]
        self._log_event("battle", result=r_label, tier=self.arena_tier,
                        boss=result.is_boss, gold=result.gold_earned,
                        skipped=skipped_names)
        self._emit_battle_end(result)

    def _truncate_battle_lines(self, messages):
        """Apply HEAD + TAIL truncation to a battle's message list.

        Previously we kept only the first MAX lines, which meant a player
        who lost a 1000 vs 1000 fight on turn 44 saw only the opening
        setup + first turn of attacks, never the actual death sequence.
        Now: first BATTLE_LOG_HEAD lines + a marker + last BATTLE_LOG_TAIL
        lines. Both ends of the battle survive.
        """
        n = len(messages)
        if n <= self.MAX_BATTLE_LOG_LINES:
            return list(messages) if not isinstance(messages, list) else messages
        head = self.BATTLE_LOG_HEAD
        tail = self.BATTLE_LOG_TAIL
        dropped = n - head - tail
        return (list(messages[:head])
                + [f"... ({dropped} lines skipped — showing start and end of battle)"]
                + list(messages[-tail:]))

    def _trim_battle_log_entry(self, entry):
        """Cap an in-memory battle log entry's line list.

        Legacy entries stored before MAX_BATTLE_LOG_LINES was tightened (or
        before head+tail) can still carry thousands of lines; this shrinks
        them as they flow through a save. Idempotent — entries already at-
        or-under the cap pass through untouched.
        """
        lines = entry.get("log") or []
        if len(lines) <= self.MAX_BATTLE_LOG_LINES:
            return entry
        new_entry = dict(entry)
        new_entry["log"] = self._truncate_battle_lines(lines)
        return new_entry
