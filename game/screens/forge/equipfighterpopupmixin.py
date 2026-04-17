# Build: 1
"""_EquipFighterPopupMixin — split off to keep file under 10KB."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


class _EquipFighterPopupMixin:
    def _show_equip_fighter_popup(self, inv_idx, item):
        """Pick a fighter to equip `item` on.

        Two fast paths bypass the popup entirely:
          1. `app.pending_equip_target_idx` is set — user navigated here
             from an empty slot on a specific fighter's Squad page. We
             equip on that fighter AND navigate back to their Squad detail
             so Back behaves naturally ("fill slot → see fighter with the
             new item"). If they wanted to keep browsing inventory, they
             would have opened the forge directly rather than tapping an
             empty slot.
          2. Roster has only one available fighter — the picker has one
             option anyway. Stay in the forge inventory in this case,
             user explicitly came through the forge.

        Otherwise build a TouchRecycleView inside the popup so 1000-fighter
        rosters open instantly (was 1-2 s for 1000 MinimalButtons).
        """
        from kivy.uix.recyclelayout import RecycleLayout  # noqa: F401  (viewclass reg)
        from kivy.uix.recycleboxlayout import RecycleBoxLayout
        from game.widgets import TouchRecycleView
        from game.ui_helpers import _equip_choice_callbacks, FighterEquipChoiceView  # noqa: F401
        from kivy.metrics import dp as _dp

        app = App.get_running_app()
        engine = app.engine
        alive = [(i, f) for i, f in enumerate(engine.fighters) if f.available]
        if not alive:
            app.show_toast(t("no_fighters"))
            return

        # Fast path 1: user came from an empty-slot tap on Squad.
        pending = getattr(app, 'pending_equip_target_idx', -1)
        app.pending_equip_target_idx = -1  # one-shot, always clear
        if 0 <= pending < len(engine.fighters):
            target = engine.fighters[pending]
            if target.available:
                self._equip_and_return_to_roster(pending, inv_idx)
                return

        # Fast path 2: single fighter — no picker needed.
        if len(alive) == 1:
            self._equip_and_refresh(alive[0][0], inv_idx)
            return

        # Build the picker via RecycleView — only visible rows materialize.
        popup_box = BoxLayout(orientation="vertical", spacing=dp(4),
                              padding=dp(8))
        rv = TouchRecycleView(
            viewclass='FighterEquipChoiceView',
            bar_width=2, bar_color=TEXT_MUTED,
            do_scroll_x=False, scroll_type=['bars', 'content'],
            scroll_distance=_dp(8), scroll_timeout=50,
        )
        rbl = RecycleBoxLayout(
            default_size=(None, _dp(50)),
            default_size_hint=(1, None),
            size_hint_y=None, orientation='vertical',
            spacing=_dp(4), padding=[_dp(4), _dp(4)],
        )
        rbl.bind(minimum_height=rbl.setter('height'))
        rv.add_widget(rbl)
        slot = item.get("slot", "weapon")
        rv.data = [
            {
                'fi': fi,
                'text': f"{f.name}  [{(f.equipment.get(slot) or {}).get('name', '—')}]",
            }
            for fi, f in alive
        ]
        popup_box.add_widget(rv)

        # Clamp popup to screen — for big rosters it doesn't blow past the
        # top/bottom of the window.
        from kivy.core.window import Window
        rows_h = dp(50 + 4) * min(len(alive), 10)
        popup_h = min(Window.height * 0.85, dp(80) + rows_h)
        popup = Popup(
            title=f"{t('equip_btn')}: {item_display_name(item)}",
            title_color=popup_color(ACCENT_GOLD),
            title_size=sp(11),
            content=popup_box,
            size_hint=(0.85, None),
            height=popup_h,
            background_color=popup_color(BG_CARD),
            separator_color=popup_color(ACCENT_GOLD),
            auto_dismiss=True,
        )

        # Wire the picker callback once per popup-open.
        def _pick(fidx):
            if engine.battle_active:
                app.show_toast(t("not_in_battle"))
                return
            popup.dismiss()
            self._equip_and_refresh(fidx, inv_idx)
        _equip_choice_callbacks['pick'] = _pick
        popup.open()

