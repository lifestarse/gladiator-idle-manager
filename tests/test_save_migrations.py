# Build: 2
"""Scaffold-level tests for the save-schema migration mechanism.

These exercise the register_migration helper and the _apply_save_data
migration loop without persisting anything — they mutate the migration
registry around a saved baseline so the real game isn't affected.
"""
import json
import os

import pytest


def _reset_migrations(backup):
    from game.engine import _shared as sh
    sh._SAVE_MIGRATIONS.clear()
    sh._SAVE_MIGRATIONS.update(backup)


@pytest.fixture
def migration_sandbox():
    """Snapshot and restore _SAVE_MIGRATIONS + CURRENT_SAVE_VERSION so tests
    can register bogus migrations without leaking to other tests."""
    from game.engine import _shared as sh
    backup = dict(sh._SAVE_MIGRATIONS)
    orig_current = sh.CURRENT_SAVE_VERSION
    try:
        yield sh
    finally:
        _reset_migrations(backup)
        sh.CURRENT_SAVE_VERSION = orig_current


def test_save_writes_current_schema_version(engine):
    engine.save()
    with open(engine.SAVE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    from game.engine._shared import CURRENT_SAVE_VERSION
    assert data["schema_version"] == CURRENT_SAVE_VERSION


def test_register_migration_rejects_duplicate(migration_sandbox):
    from game.engine._shared import register_migration

    @register_migration(0)
    def _m0(d): return d

    with pytest.raises(ValueError, match="already registered"):
        @register_migration(0)
        def _m0_again(d): return d


def test_register_migration_rejects_stale_version(migration_sandbox):
    from game.engine._shared import register_migration
    # from_version == CURRENT_SAVE_VERSION means the migration would never
    # run — register_migration must refuse it. Read the current version off
    # the module instead of hardcoding it, so a schema bump doesn't silently
    # turn this into an "already registered" failure.
    with pytest.raises(ValueError, match="bump CURRENT_SAVE_VERSION"):
        @register_migration(migration_sandbox.CURRENT_SAVE_VERSION)
        def _m(d): return d


def test_register_migration_rejects_negative(migration_sandbox):
    from game.engine._shared import register_migration
    with pytest.raises(ValueError, match="non-negative"):
        @register_migration(-1)
        def _m(d): return d


def test_v0_migration_runs_on_legacy_save(migration_sandbox, engine):
    """A v0 save (no schema_version) goes through the registered migration."""
    from game.engine._shared import register_migration

    @register_migration(0)
    def _v0_to_v1(data):
        data["_migrated_0"] = True
        return data

    # Build a real save, then drop schema_version to simulate a pre-versioning
    # (v0) file on disk.
    engine.save()
    with open(engine.SAVE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.pop("schema_version", None)

    engine._apply_save_data(data)
    assert data.get("_migrated_0") is True


def test_v1_to_v2_strips_battle_end_events(engine):
    """The real v1→v2 migration: drop the retired duplicate battle event.

    Players who fought before the fix carry up to 200 event-log entries,
    half of them "battle_end" — an event type with no evt_* key, so it
    rendered as a raw key plus a dict dump in the log.
    """
    engine.save()
    with open(engine.SAVE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["schema_version"] = 1
    data["event_log"] = [
        {"t": 1784943830, "type": "battle", "result": "victory", "tier": 1},
        {"t": 1784943830, "type": "battle_end", "result": "victory",
         "tier": 1, "skipped": []},
        {"t": 1784943831, "type": "hire", "name": "Maximus"},
    ]

    engine._apply_save_data(data)

    types = [e["type"] for e in engine.event_log]
    assert types == ["battle", "hire"]


def test_future_save_version_warns_but_loads(migration_sandbox, engine, caplog):
    """A save from a 'future' client loads with defaults and logs a warning."""
    import logging
    engine.save()
    with open(engine.SAVE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["schema_version"] = 999

    with caplog.at_level(logging.WARNING, logger="game.engine.persistencereadmixin"):
        engine._apply_save_data(data)
    assert any("newer than supported" in rec.message for rec in caplog.records)
