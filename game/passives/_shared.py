# Build: 1
"""Shared imports for game.passives submodules.

Mirrors game/models/_imports.py: one explicit import block instead of the
same `from game.constants import ...` line fanned out across every submodule.

Hard rule for this package: it must NOT import game.models or game.battle at
module scope. game/battle/_shared.py already does `from game.models import
...`, and game/models/fighterperksmixin.py has to read COMPILED_PASSIVES — so
a registry living under either of those would close an import cycle. Only
game.constants and game.slots (both leaves) may be imported here.
`tests/test_item_passives.py` asserts this.
"""
import logging  # noqa: F401

from game.constants import (  # noqa: F401
    PASSIVE_KEY_SEPARATOR, PASSIVE_MAX_PER_ITEM,
)
from game.slots import SLOTS, EQUIPMENT_SLOTS  # noqa: F401

_log = logging.getLogger(__name__)
