# Build: 1
"""The remote index: what patches exist, at which revision, for which builds.

One small document (a couple of KB) fetched first, so the client can decide
what it actually needs before downloading anything. A player on Ukrainian pulls
the Ukrainian patch and nothing else.

Shape::

    {
      "schema": 1,
      "generated_at": "2026-07-26T12:00:00Z",
      "entries": {
        "lang.uk":  {"path": "uk.v3.json",   "revision": 3, "min_app": "1.9.44"},
        "gamedata": {"path": "balance.v2.json", "revision": 2, "min_app": "1.9.45"}
      }
    }

``path`` is relative to BASE_URL so the host can move without a client release.
``min_app`` / ``max_app`` are optional and gate on game/version.py — a balance
patch written against a new formula must not land on a build that still has the
old one.
"""
from __future__ import annotations

import logging

from game.version import version_tuple, APP_VERSION

_log = logging.getLogger(__name__)

SCHEMA = 1
MAX_ENTRIES = 64


def validate(data):
    """Return {name: entry} for well-formed, applicable entries, or {}."""
    if not isinstance(data, dict):
        _log.warning("[remote] manifest is not an object")
        return {}
    if data.get("schema") != SCHEMA:
        # A newer schema means this client cannot be trusted to read it.
        # Ignoring it is correct: the bundled content is always valid.
        _log.info("[remote] manifest schema %r != %d — ignoring",
                  data.get("schema"), SCHEMA)
        return {}
    entries = data.get("entries")
    if not isinstance(entries, dict) or len(entries) > MAX_ENTRIES:
        _log.warning("[remote] manifest has no usable entries block")
        return {}

    usable = {}
    for name, entry in entries.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        path = entry.get("path")
        revision = entry.get("revision")
        if not isinstance(path, str) or not path:
            continue
        if not isinstance(revision, int) or isinstance(revision, bool):
            continue
        # A path that tries to climb out of the content directory is either a
        # mistake or an attack; either way it does not get fetched.
        if path.startswith(("/", "http://", "https://")) or ".." in path:
            _log.warning("[remote] entry %s has a suspicious path %r", name, path)
            continue
        if not _applies_to_this_build(entry):
            continue
        usable[name] = {"path": path, "revision": revision}
    return usable


def _applies_to_this_build(entry):
    minimum, maximum = entry.get("min_app"), entry.get("max_app")
    this = version_tuple()
    if minimum is not None:
        bound = version_tuple(minimum)
        # An unparseable bound yields () which would compare as "no floor";
        # treat it as "do not apply" instead.
        if not bound or this < bound:
            return False
    if maximum is not None:
        bound = version_tuple(maximum)
        if not bound or this > bound:
            return False
    return True


def describe():
    return f"app {APP_VERSION}, manifest schema {SCHEMA}"
