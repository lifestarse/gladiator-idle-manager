# Build: 5
"""ui_helpers._shop — consumable shop grid rendering."""
from ._imports import *  # noqa: F401,F403
from ._layouts import _batch_fill_grid
from ._widgets import _auto_text_size


# ============================================================
#  MARKET (Shop) — now inside MoreScreen
# ============================================================

def build_shop_card(item, shop_screen):
    from game.widgets import BaseCard

    card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(70),
                    padding=[dp(12), dp(8)], spacing=dp(10))

    info = BoxLayout(orientation="vertical", size_hint_x=0.65, spacing=dp(4))
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=item["name"], font_size="10sp", bold=True,
        color=TEXT_PRIMARY, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=item["desc"], font_size="11sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=f"{fmt_num(item['cost'])}", font_size=11, size_hint_x=0.35,
        btn_color=ACCENT_BLUE if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gold.png",
    )
    buy_btn.bind(on_release=lambda inst, iid=item["id"]: shop_screen.buy(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_shop_grid(shop_screen):
    grid = shop_screen.ids.get("shop_grid")
    if not grid:
        return
    cards = [build_shop_card(item, shop_screen) for item in shop_screen.items_data]
    _batch_fill_grid(grid, cards)
