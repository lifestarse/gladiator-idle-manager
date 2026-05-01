# Build: 1
"""AST round-trip + validation tests."""
import pytest

from game.scripting import (
    Program, Trigger,
    If, While, ForEach, Assign, Action, Break, Continue,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
    node_to_dict, node_from_dict,
)


def _round_trip(node):
    return node_from_dict(node_to_dict(node))


def test_const_roundtrip():
    for v in [1, True, False, "x", None]:
        out = _round_trip(Const(v))
        assert out.value == v


def test_const_rejects_unknown_type():
    with pytest.raises(ValueError):
        Const(1.5)  # floats not allowed
    with pytest.raises(ValueError):
        Const([1, 2])  # lists not allowed in Const


def test_binop_unknown_op_rejected():
    with pytest.raises(ValueError):
        BinOp("@@", Const(1), Const(2))


def test_unary_unknown_op_rejected():
    with pytest.raises(ValueError):
        UnaryOp("~", Const(1))


def test_globalvar_name_pattern():
    GlobalVar("ok_name_1")
    with pytest.raises(ValueError):
        GlobalVar("1bad")
    with pytest.raises(ValueError):
        GlobalVar("a" * 65)


def test_program_trigger_validation():
    Program("p")
    with pytest.raises(ValueError):
        Program("p", trigger="unknown")


def test_program_tick_interval_range():
    Program("p", trigger=Trigger.ON_TICK, tick_interval=3600)
    with pytest.raises(ValueError):
        Program("p", trigger=Trigger.ON_TICK, tick_interval=0)
    with pytest.raises(ValueError):
        Program("p", trigger=Trigger.ON_TICK, tick_interval=3601)


def test_assign_fighter_field_requires_fighter():
    with pytest.raises(ValueError):
        Assign(target_kind="fighter_field", name="is_active", value=Const(True))


def test_assign_fighter_field_whitelist():
    Assign(target_kind="fighter_field", name="is_active",
           value=Const(True), fighter=LocalVar("f"))
    with pytest.raises(ValueError):
        Assign(target_kind="fighter_field", name="hp",
               value=Const(0), fighter=LocalVar("f"))


def test_foreach_source_validation():
    ForEach(var_name="f", source="fighters")
    with pytest.raises(ValueError):
        ForEach(var_name="f", source="weird")


def test_complex_program_roundtrip():
    p = Program(
        name="cleanup",
        trigger=Trigger.ON_BATTLE_END,
        enabled=True,
        tick_interval=5,
        g_var_init={"counter": 0},
        body=[
            ForEach(
                var_name="f",
                source="fighters",
                where=BinOp(">=", FighterField(LocalVar("f"), "fatigue"), Const(80)),
                body=[
                    If(
                        cond=BinOp("<=", FighterField(LocalVar("f"), "hp_pct"), Const(30)),
                        then_body=[Action("bench", [LocalVar("f")])],
                        else_body=[Action("unequip_all", [LocalVar("f")])],
                    ),
                    Assign(target_kind="global", name="counter",
                           value=BinOp("+", GlobalVar("counter"), Const(1))),
                ],
            ),
            While(
                cond=BinOp(">", EngineField("gold"), Const(1000)),
                body=[Break()],
            ),
            Action("start_arena_battle", []),
        ],
    )
    d = p.to_dict()
    p2 = Program.from_dict(d)
    assert p2.to_dict() == d


def test_node_unknown_kind_raises():
    with pytest.raises(ValueError):
        node_from_dict({"_kind": "Bogus"})


def test_break_continue_roundtrip():
    assert isinstance(_round_trip(Break()), Break)
    assert isinstance(_round_trip(Continue()), Continue)


def test_call_roundtrip():
    n = Call("len", [LocalVar("xs")])
    out = _round_trip(n)
    assert isinstance(out, Call)
    assert out.name == "len"
    assert isinstance(out.args[0], LocalVar)
