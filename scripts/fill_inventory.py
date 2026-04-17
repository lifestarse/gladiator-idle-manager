"""Stress-test: add 1000 random items to the current inventory.

Loads the real save, appends 1000 items picked randomly from weapons /
armor / accessories / relics, each with a random upgrade_level (0-5)
and a small chance of a random enchantment. Saves back.

Backs up the current save to .before_1000 before writing.

Run:
    python scripts/fill_inventory.py
"""

import os
import sys
import random
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.engine import GameEngine
from game.data_loader import data_loader


def main():
    real_save = os.path.join(os.path.expanduser("~"),
                             ".gladiator_idle_save.json")
    backup = real_save + ".before_1000"

    if not os.path.exists(real_save):
        print(f"[error] No save at {real_save} — open the game first to init.")
        return

    shutil.copy2(real_save, backup)
    print(f"[backup] {real_save} -> {backup}")

    eng = GameEngine()
    eng.SAVE_PATH = real_save
    eng.load()
    print(f"[load] before: {len(eng.inventory)} inventory items")

    # Build pool of item templates (equipment only — not relics? include them)
    pool = (data_loader.weapons + data_loader.armor
            + data_loader.accessories + data_loader.relics)
    ench_ids = list(data_loader.enchantments.keys()) if data_loader.enchantments else []
    if not pool:
        print("[error] no items in data_loader pool — run from project root.")
        return

    random.seed()
    added = 0
    for _ in range(1000):
        template = random.choice(pool)
        item = dict(template)  # shallow copy — template fields untouched
        # Random upgrade (+0 to +5)
        item["upgrade_level"] = random.randint(0, 5)
        # 20% chance of enchantment (weapons only — other slots ignore ench)
        if item.get("slot") == "weapon" and ench_ids and random.random() < 0.2:
            item["enchantment"] = random.choice(ench_ids)
        eng.inventory.append(item)
        added += 1

    eng.save()
    print(f"[save] after: {len(eng.inventory)} inventory items (+{added})")

    # Sanity check: reload and verify
    eng2 = GameEngine()
    eng2.SAVE_PATH = real_save
    eng2.load()
    print(f"[verify] reloaded: {len(eng2.inventory)} items")
    # Summary by slot + rarity
    from collections import Counter
    by_slot = Counter(i.get("slot", "?") for i in eng2.inventory)
    by_rarity = Counter(i.get("rarity", "?") for i in eng2.inventory)
    print(f"  slots:   {dict(by_slot)}")
    print(f"  rarity:  {dict(by_rarity)}")


if __name__ == "__main__":
    main()
