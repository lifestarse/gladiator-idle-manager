# Build: 58
"""game.engine — split from 1674-line engine.py into package.

GameEngine is composed of domain mixins (Fighters, Combat, Forge,
Expeditions, Healing, Progression, Economy, Persistence) + core.
External imports `from game.engine import GameEngine` keep working.
"""

from game.engine._core import GameEngine, _default_save_path  # noqa: F401
from game.engine._shared import CURRENT_SAVE_VERSION, data_loader, mutator_registry, _log  # noqa: F401
