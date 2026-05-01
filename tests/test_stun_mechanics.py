# Build: 1
"""Net Throw stun mechanics: hold-skill (no cooldown burn when held)
and boss post-stun immunity (anti-permastun guard).

Both originate from the same change:
- A held skill (stun against an already-stunned/immune target) used to
  burn its full 5-turn cooldown because the caller blanket-overwrote
  the cooldown after _execute_skill returned. With many retiarii vs a
  boss, only one of N actually applied stun per cycle.
- After fixing the hold, multiple retiarii would chain stun on a boss
  indefinitely. Immunity caps boss downtime at ~40% (with stun_turns=2,
  immunity=4: 5-turn cycle = 2 stun + 3 boss attacks).
"""
import random
import tempfile
import os

import pytest

from game.engine import GameEngine
from game.models import Fighter, Boss
from game.constants import BOSS_STUN_IMMUNITY_TURNS


@pytest.fixture
def boss_fight_engine(tmp_save_path):
    """Engine seeded for a deterministic boss fight. Caller picks fighters."""
    random.seed(42)
    eng = GameEngine(save_path=tmp_save_path)
    eng.gold = 1_000_000
    eng.fighters = []  # blow away default Vorn
    return eng


def _add_retiarii(eng, n):
    for _ in range(n):
        eng.fighters.append(Fighter(fighter_class="retiarius"))


def _add_mercenaries(eng, n):
    for _ in range(n):
        eng.fighters.append(Fighter(fighter_class="mercenary"))


def _start_boss(eng):
    eng.spawn_boss_enemy()
    eng.start_boss_fight()
    # First do_turn() consumes BOSS_INTRO and seeds turn 1
    eng.battle_next_turn()
    return eng.battle_mgr


def test_held_stun_keeps_cooldown_at_zero(boss_fight_engine):
    """When the boss is already stunned, additional retiarii must hold
    their skill — not burn the 5-turn cooldown like the first one did.
    """
    eng = boss_fight_engine
    _add_retiarii(eng, 3)
    mgr = _start_boss(eng)
    cooldown = mgr.state.skill_states[id(eng.fighters[0])].skill_def["cooldown"]

    eng.battle_next_turn()  # turn that runs the skill phase

    boss = mgr.state.enemies[0]
    assert mgr.state.enemy_stuns.get(id(boss), 0) > 0, "boss should be stunned"

    cds = [mgr.state.skill_states[id(f)].cooldown_remaining
           for f in eng.fighters]
    fired = [c for c in cds if c == cooldown]
    held = [c for c in cds if c == 0]
    assert len(fired) == 1, f"exactly one retiarius should have fired: {cds}"
    assert len(held) == 2, f"the rest must hold (CD=0): {cds}"


def test_boss_gets_immunity_after_stun_ends(boss_fight_engine):
    """Stun decrements to 0 in the enemy phase — that transition must
    set BOSS_STUN_IMMUNITY_TURNS, only on bosses.
    """
    eng = boss_fight_engine
    _add_retiarii(eng, 1)
    mgr = _start_boss(eng)
    boss = mgr.state.enemies[0]
    boss.hp = 999_999_999  # don't let the test die to a victory before we check

    eng.battle_next_turn()  # retiarius fires → stun=2
    assert mgr.state.enemy_stuns[id(boss)] == 1  # decremented in enemy phase

    eng.battle_next_turn()  # stun → 0, immunity should be set
    # Tick at end-of-turn drops immunity by one already.
    assert mgr.state.enemy_stuns.get(id(boss), 0) == 0
    assert mgr.state.enemy_stun_immunity.get(id(boss), 0) == BOSS_STUN_IMMUNITY_TURNS - 1


def test_normal_mob_gets_no_immunity(boss_fight_engine):
    """Immunity is boss-only — regular arena fights must not set it."""
    eng = boss_fight_engine
    _add_retiarii(eng, 1)
    eng.preview_enemies = []  # force fresh spawn in start_auto_battle
    eng.start_auto_battle()
    eng.battle_next_turn()  # consume STARTING

    mgr = eng.battle_mgr
    enemy = mgr.state.enemies[0]
    enemy.hp = 999_999_999

    # Drive 3 turns: skill fires, stun ticks down, ends.
    for _ in range(3):
        eng.battle_next_turn()

    assert mgr.state.is_boss_fight is False
    assert mgr.state.enemy_stun_immunity == {}, \
        "non-boss fights must never accumulate stun immunity"


def test_no_permastun_with_many_retiarii(boss_fight_engine):
    """With N retiarii vs boss, the boss must get attack turns —
    no permastun. Verify boss successfully attacks at least once over
    a 20-turn window (immunity window is 4 turns; cycle is 5).
    """
    eng = boss_fight_engine
    _add_retiarii(eng, 20)
    # A meaningful test needs the boss alive. Pump HP so 20 retiarii
    # don't kill it inside the observation window.
    mgr = _start_boss(eng)
    boss = mgr.state.enemies[0]
    boss.hp = boss.max_hp = 10_000_000_000
    # Tank fighters too so the boss has someone to swing at.
    for f in eng.fighters:
        f.hp = 1_000_000  # max_hp is a derived property

    boss_attack_turns = 0
    boss_stun_turns = 0
    for _ in range(20):
        eng.battle_next_turn()
        if mgr.state.enemy_stuns.get(id(boss), 0) > 0:
            boss_stun_turns += 1
        else:
            boss_attack_turns += 1

    assert boss_attack_turns > 0, \
        "boss never attacked — permastun regression"
    # With 20 retiarii cycling, immunity must mean roughly half the
    # turns the boss is free. Loose bound: at least 1/4.
    assert boss_attack_turns >= 5, \
        f"boss free turns too low ({boss_attack_turns}/20) — immunity too short?"


def test_stun_resumes_after_immunity_window(boss_fight_engine):
    """After the immunity window ends, retiarius can stun again."""
    eng = boss_fight_engine
    _add_retiarii(eng, 1)
    mgr = _start_boss(eng)
    boss = mgr.state.enemies[0]
    boss.hp = boss.max_hp = 10_000_000_000
    for f in eng.fighters:
        f.hp = 1_000_000  # max_hp is a derived property

    # Drive enough turns to: stun (2) + immunity (4) + retiarius CD (5)
    # → second stun should land within ~12 turns even with the slowest path.
    second_stun_seen = False
    first_immunity_seen = False
    for _ in range(15):
        eng.battle_next_turn()
        if mgr.state.enemy_stun_immunity.get(id(boss), 0) > 0:
            first_immunity_seen = True
        elif first_immunity_seen and mgr.state.enemy_stuns.get(id(boss), 0) > 0:
            second_stun_seen = True
            break

    assert first_immunity_seen, "immunity never engaged"
    assert second_stun_seen, "stun never resumed after immunity window"
