# Build: 1
"""Save-file recovery: candidate fallback (.tmp/.bak) + corrupt quarantine.

Why candidates exist: _write_save_to_disk writes ".tmp", refreshes ".bak",
then atomically publishes via os.replace(tmp, primary). Historic builds
MOVED the primary to ".bak" before that final replace, so a process killed
between the two steps left NO primary on disk — while a complete, newer
save sat in ".tmp" and the previous good one in ".bak". load() used to
treat "no primary" as a fresh install and silently reset the player to
zero. These helpers make load() recover instead of wiping progress.

Candidate order (first parseable JSON object wins):
  1. primary          — the normal case.
  2. primary + .tmp   — a fully-written save whose final os.replace never
                        ran; when the primary is missing this is the NEWEST
                        data on disk. A half-written .tmp fails the JSON
                        parse and falls through harmlessly.
  3. primary + .bak   — the previous rotation's backup.

Plain functions (not a mixin): they need only a path, and keeping them out
of persistencereadmixin keeps that module within the 10 KB file budget.
"""
import json
import logging
import os

_log = logging.getLogger(__name__)

_CANDIDATE_SUFFIXES = ("", ".tmp", ".bak")


def try_read_save(path):
    """Parse one candidate save file.

    Returns the parsed dict, or None when the file is absent, unreadable,
    or not a JSON object (a corrupt-but-valid JSON scalar/list must not
    reach _apply_save_data).
    """
    if not os.path.exists(path):
        return None
    try:
        # encoding='utf-8' is REQUIRED on Windows: the locale default
        # (cp1252) raises UnicodeDecodeError on any save containing
        # non-Latin-1 bytes — e.g. a script-program name in Russian.
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except (OSError, ValueError) as exc:
        # ValueError covers json.JSONDecodeError and UnicodeDecodeError.
        _log.warning("[ENGINE] unreadable save candidate %s: %s", path, exc)
        return None
    if not isinstance(loaded, dict):
        _log.warning("[ENGINE] save candidate %s is not a JSON object", path)
        return None
    return loaded


def quarantine_primary(save_path):
    """Move an unreadable primary save aside to ".corrupt".

    The file is kept (support/manual recovery) instead of deleted, and the
    move stops the next backup rotation from overwriting a good ".bak"
    with garbage. Returns True when the primary no longer blocks saving
    (moved away, or was already absent); False when the broken file is
    still sitting at save_path and the engine must not overwrite it.
    """
    try:
        if os.path.exists(save_path):
            corrupt_path = save_path + ".corrupt"
            if os.path.exists(corrupt_path):
                os.remove(corrupt_path)
            os.rename(save_path, corrupt_path)
            _log.warning("[ENGINE] Unreadable save moved to %s", corrupt_path)
        return True
    except OSError as exc:
        _log.warning("[ENGINE] Could not quarantine unreadable save: %s", exc)
        return False


def read_save_with_fallback(save_path):
    """Locate the freshest readable save state for save_path.

    Returns (data, is_first_launch, load_failed):
      data            — parsed save dict, or None when nothing usable exists.
      is_first_launch — True only when NO candidate file exists at all
                        (brand-new install; drives the language picker).
      load_failed     — True when an unreadable primary is still present at
                        save_path (quarantine failed); save() must stay
                        blocked so it can't overwrite the player's file.
    """
    exists = {s: os.path.exists(save_path + s) for s in _CANDIDATE_SUFFIXES}
    if not any(exists.values()):
        return None, True, False
    for suffix in _CANDIDATE_SUFFIXES:
        data = try_read_save(save_path + suffix)
        if data is None:
            continue
        if suffix:
            _log.warning(
                "[ENGINE] primary save unusable — recovered from '%s'", suffix)
            if exists[""]:
                # Primary exists but did not parse: move it aside NOW so
                # the next save's rotation can't clobber the good backup
                # we just recovered from.
                quarantine_primary(save_path)
        return data, False, False
    # Every present candidate is unreadable → fresh start, but only if the
    # broken primary is safely out of the way.
    load_failed = not quarantine_primary(save_path) if exists[""] else False
    return None, False, load_failed
