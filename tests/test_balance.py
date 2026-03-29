# Build: 1
"""Balance and data integrity tests for game JSON data files."""
import json
import os
from collections import Counter

import pytest


RARITY_ORDER = ["common", "uncommon", "rare", "epic", "legendary"]


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────
# 1. All JSON files parse without errors
# ──────────────────────────────────────────────────────────────────
def test_all_json_files_valid(data_dir):
    json_files = [f for f in os.listdir(data_dir) if f.endswith(".json")]
    assert len(json_files) > 0, "No JSON files found in data directory"
    for fname in json_files:
        path = os.path.join(data_dir, fname)
        try:
            load_json(path)
        except json.JSONDecodeError as exc:
            pytest.fail(f"{fname} is not valid JSON: {exc}")


# ──────────────────────────────────────────────────────────────────
# 2. No duplicate weapon IDs
# ──────────────────────────────────────────────────────────────────
def test_no_duplicate_ids_weapons(data_dir):
    data = load_json(os.path.join(data_dir, "weapons.json"))
    ids = [item["id"] for item in data["items"]]
    dupes = [i for i, cnt in Counter(ids).items() if cnt > 1]
    assert dupes == [], f"Duplicate weapon ids: {dupes}"


# ──────────────────────────────────────────────────────────────────
# 3. No duplicate armor IDs
# ──────────────────────────────────────────────────────────────────
def test_no_duplicate_ids_armor(data_dir):
    data = load_json(os.path.join(data_dir, "armor.json"))
    ids = [item["id"] for item in data["items"]]
    dupes = [i for i, cnt in Counter(ids).items() if cnt > 1]
    assert dupes == [], f"Duplicate armor ids: {dupes}"


# ──────────────────────────────────────────────────────────────────
# 4. Equipment cost increases with rarity
# ──────────────────────────────────────────────────────────────────
def test_equipment_cost_increases_with_rarity(data_dir):
    all_items = []
    for fname in ("weapons.json", "armor.json", "accessories.json"):
        data = load_json(os.path.join(data_dir, fname))
        all_items.extend(data["items"])

    avg_cost_by_rarity = {}
    for rarity in RARITY_ORDER:
        costs = [it["cost"] for it in all_items if it["rarity"] == rarity]
        if costs:
            avg_cost_by_rarity[rarity] = sum(costs) / len(costs)

    prev_rarity = None
    for rarity in RARITY_ORDER:
        if rarity not in avg_cost_by_rarity:
            continue
        if prev_rarity is not None:
            assert avg_cost_by_rarity[rarity] > avg_cost_by_rarity[prev_rarity], (
                f"Average cost of {rarity} ({avg_cost_by_rarity[rarity]:.0f}) "
                f"should exceed {prev_rarity} ({avg_cost_by_rarity[prev_rarity]:.0f})"
            )
        prev_rarity = rarity


# ──────────────────────────────────────────────────────────────────
# 5. Weapon base_atk increases with rarity
# ──────────────────────────────────────────────────────────────────
def test_equipment_stats_increase_with_rarity(data_dir):
    weapons = load_json(os.path.join(data_dir, "weapons.json"))["items"]

    avg_atk_by_rarity = {}
    for rarity in RARITY_ORDER:
        atks = [w["base_atk"] for w in weapons if w["rarity"] == rarity]
        if atks:
            avg_atk_by_rarity[rarity] = sum(atks) / len(atks)

    prev_rarity = None
    for rarity in RARITY_ORDER:
        if rarity not in avg_atk_by_rarity:
            continue
        if prev_rarity is not None:
            assert avg_atk_by_rarity[rarity] > avg_atk_by_rarity[prev_rarity], (
                f"Average base_atk of {rarity} ({avg_atk_by_rarity[rarity]:.1f}) "
                f"should exceed {prev_rarity} ({avg_atk_by_rarity[prev_rarity]:.1f})"
            )
        prev_rarity = rarity


# ──────────────────────────────────────────────────────────────────
# 6. Enemy tier coverage — all T1-T100 present with correct counts
# ──────────────────────────────────────────────────────────────────
def test_enemy_tier_progression(data_dir):
    data = load_json(os.path.join(data_dir, "enemies.json"))
    all_enemies = data["enemies"]

    tiers = Counter(e["tier"] for e in all_enemies)
    # All 100 tiers should exist
    for tier in range(1, 101):
        assert tier in tiers, f"Missing tier {tier}"
        assert tiers[tier] == 6, f"Tier {tier}: expected 6 entries, got {tiers[tier]}"

    # All enemies should have required fields
    for e in all_enemies:
        assert "role" in e, f"Enemy {e.get('id')} missing 'role'"
        assert "stat_bias" in e, f"Enemy {e.get('id')} missing 'stat_bias'"
        assert e["role"] in ("swarm", "soldier", "bruiser", "elite", "assassin", "guardian")
        assert e["stat_bias"] in ("balanced", "str", "agi", "vit")


# ──────────────────────────────────────────────────────────────────
# 7. Exactly one boss per tier T1-T100
# ──────────────────────────────────────────────────────────────────
def test_boss_per_tier(data_dir):
    data = load_json(os.path.join(data_dir, "enemies.json"))
    bosses = [e for e in data["enemies"] if e.get("is_boss")]
    boss_tiers = Counter(b["tier"] for b in bosses)

    for tier in range(1, 101):
        assert boss_tiers.get(tier, 0) == 1, (
            f"Expected exactly 1 boss for tier {tier}, found {boss_tiers.get(tier, 0)}"
        )
    # All bosses must have a special_ability
    for b in bosses:
        assert b.get("special_ability"), f"Boss {b['id']} at tier {b['tier']} has no special_ability"


# ──────────────────────────────────────────────────────────────────
# 8. Injury severity distribution (±5 tolerance)
# ──────────────────────────────────────────────────────────────────
def test_injury_distribution(data_dir):
    data = load_json(os.path.join(data_dir, "injuries.json"))
    injuries = data["injuries"]

    severity_counts = Counter(inj["severity"] for inj in injuries)
    expected = {"minor": 40, "moderate": 30, "severe": 20, "permanent": 10}

    for severity, target in expected.items():
        actual = severity_counts.get(severity, 0)
        assert abs(actual - target) <= 5, (
            f"Severity '{severity}': expected ~{target}, got {actual} "
            f"(tolerance ±5)"
        )


# ──────────────────────────────────────────────────────────────────
# 9. Injury body parts balanced (12-20 each across 6 parts)
# ──────────────────────────────────────────────────────────────────
def test_injury_body_parts_balanced(data_dir):
    data = load_json(os.path.join(data_dir, "injuries.json"))
    injuries = data["injuries"]

    part_counts = Counter(inj["body_part"] for inj in injuries)
    assert len(part_counts) == 6, (
        f"Expected 6 body parts, found {len(part_counts)}: {list(part_counts.keys())}"
    )

    for part, count in part_counts.items():
        assert 12 <= count <= 20, (
            f"Body part '{part}' has {count} injuries (expected 12-20)"
        )


# ──────────────────────────────────────────────────────────────────
# 10. Specific existing items preserved with correct stats
# ──────────────────────────────────────────────────────────────────
def test_existing_items_preserved(data_dir):
    weapons = load_json(os.path.join(data_dir, "weapons.json"))["items"]
    armor = load_json(os.path.join(data_dir, "armor.json"))["items"]
    accessories = load_json(os.path.join(data_dir, "accessories.json"))["items"]
    relics = load_json(os.path.join(data_dir, "relics.json"))["items"]
    enchantments = load_json(os.path.join(data_dir, "enchantments.json"))["enchantments"]
    classes = load_json(os.path.join(data_dir, "fighter_classes.json"))["classes"]

    # Helper to find item by id across all equipment lists
    all_equipment = weapons + armor + accessories + relics
    items_by_id = {it["id"]: it for it in all_equipment}

    # rusty_blade: base_atk=3, cost=400
    assert "rusty_blade" in items_by_id, "rusty_blade not found"
    assert items_by_id["rusty_blade"]["base_atk"] == 3
    assert items_by_id["rusty_blade"]["cost"] == 400

    # dragonscale: base_def=25, cost=35000
    assert "dragonscale" in items_by_id, "dragonscale not found"
    assert items_by_id["dragonscale"]["base_def"] == 25
    assert items_by_id["dragonscale"]["cost"] == 35000

    # bone_charm: base_atk=2, base_def=2, cost=450
    assert "bone_charm" in items_by_id, "bone_charm not found"
    assert items_by_id["bone_charm"]["base_atk"] == 2
    assert items_by_id["bone_charm"]["base_def"] == 2
    assert items_by_id["bone_charm"]["cost"] == 450

    # cracked_idol: base_atk=2, cost=30
    assert "cracked_idol" in items_by_id, "cracked_idol not found"
    assert items_by_id["cracked_idol"]["base_atk"] == 2
    assert items_by_id["cracked_idol"]["cost"] == 30

    # bleeding enchantment: buildup_per_hit=20, threshold=100
    assert "bleeding" in enchantments, "bleeding enchantment not found"
    assert enchantments["bleeding"]["buildup_per_hit"] == 20
    assert enchantments["bleeding"]["threshold"] == 100

    # mercenary class: base_str=5, base_agi=5, base_vit=5
    assert "mercenary" in classes, "mercenary class not found"
    assert classes["mercenary"]["base_str"] == 5
    assert classes["mercenary"]["base_agi"] == 5
    assert classes["mercenary"]["base_vit"] == 5
