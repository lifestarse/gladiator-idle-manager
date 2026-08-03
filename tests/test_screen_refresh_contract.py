# Build: 1
"""Every screen with per-tick content must be reachable from the idle tick.

App._idle_tick calls exactly one method on the current screen —
BaseScreen.refresh(). A screen that owns a refresh_* method but does not
route it through that override is simply never redrawn on the one-second
tick: no exception, no log line, just a screen that looks frozen. This test
is the mechanism that makes that failure loud.
"""
from game.base_screen import BaseScreen


def _all_screen_classes():
    """Every BaseScreen subclass reachable once the app module is imported."""
    import game.app._core  # noqa: F401  — pulls in every registered screen

    found, stack = [], list(BaseScreen.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    return found


def _own_refresh_methods(cls):
    return sorted(
        name for name in dir(cls)
        if name.startswith("refresh_") and callable(getattr(cls, name, None))
    )


def test_screens_are_discoverable():
    assert _all_screen_classes(), "no BaseScreen subclasses found"


def test_screens_with_pertick_content_override_refresh():
    offenders = []
    for cls in _all_screen_classes():
        methods = _own_refresh_methods(cls)
        if methods and cls.refresh is BaseScreen.refresh:
            offenders.append(
                f"{cls.__module__}.{cls.__name__} has {methods} "
                f"but does not override refresh()")
    assert not offenders, (
        "these screens are never redrawn by App._idle_tick:\n  "
        + "\n  ".join(offenders))


def test_base_refresh_is_a_safe_no_op():
    """A screen with no per-tick content inherits the default; the tick calls
    it unconditionally, so the default must never raise."""
    assert BaseScreen.refresh(object()) is None
