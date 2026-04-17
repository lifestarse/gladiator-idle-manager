# Build: 1
"""BattleManager _StatsMixin."""
from ._shared import *  # noqa: F401,F403
from ._shared import _fn
from ._types import (BattlePhase, BattleEvent, EnemyStatusTracker,
                      SkillState, BattleState)
from ._enchantments import (_init_enemy_status, _trigger_enchantment,
                             _process_status_ticks)
from ._resolve import _resolve_attack


class _StatsMixin:
    def _init_mod_handler(self):
        from game.boss_modifiers import BossModifierHandler
        from game.data_loader import data_loader
        self._mod_handler = BossModifierHandler(data_loader.boss_modifiers)

    def _fighter_stats(self, fighter):
        """Return (cached) combat-stat snapshot for a Fighter.

        All values come from the Fighter's property chain (attack, defense,
        crit_chance, dodge_chance, crit_mult, max_hp, damage_reduction) —
        each of which walks the equipment dict + perk tree + injuries list.
        Cached per battle; invalidated via `_invalidate_fighter_stats` when
        the fighter's injuries change (permadeath-survived hit).
        """
        cache = self.state.fighter_stat_cache
        key = id(fighter)
        stats = cache.get(key)
        if stats is None:
            # Also snapshot the per-attack perk lookups (lifesteal_pct,
            # on_kill_heal_pct). Previously those called get_perk_effects
            # on every single attack / kill — with 1000 fighters and 44
            # turns that's ~42k + ~1k calls through the perk iteration.
            gpe = getattr(fighter, 'get_perk_effects', lambda x: 0)
            stats = {
                'attack': fighter.attack,
                'defense': fighter.defense,
                'crit_chance': fighter.crit_chance,
                'crit_mult': fighter.crit_mult,
                'dodge_chance': fighter.dodge_chance,
                'max_hp': fighter.max_hp,
                'damage_reduction': getattr(fighter, 'damage_reduction', 0),
                'lifesteal_pct': gpe('lifesteal_pct'),
                'on_kill_heal_pct': gpe('on_kill_heal_pct'),
                'regen_per_turn_pct': gpe('regen_per_turn_pct'),
            }
            cache[key] = stats
        return stats

    def _invalidate_fighter_stats(self, fighter):
        """Drop the cached stat snapshot for a fighter (e.g. after injury)."""
        self.state.fighter_stat_cache.pop(id(fighter), None)
