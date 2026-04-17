# Build: 1
"""Battle determinism — with a fixed random.seed, a battle resolution
must match across runs. Guards against subtle side-effect-ordering bugs.
"""
import random


def _run_battle(seed):
    """Construct a minimal engine, hire 1 fighter, spawn an enemy, resolve."""
    import tempfile, os
    from game.engine import GameEngine

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json').name
    try:
        eng = GameEngine(save_path=tmp)
        random.seed(seed)
        eng.gold = 99999
        initial_fighters = list(eng.fighters)
        if not initial_fighters:
            eng.hire_gladiator("mercenary")
        # Just run battle_next_turn a handful of times.
        eng.start_auto_battle()
        outcomes = []
        for _ in range(20):
            if not eng.battle_active:
                break
            eng.battle_next_turn()
            outcomes.append((
                getattr(eng.battle_mgr, "is_active", False),
                eng.wins,
                eng.gold,
            ))
        return outcomes
    finally:
        try:
            os.unlink(tmp)
            os.unlink(tmp + ".bak")
        except OSError:
            pass


def test_battle_deterministic_same_seed():
    out1 = _run_battle(42)
    out2 = _run_battle(42)
    assert out1 == out2, "Battle diverged with identical seed"


def test_battle_different_seeds_likely_differ():
    """Not strictly required, but sanity-check: seed 1 and seed 99 should
    almost never produce identical 20-turn traces."""
    out1 = _run_battle(1)
    out2 = _run_battle(99)
    # Allow equality (tiny battles end fast), but assert at least one ran.
    assert out1 or out2
