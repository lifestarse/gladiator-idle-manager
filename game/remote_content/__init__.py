# Build: 3
"""Remote content overlay — ship text and balance fixes without a Play release.

WHAT THIS IS NOT: a code updater. Nothing here downloads or executes Python.
Google Play forbids an app updating itself outside Play's own mechanism, and
the game's content is data-driven anyway, so patching JSON covers the cases
worth covering. Code changes ship through Play.

Two guarantees shape the whole design:

1. **Bundled content is always present and always valid.** A patch is an
   overlay on top of it, never a replacement. Every failure mode — offline,
   host down, malformed JSON, hostile JSON, a build too old for the patch —
   lands on the bundled file, which is exactly what ships in the APK today.

2. **A patch fetched now applies on the NEXT launch.** Startup reads only the
   local cache, so there is no network in the critical path, no difference
   between offline and online behaviour, and no screen being rebuilt underneath
   the player mid-session.

Guarantee 2 is what makes a bad patch survivable. See _cache.py for the
safe-mode marker: if a launch dies while patched, the next one throws the cache
away and comes up bundled. A fatal patch costs one launch instead of bricking
every install until a Play release clears review.

Wiring:
    game/localization.py       calls patch_language() as each file loads
    game/data_loader/_core.py  calls patch_gamedata() before the tier indexes
    game/app/_core.py          calls confirm_healthy() once the UI is up,
                               and sync_async() to warm the cache for next time
"""
from __future__ import annotations

import logging
import threading

from game.storage import user_data_dir

from . import _cache, _http, _manifest, _net, gamedata, languages, packs

_log = logging.getLogger(__name__)

# Single kill-switch, mirroring the ADS_ENABLED pattern: flip to False and the
# game behaves exactly as it did before this package existed.
REMOTE_CONTENT_ENABLED = True

# Same GitHub Pages site that already serves scripts-library.json and the
# privacy policy. Free CDN, no infrastructure, and publishing is a git push.
BASE_URL = "https://lifestarse.github.io/gladiator-idle-manager/content/"
MANIFEST_URL = BASE_URL + "manifest.json"

MANIFEST_CACHE = "manifest"
MANIFEST_TTL_S = 6 * 3600
MANIFEST_MAX_BYTES = 64 * 1024
# One language file is ~17 KB gzipped; a balance patch is far smaller. 1 MB is
# an order of magnitude of headroom and still a hard ceiling.
PATCH_MAX_BYTES = 1024 * 1024

_enabled = None
_lock = threading.Lock()


def _patching_allowed():
    """Decide once per process whether cached patches may be applied.

    Returns False — and leaves no trace on disk — when there is nothing cached,
    which is the case on every fresh install, every desktop dev run and every
    test. The marker dance only starts once there is actually a patch to apply.
    """
    global _enabled
    if _enabled is not None:
        return _enabled
    with _lock:
        if _enabled is not None:
            return _enabled
        _enabled = False
        if not REMOTE_CONTENT_ENABLED:
            return _enabled
        try:
            if _cache.crashed_while_patched():
                _cache.discard_all()
                _cache.clear_marker()
                _log.warning("[remote] previous launch died while patched — "
                             "running on bundled content")
                return _enabled
            if not _has_any_patch():
                return _enabled
            # Cannot raise the marker => cannot guarantee recovery => do not
            # apply. Failing closed is the whole point of the marker.
            _enabled = _cache.mark_applying()
        except Exception as exc:  # noqa: BLE001 - never break startup
            _log.warning("[remote] disabled after error during startup check: %s", exc)
            _enabled = False
    return _enabled


def _has_any_patch():
    prefix = _cache.CACHE_PREFIX
    skip = f"{prefix}{MANIFEST_CACHE}.json"
    try:
        return any(p.name != skip for p in user_data_dir().glob(f"{prefix}*.json"))
    except OSError:
        return False


def patch_language(lang_code, lang_data):
    """Overlay the cached patch for one language. Returns keys applied."""
    if not _patching_allowed():
        return 0
    try:
        patch = _cache.read(f"lang_{lang_code}")
        if not patch:
            return 0
        applied = languages.apply_patch(lang_data, patch)
        if applied:
            _log.info("[remote] %s: %d UI strings from cached patch", lang_code, applied)
        return applied
    except Exception as exc:  # noqa: BLE001 - a patch must never break loading
        _log.warning("[remote] language patch for %s failed: %s", lang_code, exc)
        return 0


def patch_gamedata(loader):
    """Overlay the cached balance patch. Returns field writes applied."""
    if not _patching_allowed():
        return 0
    try:
        patch = _cache.read("gamedata")
        if not patch:
            return 0
        applied = gamedata.apply_patch(loader, patch)
        if applied:
            _log.info("[remote] balance: %d fields from cached patch", applied)
        return applied
    except Exception as exc:  # noqa: BLE001 - a patch must never break loading
        _log.warning("[remote] balance patch failed: %s", exc)
        return 0


def confirm_healthy():
    """Called once the UI is up: this build survived the patch, keep it."""
    try:
        if _enabled:
            _cache.clear_marker()
    except Exception as exc:  # noqa: BLE001
        _log.warning("[remote] could not clear safe-mode marker: %s", exc)


# ------------------------------------------------------------- language packs

# Status values the picker renders. Kept as constants so the UI and the tests
# agree on the vocabulary.
BUNDLED = "bundled"              # ships in the APK, always usable
INSTALLED = "installed"          # downloaded and current
UPDATE_AVAILABLE = "update"      # downloaded, but a newer revision exists
NOT_INSTALLED = "not_installed"  # available to download
UNAVAILABLE = "unavailable"      # no pack published for this language


def _cached_manifest_entries():
    manifest = _cache.read(MANIFEST_CACHE)
    return _manifest.validate(manifest) if manifest else {}


def pack_status(lang, entries=None):
    """One of the status constants above, for the picker to render."""
    if lang in packs.BUNDLED_LANGS:
        return BUNDLED
    if entries is None:
        entries = _cached_manifest_entries()
    entry = entries.get(f"pack.{lang}")
    if packs.is_installed(lang):
        if entry and packs.installed_revision(lang) is not None \
                and entry["revision"] > packs.installed_revision(lang):
            return UPDATE_AVAILABLE
        return INSTALLED
    return NOT_INSTALLED if entry else UNAVAILABLE


def offered_languages():
    """[(display_name, code)] the picker should show, in display order.

    The APK's built-in list first, then any language the cached manifest
    publishes beyond it (a ``pack.*`` entry carrying a display ``name``) —
    which is how a brand-new language reaches installed clients without a
    Play release. Languages already installed on disk are included even when
    the manifest cache is gone (safe-mode wipe, offline first open), so the
    player can always see and re-select the language they are running.

    Codes come from _manifest.validate, which rejects anything that could
    steer a path — they end up as filenames in the packs directory.
    """
    offered = list(packs.OFFERED)
    known = {code for _name, code in offered}
    extras = {}
    for entry_name, entry in _cached_manifest_entries().items():
        if not entry_name.startswith("pack."):
            continue
        code = entry_name[len("pack."):]
        if code not in known:
            extras[code] = entry.get("name", code)
    for code in packs.installed_codes_on_disk():
        if code not in known:
            extras.setdefault(code, code)
    offered.extend((extras[code], code) for code in sorted(extras))
    return offered


def pack_statuses():
    """{lang: status} for every offered language, computed from one manifest read."""
    entries = _cached_manifest_entries()
    return {code: pack_status(code, entries) for _name, code in offered_languages()}


def refresh_manifest(force=False):
    """Fetch the index so pack_status() reflects the server. Blocking.

    Returns True if a manifest is available afterwards (fresh or cached).
    """
    if not REMOTE_CONTENT_ENABLED:
        return False
    if not force:
        cached = _cache.read(MANIFEST_CACHE, ttl_s=MANIFEST_TTL_S)
        if cached is not None:
            return True
    if not _net.is_online():
        _log.info("[remote] offline — keeping whatever manifest is cached")
        return _cache.read(MANIFEST_CACHE) is not None
    manifest = _http.fetch_json(MANIFEST_URL, max_bytes=MANIFEST_MAX_BYTES)
    if manifest is None:
        return _cache.read(MANIFEST_CACHE) is not None
    _cache.write(MANIFEST_CACHE, manifest)
    return True


def download_pack(lang, on_progress=None):
    """Fetch and install one language pack. Blocking — call off the UI thread.

    Applies immediately: the caller (the picker) is at a point where the UI is
    about to be rebuilt anyway, so there is nothing to mutate underneath.
    """
    if not REMOTE_CONTENT_ENABLED or lang in packs.BUNDLED_LANGS:
        return False
    refresh_manifest()
    entry = _cached_manifest_entries().get(f"pack.{lang}")
    if not entry:
        if on_progress:
            on_progress("unavailable", None)
        return False
    return packs.download(lang, BASE_URL, entry, on_progress=on_progress)


def sync(lang_code, force=False):
    """Fetch whatever is stale. Blocking — call from a worker thread.

    Writes to the cache only; nothing here touches live game state. Returns the
    list of entry names that were refreshed.
    """
    if not REMOTE_CONTENT_ENABLED:
        return []
    if not _net.is_online():
        _log.info("[remote] no network — update check skipped")
        return []
    if not refresh_manifest(force=force):
        return []
    entries = _cached_manifest_entries()
    refreshed = []

    # Bundled languages can only be patched — there is no pack to replace them.
    # Everything else is a pack, replaced wholesale when its revision moves;
    # one mechanism per language, so there is never a question of which
    # revision a patch sits on top of.
    for lang in packs.BUNDLED_LANGS:
        entry = entries.get(f"lang.{lang}")
        cache_name = f"lang_{lang}"
        if not entry or (not force and _cache.revision(cache_name) == entry["revision"]):
            continue
        payload = _http.fetch_json(BASE_URL + entry["path"], max_bytes=PATCH_MAX_BYTES)
        if isinstance(payload, dict):
            _cache.write(cache_name, payload, revision=entry["revision"])
            refreshed.append(f"lang.{lang}")

    # Only languages the player already downloaded. Pulling packs nobody
    # selected would spend their data on text they will never read. The
    # directory scan (not OFFERED) is what keeps manifest-only languages
    # updatable — they are installed without ever being in the APK's list.
    for lang in sorted(packs.installed_codes_on_disk() - set(packs.BUNDLED_LANGS)):
        entry = entries.get(f"pack.{lang}")
        if not entry:
            continue
        current = packs.installed_revision(lang)
        if force or current is None or current < entry["revision"]:
            if packs.download(lang, BASE_URL, entry):
                refreshed.append(f"pack.{lang}")
            continue
        # The pack is current, but its font may have changed upstream or
        # rotted on disk; ensure_font is a quiet no-op when all is well.
        packs.ensure_font(lang, BASE_URL, entry)

    entry = entries.get("gamedata")
    if entry and (force or _cache.revision("gamedata") != entry["revision"]):
        payload = _http.fetch_json(BASE_URL + entry["path"], max_bytes=PATCH_MAX_BYTES)
        if isinstance(payload, dict):
            # Validate before caching, not just before applying: a patch that
            # cannot survive validation should never occupy the cache slot that
            # would otherwise hold a good one.
            accepted, _rejected = gamedata.validate(payload)
            if accepted:
                _cache.write("gamedata", payload, revision=entry["revision"])
                refreshed.append("gamedata")
            else:
                _log.warning("[remote] balance patch rejected wholesale — not cached")

    if refreshed:
        _log.info("[remote] updated %s — applies on next launch", ", ".join(refreshed))
    return refreshed


def sync_async(lang_code):
    """Warm the cache on a daemon thread. Never blocks startup."""
    if not REMOTE_CONTENT_ENABLED:
        return None
    thread = threading.Thread(target=_sync_quietly, args=(lang_code,),
                              name="remote-content-sync", daemon=True)
    thread.start()
    return thread


def _sync_quietly(lang_code):
    try:
        sync(lang_code)
    except Exception as exc:  # noqa: BLE001 - a worker thread must not crash the app
        _log.warning("[remote] background sync failed: %s", exc)
