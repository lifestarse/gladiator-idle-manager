# Build: 1
"""ForgeScreen _EquipSwapMixin — extracted from monolithic screen."""
from ._screen_imports import *  # noqa: F401,F403


class _EquipSwapMixin:
    def _show_equipped_detail(self, fighter_idx, item):
        """Detail view for an item currently equipped on a fighter."""
        self._enter_detail_mode()
        self.eq_detail_fighter = fighter_idx
        self.eq_detail_slot = item.get("slot", "")
        self._set_view("equipped_detail")
        sv = self.ids.get("forge_scroll")
        if sv:
            sv.scroll_y = 1
        self.eq_detail_slot = item.get("slot", "")
        grid = self.ids.get("forge_grid")
        if not grid:
            return
        _safe_clear(grid)
        engine = App.get_running_app().engine
        f = engine.fighters[fighter_idx]
        slot = item.get("slot", "?")
        max_upg = get_max_upgrade(item)
        # Info card
        grid.add_widget(build_item_info_card(item, fighter=f, equipped_on=f.name))
        desc_card = self._build_description_card(item)
        if desc_card:
            grid.add_widget(desc_card)

        # Unequip button
        slot = item.get("slot", "weapon")
        unequip_btn = MinimalButton(
            text=t("unequip_btn"), font_size=11,
            btn_color=ACCENT_RED, text_color=TEXT_PRIMARY,
            size_hint_y=None, height=dp(44),
        )
        def _unequip(*a, s=slot, fi=fighter_idx):
            result = engine.unequip_from_fighter(fi, s)
            if not result.ok:
                App.get_running_app().show_toast(result.message or t("not_in_battle"))
                return
            # Stay on forge — show item in inventory now
            self.eq_detail_fighter = -1
            self.eq_detail_slot = ""
            # Find item in inventory to show its detail
            inv = engine.inventory
            found_idx = -1
            for idx, it in enumerate(inv):
                if it.get("name") == item.get("name") and it.get("slot") == s:
                    found_idx = idx
                    break
            if found_idx >= 0:
                self.inv_detail_idx = found_idx
                self._set_view("inventory_detail")
            else:
                self._set_view("inventory_list")
            self.refresh_forge()
        unequip_btn.bind(on_press=_unequip)
        grid.add_widget(unequip_btn)

        slot_def = SLOTS.get(slot)
        # Upgradable items: IMPROVE button (any equipment slot)
        if slot_def is not None:
            improve_btn = MinimalButton(
                text=t("improve_btn"), font_size=11,
                btn_color=ACCENT_BLUE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            improve_btn.bind(on_press=lambda *a: self._show_item_upgrade("equip", fighter_idx, item, f))
            grid.add_widget(improve_btn)

        # Enchant button — slot registry decides eligibility
        if slot_def is not None and slot_def.can_enchant:
            enchant_btn = MinimalButton(
                text=t("tab_enchant"), font_size=11,
                btn_color=ACCENT_PURPLE, text_color=TEXT_PRIMARY,
                size_hint_y=None, height=dp(46),
            )
            enchant_btn.bind(on_press=lambda *a: self._show_enchant_view("equip", fighter_idx, item, f))
            grid.add_widget(enchant_btn)

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

    def _equip_and_refresh(self, fighter_idx, inv_idx):
        """Equip the inventory item onto a specific fighter + refresh view."""
        engine = App.get_running_app().engine
        if engine.battle_active:
            App.get_running_app().show_toast(t("not_in_battle"))
            return
        engine.equip_from_inventory(fighter_idx, inv_idx)
        self.inv_detail_idx = -1
        self._set_view("inventory_list")
        self.refresh_forge()

    def _equip_and_return_to_roster(self, fighter_idx, inv_idx):
        """Equip and navigate back to the fighter's Squad detail.

        Used for the empty-slot → inventory → equip flow. The user started
        on Squad; going forward to the forge pushed ("roster", ...) onto
        the nav history, then coming back to Roster would normally push
        ("forge", ...) on top — so Back would take the user INTO the forge
        instead of to the roster list.

        Fix: treat this as a Back action rather than forward navigation.
        Pop the stale ("roster", ...) frame that's already on top of the
        history (that's where we came from), and set _going_back so the
        upcoming screen change doesn't append a new frame. Net result:
        one Back from the Squad detail unwinds to whatever was before the
        user entered roster — exactly what a user who'd pressed Back from
        Forge → Roster detail would expect.
        """
        app = App.get_running_app()
        engine = app.engine
        if engine.battle_active:
            app.show_toast(t("not_in_battle"))
            return
        engine.equip_from_inventory(fighter_idx, inv_idx)
        # Reset forge UI state so when user enters the forge later they
        # land on the shop, not on a stale inventory-detail view.
        self.inv_detail_idx = -1
        self._set_view("shop")

        # Nav-history cleanup: drop the ("roster", ...) frame we pushed
        # when entering the forge, and mark the incoming screen change as
        # a back-step so it doesn't push ("forge", ...).
        history = getattr(app, '_nav_history', None)
        if history and history[-1][0] == "roster":
            history.pop()
        app._going_back = True

        roster = app.sm.get_screen("roster")
        # `_return_to_list` tells Roster.on_enter that Back should unwind
        # to the roster list (not to whatever is below Roster in nav
        # history). Without this, Back from the fighter detail skips over
        # the list and lands on Arena/Pit.
        roster._pending_state = {
            'detail_index': fighter_idx,
            '_return_to_list': True,
        }
        app.sm.current = "roster"
