# Build: 2
"""Smoke tests for built-in scripting templates.

For each entry in ``game.scripting.templates.TEMPLATES``:
  * factory builds without raising
  * Program round-trips through to_dict / from_dict unchanged
  * trigger is one of Trigger.ALL
  * actions referenced exist in BUILTIN_ACTIONS
  * referenced fighter / engine field names exist in BUILTIN_FIELDS /
    BUILTIN_ENGINE_FIELDS
  * referenced ForEach sources are in ITERABLE_SOURCES

These guarantees mean a fresh user picking ANY template will get a runnable
program, not a parse error. Without this test, a refactor that renames an
internal field or removes an action would silently break the templates
because they are not exercised by the manager's seed code (only the first
two are seeded).
"""
from __future__ import annotations
import pytest

from game.scripting.templates import TEMPLATES
from game.scripting.ast_nodes import (
    Program, Trigger,
    If, While, ForEach, Assign, Action,
    BinOp, UnaryOp, Const, LocalVar, GlobalVar,
    FighterField, EngineField, Call,
    ITERABLE_SOURCES,
)
from game.scripting.builtins import (
    BUILTIN_ACTIONS, BUILTIN_FIELDS, BUILTIN_ENGINE_FIELDS, BUILTIN_CALLS,
)


@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.id)
def test_template_builds(tmpl):
    p = tmpl.factory()
    assert isinstance(p, Program), f"factory must return Program, got {type(p)}"
    assert p.name, "template program must have a name"
    assert p.trigger in Trigger.ALL, f"unknown trigger {p.trigger!r}"


@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.id)
def test_template_round_trips(tmpl):
    """to_dict / from_dict must be lossless for templates."""
    p1 = tmpl.factory()
    d = p1.to_dict()
    p2 = Program.from_dict(d)
    assert p2.to_dict() == d, (
        f"template {tmpl.id} did not round-trip:\n"
        f"  before: {d}\n"
        f"  after:  {p2.to_dict()}"
    )


def _walk(node, out_actions, out_fields, out_engine, out_calls, out_sources):
    """Collect every action name, field name, engine-field name, call name
    and ForEach source referenced anywhere inside an AST tree."""
    if isinstance(node, Action):
        out_actions.add(node.name)
        for a in node.args:
            _walk(a, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, FighterField):
        out_fields.add(node.field_name)
        _walk(node.fighter, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, EngineField):
        out_engine.add(node.field_name)
    elif isinstance(node, Call):
        out_calls.add(node.name)
        for a in node.args:
            _walk(a, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, ForEach):
        out_sources.add(node.source)
        if node.where is not None:
            _walk(node.where, out_actions, out_fields, out_engine, out_calls, out_sources)
        for s in node.body:
            _walk(s, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, If):
        _walk(node.cond, out_actions, out_fields, out_engine, out_calls, out_sources)
        for s in node.then_body:
            _walk(s, out_actions, out_fields, out_engine, out_calls, out_sources)
        for s in node.else_body:
            _walk(s, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, While):
        _walk(node.cond, out_actions, out_fields, out_engine, out_calls, out_sources)
        for s in node.body:
            _walk(s, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, Assign):
        _walk(node.value, out_actions, out_fields, out_engine, out_calls, out_sources)
        if node.fighter is not None:
            _walk(node.fighter, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, BinOp):
        _walk(node.lhs, out_actions, out_fields, out_engine, out_calls, out_sources)
        _walk(node.rhs, out_actions, out_fields, out_engine, out_calls, out_sources)
    elif isinstance(node, UnaryOp):
        _walk(node.operand, out_actions, out_fields, out_engine, out_calls, out_sources)
    # Const / LocalVar / GlobalVar carry no sub-refs


@pytest.mark.parametrize("tmpl", TEMPLATES, ids=lambda t: t.id)
def test_template_references_are_valid(tmpl):
    """Catch templates that reference removed actions / fields / sources."""
    p = tmpl.factory()
    actions, fields, engine_fields, calls, sources = set(), set(), set(), set(), set()
    for stmt in p.body:
        _walk(stmt, actions, fields, engine_fields, calls, sources)
    bad_actions = actions - BUILTIN_ACTIONS.keys()
    bad_fields = fields - BUILTIN_FIELDS.keys()
    bad_engine = engine_fields - BUILTIN_ENGINE_FIELDS.keys()
    bad_calls = calls - BUILTIN_CALLS.keys()
    bad_sources = sources - set(ITERABLE_SOURCES)
    assert not bad_actions, f"unknown actions: {bad_actions}"
    assert not bad_fields, f"unknown fighter fields: {bad_fields}"
    assert not bad_engine, f"unknown engine fields: {bad_engine}"
    assert not bad_calls, f"unknown calls: {bad_calls}"
    assert not bad_sources, f"unknown sources: {bad_sources}"


def test_template_ids_are_unique():
    """Two templates sharing an id would make ``template_by_id`` ambiguous."""
    ids = [t.id for t in TEMPLATES]
    assert len(ids) == len(set(ids)), f"duplicate template ids: {ids}"
