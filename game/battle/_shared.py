# Build: 1
"""Shared imports + helpers for game.battle package."""
import random
from collections import namedtuple
from enum import Enum, auto
from game.models import ENCHANTMENT_TYPES, fmt_num
from game.constants import (
    DAMAGE_VARIANCE_LOW, DAMAGE_VARIANCE_HIGH, DEFENSE_DIVISOR,
)
from game.localization import t

_fn = fmt_num

BattleResult = namedtuple("BattleResult", [
    "outcome",          # "ongoing" | "victory" | "defeat"
    "is_boss",          # bool
    "gold_earned",      # int
    "enemies_killed",   # int (enemies with hp <= 0)
    "survivors",        # list[Enemy] — enemies with hp > 0 (for revenge)
    "turn_number",      # int — for battle log
    "player_fighters",  # list[Fighter] — for battle log
    "enemies",          # list[Enemy] — for battle log
])
