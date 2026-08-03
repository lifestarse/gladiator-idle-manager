# Build: 3
"""_EventLogsMixin — split off to keep file under 10KB.

The legacy lore_grid fallback of _show_event_log was removed in the
2026-08 redesign wave 0 cleanup: event_log_rv is always present in
kv/lore_screen.kv, so the fallback never ran.
"""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m

# Border/label colour per event type. Single source of truth — the list
# view and the detail view both read this, so a newly logged event type
# only needs one line here.
_EVENT_COLORS = {
    "battle": ACCENT_RED, "hire": ACCENT_GREEN, "dismiss": ACCENT_RED,
    "level_up": ACCENT_GOLD, "perk": ACCENT_CYAN, "buy": ACCENT_GOLD,
    "sell": TEXT_SECONDARY, "equip": ACCENT_BLUE, "upgrade": ACCENT_PURPLE,
    "enchant": ACCENT_PURPLE, "heal": ACCENT_GREEN,
    "expedition_send": ACCENT_CYAN, "expedition_cancel": ACCENT_RED,
    "script": ACCENT_BLUE,
}

# Rendered in the detail view's header rows, so never repeated below them.
_DETAIL_HEADER_KEYS = ("t", "type")
# A detail row is one line of a fixed-width pixel font; past this the text
# is ellipsised anyway, so cut it ourselves at a word-safe length.
_MAX_VALUE_CHARS = 48


def _fmt_event_value(value):
    """Render one event field as a single compact line.

    Lists of names (``skipped``, for instance) are joined rather than
    reduced to a bare count — "<list, 0 items>" told the player nothing.
    """
    if isinstance(value, dict):
        return ", ".join(f"{k}={value[k]}" for k in sorted(value)) or "-"
    if isinstance(value, (list, tuple)):
        if not value:
            return "-"
        joined = ", ".join(str(v) for v in value)
        if len(joined) > _MAX_VALUE_CHARS:
            return joined[:_MAX_VALUE_CHARS - 1] + "…"
        return joined
    return str(value)


class _EventLogsMixin:
    def _show_event_log(self):
        """Show unified event log list."""
        import time as _time
        engine = App.get_running_app().engine
        self.lore_subview = "event_list"

        # RecycleView — virtualizes 200-entry list
        rv = self.ids.get("event_log_rv")
        if rv is None:
            return
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
        type_color = _EVENT_COLORS.get(etype, TEXT_PRIMARY)

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
                # Em dash, not U+2500: PressStart2P has no box-drawing
                # glyphs, so the old "─" rule rendered as tofu squares.
                'text': "—" * 16, 'color': TEXT_MUTED,
                'font_size': '10sp', 'height': dp(16),
            },
        ]
        # Dump remaining fields (skip already-rendered t/type) as key=value rows
        for k in sorted(entry.keys()):
            if k in _DETAIL_HEADER_KEYS:
                continue
            data.append({
                'text': f"{k}: {_fmt_event_value(entry[k])}",
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
        if etype == "expedition_cancel":
            return f"×{entry.get('n', '?')}"
        if etype == "script":
            return str(entry.get("text", ""))
        # Unknown type (older save, or an event added without a branch
        # here): show its fields instead of str(entry), which leaked the
        # raw "{'t': 1784943830, 'type': ...}" dict into the log row.
        return ", ".join(
            f"{k}={_fmt_event_value(entry[k])}"
            for k in sorted(entry) if k not in _DETAIL_HEADER_KEYS
        )
