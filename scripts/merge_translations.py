# Build: 1
"""One-off script to merge new translation keys into en.json and ru.json.

Safe to re-run: uses dict.update() which overwrites matching keys but preserves
all other existing keys. Reads with UTF-8, writes with ensure_ascii=False to
preserve Cyrillic characters.
"""

import json
import os
import sys
from scripts.translations_data import NEW_KEYS

HERE = os.path.dirname(os.path.abspath(__file__))
LANG_DIR = os.path.join(os.path.dirname(HERE), "data", "languages")

# (key, en_value, ru_value)


def merge(lang_file, lang_idx):
    path = os.path.join(LANG_DIR, lang_file)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    orig_count = len(data)
    added = 0
    updated = 0
    for key, en_val, ru_val in NEW_KEYS:
        val = en_val if lang_idx == 0 else ru_val
        if key in data:
            if data[key] != val:
                data[key] = val
                updated += 1
        else:
            data[key] = val
            added += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{lang_file}: {orig_count} -> {len(data)} keys (+{added} added, {updated} updated)")


if __name__ == "__main__":
    merge("en.json", 0)
    merge("ru.json", 1)
    print("OK")
