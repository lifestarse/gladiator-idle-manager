# Build: 1
"""One release gate, recomputed from the files on disk.

The sister translation project carried this motto in its verify.py: "a lying
pipeline cannot mark its own work as done". Every release claim here is
recomputed from the artifacts themselves — never trusted from a log line, a
state file or someone's memory of having run something. Read-only; problems
split into FAIL (blocks the release) and WARN (must be understood, may ship);
exit 1 on any FAIL.

    python scripts/release_check.py               # everything except network
    python scripts/release_check.py --live        # + byte-compare GitHub Pages
    python scripts/release_check.py --no-pytest   # fast re-run of the rest

Division of labour, so nothing is checked twice and nothing by nobody:

* the pytest suite (run from here) already carries the packaging, version
  sync, glyph coverage, i18n and pack-contract gates;
* git-BASED hygiene — `# Build: N` increments, version bump against HEAD —
  needs history and belongs to the buildcheck agent, not this gate;
* this file owns what neither covers: docs/content vs manifest integrity,
  orphan keys in the language files, dirty release inputs, and (with --live)
  whether Pages actually serves the bytes sitting in docs/content.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game.localization import flatten                        # noqa: E402

CONTENT_DIR = os.path.join(ROOT, "docs", "content")
LANG_DIR = os.path.join(ROOT, "data", "languages")
LANGS = ("ru", "uk", "de", "es", "fr", "it", "pt", "pl")
# Files whose uncommitted state silently changes what a release ships.
RELEASE_INPUTS = ("data", "docs/content", "buildozer.spec", "game", "kv",
                  "fonts", "main.py")
PYTEST_TAIL = re.compile(r"(\d+) (passed|failed|error)")


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def check_content(content_dir):
    """Manifest and files must describe each other exactly.

    Recomputed facts only: every manifest path exists and parses, a pack's
    embedded lang/revision match its manifest entry, a declared font's sha256
    matches the bytes on disk, and no unreferenced JSON rots in the folder.
    """
    fails, warns = [], []
    manifest_path = os.path.join(content_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return ["docs/content/manifest.json does not exist"], warns
    try:
        manifest = _load(manifest_path)
    except json.JSONDecodeError as exc:
        return [f"manifest.json is not valid JSON: {exc}"], warns
    if not isinstance(manifest.get("schema"), int):
        fails.append("manifest.json: 'schema' is missing or not an int")

    referenced = set()
    for name, entry in manifest.get("entries", {}).items():
        if not isinstance(entry, dict):
            fails.append(f"manifest entry {name}: not an object")
            continue
        rel = entry.get("path")
        if not isinstance(rel, str):
            fails.append(f"manifest entry {name}: no path")
            continue
        referenced.add(rel)
        path = os.path.join(content_dir, rel)
        if not os.path.exists(path):
            fails.append(f"{name}: {rel} referenced by the manifest, absent on disk")
            continue
        try:
            payload = _load(path)
        except json.JSONDecodeError as exc:
            fails.append(f"{name}: {rel} is not valid JSON: {exc}")
            continue
        if name.startswith("pack."):
            lang = name.split(".", 1)[1]
            if payload.get("lang") != lang:
                fails.append(f"{name}: file says lang={payload.get('lang')!r}")
            if payload.get("revision") != entry.get("revision"):
                fails.append(f"{name}: manifest revision {entry.get('revision')} "
                             f"but the file embeds {payload.get('revision')} — "
                             f"clients key their cache on this number")
        font = entry.get("font")
        if isinstance(font, dict):
            font_rel = font.get("path", "")
            referenced.add(font_rel)
            font_path = os.path.join(content_dir, font_rel)
            if not os.path.exists(font_path):
                fails.append(f"{name}: font {font_rel} absent on disk")
            else:
                with open(font_path, "rb") as handle:
                    body = handle.read()
                if hashlib.sha256(body).hexdigest() != font.get("sha256"):
                    fails.append(f"{name}: font {font_rel} sha256 does not "
                                 f"match the manifest — clients will refuse it")

    for dirpath, _dirs, files in os.walk(content_dir):
        for fname in files:
            rel = os.path.relpath(os.path.join(dirpath, fname),
                                  content_dir).replace(os.sep, "/")
            if rel in referenced or rel in ("manifest.json", "README.md"):
                continue
            if rel.endswith(".json") or rel.startswith("fonts/"):
                warns.append(f"{rel}: sits in docs/content but no manifest "
                             f"entry references it")
    return fails, warns


def check_parity(lang_dir):
    """Orphan keys: text no code will ever ask for.

    The coverage gate already fails a key that is MISSING from a language;
    the direction it cannot see is a key the languages still carry after en
    dropped it — dead weight that translators keep re-translating.
    """
    fails, warns = [], []
    try:
        base = set(flatten(_load(os.path.join(lang_dir, "en.json"))))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"en.json unreadable: {exc}"], warns
    for lang in LANGS:
        path = os.path.join(lang_dir, f"{lang}.json")
        if not os.path.exists(path):
            continue
        orphans = sorted(set(flatten(_load(path))) - base)
        if orphans:
            warns.append(f"{lang}.json: {len(orphans)} keys en.json does not "
                         f"have (e.g. {orphans[:3]}) — dead weight, drop them")
    return fails, warns


def check_hygiene(root):
    """Uncommitted release inputs mean the release is not what git says it is."""
    fails, warns = [], []
    result = subprocess.run(
        ["git", "status", "--porcelain", "--"] + list(RELEASE_INPUTS),
        cwd=root, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        warns.append("git status failed — hygiene not checked")
        return fails, warns
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        warns.append(f"{len(dirty)} uncommitted changes in release inputs "
                     f"(e.g. {[l.split()[-1] for l in dirty[:3]]}) — a build "
                     f"from this tree is not reproducible from any commit")
    return fails, warns


def run_pytest(root):
    """The whole suite; its gates (packaging, i18n, fonts) arrive with it.

    Returns (fails, summary_line) — the count in the verdict comes from
    pytest's own final line, never from memory or documentation.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=root, capture_output=True, text=True, encoding="utf-8")
    tail = (result.stdout or "").strip().splitlines()
    summary = tail[-1] if tail else "no output"
    if result.returncode != 0:
        failed = [line for line in tail if "FAILED" in line or "ERROR" in line]
        return ([f"pytest: {summary}"]
                + [f"    {line}" for line in failed[:5]], summary)
    if not PYTEST_TAIL.search(summary):
        return [f"pytest produced no summary line: {summary!r}"], summary
    return [], summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true",
                        help="also byte-compare docs/content with what GitHub "
                             "Pages serves (network)")
    parser.add_argument("--no-pytest", action="store_true",
                        help="skip the suite for a fast re-run of the rest")
    args = parser.parse_args()

    fails, warns = [], []
    suite = "skipped (--no-pytest)"
    if not args.no_pytest:
        print("pytest: running the whole suite...")
        pytest_fails, suite = run_pytest(ROOT)
        fails += pytest_fails
    for label, found in (("content", check_content(CONTENT_DIR)),
                         ("parity", check_parity(LANG_DIR)),
                         ("hygiene", check_hygiene(ROOT))):
        section_fails, section_warns = found
        fails += [f"{label}: {line}" for line in section_fails]
        warns += [f"{label}: {line}" for line in section_warns]

    if args.live:
        from scripts.publish_content import check_live
        mismatched, total = check_live()
        if mismatched:
            fails.append(f"live: {mismatched}/{total} files differ from what "
                         f"Pages serves")

    for line in fails:
        print(f"FAIL {line}")
    for line in warns:
        print(f"WARN {line}")
    verdict = "FAIL" if fails else "ok"
    print(f"\nрелиз-чек {verdict} | pytest: {suite} | fail {len(fails)} | "
          f"warn {len(warns)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
