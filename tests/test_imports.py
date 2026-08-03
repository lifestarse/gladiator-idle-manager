# Build: 6
"""Import smoke tests — catch circular imports and missing re-exports
that would only manifest at runtime on Android.
"""


def test_main_imports():
    import main  # noqa: F401


def test_engine_package():
    from game.engine import GameEngine, CURRENT_SAVE_VERSION, _default_save_path
    # MRO must contain each mixin
    names = {c.__name__ for c in GameEngine.__mro__}
    for mn in [
        "_FightersMixin", "_CombatMixin", "_ForgeMixin", "_ExpeditionsMixin",
        "_HealingMixin", "_ProgressionMixin", "_EconomyMixin", "_PersistenceMixin",
    ]:
        assert mn in names, f"mixin {mn} not in GameEngine MRO"


def test_ui_helpers_public_api():
    # build_roster_card / build_forge_card / build_shop_card /
    # build_achievement_card removed in the 2026-08 redesign wave 0
    # cleanup (dead pre-RecycleView builders with no live caller).
    import game.ui_helpers as u
    for name in [
        "build_item_info_card",
        "build_expedition_card",
        "refresh_forge_grid", "refresh_roster_grid",
        "RosterCardView", "ArenaUnitCardView", "ForgeCardView",
        "InventoryCardView", "AchievementCardView",
        "bind_text_wrap", "make_styled_popup", "build_back_btn",
    ]:
        assert hasattr(u, name), f"ui_helpers missing {name}"


def test_screen_packages():
    from game.screens.roster import RosterScreen
    from game.screens.forge import ForgeScreen
    from game.screens.arena import ArenaScreen
    from game.screens.lore import LoreScreen
    from game.screens.more import MoreScreen
    from game.screens.expedition import ExpeditionScreen
    from game.screens.scripts import ScriptsScreen, ScriptEditorScreen
    # Check key methods survived the split
    assert hasattr(RosterScreen, "hire")
    assert hasattr(RosterScreen, "_show_perk_tree")
    assert hasattr(ForgeScreen, "buy")
    assert hasattr(ForgeScreen, "_show_enchant_view")
    assert hasattr(ForgeScreen, "_refresh_inventory_grid")
    # kv wires these by name via root._method(); a rename breaks on first tap.
    assert hasattr(ScriptsScreen, "_new_program")
    assert hasattr(ScriptsScreen, "_open_templates")
    assert hasattr(ScriptsScreen, "_import_dialog")
    assert hasattr(ScriptEditorScreen, "_run_now")
    assert hasattr(ScriptEditorScreen, "_undo")


def test_ui_helpers_does_not_import_base_screen():
    """game.base_screen imports game.ui_helpers at MODULE level. Any import of
    game.base_screen from inside game.ui_helpers — even a lazy one inside a
    function body — closes an import cycle. ast.walk sees function-local
    imports too, which is exactly how the old _diamond.py edge stayed hidden
    from the plain import smoke tests.
    """
    import ast
    import os
    import game.ui_helpers as u

    pkg_dir = os.path.dirname(u.__file__)
    offenders = []
    for fn in sorted(os.listdir(pkg_dir)):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(pkg_dir, fn)
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "game.base_screen":
                offenders.append(f"{fn}:{node.lineno}: from game.base_screen import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "game.base_screen":
                        offenders.append(f"{fn}:{node.lineno}: import game.base_screen")
    assert not offenders, (
        "game.ui_helpers must not import game.base_screen (import cycle):\n  "
        + "\n  ".join(offenders))


def test_needs_rebuild_is_shared_single_implementation():
    """BaseScreen._needs_rebuild must be the SAME object as the _layouts one —
    no copy-paste fork — and must stay a staticmethod so the ~5 existing
    `self._needs_rebuild(...)` call sites do not bind self into `obj`.
    """
    from game.base_screen import BaseScreen
    from game.ui_helpers._layouts import _needs_rebuild

    assert isinstance(BaseScreen.__dict__["_needs_rebuild"], staticmethod)
    assert BaseScreen._needs_rebuild is _needs_rebuild

    class _Holder:
        children = [object()]

    holder = _Holder()
    assert BaseScreen._needs_rebuild(holder, "_k", "a", require_children=True) is True
    assert BaseScreen._needs_rebuild(holder, "_k", "a", require_children=True) is False
    assert BaseScreen._needs_rebuild(holder, "_k", "b", require_children=True) is True


def test_importing_ui_helpers_does_not_pull_in_base_screen():
    """Transitive counterpart of the AST guard above, run in a fresh
    interpreter so no earlier test has primed sys.modules.

    The AST test only catches a ui_helpers file naming game.base_screen
    directly. An INDIRECT path — a ui_helpers submodule importing some
    game.screens.* module that in turn subclasses BaseScreen — would slip
    past it, and would resurface as `ImportError: cannot import name
    '_needs_rebuild' from partially initialized module 'game.ui_helpers'`
    on the module-level import in base_screen.py. That failure depends on
    which module the process imports first, so it can hide until Android.
    """
    import os
    import subprocess
    import sys

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, KIVY_NO_ARGS="1", KIVY_LOG_LEVEL="error")
    proc = subprocess.run(
        [sys.executable, "-c",
         "import game.ui_helpers, sys;"
         "print('DRAGGED_IN:' + str('game.base_screen' in sys.modules))"],
        cwd=root, env=env, capture_output=True, text=True)

    assert proc.returncode == 0, f"import failed:\n{proc.stderr}"
    assert "DRAGGED_IN:False" in proc.stdout, (
        "importing game.ui_helpers transitively imported game.base_screen, "
        "which recloses the base_screen <-> ui_helpers cycle.\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}")
