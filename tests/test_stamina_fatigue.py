# Build: 1
"""Stamina/fatigue + auto-heal-injury tests.

Spec (PR2):
- 10 battles fought: stamina 100→0, fatigue 0, no penalty.
- 11th battle: fatigue 10, −10% stats applied (round()).
- 20th battle: fatigue 100, fighter is locked out from 21st.
- 5 skipped after fatigue=100: fatigue 100→0. Next 5 skipped: stamina 0→100.
- Injuries auto-heal at: minor 5, moderate 10, severe 15, permanent never.
- Save migration: missing stamina→100, fatigue→0, injuries get heal_progress=0.
"""
import pytest


# ---------- Direct Fighter unit tests ----------

def test_default_stamina_fatigue():
    from game.models import Fighter
    f = Fighter()
    assert f.stamina == 100
    assert f.fatigue == 0
    assert f.fatigue_mult == 1.0
    assert f.is_exhausted is False
    assert f.available is True


def test_stamina_drains_first_10_battles():
    from game.models import Fighter
    f = Fighter()
    for _ in range(10):
        f.apply_battle_fought()
    assert f.stamina == 0
    assert f.fatigue == 0
    # No penalty while fatigue=0.
    assert f.fatigue_mult == 1.0


def test_fatigue_accumulates_after_stamina_zero():
    from game.models import Fighter
    f = Fighter()
    for _ in range(11):
        f.apply_battle_fought()
    assert f.stamina == 0
    assert f.fatigue == 10
    assert abs(f.fatigue_mult - 0.9) < 1e-9


def test_lock_at_fatigue_100_blocks_availability():
    from game.models import Fighter
    f = Fighter()
    for _ in range(20):
        f.apply_battle_fought()
    assert f.fatigue == 100
    assert f.is_exhausted is True
    assert f.available is False
    assert f.fatigue_mult == 0.0


def test_fatigue_capped_at_100():
    from game.models import Fighter
    f = Fighter()
    for _ in range(50):
        f.apply_battle_fought()
    assert f.fatigue == 100  # clamped


def test_recovery_priority_fatigue_then_stamina():
    from game.models import Fighter
    f = Fighter()
    # Drain to fatigue 100.
    for _ in range(20):
        f.apply_battle_fought()
    assert f.stamina == 0 and f.fatigue == 100
    # 5 skipped → fatigue drains to 0 (stamina untouched).
    for _ in range(5):
        f.apply_battle_skipped()
    assert f.fatigue == 0
    assert f.stamina == 0
    # Next 5 skipped → stamina rises to 100.
    for _ in range(5):
        f.apply_battle_skipped()
    assert f.stamina == 100
    assert f.fatigue == 0


def test_recovery_clamped_at_max():
    from game.models import Fighter
    f = Fighter()
    # Already at max — extra rests are no-ops.
    for _ in range(10):
        f.apply_battle_skipped()
    assert f.stamina == 100
    assert f.fatigue == 0


# ---------- Penalty math with equipment ----------

def _equipped_attacker():
    """Fighter with a known equip bonus to verify penalty math."""
    from game.models import Fighter
    f = Fighter()
    # Strip class crit/dodge to keep math direct.
    f.equipment["weapon"] = {
        "id": "_test_sword", "name": "Test Sword", "slot": "weapon",
        "rarity": "rare", "str": 20, "agi": 0, "vit": 0,
        "upgrade_level": 0,
    }
    return f


def test_penalty_math_with_equipment_applies_to_total_stats():
    f = _equipped_attacker()
    base_atk = f.attack
    # With equipment, total_strength includes weapon's str=20.
    assert f.total_strength == f.strength + 20
    # Drive fighter to fatigue=20.
    for _ in range(12):
        f.apply_battle_fought()
    assert f.stamina == 0 and f.fatigue == 20
    expected = max(1, round(base_atk * 0.8))
    assert f.attack == expected, f"expected {expected}, got {f.attack}"


def test_penalty_math_50_percent():
    f = _equipped_attacker()
    base_atk = f.attack
    base_hp = f.max_hp
    base_def = f.defense
    # 5 + 10 = 15 fought; first 10 drain stamina, next 5 add fatigue=50.
    for _ in range(15):
        f.apply_battle_fought()
    assert f.fatigue == 50
    assert f.attack == max(1, round(base_atk * 0.5))
    assert f.max_hp == max(1, round(base_hp * 0.5))
    assert f.defense == max(0, round(base_def * 0.5))


# ---------- Injury auto-heal thresholds ----------

def _fighter_with_injury(severity, injury_id="_test_inj"):
    """Build a fighter holding a single injury of given severity, monkey-patched
    into the data_loader's by-id map for the test's lifetime."""
    from game.models import Fighter
    from game.data_loader import data_loader
    data_loader.load_all()
    data_loader.injuries_by_id[injury_id] = {
        "id": injury_id, "name": "TestInj", "severity": severity,
        "stat_penalties": [],
        "heal_cost_multiplier": 0 if severity == "permanent" else 1.0,
    }
    f = Fighter()
    f.injuries = [{"id": injury_id, "heal_progress": 0}]
    return f, injury_id


def test_injury_minor_heals_at_5_skips():
    f, _ = _fighter_with_injury("minor")
    for i in range(4):
        f.apply_battle_skipped()
        assert len(f.injuries) == 1, f"healed too early at skip #{i+1}"
    f.apply_battle_skipped()  # 5th skip
    assert f.injuries == []


def test_injury_moderate_heals_at_10_skips():
    f, _ = _fighter_with_injury("moderate")
    for _ in range(9):
        f.apply_battle_skipped()
    assert len(f.injuries) == 1
    f.apply_battle_skipped()
    assert f.injuries == []


def test_injury_severe_heals_at_15_skips():
    f, _ = _fighter_with_injury("severe")
    for _ in range(14):
        f.apply_battle_skipped()
    assert len(f.injuries) == 1
    f.apply_battle_skipped()
    assert f.injuries == []


def test_injury_permanent_never_heals():
    f, _ = _fighter_with_injury("permanent")
    for _ in range(50):
        f.apply_battle_skipped()
    assert len(f.injuries) == 1
    assert f.injuries[0]["id"].startswith("_test_inj")


# ---------- Save / load ----------

def test_save_load_roundtrip_stamina_fatigue(engine, tmp_save_path):
    engine.gold = 99999
    engine.hire_gladiator("mercenary")
    f = engine.fighters[0]
    f.stamina = 35
    f.fatigue = 60
    engine.save()

    from game.engine import GameEngine
    eng2 = GameEngine(save_path=tmp_save_path)
    eng2.load()
    f2 = eng2.fighters[0]
    assert f2.stamina == 35
    assert f2.fatigue == 60


def test_save_migration_legacy_defaults():
    """Old saves without stamina/fatigue default to 100 / 0."""
    from game.models import Fighter
    legacy = {
        "name": "Legacy", "fighter_class": "mercenary", "level": 1,
        "strength": 5, "agility": 5, "vitality": 5, "unused_points": 0,
        "alive": True, "hp": 50,
        "injuries": [{"id": "split_lip"}],  # legacy injury without heal_progress
    }
    f = Fighter.from_dict(legacy)
    assert f.stamina == 100
    assert f.fatigue == 0
    assert f.injuries[0]["heal_progress"] == 0


# ---------- Integration: battle_end event drives stamina/fatigue ----------

def test_battle_end_event_drains_stamina_for_participants(engine):
    import random
    engine.gold = 99999
    while len(engine.fighters) < 2:
        engine.hire_gladiator("mercenary")
    benched = engine.fighters[0]
    fighter = engine.fighters[1]
    benched.is_active = False

    random.seed(7)
    engine._spawn_enemy()
    engine.start_auto_battle()
    for _ in range(2000):
        if not engine.battle_active:
            break
        engine.battle_next_turn()

    # Participant lost 10 stamina; benched recovered nothing (already at max).
    assert fighter.stamina == 90 or not fighter.alive
    assert benched.stamina == 100
    assert benched.fatigue == 0
