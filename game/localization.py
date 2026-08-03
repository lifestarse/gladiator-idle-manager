# Build: 37
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

# English, matching the terminal fallback of t(): it is the only language
# guaranteed to be in the APK, and until engine.load() applies a saved code
# (it returns early when there is no save at all) this is what the UI renders.
# Any other default makes the language picker advertise a language the player
# is not looking at.
_current_lang = "en"

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


def _project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# The files the two global font aliases point at when no downloaded
# per-language font overrides them. Single source of truth: game/app/_shared.py
# registers straight from this dict at import, set_language() re-registers from
# it on every switch back to a covered language, and
# tests/test_font_glyph_coverage.py gates the translation set against the cmap
# of the file named here. A font swap edited here reaches all three.
_BUNDLED_FONT_FILES = {
    "PixelFont": os.path.join(_project_root(), "fonts", "PressStart2P-Regular.ttf"),
    "BodyFont": os.path.join(_project_root(), "fonts", "DroidSans.ttf"),
}

# Every alias the whole UI renders through, and so every alias a per-language
# font override has to cover.
_FONT_ALIASES = tuple(_BUNDLED_FONT_FILES)


def _register_fonts(mapping):
    """Point Kivy's font aliases at files. No-op headless (tests, tools).

    Kivy is imported lazily and only here: importing it parses sys.argv, which
    would break the headless CLI tools that import this module.
    """
    try:
        from kivy.core.text import LabelBase
    except ImportError:
        return
    for alias, path in mapping.items():
        if not os.path.exists(path):
            _log.warning("Font file missing, alias %s left as-is: %s", alias, path)
            continue
        try:
            LabelBase.register(name=alias, fn_regular=path)
        except Exception as exc:  # noqa: BLE001 - a bad font must not kill the app
            # Kivy validates the file when it builds the alias; a font that
            # freetype refuses leaves the previous registration in place.
            _log.warning("Font %s rejected for alias %s: %s", path, alias, exc)


def _apply_language_font(lang_code):
    """Re-point the global font aliases for the active language.

    A language whose script the bundled fonts cannot draw ships a font inside
    its pack (game/remote_content/packs.py). When the active language has one
    on disk it overrides BOTH aliases — a script the pixel font cannot render
    cannot keep the pixel font anywhere. Switching back to a covered language
    restores the bundled files. Runs before widgets are (re)built in every
    activation flow, because all of them go through set_language().
    """
    override = None
    try:
        from game.remote_content import packs
        override = packs.verified_font_path(lang_code)
    except Exception as exc:  # noqa: BLE001 - never break startup over a font
        # set_language() sits inside engine.load(); anything raising here would
        # be caught by load()'s blanket handler and QUARANTINE a healthy save.
        # A font problem must cost the bundled fallback, never the player's run.
        _log.warning("Font lookup failed for %r: %s", lang_code, exc)
    if override is not None:
        _register_fonts({alias: str(override) for alias in _FONT_ALIASES})
    else:
        _register_fonts(dict(_BUNDLED_FONT_FILES))


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


_LANG_FILE_SUFFIX = ".json"

# The game-data overlay consumed by data_loader.apply_translations(). It sits
# in the same directories as the UI files and is not a language.
_DATA_OVERLAY_PREFIX = "data_"


def _valid_lang_code(code):
    """Whether a code is safe to use as a language filename component.

    The rule belongs to game.remote_content._manifest, which owns what an
    untrusted manifest is allowed to name. Imported lazily like every other
    remote_content touch in this module — the headless tools import this
    module without the package. When it is unavailable the code is accepted:
    here it only ever becomes a dict key, and a remote_content problem must
    never cost the bundled languages, which is the same trade _language_dirs()
    makes one function up.
    """
    try:
        from game.remote_content._manifest import valid_lang_code
    except Exception as exc:  # noqa: BLE001 - bundled languages must still load
        _log.debug("Language code validation unavailable: %s", exc)
        return True
    return valid_lang_code(code)


def _is_language_file(fname):
    """Return the UI language code a directory entry names, or None.

    The one rule for what a scan of the language directories may treat as a
    language, so this scanner and game.remote_content.packs's own cannot drift
    apart. Rejected:

    * dotfiles — the packs directory keeps its bookkeeping beside the packs
      (".revisions.json", ".fonts.json"), and ".revisions" is not a language;
    * the ``data_XX.json`` overlay — t() never reads it, and loading it here
      parsed ~2 MB of JSON into _LANG_DATA on every startup for nothing;
    * a stem the manifest would refuse as a filename component.
    """
    if (fname.startswith(".") or fname.startswith(_DATA_OVERLAY_PREFIX)
            or not fname.endswith(_LANG_FILE_SUFFIX)):
        return None
    code = fname[: -len(_LANG_FILE_SUFFIX)]
    return code if _valid_lang_code(code) else None


def load_languages(force=False):
    """Load UI language files from the bundled directory and installed packs.

    Idempotent by default — each lang code is loaded at most once. The
    bottom of this module auto-loads on import (for tests), and main.py
    calls init_language() again on app build; without this guard every
    startup logged each language twice. Pass force=True to re-read from
    disk (dev hot-reload, and after a pack is installed at runtime).

    What counts as a language file is _is_language_file()'s call.
    """
    seen_dir = False
    for lang_dir in _language_dirs():
        if not os.path.isdir(lang_dir):
            continue
        seen_dir = True
        for fname in sorted(os.listdir(lang_dir)):
            lang_code = _is_language_file(fname)
            if lang_code is None:
                continue
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
        except (KeyError, IndexError, ValueError):
            # A translation is data, and remote patches make it data this build
            # has never seen: a missing placeholder (KeyError/IndexError) or an
            # unbalanced brace (ValueError) must cost the raw template, not the
            # screen that formats it.
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
    # The ACTIVE language decides the font: if the request fell back to
    # English, English must render in the bundled fonts, not in whatever the
    # unavailable language would have used.
    _apply_language_font(_current_lang)


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
    """Load language files. Current language is left at module default ("en");
    a saved language code is applied later by engine.load() via set_language().
    """
    load_languages()


# Auto-load on import if JSON files exist (for tests that don't call init_language)
try:
    load_languages()
except Exception as exc:
    # Import-time best effort. Swallow to avoid blocking test collection, but
    # surface the reason so a missing / malformed language file is debuggable.
    _log.warning("localization auto-load failed: %s", exc)
