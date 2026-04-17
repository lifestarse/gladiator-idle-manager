# Build: 1
"""ArenaScreen _HealMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m  # underscore names skipped by star-import


class _HealMixin:
    def _refresh_heal_btn(self, hb, fighters_list, engine, callback):
        """Rebuild or update the Heal All button. O(1) widgets, not per-unit."""
        if not hb:
            return
        cached = getattr(self, "_cached_heal_btn", None)
        cached_cb = getattr(self, "_cached_heal_cb", None)
        # Reuse the same button across refreshes — rebuild only if callback
        # changed (entering/leaving battle flips between _heal_all_battle /
        # _heal_all_outside).
        if cached is None or cached.parent is None or cached_cb is not callback:
            hb.clear_widgets()
            btn = self._build_heal_btn(fighters_list, callback)
            hb.add_widget(btn)
            self._cached_heal_btn = btn
            self._cached_heal_cb = callback
            return

        any_damaged = any(f.hp < f.max_hp for f in fighters_list)
        total_heal_cost = engine.get_hp_heal_cost(fighters_list)
        can_heal = total_heal_cost > 0 and engine.gold > 0 and any_damaged
        cached.text = t("heal_all_cost", cost=f"{fmt_num(total_heal_cost)}") if any_damaged else ""
        cached.btn_color = ACCENT_GREEN if can_heal else BTN_DISABLED
        cached.text_color = BG_DARK if can_heal else TEXT_MUTED
        cached.height = dp(40) if any_damaged else 0
        cached.opacity = 1 if any_damaged else 0
        cached.icon_source = "sprites/icons/ic_gold.png" if any_damaged else ""

    def _heal_single_fighter(self, fighter_idx, in_battle):
        """Heal a single fighter's HP. Works both in and outside battle."""
        engine = App.get_running_app().engine
        if in_battle:
            if not engine.battle_active:
                return
            fighters = engine.battle_mgr.state.player_fighters
        else:
            if engine.battle_active:
                return
            fighters = engine.fighters
        if not (0 <= fighter_idx < len(fighters)):
            return
        f = fighters[fighter_idx]
        if not (f.alive and f.hp > 0 and f.hp < f.max_hp):
            return
        missing = f.max_hp - f.hp
        tier_mult = HP_HEAL_TIER_MULT ** (engine.arena_tier - 1)
        cost = math.ceil(missing / HEAL_GOLD_PER_HP * tier_mult)
        if engine.gold >= cost:
            engine.gold -= cost
            f.hp = f.max_hp
        elif engine.gold > 0:
            heal_hp = int(engine.gold * HEAL_GOLD_PER_HP / tier_mult)
            engine.gold = 0
            f.hp = min(f.max_hp, f.hp + heal_hp)
        else:
            App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(cost)))
            return
        self._spawn_float(t("healed_name", name=f.name), ACCENT_GREEN)
        if not in_battle:
            engine.save()
        self.refresh_ui()

    def heal_fighter(self, fighter_idx):
        self._heal_single_fighter(fighter_idx, in_battle=True)

    def _heal_outside_battle(self, fighter_idx):
        self._heal_single_fighter(fighter_idx, in_battle=False)

    def _heal_all(self, in_battle):
        """Heal all fighters' HP. Works both in and outside battle."""
        engine = App.get_running_app().engine
        if in_battle:
            if not engine.battle_active:
                return
            fighters = engine.battle_mgr.state.player_fighters
        else:
            if engine.battle_active:
                return
            fighters = [f for f in engine.fighters if f.available]
        total_cost = engine.get_hp_heal_cost(fighters)
        healed, spent = engine.heal_all_hp(fighters)
        if healed > 0:
            self._spawn_float(t("healed_amount", n=healed, g=spent), ACCENT_GREEN)
            self.refresh_ui()
        elif total_cost > 0:
            App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(total_cost)))

    def _heal_all_battle(self):
        self._heal_all(in_battle=True)

    def _heal_all_outside(self):
        self._heal_all(in_battle=False)

    def _build_heal_btn(self, fighters_list, callback):
        """Build the Heal All button. Hidden when all fighters are full HP."""
        engine = App.get_running_app().engine
        any_damaged = any(f.hp < f.max_hp for f in fighters_list)
        total_heal_cost = engine.get_hp_heal_cost(fighters_list)
        can_heal = total_heal_cost > 0 and engine.gold > 0 and any_damaged
        visible = any_damaged
        btn = MinimalButton(
            text=t("heal_all_cost", cost=fmt_num(total_heal_cost)) if any_damaged else "",
            btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
            text_color=BG_DARK if can_heal else TEXT_MUTED,
            font_size=11, size_hint_y=None,
            height=dp(40) if visible else 0,
            icon_source="sprites/icons/ic_gold.png" if visible else "",
        )
        btn.opacity = 1 if visible else 0
        btn.bind(on_press=lambda inst: callback())
        return btn
