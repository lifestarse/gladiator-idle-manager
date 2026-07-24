# Build: 3
"""GameEngine _PersistenceMixin — combines read/snapshot/write persistence mixins."""
from .persistencereadmixin import _PersistenceReadMixin
from .persistencesnapshotmixin import _PersistenceSnapshotMixin
from .persistencewritemixin import _PersistenceWriteMixin


class _PersistenceMixin(_PersistenceWriteMixin, _PersistenceSnapshotMixin,
                        _PersistenceReadMixin):
    pass
