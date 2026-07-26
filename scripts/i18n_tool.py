# Build: 1
"""Extract translation source batches and merge translated fragments back.

Workflow agents never edit data/languages/data_XX.json directly — parallel
writers would clobber each other. Each agent writes one fragment under
scratch/i18n_out/<lang>__<batch>.json and this tool merges them deterministically.

Usage:
    python scratch/i18n_tool.py extract          # -> scratch/i18n_src/*.json
    python scratch/i18n_tool.py merge <lang>     # fragments -> data_<lang>.json
    python scratch/i18n_tool.py status           # what is still missing
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, "scratch", "i18n_src")
OUT_DIR = os.path.join(ROOT, "scratch", "i18n_out")
LANG_DIR = os.path.join(ROOT, "data", "languages")
LANGS = ("ru", "uk", "de", "es", "fr", "it", "pt", "pl")

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
    applied = missing = 0
    for name, section, rows in _batches():
        fragment_path = os.path.join(OUT_DIR, f"{lang}__{name}.json")
        if not os.path.exists(fragment_path):
            missing += len(rows)
            continue
        fragment = _load(fragment_path)
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


def status():
    names = [name for name, _section, _rows in _batches()]
    for lang in LANGS:
        done = [n for n in names
                if os.path.exists(os.path.join(OUT_DIR, f"{lang}__{n}.json"))]
        print(f"{lang}: {len(done)}/{len(names)} fragments {sorted(set(names) - set(done))}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "extract":
        extract()
    elif command == "merge":
        merge(sys.argv[2])
    else:
        status()
