# Build: 6
"""models._fighter — Fighter class + stats/equip/perks/serialize mixins."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler
from ._combat import CombatUnit
from ._data import FIGHTER_NAMES, FIGHTER_CLASSES

from .fighterstatsmixin import _FighterStatsMixin
from .fighterequipmixin import _FighterEquipMixin
from .fighterperksmixin import _FighterPerksMixin
from .fighterserializemixin import _FighterSerializeMixin

class Fighter(CombatUnit, _FighterStatsMixin, _FighterEquipMixin, _FighterPerksMixin, _FighterSerializeMixin):
    def __init__(self, name=None, level=1, fighter_class="mercenary"):
        cls_data = FIGHTER_CLASSES.get(fighter_class, FIGHTER_CLASSES["mercenary"])
        self.name = name or random.choice(FIGHTER_NAMES)
        self.fighter_class = fighter_class
        self.level = level

        # Core stats (distributable)
        self.strength = cls_data["base_str"]
        self.agility = cls_data["base_agi"]
        self.vitality = cls_data["base_vit"]
        self.unused_points = FIGHTER_STARTING_POINTS

        # Class modifiers (stored for reference)
        self.crit_bonus = cls_data["crit_bonus"]
        self.dodge_bonus = cls_data["dodge_bonus"]
        self.hp_mult = cls_data["hp_mult"]
        self.points_per_level = cls_data["points_per_level"]

        # Expedition-granted flat bonuses (used in attack/defense/max_hp formulas)
        self.base_attack = 0
        self.base_defense = 0
        self.base_hp = 0

        self.alive = True
        self.injuries = []  # list of {"id": "split_lip"} dicts
        self.kills = 0
        self.perk_points = 0
        self.unlocked_perks = []  # list of perk IDs
        self.equipment = {"weapon": None, "armor": None, "accessory": None, "relic": None}
        self.on_expedition = False
        self.expedition_id = None
        self.expedition_end = 0.0
        self.is_active = True
        # Stamina/Fatigue. Stamina drains per battle; once at 0, fatigue rises
        # in its place. Fatigue >= FATIGUE_MAX locks the fighter out of arena.
        from game.constants import STAMINA_MAX
        self.stamina = STAMINA_MAX
        self.fatigue = 0
        # When True, level_up triggers engine.auto_distribute (stats by class
        # base_str/agi/vit profile, own-class perks tier-asc).
        self.auto_distribute_enabled = False
        self.hp = self.max_hp

    @property
    def available(self):
        """True if fighter can act: alive, not on expedition, not benched, not exhausted."""
        from game.constants import FATIGUE_MAX
        if self.fatigue >= FATIGUE_MAX:
            return False
        return self.alive and not self.on_expedition and self.is_active

    @property
    def fatigue_mult(self):
        """Combat-stat multiplier from fatigue: 1.0 at 0 fatigue, 0.0 at 100."""
        from game.constants import FATIGUE_MAX
        return max(0.0, 1.0 - self.fatigue / FATIGUE_MAX)

    @property
    def is_exhausted(self):
        from game.constants import FATIGUE_MAX
        return self.fatigue >= FATIGUE_MAX

    def apply_battle_fought(self):
        """Drain stamina; once at 0, accrue fatigue. Called per battle participated."""
        from game.constants import (STAMINA_DRAIN_PER_BATTLE,
                                    FATIGUE_GAIN_PER_BATTLE,
                                    FATIGUE_MAX)
        if self.stamina > 0:
            self.stamina = max(0, self.stamina - STAMINA_DRAIN_PER_BATTLE)
        else:
            self.fatigue = min(FATIGUE_MAX, self.fatigue + FATIGUE_GAIN_PER_BATTLE)
        # max_hp may have shrunk from new fatigue — keep current hp in bounds.
        if self.hp > self.max_hp:
            self.hp = self.max_hp

    def apply_battle_skipped(self):
        """Recover from a skipped battle: priority fatigue → stamina.
        Also progresses injury auto-heal counters and removes healed injuries.
        """
        from game.constants import (STAMINA_MAX,
                                    STAMINA_RECOVERY_PER_REST,
                                    FATIGUE_RECOVERY_PER_REST,
                                    SEVERITY_HEAL_THRESHOLD)
        if self.fatigue > 0:
            self.fatigue = max(0, self.fatigue - FATIGUE_RECOVERY_PER_REST)
        elif self.stamina < STAMINA_MAX:
            self.stamina = min(STAMINA_MAX, self.stamina + STAMINA_RECOVERY_PER_REST)
        # Progress injury heal counters.
        remaining = []
        for inj in self.injuries:
            data = self._get_injury_data(inj["id"])
            severity = data.get("severity", "minor")
            threshold = SEVERITY_HEAL_THRESHOLD.get(severity)
            if threshold is None:
                # permanent or unknown severity: never auto-heals.
                remaining.append(inj)
                continue
            inj["heal_progress"] = inj.get("heal_progress", 0) + 1
            if inj["heal_progress"] < threshold:
                remaining.append(inj)
        self.injuries = remaining

    @property
    def class_name(self):
        return FIGHTER_CLASSES.get(self.fighter_class, {}).get("name", "Unknown")

    @property
    def injury_count(self):
        return len(self.injuries)

    @property
    def has_permanent_injury(self):
        """True if fighter has at least one permanent (unhealable) injury."""
        for inj in self.injuries:
            data = self._get_injury_data(inj["id"])
            if data.get("heal_cost_multiplier", 1) == 0:
                return True
        return False

    def _get_injury_data(self, injury_id):
        from game.data_loader import data_loader
        return data_loader.injuries_by_id.get(injury_id, {})

    def _injury_stat_penalty(self, *stat_names):
        """Return total percent penalty (0.0–0.95) from all injuries for given stat(s)."""
        total = 0.0
        for inj in self.injuries:
            data = self._get_injury_data(inj["id"])
            for pen in data.get("stat_penalties", []):
                if pen["stat"] in stat_names:
                    total += pen["value"]
        return min(total, 0.95)

    _cached_all_perks_map = None

    @classmethod
    def _get_all_perks_map(cls):
        """Cached {perk_id: perk_dict} from all classes."""
        cache = cls._cached_all_perks_map
        if cache is not None:
            return cache
        result = {}
        for cls_data in FIGHTER_CLASSES.values():
            for perk in cls_data.get("perk_tree", []):
                result[perk["id"]] = perk
        cls._cached_all_perks_map = result
        return result

    def distribute_point(self, stat):
        """Spend 1 unused point on STR, AGI, or VIT. Returns True if success."""
        if self.unused_points <= 0:
            return False
        if stat == "strength":
            self.strength += 1
        elif stat == "agility":
            self.agility += 1
        elif stat == "vitality":
            old_max = self.max_hp
            self.vitality += 1
            self.hp += self.max_hp - old_max
        else:
            return False
        self.unused_points -= 1
        return True

    def auto_distribute_stats(self):
        """Allocate all unused_points to STR/AGI/VIT by class base-stat ratios.

        Each point goes to the stat whose current allocated share lags
        farthest behind its target weight (greedy weighted distribution).
        Converges to the class profile over many levels regardless of
        prior manual allocations. Returns count of points spent.
        """
        if self.unused_points <= 0:
            return 0
        cls_data = FIGHTER_CLASSES.get(self.fighter_class, FIGHTER_CLASSES["mercenary"])
        base_str = cls_data.get("base_str", 0)
        base_agi = cls_data.get("base_agi", 0)
        base_vit = cls_data.get("base_vit", 0)
        total_base = max(1, base_str + base_agi + base_vit)
        weights = {
            "strength": base_str / total_base,
            "agility": base_agi / total_base,
            "vitality": base_vit / total_base,
        }
        spent = 0
        while self.unused_points > 0:
            allocated = {
                "strength": max(0, self.strength - base_str),
                "agility": max(0, self.agility - base_agi),
                "vitality": max(0, self.vitality - base_vit),
            }
            denom = sum(allocated.values()) + 1
            best_stat = max(
                weights.keys(),
                key=lambda s: weights[s] - allocated[s] / denom,
            )
            if not self.distribute_point(best_stat):
                break
            spent += 1
        return spent

    def level_up(self):
        """Level up: gain stat points based on class, perk point every 5 levels."""
        self.level += 1
        self.unused_points += self.points_per_level
        if self.level % PERK_POINT_EVERY_N_LEVELS == 0:
            self.perk_points += 1
        self.hp = self.max_hp

    def heal(self):
        self.hp = self.max_hp

    def check_permadeath(self):
        """Check permadeath. Returns (died: bool, injury_id: str|None)."""
        if random.random() < self.death_chance:
            self.alive = False
            return True, None
        from game.data_loader import data_loader
        existing_ids = {inj["id"] for inj in self.injuries}
        injury_id = data_loader.pick_random_injury(
            existing_ids,
            severity_reduction_chance=self.get_perk_effects("reduce_injury_severity"),
        )
        self.injuries.append({"id": injury_id})
        if self.hp > self.max_hp:
            self.hp = self.max_hp
        return False, injury_id

    def get_injury_heal_cost(self, injury_idx=0):
        """Cost to heal a specific injury. Returns -1 for permanent (unhealable)."""
        if not self.injuries:
            return 0
        idx = min(injury_idx, len(self.injuries) - 1)
        inj = self.injuries[idx]
        data = self._get_injury_data(inj["id"])
        mult = data.get("heal_cost_multiplier", 1.0)
        if mult == 0:
            return -1
        base = INJURY_HEAL_BASE_COST * max(1, self.level)
        return int(base * mult)

    def cheapest_healable_injury_idx(self):
        """Return index of cheapest non-permanent injury, or -1 if none."""
        best_idx, best_cost = -1, float('inf')
        for i in range(len(self.injuries)):
            cost = self.get_injury_heal_cost(i)
            if 0 < cost < best_cost:
                best_idx, best_cost = i, cost
        return best_idx
