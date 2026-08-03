# Build: 3
"""models._combat — CombatUnit: shared take_damage/deal_damage."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403

class CombatUnit:
    """Shared combat methods for Fighter and Enemy."""

    def take_damage(self, raw_dmg):
        if random.random() < self.dodge_chance:
            return 0
        reduced = max(1, int(raw_dmg * (1 - defense_mitigation(self.defense))))
        self.hp = max(0, self.hp - reduced)
        return reduced

    def deal_damage(self):
        variance = random.uniform(DAMAGE_VARIANCE_LOW, DAMAGE_VARIANCE_HIGH)
        return max(1, int(self.attack * variance))
