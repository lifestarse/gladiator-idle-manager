# Build: 4
"""Extract translation source batches and merge translated fragments back.

Workflow agents never edit data/languages/*.json directly — parallel writers
would clobber each other. Each agent writes one fragment under
scratch/i18n_out/ and this tool merges them deterministically.

Two independent pipelines share the plumbing:

* ``extract`` / ``merge`` — game DATA (data/languages/data_XX.json): enemies,
  injuries, lore, enchantments, mutators, boss modifiers. Batches are
  language-neutral; the acceptance gate is tests/test_i18n_data_quality.py.
* ``extract-ui`` / ``merge-ui`` — UI STRINGS (data/languages/XX.json): the 830
  keys behind ``t()``. Batches are per-language because each one carries the
  current translation plus a ``machine`` flag saying whether that text is still
  raw GoogleTranslate output from GT_COMMIT. The gate is
  tests/test_i18n_ui_quality.py.

The UI batches also carry, per key, the call sites found in the source tree and
the semantic role read out of game/scripting/labels.py. That context is the
whole point: translating "call" or "Type" or "Auto-train" out of context is
exactly how the GoogleTranslate pass produced "phone call", "to type" and
"railway train".

Usage:
    python scripts/i18n_tool.py extract           # -> scratch/i18n_src/*.json
    python scripts/i18n_tool.py merge <lang>      # fragments -> data_<lang>.json
    python scripts/i18n_tool.py status            # what is still missing
    python scripts/i18n_tool.py extract-ui <lang> # -> scratch/i18n_src/ui_*.json
    python scripts/i18n_tool.py merge-ui <lang>   # fragments -> <lang>.json
    python scripts/i18n_tool.py status-ui         # what is still missing
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "scratch", "i18n_src")
OUT_DIR = os.path.join(ROOT, "scratch", "i18n_out")
REJECT_DIR = os.path.join(ROOT, "scratch", "i18n_rejected")
LANG_DIR = os.path.join(ROOT, "data", "languages")
LANGS = ("ru", "uk", "de", "es", "fr", "it", "pt", "pl")

# LLM scaffolding that must never reach a player-visible string: markdown
# fences, the agent's own answer-envelope tags, a value that is itself
# serialized JSON, numbered-answer markers. The game's own markup stays legal
# on purpose — BBCode ([b], [color=...]), placeholders ({n}) and the script
# editor's <name>/<nombre> meta-variable match none of these patterns.
# Shared with tests/test_i18n_*_quality.py so the merge-time quarantine and
# the acceptance gate cannot drift apart.
SCAFFOLD_PATTERNS = (
    ("markdown fence", re.compile(r"```|~~~")),
    ("answer-envelope tag", re.compile(
        r"</?(?:content|translation|output|result|answer|json|entry|entries|text)\s*>",
        re.IGNORECASE)),
    ("serialized JSON instead of text", re.compile(r'^\s*[\[{]\s*"')),
    ("numbered-answer marker", re.compile(r"^\s*\[\d+\]\s")),
)


def find_scaffolding(text):
    """Why the text is agent scaffolding rather than a translation, or None."""
    for reason, pattern in SCAFFOLD_PATTERNS:
        if pattern.search(text):
            return reason
    return None


def _fragment_scaffolding(fragment):
    """[(key, reason)] for every string value carrying agent scaffolding."""
    hits = []

    def scan(key, value):
        if isinstance(value, str):
            reason = find_scaffolding(value)
            if reason:
                hits.append((key, reason))
        elif isinstance(value, dict):
            for sub, nested in value.items():
                scan(f"{key}.{sub}", nested)

    for key, value in fragment.items():
        scan(key, value)
    return hits


def _quarantine(fragment_path, hits):
    """Move a dirty fragment out of the merge inputs, keeping it for autopsy.

    The whole fragment goes, not just the dirty keys: scaffolding in one value
    means the writer was not returning clean JSON, so its neighbours are not
    trusted either. With the file out of scratch/i18n_out/, status() honestly
    reports the batch as missing instead of counting rejected work as done.
    """
    os.makedirs(REJECT_DIR, exist_ok=True)
    name = os.path.basename(fragment_path)
    os.replace(fragment_path, os.path.join(REJECT_DIR, name))
    for key, reason in hits[:5]:
        print(f"    REJECTED {name} {key}: {reason}")
    if len(hits) > 5:
        print(f"    ... and {len(hits) - 5} more")
    print(f"    {name} -> scratch/i18n_rejected/ — re-translate the batch")

# section -> (base file, top-level key, fields)
SECTIONS = {
    "enemies": ("enemies.json", "enemies", ("description",)),
    "injuries": ("injuries.json", "injuries", ("description",)),
    "lore": ("lore.json", "entries", ("title", "text")),
    "enchantments": ("enchantments.json", "enchantments", ("description",)),
    "boss_modifiers": ("boss_modifiers.json", "modifiers", ("description",)),
    "mutators": ("mutators.json", "mutators", ("description",)),
}
# batch name -> (section, chunk index, chunk count); keeps agent output small
CHUNKS = {"enemies": 3, "lore": 2}
# Entity names the overlay actually applies (enemy and item names stay English
# by design — see the skip tuples in game/data_loader/translationmixin.py).
# They ship as separate batches so adding them cannot disturb description
# batches that translation agents are already reading.
NAME_SECTIONS = ("injuries", "enchantments", "boss_modifiers", "mutators")
NAME_BATCHES = {
    "names_injuries": ("injuries",),
    "names_effects": ("enchantments", "boss_modifiers", "mutators"),
}


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _dump(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)


def _dump_ui(path, data):
    """Write a UI language file, preserving authored key order.

    Deliberately NOT `_dump`: the content files (`data_XX.json`) are stored
    sorted, but the UI files (`XX.json`) are stored in authored order, which
    groups keys by screen and is the only thing making them reviewable by
    hand. `sort_keys=True` here would reflow all nine files into one
    alphabetical wall on the first merge and bury the real diff.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _by_id(node):
    return dict(node) if isinstance(node, dict) else {e["id"]: e for e in node}


def _section_rows(section, fields):
    base = _by_id(_load(os.path.join(ROOT, "data", SECTIONS[section][0]))[SECTIONS[section][1]])
    return {
        entry_id: {f: entry[f] for f in fields if isinstance(entry.get(f), str)}
        for entry_id, entry in base.items()
    }


def _batches():
    """Yield (batch_name, section_or_None, {key: {field: english}}).

    section is None for batches that span sections; their keys carry a
    "<section>:<id>" prefix so merge() can still place every entry.
    """
    for section, (_fname, _key, fields) in SECTIONS.items():
        rows = _section_rows(section, fields)
        ids = sorted(rows)
        parts = CHUNKS.get(section, 1)
        size = (len(ids) + parts - 1) // parts
        for index in range(parts):
            slice_ids = ids[index * size:(index + 1) * size]
            if not slice_ids:
                continue
            name = section if parts == 1 else f"{section}_{index + 1}"
            yield name, section, {i: rows[i] for i in slice_ids}

    for batch, sections in NAME_BATCHES.items():
        if len(sections) == 1:
            yield batch, sections[0], _section_rows(sections[0], ("name",))
            continue
        rows = {}
        for section in sections:
            for entry_id, fields in _section_rows(section, ("name",)).items():
                rows[f"{section}:{entry_id}"] = fields
        yield batch, None, rows


def extract():
    for name, _section, rows in _batches():
        _dump(os.path.join(SRC_DIR, f"{name}.json"), rows)
        print(f"{name}: {len(rows)} entries")


def merge(lang):
    target = os.path.join(LANG_DIR, f"data_{lang}.json")
    data = _load(target)
    applied = missing = quarantined = 0
    for name, section, rows in _batches():
        fragment_path = os.path.join(OUT_DIR, f"{lang}__{name}.json")
        if not os.path.exists(fragment_path):
            missing += len(rows)
            continue
        fragment = _load(fragment_path)
        hits = _fragment_scaffolding(fragment)
        if hits:
            _quarantine(fragment_path, hits)
            quarantined += 1
            missing += len(rows)
            continue
        for key, fields in rows.items():
            entry_section, entry_id = (section, key) if section else key.split(":", 1)
            translated = fragment.get(key)
            if translated is None:
                missing += 1
                continue
            if isinstance(translated, str):
                translated = {next(iter(fields)): translated}
            entry = data.setdefault(entry_section, {}).setdefault(entry_id, {})
            for field in fields:
                if isinstance(translated.get(field), str) and translated[field].strip():
                    entry[field] = translated[field].strip()
                    applied += 1
                else:
                    missing += 1
    _dump(target, data)
    print(f"{lang}: applied {applied} fields, still missing {missing}")
    if quarantined:
        print(f"{lang}: {quarantined} fragments QUARANTINED — nothing from "
              f"them reached data_{lang}.json")
        sys.exit(1)


def status():
    names = [name for name, _section, _rows in _batches()]
    for lang in LANGS:
        done = [n for n in names
                if os.path.exists(os.path.join(OUT_DIR, f"{lang}__{n}.json"))]
        print(f"{lang}: {len(done)}/{len(names)} fragments {sorted(set(names) - set(done))}")


# ---------------------------------------------------------------- UI strings

# ru is the language the game was written in; en was translated from it and
# then machine-pivoted into everything else, so en alone is not a safe source
# ("Авто-прокачка" -> "Auto-train" -> "Автопоїзд"). Agents get both.
UI_MASTER = "ru"
UI_PIVOT = "en"
UI_TARGETS = ("uk", "de", "es", "fr", "it", "pt", "pl")
# The commit that imported scripts/translate_all.py (GoogleTranslator) output.
# A string identical to its blob has never been reviewed by a human or an agent.
GT_COMMIT = "4db9012"
UI_BATCH_MAX = 90
# A screen with fewer strings than this is not worth its own agent: the point
# of grouping is shared context, and a two-string batch has none. Everything
# below the threshold lands in the "misc" pool instead.
UI_MIN_GROUP = 12
GLOSSARY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "i18n_glossary.json")
# Directories worth scanning for t("key") call sites. scripts/ is excluded on
# purpose: translations_data*.py holds key->text tables, so every key would
# look referenced.
UI_SCAN_ROOTS = ("game", "kv", "data")
UI_SCAN_FILES = ("main.py",)
UI_SCAN_SUFFIXES = (".py", ".kv", ".json")
UI_REFS_SHOWN = 3
UI_LINE_CLIP = 130
_TOKEN = re.compile(r"[a-z0-9_]+")


def _ui_path(lang):
    return os.path.join(LANG_DIR, f"{lang}.json")


# Flattening and dotted-path writes live in game.localization — the game, the
# quality gate and the remote-patch validator all address nested keys
# ("help_sections.4.1") the same way, so there is one implementation of it.
sys.path.insert(0, ROOT)
from game.localization import flatten as _ui_flat, set_path as _ui_set  # noqa: E402


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ui_roles():
    """Map i18n key -> what the UI does with it, from the label registries.

    game/scripting/labels.py and game/scripting/templates.py are pure data
    modules, so they load by path without dragging in kivy. 300 of the 830 keys
    are scripting-editor labels whose part of speech is invisible from the
    English text alone — "call" is a function call, "Type" is a noun, "log" is
    an imperative.
    """
    labels_path = os.path.join(ROOT, "game", "scripting", "labels.py")
    if not os.path.exists(labels_path):
        return {}
    L = _load_module(labels_path, "_i18n_labels")
    roles = {}

    def mark(keys, role):
        for key in keys:
            if isinstance(key, str):
                roles.setdefault(key, role)

    mark(L.TRIGGER_LABELS.values(),
         "script trigger: the event that starts a program (noun phrase)")
    mark(L.SOURCE_LABELS.values(),
         "for-each source: a collection of fighters (plural noun)")
    mark(L.CALL_LABELS.values(),
         "built-in FUNCTION name in the script editor (len/min/max/abs) — a "
         "programming call, never a telephone call")
    mark(L.OP_LABELS.values(),
         "operator name in the script editor (comparison/arithmetic/boolean)")
    mark(L.UNARY_OP_LABELS.values(), "unary operator name in the script editor")
    mark(L.FIGHTER_FIELD_LABELS.values(),
         "fighter property shown in the expression picker (noun, short)")
    mark(L.ENGINE_FIELD_LABELS.values(),
         "game-state property shown in the expression picker (noun, short)")
    mark(L.SLOT_LABELS.values(), "equipment slot name (noun)")
    mark(L.CLASS_LABELS.values(), "gladiator class name (noun)")
    mark((key for _cat, key in L.ACTION_CATEGORIES),
         "script palette category heading (noun)")
    for meta in L.ACTION_META.values():
        mark([meta.get("label")],
             "script ACTION block label — imperative verb phrase on a button, "
             "keep it short")
        mark([meta.get("desc")],
             "one-line description of that action in the picker (sentence)")
        mark(meta.get("arg_labels") or [],
             "label of an argument slot of a script action (short noun)")

    templates_path = os.path.join(ROOT, "game", "scripting", "templates.py")
    if os.path.exists(templates_path):
        try:
            T = _load_module(templates_path, "_i18n_templates")
        except Exception:  # noqa: BLE001 - templates may import AST nodes
            return roles
        for template in getattr(T, "TEMPLATES", ()):
            mark([getattr(template, "name_key", None)],
                 "ready-made script template name (short noun phrase)")
            mark([getattr(template, "desc_key", None)],
                 "description of a ready-made script template (sentence)")
    return roles


def _ui_refs(keys):
    """Map key -> [(path, line_number, source_line)] for every literal mention.

    Token matching rather than a t("key") regex on purpose: many keys are
    reached through registries ({"label": "scr_act_bench"}) or data files, and
    those registry lines are the most informative context there is.
    """
    wanted = set(keys)
    refs = {}
    paths = []
    for root in UI_SCAN_ROOTS:
        for dirpath, _dirs, filenames in os.walk(os.path.join(ROOT, root)):
            rel_dir = os.path.relpath(dirpath, ROOT).replace(os.sep, "/")
            if "__pycache__" in rel_dir or rel_dir.startswith("data/languages"):
                continue
            paths += [f"{rel_dir}/{f}" for f in filenames
                      if f.endswith(UI_SCAN_SUFFIXES)]
    paths += [f for f in UI_SCAN_FILES if os.path.exists(os.path.join(ROOT, f))]
    for rel in sorted(paths):
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(lines, 1):
            for key in set(_TOKEN.findall(line)) & wanted:
                refs.setdefault(key, []).append((rel, number, line.strip()[:UI_LINE_CLIP]))
    return refs


def _ui_machine_flags(lang):
    """Map key -> True when the current text is untouched GoogleTranslate output.

    Reviewed strings must survive a re-translation pass; machine strings carry
    no information worth anchoring on and are translated from scratch.
    """
    current = _ui_flat(_load(_ui_path(lang)))
    try:
        blob = subprocess.run(
            ["git", "show", f"{GT_COMMIT}:data/languages/{lang}.json"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        machine = _ui_flat(json.loads(blob))
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        # No history (shallow clone, or a language added later): treat every
        # string as reviewed rather than silently discarding good work.
        return {path: False for path in current}
    return {path: path in machine and machine[path] == text
            for path, text in current.items()}


def _ui_area(key, refs):
    """Batch name for a key: the screen it lives on, else its key prefix.

    Grouping by screen keeps every string of one screen in one agent's context,
    which is what makes terminology consistent within a screen.
    """
    for rel, _number, _line in refs:
        parts = rel.split("/")
        if rel.startswith("game/screens/") and len(parts) > 2:
            return parts[2].removesuffix(".py")
        if rel.startswith("kv/"):
            return parts[1].removesuffix(".kv").removesuffix("_screen")
        if rel.startswith("game/scripting"):
            return "scripting"
        if rel.startswith("game/battle"):
            return "battle"
    return key.split("_")[0]


def _ui_batches(lang):
    """Yield (batch_name, {key: entry}) with entries carrying full context."""
    master = _ui_flat(_load(_ui_path(UI_MASTER)))
    pivot = _ui_flat(_load(_ui_path(UI_PIVOT)))
    current = _ui_flat(_load(_ui_path(lang)))
    roles = _ui_roles()
    refs = _ui_refs({p.split(".")[0] for p in pivot})
    machine = _ui_machine_flags(lang)

    grouped = {}
    for path in pivot:
        root = path.split(".")[0]
        grouped.setdefault(_ui_area(root, refs.get(root, [])), []).append(path)
    misc = []
    for area in [a for a in grouped if len(grouped[a]) < UI_MIN_GROUP]:
        misc += grouped.pop(area)
    if misc:
        # en.json order, so related strings stay adjacent inside the pool.
        order = list(pivot)
        grouped["misc"] = sorted(misc, key=order.index)

    for area in sorted(grouped):
        paths = grouped[area]
        parts = (len(paths) + UI_BATCH_MAX - 1) // UI_BATCH_MAX
        size = (len(paths) + parts - 1) // parts
        for index in range(parts):
            chunk = paths[index * size:(index + 1) * size]
            if not chunk:
                continue
            name = area if parts == 1 else f"{area}_{index + 1}"
            rows = {}
            for path in chunk:
                entry = {"en": pivot[path], "ru": master.get(path, ""),
                         "current": current.get(path, ""),
                         "machine": bool(machine.get(path))}
                role = roles.get(path.split(".")[0])
                if role:
                    entry["role"] = role
                where = refs.get(path.split(".")[0], [])
                if where:
                    entry["where"] = [f"{p}:{n}  {line}"
                                      for p, n, line in where[:UI_REFS_SHOWN]]
                else:
                    entry["where"] = ["(no literal reference found — key may be "
                                      "composed at runtime or unused)"]
                rows[path] = entry
            yield name, rows


def _ui_glossary(lang):
    """Glossary rows that carry a column for this language, plus its rules.

    Embedded into every batch rather than referenced: an agent that has to open
    a second file to learn that "call" is not a telephone call will not open it.
    """
    if not os.path.exists(GLOSSARY_PATH):
        return {}
    glossary = _load(GLOSSARY_PATH)
    terms = {}
    for term, spec in glossary.get("terms", {}).items():
        if not isinstance(spec, dict) or not spec.get(lang):
            continue
        terms[term] = {k: v for k, v in spec.items()
                       if k in ("en", "ru", "note", lang)}
    # The forbidden list rides along: the agent contract promises the
    # blacklist inside the batch, and an agent that has to open a second file
    # to learn that "call" is not a telephone call will not open it.
    return {"rules": glossary.get("rules", {}).get(lang, []),
            "forbidden": glossary.get("forbidden", {}).get(lang, {}),
            "terms": terms}


def extract_ui(lang):
    glossary = _ui_glossary(lang)
    total = 0
    for name, rows in _ui_batches(lang):
        payload = {
            "_lang": lang,
            "_glossary": glossary,
            "entries": rows,
        }
        _dump(os.path.join(SRC_DIR, f"ui_{lang}__{name}.json"), payload)
        machine = sum(1 for e in rows.values() if e["machine"])
        total += len(rows)
        print(f"ui_{lang}__{name}: {len(rows)} keys ({machine} machine)")
    print(f"{lang}: {total} keys total")


def merge_ui(lang):
    target = _ui_path(lang)
    data = _load(target)
    applied = missing = quarantined = 0
    for name, rows in _ui_batches(lang):
        fragment_path = os.path.join(OUT_DIR, f"ui_{lang}__{name}.json")
        if not os.path.exists(fragment_path):
            missing += len(rows)
            continue
        fragment = _load(fragment_path)
        fragment = fragment.get("entries", fragment)
        hits = _fragment_scaffolding(fragment)
        if hits:
            _quarantine(fragment_path, hits)
            quarantined += 1
            missing += len(rows)
            continue
        for path in rows:
            value = fragment.get(path)
            if isinstance(value, dict):
                value = value.get("text")
            if isinstance(value, str) and value.strip():
                _ui_set(data, path, value.strip())
                applied += 1
            else:
                missing += 1
    _dump_ui(target, data)
    print(f"{lang}: applied {applied} keys, still missing {missing}")
    if quarantined:
        print(f"{lang}: {quarantined} fragments QUARANTINED — nothing from "
              f"them reached {lang}.json")
        sys.exit(1)


def status_ui():
    for lang in UI_TARGETS:
        names = [name for name, _rows in _ui_batches(lang)]
        done = [n for n in names
                if os.path.exists(os.path.join(OUT_DIR, f"ui_{lang}__{n}.json"))]
        gap = sorted(set(names) - set(done))
        print(f"{lang}: {len(done)}/{len(names)} fragments {gap}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "extract":
        extract()
    elif command == "merge":
        merge(sys.argv[2])
    elif command == "extract-ui":
        extract_ui(sys.argv[2])
    elif command == "merge-ui":
        merge_ui(sys.argv[2])
    elif command == "status-ui":
        status_ui()
    else:
        status()
