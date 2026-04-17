# Build: 1
"""_EventLogsMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _EventLogsMixin:
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
            # Iterate by index (not reversed()) so we can pass the real
            # event_log index through for the detail view to pull from.
            for idx in range(len(engine.event_log) - 1, -1, -1):
                entry = engine.event_log[idx]
                etype = entry.get("type", "?")
                ts = entry.get("t", 0)
                time_str = _time.strftime("%d.%m %H:%M", _time.localtime(ts)) if ts else "?"
                color = _EVENT_COLORS.get(etype, TEXT_PRIMARY)
                data.append({
                    'log_idx': idx,
                    '_lore': self,
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

    def _show_event_detail(self, log_idx):
        """Render a full event entry as a list of field rows.

        Re-uses `battle_detail_rv` (BattleDetailLineView-based RV) so we
        don't need a second RV widget in KV. Each row is just a
        `{text, color, font_size, height}` dict.
        """
        import time as _time
        engine = App.get_running_app().engine
        if log_idx < 0 or log_idx >= len(engine.event_log):
            return
        entry = engine.event_log[log_idx]
        self.lore_subview = "event_detail"

        rv = self.ids.get("battle_detail_rv")
        if rv is None:
            return

        etype = entry.get("type", "?")
        type_color = {
            "battle": ACCENT_RED, "hire": ACCENT_GREEN, "dismiss": ACCENT_RED,
            "level_up": ACCENT_GOLD, "perk": ACCENT_CYAN, "buy": ACCENT_GOLD,
            "sell": TEXT_SECONDARY, "equip": ACCENT_BLUE, "upgrade": ACCENT_PURPLE,
            "enchant": ACCENT_PURPLE, "heal": ACCENT_GREEN,
            "expedition_send": ACCENT_CYAN,
        }.get(etype, TEXT_PRIMARY)

        ts = entry.get("t", 0)
        time_str = _time.strftime("%d.%m.%Y %H:%M:%S", _time.localtime(ts)) if ts else "?"

        data = [
            {
                'text': t(f"evt_{etype}"),
                'color': type_color, 'bold': True,
                'font_size': '13sp', 'height': dp(30),
            },
            {
                'text': time_str, 'color': TEXT_MUTED,
                'font_size': '10sp', 'height': dp(20),
            },
            {
                'text': self._format_event_detail(entry),
                'color': TEXT_SECONDARY,
                'font_size': '11sp', 'height': dp(26),
            },
            {
                'text': "─" * 12, 'color': TEXT_MUTED,
                'font_size': '10sp', 'height': dp(16),
            },
        ]
        # Dump remaining fields (skip already-rendered t/type) as key=value rows
        for k in sorted(entry.keys()):
            if k in ("t", "type"):
                continue
            v = entry[k]
            if isinstance(v, (list, dict)):
                # Keep it short — just length + type
                v_str = f"<{type(v).__name__}, {len(v)} items>"
            else:
                v_str = str(v)
            data.append({
                'text': f"{k}: {v_str}",
                'color': TEXT_PRIMARY,
                'font_size': '10sp', 'height': dp(20),
            })

        rv.data = data
        rv.scroll_y = 1

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

