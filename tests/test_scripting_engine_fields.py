# Build: 1
"""Engine-field registry tests against a real GameEngine.

``BUILTIN_ENGINE_FIELDS`` maps the script language's field names onto engine
state. The two vocabularies do not match one-to-one (``victories`` reads
``engine.total_wins``, ``current_tier`` reads ``engine.arena_tier``), so a
mistyped attribute name is invisible at runtime: the accessor's fallback value
is returned instead, forever, in every script, with no exception, no entry in
``last_errors`` and no log line. The player's ``engine.<field> > N`` condition
just never fires and looks like an honest zero.

That is not hypothetical — 611a3cc had to repair exactly ``victories``,
``current_tier`` and ``expedition_active`` after they shipped "always reading
0 in scripts". These tests are the guard for that class of defect: every
attribute the registry claims to read must exist on a real ``GameEngine``, not
on a stub that was written to match the registry.

The parallel gate for actions is ``tests/test_scripting_actions_e2e.py``.
"""
from __future__ import annotations

import pytest

from game.scripting.builtins import BUILTIN_ENGINE_FIELDS
from game.scripting import labels as L


# Fields whose value is not sourced from engine state at all. Membership here
# is a deliberate exemption from the attribute check below, so adding a field
# to the registry cannot dodge the gate by accident.
FIELDS_WITHOUT_ENGINE_STATE = frozenset({"current_floor"})


@pytest.fixture
def live_engine(tmp_path):
    """Real GameEngine on a tempfile save, loaded to its starting state."""
    import os
    os.environ.setdefault("KIVY_NO_ARGS", "1")
    os.environ.setdefault("KIVY_LOG_LEVEL", "error")
    from game.engine import GameEngine
    e = GameEngine(save_path=str(tmp_path / "save.json"))
    e.load()
    return e


@pytest.mark.parametrize("field", sorted(BUILTIN_ENGINE_FIELDS))
def test_engine_field_reads_a_real_engine_attribute(field, live_engine):
    """The attribute each accessor names must exist on the real engine.

    Without this, ``_engine_attr("victoryes", 0)`` is a silent constant.
    """
    accessor = BUILTIN_ENGINE_FIELDS[field]
    attr = getattr(accessor, "engine_attr", None)
    if attr is None:
        assert field in FIELDS_WITHOUT_ENGINE_STATE, (
            f"engine field {field!r} reads no engine attribute and is not "
            f"listed in FIELDS_WITHOUT_ENGINE_STATE — if it really is a "
            f"constant, say so there; otherwise build it with _engine_attr "
            f"so this gate can check it"
        )
        return
    assert hasattr(live_engine, attr), (
        f"engine field {field!r} reads engine.{attr}, which does not exist on "
        f"GameEngine — every script using it silently gets the fallback value"
    )


@pytest.mark.parametrize("field", sorted(BUILTIN_ENGINE_FIELDS))
def test_engine_field_resolves_against_live_engine(field, live_engine):
    """Every accessor runs cleanly on a real engine and yields a usable type."""
    value = BUILTIN_ENGINE_FIELDS[field](live_engine)
    if field in L.BOOLEAN_ENGINE_FIELDS:
        assert isinstance(value, bool), (
            f"engine field {field!r} is declared boolean but returned "
            f"{type(value).__name__}"
        )
    else:
        assert isinstance(value, (int, float)) and not isinstance(value, bool), (
            f"engine field {field!r} is declared numeric but returned "
            f"{type(value).__name__}"
        )


def test_registry_is_the_only_source_of_engine_field_names():
    """labels.py must not grow a hand-maintained copy of the registry."""
    assert set(L.ENGINE_FIELD_LABELS) == set(BUILTIN_ENGINE_FIELDS)
    assert L.BOOLEAN_ENGINE_FIELDS <= set(BUILTIN_ENGINE_FIELDS)
    assert L.NUMERIC_ENGINE_FIELDS == set(BUILTIN_ENGINE_FIELDS) - L.BOOLEAN_ENGINE_FIELDS


def test_aliased_fields_track_engine_state(live_engine):
    """The three fields 611a3cc had to repair read live engine state.

    Pinned by name because they are the ones whose script name differs from
    the engine attribute — the exact shape that read 0 forever.
    """
    live_engine.total_wins = 7
    live_engine.arena_tier = 4
    assert BUILTIN_ENGINE_FIELDS["victories"](live_engine) == 7
    assert BUILTIN_ENGINE_FIELDS["current_tier"](live_engine) == 4

    assert BUILTIN_ENGINE_FIELDS["expedition_active"](live_engine) is False
    assert live_engine.fighters, "engine loaded with no fighters to send away"
    live_engine.fighters[0].on_expedition = True
    assert BUILTIN_ENGINE_FIELDS["expedition_active"](live_engine) is True


def test_unknown_engine_field_is_not_readable():
    """A name outside the registry has no accessor at all."""
    assert BUILTIN_ENGINE_FIELDS.get("no_such_engine_field") is None
