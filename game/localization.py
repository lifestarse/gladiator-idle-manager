# Build: 30
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

# {lang_code: {key: translated_string}}
_LANG_DATA: dict[str, dict] = {}

SUPPORTED_LANGUAGES = ("ru", "en")


def _languages_dir():
    """Return path to data/languages/ relative to project root."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "data", "languages")


def load_languages(force=False):
    """Load all JSON language files from data/languages/.

    Idempotent by default — each lang code is loaded at most once. The
    bottom of this module auto-loads on import (for tests), and main.py
    calls init_language() again on app build; without this guard every
    startup logged each language twice. Pass force=True to re-read from
    disk (dev hot-reload).
    """
    lang_dir = _languages_dir()
    if not os.path.isdir(lang_dir):
        _log.warning("Languages directory not found: %s", lang_dir)
        return
    for fname in os.listdir(lang_dir):
        if not fname.endswith(".json"):
            continue
        lang_code = fname[:-5]  # "ru.json" → "ru"
        if lang_code in _LANG_DATA and not force:
            continue
        path = os.path.join(lang_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                _LANG_DATA[lang_code] = json.load(f)
            _log.info("Loaded language: %s (%d keys)", lang_code, len(_LANG_DATA[lang_code]))
        except (json.JSONDecodeError, OSError) as exc:
            _log.error("Failed to load language %s: %s", lang_code, exc)


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
    """Set active language code."""
    global _current_lang
    _current_lang = lang_code if lang_code in _LANG_DATA else "ru"


def get_language():
    return _current_lang


def get_available_languages():
    """Return list of loaded language codes."""
    return list(_LANG_DATA.keys())


def init_language():
    """Load language files and set default. User choice is restored from save."""
    global _current_lang
    load_languages()
    _refresh_strings()
    _current_lang = "en"


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
except Exception:
    pass
