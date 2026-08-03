# Build: 4
"""models._enemy — Enemy & Boss: from_template + tier scaling."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler
from ._combat import CombatUnit
from ._fighter import Fighter

class Enemy(CombatUnit):
    """Arena opponent with exponential stat growth.

    Enemies get a small crit and dodge chance that scales with tier,
    making high-tier fights unpredictable and dangerous.
    """

    def __init__(self, tier=1):
        self.tier = tier
        self.role = "soldier"
        title_idx = min(tier - 1, len(ENEMY_TITLES) - 1)
        self.name = ENEMY_TITLES[title_idx]

        atk, defense, hp = DifficultyScaler.enemy_stats(tier)
        self.attack = atk
        self.defense = defense
        self.max_hp = hp
        self.hp = self.max_hp
        self.gold_reward = DifficultyScaler.enemy_reward(tier)

        self.is_boss = False

        # Enemies get luck too — tier-scaling crit/dodge
        self.crit_chance = min(ENEMY_CRIT_CAP, ENEMY_CRIT_BASE + tier * ENEMY_CRIT_PER_TIER)
        self.dodge_chance = min(ENEMY_DODGE_CAP, tier * ENEMY_DODGE_PER_TIER)

    @property
    def crit_mult(self):
        return ENEMY_CRIT_MULT

    @classmethod
    def from_template(cls, template, tier):
        """Create enemy from JSON template with role/bias stat modifiers."""
        enemy = cls.__new__(cls)
        enemy.tier = tier
        enemy.name = template.get("name", ENEMY_TITLES[min(tier - 1, len(ENEMY_TITLES) - 1)])
        enemy.is_boss = False

        base_atk, base_def, base_hp = DifficultyScaler.enemy_stats(tier)
        role = template.get("role", "soldier")
        enemy.role = role
        bias = template.get("stat_bias", "balanced")
        rm = ROLE_MULT.get(role, 1.0)
        rsm = ROLE_STAT_MULT.get(role, {})
        bm = STAT_BIAS_MULT.get(bias, {})

        # Stat pipeline (see CLAUDE.md): ATK derives from str, DEF and HP both
        # derive from vit — same as fighters, where DEF = total_vitality + ...
        # and max_HP = vit * FIGHTER_HP_PER_VIT + ... ('agi' feeds dodge, not DEF).
        enemy.attack = int(base_atk * rm * rsm.get("str", 1.0) * bm.get("str", 1.0))
        enemy.defense = int(base_def * rm * rsm.get("vit", 1.0) * bm.get("vit", 1.0))
        enemy.max_hp = int(base_hp * rm * rsm.get("vit", 1.0) * bm.get("vit", 1.0))
        enemy.hp = enemy.max_hp
        enemy.gold_reward = DifficultyScaler.enemy_reward(tier)

        enemy.crit_chance = min(ENEMY_CRIT_CAP, ENEMY_CRIT_BASE + tier * ENEMY_CRIT_PER_TIER)
        enemy.dodge_chance = min(ENEMY_DODGE_CAP, tier * ENEMY_DODGE_PER_TIER)
        return enemy


class Boss(Enemy):
    """Boss enemy — stronger stats, unique name, no dodge."""

    def __init__(self, arena_tier):
        boss_tier = arena_tier + BOSS_TIER_OFFSET
        super().__init__(tier=boss_tier)
        self._apply_boss_multipliers()
        self.name = f"BOSS: {get_boss_name(arena_tier)}"
        self.modifiers = []

    def _apply_boss_multipliers(self):
        self.max_hp = int(self.max_hp * BOSS_HP_MULT)
        self.hp = self.max_hp
        self.attack = int(self.attack * BOSS_ATK_MULT)
        self.defense = int(self.defense * BOSS_DEF_MULT)
        self.gold_reward = int(self.gold_reward * BOSS_GOLD_MULT)
        self.crit_chance = max(BOSS_CRIT_MIN, self.crit_chance + BOSS_CRIT_BONUS)
        self.dodge_chance = 0
        self.is_boss = True

    @classmethod
    def from_template(cls, template, arena_tier):
        """Create boss from JSON template with boss multipliers."""
        boss_tier = arena_tier + BOSS_TIER_OFFSET
        boss = Enemy.from_template(template, boss_tier)
        boss.__class__ = cls
        boss._apply_boss_multipliers()
        boss.name = f"BOSS: {template.get('name', get_boss_name(arena_tier))}"
        boss.modifiers = []
        return boss
