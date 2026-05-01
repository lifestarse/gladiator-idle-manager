# Build: 1
"""_EquipmentBuildMixin — fighter detail equipment-slot rendering.

Split from fighterbuildmixin.py to keep both files under the 10KB src
limit (CLAUDE.md). Same render path the inventory list uses; empty
slots show a placeholder card that opens the forge equip flow.
"""
from ._screen_imports import *  # noqa: F401,F403


class _EquipmentBuildMixin:

    def _build_fighter_equipment(self, grid, f, index, engine):
        """Add equipment slot rows to detail grid.

        Uses the same card style as the main inventory list: `name`,
        `SLOT [RARITY]` subtitle (no "max +N" suffix — that's the detail
        view), and base STR/AGI/VIT stats. No `fighter=` arg and no
        `equipped_on` badge: we're already on this fighter's own page so
        owner info would be redundant.
        """
        from game.slots import SLOTS
        from game.localization import t as tr

        seen_relic_ids = set()
        inv_relics = []
        for inv_item in engine.inventory:
            if inv_item.get("slot") == "relic" and inv_item.get("id") not in seen_relic_ids:
                inv_relics.append(inv_item)
                seen_relic_ids.add(inv_item.get("id"))

        for slot, icon_src in [
            ("weapon", "icons/ic_weapon.png"),
            ("armor", "icons/ic_armor.png"),
            ("accessory", "icons/ic_accessory.png"),
            ("relic", "icons/ic_accessory.png"),
        ]:
            item = f.equipment.get(slot)
            if item:
                def _open_eq(inst, fi=index, s=slot):
                    if not f.available:
                        return
                    Clock.schedule_once(
                        lambda dt: App.get_running_app().open_equipped_detail(fi, s),
                        0.05)

                card = build_item_info_card(
                    item,
                    on_tap=_open_eq if f.available else None,
                )
                grid.add_widget(card)
            else:
                from game.widgets import BaseCard
                empty_card = BaseCard(
                    orientation="horizontal", size_hint_y=None, height=dp(75),
                    padding=[dp(12), dp(8)], spacing=dp(8),
                )
                empty_card.border_color = TEXT_MUTED
                empty_card.add_widget(KvImage(
                    source=icon_src, fit_mode="contain",
                    size_hint=(None, 1), width=dp(32),
                ))
                slot_def = SLOTS.get(slot)
                slot_label = tr(slot_def.label_keys['upper']) if slot_def else slot.upper()
                empty_card.add_widget(empty_card._make_label(
                    f"{slot_label}: {tr('empty_slot')}",
                    sp(11), False, TEXT_MUTED, "left", 1,
                ))
                if f.available:
                    def _open_empty(inst, s=slot, fi=index):
                        def _nav(dt):
                            app = App.get_running_app()
                            # Stash the source fighter so the forge's
                            # equip flow auto-targets them instead of
                            # opening a picker popup.
                            app.pending_equip_target_idx = fi
                            has_free = any(
                                it.get("slot") == s for it in app.engine.inventory
                            )
                            if has_free:
                                app.open_inventory_tab(s, equip_filter="free")
                            else:
                                app.open_forge_tab(s)
                        Clock.schedule_once(_nav, 0.05)
                    empty_card.bind(on_press=_open_empty)
                grid.add_widget(empty_card)
