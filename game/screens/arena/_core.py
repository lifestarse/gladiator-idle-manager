# Build: 4
"""ArenaScreen core — lifecycle + small methods."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m
from .battleflowmixin import _BattleFlowMixin
from .healmixin import _HealMixin
from .enemypopupmixin import _EnemyPopupMixin
from .effectsmixin import _EffectsMixin
from .resetmixin import _ResetMixin


class ArenaScreen(BaseScreen, _BattleFlowMixin, _HealMixin, _EnemyPopupMixin, _EffectsMixin, _ResetMixin):
    tier_text = StringProperty("TIER 1")

    player_summary = StringProperty("")

    enemy_summary = StringProperty("")

    arena_mode = StringProperty("common")

    arena_view = StringProperty("battle")  # "battle" or "enemy_detail"

    is_fighting = BooleanProperty(False)

    # True iff at least one roster fighter is `available` (alive + not
    # benched + stamina/fatigue OK). Used by the kv to disable the
    # "Auto" button when there's no one to send into the arena —
    # without this, clicking the button entered an awkward half-state
    # (is_fighting flipped to True for one tick, then auto-unscheduled).
    has_available_fighters = BooleanProperty(False)

    player_hp_pct = NumericProperty(1.0)

    enemy_hp_pct = NumericProperty(1.0)

    best_text = StringProperty("Best: ---")

    run_text = StringProperty("Run #1 \u00b7 0 kills")

    # Auto-battle speed multiplier label ("x1" / "x2" / "x4") \u2014 mirrors
    # engine.battle_speed, cycled by the action-row speed button.
    speed_text = StringProperty("x1")

    # Record chase: run_kills / best_record_kills for the progress lane.
    record_pct = NumericProperty(0.0)

    # True once the current run has beaten the best record \u2014 flips the
    # progress bar gold and fires a one-shot NEW RECORD ticker.
    record_is_new = BooleanProperty(False)

    # Pre-battle gold preview: summed gold_reward of preview enemies.
    # Empty string while a battle is running (the lane shows live info).
    reward_text = StringProperty("")

    # "Next unlock" carrot: what the next player level buys. Empty once
    # everything in FEATURE_UNLOCKS is open.
    next_unlock_text = StringProperty("")

    # run_number that already got its NEW RECORD celebration \u2014 one ticker
    # per run, not one per refresh tick.
    _record_run_celebrated = 0

    # (tier, gold) of a boss win that landed while the player was on another
    # screen \u2014 shown on the next arena entry instead of opening a modal over
    # whatever they were doing. See _check_battle_end.
    _pending_tier_up = None

    # Clock time of the last battle resolution, for the FIGHT/STOP tap guard.
    _battle_end_time = -1e9

    def on_enter(self):
        app = App.get_running_app()
        if not app or not app.root:
            return
        # Wire up tap callbacks once per entry — ArenaUnitCardView uses these
        # to dispatch taps without holding a back-ref to this screen instance.
        _arena_callbacks['fighter_tap'] = self._open_fighter_detail
        _arena_callbacks['enemy_tap'] = self._show_enemy_popup_by_name
        self.refresh_ui()
        self._check_tutorial()
        self._check_pending_reset()
        if self._pending_tier_up is not None:
            tier, gold = self._pending_tier_up
            self._pending_tier_up = None
            self._show_tier_up_popup(tier, gold)

    def refresh_ui(self):
        engine = App.get_running_app().engine
        self._update_top_bar()
        # Arena header: kept English-only so the pixel PressStart2P font
        # renders consistently (Cyrillic falls back to a different font).
        self.tier_text = f"TIER {engine.arena_tier}"
        if engine.best_record_tier > 0:
            self.best_text = f"Best: T{engine.best_record_tier} \u00b7 {engine.best_record_kills} kills"
        else:
            self.best_text = "Best: ---"
        self.run_text = f"Run #{engine.run_number} \u00b7 {engine.run_kills} kills"
        self.speed_text = f"x{getattr(engine, 'battle_speed', 1)}"

        # Record chase lane: how far this run is from the best kill count.
        # First run ever (no record yet) keeps the bar empty and quiet.
        best_kills = engine.best_record_kills
        if best_kills > 0:
            self.record_pct = min(1.0, engine.run_kills / best_kills)
            self.record_is_new = engine.run_kills > best_kills
        else:
            self.record_pct = 0.0
            self.record_is_new = False
        if (self.record_is_new
                and self._record_run_celebrated != engine.run_number):
            self._record_run_celebrated = engine.run_number
            self._ticker(t("new_record"), ACCENT_GOLD)

        # Level-up celebration + the next-unlock carrot.
        for lvl in engine.take_pending_level_ups():
            self._show_level_up_banner(lvl)
        nxt = engine.next_unlock()
        if nxt:
            feature, lvl = nxt
            self.next_unlock_text = t(
                "next_unlock", name=t(f"feature_{feature}"), n=lvl)
        else:
            self.next_unlock_text = ""

        fighters = [f for f in engine.fighters if f.available]
        self.player_summary = t("fighters_ready", n=len(fighters))
        self.has_available_fighters = bool(fighters)

        if engine.battle_active:
            s = engine.battle_mgr.state
            alive_f = sum(1 for f in s.player_fighters if f.alive and f.hp > 0)
            alive_e = sum(1 for e in s.enemies if e.hp > 0)
            self.player_summary = t("fighters_alive", n=alive_f)
            self.enemy_summary = t("enemies_left", n=alive_e)
            total_hp = sum(max(0, f.hp) for f in s.player_fighters if f.alive)
            total_max = sum(f.max_hp for f in s.player_fighters if f.alive) or 1
            self.player_hp_pct = total_hp / total_max
            total_ehp = sum(max(0, e.hp) for e in s.enemies)
            total_emax = sum(e.max_hp for e in s.enemies) or 1
            self.enemy_hp_pct = total_ehp / total_emax
            self.reward_text = ""
        else:
            self.player_hp_pct = 1.0
            self.enemy_hp_pct = 1.0
            enemies = engine.preview_enemies
            if enemies:
                self.enemy_summary = f"{len(enemies)}x T{enemies[0].tier}"
                # Loot preview: exact base payout for a full clear (perk
                # gold bonuses can only raise it) — arena drops gold only.
                total_reward = sum(e.gold_reward for e in enemies)
                self.reward_text = f"+{fmt_num(total_reward)} G"
            else:
                self.enemy_summary = ""
                self.reward_text = ""

        self._refresh_battle_panels(engine)

    def _get_skill_text(self, fighter):
        """Return skill badge text: 'RDY', cooldown number, skill name, or None."""
        engine = App.get_running_app().engine
        skill = getattr(fighter, 'get_active_skill', lambda: None)()
        if not skill:
            return None
        bm = getattr(engine, 'battle_mgr', None)
        if not bm or not bm.is_active:
            # Full name — the badge auto-shrinks; "RAL" read as clipped junk
            return skill["name"].upper()
        ss = bm.state.skill_states.get(id(fighter))
        if not ss:
            return None
        if ss.cooldown_remaining <= 0:
            return "RDY"
        return str(ss.cooldown_remaining)

    def _open_fighter_detail(self, fighter_idx):
        """Open fighter detail on roster screen — same as tapping in squad."""
        app = App.get_running_app()
        roster = app.sm.get_screen("roster")
        roster._pending_state = {'detail_index': fighter_idx}
        app.sm.current = "roster"

    def _refresh_battle_panels(self, engine):
        """Populate the arena RecycleViews with fighter/enemy data.

        Previously this built a fresh CardWidget per unit via plain
        GridLayout+ScrollView. With large squads that was painfully slow
        on first render — every turn allocated ~10 widgets × N units.

        Now we just hand RecycleView a list of plain dicts; the RV pool
        (ArenaUnitCardView) keeps only visible rows as real widgets and
        calls refresh_view_attrs to rebind them. Cost is O(visible_rows),
        independent of total N.
        """
        fighters_rv = self.ids.get("battle_fighters_rv")
        enemies_rv = self.ids.get("battle_enemies_rv")
        hb = self.ids.get("heal_btn_box")
        if not fighters_rv or not enemies_rv:
            return

        if engine.battle_active:
            s = engine.battle_mgr.state
            fighters_list = [f for f in s.player_fighters if f.alive and f.hp > 0]
            # Preserve the full enemy list (including dead) so the panel doesn't
            # visually shrink mid-battle — card goes greyed/wounded instead.
            enemies_list = list(s.enemies)
            heal_callback = self._heal_all_battle
        else:
            fighters_list = [f for f in engine.fighters if f.available]
            enemies_list = list(engine.preview_enemies)
            heal_callback = self._heal_all_outside

        # Map fighter name → roster index for tap dispatch.
        # Built once per refresh instead of per-card with list.index() (O(N²)).
        roster_idx_by_name = {f.name: i for i, f in enumerate(engine.fighters)}

        fighters_rv.data = [
            _fighter_to_arena_data(
                f,
                roster_index=roster_idx_by_name.get(f.name, -1),
                skill_text=self._get_skill_text(f),
            )
            for f in fighters_list
        ]
        enemies_rv.data = [
            _enemy_to_arena_data(e, enemy_index=i)
            for i, e in enumerate(enemies_list)
        ]

        # Heal button — single widget, fine to rebuild when state changes.
        self._refresh_heal_btn(hb, fighters_list, engine, heal_callback)

    def on_back_pressed(self):
        if self.arena_view != "battle":
            self._close_enemy_detail()
            return True
        return False

    _active_floats: list = []
