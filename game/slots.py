# Build: 1
"""Equipment slot registry — single source of truth for per-slot behavior.

Adding a new slot type should only require:
  1. Adding an entry to SLOTS here
  2. Adding the corresponding JSON data file
  3. Adding UI tab in forge (the actual per-slot UI branching is gone)

Everything else — upgrade formulas, shard multipliers, enchant eligibility,
stat pools — is driven from this registry.
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict


@dataclass(frozen=True)
class SlotDef:
    """Describes the behavior of an equipment slot.

    Fields:
      id: slot identifier used in item dicts (item["slot"])
      upgrade_pool: stat names summed to compute the upgrade bonus base
        (e.g. ("str","agi") means (total_str + total_agi) * lvl * 20% = bonus)
      upgrade_targets: final-stat(s) the bonus applies to
        ("atk",) = weapon bonus goes to ATK
        ("def",) = armor bonus goes to DEF
        ("hp",)  = accessory bonus goes to HP
        ("atk","def","hp") = relic bonus splits equally across all three
      pool_multiplier: multiplier applied to the pool BEFORE percent-level math.
        accessory uses 5.0 (VIT+STR is small, multiplied by 5 for HP scale).
      pool_multiplier_per_target: per-target pool multipliers override
        pool_multiplier when present. Relic uses {"atk":1.0,"def":1.0,"hp":5.0}
        because HP needs its own scale.
      pool_per_target: per-target stat pools when different from upgrade_pool.
        Relic uses different pools per target (STR+AGI → ATK, AGI+VIT → DEF,
        VIT+STR → HP).
      split_divisor: divide the final bonus by this. Relic = 3 (equal split
        across ATK/DEF/HP); others = 1.
      can_enchant: True if items in this slot accept enchantments.
      shard_multiplier: multiplies the shard cost for upgrades (relic = 10x).
      label_keys: i18n keys for UI labels.
        "upper": shop/inventory header
        "base":  "X base stat" label shown in upgrade comparison
    """
    id: str
    upgrade_pool: Tuple[str, ...]
    upgrade_targets: Tuple[str, ...]
    pool_multiplier: float = 1.0
    pool_multiplier_per_target: Dict[str, float] = field(default_factory=dict)
    pool_per_target: Dict[str, Tuple[str, ...]] = field(default_factory=dict)
    split_divisor: int = 1
    can_enchant: bool = False
    shard_multiplier: int = 1
    label_keys: Dict[str, str] = field(default_factory=dict)

    def pool_for(self, target):
        """Stats summed into the pool for a given upgrade target."""
        return self.pool_per_target.get(target, self.upgrade_pool)

    def mult_for(self, target):
        """Pool multiplier for a given upgrade target."""
        return self.pool_multiplier_per_target.get(target, self.pool_multiplier)


SLOTS: Dict[str, SlotDef] = {
    "weapon": SlotDef(
        id="weapon",
        upgrade_pool=("str", "agi"),
        upgrade_targets=("atk",),
        pool_multiplier=1.0,
        can_enchant=True,
        shard_multiplier=1,
        label_keys={"upper": "slot_weapon_upper", "base": "weapon_base_atk"},
    ),
    "armor": SlotDef(
        id="armor",
        upgrade_pool=("agi", "vit"),
        upgrade_targets=("def",),
        pool_multiplier=1.0,
        can_enchant=False,
        shard_multiplier=1,
        label_keys={"upper": "slot_armor_upper", "base": "armor_base_def"},
    ),
    "accessory": SlotDef(
        id="accessory",
        upgrade_pool=("vit", "str"),
        upgrade_targets=("hp",),
        pool_multiplier=5.0,
        can_enchant=False,
        shard_multiplier=1,
        label_keys={"upper": "slot_accessory_upper", "base": "accessory_base_hp"},
    ),
    "relic": SlotDef(
        id="relic",
        upgrade_pool=("str", "agi", "vit"),
        upgrade_targets=("atk", "def", "hp"),
        pool_multiplier=1.0,
        pool_multiplier_per_target={"atk": 1.0, "def": 1.0, "hp": 5.0},
        pool_per_target={
            "atk": ("str", "agi"),
            "def": ("agi", "vit"),
            "hp":  ("vit", "str"),
        },
        split_divisor=3,
        can_enchant=False,
        shard_multiplier=10,
        label_keys={"upper": "slot_relic_upper", "base": "relic_base"},
    ),
}

# Ordered list of slot IDs — matches prior EQUIPMENT_SLOTS for save compat.
EQUIPMENT_SLOTS = list(SLOTS.keys())
