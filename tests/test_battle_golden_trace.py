# Build: 1
"""Fine-grained golden traces of a battle — the instrument that makes a
refactor of the combat hot path verifiable.

`tests/test_battle_determinism.py` compares only `(is_active, wins, gold)`
over 20 turns. That is enough to catch "the battle broke" and blind to
everything that actually goes wrong in a refactor: damage applied in a
different order, a lifesteal tick lost, an RNG draw inserted or removed so
every later roll shifts, an event emitted twice. This test records the whole
resolution — every event field and every unit's HP after every turn — and
compares it against a committed baseline.

Two traces, because the two attack phases have different shapes:

* ``arena`` — a squad of four against five ordinary enemies. Covers crits,
  dodges (and therefore the dodge-counter path), kills, skill activation,
  status ticks and victory.
* ``boss`` — the same squad against a boss carrying an explicit modifier set,
  so ``BossModifierHandler.on_turn_start`` / ``on_boss_hit`` /
  ``on_boss_attack_pre`` all run, including thorns reflecting damage back
  into the attacker inside the player attack phase.

Deliberately isolated from game content. Fighters carry explicit names and
SYNTHETIC equipment whose ids exist in no data file, so the traces depend on
the combat code and the tuning constants and on nothing else. Adding items,
rebalancing items or giving items passive effects cannot move them — if this
test goes red, combat behaviour changed.

The one content dependency left is `data/boss_modifiers.json` params, read by
the boss trace. Retuning those numbers is a deliberate balance act and moving
this trace is the correct consequence.

Re-record only with a reason, by running this file directly:

    python tests/test_battle_golden_trace.py --record

Every re-record is a claim that the behaviour change was intended. Read the
diff first.
"""
import contextlib
import json
import os
import random

import pytest

BASELINE = os.path.join(os.path.dirname(__file__), "data",
                        "battle_golden_trace.json")

# Fixed so a trace never depends on which language happens to be loaded.
TRACE_LANG = "en"

MAX_TURNS = 80
# Chosen by search, not taste. Together with the tiers below, this seed drives
# the arena fight to victory and the boss fight to defeat, lands ripostes,
# thorns reflections and fighter knockouts, and — the part that took the
# search — leaves the traces sensitive to every single perk channel the
# on-hit / on-kill code reads. `test_traces_are_sensitive_to_each_perk_channel`
# proves that property instead of trusting it, so a future re-record cannot
# quietly settle on a seed where, say, on_kill_heal_pct never changes an
# outcome because every killing blow happens to land at full HP.
SEED = 7

# Synthetic gear: these ids are in no data file, so no content change and no
# item passive can ever reach them. Runtime item shape (post-normalize) is a
# plain dict with str/agi/vit — see game/data_loader/loadmethodsmixin.py.
_GEAR = {
    "weapon": {"id": "__trace_weapon__", "name": "Trace Blade",
               "slot": "weapon", "rarity": "rare", "cost": 0,
               "str": 12, "agi": 0, "vit": 0, "upgrade_level": 3},
    "armor": {"id": "__trace_armor__", "name": "Trace Mail",
              "slot": "armor", "rarity": "rare", "cost": 0,
              "str": 0, "agi": 2, "vit": 9, "upgrade_level": 2},
    "accessory": {"id": "__trace_charm__", "name": "Trace Charm",
                  "slot": "accessory", "rarity": "uncommon", "cost": 0,
                  "str": 0, "agi": 4, "vit": 2, "upgrade_level": 1},
}

# Five classes whose passive_ability is actually implemented, each carrying
# explicit perks. The perks are not decoration: between them they light up
# every key `BattleManager._fighter_stats` snapshots — lifesteal_pct,
# on_kill_heal_pct, regen_per_turn_pct, on_dodge_counter, bonus_gold_pct,
# damage_reduction — which is exactly the set the on-hit / on-kill code paths
# read. With an unperked squad those branches never run and the trace cannot
# tell a working lifesteal from a deleted one.
#
# ret_riposte and med_resurgence are `*_upgrade` perks, so the override
# semantics in get_perk_effects (upgrade REPLACES the base sum) are covered
# too.
#
# `berserker` is deliberately absent: its passive `damage_bonus_on_low_hp` is
# declared in data/fighter_classes.json and read by no code today, so a
# berserker here would move these traces the moment that gets wired up.
_SQUAD = [
    ("Trace-Merc", "mercenary", ["merc_sellsword_mastery",     # lifesteal_pct
                                 "merc_coin_hunter",           # bonus_gold_pct
                                 "merc_iron_will"]),           # damage_reduction
    ("Trace-Assassin", "assassin", ["assa_throat_cutter"]),    # on_kill_heal_pct
    ("Trace-Tank", "tank", ["tank_undying",                    # lifesteal_pct
                            "tank_iron_body"]),          # reduce_injury_severity
    ("Trace-Retiarius", "retiarius", ["ret_riposte"]),   # on_dodge_counter_upgrade
    ("Trace-Medicus", "medicus", ["med_resurgence"]),   # regen_per_turn_pct_upgrade
]

_FIGHTER_LEVEL = 4
_ARENA_TIER = 10
_ARENA_ENEMIES = 5
_BOSS_ARENA_TIER = 8

# Every key `BattleManager._fighter_stats` snapshots that the attack phases
# actually branch on. The sensitivity test zeroes each in turn and requires
# the trace to move — that is what proves the baseline exercises the branch.
_PERK_CHANNELS = (
    "lifesteal_pct",
    "on_kill_heal_pct",
    "regen_per_turn_pct",
    "bonus_gold_pct",
    "damage_reduction",
    "on_dodge_counter_pct",
)
# Explicit, not random.sample: assign_modifiers draws from the global RNG and
# would make the trace depend on how many draws everything before it consumed.
_BOSS_MODIFIERS = ["thorns", "regeneration", "enrage"]


def _squad(engine, tier):
    """Populate `engine` with the fixed squad. Consumes no randomness: every
    name is explicit, so seeding immediately before the turn loop is enough
    to pin the whole trace."""
    from game.models import Fighter

    engine.arena_tier = tier
    engine.gold = 0
    engine.wins = 0

    fighters = []
    for name, cls, perks in _SQUAD:
        f = Fighter(name=name, level=_FIGHTER_LEVEL, fighter_class=cls)
        f.unused_points = 0
        f.unlocked_perks = list(perks)
        for slot, item in _GEAR.items():
            f.equipment[slot] = dict(item)
        f.hp = f.max_hp
        fighters.append(f)
    engine.fighters[:] = fighters
    return fighters


def _mask_tables():
    """Content-derived names that get interpolated into battle messages.

    Why this exists: `DataLoader.apply_translations` overwrites skill / passive
    / perk / injury / boss-modifier names IN PLACE on the module-level
    collections, and `apply_translations("en")` returns early — so once
    anything in the session has switched content to another language, the
    English names are gone and cannot be restored without reloading every data
    file. `GameEngine.load` applies the saved language (see
    game/engine/persistencereadmixin.py:155) and the default is `ru`, so
    whether content is English depends on which tests ran first. Pinning the
    UI language does not help: `set_language` fixes the `t()` template and does
    nothing for the names substituted into it.

    Masking those names makes the trace invariant under content translation
    while still comparing the rest of every message verbatim.

    Returns (always, boss_intro_only).

    The split is not fussiness. Boss-modifier names collide with literal
    English template text — `boss_thorns` is "Thorns! {attacker} takes {dmg}
    damage!" and `boss_shield_absorb` is "Shield absorbs {dmg}!" — where the
    name is NOT interpolated and the word belongs to the template. Masking
    those globally would rewrite template text and make the trace differ
    between an English-content run and a translated-content run, which is the
    exact bug this masking is here to prevent. Modifier names are only ever
    interpolated in the boss-intro line built by
    `BattleManager.start_boss_fight`, so that is the only place they are masked.

    Item and enemy names are absent on purpose: `apply_translations` skips
    `name` for both (its `skip=("name",)` calls), so they are already
    translation-proof.
    """
    import game.models as models
    from game.data_loader import data_loader

    always = []
    for cls_data in models.FIGHTER_CLASSES.values():
        for holder, tag in ((cls_data.get("active_skill"), "<skill>"),
                            (cls_data.get("passive_ability"), "<passive>")):
            if isinstance(holder, dict) and holder.get("name"):
                always.append((holder["name"], tag))
        for perk in cls_data.get("perk_tree", []):
            if perk.get("name"):
                always.append((perk["name"], "<perk>"))
    for injury in data_loader.injuries:
        if injury.get("name"):
            always.append((injury["name"], "<injury>"))

    boss_intro_only = [(mod["name"], "<mod>")
                       for mod in data_loader.boss_modifiers.values()
                       if isinstance(mod, dict) and mod.get("name")]

    # Longest first: a name that contains another must be masked before it.
    for table in (always, boss_intro_only):
        table.sort(key=lambda pair: -len(pair[0]))
    return always, boss_intro_only


def _mask(message, table):
    for name, tag in table:
        if name in message:
            message = message.replace(name, tag)
    return message


def _event_row(ev, tables):
    always, boss_intro_only = tables
    message = _mask(ev.message, always)
    if ev.event_type == "boss_intro":
        message = _mask(message, boss_intro_only)
    return [
        ev.event_type, ev.attacker, ev.defender, ev.damage,
        bool(ev.is_kill), bool(ev.is_crit), bool(ev.is_boss),
        bool(ev.is_dodge), ev.skill_type, message,
    ]


def _drive(engine, start_events):
    """Run the fight to its end (or MAX_TURNS) and return the trace body."""
    mgr = engine.battle_mgr
    tables = _mask_tables()
    trace = {
        "seed": SEED,
        "lang": TRACE_LANG,
        "start_events": [_event_row(e, tables) for e in start_events],
        "turns": [],
    }
    random.seed(SEED)
    for _ in range(MAX_TURNS):
        if not mgr.is_active:
            break
        events, result = mgr.do_turn()
        trace["turns"].append({
            "n": mgr.state.turn_number,
            "events": [_event_row(e, tables) for e in events],
            "fighters": [[f.name, f.hp, f.alive, len(f.injuries)]
                         for f in mgr.state.player_fighters],
            "enemies": [[e.name, e.hp, e.attack, e.defense]
                        for e in mgr.state.enemies],
            "outcome": result.outcome,
            "gold_earned": result.gold_earned,
            "wins": engine.wins,
            "engine_gold": engine.gold,
        })
    trace["final_outcome"] = (trace["turns"][-1]["outcome"]
                              if trace["turns"] else "none")
    return trace


def _record_arena(engine):
    from game.models import Enemy

    _squad(engine, _ARENA_TIER)
    # One opponent per fighter, so start_auto_battle never falls through to its
    # data_loader top-up branch. Names are overridden: Enemy() takes its name
    # from ENEMY_TITLES by tier, so all five would be called the same thing and
    # the trace could not say which one was hit.
    enemies = []
    for i in range(_ARENA_ENEMIES):
        enemy = Enemy(tier=_ARENA_TIER)
        enemy.name = f"Trace-Foe-{i + 1}"
        enemies.append(enemy)
    engine.preview_enemies[:] = enemies
    return _drive(engine, engine.battle_mgr.start_auto_battle())


def _record_boss(engine):
    from game.models import Boss

    _squad(engine, _BOSS_ARENA_TIER)
    boss = Boss(_BOSS_ARENA_TIER)
    # get_boss_name() picks by tier from a name table; pinning it keeps the
    # trace readable and independent of that table.
    boss.name = "Trace-Boss"
    boss.modifiers = list(_BOSS_MODIFIERS)
    engine.current_enemy = boss
    engine.preview_enemies[:] = [boss]
    return _drive(engine, engine.battle_mgr.start_boss_fight())


@contextlib.contextmanager
def _pinned_lang():
    """Pin the UI language to TRACE_LANG for the duration.

    Anything that reads a battle message has to run inside this, recording
    AND assertions alike: the default language is `ru`, so a matcher built
    outside the block would compare a Russian template against an English
    trace and silently find nothing.
    """
    from game import localization

    prev = localization.get_language()
    localization.set_language(TRACE_LANG)
    try:
        yield
    finally:
        localization.set_language(prev)


def _record_all(engine):
    """Both traces, with the language pinned for the duration."""
    with _pinned_lang():
        return {"arena": _record_arena(engine), "boss": _record_boss(engine)}


def _flags(trace):
    return [row for turn in trace["turns"] for row in turn["events"]]


def _template_fragments(key, **placeholders):
    """Literal fragments of a localized template, placeholders removed.

    Lets a coverage assertion recognise "this message came from `battle_counter`"
    without hardcoding the English wording — if the string is retranslated or
    reworded, the matcher follows it instead of going stale.
    """
    import re
    from game.localization import t

    sentinel = "\x00"
    filled = t(key, **{name: sentinel for name in placeholders})
    return [frag for frag in re.split(re.escape(sentinel), filled) if frag.strip()]


def _count_from_template(rows, key, *placeholders):
    with _pinned_lang():
        frags = _template_fragments(key, **{p: None for p in placeholders})
    assert frags, f"template {key!r} has no literal text to match on"
    return sum(1 for row in rows if all(f in row[9] for f in frags))


def _assert_arena_meaningful(trace):
    """A trace that resolves in two dodgeless turns guards nothing."""
    rows = _flags(trace)
    kinds = {row[0] for row in rows}
    assert len(trace["turns"]) >= 8, "arena trace too short to be a baseline"
    assert "attack" in kinds, "no attacks in arena trace"
    assert "death" in kinds, "no kills in arena trace"
    assert "skill" in kinds, "no skill activation in arena trace"
    assert any(row[5] for row in rows), "no crit in arena trace"
    assert any(row[7] for row in rows), "no dodge in arena trace"
    assert trace["final_outcome"] == "victory", \
        "arena trace must end in victory so _declare_victory is covered"


def _assert_boss_meaningful(trace):
    rows = _flags(trace)
    assert len(trace["turns"]) >= 6, "boss trace too short to be a baseline"
    assert any(row[6] for row in rows), "nothing flagged is_boss in boss trace"
    assert any(row[0] == "status" for row in rows), \
        "no status events in boss trace — boss modifiers never fired"
    assert trace["final_outcome"] == "defeat", \
        "boss trace must end in defeat so the defeat tail is covered"


def test_golden_traces_match_baseline(engine):
    """Both recorded battles resolve exactly as they did when the baseline
    was committed. See the module docstring before re-recording."""
    assert os.path.exists(BASELINE), (
        f"missing baseline {BASELINE} — record it with "
        "`python tests/test_battle_golden_trace.py --record`")
    with open(BASELINE, encoding="utf-8") as fh:
        expected = json.load(fh)
    actual = _record_all(engine)

    for name in ("arena", "boss"):
        if actual[name] != expected.get(name):
            pytest.fail(
                f"{name} battle trace diverged from the committed baseline.\n"
                f"{_first_divergence(expected.get(name, {}), actual[name])}\n"
                "If this change was intended, re-record with "
                "`python tests/test_battle_golden_trace.py --record` and say "
                "why in the commit message.")


def test_baselines_are_meaningful(engine):
    """Guard the guard: baselines recorded from trivial fights would pass
    forever without proving anything."""
    traces = _record_all(engine)
    _assert_arena_meaningful(traces["arena"])
    _assert_boss_meaningful(traces["boss"])


def test_traces_cover_the_paths_they_claim_to(engine):
    """Pin the code paths the seed was chosen for.

    Without this, a re-record could drift onto a seed where the retiarius
    never dodges or nobody is knocked out, and the traces would keep passing
    while silently covering less. Each branch below is one this project is
    about to refactor, so losing its coverage has to be loud.
    """
    traces = _record_all(engine)
    rows = _flags(traces["arena"]) + _flags(traces["boss"])

    assert _count_from_template(rows, "battle_counter",
                                "defender", "attacker", "dmg"), \
        "_apply_dodge_counter never produced an event — riposte path uncovered"
    assert _count_from_template(rows, "boss_thorns", "attacker", "dmg"), \
        "boss thorns never fired — on_boss_hit path uncovered"
    knockouts = _count_from_template(rows, "knocked_out_injury",
                                     "name", "injury")
    permadeaths = _count_from_template(rows, "fallen_forever", "name")
    assert knockouts + permadeaths, \
        "no fighter went down — handle_fighter_death path uncovered"
    assert any(row[0] == "skill" for row in rows), \
        "no active skill fired — _execute_skill path uncovered"


def test_trace_is_invariant_under_content_translation(engine, tmp_path):
    """The same battle must trace identically with Russian content loaded.

    Not hypothetical: `GameEngine.load` applies the saved language and the
    default is `ru`, so whether `FIGHTER_CLASSES` holds English or Russian
    skill names when this file runs depends on which tests ran before it.
    Without the masking in `_mask_tables` the baseline passes standalone and
    fails under `pytest -q`, or the reverse — the worst possible failure mode
    for a guard whose whole job is to be trusted.

    The translated run happens in a subprocess because
    `apply_translations` mutates the module-level collections in place and
    `apply_translations("en")` cannot undo it; doing it in-process would leak
    Russian content into every test that follows.
    """
    import subprocess
    import sys

    out = tmp_path / "ru_trace.json"
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--dump-translated",
         "ru", str(out)],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, (
        f"translated-content dump failed:\n{proc.stdout}\n{proc.stderr}")
    with open(out, encoding="utf-8") as fh:
        translated = json.load(fh)

    english = _record_all(engine)
    for name in ("arena", "boss"):
        assert translated[name] == english[name], (
            f"{name} trace differs between English and Russian content:\n"
            f"{_first_divergence(english[name], translated[name])}\n"
            "A content-derived name is leaking into the trace unmasked — add "
            "it to _mask_tables().")


@pytest.mark.parametrize("channel", _PERK_CHANNELS)
def test_traces_are_sensitive_to_each_perk_channel(engine, monkeypatch,
                                                   channel):
    """Zeroing any one perk channel must move at least one trace.

    This is the property the baseline exists for. A trace that reproduces
    byte-for-byte after a channel is silently switched off would also
    reproduce after a refactor drops that channel's call site — which is the
    single most likely way extracting the shared post-hit tail goes wrong.
    Asserting sensitivity directly is stronger than asserting that some
    message appeared, and it is what keeps the chosen seed honest.
    """
    from game.battle._manager_stats import _StatsMixin

    baseline = _record_all(engine)

    original = _StatsMixin._fighter_stats

    def zeroed(self, fighter):
        stats = dict(original(self, fighter))
        stats[channel] = 0.0
        return stats

    monkeypatch.setattr(_StatsMixin, "_fighter_stats", zeroed)
    perturbed = _record_all(engine)

    assert perturbed != baseline, (
        f"zeroing {channel!r} left both traces byte-identical — the baseline "
        "does not exercise that channel, so it cannot catch its loss. "
        "Re-tune the squad perks or the (SEED, tier) choice until it does.")


def _first_divergence(expected, actual):
    """Point at the first difference instead of dumping two 80-turn blobs."""
    if expected.get("start_events") != actual.get("start_events"):
        return ("start_events differ:\n"
                f"  expected {expected.get('start_events')}\n"
                f"  actual   {actual.get('start_events')}")
    exp_turns, act_turns = expected.get("turns", []), actual.get("turns", [])
    for i, (e, a) in enumerate(zip(exp_turns, act_turns)):
        if e == a:
            continue
        for key in ("n", "events", "fighters", "enemies", "outcome",
                    "gold_earned", "wins", "engine_gold"):
            if e.get(key) != a.get(key):
                return (f"turn index {i}, field {key!r}:\n"
                        f"  expected {e.get(key)}\n"
                        f"  actual   {a.get(key)}")
    if len(exp_turns) != len(act_turns):
        return f"turn count: expected {len(exp_turns)}, actual {len(act_turns)}"
    return "traces differ outside the compared fields"


def _record_to_disk():
    """Write the baseline. Invoked only by an explicit --record run."""
    import tempfile
    from game.engine import GameEngine

    tmp = os.path.join(tempfile.mkdtemp(), "trace_save.json")
    engine = GameEngine(save_path=tmp)
    traces = _record_all(engine)
    _assert_arena_meaningful(traces["arena"])
    _assert_boss_meaningful(traces["boss"])
    os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
    with open(BASELINE, "w", encoding="utf-8") as fh:
        json.dump(traces, fh, ensure_ascii=False, indent=1)
    for name, tr in traces.items():
        print(f"{name}: {len(tr['turns'])} turns, {tr['final_outcome']}")
    print(f"-> {BASELINE}")


def _dump_translated(lang, out_path):
    """Record both traces with `lang` content applied, and write them out.

    Only ever run as a subprocess (see
    test_trace_is_invariant_under_content_translation): applying translations
    is a one-way, session-global mutation.
    """
    import tempfile
    from game.data_loader import data_loader
    from game.engine import GameEngine

    tmp = os.path.join(tempfile.mkdtemp(), "trace_save.json")
    engine = GameEngine(save_path=tmp)
    data_loader.apply_translations(lang)
    engine._wire_data()
    traces = _record_all(engine)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(traces, fh, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")))
    if "--record" in sys.argv:
        _record_to_disk()
    elif "--dump-translated" in sys.argv:
        idx = sys.argv.index("--dump-translated")
        _dump_translated(sys.argv[idx + 1], sys.argv[idx + 2])
    else:
        print(__doc__)
