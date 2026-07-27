# Build: 3
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


def test_no_missing_class_attrs_from_splits():
    """Classes that went through the mixin-splitter sometimes lose their
    module-level / class-level `UPPER_CASE = ...` constants because the
    splitter only moved FunctionDefs. This test checks a curated list of
    well-known constants that MUST exist on the split classes.
    """
    from game.battle import BattleManager
    from game.engine import GameEngine

    expected = [
        (BattleManager, "MAX_SKIP_BATTLE_TURNS"),
        (BattleManager, "_SKILL_SUMMARY_KEYS"),
        (GameEngine,   "MAX_BATTLE_LOG_LINES"),
        (GameEngine,   "BATTLE_LOG_HEAD"),
        (GameEngine,   "BATTLE_LOG_TAIL"),
    ]
    missing = [(cls.__name__, attr) for (cls, attr) in expected if not hasattr(cls, attr)]
    assert not missing, f"Split classes missing class-level constants: {missing}"


def test_cross_package_name_resolution():
    """Walk every submodule of every split package and flag any method
    that does LOAD_GLOBAL on a name defined in a sibling submodule but
    not imported. This is the test that would have caught the
    NavBar/NavButton/theme/etc. crashes that only fire on clock tick.
    """
    import os
    import importlib

    PKGS = [
        "game.widgets", "game.models", "game.iap", "game.app",
        "game.engine", "game.cloud_save", "game.leaderboard",
        "game.data_loader", "game.ui_helpers", "game.scripting",
        "game.battle",
        "game.screens.roster", "game.screens.forge", "game.screens.arena",
        "game.screens.lore", "game.screens.more",
    ]

    # Names we intentionally resolve via lazy-import-inside-function:
    LAZY_OK = {"NavBar", "NavButton"}

    issues = []
    for pkg_name in PKGS:
        try:
            pkg = importlib.import_module(pkg_name)
        except Exception as e:
            issues.append(f"{pkg_name}: import FAIL {e}")
            continue
        pkg_dir = os.path.dirname(pkg.__file__)

        defined_in = {}
        submods = []
        for fn in sorted(os.listdir(pkg_dir)):
            if not fn.endswith(".py") or fn.startswith("__"):
                continue
            try:
                mod = importlib.import_module(f"{pkg_name}.{fn[:-3]}")
            except Exception:
                continue
            submods.append(mod)
            for name in vars(mod):
                defined_in.setdefault(name, []).append(fn[:-3])

        for mod in submods:
            mod_globals = set(vars(mod).keys())
            for name, obj in list(vars(mod).items()):
                if not isinstance(obj, type):
                    continue
                if obj.__module__ != mod.__name__:
                    continue
                for meth_name, m in vars(obj).items():
                    if not callable(m) or not hasattr(m, "__code__"):
                        continue
                    for instr in dis.get_instructions(m):
                        if instr.opname not in ("LOAD_GLOBAL", "LOAD_NAME"):
                            continue
                        n = instr.argval[1] if isinstance(instr.argval, tuple) else instr.argval
                        if not isinstance(n, str):
                            continue
                        if n in mod_globals or n in _BUILTIN_NAMES:
                            continue
                        if n in LAZY_OK:
                            continue
                        if n in defined_in:
                            issues.append(
                                f"{pkg_name}.{os.path.basename(mod.__file__)[:-3]}."
                                f"{obj.__name__}.{meth_name} uses {n!r} "
                                f"(defined in sibling {defined_in[n]})"
                            )

    assert not issues, "Cross-package name-resolution issues:\n  " + "\n  ".join(issues)
