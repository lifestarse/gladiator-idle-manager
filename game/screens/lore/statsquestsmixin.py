# Build: 1
"""LoreScreen _StatsQuestsMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _StatsQuestsMixin:
    def _refresh_stats_grid(self):
        grid = self._get_grid("lore_grid")
        if not grid:
            return
        engine = App.get_running_app().engine

        with grid_batch(grid):
            grid.clear_widgets()

            def _header(text):
                lbl = AutoShrinkLabel(
                    text=text, font_size=sp(11), bold=True,
                    color=ACCENT_GREEN, halign="left", valign="middle",
                    size_hint_y=None, height=dp(36),
                    padding=[dp(4), 0],
                )
                bind_text_wrap(lbl)
                grid.add_widget(lbl)

            def _row(label, value):
                box = BoxLayout(
                    orientation="horizontal", size_hint_y=None, height=dp(30),
                    padding=[dp(8), 0],
                )
                lbl = AutoShrinkLabel(
                    text=label, font_size=sp(10), color=TEXT_MUTED,
                    halign="left", valign="middle", size_hint_x=0.55,
                )
                bind_text_wrap(lbl)
                val = AutoShrinkLabel(
                    text=str(value), font_size=sp(10), bold=True,
                    color=TEXT_PRIMARY, halign="right", valign="middle",
                    size_hint_x=0.45,
                )
                bind_text_wrap(val)
                box.add_widget(lbl)
                box.add_widget(val)
                grid.add_widget(box)

            # --- Current Run ---
            _header(t("stat_hdr_current_run"))
            _row(t("stat_row_run_num"), engine.run_number)
            _row(t("stat_row_arena_tier"), engine.arena_tier)
            _row(t("stat_row_kills"), engine.run_kills)
            _row(t("stat_row_max_tier"), engine.run_max_tier)

            # --- Records ---
            _header(t("stat_hdr_records"))
            _row(t("stat_row_best_tier"), engine.best_record_tier if engine.best_record_tier > 0 else "---")
            _row(t("stat_row_best_kills"), engine.best_record_kills if engine.best_record_kills > 0 else "---")
            _row(t("stat_row_total_runs"), engine.total_runs)

            # --- Combat ---
            _header(t("stat_hdr_combat"))
            _row(t("stat_row_wins"), engine.wins)
            _row(t("stat_row_bosses_killed"), engine.bosses_killed)
            _row(t("stat_row_fighters_lost"), engine.total_deaths)
            _row(t("stat_row_graveyard"), len(engine.graveyard))

            # --- Economy ---
            _header(t("stat_hdr_economy"))
            _row(t("stat_row_gold"), fmt_num(engine.gold))
            _row(t("stat_row_total_gold"), fmt_num(engine.total_gold_earned))
            _row(t("stat_row_diamonds"), fmt_num(engine.diamonds))

            # --- Roster ---
            _header(t("stat_hdr_roster"))
            alive = [f for f in engine.fighters if f.alive]
            _row(t("stat_row_fighters_alive"), len(alive))
            total_kills = sum(f.kills for f in engine.fighters)
            _row(t("stat_row_total_kills"), total_kills)
            if engine.fighters:
                best_f = max(engine.fighters, key=lambda f: f.level)
                _row(t("stat_row_highest_level"), f"{best_f.name} Lv.{best_f.level}")
            total_injuries = sum(f.injury_count for f in engine.fighters)
            _row(t("stat_row_total_injuries"), total_injuries)

            # --- Progress ---
            _header(t("stat_hdr_progress"))
            unlocked = len(engine.achievements_unlocked)
            total_ach = len(ACHIEVEMENTS)
            _row(t("stat_row_achievements"), f"{unlocked} / {total_ach}")
            _row(t("stat_row_story_chapter"), engine.story_chapter)
            _row(t("stat_row_expeditions_done"), len(engine.expedition_log))
            _row(t("battle_log_btn"), len(engine.battle_log))

    def _refresh_quests_grid(self):
        grid = self._get_grid("lore_grid")
        if not grid:
            return
        engine = App.get_running_app().engine

        def _shard_display(tier):
            """Translated shard name (falls back to generic if key missing)."""
            key = f"shard_tier_{tier}_name"
            val = t(key)
            return val if val != key else t("shard_name_fallback", tier=tier)

        def _reward_text(reward):
            parts = []
            if "diamonds" in reward:
                parts.append(t("reward_diamonds", n=reward['diamonds']))
            if "shards" in reward:
                for tier, count in reward["shards"].items():
                    parts.append(f"{count}x {_shard_display(tier)}")
            return ", ".join(parts) if parts else t("reward_none")

        with grid_batch(grid):
            grid.clear_widgets()

            for ch_idx, chapter in enumerate(STORY_CHAPTERS):
                locked = ch_idx > engine.story_chapter
                completed_ch = ch_idx < engine.story_chapter

                # Chapter header — color conveys state.
                # Completed: green + checkmark prefix. Locked: muted gray.
                # Current: gold. No more "[DONE]/[LOCKED]" suffix noise.
                if completed_ch:
                    ch_color = ACCENT_GREEN
                    ch_prefix = "✓ "
                elif locked:
                    ch_color = TEXT_MUTED
                    ch_prefix = ""
                else:
                    ch_color = ACCENT_GOLD
                    ch_prefix = ""

                chap_name = t("chap_" + chapter['id'])
                hdr = AutoShrinkLabel(
                    text=f"{ch_prefix}{chap_name}",
                    font_size=sp(12), bold=True,
                    color=ch_color, halign="left", valign="middle",
                    size_hint_y=None, height=dp(44),
                    padding=[dp(4), dp(6)],
                )
                bind_text_wrap(hdr)
                grid.add_widget(hdr)

                if locked:
                    continue

                # Quest rows — more breathing room, cleaner status marks.
                for quest in chapter["quests"]:
                    done = quest["id"] in engine.quests_completed
                    check_mark = "✓  " if done else "·  "
                    q_color = ACCENT_GREEN if done else TEXT_PRIMARY
                    q_name = t("qst_" + quest['id'] + "_name")
                    q_desc = t("qst_" + quest['id'] + "_desc")

                    row = BoxLayout(
                        orientation="vertical", size_hint_y=None, height=dp(56),
                        padding=[dp(14), dp(6)], spacing=dp(2),
                    )
                    name_lbl = AutoShrinkLabel(
                        text=f"{check_mark}{q_name}",
                        font_size=sp(11), bold=True, color=q_color,
                        halign="left", valign="middle",
                        size_hint_y=None, height=dp(22),
                    )
                    bind_text_wrap(name_lbl)

                    desc_lbl = AutoShrinkLabel(
                        text=f"{q_desc}  —  {_reward_text(quest.get('reward', {}))}",
                        font_size=sp(9), color=TEXT_MUTED,
                        halign="left", valign="middle",
                        size_hint_y=None, height=dp(22),
                    )
                    bind_text_wrap(desc_lbl)

                    row.add_widget(name_lbl)
                    row.add_widget(desc_lbl)
                    grid.add_widget(row)
