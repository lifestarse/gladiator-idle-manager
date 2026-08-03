# Build: 6
"""ui_helpers._shop — consumable shop card builder.

refresh_shop_grid() was removed (dead: no kv template defines a `shop_grid`
id and no screen exposes `items_data`) — see memory/architecture for the
audit. build_shop_card() is kept: it's part of the public ui_helpers API
(tests/test_imports.py::test_ui_helpers_public_api) pending a live caller.
"""
from ._imports import *  # noqa: F401,F403
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
