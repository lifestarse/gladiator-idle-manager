# Build: 4
"""Fighter _FighterStatsMixin — derived atk/def/hp/crit/dodge from raw stats."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler
from ._combat import CombatUnit
from ._data import FIGHTER_NAMES, FIGHTER_CLASSES


class _FighterStatsMixin:
    @property
    def total_strength(self):
        return self.strength + self.equip_str

    @property
    def total_agility(self):
        return self.agility + self.equip_agi

    @property
    def total_vitality(self):
        return self.vitality + self.equip_vit

    def _stat_pool(self, stat_names):
        """Sum total_<stat> for each stat in the tuple (uses total_* properties)."""
        getters = {
            "str": lambda: self.total_strength,
            "agi": lambda: self.total_agility,
            "vit": lambda: self.total_vitality,
        }
        return sum(getters[s]() for s in stat_names)

    def _slot_upgrade_bonus(self, slot_id, target):
        """Generic per-target upgrade bonus driven by SLOTS registry.

        Formula: pool(slot, target) * lvl * 20% * mult(slot, target) / split_divisor.
        """
        slot = SLOTS.get(slot_id)
        if slot is None:
            return 0
        item = self.equipment.get(slot_id)
        if not item:
            return 0
        lvl = item.get("upgrade_level", 0)
        if lvl <= 0:
            return 0
        pool_val = self._stat_pool(slot.pool_for(target))
        raw = pool_val * lvl * UPGRADE_BONUS_PER_LEVEL / 100 * slot.mult_for(target)
        return int(raw) // slot.split_divisor

    def upgrade_bonus_for(self, target):
        """Sum upgrade bonuses from every equipped slot that targets `target`.

        target ∈ ("atk", "def", "hp"). Preserves prior behavior: weapon→atk,
        armor→def, accessory→hp, relic→all three (split by 3).
        """
        total = 0
        for slot in SLOTS.values():
            if target in slot.upgrade_targets:
                total += self._slot_upgrade_bonus(slot.id, target)
        return total

    @property
    def weapon_upgrade_atk(self):
        return self._slot_upgrade_bonus("weapon", "atk")

    @property
    def armor_upgrade_def(self):
        return self._slot_upgrade_bonus("armor", "def")

    @property
    def accessory_upgrade_hp(self):
        return self._slot_upgrade_bonus("accessory", "hp")

    @property
    def relic_upgrade_atk(self):
        return self._slot_upgrade_bonus("relic", "atk")

    @property
    def relic_upgrade_def(self):
        return self._slot_upgrade_bonus("relic", "def")

    @property
    def relic_upgrade_hp(self):
        return self._slot_upgrade_bonus("relic", "hp")

    @property
    def attack(self):
        base = (self.total_strength * FIGHTER_ATK_PER_STR + self.base_attack
                + (self.level - 1) * FIGHTER_ATK_PER_LEVEL
                + self.weapon_upgrade_atk + self.relic_upgrade_atk)
        result = int(base * (1 + self.get_perk_effects("damage_bonus")))
        penalty = self._injury_stat_penalty("attack", "strength")
        return max(1, round(result * (1 - penalty) * self.fatigue_mult))

    @property
    def defense(self):
        base = self.total_vitality + self.base_defense + self.armor_upgrade_def + self.relic_upgrade_def
        penalty = self._injury_stat_penalty("defense")
        return max(0, round(base * (1 - penalty) * self.fatigue_mult))

    @property
    def max_hp(self):
        base = (FIGHTER_BASE_HP + self.total_vitality * FIGHTER_HP_PER_VIT
                + self.base_hp + (self.level - 1) * FIGHTER_HP_PER_LEVEL
                + self.accessory_upgrade_hp + self.relic_upgrade_hp)
        result = int(base * self.hp_mult * (1 + self.get_perk_effects("hp_bonus_pct")))
        penalty = self._injury_stat_penalty("max_hp", "vitality")
        return max(1, round(result * (1 - penalty) * self.fatigue_mult))

    @property
    def effective_agility(self):
        """Total AGI including perk bonuses (crit/dodge perks add AGI)."""
        perk_bonus = (self.get_perk_effects("crit_chance_bonus")
                      + self.get_perk_effects("dodge_chance_bonus"))
        # Convert % bonuses to AGI points (e.g. 0.05 = +5 AGI)
        return self.total_agility + int(perk_bonus * 100)

    @property
    def crit_chance(self):
        agi = self.effective_agility
        raw = agi / (agi + CRIT_K) + self.crit_bonus
        penalty = self._injury_stat_penalty("crit_chance")
        return min(FIGHTER_CRIT_CAP, max(0.0, raw * (1 - penalty) * self.fatigue_mult))

    @property
    def crit_mult(self):
        return CRIT_MULT_BASE + self.effective_agility * CRIT_MULT_PER_AGI + self.get_perk_effects("crit_damage_bonus")

    @property
    def dodge_chance(self):
        raw = self.effective_agility * DODGE_AGI_FACTOR + self.dodge_bonus
        base = 1.0 - 1.0 / (1.0 + raw * DODGE_DIMINISH_FACTOR)
        penalty = self._injury_stat_penalty("dodge_chance", "agility")
        return min(FIGHTER_DODGE_CAP, max(0.0, base * (1 - penalty) * self.fatigue_mult))

    @property
    def damage_reduction(self):
        return self.get_perk_effects("damage_reduction")

    @property
    def power_rating(self):
        return self.attack + self.defense + self.max_hp // 5

    @property
    def death_chance(self):
        from game.constants import SEVERITY_DEATH_CHANCE
        total = DEATH_CHANCE_BASE
        for inj in self.injuries:
            data = self._get_injury_data(inj["id"])
            severity = data.get("severity", "minor")
            total += SEVERITY_DEATH_CHANCE.get(severity, 0.06)
        return min(DEATH_CHANCE_CAP, total)
