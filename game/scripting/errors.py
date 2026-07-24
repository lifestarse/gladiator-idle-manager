# Build: 1
"""Script runtime exceptions + internal control-flow signals.

Leaf module (no intra-package imports) so both interpreter mixins and the
manager can share these without import cycles. External code keeps
importing them from `.interpreter`, which re-exports.
"""


class ScriptError(Exception):
    pass


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass
