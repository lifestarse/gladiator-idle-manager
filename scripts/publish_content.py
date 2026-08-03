# Build: 5
"""Build remote content patches from the diff against a released build.

A patch is not "the current file" — it is "what changed since the APK players
are running". So the baseline is a git ref: the tag or commit the release was
cut from. Everything this script emits is validated against THAT baseline with
the same validator the game runs at startup, because a patch the client will
reject is worse than no patch — it occupies the cache slot and fixes nothing.

The default run is a PLAN: it reports everything and writes nothing. Writing
is the explicit flag, because opt-in safety gets forgotten exactly once.
Before writing, the live manifest is fetched and compared: the remote is the
truth about what players already have, and a checkout behind the live site
would mint revisions that overwrite published ones.

Usage:
    python scripts/publish_content.py --since v1.9.44 --lang uk            # plan
    python scripts/publish_content.py --since v1.9.44 --lang uk --publish  # write
    python scripts/publish_content.py --since v1.9.44 --lang uk,de --balance --publish
    python scripts/publish_content.py --check-live   # is Pages serving docs/content?

A language that is NOT in the APK (not in packs.OFFERED) can still be
published — installed clients read the picker list from the manifest. Give it
a display name, and a font when the bundled pixel font cannot draw its script:

    python scripts/publish_content.py --since v1.9.46 --packs tr \\
        --name "tr=Türkçe" --font tr=scratch/fonts/NotoSans-tr.ttf

The font is copied to docs/content/fonts/ and referenced from the manifest
with its sha256; the client refuses to install the pack without it. Glyph
coverage is enforced here with the same rule as tests/test_font_glyph_coverage:
every pack string must render in the font the players will actually see —
the declared font if any, the bundled pixel font otherwise. To replace a
font later, publish it under a NEW filename (clients treat the name as the
version, mirroring how pack files are versioned).

Output lands in docs/content/, which GitHub Pages already serves (the same
folder convention as scripts-library.json):

    docs/content/manifest.json     the index the game fetches first
    docs/content/uk.v3.json        {dotted.path: "text"}
    docs/content/balance.v2.json   {section: {entry_id: {field: value}}}
    docs/content/fonts/*.ttf       fonts for languages the APK cannot draw

Publishing is a git push. Reverting a bad patch is another git push — but note
that clients cache by revision, so a revert must BUMP the revision, never
restore an old one.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from game.remote_content import BASE_URL, MANIFEST_URL       # noqa: E402
from game.remote_content import gamedata, languages          # noqa: E402
from game.remote_content._manifest import SCHEMA             # noqa: E402
from game.localization import flatten                        # noqa: E402
from game.version import APP_VERSION                         # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "content")
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")
LANG_DIR = "data/languages"
FONTS_OUT_SUBDIR = "fonts"
PIXEL_FONT = os.path.join(ROOT, "fonts", "PressStart2P-Regular.ttf")


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
    """Atomic write: a crash mid-write never leaves a half-written file.

    mkstemp rather than a fixed '<path>.tmp' — a fixed name is a race the
    moment two publishes overlap, and the temp file must live on the same
    filesystem as the target for os.replace to stay atomic.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2,
                      sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


FETCH_TIMEOUT_S = 15


def _fetch(url):
    """Bytes at a live URL, or None with a printed reason (offline happens)."""
    try:
        with urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_S) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"    fetch failed {url}: {exc}")
        return None


def check_remote_sync(local_manifest):
    """Compare the local manifest with what GitHub Pages actually serves.

    The remote is the truth about what players already have. Live AHEAD of
    local means this checkout is stale (someone published elsewhere) and the
    revisions computed here would overwrite published files under new numbers'
    feet — that refuses the publish. Live BEHIND local is the normal window
    between a publish and its push/deploy, and is only reported.
    Returns False when publishing must not proceed.
    """
    body = _fetch(MANIFEST_URL)
    if body is None:
        print("    live manifest unreachable — revision check SKIPPED; "
              "fine offline, verify with --check-live after pushing")
        return True
    try:
        live = json.loads(body)
    except json.JSONDecodeError:
        print("    live manifest is not valid JSON (Pages mid-deploy?) — "
              "revision check skipped, verify with --check-live later")
        return True
    local_entries = local_manifest.get("entries", {})
    live_entries = live.get("entries", {}) if isinstance(live, dict) else {}
    stale = []
    for name, live_entry in live_entries.items():
        if not isinstance(live_entry, dict):
            continue
        local_entry = local_entries.get(name)
        local_rev = local_entry.get("revision", 0) \
            if isinstance(local_entry, dict) else 0
        if live_entry.get("revision", 0) > local_rev:
            stale.append(f"{name}: live v{live_entry.get('revision')} > "
                         f"local v{local_rev}")
    if stale:
        print("REFUSED: the live site is AHEAD of this checkout — git pull "
              "before publishing:")
        for line in stale:
            print(f"    {line}")
        return False
    if live_entries != local_entries:
        print("    NOTE live manifest differs from local — unpushed or "
              "undeployed changes are pending")
    return True


def check_live():
    """Verify the live site serves byte-for-byte what docs/content holds.

    'Pushed' is not 'deployed': Pages builds lag, and a log line saying
    published proves nothing. This recomputes the answer from the two ends
    that matter — local bytes and live bytes. Returns (mismatched, total)
    so scripts/release_check.py can fold it into the release gate.
    """
    manifest = _load(MANIFEST_PATH) if os.path.exists(MANIFEST_PATH) else {}
    targets = [os.path.relpath(MANIFEST_PATH, OUT_DIR).replace(os.sep, "/")]
    for entry in manifest.get("entries", {}).values():
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("path"), str):
            targets.append(entry["path"])
        font = entry.get("font")
        if isinstance(font, dict) and isinstance(font.get("path"), str):
            targets.append(font["path"])
    mismatched = 0
    for rel in dict.fromkeys(targets):
        local_path = os.path.join(OUT_DIR, rel)
        if not os.path.exists(local_path):
            print(f"MISSING locally: docs/content/{rel} (manifest points at it)")
            mismatched += 1
            continue
        body = _fetch(BASE_URL + rel)
        if body is None:
            mismatched += 1
            continue
        with open(local_path, "rb") as handle:
            local_body = handle.read()
        if hashlib.sha256(body).hexdigest() \
                == hashlib.sha256(local_body).hexdigest():
            print(f"ok       {rel}")
        else:
            print(f"DIFFERS  {rel} — live {len(body)} B, local {len(local_body)} B")
            mismatched += 1
    total = len(dict.fromkeys(targets))
    if mismatched:
        print(f"\n{mismatched} of {total} files are not what Pages serves — "
              f"push not done, deploy lagging, or checkout stale")
    else:
        print(f"\nlive site serves all {total} files byte-for-byte — "
              f"deploy confirmed")
    return mismatched, total


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


def _parse_pairs(values, flag):
    """['tr=Türkçe', ...] -> {'tr': 'Türkçe'}; malformed input aborts loudly."""
    pairs = {}
    for value in values or []:
        code, sep, rest = value.partition("=")
        if not sep or not code.strip() or not rest.strip():
            raise SystemExit(f"{flag} expects lang=value, got {value!r}")
        pairs[code.strip()] = rest.strip()
    return pairs


def _font_cmap(path):
    """Codepoints a font can draw, or None when fontTools is unavailable."""
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return None
    return set(TTFont(path).getBestCmap())


def _pack_strings(pack):
    """Every player-visible string a pack carries, UI and data alike."""
    strings = [text for text in pack["ui"].values() if isinstance(text, str)]
    strings.extend(text for text in flatten(pack["data"]).values()
                   if isinstance(text, str))
    return strings


def check_glyph_coverage(pack, lang, font_path):
    """The publisher-side twin of tests/test_font_glyph_coverage.

    That test only sees languages checked into data/languages/, so a
    manifest-only language would bypass it entirely — this is where its
    strings meet the font players will actually render them with. Returns
    True when publishable.
    """
    cmap = _font_cmap(font_path)
    if cmap is None:
        print(f"    WARNING {lang}: fontTools not installed — glyph coverage "
              f"NOT verified against {os.path.basename(font_path)}")
        return True
    uncovered = set()
    for text in _pack_strings(pack):
        uncovered.update(ch for ch in text
                         if not ch.isspace() and ord(ch) not in cmap)
    if uncovered:
        sample = "".join(sorted(uncovered))[:20]
        print(f"{lang}: PACK REFUSED — {len(uncovered)} chars missing from "
              f"{os.path.basename(font_path)} (e.g. {sample!r}). "
              f"Publish with --font {lang}=<ttf that covers them>.")
        return False
    return True


def publish_font(lang, source_path, dry_run):
    """Copy a font into docs/content/fonts/ and build its manifest block."""
    if not os.path.exists(source_path):
        raise SystemExit(f"--font {lang}: {source_path} not found")
    with open(source_path, "rb") as handle:
        body = handle.read()
    filename = os.path.basename(source_path)
    target = os.path.join(OUT_DIR, FONTS_OUT_SUBDIR, filename)
    if os.path.exists(target):
        with open(target, "rb") as handle:
            if handle.read() != body:
                # Clients key the font by filename, so silently replacing the
                # bytes under the same name would strand every install that
                # already recorded the old sha256.
                raise SystemExit(
                    f"--font {lang}: docs/content/fonts/{filename} already "
                    f"exists with different content — publish under a new "
                    f"filename instead")
    if not dry_run:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source_path, target)
        print(f"wrote docs/content/{FONTS_OUT_SUBDIR}/{filename}")
    return {"path": f"{FONTS_OUT_SUBDIR}/{filename}",
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since",
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
    parser.add_argument("--name", action="append", metavar="LANG=DISPLAY",
                        help="picker display name for a language the APK does "
                             "not list, e.g. --name \"tr=Türkçe\"; sticks to "
                             "the manifest entry across republishes")
    parser.add_argument("--font", action="append", metavar="LANG=TTF_PATH",
                        help="font the language needs because the bundled "
                             "fonts cannot draw its script; copied into "
                             "docs/content/fonts/ and pinned by sha256")
    parser.add_argument("--publish", action="store_true",
                        help="actually write docs/content; without it the run "
                             "is a plan that reports everything and writes "
                             "nothing")
    parser.add_argument("--check-live", action="store_true",
                        help="verify the live Pages site serves docs/content "
                             "byte-for-byte, then exit")
    args = parser.parse_args()
    if args.check_live:
        mismatched, _total = check_live()
        sys.exit(1 if mismatched else 0)
    if not args.since:
        parser.error("--since is required (git ref of the released build)")
    names = _parse_pairs(args.name, "--name")
    fonts = _parse_pairs(args.font, "--font")

    manifest = _load(MANIFEST_PATH) if os.path.exists(MANIFEST_PATH) else {}
    # Default-on, before any revision is minted: minting revisions from a
    # stale checkout is the one mistake this script cannot undo.
    in_sync = check_remote_sync(manifest)
    if not in_sync and args.publish:
        sys.exit(1)
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
        offered_codes = {code for _n, code in OFFERED}
        for lang in codes:
            if lang in BUNDLED_LANGS:
                print(f"{lang}: bundled in the APK — packs are for the others")
                continue
            pack = build_pack(lang)
            name = f"pack.{lang}"
            previous = manifest.get("entries", {}).get(name)
            previous = previous if isinstance(previous, dict) else {}
            revision = _next_revision(manifest, name)
            pack["revision"] = revision
            # Same validator the device runs, so a pack that would be refused
            # on the phone is refused here instead. The validated data half is
            # what gets published: it is the pack reduced to what the overlay
            # in game/data_loader actually reads, so the file on the CDN is
            # byte-for-byte what a client accepts.
            ui, data = validate_pack(pack, lang)
            if ui is None:
                print(f"{lang}: PACK REJECTED by the device validator — not published")
                continue
            dropped = sorted(set(pack["data"]) - set(data))
            if dropped:
                print(f"    NOTE {lang}: data sections no code reads, "
                      f"stripped from the pack: {', '.join(dropped)}")
            pack["data"] = data

            # The font players will actually render with: the newly declared
            # one, else the already-published one, else the bundled pixel font
            # (same rule as the repo test gate). Checked BEFORE anything is
            # copied so a refused pack leaves no orphan files behind.
            if lang in fonts:
                render_font = fonts[lang]
            elif "font" in previous:
                render_font = os.path.join(OUT_DIR, previous["font"]["path"])
            else:
                render_font = PIXEL_FONT
            if not os.path.exists(render_font):
                print(f"{lang}: PACK REFUSED — render font {render_font} not found")
                continue
            if not check_glyph_coverage(pack, lang, render_font):
                continue

            # name/font stick to the entry across republishes; new flags win.
            entry = {"path": f"packs/{lang}.v{revision}.json",
                     "revision": revision, "min_app": args.min_app}
            if lang in fonts:
                entry["font"] = publish_font(lang, fonts[lang],
                                             dry_run=not args.publish)
            elif "font" in previous:
                entry["font"] = previous["font"]
            if lang in names:
                entry["name"] = names[lang]
            elif "name" in previous:
                entry["name"] = previous["name"]
            if lang not in offered_codes and "name" not in entry:
                print(f"    NOTE {lang}: not in the APK's list and no --name "
                      f"given — the picker will show the bare code")

            print(f"{lang}: pack v{revision}, {len(pack['ui'])} strings, "
                  f"{len(pack['data'])} data sections"
                  + (f", font {os.path.basename(entry['font']['path'])}"
                     if "font" in entry else ""))
            writes.append((os.path.join(OUT_DIR, entry["path"]), pack))
            entries[name] = entry

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

    if not args.publish:
        for path, _payload in writes:
            print(f"would write {os.path.relpath(path, ROOT)}")
        print(f"would update {os.path.relpath(MANIFEST_PATH, ROOT)}")
        print("\nplan only — re-run with --publish to write")
        return

    for path, payload in writes:
        _dump(path, payload)
        print(f"wrote {os.path.relpath(path, ROOT)}")
    _dump(MANIFEST_PATH, {"schema": SCHEMA, "entries": entries})
    print(f"wrote {os.path.relpath(MANIFEST_PATH, ROOT)}")
    print("\nPublish with: git add docs/content && git commit && git push")
    print("Then confirm the deploy actually served it:\n"
          "    python scripts/publish_content.py --check-live")


if __name__ == "__main__":
    main()
