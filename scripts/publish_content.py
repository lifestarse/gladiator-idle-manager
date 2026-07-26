# Build: 1
"""Build remote content patches from the diff against a released build.

A patch is not "the current file" — it is "what changed since the APK players
are running". So the baseline is a git ref: the tag or commit the release was
cut from. Everything this script emits is validated against THAT baseline with
the same validator the game runs at startup, because a patch the client will
reject is worse than no patch — it occupies the cache slot and fixes nothing.

Usage:
    python scripts/publish_content.py --since v1.9.44 --lang uk
    python scripts/publish_content.py --since v1.9.44 --lang uk,de --balance
    python scripts/publish_content.py --since HEAD~5 --lang uk --dry-run

Output lands in docs/content/, which GitHub Pages already serves (the same
folder convention as scripts-library.json):

    docs/content/manifest.json     the index the game fetches first
    docs/content/uk.v3.json        {dotted.path: "text"}
    docs/content/balance.v2.json   {section: {entry_id: {field: value}}}

Publishing is a git push. Reverting a bad patch is another git push — but note
that clients cache by revision, so a revert must BUMP the revision, never
restore an old one.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game.remote_content import gamedata, languages          # noqa: E402
from game.remote_content._manifest import SCHEMA             # noqa: E402
from game.localization import flatten                        # noqa: E402
from game.version import APP_VERSION                         # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "content")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")
LANG_DIR = "data/languages"


def _git_show(ref, rel_path):
    """Read a file as it was at a git ref. None if it did not exist there."""
    result = subprocess.run(["git", "show", f"{ref}:{rel_path}"],
                            cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8")
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{rel_path} at {ref} is not valid JSON: {exc}")


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _dump(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def build_language_patch(lang, since):
    """{dotted_path: text} for every leaf that changed since the baseline."""
    rel = f"{LANG_DIR}/{lang}.json"
    baseline = _git_show(since, rel)
    if baseline is None:
        raise SystemExit(f"{rel} does not exist at {since} — nothing to diff against")
    current = _load(os.path.join(ROOT, rel))

    old, new = flatten(baseline), flatten(current)
    patch = {path: text for path, text in new.items()
             if path in old and old[path] != text}
    added = [p for p in new if p not in old]

    accepted, rejected = languages.validate(patch, baseline)
    return accepted, rejected, added


def build_balance_patch(since):
    """{section: {entry_id: {field: value}}} for whitelisted numeric changes."""
    patch, notes = {}, []
    for section, (fname, top_key, fields) in gamedata.PATCHABLE.items():
        rel = f"data/{fname}"
        baseline = _git_show(since, rel)
        if baseline is None:
            notes.append(f"{rel}: absent at {since}, skipped")
            continue
        current = _load(os.path.join(ROOT, rel))
        old = dict(gamedata._entries_of(baseline.get(top_key)))
        new = dict(gamedata._entries_of(current.get(top_key)))
        for entry_id, entry in new.items():
            if entry_id not in old:
                notes.append(f"{section}.{entry_id}: new entry, cannot be patched in")
                continue
            for field in fields:
                if field in entry and field in old[entry_id] \
                        and entry[field] != old[entry_id][field]:
                    patch.setdefault(section, {}).setdefault(entry_id, {})[field] = entry[field]
    accepted, rejected = gamedata.validate(patch)
    return accepted, rejected, notes


def build_pack(lang):
    """A whole language as one document: {"lang", "revision", "ui", "data"}.

    Packs are not diffs. A player downloading Ukrainian for the first time has
    nothing to diff against, and a language whose UI and game text came from
    different revisions reads as two half-translations. Revision is filled in
    by the caller once it knows the number.
    """
    ui_path = os.path.join(ROOT, LANG_DIR, f"{lang}.json")
    data_path = os.path.join(ROOT, LANG_DIR, f"data_{lang}.json")
    if not os.path.exists(ui_path):
        raise SystemExit(f"{ui_path} not found — cannot build a pack for {lang}")
    ui = flatten(_load(ui_path))
    data = _load(data_path) if os.path.exists(data_path) else {}
    if not data:
        print(f"    NOTE {lang}: no data_{lang}.json — game text stays English")
    return {"lang": lang, "ui": ui, "data": data}


def _next_revision(manifest, name):
    entry = manifest.get("entries", {}).get(name)
    return (entry.get("revision", 0) + 1) if isinstance(entry, dict) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True,
                        help="git ref of the build players are running (tag or commit)")
    parser.add_argument("--lang", default="",
                        help="comma-separated language codes, e.g. uk,de")
    parser.add_argument("--balance", action="store_true",
                        help="also emit a balance patch from the data files")
    parser.add_argument("--packs", default="",
                        help="comma-separated languages to publish as full "
                             "downloadable packs, or 'all' for every "
                             "non-bundled language")
    parser.add_argument("--min-app", default=APP_VERSION,
                        help="oldest build the patch may apply to (default: this one)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be published, write nothing")
    args = parser.parse_args()

    manifest = _load(MANIFEST_PATH) if os.path.exists(MANIFEST_PATH) else {}
    entries = dict(manifest.get("entries", {}))
    writes = []

    for lang in [code.strip() for code in args.lang.split(",") if code.strip()]:
        accepted, rejected, added = build_language_patch(lang, args.since)
        print(f"{lang}: {len(accepted)} changed strings, "
              f"{len(rejected)} rejected, {len(added)} new keys skipped")
        for path, reason in list(rejected.items())[:5]:
            print(f"    REJECTED {path}: {reason}")
        if added:
            print(f"    NOTE new keys can only ship in an APK: {added[:5]}")
        if not accepted:
            continue
        name = f"lang.{lang}"
        revision = _next_revision(manifest, name)
        filename = f"{lang}.v{revision}.json"
        writes.append((os.path.join(OUT_DIR, filename), accepted))
        entries[name] = {"path": filename, "revision": revision,
                         "min_app": args.min_app}

    if args.packs:
        from game.remote_content.packs import BUNDLED_LANGS, OFFERED, validate_pack
        if args.packs.strip() == "all":
            codes = [code for _name, code in OFFERED if code not in BUNDLED_LANGS]
        else:
            codes = [c.strip() for c in args.packs.split(",") if c.strip()]
        for lang in codes:
            if lang in BUNDLED_LANGS:
                print(f"{lang}: bundled in the APK — packs are for the others")
                continue
            pack = build_pack(lang)
            name = f"pack.{lang}"
            revision = _next_revision(manifest, name)
            pack["revision"] = revision
            # Same validator the device runs, so a pack that would be refused
            # on the phone is refused here instead.
            ui, _data = validate_pack(pack, lang)
            if ui is None:
                print(f"{lang}: PACK REJECTED by the device validator — not published")
                continue
            print(f"{lang}: pack v{revision}, {len(pack['ui'])} strings, "
                  f"{len(pack['data'])} data sections")
            filename = f"packs/{lang}.v{revision}.json"
            writes.append((os.path.join(OUT_DIR, filename), pack))
            entries[name] = {"path": filename, "revision": revision,
                             "min_app": args.min_app}

    if args.balance:
        accepted, rejected, notes = build_balance_patch(args.since)
        total = sum(len(f) for e in accepted.values() for f in e.values())
        print(f"balance: {total} field changes, {len(rejected)} rejected")
        for key, reason in list(rejected.items())[:5]:
            print(f"    REJECTED {key}: {reason}")
        for note in notes[:5]:
            print(f"    NOTE {note}")
        if accepted:
            revision = _next_revision(manifest, "gamedata")
            filename = f"balance.v{revision}.json"
            writes.append((os.path.join(OUT_DIR, filename), accepted))
            entries["gamedata"] = {"path": filename, "revision": revision,
                                   "min_app": args.min_app}

    if not writes:
        print("nothing to publish")
        return

    if args.dry_run:
        for path, _payload in writes:
            print(f"would write {os.path.relpath(path, ROOT)}")
        print(f"would update {os.path.relpath(MANIFEST_PATH, ROOT)}")
        return

    for path, payload in writes:
        _dump(path, payload)
        print(f"wrote {os.path.relpath(path, ROOT)}")
    _dump(MANIFEST_PATH, {"schema": SCHEMA, "entries": entries})
    print(f"wrote {os.path.relpath(MANIFEST_PATH, ROOT)}")
    print("\nPublish with: git add docs/content && git commit && git push")


if __name__ == "__main__":
    main()
