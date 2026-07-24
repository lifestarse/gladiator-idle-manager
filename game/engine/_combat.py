# Build: 5
"""GameEngine _CombatMixin — combines spawn + flow + resolve combat mixins."""
from .combatspawnmixin import _CombatSpawnMixin
from .combatflowmixin import _CombatFlowMixin
from .combatresolvemixin import _CombatResolveMixin


class _CombatMixin(_CombatFlowMixin, _CombatSpawnMixin, _CombatResolveMixin):
    pass
