# Build: 2
"""models._combat — CombatUnit: shared take_damage/deal_damage."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403

class CombatUnit:
    """Shared combat methods for Fighter and Enemy."""

    def take_damage(self, raw_dmg):
        if random.random() < self.dodge_chance:
            return 0
        reduction = self.defense / (self.defense + DEFENSE_DIVISOR)
        reduced = max(1, int(raw_dmg * (1 - reduction)))
        self.hp = max(0, self.hp - reduced)
        return reduced

    def deal_damage(self):
        variance = random.uniform(DAMAGE_VARIANCE_LOW, DAMAGE_VARIANCE_HIGH)
        return max(1, int(self.attack * variance))
