# Build: 1
"""LoreScreen _LogsMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _LogsMixin:
    def _show_battle_log(self):
        """Show list of battles. Tap a battle to see full event log."""
        import time as _time
        engine = App.get_running_app().engine

        # Prefer RecycleView — virtualizes 200-entry list
        rv = self.ids.get("battle_log_rv")
        if rv is not None:
            self.lore_subview = "blog_list"
            # Cap the name preview: for 1000-vs-1000 battles the raw
            # list has 1000 names and ", ".join(...) produces a 10k-char
            # string. Shoving that into an AutoShrinkLabel is the cause
            # of the battle-log list lag user reported — Kivy renders
            # the full string then auto-shrinks to fit.
            def _preview(names, cap=5):
                if len(names) <= cap:
                    return ", ".join(names)
                return ", ".join(names[:cap]) + f", +{len(names) - cap}"

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
                    'fighters_text': _preview(entry.get("f", [])),
                    'enemies_text': _preview(entry.get("e", [])),
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
        """Show full event-by-event log for a single battle.

        Previously this built one AutoShrinkLabel + bind_text_wrap per log
        line. Battles with huge participant counts (e.g. 1000 vs 1000) can
        generate 10000+ log lines — the plain-widget build blocked the UI
        thread for seconds. Now routed through battle_detail_rv, which
        virtualizes to ~20 on-screen rows regardless of total N.
        """
        import time as _time
        engine = App.get_running_app().engine
        if log_idx < 0 or log_idx >= len(engine.battle_log):
            return
        entry = engine.battle_log[log_idx]
        self.lore_subview = "blog_detail"

        rv = self.ids.get("battle_detail_rv")
        if rv is None:
            return

        is_victory = entry.get("r") == "V"
        result_color = ACCENT_GREEN if is_victory else ACCENT_RED
        result_text = t("battle_log_victory") if is_victory else t("battle_log_defeat")
        if entry.get("boss"):
            result_text = f"{t('battle_log_boss')} {result_text}"

        ts = entry.get("t", 0)
        time_str = _time.strftime("%d.%m.%Y %H:%M", _time.localtime(ts)) if ts else "?"
        tier = entry.get("tier", 0)
        gold = fmt_num(entry.get("g", 0))
        turns = entry.get("turns", 0)
        log_lines = entry.get("log", [])

        # Two header rows + one row per log line. All use BattleDetailLineView;
        # explicit color/height/bold override the keyword-scan fallback.
        data = [
            {
                'text': f"{result_text}  T{tier}  +{gold}g  {turns} turns",
                'color': result_color, 'bold': True,
                'font_size': '11sp', 'height': dp(28),
            },
            {
                'text': time_str, 'color': TEXT_MUTED,
                'font_size': '11sp', 'height': dp(18),
            },
        ]
        if not log_lines:
            data.append({
                'text': t("battle_log_empty"), 'color': TEXT_MUTED,
                'font_size': '10sp', 'height': dp(30),
            })
        else:
            # Cheap comprehension: viewclass recomputes color from the text
            # lazily for visible rows only. For 10k lines this is ~1ms.
            data.extend({'text': line} for line in log_lines)

        rv.data = data
        # Jump to top when opening a battle detail.
        rv.scroll_y = 1
