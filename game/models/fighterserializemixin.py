# Build: 7
"""Fighter _FighterSerializeMixin — to_dict / from_dict save round-trip."""
from ._imports import *  # noqa: F401,F403
from ._helpers import *  # noqa: F401,F403
from ._scaling import DifficultyScaler
from ._combat import CombatUnit
from ._data import FIGHTER_NAMES, FIGHTER_CLASSES


class _FighterSerializeMixin:
    def to_dict(self):
        return {
            "name": self.name,
            "fighter_class": self.fighter_class,
            "level": self.level,
            "strength": self.strength,
            "agility": self.agility,
            "vitality": self.vitality,
            "unused_points": self.unused_points,
            "crit_bonus": self.crit_bonus,
            "dodge_bonus": self.dodge_bonus,
            "hp_mult": self.hp_mult,
            "points_per_level": self.points_per_level,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_hp": self.base_hp,
            "hp": self.hp,
            "alive": self.alive,
            "injuries": [inj.copy() for inj in self.injuries],
            "kills": self.kills,
            "perk_points": self.perk_points,
            # Copies, not references: save_async JSON-dumps this snapshot on
            # a worker thread — a shared list/dict mutated by the main
            # thread mid-dump (equip, perk unlock) kills the save with
            # "changed size during iteration".
            "unlocked_perks": list(self.unlocked_perks),
            "equipment": {k: (dict(v) if isinstance(v, dict) else v)
                          for k, v in self.equipment.items()},
            "on_expedition": self.on_expedition,
            "expedition_id": self.expedition_id,
            "expedition_end": self.expedition_end,
            "is_active": self.is_active,
            "stamina": self.stamina,
            "fatigue": self.fatigue,
            "auto_distribute_enabled": self.auto_distribute_enabled,
        }

    @classmethod
    def from_dict(cls, data):
        g = cls.__new__(cls)
        g.name = data.get("name", "Unknown")
        g.fighter_class = data.get("fighter_class", "mercenary")
        g.level = data.get("level", 1)
        g.strength = data.get("strength", 5)
        g.agility = data.get("agility", 5)
        g.vitality = data.get("vitality", 5)
        g.unused_points = data.get("unused_points", 0)
        cls_data = FIGHTER_CLASSES.get(g.fighter_class, FIGHTER_CLASSES["mercenary"])
        g.crit_bonus = data.get("crit_bonus", cls_data["crit_bonus"])
        g.dodge_bonus = data.get("dodge_bonus", cls_data["dodge_bonus"])
        g.hp_mult = data.get("hp_mult", cls_data["hp_mult"])
        g.points_per_level = data.get("points_per_level", cls_data["points_per_level"])
        g.base_attack = data.get("base_attack", 0)
        g.base_defense = data.get("base_defense", 0)
        g.base_hp = data.get("base_hp", 0)
        g.hp = data.get("hp", 50)
        g.alive = data.get("alive", True)
        g.injuries = data.get("injuries", [])
        # Migration: ensure each injury dict carries auto-heal progress counter.
        for inj in g.injuries:
            inj.setdefault("heal_progress", 0)
        g.kills = data.get("kills", 0)
        g.perk_points = data.get("perk_points", 0)
        g.unlocked_perks = data.get("unlocked_perks", [])
        equip = data.get("equipment", {"weapon": None, "armor": None, "accessory": None, "relic": None})
        # Back-compat: old saves didn't have a 'relic' slot.
        if "relic" not in equip:
            equip["relic"] = None
        g.equipment = equip
        g.on_expedition = data.get("on_expedition", False)
        g.expedition_id = data.get("expedition_id")
        g.expedition_end = data.get("expedition_end", 0.0)
        g.is_active = data.get("is_active", True)
        from game.constants import STAMINA_MAX
        g.stamina = data.get("stamina", STAMINA_MAX)
        g.fatigue = data.get("fatigue", 0)
        g.auto_distribute_enabled = data.get("auto_distribute_enabled", False)
        return g
