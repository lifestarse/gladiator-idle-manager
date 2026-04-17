# Build: 1
"""RosterScreen _HireMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _HireMixin:
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

    def _back_to_hire(self):
        self._class_detail_id = None
        self.roster_view = "hire"
        self._show_hire_view()
