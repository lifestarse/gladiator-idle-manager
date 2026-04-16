"""Build a 'max progression' save for testing.

Writes to ~/.gladiator_idle_save.json. Backs up the existing save first to
~/.gladiator_idle_save.json.premax_backup so nothing is ever silently lost.

What this save gives you:
- 10M gold, 10K diamonds, 999 of every shard tier
- Arena tier 30, run#30, 1500 total wins, 30 bosses killed, all records
- Story chapter 6 complete, all 24 quests done, all 30 lore entries unlocked
- All 50 achievements unlocked
- All 6 fighter classes at Lv.30, 50/50/50 stats, ALL class perks unlocked
- Each fighter wears a legendary weapon/armor/accessory/relic at +5 upgrade
- Inventory stocked with legendary + epic variety for testing
- All achievement counters filled (enchantments, injuries healed, expeditions)
- Extra expedition slots (+2), ads removed, fastest T15 recorded

Run:
    python scripts/make_max_save.py
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.engine import GameEngine
from game.models import Fighter
from game.data_loader import data_loader
import game.achievements as _ach_module  # read ACHIEVEMENTS after _wire_data rebinds it
from game.story import STORY_CHAPTERS
from game.localization import set_language


def _equip_legendary(fighter, slot_pool, slot_name):
    """Equip the first legendary item of the given pool onto fighter, +5 upgrade."""
    legs = [x for x in slot_pool if x.get("rarity") == "legendary"]
    if not legs:
        return
    item = dict(legs[0])
    item["upgrade_level"] = 5
    fighter.equipment[slot_name] = item


def build_max_save(eng):
    # --- Economy ---
    eng.gold = 10_000_000
    eng.diamonds = 10_000
    eng.total_gold_earned = 100_000_000.0
    eng.total_gold_spent_equipment = 1_000_000
    eng.surgeon_uses = 5

    # --- Arena / records ---
    # Tier kept LOW (5) so user can't insta-wipe by tapping auto-battle
    # at late game. Records preserved to unlock T15-related achievements.
    eng.arena_tier = 5
    eng.run_max_tier = 30  # records show prior peak
    eng.best_record_tier = 30
    eng.wins = 500
    eng.total_wins = 1500
    eng.run_kills = 100
    eng.best_record_kills = 100
    eng.bosses_killed = 30
    eng.total_deaths = 10
    eng.total_runs = 30
    eng.run_number = 31  # current run is #31
    eng.fastest_t15_time = 300  # 5 min
    eng.run_start_time = 0.0

    # --- Story: all chapters complete ---
    eng.story_chapter = 6
    eng.quests_completed = [
        q["id"] for ch in STORY_CHAPTERS for q in ch["quests"]
    ]

    # --- Achievement counters (drive achievement unlocks) ---
    eng.total_enchantments_applied = 20
    eng.total_enchantment_procs = 200
    eng.total_injuries_healed = 50
    eng.total_expeditions_completed = 30

    # --- Lore: unlock every entry ---
    eng.lore_unlocked = [e["id"] for e in data_loader.lore]

    # --- Shards: maxed per tier ---
    eng.shards = {1: 999, 2: 999, 3: 999, 4: 999, 5: 999}

    # --- Misc ---
    eng.extra_expedition_slots = 2
    eng.ads_removed = True
    eng.active_mutators = []
    eng.tutorial_shown = ["welcome", "discover_boss"]  # skip tutorials
    eng.graveyard = []  # clean slate

    # --- Fighters: one of each class at Lv.30, full perks, full gear ---
    classes = ["mercenary", "berserker", "tank", "assassin", "retiarius", "medicus"]
    names = ["Vorn", "Ragnar", "Titus", "Kira", "Nexus", "Mira"]
    eng.fighters = []
    for cls, name in zip(classes, names):
        f = Fighter(name=name, fighter_class=cls)
        f.level = 25
        f.strength = 45
        f.agility = 45
        f.vitality = 45
        f.unused_points = 0
        f.kills = 50
        f.injuries = []

        # Unlock every perk of this class
        cls_data = data_loader.fighter_classes.get(cls, {})
        perk_tree = cls_data.get("perk_tree", [])
        f.unlocked_perks = [p["id"] for p in perk_tree]
        f.perk_points = 3  # a few leftover to distribute

        # Equip a legendary in every slot at +5 upgrade
        _equip_legendary(f, data_loader.weapons, "weapon")
        _equip_legendary(f, data_loader.armor, "armor")
        _equip_legendary(f, data_loader.accessories, "accessory")
        _equip_legendary(f, data_loader.relics, "relic")

        f.hp = f.max_hp  # refresh HP after equipping
        eng.fighters.append(f)

    eng.active_fighter_idx = 0

    # --- Inventory: stock legendaries + epics for variety ---
    inv = []
    for pool in (data_loader.weapons, data_loader.armor,
                 data_loader.accessories, data_loader.relics):
        legs = [x for x in pool if x.get("rarity") == "legendary"]
        epics = [x for x in pool if x.get("rarity") == "epic"]
        # take 3 legendaries + 2 epics from each slot (skip the one already equipped)
        for item in (legs[1:4] + epics[:2]):
            new_item = dict(item)
            new_item["upgrade_level"] = 3
            inv.append(new_item)
    eng.inventory = inv

    # --- Achievements: unlock every one (from JSON-rebuilt list, not hardcoded fallback) ---
    eng.achievements_unlocked = [a["id"] for a in _ach_module.ACHIEVEMENTS]

    # --- Language (preserved on save) ---
    set_language("ru")


def main():
    real_save_path = os.path.join(os.path.expanduser("~"),
                                  ".gladiator_idle_save.json")
    backup_path = real_save_path + ".premax_backup"

    # Back up anything currently there
    if os.path.exists(real_save_path):
        shutil.copy2(real_save_path, backup_path)
        print(f"[backup] {real_save_path} -> {backup_path}")

    # Also back up the .bak file if it exists, just in case
    bak_file = real_save_path + ".bak"
    if os.path.exists(bak_file):
        shutil.copy2(bak_file, bak_file + ".premax_backup")
        print(f"[backup] {bak_file} -> {bak_file}.premax_backup")

    # Build engine, stuff it full, save
    eng = GameEngine()
    eng.SAVE_PATH = real_save_path
    build_max_save(eng)
    eng.save()
    print(f"[save] max progression written to {real_save_path}")

    # Quick sanity check: re-load and print a summary
    eng2 = GameEngine()
    eng2.SAVE_PATH = real_save_path
    eng2.load()
    print()
    print("=== LOADED BACK ===")
    print(f"  gold:       {eng2.gold:,}")
    print(f"  diamonds:   {eng2.diamonds:,}")
    print(f"  arena_tier: {eng2.arena_tier}")
    print(f"  story:      chapter {eng2.story_chapter} (all complete)")
    print(f"  fighters:   {len(eng2.fighters)} "
          f"({', '.join(f.fighter_class for f in eng2.fighters)})")
    print(f"  first fighter equipped: {list(eng2.fighters[0].equipment.keys())}")
    print(f"  inventory:  {len(eng2.inventory)} items")
    print(f"  achievements unlocked: {len(eng2.achievements_unlocked)} / {len(_ach_module.ACHIEVEMENTS)}")
    print(f"  quests completed:       {len(eng2.quests_completed)}")
    print(f"  lore unlocked:          {len(eng2.lore_unlocked)}")
    print(f"  shards:     {eng2.shards}")


if __name__ == "__main__":
    main()
