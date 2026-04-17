# Build: 1
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
from game.localization import t, get_language, set_language
from game.battle import BattleManager, BattlePhase, BattleResult
from game.achievements import ACHIEVEMENTS, DIAMOND_SHOP, DIAMOND_BUNDLES, build_achievements_from_json
import game.achievements as _ach_module
from game.constants import (
    STARTING_GOLD, RENAME_COST_DIAMONDS, EXPEDITION_SLOT_BASE_COST,
    HP_HEAL_TIER_MULT, HP_HEAL_DIVISOR, INJURY_HEAL_BASE_COST,
)
from game.story import TUTORIAL_STEPS, STORY_CHAPTERS, get_pending_tutorial
from game.data_loader import data_loader
from game.mutators import mutator_registry

_log = logging.getLogger(__name__)

# --- Save schema ---
CURRENT_SAVE_VERSION = 1
# Migrations run sequentially: key N transforms schema version N → N+1.
# Saves without "schema_version" are treated as version 0.
_SAVE_MIGRATIONS = {
    # 0: lambda d: d,   # placeholder for future schema bumps
}
