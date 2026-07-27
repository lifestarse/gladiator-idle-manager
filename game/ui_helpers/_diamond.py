# Build: 6
"""ui_helpers._diamond — diamond shop grid rendering."""
from ._imports import *  # noqa: F401,F403
from ._layouts import _batch_fill_grid, _needs_rebuild
from ._widgets import _auto_text_size


# ============================================================
#  DIAMOND SHOP (LoreScreen)
# ============================================================

def _show_diamond_item_popup(item, lore_screen):
    """Popup with item description and buy button."""
    content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(14))
    iid = item.get("id", "")
    desc_text = t("ds_" + iid + "_desc") if iid else item.get("desc", "")
    name_text = t("ds_" + iid + "_name") if iid else item.get("name", "")
    desc_lbl = AutoShrinkLabel(
        text=desc_text, font_size="10sp",
        color=TEXT_SECONDARY, halign="center", valign="middle",
        size_hint_y=0.5,
    )
    desc_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    content.add_widget(desc_lbl)
    affordable = item.get("affordable", False)
    buy_btn = MinimalButton(
        text=f"{item['cost']}", font_size=11,
        btn_color=ACCENT_CYAN if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gem.png",
        size_hint_y=None, height=dp(48),
    )
    popup = Popup(
        title=name_text,
        title_color=list(ACCENT_CYAN)[:3] + [1],
        title_size=sp(11),
        content=content,
        size_hint=(0.9, 0.45),
        background_color=list(BG_CARD)[:3] + [1],
        separator_color=list(ACCENT_CYAN)[:3] + [1],
        auto_dismiss=True,
    )
    def _buy(inst, iid=item["id"]):
        popup.dismiss()
        lore_screen.buy_diamond_item(iid)
    if affordable:
        buy_btn.bind(on_release=_buy)
    content.add_widget(buy_btn)
    popup.open()


def build_diamond_shop_card(item, lore_screen):
    from game.widgets import BaseCard

    card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(52),
                    padding=[dp(12), dp(6)], spacing=dp(8))
    card.border_color = ACCENT_CYAN
    iid = item.get("id", "")
    name_text = t("ds_" + iid + "_name") if iid else item.get("name", "")
    card.add_widget(_auto_text_size(AutoShrinkLabel(
        text=name_text, font_size="11sp", bold=True,
        color=ACCENT_CYAN, halign="left", size_hint_x=0.55,
    )))
    card.bind(on_press=lambda inst, it=item: _show_diamond_item_popup(it, lore_screen))

    affordable = item.get("affordable", False)
    buy_btn = MinimalButton(
        text=str(item["cost"]), font_size=10, size_hint_x=0.45,
        btn_color=ACCENT_CYAN if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gem.png",
    )
    buy_btn.bind(on_release=lambda inst, iid=item["id"]: lore_screen.buy_diamond_item(iid))
    card.add_widget(buy_btn)
    return card


def refresh_diamond_shop_grid(lore_screen):
    grid = lore_screen.ids.get("lore_grid")
    if not grid:
        return
    items = lore_screen.diamond_shop_data
    shop_key = tuple((it["id"], it.get("affordable", False)) for it in items)
    if not _needs_rebuild(grid, '_dshop_key', shop_key, require_children=True):
        return
    cards = [build_diamond_shop_card(item, lore_screen) for item in items]
    _batch_fill_grid(grid, cards)
