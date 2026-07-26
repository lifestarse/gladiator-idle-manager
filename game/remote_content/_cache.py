# Build: 1
"""On-device cache for remote content, plus the safe-mode marker.

Patches fetched during a run are applied on the NEXT launch, never mid-session.
Startup therefore reads only this cache: no network in the critical path, the
same content offline as online, and no chance of a screen being rebuilt under a
half-applied patch while the player is looking at it.

The safe-mode marker is what makes that survivable. A bad patch published to
GitHub would otherwise reach every player at once and brick them, with a Play
release — hours of review — as the only remedy. Instead:

    startup: marker present?  -> last run died while patched, drop the cache
             else             -> write marker, apply patches
    UI built successfully     -> clear marker

so a fatal patch costs exactly one launch and then heals itself.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

_log = logging.getLogger(__name__)

# Kivy redirects HOME to the app's private storage on Android, so Path.home()
# is correct on both desktop and device without a platform branch — the same
# assumption the save file and the scripts-library cache already make.
CACHE_PREFIX = ".gladiator_content_"
MARKER_NAME = ".gladiator_content_applying"


def _path(name):
    return Path.home() / f"{CACHE_PREFIX}{name}.json"


def read(name, ttl_s=None):
    """Return a cached payload, or None if absent, unreadable or stale.

    ttl_s=None means "no expiry" — content caches are replaced by revision
    comparison against the manifest, not by age. The manifest itself passes a
    TTL so a dead upstream is retried rather than trusted forever.
    """
    path = _path(name)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            wrapper = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("[remote] unreadable cache %s: %s", path.name, exc)
        return None
    if not isinstance(wrapper, dict):
        return None
    if ttl_s is not None and time.time() - wrapper.get("_cached_at", 0) > ttl_s:
        return None
    return wrapper.get("payload")


def write(name, payload, revision=None):
    """Persist a payload. Silent on failure — the cache is an optimisation."""
    try:
        with open(_path(name), "w", encoding="utf-8") as handle:
            json.dump({"_cached_at": time.time(), "_revision": revision,
                       "payload": payload}, handle, ensure_ascii=False)
    except OSError as exc:
        _log.warning("[remote] failed to write cache %s: %s", name, exc)


def revision(name):
    """The revision stored alongside a cached payload, or None."""
    path = _path(name)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle).get("_revision")
    except (json.JSONDecodeError, OSError, AttributeError):
        return None


def discard_all():
    """Delete every cached patch. Used when the previous launch died patched."""
    dropped = 0
    try:
        for path in Path.home().glob(f"{CACHE_PREFIX}*.json"):
            try:
                path.unlink()
                dropped += 1
            except OSError:
                pass
    except OSError as exc:
        _log.warning("[remote] could not enumerate caches: %s", exc)
    if dropped:
        _log.warning("[remote] discarded %d cached patches after a bad launch", dropped)
    return dropped


def _marker():
    return Path.home() / MARKER_NAME


def crashed_while_patched():
    """True if the marker from the previous launch is still there."""
    return _marker().exists()


def mark_applying():
    """Raise the marker before touching game state with remote content."""
    try:
        _marker().write_text(str(time.time()), encoding="utf-8")
    except OSError as exc:
        # Cannot raise the marker => cannot guarantee recovery => the caller
        # treats this as "do not apply", which is the safe direction.
        _log.warning("[remote] could not write safe-mode marker: %s", exc)
        return False
    return True


def clear_marker():
    """Lower the marker once the app has reached a working UI."""
    try:
        _marker().unlink(missing_ok=True)
    except OSError as exc:
        _log.warning("[remote] could not clear safe-mode marker: %s", exc)
