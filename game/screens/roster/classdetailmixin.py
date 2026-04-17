# Build: 1
"""_ClassDetailMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _ClassDetailMixin:
    def _show_class_detail(self, cls_id):
        """Full detail page for a fighter class — description, stats, passive, perk tree."""
        from kivy.uix.label import Label
        engine = App.get_running_app().engine
        cls_data = _m.FIGHTER_CLASSES.get(cls_id)
        if not cls_data:
            return
        self._class_detail_id = cls_id
        self.roster_view = "class_detail"
        self.hire_cost_text = t("recruit_btn", cost=fmt_num(engine.hire_cost))
        self.hire_enabled = "true" if engine.gold >= engine.hire_cost else "false"
        cls_color = self._CLASS_COLORS.get(cls_id, ACCENT_BLUE)

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        # Class name
        grid.add_widget(AutoShrinkLabel(
            text=cls_data["name"], font_size="12sp", bold=True,
            color=cls_color, halign="center",
            size_hint_y=None, height=dp(36),
        ))

        # Base stats
        grid.add_widget(AutoShrinkLabel(
            text=f"STR {cls_data['base_str']}   AGI {cls_data['base_agi']}   VIT {cls_data['base_vit']}",
            font_size="11sp", bold=True, color=TEXT_SECONDARY, halign="center",
            size_hint_y=None, height=dp(26),
        ))

        # Description (dynamic height)
        desc_text = cls_data.get("desc", cls_data.get("description", ""))
        if desc_text:
            desc_lbl = Label(
                text=desc_text, font_size="10sp", font_name='PixelFont',
                color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
            )
            desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(16), None)))
            desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)))
            grid.add_widget(desc_lbl)

        # Modifiers
        mods = []
        if cls_data.get("crit_bonus", 0) != 0:
            sign = "+" if cls_data["crit_bonus"] > 0 else ""
            mods.append(f"CRIT {sign}{cls_data['crit_bonus']:.0%}")
        if cls_data.get("dodge_bonus", 0) != 0:
            sign = "+" if cls_data["dodge_bonus"] > 0 else ""
            mods.append(f"DODGE {sign}{cls_data['dodge_bonus']:.0%}")
        if cls_data.get("hp_mult", 1.0) != 1.0:
            mods.append(f"HP x{cls_data['hp_mult']:.2g}")
        pts = cls_data.get("points_per_level", 3)
        mods.append(t("class_points_per_level", n=pts))
        if mods:
            mod_hdr = AutoShrinkLabel(
                text=t("class_modifiers_label"), font_size="10sp", bold=True,
                color=cls_color, halign="left",
                size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(mod_hdr)
            grid.add_widget(mod_hdr)
            mod_lbl = AutoShrinkLabel(
                text="   ".join(mods), font_size="10sp",
                color=TEXT_SECONDARY, halign="center",
                size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(mod_lbl)
            grid.add_widget(mod_lbl)

        # Passive ability
        passive = cls_data.get("passive_ability")
        if passive:
            grid.add_widget(AutoShrinkLabel(
                text=t("perk_passive_label"), font_size="10sp", bold=True,
                color=ACCENT_GOLD, halign="left",
                size_hint_y=None, height=dp(30),
            ))
            p_card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(70),
                              padding=[dp(10), dp(6)], spacing=dp(2))
            p_card.border_color = ACCENT_GOLD
            passive_name_lbl = AutoShrinkLabel(
                text=passive["name"], font_size="10sp", bold=True,
                color=ACCENT_GOLD, halign="left",
                size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(passive_name_lbl)
            p_card.add_widget(passive_name_lbl)
            p_desc = Label(
                text=passive.get("description", ""), font_size="11sp", font_name='PixelFont',
                color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
            )
            p_desc.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
            p_desc.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
            p_desc.bind(height=lambda inst, h, c=p_card: setattr(c, "height", max(dp(70), h + dp(40))))
            p_card.add_widget(p_desc)
            grid.add_widget(p_card)

        # Active skill — same layout as passive but purple accent + cooldown.
        # Was missing from the hire preview entirely; players couldn't see
        # what Rally/Frenzy/Shield Wall etc. did until after recruiting.
        active = cls_data.get("active_skill")
        if active:
            grid.add_widget(AutoShrinkLabel(
                text=t("active_skill_label"), font_size="10sp", bold=True,
                color=ACCENT_PURPLE, halign="left",
                size_hint_y=None, height=dp(30),
            ))
            a_card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(90),
                              padding=[dp(10), dp(6)], spacing=dp(2))
            a_card.border_color = ACCENT_PURPLE
            active_name_lbl = AutoShrinkLabel(
                text=active["name"], font_size="12sp", bold=True,
                color=ACCENT_PURPLE, halign="left",
                size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(active_name_lbl)
            a_card.add_widget(active_name_lbl)
            a_desc = Label(
                text=active.get("description", ""), font_size="11sp", font_name='PixelFont',
                color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
            )
            a_desc.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
            a_desc.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
            a_desc.bind(height=lambda inst, h, c=a_card: setattr(c, "height", max(dp(90), h + dp(60))))
            a_card.add_widget(a_desc)
            cd = active.get("cooldown", 0)
            if cd:
                cd_lbl = AutoShrinkLabel(
                    text=t("cooldown_label", n=cd), font_size="11sp", bold=True,
                    color=ACCENT_CYAN, halign="left",
                    size_hint_y=None, height=dp(26),
                )
                bind_text_wrap(cd_lbl)
                a_card.add_widget(cd_lbl)
            grid.add_widget(a_card)

        # Perk tree preview
        tree = cls_data.get("perk_tree", [])
        if tree:
            grid.add_widget(AutoShrinkLabel(
                text=t("class_perks_label"), font_size="10sp", bold=True,
                color=cls_color, halign="left",
                size_hint_y=None, height=dp(30),
            ))
            tiers = {}
            for perk in tree:
                tiers.setdefault(perk.get("tier", 1), []).append(perk)
            for tier_num in sorted(tiers.keys()):
                grid.add_widget(AutoShrinkLabel(
                    text=t("perk_tier_label", n=tier_num), font_size="10sp", bold=True,
                    color=ACCENT_CYAN, halign="left",
                    size_hint_y=None, height=dp(30),
                ))
                for perk in tiers[tier_num]:
                    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(70),
                                    padding=[dp(10), dp(6)], spacing=dp(2))
                    card.border_color = BTN_DISABLED
                    perk_name_lbl = AutoShrinkLabel(
                        text=f"{perk['name']}  ({perk['cost']} pts)",
                        font_size="10sp", bold=True, color=TEXT_PRIMARY,
                        halign="left", size_hint_y=None, height=dp(18),
                    )
                    bind_text_wrap(perk_name_lbl)
                    card.add_widget(perk_name_lbl)
                    pk_desc = Label(
                        text=perk.get("description", ""), font_size="11sp", font_name='PixelFont',
                        color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
                    )
                    pk_desc.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
                    pk_desc.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
                    pk_desc.bind(height=lambda inst, h, c=card: setattr(c, "height", max(dp(70), h + dp(40))))
                    card.add_widget(pk_desc)
                    grid.add_widget(card)

