# Build: 6
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

import hashlib
import json
import logging
import os
import shutil
import threading

from game.storage import user_data_dir

from . import _http, _net, languages

_log = logging.getLogger(__name__)

# The picker downloads each row on its own thread and the background sync runs
# concurrently, so the two small state files (.revisions.json, .fonts.json) are
# read-modify-written under one lock. Without it two downloads finishing
# together lose one record — the language installs but its font is forgotten.
_state_lock = threading.Lock()

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

# Downloaded per-language fonts (for scripts the bundled fonts cannot render)
# live in a subdirectory of the packs dir, stored under the sha256 of their own
# bytes. Content-addressing is what makes the store safe: the remote side never
# picks a filename, two languages sharing one font share one file, and a font
# published under a new name cannot overwrite the bytes another language is
# still using. Which language uses which file is recorded in .fonts.json:
# {lang: {"file": "<sha>.ttf", "sha256": hex}}.
FONTS_SUBDIRNAME = "fonts"
FONTS_STATE_NAME = ".fonts.json"
# Extensions kept from the published name, purely so the store is legible when
# debugging on a device. Anything else is stored as .ttf — freetype sniffs the
# content, the suffix decides nothing.
FONT_EXTENSIONS = (".ttf", ".otf", ".ttc")
# A Latin/Cyrillic-extension font is ~0.5 MB; a single-script CJK subset can
# reach a few MB. 8 MB is generous headroom and still a hard ceiling.
FONT_MAX_BYTES = 8 * 1024 * 1024
# TTF / OTF / legacy-Mac TTF / TTC — anything else is not a font file and must
# not reach freetype.
FONT_MAGIC = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf")

# Every half-written file in these directories carries this suffix until the
# rename that publishes it. Anything scanning a directory a writer also uses
# has to recognise it: a download in progress is not garbage.
TMP_SUFFIX = ".tmp"

# ------------------------------------------------------------ data-half shape
#
# The contract below is what game/data_loader/translationmixin.py reads, and it
# is closed: the overlay looks at these sections and these fields and nothing
# else. Enforcing it here is not tidiness — apply_translations() runs inside
# engine.load(), whose blanket handler quarantines the save when anything
# raises, so a section of the wrong type would cost the player their progress.
#
# Flat sections map an entry id to {field: text}.
DATA_TEXT_FIELDS = ("name", "desc", "description", "title", "text",
                    "special_effect")
DATA_FLAT_SECTIONS = (
    "weapons", "armor", "accessories", "relics", "achievements", "enemies",
    "injuries", "expeditions", "lore", "enchantments", "boss_modifiers",
    "mutators",
)
# "classes" is the one nested section: a class carries the same text fields
# plus two sub-blocks and a map of perks, each of which is {field: text} again.
DATA_CLASSES_SECTION = "classes"
DATA_CLASS_BLOCKS = ("passive_ability", "active_skill")
DATA_CLASS_PERKS = "perks"
# The longest translated string across the eight shipped packs is 712
# characters (a lore paragraph), so this is an order of magnitude of headroom
# and still a bound on what can reach a widget.
MAX_DATA_TEXT_CHARS = 4000


def bundled_dir():
    """data/languages/ inside the app — the read-only files from the APK."""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, "data", "languages")


def packs_dir():
    """Writable directory holding downloaded packs.

    Lives in user_data_dir() (app-private storage on Android), so it survives
    app updates and disappears with an uninstall — exactly the lifetime a cache
    of re-downloadable content should have.
    """
    path = user_data_dir() / PACKS_DIRNAME
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


def _tmp_path(path):
    return path.with_suffix(path.suffix + TMP_SUFFIX)


def _write_atomic(path, payload):
    """Write JSON so a reader sees either the old file or the whole new one.

    Every file this module owns goes through here. The player force-kills the
    game routinely, and a truncated state file is indistinguishable from a
    corrupt one to the readers above — they fall back to "nothing installed".
    """
    tmp = _tmp_path(path)
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    shutil.move(str(tmp), str(path))


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
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}


def installed_revision(lang):
    """Which revision of this pack is on disk, or None."""
    value = _revisions().get(lang)
    return value if isinstance(value, int) else None


def _record_revision(lang, revision):
    with _state_lock:
        data = _revisions()
        data[lang] = revision
        try:
            _write_atomic(packs_dir() / REVISIONS_NAME, data)
        except OSError as exc:
            # Losing the revision only costs a redundant re-download later.
            _log.warning("[packs] could not record revision for %s: %s", lang, exc)


def fonts_dir():
    """Writable directory holding downloaded per-language fonts."""
    path = packs_dir() / FONTS_SUBDIRNAME
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log.warning("[packs] cannot create %s: %s", path, exc)
    return path


def _fonts_state():
    path = packs_dir() / FONTS_STATE_NAME
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    # Every consumer of this file builds a path out of it, and it can be
    # corrupt (a half-written file, a device that lost power) — so only
    # well-shaped records survive the read.
    return {lang: entry for lang, entry in data.items()
            if isinstance(lang, str) and isinstance(entry, dict)
            and isinstance(entry.get("file"), str) and entry["file"]
            and isinstance(entry.get("sha256"), str) and entry["sha256"]}


def _write_fonts_state(data):
    try:
        _write_atomic(packs_dir() / FONTS_STATE_NAME, data)
    except OSError as exc:
        # Losing the mapping only costs a redundant re-download later.
        _log.warning("[packs] could not record font state: %s", exc)


def _collect_garbage(state):
    """Delete font files no record references any more. Caller holds the lock."""
    referenced = {entry["file"] for entry in state.values()}
    try:
        for path in fonts_dir().iterdir():
            # A concurrent download writes its bytes here under a .tmp name
            # before the rename that makes it referenced; deleting that leaves
            # the download reporting failure for no reason.
            if path.name.endswith(TMP_SUFFIX) or path.name in referenced:
                continue
            path.unlink(missing_ok=True)
    except OSError as exc:
        _log.warning("[packs] could not tidy the font store: %s", exc)


def _record_font(lang, filename, sha256):
    with _state_lock:
        data = _fonts_state()
        data[lang] = {"file": filename, "sha256": sha256}
        _write_fonts_state(data)
        # A language moving to a new font leaves the old file behind unless
        # something collects it, and fonts are megabytes.
        _collect_garbage(data)


def _forget_font(lang):
    """Drop a language's font mapping; delete the file when unreferenced."""
    with _state_lock:
        data = _fonts_state()
        if data.pop(lang, None) is None:
            return
        _write_fonts_state(data)
        _collect_garbage(data)


def _font_filename(font):
    """Content-addressed store name: the sha256 the manifest pins, plus a
    legible extension. The remote side never chooses this name."""
    suffix = os.path.splitext(font["path"].replace("\\", "/"))[1].lower()
    if suffix not in FONT_EXTENSIONS:
        suffix = ".ttf"
    return f"{font['sha256']}{suffix}"


def verified_font_path(lang):
    """Absolute path of this language's downloaded font, or None.

    Re-hashes the file on every call: this feeds a native renderer at startup,
    and a font that rotted on disk crashing the app in freetype would be a
    crash loop with no recovery. A corrupt file is deleted and forgotten so
    the next sync() re-downloads it; until then the language renders in the
    bundled fonts (tofu for an uncovered script, but alive).
    """
    entry = _fonts_state().get(lang)
    if entry is None:
        return None
    path = fonts_dir() / entry["file"]
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
    if digest != entry["sha256"]:
        _log.warning("[packs] font %s is corrupt on disk — dropping it",
                     entry["file"])
        _forget_font(lang)
        return None
    return path


def ensure_font(lang, base_url, entry, on_progress=None):
    """Make the font a manifest entry declares present on disk. True on success.

    True also when the entry declares no font — most languages need none. The
    downloaded file is verified (sha256 from the manifest + font magic) before
    it is recorded, so nothing unverified is ever handed to freetype.
    """
    font = entry.get("font") if isinstance(entry, dict) else None
    if not font:
        return True
    filename = _font_filename(font)
    recorded = _fonts_state().get(lang)
    if recorded is not None and recorded["sha256"] == font["sha256"] \
            and (fonts_dir() / filename).exists():
        return True

    def on_bytes(received, total):
        if on_progress:
            try:
                on_progress("downloading", (received / total) if total else None)
            except Exception:  # noqa: BLE001 - a UI callback must not break the download
                pass

    body = _http.fetch_bytes(base_url + font["path"], max_bytes=FONT_MAX_BYTES,
                             on_bytes=on_bytes, sha256=font["sha256"])
    if body is None:
        return False
    if not body.startswith(FONT_MAGIC):
        _log.warning("[packs] %s is not a font file — rejected", font["path"])
        return False
    target = fonts_dir() / filename
    tmp = _tmp_path(target)
    try:
        tmp.write_bytes(body)
        shutil.move(str(tmp), str(target))
    except OSError as exc:
        _log.warning("[packs] could not write font %s: %s", filename, exc)
        return False
    _record_font(lang, filename, font["sha256"])
    _log.info("[packs] installed font %s for %s", filename, lang)
    return True


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


def installed_codes_on_disk():
    """Language codes with a complete pack in the packs directory.

    Unlike installed_languages() this is not filtered through OFFERED, so a
    language that arrived purely via the manifest (no APK release) is still
    seen by the background updater. And unlike is_installed() it ignores the
    bundled directory — on a dev checkout every language is bundled, and
    "installed" there must not mean "download all eight packs on every sync".
    """
    from ._manifest import valid_lang_code
    directory = packs_dir()
    codes = set()
    try:
        for path in directory.glob("*.json"):
            name = path.name
            if name.startswith(".") or name.startswith("data_"):
                continue
            code = name[: -len(".json")]
            if valid_lang_code(code) and (directory / f"data_{code}.json").exists():
                codes.add(code)
    except OSError as exc:
        _log.warning("[packs] cannot scan packs directory: %s", exc)
    return codes


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
    _forget_font(lang)
    return removed


def _clean_text_fields(entry):
    """{field: text} for the fields the overlay reads, or None.

    None means the entry does not obey the contract — it is not a mapping, or
    one of the fields it does carry is not a string of sane length.
    """
    if not isinstance(entry, dict):
        return None
    fields = {}
    for field in DATA_TEXT_FIELDS:
        if field not in entry:
            continue
        text = entry[field]
        if not isinstance(text, str) or len(text) > MAX_DATA_TEXT_CHARS:
            return None
        fields[field] = text
    return fields


def _clean_flat_section(entries):
    """{entry_id: {field: text}} for one flat section, or None."""
    if not isinstance(entries, dict):
        return None
    clean = {}
    for entry_id, entry in entries.items():
        fields = _clean_text_fields(entry)
        if fields is None:
            return None
        clean[entry_id] = fields
    return clean


def _clean_classes_section(entries):
    """{class_id: {...}} for the nested classes section, or None."""
    if not isinstance(entries, dict):
        return None
    clean = {}
    for class_id, entry in entries.items():
        fields = _clean_text_fields(entry)
        if fields is None:
            return None
        for block in DATA_CLASS_BLOCKS:
            if block not in entry:
                continue
            block_fields = _clean_text_fields(entry[block])
            if block_fields is None:
                return None
            fields[block] = block_fields
        if DATA_CLASS_PERKS in entry:
            perks = _clean_flat_section(entry[DATA_CLASS_PERKS])
            if perks is None:
                return None
            fields[DATA_CLASS_PERKS] = perks
        clean[class_id] = fields
    return clean


def validate_data(data):
    """Return the translatable half of a pack, restricted to the contract, or None.

    None means the payload is not shaped like a data document at all, and the
    pack must be refused whole: the overlay would raise inside engine.load(),
    where an exception costs the player their save rather than their subtitles.

    Sections this build does not read are DROPPED, not refused. A pack
    published for a newer build has to stay installable on an older one, which
    is the same rule the UI half follows for keys it does not know.
    """
    if not isinstance(data, dict):
        return None
    clean, unknown = {}, []
    for section, entries in data.items():
        if section in DATA_FLAT_SECTIONS:
            cleaned = _clean_flat_section(entries)
        elif section == DATA_CLASSES_SECTION:
            cleaned = _clean_classes_section(entries)
        else:
            unknown.append(section)
            continue
        if cleaned is None:
            _log.warning("[packs] data section %r does not obey the "
                         "translation contract", section)
            return None
        clean[section] = cleaned
    if unknown:
        _log.info("[packs] data sections not read by this build, dropped: %s",
                  ", ".join(str(name) for name in unknown))
    return clean


def validate_pack(payload, lang):
    """Return (ui, data) when the payload is a usable pack, else (None, None).

    The UI half is checked against bundled en.json with the same validator the
    patch path uses: same key universe, same placeholders, same markup. A pack
    that fails wholesale is not installed — the player keeps English, which
    works, instead of a screen of broken format strings.

    The data half is checked against the contract its only consumer imposes
    (see DATA_FLAT_SECTIONS above) and comes back reduced to it, so what
    install() writes to disk cannot make the overlay raise.
    """
    if not isinstance(payload, dict) or payload.get("lang") != lang:
        return None, None
    ui, data = payload.get("ui"), payload.get("data")
    if not isinstance(ui, dict):
        return None, None
    data = validate_data(data)
    if data is None:
        _log.warning("[packs] %s rejected: malformed data half", lang)
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
    reference_leaves = languages_reference_leaves(reference)
    if len(accepted) < len(reference_leaves) * 0.9:
        _log.warning("[packs] %s rejected: only %d of %d strings valid (e.g. %s)",
                     lang, len(accepted), len(reference_leaves),
                     list(rejected.items())[:3])
        return None, None
    if rejected:
        _log.info("[packs] %s: %d strings fell back to English", lang, len(rejected))
    return accepted, data


def languages_reference_leaves(reference):
    from game.localization import flatten
    return flatten(reference)


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
    # Font first: a language whose script the bundled fonts cannot draw is
    # worse than no language, so the pack does not install without its font.
    if not ensure_font(lang, base_url, entry, on_progress=on_progress):
        report("failed")
        return False
    payload = _http.fetch_json(base_url + entry["path"],
                               max_bytes=PACK_MAX_BYTES, on_bytes=on_bytes)
    if payload is None:
        report("failed")
        return False
    report("installing")
    ok = install(lang, payload, revision=entry.get("revision"))
    report("done" if ok else "failed")
    return ok
