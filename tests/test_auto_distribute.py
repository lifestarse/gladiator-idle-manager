# Build: 1
"""Auto-distribute tests — stat allocation by class profile, own-class perk
auto-unlock by tier, save/load roundtrip, level_up triggers when flag is on.
"""
import pytest

from game.engine import GameEngine
from game.models import Fighter, FIGHTER_CLASSES


@pytest.fixture(autouse=True)
def _engine_for_data(tmp_save_path):
    """Engine instance is required so FIGHTER_CLASSES gets wired from JSON."""
    GameEngine(save_path=tmp_save_path)


# ---------------------------------------------------------------------------
# Fighter.auto_distribute_stats — class-profile distribution
# ---------------------------------------------------------------------------

def test_default_flag_is_off():
    f = Fighter(fighter_class="mercenary")
    assert f.auto_distribute_enabled is False


def test_no_points_returns_zero():
    f = Fighter(fighter_class="berserker")
    f.unused_points = 0
    assert f.auto_distribute_stats() == 0


def test_spends_all_unused_points():
    f = Fighter(fighter_class="berserker")
    f.unused_points = 30
    spent = f.auto_distribute_stats()
    assert spent == 30
    assert f.unused_points == 0


def test_berserker_strength_dominant():
    """Berserker base 8/3/4 — STR should get the largest share."""
    f = Fighter(fighter_class="berserker")
    base = FIGHTER_CLASSES["berserker"]
    f.unused_points = 60
    f.auto_distribute_stats()
    str_gain = f.strength - base["base_str"]
    agi_gain = f.agility - base["base_agi"]
    vit_gain = f.vitality - base["base_vit"]
    assert str_gain > agi_gain and str_gain > vit_gain
    # 8/15 of 60 ≈ 32 ± rounding from greedy fill
    assert 28 <= str_gain <= 36


def test_tank_vitality_dominant():
    """Tank base 3/2/10 — VIT should dominate."""
    f = Fighter(fighter_class="tank")
    base = FIGHTER_CLASSES["tank"]
    f.unused_points = 60
    f.auto_distribute_stats()
    str_gain = f.strength - base["base_str"]
    agi_gain = f.agility - base["base_agi"]
    vit_gain = f.vitality - base["base_vit"]
    assert vit_gain > str_gain and vit_gain > agi_gain


def test_assassin_agility_dominant():
    """Assassin base 4/8/3 — AGI should dominate."""
    f = Fighter(fighter_class="assassin")
    base = FIGHTER_CLASSES["assassin"]
    f.unused_points = 60
    f.auto_distribute_stats()
    str_gain = f.strength - base["base_str"]
    agi_gain = f.agility - base["base_agi"]
    vit_gain = f.vitality - base["base_vit"]
    assert agi_gain > str_gain and agi_gain > vit_gain


def test_mercenary_balanced():
    """Mercenary base 5/5/5 — distribution should be near-even."""
    f = Fighter(fighter_class="mercenary")
    base = FIGHTER_CLASSES["mercenary"]
    f.unused_points = 30
    f.auto_distribute_stats()
    gains = [
        f.strength - base["base_str"],
        f.agility - base["base_agi"],
        f.vitality - base["base_vit"],
    ]
    # 30 / 3 = 10, all stats within 1 of each other
    assert max(gains) - min(gains) <= 1


def test_vitality_distribution_grows_max_hp():
    """Allocating to VIT must lift max_hp (verifies distribute_point HP path
    is used, not direct stat assignment)."""
    f = Fighter(fighter_class="tank")
    f.unused_points = 20
    hp_before = f.max_hp
    f.auto_distribute_stats()
    assert f.max_hp > hp_before


# ---------------------------------------------------------------------------
# Engine auto-unlock perks
# ---------------------------------------------------------------------------

def test_auto_unlock_buys_tier1_first(engine):
    """With 2 perk_points (1+1), only the two tier-1 perks unlock."""
    f = Fighter(fighter_class="mercenary")
    f.perk_points = 2
    engine.fighters.append(f)
    unlocked = engine._auto_unlock_perks(f)
    tiers = [p["tier"] for p in unlocked]
    assert tiers == [1, 1]
    assert f.perk_points == 0


def test_auto_unlock_skips_unaffordable(engine):
    """7 points buys tier-1 (1+1) and tier-2 (2+2) — totals 6. Remainder
    1 point cannot afford tier-3 (cost 3), so is left over."""
    f = Fighter(fighter_class="tank")
    f.perk_points = 7
    engine.fighters.append(f)
    unlocked = engine._auto_unlock_perks(f)
    assert sum(p["cost"] for p in unlocked) == 6
    assert f.perk_points == 1


def test_auto_unlock_only_own_class(engine):
    """A berserker with 100 perk_points only buys berserker perks (no
    cross-class auto-spending)."""
    f = Fighter(fighter_class="berserker")
    f.perk_points = 100
    engine.fighters.append(f)
    unlocked = engine._auto_unlock_perks(f)
    assert all(p["id"].startswith("berserk_") for p in unlocked)


def test_auto_unlock_skips_already_owned(engine):
    """Owned perks are not re-purchased."""
    f = Fighter(fighter_class="mercenary")
    f.perk_points = 2
    f.unlocked_perks.append("merc_iron_will")  # tier-1, cost 1
    engine.fighters.append(f)
    unlocked = engine._auto_unlock_perks(f)
    ids = [p["id"] for p in unlocked]
    assert "merc_iron_will" not in ids


# ---------------------------------------------------------------------------
# set_auto_distribute — toggle behavior
# ---------------------------------------------------------------------------

def test_toggle_on_immediately_distributes(engine):
    """Turning on with pending unused_points spends them immediately."""
    f = Fighter(fighter_class="berserker")
    f.unused_points = 12
    engine.fighters.append(f)
    engine.set_auto_distribute(0, True)
    assert f.auto_distribute_enabled is True
    assert f.unused_points == 0


def test_toggle_off_does_not_redistribute(engine):
    """Turning off leaves current stats untouched."""
    f = Fighter(fighter_class="tank")
    engine.fighters.append(f)
    engine.set_auto_distribute(0, True)
    str_after = f.strength
    engine.set_auto_distribute(0, False)
    assert f.auto_distribute_enabled is False
    assert f.strength == str_after


def test_dead_fighter_toggle_skips_distribution(engine):
    """Dead fighter: flag flips but distribution is skipped (no logs emitted)."""
    f = Fighter(fighter_class="mercenary")
    f.unused_points = 5
    f.alive = False
    engine.fighters.append(f)
    engine.set_auto_distribute(0, True)
    assert f.auto_distribute_enabled is True
    assert f.unused_points == 5  # untouched


# ---------------------------------------------------------------------------
# upgrade_gladiator hook
# ---------------------------------------------------------------------------

def test_upgrade_with_flag_off_keeps_pending_points(engine):
    """Without the flag, level_up leaves unused_points to player."""
    f = Fighter(fighter_class="mercenary")
    engine.fighters.append(f)
    engine.gold = 10**9
    engine.upgrade_gladiator(0)
    assert f.unused_points > 0


def test_upgrade_with_flag_on_distributes(engine):
    """With flag on, level_up spends the new points automatically."""
    f = Fighter(fighter_class="mercenary")
    f.unused_points = 0
    f.auto_distribute_enabled = True
    engine.fighters.append(f)
    engine.gold = 10**9
    engine.upgrade_gladiator(0)
    assert f.unused_points == 0


# ---------------------------------------------------------------------------
# Save/load roundtrip
# ---------------------------------------------------------------------------

def test_flag_persists_through_save_load(engine, tmp_save_path):
    f = Fighter(fighter_class="mercenary")
    f.auto_distribute_enabled = True
    engine.fighters.append(f)
    engine.save()

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.fighters[0].auto_distribute_enabled is True


def test_old_save_defaults_flag_off(engine, tmp_save_path):
    """Saves predating this feature — missing key defaults to False."""
    f = Fighter(fighter_class="mercenary")
    engine.fighters.append(f)
    engine.save()

    import json
    with open(tmp_save_path, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    # Strip the new field to simulate a pre-feature save.
    for fdict in data["fighters"]:
        fdict.pop("auto_distribute_enabled", None)
    with open(tmp_save_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp)

    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    assert eng2.fighters[0].auto_distribute_enabled is False
