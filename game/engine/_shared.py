# Build: 9
"""Internal shared imports for game.engine submodules."""
import json
import logging
import math
import os
import random
import time

import game.models as _m
from game.models import (
    Fighter, Enemy, Boss, FIGHTER_CLASSES,
    DifficultyScaler, EQUIPMENT_SLOTS,
    get_upgrade_tier, item_display_name, get_max_upgrade,
    get_dynamic_shop_items, fmt_num, get_boss_name, Result,
)
from game.slots import SLOTS
from game.localization import (t, get_language, set_language,
                               get_requested_language)
from game.battle import (BattleManager, BattlePhase, BattleResult,
                         BossModifierHandler)
from game.achievements import ACHIEVEMENTS, build_achievements_from_json
from game.diamonds import DIAMOND_SHOP, DIAMOND_BUNDLES
import game.achievements as _ach_module
from game.constants import (
    STARTING_GOLD, RENAME_COST_DIAMONDS, EXPEDITION_SLOT_BASE_COST,
    HP_HEAL_TIER_MULT, HP_HEAL_DIVISOR, INJURY_HEAL_BASE_COST,
    EVENT_LOG_MAX, SHARD_TIER_COUNT, BATTLE_SPEED_OPTIONS,
    PLAYER_MAX_LEVEL, PLAYER_XP_BASE, PLAYER_XP_EXPO,
    PLAYER_XP_PER_ARENA_WIN, PLAYER_XP_PER_TIER, PLAYER_XP_PER_BOSS_KILL,
    PLAYER_XP_PER_EXPEDITION, PLAYER_XP_PER_ACHIEVEMENT, FEATURE_UNLOCKS,
)
from game.story import TUTORIAL_STEPS, STORY_CHAPTERS, get_pending_tutorial
from game.data_loader import data_loader
from game.mutators import mutator_registry

_log = logging.getLogger(__name__)


def default_shards():
    """Fresh all-zero shard wallet, one slot per tier 1..SHARD_TIER_COUNT."""
    return {tier: 0 for tier in range(1, SHARD_TIER_COUNT + 1)}


# --- Save schema ---
CURRENT_SAVE_VERSION = 2
# Migrations run sequentially: key N transforms schema version N → N+1.
# Saves without "schema_version" are treated as version 0. Register new
# migrations via `register_migration(from_version)` so typos and version
# gaps are caught at import time, not in the field when a player's save
# silently falls through the loader. The migration functions themselves
# live in game/engine/_migrations.py, imported by the package __init__.
_SAVE_MIGRATIONS = {}


def register_migration(from_version):
    """Decorator: register a save-schema migration from_version → from_version+1.

    Usage (in a future schema bump):

        @register_migration(1)
        def _v1_to_v2(data):
            data["new_field"] = data.pop("old_field", 0)
            return data

    Enforces no duplicate registrations and that from_version is non-negative
    and strictly less than CURRENT_SAVE_VERSION — because a migration from a
    version that is already current would never run, which is almost always
    a sign the engineer forgot to bump CURRENT_SAVE_VERSION.
    """
    if not isinstance(from_version, int) or from_version < 0:
        raise ValueError(
            "register_migration: from_version must be a non-negative int, "
            f"got {from_version!r}"
        )
    if from_version >= CURRENT_SAVE_VERSION:
        raise ValueError(
            f"register_migration({from_version}): bump CURRENT_SAVE_VERSION "
            f"to at least {from_version + 1} before registering this migration."
        )
    if from_version in _SAVE_MIGRATIONS:
        raise ValueError(
            f"register_migration: migration from version {from_version} "
            "already registered."
        )

    def _decorator(fn):
        _SAVE_MIGRATIONS[from_version] = fn
        return fn

    return _decorator
