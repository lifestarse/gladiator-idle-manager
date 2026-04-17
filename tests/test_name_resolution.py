# Build: 1
"""Catch NameErrors that would only fire at runtime (on actual Kivy
event) by walking every method's co_names and checking each global
lookup resolves in the defining module's namespace.

This is the test that would have caught the v1.9.11 regression where
`_roster_callbacks` was used in on_enter but not re-exported to the
split screen package.
"""
import builtins
import dis
import inspect
import sys


_BUILTIN_NAMES = set(dir(builtins))


def _module_of(cls):
    return sys.modules.get(cls.__module__)


def _global_loads(func):
    """Yield every name that the function tries to resolve as a module
    global (LOAD_GLOBAL / LOAD_NAME opcodes). Skips LOAD_ATTR which also
    appears in co_names but is attribute access, not global lookup.
    """
    for instr in dis.get_instructions(func):
        if instr.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
            arg = instr.argval
            # Python 3.11+ encodes a "push NULL" flag in the name tuple.
            if isinstance(arg, tuple):
                arg = arg[1]
            if isinstance(arg, str):
                yield arg


def _check_class(cls, allow_missing=()):
    """For every method defined directly on `cls`, verify every global
    lookup resolves in the defining module's namespace.
    """
    allow_missing = set(allow_missing)
    mod = _module_of(cls)
    if mod is None:
        return []
    mod_globals = set(vars(mod).keys())

    problems = []
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if not method.__qualname__.startswith(cls.__name__ + "."):
            continue
        for referenced in _global_loads(method):
            if referenced in mod_globals or referenced in _BUILTIN_NAMES:
                continue
            if referenced in allow_missing:
                continue
            problems.append((method.__qualname__, referenced))
    return problems


def test_roster_screen_names_resolve():
    from game.screens.roster import RosterScreen
    # Walk every mixin class too
    bad = []
    for cls in RosterScreen.__mro__:
        if cls.__name__ == "RosterScreen" or cls.__name__.endswith("Mixin"):
            bad.extend(_check_class(cls))
    assert not bad, f"Unresolved globals in roster: {bad}"


def test_forge_screen_names_resolve():
    from game.screens.forge import ForgeScreen
    bad = []
    for cls in ForgeScreen.__mro__:
        if cls.__name__ == "ForgeScreen" or cls.__name__.endswith("Mixin"):
            bad.extend(_check_class(cls))
    assert not bad, f"Unresolved globals in forge: {bad}"


def test_engine_names_resolve():
    from game.engine import GameEngine
    bad = []
    for cls in GameEngine.__mro__:
        if cls.__name__ == "GameEngine" or cls.__name__.endswith("Mixin"):
            bad.extend(_check_class(cls))
    assert not bad, f"Unresolved globals in engine: {bad}"
