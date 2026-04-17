# Build: 1
"""ArenaScreen _EnemyPopupMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _EnemyPopupMixin:
    def _show_enemy_popup_by_name(self, enemy_name):
        """RV callback — find the enemy object by name, then open detail."""
        engine = App.get_running_app().engine
        pool = []
        if engine.battle_active:
            pool = list(engine.battle_mgr.state.enemies)
        else:
            pool = list(engine.preview_enemies)
        for e in pool:
            if e.name == enemy_name:
                self._show_enemy_popup(e)
                return

    def _show_enemy_popup(self, enemy):
        """Show enemy stats as inline view replacing battle UI."""
        self.arena_view = "enemy_detail"
        grid = self.ids.get("enemy_detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        is_boss = getattr(enemy, 'is_boss', False)
        border = ACCENT_PURPLE if is_boss else ACCENT_RED
        name_prefix = ""  # boss name already includes "BOSS:" from models.py

        def _lbl(text, size=sp(8), bold=False, color=None):
            lbl = AutoShrinkLabel(
                text=text, font_size=size, bold=bold,
                color=color or border,
                halign="center", valign="middle",
                size_hint_y=None, height=dp(32),
            )
            bind_text_wrap(lbl)
            return lbl

        grid.add_widget(_lbl(f"{name_prefix}{enemy.name}", sp(13), bold=True))
        grid.add_widget(_lbl(t("arena_tier_enemy", n=enemy.tier), sp(7), color=TEXT_MUTED))
        grid.add_widget(_lbl(
            f"HP  {fmt_num(enemy.max_hp)}", sp(9), bold=True))
        grid.add_widget(_lbl(
            f"ATK  {fmt_num(enemy.attack)}    DEF  {fmt_num(enemy.defense)}", sp(9), bold=True))
        grid.add_widget(_lbl(
            f"CRIT  {enemy.crit_chance * 100:.0f}%    DODGE  {enemy.dodge_chance * 100:.0f}%",
            sp(8), color=TEXT_SECONDARY))
        grid.add_widget(_lbl(
            f"REWARD  {fmt_num(enemy.gold_reward)} G", sp(8), color=ACCENT_GREEN))

        # Boss modifiers
        mods = getattr(enemy, 'modifiers', [])
        if mods and is_boss:
            from game.data_loader import data_loader
            for mid in mods:
                mod_def = data_loader.boss_modifiers.get(mid, {})
                mod_name = mod_def.get("name", mid)
                mod_desc = mod_def.get("description", "")
                grid.add_widget(_lbl(
                    f"[{mod_name}] {mod_desc}", sp(7), color=ACCENT_PURPLE))

    def _close_enemy_detail(self):
        self.arena_view = "battle"
