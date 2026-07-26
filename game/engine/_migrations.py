# Build: 1
"""Save-schema migrations.

Each function is registered via `register_migration(N)` and transforms a
save dict from schema version N to N+1. `_apply_save_data` runs them in
sequence, so a save from any older version walks up to the current one.

This module exists purely for its import side effect (registration), so
`game/engine/__init__.py` imports it — never call these directly.
"""
from game.engine._shared import register_migration


@register_migration(1)
def _v1_to_v2(data):
    """Drop retired "battle_end" event-log entries.

    Every resolved battle used to append two events: "battle" and
    "battle_end", the latter existing only to carry the list of roster
    fighters that skipped the fight. That made each fight show up twice
    in the player-facing event log, and since "battle_end" never had an
    `evt_*` translation key it rendered as the raw key plus a dict dump.
    The surviving "battle" event now carries the `skipped` field itself,
    so the stale entries sitting in existing saves are pure noise.
    """
    log = data.get("event_log")
    if isinstance(log, list):
        data["event_log"] = [
            e for e in log
            if not (isinstance(e, dict) and e.get("type") == "battle_end")
        ]
    return data
