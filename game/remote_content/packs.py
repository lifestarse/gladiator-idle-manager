# Build: 1
"""Downloadable language packs.

Only English ships inside the APK. Every other language is a pack the player
downloads: one file carrying both documents that language needs —

    <lang>.json        the 830 UI strings behind t()
    data_<lang>.json   translated enemy/injury/lore/enchantment text

They travel together in one request because a half-installed language (UI
translated, enemy names English) looks broken in a way the player cannot fix.
Installation is atomic for the same reason: both files are written to .tmp and
renamed only after both validate.

Sizes measured 2026-07-26: 78-95 KB gzipped per language, ~675 KB saved in the
APK across the eight.

RESOLUTION ORDER is bundled-first. A pack can never shadow English, so the
fallback chain in localization.t() always terminates on a file that is
guaranteed present.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

from . import _http, _net, languages

_log = logging.getLogger(__name__)

# What the APK carries. Everything else is downloadable.
BUNDLED_LANGS = ("en",)
# Offered in the picker, in display order. Kept here rather than in the UI so
# the picker, the sync path and the publisher agree on one list.
OFFERED = (
    ("English", "en"),
    ("Русский", "ru"),
    ("Українська", "uk"),
    ("Deutsch", "de"),
    ("Español", "es"),
    ("Français", "fr"),
    ("Italiano", "it"),
    ("Português", "pt"),
    ("Polski", "pl"),
)

PACKS_DIRNAME = ".gladiator_lang_packs"
# A pack is ~360 KB of JSON uncompressed; 4 MB is far beyond any real pack and
# still bounded.
PACK_MAX_BYTES = 4 * 1024 * 1024


def bundled_dir():
    """data/languages/ inside the app — the read-only files from the APK."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "data", "languages")


def packs_dir():
    """Writable directory holding downloaded packs.

    Kivy points HOME at the app's private storage on Android, so this survives
    app updates and disappears with an uninstall — exactly the lifetime a cache
    of re-downloadable content should have.
    """
    path = Path.home() / PACKS_DIRNAME
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log.warning("[packs] cannot create %s: %s", path, exc)
    return path


def resolve(filename):
    """Absolute path for a language file: bundled first, then installed packs.

    Returns None when neither has it.
    """
    bundled = os.path.join(bundled_dir(), filename)
    if os.path.exists(bundled):
        return bundled
    downloaded = packs_dir() / filename
    if downloaded.exists():
        return str(downloaded)
    return None


REVISIONS_NAME = ".revisions.json"


def _pack_files(lang):
    return (f"{lang}.json", f"data_{lang}.json")


def _revisions():
    path = packs_dir() / REVISIONS_NAME
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def installed_revision(lang):
    """Which revision of this pack is on disk, or None."""
    value = _revisions().get(lang)
    return value if isinstance(value, int) else None


def _record_revision(lang, revision):
    data = _revisions()
    data[lang] = revision
    try:
        with open(packs_dir() / REVISIONS_NAME, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    except OSError as exc:
        # Losing the revision only costs a redundant re-download later.
        _log.warning("[packs] could not record revision for %s: %s", lang, exc)


def is_installed(lang):
    """True when this language is usable right now, from wherever it resolves.

    English is bundled and always true — it has no data_en.json because the
    base data files are already English. For the rest BOTH files must resolve:
    a language whose UI is translated but whose enemy names are English looks
    broken, so half a pack counts as none and the next download replaces it
    rather than layering onto it.

    Deliberately not "is it in the packs directory": during development every
    language still sits in the bundled directory, and a status that contradicts
    what the player can actually select would be worse than useless.
    """
    if lang in BUNDLED_LANGS:
        return True
    return all(resolve(name) is not None for name in _pack_files(lang))


def installed_languages():
    return {code for _name, code in OFFERED if is_installed(code)}


def remove(lang):
    """Delete a downloaded pack. Bundled languages cannot be removed."""
    if lang in BUNDLED_LANGS:
        return False
    directory = packs_dir()
    removed = False
    for name in _pack_files(lang):
        try:
            (directory / name).unlink(missing_ok=True)
            removed = True
        except OSError as exc:
            _log.warning("[packs] could not remove %s: %s", name, exc)
    return removed


def validate_pack(payload, lang):
    """Return (ui, data) when the payload is a usable pack, else (None, None).

    The UI half is checked against bundled en.json with the same validator the
    patch path uses: same key universe, same placeholders, same markup. A pack
    that fails wholesale is not installed — the player keeps English, which
    works, instead of a screen of broken format strings.
    """
    if not isinstance(payload, dict) or payload.get("lang") != lang:
        return None, None
    ui, data = payload.get("ui"), payload.get("data")
    if not isinstance(ui, dict) or not isinstance(data, dict):
        return None, None

    reference_path = os.path.join(bundled_dir(), "en.json")
    try:
        with open(reference_path, encoding="utf-8") as handle:
            reference = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("[packs] cannot read bundled en.json: %s", exc)
        return None, None

    accepted, rejected = languages.validate(ui, reference)
    # A pack is a whole language, not a patch: losing a slice of it means the
    # player reads that slice in English with no indication why. Demand that
    # the overwhelming majority survives, and log what did not.
    if len(accepted) < len(languages_reference_leaves(reference)) * 0.9:
        _log.warning("[packs] %s rejected: only %d of %d strings valid (e.g. %s)",
                     lang, len(accepted), len(reference),
                     list(rejected.items())[:3])
        return None, None
    if rejected:
        _log.info("[packs] %s: %d strings fell back to English", lang, len(rejected))
    return accepted, data


def languages_reference_leaves(reference):
    from game.localization import flatten
    return flatten(reference)


def _write_atomic(path, payload):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    shutil.move(str(tmp), str(path))


def install(lang, payload, revision=None):
    """Validate and write a pack. Returns True when the language is usable.

    Both files land or neither does: the UI file is written last, and
    is_installed() checks for both, so an interrupted install reads as absent.
    """
    ui, data = validate_pack(payload, lang)
    if ui is None:
        return False
    directory = packs_dir()
    ui_name, data_name = _pack_files(lang)
    try:
        # Reconstitute the nested shape (enchant_names, help_sections) from the
        # flat validated leaves, using bundled en.json as the mould.
        from game.localization import set_path
        with open(os.path.join(bundled_dir(), "en.json"), encoding="utf-8") as handle:
            document = json.load(handle)
        for path, text in ui.items():
            set_path(document, path, text)

        _write_atomic(directory / data_name, data)
        _write_atomic(directory / ui_name, document)
    except (OSError, KeyError, IndexError, ValueError) as exc:
        _log.warning("[packs] install of %s failed: %s", lang, exc)
        remove(lang)
        return False
    if revision is not None:
        _record_revision(lang, revision)
    _log.info("[packs] installed %s (revision %s)", lang, revision)
    return True


def download(lang, base_url, entry, on_progress=None):
    """Fetch and install one pack. Returns True on success.

    on_progress(stage, fraction) is called with "checking" / "downloading" /
    "installing" / "done" / "offline" / "failed" so the picker can animate
    without knowing anything about HTTP. fraction is 0.0-1.0 during the
    download when the server declares a size, and None otherwise.
    """
    def report(stage, fraction=None):
        if on_progress:
            try:
                on_progress(stage, fraction)
            except Exception:  # noqa: BLE001 - a UI callback must not break the download
                pass

    def on_bytes(received, total):
        # total is None when the server sends no Content-Length; pass the None
        # through so the UI shows an indeterminate bar instead of a made-up
        # percentage.
        report("downloading", (received / total) if total else None)

    report("checking")
    if not _net.is_online():
        report("offline")
        return False
    report("downloading", 0.0)
    payload = _http.fetch_json(base_url + entry["path"],
                               max_bytes=PACK_MAX_BYTES, on_bytes=on_bytes)
    if payload is None:
        report("failed")
        return False
    report("installing")
    ok = install(lang, payload, revision=entry.get("revision"))
    report("done" if ok else "failed")
    return ok
