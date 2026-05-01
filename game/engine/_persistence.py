# Build: 2
"""GameEngine _PersistenceMixin — combines read + write persistence mixins."""
from .persistencereadmixin import _PersistenceReadMixin
from .persistencewritemixin import _PersistenceWriteMixin


class _PersistenceMixin(_PersistenceWriteMixin, _PersistenceReadMixin):
    pass
