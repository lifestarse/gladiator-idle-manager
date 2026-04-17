# Build: 1
"""GameEngine _PersistenceMixin — extracted from monolithic engine.py."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module, _SAVE_MIGRATIONS, CURRENT_SAVE_VERSION


from .persistencewritemixin import _PersistenceWriteMixin
from .persistencereadmixin import _PersistenceReadMixin

class _PersistenceMixin(_PersistenceWriteMixin, _PersistenceReadMixin):
    pass
