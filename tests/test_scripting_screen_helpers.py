# Build: 1
"""Acceptance gate for the pure helpers of ``game.screens.scripts``.

The package had no tests at all, on the assumption that a Kivy screen needs a
display. It does not: ``blocks.summarize`` / ``blocks.expr_str``,
``popups.default_block`` and ``popups.default_action_args`` build and inspect
AST nodes, and the Window they cost on import is the same one
tests/test_imports.py already pays for.

What that gap let through, all three shipped and survived a green run:

* ``default_block("assign_field")`` naming a fighter field literally, against a
  one-element whitelist that ``Assign.__post_init__`` validates — narrowing
  WRITABLE_FIGHTER_FIELDS threw ValueError into the UI on palette tap;
* the constant-type picker losing its pill captions on the first tap;
* ``BlockCard._build`` stacking canvas instructions per rebuild.

The registry-driven tests below are parametrised off BUILTIN_ACTIONS and the
palette so a newly added action or block kind is covered the moment it lands.
"""
import dis
import importlib
import os

import pytest

from game.scripting.ast_nodes import (
    Assign, Action, Break, Continue, If, While, ForEach,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar, FighterField, EngineField, Call,
    WRITABLE_FIGHTER_FIELDS, BIN_OPS, UNARY_OPS, ITERABLE_SOURCES,
)
from game.scripting.builtins import BUILTIN_ACTIONS
from game.screens.scripts import blocks, popups


# Palette kinds that ``popups.open_block_palette`` offers directly. Actions get
# their own picker and are covered by ACTION_KINDS below.
PALETTE_KINDS = (
    "if", "while", "foreach",
    "assign_local", "assign_global", "assign_field",
    "break", "continue",
)
ACTION_KINDS = tuple(f"action:{name}" for name in sorted(BUILTIN_ACTIONS))


# ---------- default_block ----------

@pytest.mark.parametrize("kind", PALETTE_KINDS + ACTION_KINDS)
def test_default_block_constructs(kind):
    """Every palette entry builds a node the AST itself accepts.

    The dataclasses validate in __post_init__, so "it constructs" is the whole
    assertion: a default that violates a whitelist raises here instead of on
    the user's screen.
    """
    node = popups.default_block(kind)
    assert node is not None


def test_default_block_rejects_unknown_kind():
    with pytest.raises(ValueError):
        popups.default_block("no_such_kind")


def test_default_assign_field_comes_from_the_whitelist():
    """The SET-fighter-field default must be a member of the whitelist, not a
    name that merely happens to be in it today."""
    node = popups.default_block("assign_field")
    assert isinstance(node, Assign)
    assert node.target_kind == "fighter_field"
    assert node.name in WRITABLE_FIGHTER_FIELDS
    assert node.name == blocks.default_writable_fighter_field()


def test_default_blocks_match_their_node_types():
    assert isinstance(popups.default_block("if"), If)
    assert isinstance(popups.default_block("while"), While)
    assert isinstance(popups.default_block("foreach"), ForEach)
    assert isinstance(popups.default_block("break"), Break)
    assert isinstance(popups.default_block("continue"), Continue)
    assert popups.default_block("foreach").source in ITERABLE_SOURCES
    assert popups.default_block("assign_local").target_kind == "local"
    assert popups.default_block("assign_global").target_kind == "global"


# ---------- default_action_args ----------

@pytest.mark.parametrize("name", sorted(BUILTIN_ACTIONS))
def test_default_action_args_satisfy_the_spec(name):
    """Args the palette pre-fills must land inside the action's arity band.

    Too few and the interpreter raises on the first run; too many and the
    surplus is silently dropped, so the user edits an argument that never
    reaches the engine.
    """
    amin, amax = BUILTIN_ACTIONS[name]["args"]
    args = popups.default_action_args(name)
    assert amin <= len(args) <= amax, (
        f"{name}: {len(args)} default args outside spec ({amin}, {amax})")


@pytest.mark.parametrize("name", sorted(BUILTIN_ACTIONS))
def test_fighter_actions_prefill_the_loop_variable(name):
    """An action declaring fighter_arg gets LocalVar('f') in slot 0.

    That is the variable ForEach binds, so the block drops straight into a
    loop body without the user rebuilding its first argument.
    """
    spec = BUILTIN_ACTIONS[name]
    if not spec.get("fighter_arg") or spec["args"][0] < 1:
        pytest.skip(f"{name} takes no fighter")
    args = popups.default_action_args(name)
    assert isinstance(args[0], LocalVar)
    assert args[0].name == "f"


def test_default_action_args_for_unknown_action():
    assert popups.default_action_args("no_such_action") == []


def test_action_blocks_carry_their_default_args():
    for name in BUILTIN_ACTIONS:
        node = popups.default_block(f"action:{name}")
        assert isinstance(node, Action)
        assert node.name == name
        assert len(node.args) == len(popups.default_action_args(name))


# ---------- summarize / expr_str ----------

_EXPRESSIONS = (
    Const(0),
    Const(True),
    Const(False),
    Const("hello"),
    Const(None),
    LocalVar("f"),
    GlobalVar("counter"),
    FighterField(LocalVar("f"), "hp"),
    EngineField("gold"),
    BinOp(">=", EngineField("gold"), Const(100)),
    UnaryOp("not", EngineField("battle_active")),
    Call("len", [LocalVar("f")]),
)

_STATEMENTS = (
    If(cond=Const(True)),
    While(cond=Const(False)),
    ForEach(var_name="f", source="fighters"),
    ForEach(var_name="f", source="active",
            where=BinOp(">", FighterField(LocalVar("f"), "hp"), Const(0))),
    Assign("local", "x", Const(1)),
    Assign("global", "counter", Const(1)),
    Assign("fighter_field", blocks.default_writable_fighter_field(),
           Const(True), fighter=LocalVar("f")),
    Action("start_arena_battle", []),
    Action("bench", [LocalVar("f")]),
    Break(),
    Continue(),
)


@pytest.mark.parametrize("expr", _EXPRESSIONS, ids=lambda e: type(e).__name__)
def test_expr_str_renders_every_expression_type(expr):
    """No expression type may fall through to the bare class name.

    ``expr_str`` ends in ``return type(e).__name__``; a node that reaches it
    shows the user "BinOp" where the editor promised them their condition.
    """
    text = blocks.expr_str(expr)
    assert isinstance(text, str) and text
    assert text != type(expr).__name__


@pytest.mark.parametrize("node", _STATEMENTS, ids=lambda n: type(n).__name__)
def test_summarize_renders_every_statement_type(node):
    text = blocks.summarize(node)
    assert isinstance(text, str) and text
    assert text != type(node).__name__


def test_summarize_covers_every_palette_default():
    """Whatever the palette can add, the card above it can describe."""
    for kind in PALETTE_KINDS + ACTION_KINDS:
        node = popups.default_block(kind)
        text = blocks.summarize(node)
        assert text and text != type(node).__name__, kind


def test_expr_str_embeds_operands_and_operators():
    """Round-trip check: a compound's rendering contains its parts.

    Symbols come from the i18n layer, so the assertion is on structure — the
    operands appear inside the operator's rendering — rather than on exact
    punctuation, which changes per language.
    """
    inner = blocks.expr_str(Const(42))
    outer = blocks.expr_str(BinOp("+", Const(42), Const(42)))
    assert outer.count(inner) == 2
    assert blocks.expr_str(Const("abc")) == '"abc"'
    assert blocks.expr_str(None) == "?"


def test_summarize_of_nested_control_flow_shows_the_condition():
    cond = BinOp(">=", EngineField("gold"), Const(500))
    node = If(cond=cond, then_body=[Action("start_arena_battle", [])])
    assert blocks.expr_str(cond) in blocks.summarize(node)


def test_every_binary_and_unary_operator_renders():
    for op in sorted(BIN_OPS):
        text = blocks.expr_str(BinOp(op, Const(1), Const(2)))
        assert text and text != "BinOp"
    for op in sorted(UNARY_OPS):
        text = blocks.expr_str(UnaryOp(op, Const(1)))
        assert text and text != "UnaryOp"


# ---------- widgets ----------
#
# These build real Kivy widgets. That needs the bundled fonts registered,
# which happens when game.app is imported — the Window itself is already paid
# for by importing this module's subjects.

@pytest.fixture(scope="module")
def kivy_fonts():
    import main  # noqa: F401 — registers PixelFont/BodyFont as a side effect


def _pill_texts(picker):
    """Pill captions in option order (Kivy stores children back to front)."""
    return [child.text for child in picker.children[::-1]]


def test_enum_picker_keeps_raw_labels_across_a_pick(kivy_fonts):
    """Untranslated captions must survive _render, which reruns on every pick.

    The constant-type pills used to be patched from outside after
    construction; _render rebuilt them from the label map on the first tap and
    all three turned into the same localized string, leaving only the gold
    highlight to tell 123 / bool / "abc" apart.
    """
    from game.screens.scripts.cells import (
        EnumPicker, CONST_TYPE_LABELS, CONST_TYPE_ORDER,
    )
    picked = []
    picker = EnumPicker(
        options=CONST_TYPE_ORDER, label_map=CONST_TYPE_LABELS,
        current="int", on_pick=picked.append, translate=False,
    )
    expected = [CONST_TYPE_LABELS[opt] for opt in CONST_TYPE_ORDER]
    assert _pill_texts(picker) == expected

    picker._pick("str")
    assert _pill_texts(picker) == expected
    assert picker.current == "str"
    assert picked == ["str"]
    assert len(set(expected)) == len(expected), "type pills must stay distinct"


def test_enum_picker_translates_by_default(kivy_fonts):
    """Vocabulary pickers (slot / class) still route their labels through t()."""
    from game.localization import t
    from game.screens.scripts.cells import EnumPicker
    from game.scripting import labels as L

    picker = EnumPicker(
        options=L.SLOT_OPTIONS, label_map=L.SLOT_LABELS,
        current=L.SLOT_OPTIONS[0], on_pick=lambda v: None,
    )
    assert _pill_texts(picker) == [t(L.SLOT_LABELS[s]) for s in L.SLOT_OPTIONS]


def _make_card(node):
    from game.screens.scripts.cells import BlockCard
    return BlockCard(node, 0, on_change=lambda n: None,
                     on_delete=lambda: None, on_move=lambda d: None)


@pytest.mark.parametrize("kind", PALETTE_KINDS)
def test_block_card_rebuild_is_idempotent(kind, kivy_fonts):
    """_build is called from five places; it may not accumulate canvas state.

    clear_widgets does not touch canvas.before, so a _build that paints its
    background there per call stacks a Color+Rectangle pair and a fresh
    pos/size observer on every edit, unbounded, with the stale rectangles
    frozen at the position they had when they were created.
    """
    card = _make_card(popups.default_block(kind))
    before = len(card.canvas.before.children)
    for _ in range(5):
        card._build()
    assert len(card.canvas.before.children) == before


def test_switch_action_rebuilds_the_card_once(kivy_fonts):
    """Switching a DO block's action must not leave duplicated canvas state."""
    from game.scripting.ast_nodes import Action
    card = _make_card(popups.default_block("action:bench"))
    before = len(card.canvas.before.children)
    card._switch_action(card._node, "log")
    assert isinstance(card._node, Action) and card._node.name == "log"
    assert card._node.args == popups.default_action_args("log")
    assert len(card.canvas.before.children) == before


# ---------- program-name uniqueness ----------
#
# ScriptManager owns the invariant, but it exists for this package: the editor
# is the only thing that names programs, and it used to enforce uniqueness in
# three hand-rolled copies while rename bypassed it entirely.

def _mgr_with(*names):
    from game.scripting.ast_nodes import Program
    from game.scripting.manager import ScriptManager
    mgr = ScriptManager()
    for name in names:
        mgr.programs.append(Program(name=name))
    return mgr


def test_add_program_renames_a_taken_name():
    from game.scripting.ast_nodes import Program
    mgr = _mgr_with("farm")
    mgr.add_program(Program(name="farm"))
    mgr.add_program(Program(name="farm"))
    assert [p.name for p in mgr.programs] == ["farm", "farm (2)", "farm (3)"]


def test_add_program_leaves_a_free_name_alone():
    from game.scripting.ast_nodes import Program
    mgr = _mgr_with("farm")
    mgr.add_program(Program(name="heal"))
    assert [p.name for p in mgr.programs] == ["farm", "heal"]


def test_unique_program_name_with_copy_marker():
    from game.scripting.manager import COPY_MARKER
    mgr = _mgr_with("farm")
    first = mgr.unique_program_name("farm", marker=COPY_MARKER)
    assert first == "farm (copy)"
    mgr.programs.append(type(mgr.programs[0])(name=first))
    assert mgr.unique_program_name("farm", marker=COPY_MARKER) == "farm (copy 2)"


def test_rename_program_refuses_to_collide():
    """Two programs sharing a name share a _tick_accum bucket, so both fire at
    roughly double their interval and each shows the other's status."""
    mgr = _mgr_with("farm", "heal")
    applied = mgr.rename_program(mgr.programs[1], "farm")
    assert applied == "farm (2)"
    assert len({p.name for p in mgr.programs}) == len(mgr.programs)


def test_rename_program_is_idempotent_on_its_own_name():
    mgr = _mgr_with("farm", "heal")
    assert mgr.rename_program(mgr.programs[0], "farm") == "farm"
    assert mgr.rename_program(mgr.programs[0], "  ") == "farm"


def test_program_keys_stay_distinct_after_every_naming_path():
    from game.scripting.ast_nodes import Program
    mgr = _mgr_with("farm")
    mgr.add_program(Program(name="farm"))
    mgr.rename_program(mgr.programs[1], "farm")
    keys = [mgr._program_key(p) for p in mgr.programs]
    assert len(set(keys)) == len(keys)


# ---------- package-level name resolution ----------

def _global_loads(code):
    """Every module-global name ``code`` and its nested code objects read.

    Recursing into co_consts matters here: almost every callback in this
    package is a closure defined inside a method (``_rename``, ``_apply``,
    ``_save``), and a closure resolves module globals exactly like its parent.
    LOAD_FAST / LOAD_DEREF are locals and closure cells, so they are not
    module-global lookups and never appear.
    """
    from types import CodeType

    for instr in dis.get_instructions(code):
        if instr.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
            name = (instr.argval[1] if isinstance(instr.argval, tuple)
                    else instr.argval)
            if isinstance(name, str):
                yield name
    for const in code.co_consts:
        if isinstance(const, CodeType):
            yield from _global_loads(const)


def test_scripts_package_names_resolve():
    """Every global a scripts module reads must exist in that module.

    This package builds its whole surface from Kivy callbacks, so a name that
    only the star-import from ``_screen_imports`` provides would raise
    NameError on tap and nowhere else. tests/test_name_resolution.py walks the
    split packages the same way; scripts is not one of those (it is not a
    mixin split), so it gets its own walk here.
    """
    import builtins

    pkg = importlib.import_module("game.screens.scripts")
    pkg_dir = os.path.dirname(pkg.__file__)
    builtin_names = set(dir(builtins))

    problems = []
    for fname in sorted(os.listdir(pkg_dir)):
        if not fname.endswith(".py") or fname == "__init__.py":
            continue
        mod = importlib.import_module(f"game.screens.scripts.{fname[:-3]}")
        mod_globals = set(vars(mod))
        funcs = []
        for obj in list(vars(mod).values()):
            if callable(obj) and hasattr(obj, "__code__"):
                funcs.append(obj)
            elif isinstance(obj, type) and getattr(obj, "__module__", "") == mod.__name__:
                funcs.extend(m for m in vars(obj).values()
                             if callable(m) and hasattr(m, "__code__"))
        for func in funcs:
            if getattr(func, "__module__", None) != mod.__name__:
                continue
            for name in _global_loads(func.__code__):
                if name in mod_globals or name in builtin_names:
                    continue
                problems.append(f"{fname}:{func.__qualname__} -> {name!r}")

    assert not problems, ("Unresolved globals in game.screens.scripts:\n  "
                          + "\n  ".join(sorted(set(problems))))
