# Build: 1
"""Validate and apply a remote UI-string patch.

A language file drives every screen, so a bad patch is not a cosmetic problem —
one malformed value reaches every player at once. The validator below is the
runtime twin of tests/test_i18n_ui_quality.py: same rules, enforced against the
BUNDLED file rather than against a checked-in expectation.

The single most important rule is that a patch may only OVERWRITE keys that
already ship in the APK. It can never add or remove one. That makes the patch a
pure overlay and gives compatibility in both directions for free: an old patch
on a new build simply leaves the new keys bundled, and a new patch on an old
build has its unknown keys dropped.
"""
from __future__ import annotations

import logging
import re

_log = logging.getLogger(__name__)

# flatten/set_path are imported inside the functions, not at module scope.
# game.localization auto-loads every language file when it is first imported,
# and that load calls back into this package — a module-level import here would
# close the cycle and leave whichever module imported second half-built.


def _shape():
    from game.localization import flatten, set_path
    return flatten, set_path

PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]*\}")
BBCODE = re.compile(r"\[/?[a-z]+(?:=[^\]]+)?\]")

# A UI string that is 4x the bundled one either overflows its widget or is not
# a translation of it. LENGTH_FLOOR keeps the ratio from being absurd on short
# strings — "OK" legitimately becomes "Гаразд" — without leaving them
# unbounded: a 5-character label may reach 40 characters, not 4000.
MAX_LENGTH_RATIO = 4.0
LENGTH_FLOOR = 40
MAX_VALUE_CHARS = 4000
# The whole file is 856 leaves; a patch claiming far more is not describing
# this game.
MAX_ENTRIES = 2000


def validate(patch, bundled):
    """Return (accepted, rejected) — {path: text} and {path: reason}.

    Rejection is per key, not per file: one bad string must not cost the player
    the other eight hundred good ones.
    """
    accepted, rejected = {}, {}
    if not isinstance(patch, dict):
        return {}, {"<patch>": "not a JSON object"}
    if len(patch) > MAX_ENTRIES:
        return {}, {"<patch>": f"{len(patch)} entries exceeds {MAX_ENTRIES}"}

    flatten, _set_path = _shape()
    base = flatten(bundled)
    for path, text in patch.items():
        reason = _reject_reason(path, text, base)
        if reason:
            rejected[path] = reason
        else:
            accepted[path] = text
    return accepted, rejected


def _reject_reason(path, text, base):
    if not isinstance(path, str) or not isinstance(text, str):
        return "key and value must both be strings"
    if path not in base:
        return "not a key of the bundled language file"
    if not text.strip():
        return "empty"
    if len(text) > MAX_VALUE_CHARS:
        return f"{len(text)} chars exceeds {MAX_VALUE_CHARS}"
    original = base[path]
    allowed = max(len(original) * MAX_LENGTH_RATIO, LENGTH_FLOOR)
    if len(text) > allowed:
        return (f"{len(text)} chars exceeds {allowed:.0f} "
                f"(bundled string is {len(original)})")
    if sorted(PLACEHOLDER.findall(text)) != sorted(PLACEHOLDER.findall(original)):
        # A dropped or renamed placeholder is a KeyError the moment the string
        # is formatted, i.e. a crash in whichever screen uses it.
        return "placeholders differ from the bundled string"
    if sorted(BBCODE.findall(text)) != sorted(BBCODE.findall(original)):
        # Kivy renders a broken markup tag literally, as visible garbage.
        return "BBCode markup differs from the bundled string"
    return None


def apply_patch(lang_data, patch):
    """Overlay a validated patch onto one language's in-memory mapping.

    Returns the number of keys applied. lang_data is mutated in place because
    localization._LANG_DATA hands out references to it.
    """
    _flatten, set_path = _shape()
    accepted, rejected = validate(patch, lang_data)
    for path, text in list(accepted.items()):
        try:
            set_path(lang_data, path, text)
        except (KeyError, IndexError, ValueError) as exc:
            # validate() proved the path resolves, so this means the bundled
            # structure changed underneath us. Skip the key, keep the rest.
            rejected[path] = f"could not write: {exc}"
            del accepted[path]
    if rejected:
        sample = list(rejected.items())[:3]
        _log.warning("[remote] language patch: %d keys rejected, e.g. %s",
                     len(rejected), sample)
    return len(accepted)
