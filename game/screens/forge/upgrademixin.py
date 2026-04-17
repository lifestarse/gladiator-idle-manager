# Build: 1
"""ForgeScreen _UpgradeMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _UpgradeMixin:
    @staticmethod
    def _fighter_target_total(fighter, target):
        """Current totalized final stat on fighter for a given target."""
        if target == "atk":
            return fighter.attack
        if target == "def":
            return fighter.defense
        if target == "hp":
            return fighter.max_hp
        return 0

    @staticmethod
    def _fighter_pool_value(fighter, stat_names):
        """Sum total_<stat> from fighter for a tuple of stat names."""
        m = {"str": fighter.total_strength,
             "agi": fighter.total_agility,
             "vit": fighter.total_vitality}
        return sum(m[s] for s in stat_names)

    def _build_upgrade_comparison_card(self, item, fighter, engine):
        """Build the stat-comparison BaseCard for an upgrade screen.

        Driven entirely by the SlotDef registry — per-slot branching collapses
        into a loop over slot.upgrade_targets.
        """
        slot_id = item.get("slot", "weapon")
        slot_def = SLOTS.get(slot_id)
        if slot_def is None:
            # Non-equipment fallback (shouldn't reach the upgrade screen, but
            # leave a safe path in case data drifts).
            slot_def = SLOTS["weapon"]

        is_relic = (slot_id == "relic")
        rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
        current_lvl = item.get("upgrade_level", 0)
        max_lvl = get_max_upgrade(item)

        num_rows = (12 if is_relic else 8) if fighter else 5
        comp_card = BC(
            orientation="vertical", size_hint_y=None, height=dp(30 + num_rows * 24),
            padding=[dp(12), dp(8)], spacing=dp(2),
        )
        comp_card.border_color = rcolor
        comp_card.add_label(item_display_name(item), font_size=sp(11), bold=True,
                            color=rcolor, halign="center", size_hint_y=0.15)

        def _info_row(label, value, color=TEXT_SECONDARY):
            return comp_card.add_text_row(
                (label, sp(6), False, TEXT_MUTED, 0.5),
                (str(value), sp(7), True, color, 0.5),
                height=dp(30),
            )

        def _pool_display(stat_names):
            return "+".join(s.upper() for s in stat_names)

        def _breakdown(pct, label_prefix):
            # No fighter context → compact summary describing the formula.
            if not fighter:
                for target in slot_def.upgrade_targets:
                    pool = slot_def.pool_for(target)
                    mult = slot_def.mult_for(target)
                    mult_s = f"x{int(mult)}" if mult != 1.0 else ""
                    div_s = f"/{slot_def.split_divisor}" if slot_def.split_divisor > 1 else ""
                    target_label = self._TARGET_LABELS.get(target, target.upper())
                    if is_relic:
                        # Compact single-line summary for relics (they list all 3).
                        _info_row(
                            f"{label_prefix} {t('bonus_label')}",
                            f"{pct}%{div_s} → ATK+DEF+HP",
                            ACCENT_GREEN,
                        )
                        return
                    _info_row(
                        f"{label_prefix} {t('bonus_label')}",
                        f"{pct}% ({_pool_display(pool)}){mult_s} → {target_label}",
                        ACCENT_GREEN,
                    )
                return

            # Fighter context → show pool value, computed bonus, running total.
            for target in slot_def.upgrade_targets:
                pool = slot_def.pool_for(target)
                mult = slot_def.mult_for(target)
                pair_val = self._fighter_pool_value(fighter, pool)
                bonus = int(pair_val * pct / 100 * mult) // slot_def.split_divisor
                mult_s = f" x{int(mult)}" if mult != 1.0 else ""
                div_s = f"/{slot_def.split_divisor}" if slot_def.split_divisor > 1 else ""
                target_label = self._TARGET_LABELS.get(target, target.upper())
                if is_relic:
                    _info_row(
                        f"{label_prefix} {target_label} ({pct}%{div_s})",
                        f"+{bonus}",
                        ACCENT_GREEN,
                    )
                else:
                    _info_row(
                        f"{label_prefix} ({pct}% {_pool_display(pool)}{mult_s})",
                        f"+{bonus} {target_label}",
                        ACCENT_GREEN,
                    )
                    _info_row(
                        f"{t('total_label')} {target_label}",
                        self._fighter_target_total(fighter, target),
                        ACCENT_GOLD,
                    )

        # Context rows above the breakdown.
        if fighter and slot_id == "weapon":
            _info_row(f"STR ({fighter.total_strength}) x2", fighter.total_strength * 2, ACCENT_RED)
            _info_row("STR+AGI", f"{fighter.total_strength}+{fighter.total_agility}={fighter.total_strength + fighter.total_agility}", TEXT_SECONDARY)
        elif fighter and slot_id == "armor":
            _info_row("AGI+VIT", f"{fighter.total_agility}+{fighter.total_vitality}={fighter.total_agility + fighter.total_vitality}", TEXT_SECONDARY)
        elif fighter and slot_id == "accessory":
            _info_row("VIT+STR", f"{fighter.total_vitality}+{fighter.total_strength}={fighter.total_vitality + fighter.total_strength}", TEXT_SECONDARY)

        base_label_key = slot_def.label_keys.get("base", "")
        base_label = t(base_label_key) if base_label_key else ""
        if is_relic:
            # Relics provide STR/AGI/VIT (not flat ATK/DEF/HP). These feed into
            # all three final stats via the upgrade formulas.
            _info_row(t("relic_base"),
                      f"STR+{item.get('str',0)} AGI+{item.get('agi',0)} VIT+{item.get('vit',0)}",
                      TEXT_PRIMARY)
        else:
            # Non-relic items have a primary stat matching their target.
            # weapon→STR, armor→AGI, accessory→VIT
            primary_stat_map = {"weapon": "str", "armor": "agi", "accessory": "vit"}
            base_val = item.get(primary_stat_map.get(slot_id, "str"), 0)
            _info_row(base_label, f"+{base_val}", TEXT_PRIMARY)
        _breakdown(current_lvl * UPGRADE_BONUS_PER_LEVEL, f"+{current_lvl}")

        if current_lvl < max_lvl:
            next_lvl = current_lvl + 1
            comp_card.add_widget(AutoShrinkLabel(
                text=f"--- +{next_lvl} ---", font_size="11sp",
                color=ACCENT_GOLD, halign="center", size_hint_y=None, height=dp(30),
            ))
            _breakdown(next_lvl * UPGRADE_BONUS_PER_LEVEL, f"+{next_lvl}")
            tier, count = get_upgrade_tier(next_lvl)
            count *= slot_def.shard_multiplier
            have = engine.shards.get(tier, 0)
            cost_text = f"{count}x {t('shard_tier_' + str(tier) + '_name')}"
            _info_row(t("cost_label"),
                      f"{cost_text} ({t('have_label')}: {have})",
                      ACCENT_GREEN if have >= count else ACCENT_RED)
        else:
            comp_card.add_widget(AutoShrinkLabel(
                text=f"MAX +{max_lvl}", font_size="11sp", bold=True,
                color=ACCENT_GOLD, halign="center", size_hint_y=None, height=dp(30),
            ))
        return comp_card

    def _show_item_upgrade(self, source, idx, item, fighter=None):
        """Universal upgrade screen for any equipment slot."""
        self._enter_detail_mode()
        self._set_view("upgrade")
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        engine = App.get_running_app().engine
        slot_id = item.get("slot", "weapon")
        slot_def = SLOTS.get(slot_id)
        current_lvl = item.get("upgrade_level", 0)
        max_lvl = get_max_upgrade(item)

        grid.add_widget(self._build_upgrade_comparison_card(item, fighter, engine))

        if current_lvl < max_lvl:
            tier, count = get_upgrade_tier(current_lvl + 1)
            if slot_def is not None:
                count *= slot_def.shard_multiplier
            have = engine.shards.get(tier, 0)
            can_upgrade = have >= count
            upg_btn = MinimalButton(
                text=f"{t('upgrade_btn')} +{current_lvl + 1}", font_size=11,
                btn_color=ACCENT_GREEN if can_upgrade else BTN_DISABLED,
                text_color=BG_DARK if can_upgrade else TEXT_MUTED,
                size_hint_y=None, height=dp(46),
            )
            def _do_upgrade(inst, w=item, s=source, i=idx, f=fighter):
                result = engine.upgrade_item(w)
                if result.ok:
                    self._sparkle_effect(inst)
                    self._show_item_upgrade(s, i, w, f)
                else:
                    App.get_running_app().show_toast(result.message)
            upg_btn.bind(on_press=_do_upgrade)
            grid.add_widget(upg_btn)
