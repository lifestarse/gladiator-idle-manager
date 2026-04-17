# Build: 1
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
    import game.ui_helpers as u
    for name in [
        "build_roster_card", "build_forge_card", "build_item_info_card",
        "build_expedition_card", "build_shop_card", "build_unit_card",
        "build_fighter_pit_card", "build_achievement_card",
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
    # Check key methods survived the split
    assert hasattr(RosterScreen, "hire")
    assert hasattr(RosterScreen, "_show_perk_tree")
    assert hasattr(ForgeScreen, "buy")
    assert hasattr(ForgeScreen, "_show_enchant_view")
    assert hasattr(ForgeScreen, "_refresh_inventory_grid")
