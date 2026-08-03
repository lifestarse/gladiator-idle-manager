# Build: 7
"""ui_helpers._roster_grid — refresh_roster_grid entry point.

build_roster_card() removed in the 2026-08 redesign wave 0 cleanup: it was
the pre-RecycleView card builder with no live caller (roster renders via
RosterCardView in _roster_cell.py).
"""
from ._imports import *  # noqa: F401,F403


# ============================================================
#  ROSTER
# ============================================================


def refresh_roster_grid(roster_screen):
    rv = roster_screen.ids.get('roster_rv')
    if not rv:
        return
    rv.data = [dict(d) for d in roster_screen.gladiators_data]
