# Build: 1
"""AST nodes for the squad scripting mini-language.

All nodes are dataclasses that round-trip via `node_to_dict` / `node_from_dict`.
The `_kind` field on each dict is the discriminator.

Tree shape:
    Program
      body: list[Statement]
      g_var_init: dict[str, value]      # initial persistent globals
      trigger: "on_battle_end" | "on_tick" | "on_demand"
      tick_interval: int (seconds, when trigger == on_tick)
      enabled: bool
      name: str

Statement   = If | While | ForEach | Assign | Action | Break | Continue
Expression  = Const | LocalVar | GlobalVar | FighterField | EngineField
            | BinOp | UnaryOp | Call

Constraints (validated at construction or load):
    - Only known operators, action names, fighter fields, engine fields.
    - Const types restricted to int|bool|str|None|list (for foreach sources).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


# ---------- enums / constants ----------

class Trigger:
    ON_BATTLE_END = "on_battle_end"
    ON_TICK = "on_tick"
    ON_DEMAND = "on_demand"
    ALL = (ON_BATTLE_END, ON_TICK, ON_DEMAND)


BIN_OPS = {"+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "and", "or"}
UNARY_OPS = {"not", "-"}
ITERABLE_SOURCES = ("fighters", "active", "benched", "available", "exhausted")
ASSIGN_TARGETS = ("local", "global", "fighter_field")
WRITABLE_FIGHTER_FIELDS = {"is_active"}  # narrow whitelist; everything else read-only
GLOBAL_VAR_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,63}$"


# ---------- base classes ----------

@dataclass
class Node:
    pass


@dataclass
class Statement(Node):
    pass


@dataclass
class Expression(Node):
    pass


# ---------- expressions ----------

@dataclass
class Const(Expression):
    value: Any  # int|bool|str|None

    def __post_init__(self):
        if not isinstance(self.value, (int, bool, str)) and self.value is not None:
            raise ValueError(f"Const supports int|bool|str|None, got {type(self.value).__name__}")


@dataclass
class LocalVar(Expression):
    name: str


@dataclass
class GlobalVar(Expression):
    name: str

    def __post_init__(self):
        import re
        if not re.match(GLOBAL_VAR_PATTERN, self.name):
            raise ValueError(f"invalid global var name: {self.name!r}")


@dataclass
class FighterField(Expression):
    """Read fighter.field — fighter is a sub-expression that should evaluate to a Fighter."""
    fighter: Expression
    field_name: str  # validated lazily by interpreter against BUILTIN_FIELDS


@dataclass
class EngineField(Expression):
    """Read engine.field — gold, diamonds, victories, battle_active, etc."""
    field_name: str


@dataclass
class BinOp(Expression):
    op: str
    lhs: Expression
    rhs: Expression

    def __post_init__(self):
        if self.op not in BIN_OPS:
            raise ValueError(f"unknown binary op: {self.op!r}")


@dataclass
class UnaryOp(Expression):
    op: str
    operand: Expression

    def __post_init__(self):
        if self.op not in UNARY_OPS:
            raise ValueError(f"unknown unary op: {self.op!r}")


@dataclass
class Call(Expression):
    """Built-in function call producing a value (e.g. len, count_active, hp_pct)."""
    name: str
    args: list[Expression] = field(default_factory=list)


# ---------- statements ----------

@dataclass
class If(Statement):
    cond: Expression
    then_body: list[Statement] = field(default_factory=list)
    else_body: list[Statement] = field(default_factory=list)


@dataclass
class While(Statement):
    cond: Expression
    body: list[Statement] = field(default_factory=list)


@dataclass
class ForEach(Statement):
    """Iterate over a builtin source (fighters/active/...) with optional `where` filter."""
    var_name: str
    source: str  # one of ITERABLE_SOURCES
    body: list[Statement] = field(default_factory=list)
    where: Expression | None = None

    def __post_init__(self):
        if self.source not in ITERABLE_SOURCES:
            raise ValueError(f"unknown iterable source: {self.source!r}")


@dataclass
class Assign(Statement):
    """Assignment. `target_kind` decides which dict/object is written."""
    target_kind: str  # one of ASSIGN_TARGETS
    name: str         # var name, OR field_name for fighter_field
    value: Expression
    fighter: Expression | None = None  # required when target_kind == fighter_field

    def __post_init__(self):
        if self.target_kind not in ASSIGN_TARGETS:
            raise ValueError(f"unknown assign target: {self.target_kind!r}")
        if self.target_kind == "fighter_field":
            if self.fighter is None:
                raise ValueError("fighter_field assign requires fighter expression")
            if self.name not in WRITABLE_FIGHTER_FIELDS:
                raise ValueError(f"fighter field {self.name!r} is not writable")
        if self.target_kind == "global":
            import re
            if not re.match(GLOBAL_VAR_PATTERN, self.name):
                raise ValueError(f"invalid global var name: {self.name!r}")


@dataclass
class Action(Statement):
    """Side-effect call (bench/activate/start_arena_battle/...)."""
    name: str
    args: list[Expression] = field(default_factory=list)


@dataclass
class Break(Statement):
    pass


@dataclass
class Continue(Statement):
    pass


# ---------- top-level Program ----------

@dataclass
class Program:
    name: str
    trigger: str = Trigger.ON_BATTLE_END
    enabled: bool = True
    tick_interval: int = 5  # seconds, used only when trigger == on_tick
    body: list[Statement] = field(default_factory=list)
    g_var_init: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.trigger not in Trigger.ALL:
            raise ValueError(f"unknown trigger: {self.trigger!r}")
        if self.tick_interval < 1 or self.tick_interval > 3600:
            raise ValueError(f"tick_interval out of range [1,3600]: {self.tick_interval}")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trigger": self.trigger,
            "enabled": self.enabled,
            "tick_interval": self.tick_interval,
            "g_var_init": dict(self.g_var_init),
            "body": [node_to_dict(s) for s in self.body],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Program":
        return cls(
            name=d.get("name", "untitled"),
            trigger=d.get("trigger", Trigger.ON_BATTLE_END),
            enabled=bool(d.get("enabled", True)),
            tick_interval=int(d.get("tick_interval", 5)),
            g_var_init=dict(d.get("g_var_init", {})),
            body=[node_from_dict(x) for x in d.get("body", [])],
        )


# ---------- (de)serialization ----------

def node_to_dict(node: Node) -> dict:
    """Serialize an AST node (or list of nodes) into a JSON-safe dict."""
    if node is None:
        return None
    cls = type(node)
    name = cls.__name__
    if name == "Const":
        return {"_kind": "Const", "value": node.value}
    if name == "LocalVar":
        return {"_kind": "LocalVar", "name": node.name}
    if name == "GlobalVar":
        return {"_kind": "GlobalVar", "name": node.name}
    if name == "FighterField":
        return {"_kind": "FighterField", "fighter": node_to_dict(node.fighter), "field_name": node.field_name}
    if name == "EngineField":
        return {"_kind": "EngineField", "field_name": node.field_name}
    if name == "BinOp":
        return {"_kind": "BinOp", "op": node.op,
                "lhs": node_to_dict(node.lhs), "rhs": node_to_dict(node.rhs)}
    if name == "UnaryOp":
        return {"_kind": "UnaryOp", "op": node.op, "operand": node_to_dict(node.operand)}
    if name == "Call":
        return {"_kind": "Call", "name": node.name, "args": [node_to_dict(a) for a in node.args]}
    if name == "If":
        return {"_kind": "If", "cond": node_to_dict(node.cond),
                "then_body": [node_to_dict(s) for s in node.then_body],
                "else_body": [node_to_dict(s) for s in node.else_body]}
    if name == "While":
        return {"_kind": "While", "cond": node_to_dict(node.cond),
                "body": [node_to_dict(s) for s in node.body]}
    if name == "ForEach":
        return {"_kind": "ForEach", "var_name": node.var_name, "source": node.source,
                "body": [node_to_dict(s) for s in node.body],
                "where": node_to_dict(node.where) if node.where else None}
    if name == "Assign":
        return {"_kind": "Assign", "target_kind": node.target_kind, "name": node.name,
                "value": node_to_dict(node.value),
                "fighter": node_to_dict(node.fighter) if node.fighter else None}
    if name == "Action":
        return {"_kind": "Action", "name": node.name, "args": [node_to_dict(a) for a in node.args]}
    if name == "Break":
        return {"_kind": "Break"}
    if name == "Continue":
        return {"_kind": "Continue"}
    raise ValueError(f"cannot serialize node of type {name}")


_NODE_CTORS = {
    "Const":        lambda d: Const(value=d["value"]),
    "LocalVar":     lambda d: LocalVar(name=d["name"]),
    "GlobalVar":    lambda d: GlobalVar(name=d["name"]),
    "FighterField": lambda d: FighterField(fighter=node_from_dict(d["fighter"]), field_name=d["field_name"]),
    "EngineField":  lambda d: EngineField(field_name=d["field_name"]),
    "BinOp":        lambda d: BinOp(op=d["op"], lhs=node_from_dict(d["lhs"]), rhs=node_from_dict(d["rhs"])),
    "UnaryOp":      lambda d: UnaryOp(op=d["op"], operand=node_from_dict(d["operand"])),
    "Call":         lambda d: Call(name=d["name"], args=[node_from_dict(a) for a in d.get("args", [])]),
    "If":           lambda d: If(cond=node_from_dict(d["cond"]),
                                 then_body=[node_from_dict(s) for s in d.get("then_body", [])],
                                 else_body=[node_from_dict(s) for s in d.get("else_body", [])]),
    "While":        lambda d: While(cond=node_from_dict(d["cond"]),
                                    body=[node_from_dict(s) for s in d.get("body", [])]),
    "ForEach":      lambda d: ForEach(var_name=d["var_name"], source=d["source"],
                                      body=[node_from_dict(s) for s in d.get("body", [])],
                                      where=node_from_dict(d["where"]) if d.get("where") else None),
    "Assign":       lambda d: Assign(target_kind=d["target_kind"], name=d["name"],
                                     value=node_from_dict(d["value"]),
                                     fighter=node_from_dict(d["fighter"]) if d.get("fighter") else None),
    "Action":       lambda d: Action(name=d["name"], args=[node_from_dict(a) for a in d.get("args", [])]),
    "Break":        lambda d: Break(),
    "Continue":     lambda d: Continue(),
}


def node_from_dict(d: dict | None) -> Node | None:
    if d is None:
        return None
    kind = d.get("_kind")
    ctor = _NODE_CTORS.get(kind)
    if ctor is None:
        raise ValueError(f"unknown node kind: {kind!r}")
    return ctor(d)
