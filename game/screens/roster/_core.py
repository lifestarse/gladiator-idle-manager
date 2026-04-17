# Build: 1
"""RosterScreen core — lifecycle + small methods."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _roster_callbacks, _perk_callbacks  # underscore names skipped by `import *`
from .hiremixin import _HireMixin
from .injuriesmixin import _InjuriesMixin
from .fighterdetailmixin import _FighterDetailMixin
from .perksmixin import _PerksMixin
from .equipmentmixin import _EquipmentMixin


class RosterScreen(BaseScreen, _HireMixin, _InjuriesMixin, _FighterDetailMixin, _PerksMixin, _EquipmentMixin):
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
        # Perk tree RV dispatch (tier toggle + unlock) — module-level dict
        # so the viewclass pool doesn't need a back-ref to this screen.
        _perk_callbacks['toggle_tier'] = self._on_perk_tier_toggle
        _perk_callbacks['unlock'] = self._on_perk_unlock
        state = self._pending_state
        self._pending_state = None
        self._entered_with_detail = False
        # `_return_to_list` flag means this entry is a RETURN from forge
        # back to a detail view the user was already on (auto-equip flow).
        # Back should unwind to the list instead of skipping to whatever
        # is below Roster in the nav history.
        return_to_list = state.get('_return_to_list', False) if state else False
        if state:
            idx = state.get('detail_index', -1)
            view = state.get('roster_view', 'list')
            if view == "skills" and idx >= 0:
                self._entered_with_detail = not return_to_list
                self._show_skills_view(idx)
                return
            if idx >= 0:
                self._entered_with_detail = not return_to_list
                self.show_fighter_detail(idx)
                if state.get('perk_view'):
                    self._show_perk_tree(idx)
                return
            if view == "hire":
                self._entered_with_detail = not return_to_list
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

    _CLASS_COLORS = {
        "mercenary": ACCENT_GREEN, "assassin": ACCENT_RED, "tank": ACCENT_BLUE,
        "berserker": ACCENT_RED, "retiarius": ACCENT_CYAN, "medicus": ACCENT_PURPLE,
    }

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
