# Build: 9
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.properties import StringProperty, ListProperty
from kivy.metrics import dp, sp
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton
from game.models import fmt_num, SHARD_TIERS
from game.theme import *
from game.theme import popup_color
from game.localization import t
from game.achievements import ACHIEVEMENTS
from game.story import STORY_CHAPTERS
from game.ui_helpers import (
    refresh_achievement_grid,
    refresh_diamond_shop_grid,
    grid_batch,
    bind_text_wrap,
)


class LoreScreen(BaseScreen):
    achievements_data = ListProperty()
    diamond_shop_data = ListProperty()
    lore_tab = StringProperty("achievements")
    lore_subview = StringProperty("")       # "" = none, "blog_list", "blog_detail"
    lore_back_text = StringProperty("")
    battle_log_count = StringProperty("")
    event_log_count = StringProperty("")
    _achievement_widgets = []
    _achievement_unlock_hash = None

    def on_enter(self):
        self.refresh_lore()

    def set_lore_tab(self, tab):
        self.lore_subview = ""
        self.lore_tab = tab
        grid = self._get_grid("lore_grid")
        if grid:
            grid._dshop_key = None
            grid._ach_key = None
        self.refresh_lore()

    def refresh_lore(self):
        if self.lore_subview:
            return
        engine = App.get_running_app().engine
        self._update_top_bar()
        if self.lore_tab == "achievements":
            self.achievements_data = engine.get_achievements()
            refresh_achievement_grid(self)
        elif self.lore_tab == "shop":
            self.diamond_shop_data = engine.get_diamond_shop()
            refresh_diamond_shop_grid(self)
        elif self.lore_tab == "quests":
            self._refresh_quests_grid()
        elif self.lore_tab == "stats":
            self.battle_log_count = f"{t('battle_log_btn')} ({len(engine.battle_log)})"
            self.event_log_count = f"{t('event_log_btn')} ({len(engine.event_log)})"
            self._refresh_stats_grid()

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

    def _show_battle_log(self):
        """Show list of battles. Tap a battle to see full event log."""
        import time as _time
        engine = App.get_running_app().engine

        # Prefer RecycleView — virtualizes 200-entry list
        rv = self.ids.get("battle_log_rv")
        if rv is not None:
            self.lore_subview = "blog_list"
            data = []
            for idx in range(len(engine.battle_log) - 1, -1, -1):
                entry = engine.battle_log[idx]
                is_victory = entry.get("r") == "V"
                is_boss = entry.get("boss", False)
                result_color = ACCENT_GREEN if is_victory else ACCENT_RED
                result_text = t("battle_log_victory") if is_victory else t("battle_log_defeat")
                if is_boss:
                    result_text = f"{t('battle_log_boss')} {result_text}"
                ts = entry.get("t", 0)
                time_str = _time.strftime("%d.%m %H:%M", _time.localtime(ts)) if ts else "?"
                data.append({
                    'log_idx': idx,
                    '_lore': self,
                    'result_text': result_text,
                    'result_color': list(result_color),
                    'tier_text': f"T{entry.get('tier', 0)}",
                    'gold_text': f"+{fmt_num(entry.get('g', 0))}g",
                    'time_text': time_str,
                    'fighters_text': ", ".join(entry.get("f", [])),
                    'enemies_text': ", ".join(entry.get("e", [])),
                })
            rv.data = data
            return
        # Legacy path below — keep as fallback
        self.lore_subview = "blog_list"
        grid = self._get_grid("lore_grid")
        if not grid:
            return
        from game.widgets import BaseCard

        with grid_batch(grid):
            grid.clear_widgets()

            grid.add_widget(AutoShrinkLabel(
                text=t("battle_log_title"), font_size="10sp", bold=True,
                color=ACCENT_CYAN, halign="center",
                size_hint_y=None, height=dp(32),
            ))

            if not engine.battle_log:
                grid.add_widget(AutoShrinkLabel(
                    text=t("battle_log_empty"), font_size="11sp",
                    color=TEXT_MUTED, halign="center",
                    size_hint_y=None, height=dp(40),
                ))
                return

            for idx, entry in enumerate(reversed(engine.battle_log)):
                real_idx = len(engine.battle_log) - 1 - idx
                is_victory = entry.get("r") == "V"
                is_boss = entry.get("boss", False)
                result_color = ACCENT_GREEN if is_victory else ACCENT_RED
                result_text = t("battle_log_victory") if is_victory else t("battle_log_defeat")
                if is_boss:
                    result_text = f"{t('battle_log_boss')} {result_text}"

                ts = entry.get("t", 0)
                time_str = _time.strftime("%d.%m %H:%M", _time.localtime(ts)) if ts else "?"
                tier = entry.get("tier", 0)
                gold = fmt_num(entry.get("g", 0))
                turns = entry.get("turns", 0)
                fighters = ", ".join(entry.get("f", []))
                enemies = ", ".join(entry.get("e", []))

                card = BaseCard(orientation="vertical", size_hint_y=None,
                                height=dp(78), padding=[dp(8), dp(4)], spacing=dp(2))
                card.border_color = result_color

                card.add_text_row(
                    (result_text, sp(7), True, result_color, 0.35),
                    (f"T{tier}", sp(7), True, ACCENT_GOLD, 0.12),
                    (f"+{gold}g", sp(7), True, ACCENT_GOLD, 0.23),
                    (time_str, sp(6), False, TEXT_MUTED, 0.30),
                    size_hint_y=0.5,
                )
                card.add_text_row(
                    (fighters, sp(6), False, TEXT_SECONDARY, 0.45),
                    ("vs", sp(6), False, TEXT_MUTED, 0.10),
                    (enemies, sp(6), False, TEXT_SECONDARY, 0.45),
                    size_hint_y=0.5,
                )
                card.bind(on_press=lambda inst, i=real_idx: self._show_battle_detail(i))
                grid.add_widget(card)

    def _show_battle_detail(self, log_idx):
        """Show full event-by-event log for a single battle."""
        import time as _time
        engine = App.get_running_app().engine
        if log_idx < 0 or log_idx >= len(engine.battle_log):
            return
        entry = engine.battle_log[log_idx]
        self.lore_subview = "blog_detail"
        grid = self._get_grid("lore_grid")
        if not grid:
            return

        is_victory = entry.get("r") == "V"
        result_color = ACCENT_GREEN if is_victory else ACCENT_RED
        result_text = t("battle_log_victory") if is_victory else t("battle_log_defeat")
        if entry.get("boss"):
            result_text = f"{t('battle_log_boss')} {result_text}"

        with grid_batch(grid):
            grid.clear_widgets()

            # Header
            ts = entry.get("t", 0)
            time_str = _time.strftime("%d.%m.%Y %H:%M", _time.localtime(ts)) if ts else "?"
            tier = entry.get("tier", 0)
            gold = fmt_num(entry.get("g", 0))
            turns = entry.get("turns", 0)

            grid.add_widget(AutoShrinkLabel(
                text=f"{result_text}  T{tier}  +{gold}g  {turns} turns",
                font_size="11sp", bold=True, color=result_color,
                halign="center", size_hint_y=None, height=dp(28),
            ))
            grid.add_widget(AutoShrinkLabel(
                text=time_str, font_size="11sp", color=TEXT_MUTED,
                halign="center", size_hint_y=None, height=dp(18),
            ))

            # Full event log
            log_lines = entry.get("log", [])
            if not log_lines:
                grid.add_widget(AutoShrinkLabel(
                    text=t("battle_log_empty"), font_size="10sp",
                    color=TEXT_MUTED, halign="center",
                    size_hint_y=None, height=dp(30),
                ))
                return

            for line in log_lines:
                color = TEXT_SECONDARY
                if "CRIT" in line:
                    color = ACCENT_GOLD
                elif "DODGE" in line:
                    color = ACCENT_CYAN
                elif "KILL" in line or "FALLEN" in line:
                    color = ACCENT_RED
                elif "VICTORY" in line or t("battle_log_victory").upper() in line.upper():
                    color = ACCENT_GREEN
                elif "DEFEAT" in line:
                    color = ACCENT_RED
                elif "POISON" in line or "BLEED" in line or "BURN" in line:
                    color = ACCENT_PURPLE

                lbl = AutoShrinkLabel(
                    text=line, font_size="11sp", color=color,
                    halign="left", size_hint_y=None, height=dp(18),
                )
                bind_text_wrap(lbl)
                grid.add_widget(lbl)

    def _close_subview(self):
        self.lore_subview = ""
        self.refresh_lore()

    def _show_event_log(self):
        """Show unified event log list."""
        import time as _time
        engine = App.get_running_app().engine
        self.lore_subview = "event_list"

        _EVENT_COLORS = {
            "battle": ACCENT_RED, "hire": ACCENT_GREEN, "dismiss": ACCENT_RED,
            "level_up": ACCENT_GOLD, "perk": ACCENT_CYAN, "buy": ACCENT_GOLD,
            "sell": TEXT_SECONDARY, "equip": ACCENT_BLUE, "upgrade": ACCENT_PURPLE,
            "enchant": ACCENT_PURPLE, "heal": ACCENT_GREEN,
            "expedition_send": ACCENT_CYAN,
        }

        # Prefer RecycleView — virtualizes 200-entry list
        rv = self.ids.get("event_log_rv")
        if rv is not None:
            data = []
            for entry in reversed(engine.event_log):
                etype = entry.get("type", "?")
                ts = entry.get("t", 0)
                time_str = _time.strftime("%d.%m %H:%M", _time.localtime(ts)) if ts else "?"
                color = _EVENT_COLORS.get(etype, TEXT_PRIMARY)
                data.append({
                    'color': list(color),
                    'label': t(f"evt_{etype}"),
                    'time_text': time_str,
                    'detail': self._format_event_detail(entry),
                })
            rv.data = data
            return

        # Legacy path below
        grid = self._get_grid("lore_grid")
        if not grid:
            return
        from game.widgets import BaseCard

        _EVENT_COLORS = {
            "battle": ACCENT_RED, "hire": ACCENT_GREEN, "dismiss": ACCENT_RED,
            "level_up": ACCENT_GOLD, "perk": ACCENT_CYAN, "buy": ACCENT_GOLD,
            "sell": TEXT_SECONDARY, "equip": ACCENT_BLUE, "upgrade": ACCENT_PURPLE,
            "enchant": ACCENT_PURPLE, "heal": ACCENT_GREEN,
            "expedition_send": ACCENT_CYAN,
        }

        with grid_batch(grid):
            grid.clear_widgets()
            grid.add_widget(AutoShrinkLabel(
                text=t("event_log_title"), font_size="10sp", bold=True,
                color=ACCENT_GOLD, halign="center",
                size_hint_y=None, height=dp(32),
            ))
            if not engine.event_log:
                grid.add_widget(AutoShrinkLabel(
                    text=t("event_log_empty"), font_size="11sp",
                    color=TEXT_MUTED, halign="center",
                    size_hint_y=None, height=dp(40),
                ))
                return
            for entry in reversed(engine.event_log):
                etype = entry.get("type", "?")
                ts = entry.get("t", 0)
                time_str = _time.strftime("%d.%m %H:%M", _time.localtime(ts)) if ts else "?"
                color = _EVENT_COLORS.get(etype, TEXT_PRIMARY)
                label = t(f"evt_{etype}")
                detail = self._format_event_detail(entry)

                card = BaseCard(orientation="vertical", size_hint_y=None,
                                height=dp(48), padding=[dp(8), dp(4)], spacing=dp(1))
                card.border_color = color
                card.add_text_row(
                    (label, sp(7), True, color, 0.45),
                    (time_str, sp(6), False, TEXT_MUTED, 0.30),
                    size_hint_y=0.45,
                )
                card.add_text_row(
                    (detail, sp(6), False, TEXT_SECONDARY, 1.0),
                    size_hint_y=0.55,
                )
                grid.add_widget(card)

    @staticmethod
    def _format_event_detail(entry):
        etype = entry.get("type", "")
        gold = entry.get("gold", 0)
        gold_str = f" ({fmt_num(gold)}g)" if gold else ""
        if etype == "battle":
            r = entry.get("result", "?")
            boss = "BOSS " if entry.get("boss") else ""
            return f"{boss}{r} T{entry.get('tier', '?')}{gold_str}"
        if etype == "hire":
            return f"{entry.get('name', '?')} [{entry.get('cls', '?')}]{gold_str}"
        if etype == "dismiss":
            return f"{entry.get('name', '?')} Lv{entry.get('lv', '?')}"
        if etype == "level_up":
            return f"{entry.get('name', '?')} → Lv{entry.get('lv', '?')}{gold_str}"
        if etype == "perk":
            return f"{entry.get('name', '?')}: {entry.get('perk', '?')}"
        if etype in ("buy", "sell"):
            return f"{entry.get('item', '?')}{gold_str}"
        if etype == "equip":
            return f"{entry.get('item', '?')} → {entry.get('fighter', '?')}{gold_str}"
        if etype == "upgrade":
            return f"{entry.get('item', '?')} +{entry.get('lv', '?')}"
        if etype == "enchant":
            return f"{entry.get('item', '?')}: {entry.get('ench', '?')}{gold_str}"
        if etype == "heal":
            return f"{entry.get('fighter', '?')}: {entry.get('injury', '?')}{gold_str}"
        if etype == "expedition_send":
            return f"{entry.get('fighter', '?')} → {entry.get('exp', '?')}"
        return str(entry)

    def on_back_pressed(self):
        if self.lore_subview == "blog_detail":
            self._show_battle_log()
            return True
        if self.lore_subview:
            self._close_subview()
            return True
        return False

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

    def buy_diamond_item(self, item_id):
        app = App.get_running_app()
        result = app.engine.buy_diamond_item(item_id)
        if result.code == "name_change":
            self._show_rename_popup()
            return
        if not result.ok and result.message:
            app.show_toast(result.message)
        self.refresh_lore()

    def _show_rename_popup(self):
        """Popup: select fighter → enter new name → confirm."""

        engine = App.get_running_app().engine
        fighters = [(i, f) for i, f in enumerate(engine.fighters) if f.alive]
        if not fighters:
            return

        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=[dp(12), dp(8)])

        # Fighter selector buttons
        selected = {"idx": fighters[0][0]}
        btn_refs = []
        selector = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        for i, f in fighters:
            btn = MinimalButton(
                text=f.name, font_size=11,
                btn_color=ACCENT_GOLD if i == selected["idx"] else BTN_DISABLED,
            )
            def on_select(inst, idx=i):
                selected["idx"] = idx
                for b, (bi, _) in zip(btn_refs, fighters):
                    b.btn_color = ACCENT_GOLD if bi == idx else BTN_DISABLED
                name_input.text = engine.fighters[idx].name
            btn.bind(on_press=on_select)
            btn_refs.append(btn)
            selector.add_widget(btn)
        content.add_widget(selector)

        # Text input
        name_input = TextInput(
            text=engine.fighters[selected["idx"]].name,
            font_size=sp(10), multiline=False,
            size_hint_y=None, height=dp(44),
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            cursor_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)],
        )
        content.add_widget(name_input)

        # Confirm button
        popup = Popup(
            title=t("rename_title"),
            title_size=sp(10),
            content=content,
            size_hint=(0.9, 0.38),
            background_color=BG_CARD,
        )
        confirm_btn = MinimalButton(
            text=t("confirm_btn"), font_size=9,
            btn_color=ACCENT_GOLD, size_hint_y=None, height=dp(42),
        )
        def do_rename(inst):
            engine.rename_fighter(selected["idx"], name_input.text)
            popup.dismiss()
            self.refresh_lore()
        confirm_btn.bind(on_press=do_rename)
        content.add_widget(confirm_btn)
        popup.open()
