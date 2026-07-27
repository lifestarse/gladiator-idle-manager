# Build: 3
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
        "gamedata": {"path": "balance.v2.json", "revision": 2, "min_app": "1.9.45"},
        "pack.tr":  {"path": "packs/tr.v1.json", "revision": 1, "name": "Türkçe",
                     "font": {"path": "fonts/NotoSans-tr.ttf",
                              "sha256": "…64 hex…", "bytes": 412345}}
      }
    }

``path`` is relative to BASE_URL so the host can move without a client release.
``min_app`` / ``max_app`` are optional and gate on game/version.py — a balance
patch written against a new formula must not land on a build that still has the
old one.

``name`` (optional, pack.* entries) is the picker display name for a language
that is not in the APK's built-in OFFERED list — it is what lets a brand-new
language appear on installed clients without a Play release.

``font`` (optional, pack.* entries) declares a font the language needs because
the bundled fonts do not cover its script. The pack is unusable without it, so
a malformed font block invalidates the whole entry rather than silently
shipping a language that would render as tofu.
"""
from __future__ import annotations

import logging

from game.version import version_tuple, APP_VERSION

_log = logging.getLogger(__name__)

SCHEMA = 1
MAX_ENTRIES = 64
MAX_NAME_CHARS = 40
SHA256_HEX_CHARS = 64
# A language code becomes a filename (``<code>.json``, ``data_<code>.json``)
# under the packs directory. Since the picker's language list now comes from
# the manifest, that code is remote input, so it is restricted to what a real
# BCP-47-ish code needs and nothing that can steer a path.
LANG_CODE_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
MAX_LANG_CODE_CHARS = 16


def _suspicious_path(path):
    """A path that tries to climb out of the content directory is either a
    mistake or an attack; either way it does not get fetched."""
    return path.startswith(("/", "http://", "https://")) or ".." in path


def valid_lang_code(code):
    """True for a code that is safe to use as a filename component."""
    return (isinstance(code, str) and 0 < len(code) <= MAX_LANG_CODE_CHARS
            and all(char in LANG_CODE_CHARS for char in code))


def _basename(path):
    """Filename part of a manifest path, or "" when the path names a directory.

    Both separators count: os.path.basename is platform-dependent — on POSIX
    it keeps "a\\b" whole, so a Windows-style separator in remote input would
    pass a check that ran on the device and bite on a desktop build. A
    trailing separator yields "" on purpose; "fonts/" is a directory, and
    treating it as the file "fonts" is how the empty-basename bug worked.
    """
    return path.replace("\\", "/").rpartition("/")[2]


def _valid_font(entry_name, font):
    """Return a cleaned {"path", "sha256"[, "bytes"]} dict, or None.

    sha256 is mandatory: the file goes to a native font renderer, so an
    unverifiable download is not worth having.
    """
    if not isinstance(font, dict):
        _log.warning("[remote] entry %s has a malformed font block", entry_name)
        return None
    path, digest = font.get("path"), font.get("sha256")
    # The basename must survive as a real filename: "fonts/" passes the
    # traversal check but basenames to "", which would resolve back to the
    # fonts directory itself and install a pack with no usable font.
    if not isinstance(path, str) or not path or _suspicious_path(path) \
            or not _basename(path):
        _log.warning("[remote] entry %s has a suspicious font path %r",
                     entry_name, path)
        return None
    if not isinstance(digest, str) or len(digest) != SHA256_HEX_CHARS \
            or any(c not in "0123456789abcdefABCDEF" for c in digest):
        _log.warning("[remote] entry %s has an invalid font sha256", entry_name)
        return None
    cleaned = {"path": path, "sha256": digest.lower()}
    size = font.get("bytes")
    if isinstance(size, int) and not isinstance(size, bool) and size > 0:
        cleaned["bytes"] = size
    return cleaned


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
        # The suffix of a lang.*/pack.* name IS a language code, and a language
        # code becomes a filename on the device. Reject anything that could
        # steer a path before the name reaches the rest of the client.
        prefix, sep, code = name.partition(".")
        if prefix in ("lang", "pack") and (not sep or not valid_lang_code(code)):
            _log.warning("[remote] entry %r has an unusable language code", name)
            continue
        path = entry.get("path")
        revision = entry.get("revision")
        if not isinstance(path, str) or not path:
            continue
        if not isinstance(revision, int) or isinstance(revision, bool):
            continue
        if _suspicious_path(path):
            _log.warning("[remote] entry %s has a suspicious path %r", name, path)
            continue
        if not _applies_to_this_build(entry):
            continue
        cleaned = {"path": path, "revision": revision}
        font = entry.get("font")
        if font is not None:
            cleaned_font = _valid_font(name, font)
            if cleaned_font is None:
                # The language needs this font to render; without a valid font
                # block the whole entry is unusable, not just incomplete.
                continue
            cleaned["font"] = cleaned_font
        label = entry.get("name")
        if isinstance(label, str) and 0 < len(label.strip()) <= MAX_NAME_CHARS:
            cleaned["name"] = label.strip()
        usable[name] = cleaned
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
