# Build: 1
"""Import shim for environments that hide directories named ``input``.

BlueStacks' anti-detection layer filters entries named ``input`` out of
``readdir()`` results inside game processes (it masks emulated
``/dev/input`` devices from cheat scanners). Python's ``FileFinder``
resolves imports from the parent-directory listing, so ``kivy.input``
becomes unimportable there even though every file is present and readable
by exact path — Kivy then finds no window provider and the app dies on
startup.

The shim compares the directory listing with an exact-path probe. Only
when ``kivy/input`` exists on disk but is absent from the listing does it
install a meta-path finder that resolves ``kivy.input`` and its
submodules via exact paths, bypassing ``readdir``. On healthy platforms
(desktop, real Android) importing this module is a no-op.

Must be imported before anything imports ``kivy``.
"""
import importlib.machinery
import importlib.util
import os
import sys

_PREFIX = "kivy.input"
_SUFFIXES = (
    importlib.machinery.SOURCE_SUFFIXES + importlib.machinery.BYTECODE_SUFFIXES
)


def _kivy_dir():
    """Locate the kivy package directory without importing kivy."""
    try:
        spec = importlib.util.find_spec("kivy")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return next(iter(spec.submodule_search_locations), None)


class _ExactPathFinder:
    """Meta-path finder resolving ``kivy.input.*`` without readdir."""

    def __init__(self, kivy_dir):
        self._kivy_dir = kivy_dir

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _PREFIX and not fullname.startswith(_PREFIX + "."):
            return None
        rel_parts = fullname.split(".")[1:]  # drop leading "kivy"
        fs_path = os.path.join(self._kivy_dir, *rel_parts)
        for suffix in _SUFFIXES:
            init = os.path.join(fs_path, "__init__" + suffix)
            if os.path.isfile(init):
                return importlib.util.spec_from_file_location(
                    fullname, init, submodule_search_locations=[fs_path]
                )
            module_file = fs_path + suffix
            if os.path.isfile(module_file):
                return importlib.util.spec_from_file_location(
                    fullname, module_file
                )
        return None


def install():
    """Install the finder when kivy/input is readdir-hidden. Returns bool."""
    base = _kivy_dir()
    if base is None:
        return False
    input_dir = os.path.join(base, "input")
    exact = any(
        os.path.isfile(os.path.join(input_dir, "__init__" + suffix))
        for suffix in _SUFFIXES
    )
    try:
        listed = "input" in os.listdir(base)
    except OSError:
        listed = False
    active = exact and not listed
    if active:
        sys.meta_path.insert(0, _ExactPathFinder(base))
    if not listed:
        # Only log in the anomalous case to keep desktop startup quiet.
        print(
            "[kivy_input_shim] kivy dir=%s listed=%s exact=%s active=%s"
            % (base, listed, exact, active)
        )
    return active


SHIM_ACTIVE = install()
