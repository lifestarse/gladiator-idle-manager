# Build: 1
"""Every non-English language file must be excluded from the APK.

Only en.json ships: it is the terminal fallback of localization.t(). Every
other language is a downloadable pack (game/remote_content/packs.py), and a
bundled copy permanently shadows the pack's UI half — localization resolves
bundled before packs, and load_languages skips a code already in _LANG_DATA.
The result is a half-stale language: fresh game text next to interface
strings frozen at the APK version, undeliverable by any remote patch.

buildozer.spec lists those exclusions by hand, so adding a tenth source
language is one forgotten line away from shipping that. This test is the
mechanism that makes the hand-written list safe.
"""
import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "buildozer.spec"
LANG_DIR = ROOT / "data" / "languages"

# The one language that must stay in the APK — localization.t()'s last resort.
BUNDLED_LANG_FILE = "en.json"


def _exclude_patterns():
    """source.exclude_patterns from buildozer.spec, as a list of globs."""
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*source\.exclude_patterns\s*=\s*(.+?)\s*$", line)
        if match:
            return [p.strip() for p in match.group(1).split(",") if p.strip()]
    return []


def _is_excluded(rel_path, patterns):
    return any(fnmatch.fnmatch(rel_path, pat) for pat in patterns)


def _language_files():
    return sorted(p.name for p in LANG_DIR.glob("*.json"))


def test_spec_declares_exclude_patterns():
    assert _exclude_patterns(), "buildozer.spec has no 'source.exclude_patterns = ' line"


def test_language_dir_is_not_empty():
    assert _language_files(), f"no *.json under {LANG_DIR}"


def test_every_non_english_language_file_is_excluded():
    patterns = _exclude_patterns()
    shipped = [
        name for name in _language_files()
        if name != BUNDLED_LANG_FILE
        and not _is_excluded(f"data/languages/{name}", patterns)
    ]
    assert not shipped, (
        "these language files would ship inside the APK and permanently "
        "shadow the UI half of their downloadable pack: "
        + ", ".join(shipped)
        + ". Add each to source.exclude_patterns in buildozer.spec."
    )


def test_english_language_file_still_ships():
    """Guards the tempting 'simplification' to data/languages/*.json."""
    patterns = _exclude_patterns()
    assert not _is_excluded(f"data/languages/{BUNDLED_LANG_FILE}", patterns), (
        f"data/languages/{BUNDLED_LANG_FILE} is excluded from the APK. It is "
        "the terminal fallback of localization.t() and must always be present."
    )
