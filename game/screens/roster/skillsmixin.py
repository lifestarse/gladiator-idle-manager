# Build: 1
"""_SkillsMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _SkillsMixin:
    def _show_skills_view(self, fighter_idx):
        """Show passive ability + active skill for a fighter."""
        from game.models import FIGHTER_CLASSES
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]
        self.detail_index = fighter_idx
        self.roster_view = "skills"

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        grid.clear_widgets()

        cls_data = FIGHTER_CLASSES.get(f.fighter_class, {})

        # Header
        grid.add_widget(AutoShrinkLabel(
            text=f"{f.name}  [{f.class_name}]", font_size="13sp", bold=True,
            color=ACCENT_GOLD, halign="center",
            size_hint_y=None, height=dp(44),
        ))

        # Passive ability
        passive = cls_data.get("passive_ability")
        if passive:
            grid.add_widget(AutoShrinkLabel(
                text=t("passive_label"), font_size="11sp", bold=True,
                color=ACCENT_GOLD, halign="left",
                size_hint_y=None, height=dp(30),
            ))
            grid.add_widget(self._build_passive_card(passive))

        # Active skill
        skill = cls_data.get("active_skill")
        if skill:
            grid.add_widget(AutoShrinkLabel(
                text=t("active_skill_label"), font_size="11sp", bold=True,
                color=ACCENT_PURPLE, halign="left",
                size_hint_y=None, height=dp(30),
            ))
            grid.add_widget(self._build_active_skill_card(skill))

    def _build_active_skill_card(self, skill):
        """Build card for a class's active skill."""
        from kivy.uix.label import Label
        card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(90),
                        padding=[dp(10), dp(6)], spacing=dp(2))
        card.border_color = ACCENT_PURPLE

        # Skill name
        name_lbl = AutoShrinkLabel(
            text=skill["name"], font_size="12sp", bold=True,
            color=ACCENT_PURPLE, halign="left",
            size_hint_y=None, height=dp(30),
        )
        bind_text_wrap(name_lbl)
        card.add_widget(name_lbl)

        # Description
        desc_lbl = Label(
            text=skill.get("description", ""), font_size="11sp", font_name='PixelFont',
            color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
        )
        desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
        desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
        desc_lbl.bind(height=lambda inst, h, c=card: setattr(c, "height", max(dp(90), h + dp(70))))
        card.add_widget(desc_lbl)

        # Cooldown
        cd = skill.get("cooldown", 0)
        cd_lbl = AutoShrinkLabel(
            text=t("cooldown_label", n=cd), font_size="11sp", bold=True,
            color=ACCENT_CYAN, halign="left",
            size_hint_y=None, height=dp(26),
        )
        bind_text_wrap(cd_lbl)
        card.add_widget(cd_lbl)

        return card

