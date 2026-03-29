# Build: 1
"""Prestige system — permanent progression across roguelike runs."""

import json
import logging
import os

from game.models import Result

_log = logging.getLogger(__name__)

# --- Load prestige reward table ---

def _load_prestige_data():
    """Load prestige levels from data/prestige.json."""
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    path = os.path.join(base, "prestige.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return {entry["level"]: entry for entry in data.get("levels", [])}
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        _log.warning("[Prestige] Failed to load prestige.json: %s", exc)
        return {}

PRESTIGE_REWARDS = _load_prestige_data()

# Required arena tier to prestige
PRESTIGE_ARENA_REQUIREMENT = 15


class PrestigeManager:
    """Manages prestige progression — permanent bonuses across runs."""

    def __init__(self, engine):
        self.engine = engine

    def can_prestige(self) -> bool:
        """Can prestige if arena_tier >= 15 (alive or dead)."""
        return self.engine.arena_tier >= PRESTIGE_ARENA_REQUIREMENT

    def get_stat_bonus(self) -> float:
        """Return stat multiplier (e.g., 1.10 for +10%)."""
        return 1.0 + self.engine.prestige_level * 0.02

    def get_prestige_reward_preview(self) -> dict:
        """Preview what the next prestige level gives.

        Returns dict with keys: level, stat_bonus_pct, unlock, description.
        """
        next_level = self.engine.prestige_level + 1
        if next_level in PRESTIGE_REWARDS:
            return dict(PRESTIGE_REWARDS[next_level])
        # Beyond table — still gives +2% per level, no special unlock
        return {
            "level": next_level,
            "stat_bonus_pct": next_level * 2,
            "unlock": None,
            "description": f"+{next_level * 2}% base stats",
        }

    def do_prestige(self) -> Result:
        """Execute prestige: reset run, increment level, apply bonuses."""
        if not self.can_prestige():
            return Result(False, "Cannot prestige yet — reach arena tier 15", "not_ready")

        self.engine.prestige_level += 1
        level = self.engine.prestige_level

        # Roguelike reset preserves prestige_level (see engine.roguelike_reset)
        self.engine.roguelike_reset()

        # Update prestige_bonus on all newly spawned fighters
        bonus = self.get_stat_bonus()
        for f in self.engine.fighters:
            f.prestige_bonus = bonus

        self.engine.save()

        reward = PRESTIGE_REWARDS.get(level)
        desc = reward["description"] if reward else f"+{level * 2}% base stats"
        return Result(True, f"Prestige {level}! {desc}", "prestige_up")

    def is_unlocked(self, feature_id: str) -> bool:
        """Check if a prestige-gated feature is unlocked.

        feature_id examples: 'mutators', 'mutator_slot_2', 'class_berserker',
        'class_retiarius', 'dual_enchantment', 'class_medicus',
        'mutator_slot_3', 'title_ascended', 'diamond_earn_bonus_50'.
        """
        for lvl in range(1, self.engine.prestige_level + 1):
            reward = PRESTIGE_REWARDS.get(lvl)
            if not reward or not reward.get("unlock"):
                continue
            unlocks = [u.strip() for u in reward["unlock"].split(",")]
            if feature_id in unlocks:
                return True
        return False

    def get_all_unlocks(self) -> list[str]:
        """Return list of all feature_ids unlocked at current prestige level."""
        unlocked = []
        for lvl in range(1, self.engine.prestige_level + 1):
            reward = PRESTIGE_REWARDS.get(lvl)
            if not reward or not reward.get("unlock"):
                continue
            unlocked.extend(u.strip() for u in reward["unlock"].split(","))
        return unlocked
