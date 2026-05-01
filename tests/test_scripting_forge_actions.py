# Build: 1
"""Tests for the buy_item / equip_best / forge_upgrade actions and
the new equipment / inventory fields. Uses a stub engine to stay
independent of the heavy GameEngine."""

from game.scripting import (
    Program, Interpreter, Action, ForEach, LocalVar, Const, EngineField,
    FighterField, Assign, BinOp, If,
)


# ---------- shared stubs ----------

class FakeFighter:
    def __init__(self, name="x", is_active=True):
        self.name = name
        self.hp = 100
        self.max_hp = 100
        self.fatigue = 0
        self.stamina = 100
        self.is_active = is_active
        self.alive = True
        self.injuries = []
        self.level = 1
        self.strength = 5
        self.agility = 5
        self.vitality = 5
        self.fighter_class = "mercenary"
        self.equipment = {}  # slot -> item dict


class FakeEngine:
    def __init__(self, fighters=None, gold=0, shop=None, inventory=None):
        self.fighters = fighters or []
        self.gold = gold
        self.diamonds = 0
        self.victories = 0
        self.current_tier = 1
        self.current_floor = 1
        self.battle_active = False
        self.expedition_active = False
        self.inventory = inventory or []
        self._shop = shop or []
        self.upgrade_calls = []  # for assertions

    def get_forge_items(self):
        return [
            {**it, "affordable": self.gold >= it.get("cost", 0)}
            for it in self._shop
        ]

    def buy_forge_item(self, item_id):
        item = next((i for i in self._shop if i["id"] == item_id), None)
        if not item:
            return None
        if self.gold < item["cost"]:
            return None
        self.gold -= item["cost"]
        self.inventory.append(dict(item))
        return True

    def equip_from_inventory(self, fighter_idx, inv_index):
        if self.battle_active:
            return None
        if fighter_idx >= len(self.fighters):
            return None
        if inv_index >= len(self.inventory):
            return None
        f = self.fighters[fighter_idx]
        item = self.inventory.pop(inv_index)
        old = f.equipment.get(item["slot"])
        f.equipment[item["slot"]] = item
        if old:
            self.inventory.append(old)
        return True

    def upgrade_item(self, item):
        self.upgrade_calls.append(item.get("id"))
        item["upgrade_level"] = item.get("upgrade_level", 0) + 1
        return True


def _run(body, engine):
    p = Program(name="t", body=body)
    Interpreter(engine, p).run()


# ---------- buy_item ----------

def test_buy_item_picks_cheapest_affordable_in_slot():
    e = FakeEngine(
        gold=300,
        shop=[
            {"id": "w_cheap",  "slot": "weapon", "cost": 100, "name": "stick"},
            {"id": "w_mid",    "slot": "weapon", "cost": 250, "name": "sword"},
            {"id": "w_pricey", "slot": "weapon", "cost": 500, "name": "blade"},
            {"id": "a_cheap",  "slot": "armor",  "cost": 80,  "name": "rags"},
        ],
    )
    _run([Action("buy_item", [Const("weapon")])], e)
    assert len(e.inventory) == 1
    assert e.inventory[0]["id"] == "w_cheap"
    assert e.gold == 200  # 300 - 100


def test_buy_item_no_op_when_not_affordable():
    e = FakeEngine(gold=10, shop=[
        {"id": "w_cheap", "slot": "weapon", "cost": 100, "name": "stick"},
    ])
    _run([Action("buy_item", [Const("weapon")])], e)
    assert e.inventory == []
    assert e.gold == 10


def test_buy_item_invalid_slot_no_op():
    e = FakeEngine(gold=999, shop=[
        {"id": "w", "slot": "weapon", "cost": 1, "name": "x"},
    ])
    _run([Action("buy_item", [Const("notaslot")])], e)
    assert e.inventory == []


# ---------- equip_best ----------

def test_equip_best_picks_highest_cost_then_upgrade_level():
    f = FakeFighter("a")
    e = FakeEngine(
        fighters=[f],
        inventory=[
            {"id": "w_low",  "slot": "weapon", "cost": 100, "upgrade_level": 5,
             "name": "stick"},
            {"id": "w_mid",  "slot": "weapon", "cost": 250, "upgrade_level": 0,
             "name": "sword"},
            {"id": "w_high", "slot": "weapon", "cost": 250, "upgrade_level": 3,
             "name": "edge"},
            {"id": "a_any",  "slot": "armor",  "cost": 999, "name": "plate"},
        ],
    )
    _run([ForEach("f", "fighters", body=[
        Action("equip_best", [LocalVar("f"), Const("weapon")])
    ])], e)
    assert f.equipment["weapon"]["id"] == "w_high"
    # Armor not touched.
    assert "armor" not in f.equipment
    # Inventory shrank by 1 weapon.
    assert sum(1 for it in e.inventory if it["slot"] == "weapon") == 2


def test_equip_best_no_op_during_battle():
    f = FakeFighter("a")
    e = FakeEngine(fighters=[f], inventory=[
        {"id": "w", "slot": "weapon", "cost": 1, "name": "x"},
    ])
    e.battle_active = True
    _run([ForEach("f", "fighters", body=[
        Action("equip_best", [LocalVar("f"), Const("weapon")])
    ])], e)
    assert "weapon" not in f.equipment


def test_equip_best_no_op_when_inventory_empty():
    f = FakeFighter("a")
    e = FakeEngine(fighters=[f])
    _run([ForEach("f", "fighters", body=[
        Action("equip_best", [LocalVar("f"), Const("weapon")])
    ])], e)
    assert f.equipment == {}


# ---------- forge_upgrade ----------

def test_forge_upgrade_calls_engine_with_equipped_item():
    f = FakeFighter("a")
    weapon = {"id": "w1", "slot": "weapon", "name": "x", "upgrade_level": 0}
    f.equipment["weapon"] = weapon
    e = FakeEngine(fighters=[f])
    _run([ForEach("f", "fighters", body=[
        Action("forge_upgrade", [LocalVar("f"), Const("weapon")])
    ])], e)
    assert e.upgrade_calls == ["w1"]
    assert weapon["upgrade_level"] == 1


def test_forge_upgrade_no_op_when_slot_empty():
    f = FakeFighter("a")
    e = FakeEngine(fighters=[f])
    _run([ForEach("f", "fighters", body=[
        Action("forge_upgrade", [LocalVar("f"), Const("weapon")])
    ])], e)
    assert e.upgrade_calls == []


def test_forge_upgrade_no_op_during_battle():
    f = FakeFighter("a")
    f.equipment["weapon"] = {"id": "w", "slot": "weapon", "name": "x"}
    e = FakeEngine(fighters=[f])
    e.battle_active = True
    _run([ForEach("f", "fighters", body=[
        Action("forge_upgrade", [LocalVar("f"), Const("weapon")])
    ])], e)
    assert e.upgrade_calls == []


# ---------- engine inventory fields ----------

def test_engine_inv_fields():
    e = FakeEngine(inventory=[
        {"slot": "weapon", "id": "a"},
        {"slot": "weapon", "id": "b"},
        {"slot": "armor",  "id": "c"},
        {"slot": "relic",  "id": "d"},
    ])
    p = Program(name="t", body=[
        Assign("local", "w", EngineField("inv_weapons")),
        Assign("local", "a", EngineField("inv_armor")),
        Assign("local", "r", EngineField("inv_relics")),
        Assign("local", "n", EngineField("inv_accessories")),
        Assign("local", "s", EngineField("inventory_size")),
    ])
    interp = Interpreter(e, p)
    interp.run()
    assert interp.locals == {"w": 2, "a": 1, "r": 1, "n": 0, "s": 4}


# ---------- fighter has_* fields ----------

def test_fighter_has_slot_fields():
    f = FakeFighter("a")
    f.equipment["weapon"] = {"id": "w", "slot": "weapon", "name": "x"}
    e = FakeEngine(fighters=[f])
    interp = Interpreter(e, Program(name="t", body=[
        ForEach("f", "fighters", body=[
            Assign("local", "hw", FighterField(LocalVar("f"), "has_weapon")),
            Assign("local", "ha", FighterField(LocalVar("f"), "has_armor")),
        ])
    ]))
    interp.run()
    assert interp.locals["hw"] is True
    assert interp.locals["ha"] is False


# ---------- end-to-end: grind + buy + equip ----------

def test_full_grind_buy_equip_loop():
    """Simulates the user's request: keep battling until enough gold,
    then buy a weapon, equip it, and continue."""
    f = FakeFighter("a")
    e = FakeEngine(
        fighters=[f],
        gold=0,
        shop=[{"id": "w_cheap", "slot": "weapon", "cost": 100, "name": "stick"}],
    )

    # Program: if not in battle and gold >= 100 → buy + equip; else start battle.
    program = Program(name="grind", body=[
        If(BinOp(">=", EngineField("gold"), Const(100)), [
            Action("buy_item", [Const("weapon")]),
            ForEach("f", "fighters", body=[
                Action("equip_best", [LocalVar("f"), Const("weapon")]),
            ]),
        ], []),
    ])

    # Phase 1: not enough gold → buy must no-op.
    Interpreter(e, program).run()
    assert e.inventory == []
    assert "weapon" not in f.equipment

    # Phase 2: gold accrued → buy + equip kicks in.
    e.gold = 150
    Interpreter(e, program).run()
    assert "weapon" in f.equipment
    assert f.equipment["weapon"]["id"] == "w_cheap"
    assert e.gold == 50  # 150 - 100
