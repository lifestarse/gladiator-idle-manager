# Build: 1
"""Tests for mutator registry and reward multipliers (~10 tests)."""
import pytest

from game.mutators import MutatorRegistry, mutator_registry
from game.data_loader import data_loader


@pytest.fixture(autouse=True)
def ensure_data_loaded():
    """Ensure data_loader and mutator_registry are loaded for all tests."""
    data_loader.load_all()
    if not mutator_registry.get_all():
        mutator_registry.load(list(data_loader.mutators.values()))


# ---- 1. Registry loads ----

def test_registry_load():
    assert len(mutator_registry.get_all()) > 0


# ---- 2. Can retrieve by ID ----

def test_get_mutator():
    m = mutator_registry.get("fragile")
    assert m is not None
    assert m["id"] == "fragile"
    assert m["type"] == "negative"


# ---- 3. 15 negative mutators ----

def test_negative_count():
    negs = mutator_registry.get_all_negative()
    assert len(negs) == 15


# ---- 4. 5 positive mutators ----

def test_positive_count():
    pos = mutator_registry.get_all_positive()
    assert len(pos) == 5


# ---- 5. Negative mutators increase reward (mult > 1.0) ----

def test_reward_mult_negative():
    for m in mutator_registry.get_all_negative():
        assert m["reward_mult"] > 1.0, f"{m['id']} reward_mult should be > 1.0"


# ---- 6. Positive mutators decrease reward (mult < 1.0) ----

def test_reward_mult_positive():
    for m in mutator_registry.get_all_positive():
        assert m["reward_mult"] < 1.0, f"{m['id']} reward_mult should be < 1.0"


# ---- 7. Combined reward multiplier ----

def test_combined_reward_mult():
    # fragile (1.5) * poverty (1.5) = 2.25
    mult = mutator_registry.calc_reward_multiplier(["fragile", "poverty"])
    assert abs(mult - 2.25) < 0.01


# ---- 8. has_effect works ----

def test_has_effect():
    assert mutator_registry.has_effect(["fragile"], "incoming_damage_mult") is True
    assert mutator_registry.has_effect(["fragile"], "nonexistent_effect") is False
    assert mutator_registry.has_effect([], "incoming_damage_mult") is False


# ---- 9. get_effect_value works ----

def test_get_effect_value():
    val = mutator_registry.get_effect_value(["fragile"], "incoming_damage_mult")
    assert val == 1.3
    val = mutator_registry.get_effect_value(["fragile"], "nonexistent", default=42)
    assert val == 42


# ---- 10. Mutators save/load in engine ----

def test_mutators_save_load(engine):
    engine.active_mutators = ["fragile", "poverty"]
    save_data = engine.save()
    assert save_data["active_mutators"] == ["fragile", "poverty"]
    # Load it back
    engine.active_mutators = []
    engine.load(save_data)
    assert engine.active_mutators == ["fragile", "poverty"]
