# Build: 1
"""Online community scripts library — fetch + 24-hour local cache.

This is the Tier-1 implementation discussed in design notes: a single
JSON manifest hosted on GitHub Pages, fetched over HTTPS, parsed into
the same ``Program.from_dict`` flow that powers Import. No server, no
auth, no user-publishing-from-game — submissions arrive via PR to the
``docs/scripts-library.json`` file in the project repo.

Why this shape:
  * Zero infrastructure cost — GitHub's raw-pages CDN is free and fast.
  * Moderation is just code review (PRs).
  * Any failure mode (offline, repo down, malformed JSON) is invisible
    to the user — the game falls through to bundled templates.
  * Scripts execute through the existing AST sandbox: arbitrary remote
    JSON can't run code, only construct AST nodes from a known whitelist,
    so even a malicious manifest only wastes the user's gold at worst.

Public API:
    DEFAULT_MANIFEST_URL  — the project's official manifest URL.
    fetch_remote(url, timeout)
    load_cached()
    save_cached(payload)
    get_library(force_refresh=False)

The cache file sits next to the save (~/.gladiator_scripts_library_cache.json)
so it survives across game runs but never leaves the user's device.
"""
from __future__ import annotations
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


# Update this when you move the manifest. The .lifestarse.github.io path
# matches the existing privacy-policy GitHub Pages site (see
# project_gladiator notes — privacy-policy.html is already served from
# the same docs/ folder).
DEFAULT_MANIFEST_URL = (
    "https://lifestarse.github.io/gladiator-idle-manager/scripts-library.json"
)

# 24 hours — fresh enough for daily updates but rare enough that we don't
# pound github.io on every screen open. The user can also force-refresh
# from the UI's "Reload" button.
CACHE_TTL_S = 24 * 3600

# Fetch timeout. Short so a broken DNS doesn't freeze the loading UI
# even though we already fetch on a worker thread — the thread will
# still resolve in this many seconds tops.
HTTP_TIMEOUT_S = 5.0


def _cache_path() -> Path:
    """Cache file lives next to the save, in the user's home directory.

    On Android Kivy redirects HOME to the app's private storage, so we
    don't need a special branch for the platform — Path.home() does the
    right thing in both desktop and APK contexts.
    """
    return Path.home() / ".gladiator_scripts_library_cache.json"


def load_cached() -> dict | None:
    """Return the cached payload IFF it exists and is younger than
    CACHE_TTL_S. Stale entries return None so the next fetch_remote()
    call will replace them.
    """
    p = _cache_path()
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            wrapper = json.load(f)
        ts = wrapper.get("_cached_at", 0)
        if time.time() - ts > CACHE_TTL_S:
            return None
        payload = wrapper.get("payload")
        if not isinstance(payload, dict):
            return None
        return payload
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("[online_library] failed to read cache: %s", exc)
        return None


def save_cached(payload: dict) -> None:
    """Persist payload with a fresh timestamp. Silent on failure — cache
    is purely a perf optimisation, not load-bearing."""
    try:
        with open(_cache_path(), "w", encoding="utf-8") as f:
            json.dump({"_cached_at": time.time(), "payload": payload},
                      f, ensure_ascii=True)
    except OSError as exc:
        _log.warning("[online_library] failed to write cache: %s", exc)


def _validate_manifest(data: Any) -> dict | None:
    """Shallow schema check. Manifest must be a dict with a ``scripts``
    list of dicts each having an ``id`` and a ``program`` blob. Anything
    else is rejected so a corrupted upstream file can't crash the UI.

    We intentionally DON'T validate ``program`` here — that's the
    Program.from_dict path's job, which the picker already runs through
    a try/except. Better to surface "couldn't import this one entry"
    than to drop the entire manifest on one bad row.
    """
    if not isinstance(data, dict):
        return None
    scripts = data.get("scripts")
    if not isinstance(scripts, list):
        return None
    cleaned = []
    for entry in scripts:
        if not isinstance(entry, dict):
            continue
        if "id" not in entry or "program" not in entry:
            continue
        cleaned.append(entry)
    if not cleaned:
        return None
    return {**data, "scripts": cleaned}


def fetch_remote(
    url: str = DEFAULT_MANIFEST_URL,
    timeout: float = HTTP_TIMEOUT_S,
) -> dict | None:
    """Fetch + validate + cache. Returns the validated payload or None.

    Called from a worker thread (UI doesn't freeze on the timeout); the
    HTTPS handshake to github.io is fast in practice (~100-300ms) but we
    cap the worst case at HTTP_TIMEOUT_S to keep the loading dialog from
    sitting forever on a flaky network.
    """
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "gladiator-idle-manager/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            json.JSONDecodeError, OSError, ValueError) as exc:
        _log.info("[online_library] fetch failed (%s): %s",
                  type(exc).__name__, exc)
        return None
    payload = _validate_manifest(data)
    if payload is None:
        _log.warning("[online_library] manifest failed validation: %r",
                     str(data)[:200])
        return None
    save_cached(payload)
    return payload


def get_library(force_refresh: bool = False) -> dict | None:
    """The one-call entry point for UI code.

    Order: fresh cache → remote fetch → None. ``force_refresh=True``
    skips the cache so the user's "Reload" button always hits the network.
    """
    if not force_refresh:
        cached = load_cached()
        if cached is not None:
            return cached
    return fetch_remote()
