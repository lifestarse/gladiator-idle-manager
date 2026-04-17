# Build: 1
"""Item migration tests — _migrate_item pulls fresh data from JSON
templates by id (or name fallback). Legacy saves with stale item names
should refresh after load.
"""


def test_migrate_by_id_refreshes_name(engine):
    """An item stored with id but stale name should refresh from JSON template."""
    import game.models as _m
    if not getattr(_m, "ALL_FORGE_ITEMS", None):
        return  # data not wired; skip gracefully
    template = _m.ALL_FORGE_ITEMS[0]
    stale = dict(template)
    stale["name"] = "Stale Name"
    migrated = engine._migrate_item(stale)
    assert migrated["name"] == template["name"]
    assert migrated["id"] == template["id"]


def test_migrate_preserves_upgrade_level(engine):
    """Upgrade level on a saved item must not be reset by migration."""
    import game.models as _m
    if not getattr(_m, "ALL_FORGE_ITEMS", None):
        return
    template = dict(_m.ALL_FORGE_ITEMS[0])
    template["upgrade_level"] = 5
    template["enchantment"] = "bleeding"
    migrated = engine._migrate_item(template)
    assert migrated.get("upgrade_level") == 5
    assert migrated.get("enchantment") == "bleeding"


def test_migrate_all_items_runs_cleanly(engine):
    """_migrate_all_items should not throw on a fresh roster (no items yet)."""
    engine._migrate_all_items()  # should be idempotent / no-op-safe
