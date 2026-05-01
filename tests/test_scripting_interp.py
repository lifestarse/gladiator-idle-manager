# Build: 1
"""Interpreter unit tests with a fake engine + fake fighters.

We use a stub engine so these tests do not depend on the heavy GameEngine
nor on PR1 (battle_end events) / PR2 (stamina/fatigue) being merged.
"""
import pytest

from game.scripting import (
    Program, Interpreter, ScriptError,
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
)


# ---------- stub engine + fighter ----------

class FakeFighter:
    def __init__(self, name="x", hp=100, max_hp=100, fatigue=0, stamina=100,
                 is_active=True, injuries=None):
        self.name = name
        self.hp = hp
        self.max_hp = max_hp
        self.fatigue = fatigue
        self.stamina = stamina
        self.is_active = is_active
        self.injuries = injuries or []
        self.alive = hp > 0
        self.level = 1
        self.strength = 5
        self.agility = 5
        self.vitality = 5
        self.fighter_class = "mercenary"
        self.weapon = None
        self.armor = None
        self.accessory = None
        self.relic = None

    @property
    def is_exhausted(self):
        return self.fatigue >= 100

    @property
    def available(self):
        return self.is_active and not self.is_exhausted and self.alive


class FakeEngine:
    def __init__(self, fighters=None, gold=0, diamonds=0):
        self.fighters = fighters or []
        self.gold = gold
        self.diamonds = diamonds
        self.victories = 0
        self.current_tier = 1
        self.battle_active = False
        self.expedition_active = False
        self.current_floor = 1
        self.events = []
        self.battles_started = 0
        self.expeditions_started = []

    def start_auto_battle(self):
        if self.battle_active:
            return
        self.battle_active = True
        self.battles_started += 1

    def stop_battle(self):
        self.battle_active = False

    def start_expedition(self, tier):
        if self.expedition_active:
            return
        self.expedition_active = True
        self.expeditions_started.append(tier)

    def stop_expedition(self):
        self.expedition_active = False

    def log_event(self, msg):
        self.events.append(msg)


def _run(body, engine=None, g_vars=None, **kw):
    p = Program(name="t", body=body)
    interp = Interpreter(engine or FakeEngine(), p, g_vars, **kw)
    interp.run()
    return interp


# ---------- expressions ----------

@pytest.mark.parametrize("op,lhs,rhs,expected", [
    ("+", 2, 3, 5),
    ("-", 5, 2, 3),
    ("*", 4, 3, 12),
    ("/", 10, 4, 2.5),
    ("%", 10, 3, 1),
    ("==", 1, 1, True),
    ("!=", 1, 2, True),
    ("<", 1, 2, True),
    ("<=", 2, 2, True),
    (">", 3, 2, True),
    (">=", 2, 2, True),
    ("and", True, False, False),
    ("or", False, True, True),
])
def test_binop_arith(op, lhs, rhs, expected):
    interp = _run([Assign("local", "r", BinOp(op, Const(lhs), Const(rhs)))])
    assert interp.locals["r"] == expected


def test_div_by_zero():
    with pytest.raises(ScriptError):
        _run([Assign("local", "r", BinOp("/", Const(1), Const(0)))])


def test_mod_by_zero():
    with pytest.raises(ScriptError):
        _run([Assign("local", "r", BinOp("%", Const(1), Const(0)))])


def test_unary_not_neg():
    interp = _run([
        Assign("local", "a", UnaryOp("not", Const(False))),
        Assign("local", "b", UnaryOp("-", Const(5))),
    ])
    assert interp.locals["a"] is True
    assert interp.locals["b"] == -5


def test_call_len_min_max_abs():
    e = FakeEngine(fighters=[FakeFighter() for _ in range(3)])
    interp = _run([
        Assign("local", "n", Call("min", [Const(3), Const(7), Const(2)])),
        Assign("local", "m", Call("max", [Const(3), Const(7), Const(2)])),
        Assign("local", "a", Call("abs", [Const(-9)])),
    ], engine=e)
    assert interp.locals["n"] == 2
    assert interp.locals["m"] == 7
    assert interp.locals["a"] == 9


# ---------- if / while / foreach ----------

def test_if_true_branch():
    interp = _run([
        Assign("local", "x", Const(0)),
        If(Const(True),
           [Assign("local", "x", Const(1))],
           [Assign("local", "x", Const(2))]),
    ])
    assert interp.locals["x"] == 1


def test_if_false_branch():
    interp = _run([
        Assign("local", "x", Const(0)),
        If(Const(False),
           [Assign("local", "x", Const(1))],
           [Assign("local", "x", Const(2))]),
    ])
    assert interp.locals["x"] == 2


def test_while_break():
    interp = _run([
        Assign("local", "i", Const(0)),
        While(BinOp("<", LocalVar("i"), Const(100)), [
            Assign("local", "i", BinOp("+", LocalVar("i"), Const(1))),
            If(BinOp(">=", LocalVar("i"), Const(5)), [Break()], []),
        ]),
    ])
    assert interp.locals["i"] == 5


def test_while_continue():
    interp = _run([
        Assign("local", "i", Const(0)),
        Assign("local", "even", Const(0)),
        While(BinOp("<", LocalVar("i"), Const(10)), [
            Assign("local", "i", BinOp("+", LocalVar("i"), Const(1))),
            If(BinOp("==", BinOp("%", LocalVar("i"), Const(2)), Const(1)),
               [Continue()], []),
            Assign("local", "even", BinOp("+", LocalVar("even"), Const(1))),
        ]),
    ])
    assert interp.locals["even"] == 5


def test_while_iter_limit():
    with pytest.raises(ScriptError, match="while iteration"):
        _run([
            While(Const(True), [Assign("local", "x", Const(0))])
        ], max_loop_iters=10, max_steps=10**6)


def test_step_limit():
    with pytest.raises(ScriptError, match="step limit"):
        _run([
            While(Const(True), [Assign("local", "x", Const(0))])
        ], max_steps=20, max_loop_iters=10**6)


def test_loop_depth_limit():
    # build 5 nested whiles, set max_loop_depth=2
    body = [Break()]
    for _ in range(5):
        body = [While(Const(True), body)]
    with pytest.raises(ScriptError, match="loop nesting"):
        _run(body, max_loop_depth=2)


def test_foreach_filters():
    fs = [FakeFighter("a", fatigue=10), FakeFighter("b", fatigue=80), FakeFighter("c", fatigue=90)]
    e = FakeEngine(fighters=fs)
    interp = _run([
        Assign("local", "n", Const(0)),
        ForEach("f", "fighters",
                body=[Assign("local", "n", BinOp("+", LocalVar("n"), Const(1)))],
                where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(50))),
    ], engine=e)
    assert interp.locals["n"] == 2


def test_foreach_break_continue():
    fs = [FakeFighter(str(i)) for i in range(5)]
    e = FakeEngine(fighters=fs)
    interp = _run([
        Assign("local", "n", Const(0)),
        ForEach("f", "fighters",
                body=[
                    If(BinOp("==", FighterField(LocalVar("f"), "name"), Const("3")),
                       [Break()], []),
                    Assign("local", "n", BinOp("+", LocalVar("n"), Const(1))),
                ]),
    ], engine=e)
    assert interp.locals["n"] == 3


def test_foreach_var_scope_restored():
    fs = [FakeFighter("a"), FakeFighter("b")]
    e = FakeEngine(fighters=fs)
    interp = _run([
        Assign("local", "f", Const("outer")),
        ForEach("f", "fighters", body=[]),
    ], engine=e)
    assert interp.locals["f"] == "outer"


# ---------- assignments / variables ----------

def test_global_var_persists_across_runs():
    g = {}
    p = Program(name="t", body=[
        Assign("global", "counter",
               BinOp("+", GlobalVar("counter"), Const(1))),
    ])
    Interpreter(FakeEngine(), p, g).run()
    Interpreter(FakeEngine(), p, g).run()
    Interpreter(FakeEngine(), p, g).run()
    assert g["counter"] == 3


def test_g_var_init_does_not_overwrite():
    g = {"counter": 42}
    p = Program(name="t", g_var_init={"counter": 0}, body=[])
    Interpreter(FakeEngine(), p, g).run()
    assert g["counter"] == 42


def test_unknown_local_raises():
    with pytest.raises(ScriptError):
        _run([Assign("local", "y", LocalVar("undefined"))])


# ---------- field access ----------

def test_fighter_field_read():
    f = FakeFighter("x", hp=50, max_hp=200, fatigue=40)
    interp = _run([
        Assign("local", "h", FighterField(Const(None), "hp")),  # Const(None) handled below
    ], engine=FakeEngine(fighters=[f]))
    # actually exercise via foreach
    interp2 = _run([
        ForEach("f", "fighters", body=[
            Assign("local", "h", FighterField(LocalVar("f"), "hp")),
            Assign("local", "p", FighterField(LocalVar("f"), "hp_pct")),
        ]),
    ], engine=FakeEngine(fighters=[f]))
    assert interp2.locals["h"] == 50
    assert interp2.locals["p"] == 25.0


def test_engine_field_read():
    e = FakeEngine(fighters=[FakeFighter(), FakeFighter(is_active=False)], gold=777)
    interp = _run([
        Assign("local", "g", EngineField("gold")),
        Assign("local", "n", EngineField("fighter_count")),
        Assign("local", "a", EngineField("active_count")),
    ], engine=e)
    assert interp.locals["g"] == 777
    assert interp.locals["n"] == 2
    assert interp.locals["a"] == 1


def test_unknown_engine_field():
    with pytest.raises(ScriptError):
        _run([Assign("local", "x", EngineField("nope"))])


def test_unknown_fighter_field():
    f = FakeFighter()
    with pytest.raises(ScriptError):
        _run([
            ForEach("f", "fighters", body=[
                Assign("local", "x", FighterField(LocalVar("f"), "nope"))
            ]),
        ], engine=FakeEngine(fighters=[f]))


def test_fighter_field_write_is_active():
    f = FakeFighter(is_active=True)
    _run([
        ForEach("f", "fighters", body=[
            Assign("fighter_field", "is_active", Const(False), fighter=LocalVar("f")),
        ]),
    ], engine=FakeEngine(fighters=[f]))
    assert f.is_active is False


# ---------- actions ----------

def test_action_bench_idempotent():
    f = FakeFighter(is_active=True)
    e = FakeEngine(fighters=[f])
    body = [ForEach("f", "fighters", body=[Action("bench", [LocalVar("f")])])]
    _run(body, engine=e)
    assert f.is_active is False
    _run(body, engine=e)  # re-apply
    assert f.is_active is False


def test_action_activate():
    f = FakeFighter(is_active=False)
    e = FakeEngine(fighters=[f])
    _run([ForEach("f", "fighters", body=[Action("activate", [LocalVar("f")])])], engine=e)
    assert f.is_active is True


def test_action_unequip_all_fallback():
    f = FakeFighter()
    f.weapon = object()
    f.armor = object()
    e = FakeEngine(fighters=[f])
    _run([ForEach("f", "fighters", body=[Action("unequip_all", [LocalVar("f")])])], engine=e)
    assert f.weapon is None and f.armor is None


def test_action_start_arena_idempotent():
    e = FakeEngine()
    _run([Action("start_arena_battle", [])], engine=e)
    assert e.battles_started == 1
    _run([Action("start_arena_battle", [])], engine=e)  # already active → no-op
    assert e.battles_started == 1


def test_action_start_expedition():
    e = FakeEngine()
    _run([Action("start_expedition", [Const(3)])], engine=e)
    assert e.expeditions_started == [3]


def test_action_log():
    e = FakeEngine()
    _run([Action("log", [Const("hello")])], engine=e)
    assert e.events == ["hello"]


def test_unknown_action():
    with pytest.raises(ScriptError):
        _run([Action("nuke", [])])


def test_action_arity():
    with pytest.raises(ScriptError):
        _run([Action("bench", [])])


# ---------- control-flow misuse ----------

def test_break_outside_loop():
    with pytest.raises(ScriptError, match="break"):
        _run([Break()])


def test_continue_outside_loop():
    with pytest.raises(ScriptError, match="continue"):
        _run([Continue()])
