# Build: 1
"""GameEngine _CombatSpawnMixin — enemy staging: spawn, boss, arena preview."""
from game.engine._shared import *  # noqa: F401,F403
from game.engine._shared import _m, _log, _ach_module


class _CombatSpawnMixin:
    def _spawn_enemy(self):
        if self._revenge_common:
            self.preview_enemies = self._revenge_common
            self.current_enemy = self._revenge_common[0]
            return
        num = max(1, sum(1 for f in self.fighters if f.available))
        tier = self.arena_tier
        normals = data_loader.normals_by_tier.get(tier)
        enemies = []
        for _ in range(num):
            if normals:
                template = random.choice(normals)
                enemies.append(Enemy.from_template(template, tier))
            else:
                enemies.append(Enemy(tier=tier))
        self.preview_enemies = enemies
        self.current_enemy = enemies[0] if enemies else None

    def refresh_arena_preview(self):
        """Re-roll the common-arena enemy preview to match available fighter count.

        Called after roster composition changes (bench toggle) so the next
        fight's enemy count tracks the active pool. No-op during a battle,
        when a boss is staged, or when revenge enemies are queued (those
        carry their own count).
        """
        if getattr(self, 'battle_active', False):
            return
        if self.current_enemy is not None and getattr(self.current_enemy, 'is_boss', False):
            return
        if self._revenge_common or self._revenge_boss:
            return
        self._spawn_enemy()

    def spawn_boss_enemy(self):
        """Spawn a boss-tier enemy as current_enemy (no battle start)."""
        if self._revenge_boss:
            self.preview_enemies = self._revenge_boss
            self.current_enemy = self._revenge_boss[0]
            return
        bosses = data_loader.bosses_by_tier.get(self.arena_tier)
        if bosses:
            template = random.choice(bosses)
            boss = Boss.from_template(template, self.arena_tier)
        else:
            boss = Boss(self.arena_tier)
        from game.boss_modifiers import BossModifierHandler
        BossModifierHandler(data_loader.boss_modifiers).assign_modifiers(boss, self.arena_tier)
        self.preview_enemies = [boss]
        self.current_enemy = boss
