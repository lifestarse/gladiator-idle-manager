# Build: 27
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.metrics import dp, sp
from kivy.uix.image import Image as KvImage
from kivy.uix.scrollview import ScrollView
from kivy.effects.scroll import ScrollEffect
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard
import game.models as _m
from game.models import (
    fmt_num, RARITY_COLORS,
    FORGE_WEAPONS, FORGE_ARMOR, FORGE_ACCESSORIES,
    item_display_name,
)
from game.theme import *
from game.theme import popup_color
from game.localization import t
from game.ui_helpers import (
    refresh_roster_grid,
    build_item_info_card,
    _roster_callbacks,
    bind_text_wrap,
    make_styled_popup,
)
from game.screens.shared import _safe_clear, _safe_rebind


class RosterScreen(BaseScreen):
    gladiators_data = ListProperty()
    graveyard_text = StringProperty("")
    hire_cost_text = StringProperty("")
    hire_enabled = StringProperty("true")
    heal_all_text = StringProperty("")
    heal_all_enabled = StringProperty("false")
    has_injuries = StringProperty("false")
    detail_index = NumericProperty(-1)
    roster_view = StringProperty("list")  # "list", "detail", "hire", "class_detail"
    perk_view = BooleanProperty(False)

    _pending_state = None

    def get_nav_state(self):
        """Snapshot current view for navigation stack."""
        return {
            'roster_view': self.roster_view,
            'detail_index': self.detail_index,
            'perk_view': self.perk_view,
        }

    def restore_nav_state(self, state):
        """Restore view from navigation stack — on_enter will use this."""
        self._pending_state = state

    def on_enter(self):
        _roster_callbacks['show_detail'] = self.show_fighter_detail
        _roster_callbacks['dismiss'] = self.dismiss
        state = self._pending_state
        self._pending_state = None
        self._entered_with_detail = False
        if state:
            idx = state.get('detail_index', -1)
            view = state.get('roster_view', 'list')
            if view == "skills" and idx >= 0:
                self._entered_with_detail = True
                self._show_skills_view(idx)
                return
            if idx >= 0:
                self._entered_with_detail = True
                self.show_fighter_detail(idx)
                if state.get('perk_view'):
                    self._show_perk_tree(idx)
                return
            if view == "hire":
                self._entered_with_detail = True
                self.roster_view = "hire"
                self.detail_index = -1
                self._show_hire_view()
                return
        self.detail_index = -1
        self.roster_view = "list"
        self.refresh_roster()

    def refresh_roster(self):
        engine = App.get_running_app().engine
        self._update_top_bar()
        deaths = engine.total_deaths
        self.graveyard_text = t("fallen", n=deaths) if deaths > 0 else ""
        # Fast path: skip if fighters haven't changed
        roster_key = tuple(
            (f.name, f.level, f.hp, f.alive, f.injury_count, f.on_expedition,
             i == engine.active_fighter_idx)
            for i, f in enumerate(engine.fighters)
        )
        hire_affordable = engine.gold >= engine.hire_cost
        full_key = (roster_key, hire_affordable)
        if not self._needs_rebuild(self, '_roster_key', full_key):
            return

        self.gladiators_data = [
            {
                "name": f.name, "level": f.level,
                "fighter_class": f.fighter_class,
                "fighter_class_name": f.class_name,
                "str": f.strength, "agi": f.agility, "vit": f.vitality,
                "unused_points": f.unused_points,
                "atk": f.attack, "def": f.defense, "hp": f.max_hp,
                "current_hp": f.hp,
                "crit": f.crit_chance, "dodge": f.dodge_chance,
                "cost": f.upgrade_cost,
                "index": i, "active": i == engine.active_fighter_idx,
                "alive": f.alive, "injuries": f.injury_count, "kills": f.kills,
                "perk_points": f.perk_points,
                "death_chance": f.death_chance,
                "on_expedition": f.on_expedition,
                "weapon": f.equipment.get("weapon"),
                "armor": f.equipment.get("armor"),
                "accessory": f.equipment.get("accessory"),
                "relic": f.equipment.get("relic"),
            }
            for i, f in enumerate(engine.fighters)
        ]
        self.hire_cost_text = t("recruit_btn", cost=fmt_num(engine.hire_cost))
        self.hire_enabled = "true" if hire_affordable else "false"
        heal_cost = engine.heal_all_injuries_cost()
        has_injuries = heal_cost > 0
        can_afford = engine.gold >= heal_cost and has_injuries
        self.heal_all_text = t("heal_all_injuries_cost", cost=fmt_num(heal_cost)) if has_injuries else t("heal_all_injuries")
        self.heal_all_enabled = "true" if can_afford else "false"
        self.has_injuries = "true" if has_injuries else "false"
        refresh_roster_grid(self)

    def upgrade(self, index):
        app = App.get_running_app()
        result = app.engine.upgrade_gladiator(index)
        if not result.ok and result.message:
            app.show_toast(result.message)
        self.refresh_roster()

    def set_active(self, index):
        App.get_running_app().engine.active_fighter_idx = index
        self.refresh_roster()

    def hire(self):
        engine = App.get_running_app().engine
        cls_id = getattr(self, '_class_detail_id', None)
        if cls_id and self.roster_view == "class_detail":
            if engine.gold < engine.hire_cost:
                App.get_running_app().show_toast(t("not_enough_gold", need=fmt_num(engine.hire_cost - engine.gold)))
                return
            engine.hire_gladiator(cls_id)
            self._class_detail_id = None
            self.close_detail()
            return
        if self.roster_view in ("hire", "class_detail"):
            return
        self.roster_view = "hire"
        self.detail_index = -1
        self._show_hire_view()

    _CLASS_COLORS = {
        "mercenary": ACCENT_GREEN, "assassin": ACCENT_RED, "tank": ACCENT_BLUE,
        "berserker": ACCENT_RED, "retiarius": ACCENT_CYAN, "medicus": ACCENT_PURPLE,
    }

    def _show_hire_view(self):
        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)
        self._class_detail_id = None

        grid.add_widget(AutoShrinkLabel(
            text=t("choose_class"), font_size="10sp",
            color=ACCENT_GOLD, size_hint_y=None, height=dp(30),
        ))

        for cls_id, cls_data in _m.FIGHTER_CLASSES.items():
            cls_color = self._CLASS_COLORS.get(cls_id, ACCENT_BLUE)
            card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(60),
                            padding=[dp(12), dp(6)], spacing=dp(2))
            card.border_color = cls_color
            card.add_widget(card._make_label(cls_data["name"], sp(10), True, cls_color, "left", 1))
            card.add_widget(card._make_label(
                f"STR {cls_data['base_str']}  AGI {cls_data['base_agi']}  VIT {cls_data['base_vit']}",
                sp(7), False, TEXT_SECONDARY, "left", 1))
            card.bind(on_press=lambda inst, cid=cls_id: self._show_class_detail(cid))
            grid.add_widget(card)

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

        # Recruit button is in the fixed bottom panel (KV)

    def _back_to_hire(self):
        self._class_detail_id = None
        self.roster_view = "hire"
        self._show_hire_view()

    def _show_injuries_view(self, fighter_idx):
        """Separate view listing all injuries with heal buttons."""
        from game.data_loader import data_loader
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]
        self.detail_index = fighter_idx
        self._injuries_list_idx = fighter_idx
        self.roster_view = "detail"

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        # Title
        grid.add_widget(AutoShrinkLabel(
            text=f"{f.name} — {t('injuries_tab')}",
            font_size="11sp", bold=True, color=ACCENT_RED,
            halign="center", size_hint_y=None, height=dp(30),
        ))
        grid.add_widget(AutoShrinkLabel(
            text=f"{t('death_risk')}: {f.death_chance:.0%}",
            font_size="10sp", color=ACCENT_RED,
            halign="center", size_hint_y=None, height=dp(30),
        ))

        # Heal all button
        healable = [i for i, inj in enumerate(f.injuries)
                    if data_loader.injuries_by_id.get(inj["id"], {}).get("heal_cost_multiplier", 1) != 0]
        if len(healable) > 1:
            total_cost = engine.heal_fighter_all_injuries_cost(fighter_idx)
            can_heal_all = total_cost > 0 and engine.gold >= total_cost
            heal_all_btn = MinimalButton(
                text=f"{t('heal_all_injuries_btn')} ({fmt_num(total_cost)})",
                font_size=11, btn_color=ACCENT_GREEN if can_heal_all else BTN_DISABLED,
                text_color=BG_DARK if can_heal_all else TEXT_MUTED,
                size_hint_y=None, height=dp(40),
                icon_source="sprites/icons/ic_gold.png",
            )
            def _heal_all(inst, fi=fighter_idx):
                result = engine.heal_fighter_all_injuries(fi)
                if result.ok:
                    App.get_running_app().show_toast(result.message)
                    if engine.fighters[fi].injury_count > 0:
                        self._show_injuries_view(fi)
                    else:
                        self.show_fighter_detail(fi)
                else:
                    App.get_running_app().show_toast(result.message)
            heal_all_btn.bind(on_press=_heal_all)
            grid.add_widget(heal_all_btn)

        # Individual injuries
        for i_idx, inj in enumerate(f.injuries):
            inj_data = data_loader.injuries_by_id.get(inj["id"], {})
            severity = inj_data.get("severity", "?")
            name = inj_data.get("name", inj["id"])
            is_perm = inj_data.get("heal_cost_multiplier", 1) == 0
            perm_tag = f" {t('permanent_injury_tag')}" if is_perm else ""
            sev_color = ACCENT_RED if severity in ("severe", "permanent") else TEXT_MUTED

            card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(70),
                            padding=[dp(10), dp(6)], spacing=dp(2))
            card.border_color = sev_color

            inj_name_lbl = AutoShrinkLabel(
                text=f"[{severity.upper()}] {name}{perm_tag}",
                font_size="10sp", bold=True, color=sev_color,
                halign="left", size_hint_y=None, height=dp(30),
            )
            bind_text_wrap(inj_name_lbl)
            card.add_widget(inj_name_lbl)

            # Stat penalties summary
            penalties = inj_data.get("stat_penalties", [])
            if penalties:
                pen_parts = []
                for pen in penalties:
                    stat = pen.get("stat", "?").replace("_", " ").upper()
                    val = pen.get("value", 0)
                    pen_parts.append(f"{stat} -{val:.0%}")
                pen_lbl = AutoShrinkLabel(
                    text="  ".join(pen_parts), font_size="11sp",
                    color=ACCENT_RED, halign="left",
                    size_hint_y=None, height=dp(16),
                )
                bind_text_wrap(pen_lbl)
                card.add_widget(pen_lbl)

            if not is_perm:
                heal_cost = f.get_injury_heal_cost(i_idx)
                can_heal = engine.gold >= heal_cost
                heal_btn = MinimalButton(
                    text=f"{t('heal_btn')} {fmt_num(heal_cost)}",
                    font_size=11, btn_color=ACCENT_GREEN if can_heal else BTN_DISABLED,
                    text_color=BG_DARK if can_heal else TEXT_MUTED,
                    size_hint_y=None, height=dp(28),
                    icon_source="sprites/icons/ic_gold.png",
                )
                def _heal_one(inst, idx=fighter_idx, ii=i_idx):
                    result = engine.heal_fighter_injury(idx, ii)
                    if result.ok:
                        App.get_running_app().show_toast(result.message)
                        if engine.fighters[idx].injury_count > 0:
                            self._show_injuries_view(idx)
                        else:
                            self.show_fighter_detail(idx)
                    else:
                        App.get_running_app().show_toast(result.message)
                heal_btn.bind(on_press=_heal_one)
                card.add_widget(heal_btn)

            card.bind(on_press=lambda inst, iid=inj["id"], fi=fighter_idx:
                      self._show_injury_detail(iid, fi))
            grid.add_widget(card)

    def _show_injury_detail(self, injury_id, fighter_idx):
        """Show full injury info page."""
        from kivy.uix.label import Label
        from game.data_loader import data_loader
        inj_data = data_loader.injuries_by_id.get(injury_id, {})
        if not inj_data:
            return
        self._injury_detail = (injury_id, fighter_idx)
        self.roster_view = "detail"

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        severity = inj_data.get("severity", "?")
        is_perm = inj_data.get("heal_cost_multiplier", 1) == 0
        sev_colors = {
            "minor": TEXT_MUTED, "moderate": ACCENT_GOLD,
            "severe": ACCENT_RED, "permanent": ACCENT_RED,
        }
        sev_color = sev_colors.get(severity, TEXT_MUTED)

        # Name
        grid.add_widget(AutoShrinkLabel(
            text=inj_data.get("name", injury_id), font_size="11sp", bold=True,
            color=sev_color, halign="center",
            size_hint_y=None, height=dp(34),
        ))

        # Severity + body part
        body_part = inj_data.get("body_part", "").replace("_", " ").title()
        tag_text = f"[{severity.upper()}]"
        if is_perm:
            tag_text += f"  {t('permanent_injury_tag')}"
        if body_part:
            tag_text += f"  —  {body_part}"
        grid.add_widget(AutoShrinkLabel(
            text=tag_text, font_size="10sp", color=sev_color,
            halign="center", size_hint_y=None, height=dp(30),
        ))

        # Description
        desc = inj_data.get("description", "")
        if desc:
            desc_lbl = Label(
                text=desc, font_size="11sp", font_name='PixelFont',
                color=TEXT_SECONDARY, halign="left", valign="top", size_hint_y=None,
            )
            desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(16), None)))
            desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)))
            grid.add_widget(desc_lbl)

        # Stat penalties
        penalties = inj_data.get("stat_penalties", [])
        if penalties:
            grid.add_widget(AutoShrinkLabel(
                text=t("class_modifiers_label"), font_size="10sp", bold=True,
                color=ACCENT_RED, halign="left",
                size_hint_y=None, height=dp(26),
            ))
            for pen in penalties:
                stat = pen.get("stat", "?").replace("_", " ").upper()
                val = pen.get("value", 0)
                grid.add_widget(AutoShrinkLabel(
                    text=f"  {stat}  -{val:.0%}", font_size="10sp",
                    color=ACCENT_RED, halign="left",
                    size_hint_y=None, height=dp(30),
                ))

        # Heal info
        if is_perm:
            grid.add_widget(AutoShrinkLabel(
                text=t("no_healable_injuries"), font_size="10sp",
                color=TEXT_MUTED, halign="center",
                size_hint_y=None, height=dp(26),
            ))
        else:
            mult = inj_data.get("heal_cost_multiplier", 1.0)
            grid.add_widget(AutoShrinkLabel(
                text=t("heal_cost_mult", mult=f"{mult:.1f}"), font_size="10sp",
                color=ACCENT_GREEN, halign="center",
                size_hint_y=None, height=dp(26),
            ))


    def _back_from_injury(self):
        idx = getattr(self, '_injury_detail', (None, -1))[1]
        self._injury_detail = None
        if idx >= 0:
            self._show_injuries_view(idx)
        else:
            self.close_detail()

    def dismiss(self, index):
        App.get_running_app().engine.dismiss_dead(index)
        self.refresh_roster()

    def add_str(self, index):
        App.get_running_app().engine.distribute_stat(index, "strength")
        self.refresh_roster()

    def add_agi(self, index):
        App.get_running_app().engine.distribute_stat(index, "agility")
        self.refresh_roster()

    def add_vit(self, index):
        App.get_running_app().engine.distribute_stat(index, "vitality")
        self.refresh_roster()

    def heal_all_injuries(self):
        app = App.get_running_app()
        result = app.engine.heal_all_injuries()
        if not result.ok and result.message:
            app.show_toast(result.message)
        self.refresh_roster()

    def _build_fighter_header(self, grid, f, index, engine):
        """Add name/stats/attribute rows to detail grid."""
        header_lbl = AutoShrinkLabel(
            text=f"{f.name}  [{f.class_name}]  Lv.{f.level}", font_size="13sp", bold=True,
            color=ACCENT_GOLD, size_hint_y=None, height=dp(44), halign="center",
        )
        bind_text_wrap(header_lbl)
        grid.add_widget(header_lbl)

        def _c(color):
            return ''.join(f'{int(v*255):02x}' for v in color[:3])
        rc, gc, bc = _c(ACCENT_RED), _c(ACCENT_GREEN), _c(ACCENT_BLUE)
        gc2, cc = _c(ACCENT_GOLD), _c(ACCENT_CYAN)
        atk_text = (
            f"[color=#{rc}]ATK {fmt_num(f.attack)}[/color]   "
            f"[color=#{bc}]DEF {fmt_num(f.defense)}[/color]   "
            f"[color=#{gc}]HP {fmt_num(f.hp)}/{fmt_num(f.max_hp)}[/color]"
        )
        stats_lbl = AutoShrinkLabel(
            text=atk_text, font_size="11sp", markup=True, color=TEXT_SECONDARY,
            size_hint_y=None, height=dp(30), halign="center",
        )
        bind_text_wrap(stats_lbl)
        grid.add_widget(stats_lbl)

        crit_text = (
            f"[color=#{gc2}]Crit {f.crit_chance:.0%}[/color]   "
            f"[color=#{cc}]Dodge {f.dodge_chance:.0%}[/color]"
        )
        crit_lbl = AutoShrinkLabel(
            text=crit_text, font_size="11sp", markup=True, color=TEXT_SECONDARY,
            size_hint_y=None, height=dp(30), halign="center",
        )
        bind_text_wrap(crit_lbl)
        grid.add_widget(crit_lbl)

        stat_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        has_pts = f.unused_points > 0 and f.available
        for stat_name, stat_val, color, stat_key in [
            ("STR", f.total_strength, ACCENT_RED, "strength"),
            ("AGI", f.total_agility, ACCENT_GREEN, "agility"),
            ("VIT", f.total_vitality, ACCENT_BLUE, "vitality"),
        ]:
            cell = BoxLayout(spacing=dp(2))
            lbl = AutoShrinkLabel(text=f"{stat_name} {stat_val}", font_size="11sp",
                        color=color, halign="center", bold=True)
            bind_text_wrap(lbl)
            cell.add_widget(lbl)
            if has_pts:
                btn = MinimalButton(text="+", btn_color=color, text_color=BG_DARK,
                                    font_size=11, size_hint_x=0.4)
                def _add(inst, sk=stat_key, idx=index):
                    engine.distribute_stat(idx, sk)
                    engine.save()
                    self.refresh_roster()
                    self.show_fighter_detail(idx)
                btn.bind(on_press=_add)
                cell.add_widget(btn)
            stat_row.add_widget(cell)
        grid.add_widget(stat_row)

        if has_pts:
            grid.add_widget(AutoShrinkLabel(
                text=t("pts_label", n=f.unused_points), font_size="11sp",
                color=ACCENT_GOLD, size_hint_y=None, height=dp(30), halign="center",
            ))

    def _build_fighter_equipment(self, grid, f, index, engine):
        """Add equipment slot rows to detail grid."""
        seen_relic_ids = set()
        inv_relics = []
        for inv_item in engine.inventory:
            if inv_item.get("slot") == "relic" and inv_item.get("id") not in seen_relic_ids:
                inv_relics.append(inv_item)
                seen_relic_ids.add(inv_item.get("id"))
        for slot, icon_src, items_list in [
            ("weapon", "icons/ic_weapon.png", FORGE_WEAPONS),
            ("armor", "icons/ic_armor.png", FORGE_ARMOR),
            ("accessory", "icons/ic_accessory.png", FORGE_ACCESSORIES),
            ("relic", "icons/ic_accessory.png", inv_relics),
        ]:
            eq_row = BaseCard(
                orientation="horizontal", size_hint_y=None, height=dp(48),
                spacing=dp(6), padding=[dp(4), dp(2)],
                card_color=[0, 0, 0, 0], border_color=[0, 0, 0, 0],
            )
            eq_row.add_widget(KvImage(source=icon_src, fit_mode="contain",
                                      size_hint=(None, 1), width=dp(28)))
            item = f.equipment.get(slot)
            if item:
                rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
                eq_row.border_color = rcolor
                display = item_display_name(item)
                ulvl = item.get("upgrade_level", 0)
                if ulvl:
                    display += f" +{ulvl}"
                ench = item.get("enchant_id", "")
                if ench:
                    display += f" [{ench}]"
                eq_row.add_widget(eq_row._make_label(display, sp(11), True, rcolor, "left", 1))
            else:
                eq_row.add_widget(eq_row._make_label(t("empty_slot"), sp(11), False, TEXT_MUTED, "left", 1))
            if f.available:
                if item:
                    def _open_eq(inst, fi=index, s=slot):
                        Clock.schedule_once(lambda dt: App.get_running_app().open_equipped_detail(fi, s), 0.05)
                    eq_row.bind(on_press=_open_eq)
                else:
                    def _open_empty(inst, s=slot, fi=index):
                        def _nav(dt):
                            app = App.get_running_app()
                            has_free = any(
                                it.get("slot") == s for it in app.engine.inventory
                            )
                            if has_free:
                                app.open_inventory_tab(s, equip_filter="free")
                            else:
                                app.open_forge_tab(s)
                        Clock.schedule_once(_nav, 0.05)
                    eq_row.bind(on_press=_open_empty)
            grid.add_widget(eq_row)

    def _build_fighter_actions(self, grid, f, index, engine):
        """Add kills label, injuries button, and action buttons to detail grid."""
        grid.add_widget(AutoShrinkLabel(
            text=t("kills_label", n=f.kills), font_size="11sp", color=TEXT_MUTED,
            size_hint_y=None, height=dp(32), halign="center",
        ))

        # Injuries button (only if fighter has injuries)
        if f.injury_count > 0:
            inj_btn = MinimalButton(
                text=f"{t('injuries_tab')} ({f.injury_count})  —  {t('death_risk')}: {f.death_chance:.0%}",
                font_size=11, btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(48),
            )
            inj_btn.bind(on_press=lambda inst, idx=index: self._show_injuries_view(idx))
            grid.add_widget(inj_btn)

        # Skills button
        skills_btn = MinimalButton(
            text=t("skills_btn"), font_size=11,
            btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(48),
        )
        skills_btn.bind(on_press=lambda inst, idx=index: self._show_skills_view(idx))
        grid.add_widget(skills_btn)

        # Perk tree button
        if f.available:
            perk_label = f"{t('perks_btn')} ({f.perk_points})" if f.perk_points > 0 else t("perks_btn")
            perk_btn = MinimalButton(
                text=perk_label, font_size=11,
                btn_color=ACCENT_CYAN, text_color=BG_DARK,
                size_hint_y=None, height=dp(48),
            )
            perk_btn.bind(on_press=lambda inst, idx=index: self._show_perk_tree(idx))
            grid.add_widget(perk_btn)

        if f.available:
            cost = f.upgrade_cost
            can_train = engine.gold >= cost
            train_btn = MinimalButton(
                text=t("train_btn", lv=f.level + 1, cost=fmt_num(cost)),
                btn_color=ACCENT_GOLD if can_train else BTN_DISABLED,
                text_color=BG_DARK if can_train else TEXT_MUTED,
                font_size=11, icon_source="sprites/icons/ic_gold.png",
                size_hint_y=None, height=dp(48),
            )
            def _train(inst, idx=index):
                result = engine.upgrade_gladiator(idx)
                if not result.ok and result.message:
                    App.get_running_app().show_toast(result.message)
                self.refresh_roster()
                self.show_fighter_detail(idx)
            train_btn.bind(on_press=_train)
            grid.add_widget(train_btn)

        # Dismiss button
        dismiss_btn = MinimalButton(
            text=t("dismiss_btn"), font_size=11,
            btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(48),
        )
        dismiss_btn.bind(on_press=lambda inst, idx=index: self._confirm_dismiss(idx))
        grid.add_widget(dismiss_btn)

    def _confirm_dismiss(self, fighter_idx):
        """Show confirmation popup before dismissing a fighter."""
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]

        content = BoxLayout(orientation="vertical", spacing=dp(8),
                            padding=[dp(12), dp(8)])
        content.add_widget(AutoShrinkLabel(
            text=t("dismiss_confirm_msg", name=f.name),
            font_size="11sp", color=TEXT_SECONDARY,
            halign="center", valign="middle",
            size_hint_y=0.6,
        ))
        btn_row = BoxLayout(size_hint_y=0.4, spacing=dp(8))
        cancel_btn = MinimalButton(
            text=t("back_btn"), btn_color=BTN_PRIMARY,
            font_size=11,
        )
        confirm_btn = MinimalButton(
            text=t("dismiss_confirm_btn"), btn_color=ACCENT_RED,
            text_color=TEXT_PRIMARY, font_size=11,
        )
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(confirm_btn)
        content.add_widget(btn_row)

        popup = make_styled_popup(t("dismiss_confirm_title"), content,
                                  size_hint=(0.85, 0.35))
        cancel_btn.bind(on_press=lambda inst: popup.dismiss())
        def _do_dismiss(inst, idx=fighter_idx):
            popup.dismiss()
            result = engine.dismiss_fighter(idx)
            if result.ok:
                App.get_running_app().show_toast(result.message)
                self.close_detail()
            else:
                App.get_running_app().show_toast(result.message)
        confirm_btn.bind(on_press=_do_dismiss)
        popup.open()

    def show_fighter_detail(self, index):
        engine = App.get_running_app().engine
        if index < 0 or index >= len(engine.fighters):
            return
        self.detail_index = index
        self.roster_view = "detail"
        f = engine.fighters[index]

        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        self._build_fighter_header(grid, f, index, engine)
        self._build_fighter_equipment(grid, f, index, engine)
        self._build_fighter_actions(grid, f, index, engine)

    def close_detail(self):
        self.detail_index = -1
        self.roster_view = "list"
        self.refresh_roster()

    def on_back_pressed(self):
        if getattr(self, '_injury_detail', None):
            self._back_from_injury()
            return True
        if getattr(self, '_injuries_list_idx', -1) >= 0:
            idx = self._injuries_list_idx
            self._injuries_list_idx = -1
            self.show_fighter_detail(idx)
            return True
        if self.perk_view:
            self.perk_view = False
            self.show_fighter_detail(self.detail_index)
            return True
        if self.roster_view == "skills":
            self.show_fighter_detail(self.detail_index)
            return True
        if getattr(self, '_class_detail_id', None):
            self._back_to_hire()
            return True
        if self.roster_view != "list":
            if getattr(self, '_entered_with_detail', False):
                # Entered roster directly into detail from another screen — go back there
                self.close_detail()
                return False  # let go_back() pop history → previous screen
            self.close_detail()
            return True
        return False

    def _build_passive_card(self, passive):
        """Build card for a class's passive ability."""
        from kivy.uix.label import Label
        p_card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(70),
                          padding=[dp(10), dp(6)], spacing=dp(2))
        p_card.border_color = ACCENT_GOLD
        passive_lbl = AutoShrinkLabel(
            text=f"{t('perk_passive_label')}: {passive['name']}", font_size="10sp",
            bold=True, color=ACCENT_GOLD, halign="left",
            size_hint_y=None, height=dp(30),
        )
        bind_text_wrap(passive_lbl)
        p_card.add_widget(passive_lbl)
        desc_lbl = Label(
            text=passive.get("description", ""), font_size="11sp", font_name='PixelFont',
            color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
        )
        desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
        desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
        desc_lbl.bind(height=lambda inst, h, c=p_card: setattr(c, "height", max(dp(70), h + dp(40))))
        p_card.add_widget(desc_lbl)
        return p_card

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

    def _build_perk_card(self, perk, fighter, fighter_idx, is_cross, engine):
        """Build a single perk card with unlock button if applicable."""
        from kivy.uix.label import Label
        pid = perk["id"]
        is_unlocked = pid in fighter.unlocked_perks
        cost = perk["cost"]
        if is_cross:
            cost = int(cost * perk.get("cross_class_cost_mult", 2.0))
        can_unlock = not is_unlocked and fighter.perk_points >= cost

        if is_unlocked:
            border_color = ACCENT_GOLD
        elif can_unlock:
            border_color = ACCENT_CYAN
        else:
            border_color = BTN_DISABLED

        card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(90),
                        padding=[dp(10), dp(6)], spacing=dp(2))
        card.border_color = border_color

        name_text = perk["name"]
        if is_unlocked:
            name_text += f"  [{t('perk_unlocked')}]"
        perk_nm_lbl = AutoShrinkLabel(
            text=name_text, font_size="10sp", bold=True,
            color=ACCENT_GOLD if is_unlocked else (TEXT_PRIMARY if can_unlock else TEXT_MUTED),
            halign="left", size_hint_y=None, height=dp(18),
        )
        bind_text_wrap(perk_nm_lbl)
        card.add_widget(perk_nm_lbl)

        desc_lbl = Label(
            text=perk.get("description", ""), font_size="11sp", font_name='PixelFont',
            color=TEXT_MUTED, halign="left", valign="top", size_hint_y=None,
        )
        desc_lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - dp(20), None)))
        desc_lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1]))
        def _upd_card(inst, h, c=card):
            c.height = max(dp(90), h + dp(60))
        desc_lbl.bind(height=_upd_card)
        card.add_widget(desc_lbl)

        if not is_unlocked:
            btn = MinimalButton(
                text=t("perk_unlock_btn", cost=cost), font_size=11,
                btn_color=ACCENT_CYAN if can_unlock else BTN_DISABLED,
                text_color=BG_DARK if can_unlock else TEXT_MUTED,
                size_hint_y=None, height=dp(30),
            )
            def _unlock(inst, fi=fighter_idx, pi=pid):
                result = engine.unlock_perk(fi, pi)
                if result.ok:
                    self._show_perk_tree(fi)
                else:
                    App.get_running_app().show_toast(result.message)
            btn.bind(on_press=_unlock)
            card.add_widget(btn)

        return card

    def _show_perk_tree(self, fighter_idx):
        """Show perk tree view with collapsible tiers."""
        engine = App.get_running_app().engine
        if fighter_idx >= len(engine.fighters):
            return
        f = engine.fighters[fighter_idx]
        self.perk_view = True
        self.detail_index = fighter_idx
        self.roster_view = "detail"
        grid = self.ids.get("detail_grid")
        if not grid:
            return
        _safe_clear(grid)

        if not hasattr(self, '_perk_expanded'):
            self._perk_expanded = {}
        expanded = self._perk_expanded.setdefault(f.name, {})

        grid.add_widget(AutoShrinkLabel(
            text=f"{f.class_name} — {t('perks_btn')}", font_size="11sp", bold=True,
            color=ACCENT_CYAN, halign="center", size_hint_y=None, height=dp(30),
        ))
        grid.add_widget(AutoShrinkLabel(
            text=t("perk_points_label", n=f.perk_points), font_size="10sp",
            color=ACCENT_GOLD if f.perk_points > 0 else TEXT_MUTED,
            halign="center", size_hint_y=None, height=dp(30),
        ))

        cls_data = _m.FIGHTER_CLASSES.get(f.fighter_class, {})
        passive = cls_data.get("passive_ability")
        if passive:
            grid.add_widget(self._build_passive_card(passive))

        # Collect perks
        all_perks = []
        for cid, cdata in _m.FIGHTER_CLASSES.items():
            for perk in cdata.get("perk_tree", []):
                all_perks.append((cid, perk))
        own_perks = [(cid, p) for cid, p in all_perks if cid == f.fighter_class]
        cross_perks = [(cid, p) for cid, p in all_perks if cid != f.fighter_class]

        for section_label, perks, section_key in [
            ("", own_perks, "own"),
            (t("perk_cross_class", mult="2"), cross_perks, "cross"),
        ]:
            if not perks:
                continue
            if section_label:
                grid.add_widget(AutoShrinkLabel(
                    text=section_label, font_size="10sp", bold=True,
                    color=TEXT_MUTED, halign="center",
                    size_hint_y=None, height=dp(26),
                ))

            tiers = {}
            for cid, perk in perks:
                tiers.setdefault(perk.get("tier", 1), []).append((cid, perk))

            for tier_num in sorted(tiers.keys()):
                tier_key = f"{section_key}_t{tier_num}"
                is_open = expanded.get(tier_key, False)
                arrow = "v" if is_open else ">"
                tier_perks = tiers[tier_num]
                unlocked_count = sum(1 for _, p in tier_perks if p["id"] in f.unlocked_perks)

                tier_btn = MinimalButton(
                    text=f"{arrow}  {t('perk_tier_label', n=tier_num)}  ({unlocked_count}/{len(tier_perks)})",
                    font_size=11, btn_color=ACCENT_CYAN, text_color=BG_DARK,
                    size_hint_y=None, height=dp(30),
                )
                def _toggle(inst, tk=tier_key, fi=fighter_idx):
                    expanded[tk] = not expanded.get(tk, False)
                    self._show_perk_tree(fi)
                tier_btn.bind(on_press=_toggle)
                grid.add_widget(tier_btn)

                if not is_open:
                    continue
                for cid, perk in tier_perks:
                    is_cross = (cid != f.fighter_class)
                    grid.add_widget(self._build_perk_card(perk, f, fighter_idx, is_cross, engine))


    def _show_equipment_popup(self, fighter_idx, slot, items_list):
        """Popup showing all items for a slot — buy or equip from inventory."""
        engine = App.get_running_app().engine
        f = engine.fighters[fighter_idx]

        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False,
                            effect_cls=ScrollEffect,
                            scroll_distance=dp(20), scroll_timeout=150)
        content = BoxLayout(orientation="vertical", spacing=dp(6),
                            padding=[dp(8), dp(6)], size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        # Currently equipped
        current = f.equipment.get(slot)
        if current:
            def _tap_equipped(inst, fi=fighter_idx, s=slot):
                equip_popup.dismiss()
                App.get_running_app().open_equipped_detail(fi, s)
            content.add_widget(build_item_info_card(current, fighter=f, equipped_on=f.name,
                                                    on_tap=_tap_equipped))
            unequip_btn = MinimalButton(
                text=t("unequip_btn"), font_size=11,
                btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(36),
            )
            def _unequip(inst, s=slot, idx=fighter_idx):
                result = engine.unequip_from_fighter(idx, s)
                if not result.ok:
                    App.get_running_app().show_toast(result.message or t("not_in_battle"))
                    return
                equip_popup.dismiss()
                self.refresh_roster()
                self.show_fighter_detail(idx)
            unequip_btn.bind(on_press=_unequip)
            content.add_widget(unequip_btn)

        for template_item in items_list:
            # Use actual inventory item (with upgrade_level) if available
            inv_idx = engine.find_inventory_index(template_item["id"])
            item = engine.inventory[inv_idx] if inv_idx >= 0 else template_item
            inv_count = engine.get_inventory_count(item["id"])

            # Item card — tap opens detail in ForgeScreen (or popup for shop-only items)
            def _tap_card(inst, it=item):
                ii = engine.find_inventory_index(it["id"])
                if ii >= 0:
                    equip_popup.dismiss()
                    App.get_running_app().open_item_detail(ii)
                else:
                    equip_popup.dismiss()
                    App.get_running_app().open_shop_preview(it)
            info_card = build_item_info_card(item, fighter=f, on_tap=_tap_card)
            content.add_widget(info_card)

            # Action button row under the card
            btn_row = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(6))
            if inv_count > 0:
                btn_row.add_widget(AutoShrinkLabel(
                    text=f"x{inv_count}", font_size="10sp", color=ACCENT_GOLD,
                    size_hint_x=0.15, halign="center",
                ))
                equip_btn = MinimalButton(
                    text=t("equip_btn"), font_size=11,
                    btn_color=ACCENT_GREEN, text_color=BG_DARK,
                )
                def _equip(inst, iid=item["id"], idx=fighter_idx):
                    if engine.battle_active:
                        App.get_running_app().show_toast(t("not_in_battle"))
                        return
                    inv_idx = engine.find_inventory_index(iid)
                    if inv_idx >= 0:
                        engine.equip_from_inventory(idx, inv_idx)
                        equip_popup.dismiss()
                        self.refresh_roster()
                        self.show_fighter_detail(idx)
                equip_btn.bind(on_press=_equip)
                btn_row.add_widget(equip_btn)
            else:
                shop_cost = template_item["cost"]
                affordable = engine.gold >= shop_cost
                rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
                buy_btn = MinimalButton(
                    text=t("buy_btn_price", price=fmt_num(shop_cost)), font_size=11,
                    btn_color=rcolor if affordable else BTN_DISABLED,
                    text_color=BG_DARK if affordable else TEXT_MUTED,
                    icon_source="sprites/icons/ic_gold.png",
                )
                def _buy(inst, iid=template_item["id"], idx=fighter_idx, s=slot, il=items_list):
                    result = engine.buy_forge_item(iid)
                    if result.message:
                        App.get_running_app().show_toast(result.message)
                    equip_popup.dismiss()
                    self.refresh_roster()
                    self._show_equipment_popup(idx, s, il)
                if affordable:
                    buy_btn.bind(on_press=_buy)
                btn_row.add_widget(buy_btn)
            content.add_widget(btn_row)

        scroll.add_widget(content)

        equip_popup = Popup(
            title=f"{slot.upper()} — {f.name}",
            title_color=ACCENT_GOLD, title_size="11sp",
            content=scroll, size_hint=(0.94, 0.7),
            background_color=(0.08, 0.08, 0.11, 0.97),
            separator_color=ACCENT_GOLD,
        )
        equip_popup.open()
