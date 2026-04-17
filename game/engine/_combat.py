# Build: 1
"""GameEngine _CombatMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _CombatMixin:
    def _spawn_enemy(self):
        if self._revenge_common:
            self.preview_enemies = self._revenge_common
            self.current_enemy = self._revenge_common[0]
            return
        num = max(1, sum(1 for f in self.fighters if f.available))
        tier = self.arena_tier
        normals = data_loader.normals_by_tier.get(tier)
        enemies = []
        for _ in range(num):
            if normals:
                template = random.choice(normals)
                enemies.append(Enemy.from_template(template, tier))
            else:
                enemies.append(Enemy(tier=tier))
        self.preview_enemies = enemies
        self.current_enemy = enemies[0] if enemies else None

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

    def spawn_boss_enemy(self):
        """Spawn a boss-tier enemy as current_enemy (no battle start)."""
        if self._revenge_boss:
            self.preview_enemies = self._revenge_boss
            self.current_enemy = self._revenge_boss[0]
            return
        bosses = data_loader.bosses_by_tier.get(self.arena_tier)
        if bosses:
            template = random.choice(bosses)
            boss = Boss.from_template(template, self.arena_tier)
        else:
            boss = Boss(self.arena_tier)
        from game.boss_modifiers import BossModifierHandler
        BossModifierHandler(data_loader.boss_modifiers).assign_modifiers(boss, self.arena_tier)
        self.preview_enemies = [boss]
        self.current_enemy = boss

    def start_auto_battle(self):
        self._current_battle_messages = []
        events = self.battle_mgr.start_auto_battle()
        self._collect_events(events)
        return events

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

    def _post_battle_check(self, result):
        """After battle turn: check permadeath → roguelike reset.

        Takes a BattleResult from BattleManager. Wins, arena_tier, gold,
        fighter.kills and HP reset are already handled inside
        BattleManager.do_turn(). Here we only update run-level stats and
        spawn next enemy.
        """
        if result.outcome == "victory":
            if result.is_boss:
                self.bosses_killed += 1
                self.check_t15_clear()
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
        self._log_event("battle", result=r_label, tier=self.arena_tier,
                        boss=result.is_boss, gold=result.gold_earned)

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
