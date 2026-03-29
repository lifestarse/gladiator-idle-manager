# Build: 1
"""Tests for data loading and JSON schema validation (~10 tests)."""
import json
import os
import pytest

from game.data_loader import DataLoader, data_loader


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

JSON_FILES = [
    "weapons.json", "armor.json", "accessories.json", "relics.json",
    "enchantments.json", "fighter_classes.json", "fighter_names.json",
    "enemies.json", "injuries.json", "achievements.json", "lore.json",
    "boss_modifiers.json", "mutators.json", "prestige.json",
]


# ---- 1. All JSON files load without error ----

def test_all_json_loads():
    for fname in JSON_FILES:
        path = os.path.join(DATA_DIR, fname)
        assert os.path.exists(path), f"Missing data file: {fname}"
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        assert data is not None, f"Empty or invalid JSON: {fname}"


# ---- 2. No duplicate weapon IDs ----

def test_no_duplicate_weapon_ids():
    data_loader.load_all()
    ids = [w.get("id") for w in data_loader.weapons]
    assert len(ids) == len(set(ids)), f"Duplicate weapon IDs found"


# ---- 3. No duplicate armor IDs ----

def test_no_duplicate_armor_ids():
    data_loader.load_all()
    ids = [a.get("id") for a in data_loader.armor]
    assert len(ids) == len(set(ids)), f"Duplicate armor IDs found"


# ---- 4. No duplicate enemy IDs ----

def test_no_duplicate_enemy_ids():
    data_loader.load_all()
    ids = [e.get("id") for e in data_loader.enemies]
    assert len(ids) == len(set(ids)), f"Duplicate enemy IDs found"


# ---- 5. Enchantment schema ----

def test_enchantment_schema():
    data_loader.load_all()
    required = {"name", "buildup_per_hit", "threshold", "effect", "cost_gold",
                "cost_shard_tier", "cost_shard_count"}
    for eid, ench in data_loader.enchantments.items():
        for field in required:
            assert field in ench, f"Enchantment '{eid}' missing field '{field}'"


# ---- 6. Fighter class schema ----

def test_fighter_class_schema():
    data_loader.load_all()
    required = {"name", "base_str", "base_agi", "base_vit", "crit_bonus",
                "dodge_bonus", "hp_mult", "points_per_level"}
    for cid, cls in data_loader.fighter_classes.items():
        for field in required:
            assert field in cls, f"Class '{cid}' missing field '{field}'"


# ---- 7. Injury schema ----

def test_injury_schema():
    data_loader.load_all()
    for inj in data_loader.injuries:
        assert "body_part" in inj, f"Injury missing 'body_part': {inj.get('id', '?')}"
        assert "severity" in inj, f"Injury missing 'severity': {inj.get('id', '?')}"


# ---- 8. Boss modifier schema ----

def test_boss_modifier_schema():
    data_loader.load_all()
    for mid, mod in data_loader.boss_modifiers.items():
        assert "name" in mod, f"Boss modifier '{mid}' missing 'name'"
        assert "effect_type" in mod, f"Boss modifier '{mid}' missing 'effect_type'"


# ---- 9. Enemies cover all tiers T1-T100 ----

def test_enemies_cover_all_tiers():
    data_loader.load_all()
    tiers_present = set()
    for enemy in data_loader.enemies:
        tiers_present.add(enemy.get("tier"))
    for t in range(1, 101):
        assert t in tiers_present, f"No enemies for tier {t}"


# ---- 10. DataLoader is singleton ----

def test_data_loader_singleton():
    dl1 = DataLoader()
    dl2 = DataLoader()
    assert dl1 is dl2
