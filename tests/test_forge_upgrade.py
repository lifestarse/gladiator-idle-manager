# Build: 2
"""Forge upgrade + enchant tests.

Covers the previously-untested paths:
- upgrade_item: shard debit, level increment, HP recompute when equipped
- max-level guard, insufficient-shards guard
- enchant_weapon: gold+shard debit, enchantment key set, counter incremented
- enchant slot guard (armor can't be enchanted)
"""
import pytest

from game.engine import GameEngine
import game.models as _m


def _find_weapon_template():
    """Pick any common weapon from loaded JSON data as a safe upgrade target."""
    for w in _m.FORGE_WEAPONS:
        if w.get("rarity") == "common":
            return w
    return _m.FORGE_WEAPONS[0] if _m.FORGE_WEAPONS else None


def _find_armor_template():
    for a in _m.FORGE_ARMOR:
        if a.get("rarity") == "common":
            return a
    return _m.FORGE_ARMOR[0] if _m.FORGE_ARMOR else None


# ---- upgrade_item ---------------------------------------------------------


def test_upgrade_increments_level_and_debits_shards(engine):
    tmpl = _find_weapon_template()
    if tmpl is None:
        pytest.skip("no weapons wired")
    item = dict(tmpl)
    item["upgrade_level"] = 0
    engine.inventory.append(item)
    # Enough shards for level 1 (weapon shard_multiplier=1, tier 1, count 1)
    engine.shards = {1: 10, 2: 10, 3: 10, 4: 10, 5: 10}

    result = engine.upgrade_item(item)

    assert result.ok, f"upgrade failed: {result.message}"
    assert item["upgrade_level"] == 1
    assert engine.shards[1] == 9  # one tier-1 shard spent


def test_upgrade_rejects_at_max_level(engine):
    tmpl = _find_weapon_template()
    if tmpl is None:
        pytest.skip("no weapons wired")
    item = dict(tmpl)
    # Common rarity maxes out at +5
    item["upgrade_level"] = 5
    engine.inventory.append(item)
    engine.shards = {1: 99, 2: 99, 3: 99, 4: 99, 5: 99}

    result = engine.upgrade_item(item)

    assert not result.ok
    assert result.code == "max_level"
    assert item["upgrade_level"] == 5  # unchanged


def test_upgrade_rejects_without_shards(engine):
    tmpl = _find_weapon_template()
    if tmpl is None:
        pytest.skip("no weapons wired")
    item = dict(tmpl)
    item["upgrade_level"] = 0
    engine.inventory.append(item)
    engine.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    result = engine.upgrade_item(item)

    assert not result.ok
    assert result.code == "not_enough_shards"
    assert item["upgrade_level"] == 0


def test_relic_upgrade_costs_10x_shards(engine):
    """Relic slot has shard_multiplier=10 — upgrading +1 should cost 10 tier-1 shards."""
    if not _m.RELICS:
        pytest.skip("no relics wired")
    # Pick first relic of any rarity
    relic_list = next(iter(_m.RELICS.values()))
    if not relic_list:
        pytest.skip("relic pool empty")
    item = dict(relic_list[0])
    item["upgrade_level"] = 0
    engine.inventory.append(item)
    engine.shards = {1: 20, 2: 0, 3: 0, 4: 0, 5: 0}

    result = engine.upgrade_item(item)

    assert result.ok, result.message
    assert item["upgrade_level"] == 1
    assert engine.shards[1] == 10  # 10 tier-1 shards spent (1 * multiplier 10)


def test_upgrade_equipped_weapon_keeps_owner_hp_consistent(engine):
    """Upgrading a weapon shouldn't break owner's HP (weapon grants no HP,
    but the owner-lookup branch in upgrade_item must not crash or reduce hp).

    Engine fixture starts with no fighters (load() is what seeds 'Vorn'),
    so hire one explicitly to give the upgrade an equipment owner to find.
    """
    tmpl = _find_weapon_template()
    if tmpl is None:
        pytest.skip("no weapons wired")
    engine.gold = 10**9
    engine.hire_gladiator("mercenary")
    fighter = engine.fighters[0]
    item = dict(tmpl)
    item["upgrade_level"] = 0
    fighter.equip_item(item)
    hp_before = fighter.hp
    engine.shards = {1: 10, 2: 10, 3: 10, 4: 10, 5: 10}

    result = engine.upgrade_item(fighter.equipment["weapon"])

    assert result.ok, result.message
    assert fighter.hp >= hp_before  # never regressed
    assert fighter.hp <= fighter.max_hp


# ---- enchant_weapon -------------------------------------------------------


def test_enchant_sets_key_and_debits_resources(engine):
    tmpl = _find_weapon_template()
    if tmpl is None or not _m.ENCHANTMENT_TYPES:
        pytest.skip("no weapons/enchantments wired")
    # Pick any enchantment; we'll pay whatever it costs
    ench_id, ench_def = next(iter(_m.ENCHANTMENT_TYPES.items()))
    item = dict(tmpl)
    engine.inventory.append(item)
    engine.gold = ench_def["cost_gold"] + 1000
    tier = ench_def["cost_shard_tier"]
    count = ench_def["cost_shard_count"]
    engine.shards = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    engine.shards[tier] = count + 5

    gold_before = engine.gold
    before_counter = engine.total_enchantments_applied

    result = engine.enchant_weapon(item, ench_id)

    assert result.ok, result.message
    assert item["enchantment"] == ench_id
    assert engine.gold == gold_before - ench_def["cost_gold"]
    assert engine.shards[tier] == 5
    assert engine.total_enchantments_applied == before_counter + 1


def test_enchant_rejects_non_weapon_slot(engine):
    """Armor can't be enchanted — slot guard must kick in before charging anything."""
    armor_tmpl = _find_armor_template()
    if armor_tmpl is None or not _m.ENCHANTMENT_TYPES:
        pytest.skip("no armor/enchantments wired")
    ench_id = next(iter(_m.ENCHANTMENT_TYPES))
    item = dict(armor_tmpl)
    engine.inventory.append(item)
    engine.gold = 10**9
    engine.shards = {1: 999, 2: 999, 3: 999, 4: 999, 5: 999}

    gold_before = engine.gold
    result = engine.enchant_weapon(item, ench_id)

    assert not result.ok
    assert result.code == "wrong_slot"
    assert "enchantment" not in item
    assert engine.gold == gold_before  # no charge


def test_enchant_rejects_unknown_enchantment(engine):
    tmpl = _find_weapon_template()
    if tmpl is None:
        pytest.skip("no weapons wired")
    item = dict(tmpl)
    engine.inventory.append(item)
    engine.gold = 10**9

    result = engine.enchant_weapon(item, "nonsense_ench_id")

    assert not result.ok
    assert result.code == "invalid_enchantment"


def test_enchant_rejects_without_gold(engine):
    tmpl = _find_weapon_template()
    if tmpl is None or not _m.ENCHANTMENT_TYPES:
        pytest.skip("no weapons/enchantments wired")
    ench_id, ench_def = next(iter(_m.ENCHANTMENT_TYPES.items()))
    item = dict(tmpl)
    engine.inventory.append(item)
    engine.gold = ench_def["cost_gold"] // 2  # definitely not enough
    engine.shards[ench_def["cost_shard_tier"]] = ench_def["cost_shard_count"] + 100

    result = engine.enchant_weapon(item, ench_id)

    assert not result.ok
    assert result.code == "not_enough_gold"
    assert item.get("enchantment") is None
