# Build: 35
"""Localization — loads translations from data/languages/*.json.

Each JSON file is a flat {key: value} dict for one language.
Fallback chain: current_lang → "en" → raw key.
To add a new language, drop a new JSON (e.g. data/languages/uk.json)
and list the code in SUPPORTED_LANGUAGES.
"""

import json
import logging
import os

_log = logging.getLogger(__name__)

_current_lang = "ru"

# What the player asked for, even when its pack is not on the device yet.
# set_language() falls back to "en" in that case; without this the fallback
# would masquerade as the player's choice — the pack-fetch prompt would never
# fire and the next save would overwrite the real preference with "en".
_requested_lang = None

# {lang_code: {key: translated_string}}
_LANG_DATA: dict[str, dict] = {}

SUPPORTED_LANGUAGES = ("ru", "en", "uk", "de", "es", "fr", "it", "pt", "pl")


def _languages_dir():
    """Return path to data/languages/ relative to project root."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "data", "languages")


def _language_dirs():
    """Where UI language files live, in resolution order.

    The bundled directory holds what shipped in the APK — only en.json now
    that the rest are downloadable packs. The packs directory holds what the
    player chose to download. Bundled wins on a name collision so English, the
    terminal fallback of t(), can never be shadowed by downloaded content.
    """
    dirs = [_languages_dir()]
    try:
        from game.remote_content.packs import packs_dir
        dirs.append(str(packs_dir()))
    except Exception as exc:  # noqa: BLE001 - bundled languages must still load
        _log.warning("Language packs directory unavailable: %s", exc)
    return dirs


def load_languages(force=False):
    """Load UI language files from the bundled directory and installed packs.

    Idempotent by default — each lang code is loaded at most once. The
    bottom of this module auto-loads on import (for tests), and main.py
    calls init_language() again on app build; without this guard every
    startup logged each language twice. Pass force=True to re-read from
    disk (dev hot-reload, and after a pack is installed at runtime).

    ``data_XX.json`` files are skipped on purpose. They are the game-data
    overlay consumed by data_loader.apply_translations(), not UI strings, and
    t() never reads them — loading them here parsed ~2 MB of JSON into
    _LANG_DATA on every startup for nothing. They now also sit in the packs
    directory next to the UI files, so skipping them by name is what keeps
    "data_uk" from being offered as a language.
    """
    seen_dir = False
    for lang_dir in _language_dirs():
        if not os.path.isdir(lang_dir):
            continue
        seen_dir = True
        for fname in sorted(os.listdir(lang_dir)):
            if not fname.endswith(".json") or fname.startswith("data_"):
                continue
            lang_code = fname[:-5]  # "ru.json" → "ru"
            if lang_code in _LANG_DATA and not force:
                continue
            path = os.path.join(lang_dir, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    _LANG_DATA[lang_code] = json.load(f)
                _log.info("Loaded language: %s (%d keys)", lang_code,
                          len(_LANG_DATA[lang_code]))
            except (json.JSONDecodeError, OSError) as exc:
                _log.error("Failed to load language %s: %s", lang_code, exc)
                continue
            # Overlay any cached remote patch on top. Imported lazily because
            # game.remote_content reads flatten()/set_path() from this module —
            # a top-level import would close the cycle. It is a no-op (and
            # touches no disk) when nothing is cached, which is every test run
            # and every fresh install.
            try:
                from game.remote_content import patch_language
                patch_language(lang_code, _LANG_DATA[lang_code])
            except Exception as exc:  # noqa: BLE001 - bundled text must still load
                _log.warning("Remote language overlay skipped for %s: %s",
                             lang_code, exc)
    if not seen_dir:
        _log.warning("No language directory found (looked in %s)", _language_dirs())


# ---- Nested-key addressing ----

# Two keys are not plain strings: ``enchant_names`` is a dict of effect names
# and ``help_sections`` is nine [title, body] pairs — the whole help screen.
# Addressing their leaves as "help_sections.4.1" lets translation tooling, the
# quality gate and remote patches all speak one flat vocabulary instead of each
# growing its own tree-walker.

def flatten(mapping):
    """Flatten a language mapping to {dotted_path: text} over string leaves."""
    flat = {}

    def walk(value, path):
        if isinstance(value, str):
            flat[path] = value
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}.{index}" if path else str(index))

    walk(mapping, "")
    return flat


def set_path(mapping, path, text):
    """Write a string leaf addressed by a dotted path, in place.

    Raises KeyError/IndexError/ValueError on a path that does not already
    resolve — callers validate against the bundled file first, so a miss here
    means the caller skipped that check.
    """
    parts = path.split(".")
    node = mapping
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = text
    else:
        node[last] = text


# ---- Public API (unchanged signatures) ----

def t(key, **kwargs):
    """Get localized string by key with format substitution."""
    # Try current language, then English fallback
    text = _LANG_DATA.get(_current_lang, {}).get(key)
    if text is None:
        text = _LANG_DATA.get("en", {}).get(key)
    if text is None:
        return key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def set_language(lang_code):
    """Set active language code, falling back to what is actually loaded.

    The fallback is English, not Russian: since language packs, English is the
    only language guaranteed to be in the APK, and it is already the terminal
    fallback of t(). Falling back to "ru" would set a code with no data behind
    it, leaving _current_lang pointing at nothing.

    The requested code is remembered either way — get_requested_language()
    is how the pack-fetch path and the save learn what the player actually
    chose when the fallback kicked in.
    """
    global _current_lang, _requested_lang
    _requested_lang = lang_code
    if lang_code in _LANG_DATA:
        _current_lang = lang_code
    else:
        _log.info("Language %r not loaded — falling back to en", lang_code)
        _current_lang = "en" if "en" in _LANG_DATA else lang_code


def get_language():
    return _current_lang


def get_requested_language():
    """The code last passed to set_language(), or the active one.

    Differs from get_language() only while the requested language's pack is
    absent from the device: get_language() answers "what can t() render",
    this answers "what did the player pick". The save writes this so an
    offline launch cannot erase the preference, and the startup pack-fetch
    reads it to know which pack to offer.
    """
    return _requested_lang or _current_lang


def get_available_languages():
    """Return list of loaded language codes."""
    return list(_LANG_DATA.keys())


def init_language():
    """Load language files. Current language is left at module default ("ru");
    a saved language code is applied later by engine.load() via set_language().
    """
    load_languages()
    _refresh_strings()


# ---- Backward compat: STRINGS dict (read-only, built from JSON) ----

def _build_strings_compat():
    """Build {key: {lang: value}} dict for any code still using STRINGS directly."""
    result = {}
    all_keys = set()
    for lang_data in _LANG_DATA.values():
        all_keys.update(lang_data.keys())
    for key in all_keys:
        entry = {}
        for lang_code, lang_data in _LANG_DATA.items():
            if key in lang_data:
                entry[lang_code] = lang_data[key]
        result[key] = entry
    return result


# STRINGS is populated after load_languages() is called (via init_language or data_loader)
STRINGS: dict = {}


def _refresh_strings():
    """Refresh the STRINGS compat dict after languages are loaded."""
    global STRINGS
    STRINGS = _build_strings_compat()


# Auto-load on import if JSON files exist (for tests that don't call init_language)
try:
    load_languages()
    _refresh_strings()
except Exception as exc:
    # Import-time best effort. Swallow to avoid blocking test collection, but
    # surface the reason so a missing / malformed language file is debuggable.
    _log.warning("localization auto-load failed: %s", exc)
