"""Stress-test: add 1000 random fighters to the current roster.

Loads the real save, appends 1000 Fighter instances with random class,
level 1-25, random stat distribution. Saves back.

Backs up the current save to .before_1000_fighters before writing.

Run:
    python scripts/fill_roster.py
"""

import os
import sys
import random
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.engine import GameEngine
from game.models import Fighter
from game.data_loader import data_loader


CLASSES = ["mercenary", "assassin", "tank", "berserker", "retiarius", "medicus"]


def main():
    real_save = os.path.join(os.path.expanduser("~"),
                             ".gladiator_idle_save.json")
    backup = real_save + ".before_1000_fighters"

    if not os.path.exists(real_save):
        print(f"[error] No save at {real_save}")
        return

    shutil.copy2(real_save, backup)
    print(f"[backup] {real_save} -> {backup}")

    eng = GameEngine()
    eng.SAVE_PATH = real_save
    eng.load()
    print(f"[load] before: {len(eng.fighters)} fighters")

    names_pool = data_loader.fighter_names or ["Anon"]
    random.seed()

    for _ in range(1000):
        cls = random.choice(CLASSES)
        name = random.choice(names_pool)
        lvl = random.randint(1, 25)
        f = Fighter(name=name, fighter_class=cls, level=lvl)
        # Distribute extra points from levels (points_per_level × levels)
        extra_points = f.points_per_level * (lvl - 1)
        # Spread across STR/AGI/VIT
        for _ in range(extra_points):
            stat = random.choice(['strength', 'agility', 'vitality'])
            setattr(f, stat, getattr(f, stat) + 1)
        f.unused_points = 0
        f.hp = f.max_hp
        # 30% chance of some injuries (to test rendering)
        if random.random() < 0.3:
            injury_count = random.randint(1, 3)
            for _ in range(injury_count):
                try:
                    inj_id = data_loader.pick_random_injury(
                        {i["id"] for i in f.injuries})
                    f.injuries.append({"id": inj_id})
                except Exception:
                    break
        eng.fighters.append(f)

    eng.save()
    print(f"[save] after: {len(eng.fighters)} fighters")

    # Verify via reload
    eng2 = GameEngine()
    eng2.SAVE_PATH = real_save
    eng2.load()
    print(f"[verify] reloaded: {len(eng2.fighters)} fighters")
    from collections import Counter
    by_class = Counter(f.fighter_class for f in eng2.fighters)
    print(f"  classes: {dict(by_class)}")
    avg_level = sum(f.level for f in eng2.fighters) / len(eng2.fighters)
    print(f"  avg level: {avg_level:.1f}")
    injured = sum(1 for f in eng2.fighters if f.injuries)
    print(f"  injured: {injured}")
    print(f"  save file size: {os.path.getsize(real_save):,} bytes")


if __name__ == "__main__":
    main()
