# Build: 39
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, ListProperty, BooleanProperty
from kivy.metrics import dp, sp
from game.base_screen import BaseScreen
from game.widgets import AutoShrinkLabel, MinimalButton, BaseCard, FloatingText
import game.models as _m
from game.models import (
    fmt_num, RARITY_COLORS,
    get_upgrade_tier, item_display_name,
    get_max_upgrade, RARITY_MAX_UPGRADE,
)
from game.slots import SLOTS
from game.theme import *
from game.theme import popup_color
from game.constants import (
    UPGRADE_BONUS_PER_LEVEL, RELIC_STAT_SPLIT, ACCESSORY_HP_MULT,
)
from game.localization import t
from game.ui_helpers import (
    _batch_fill_grid,
    refresh_forge_grid,
    build_item_info_card, build_tab_row,
    bind_text_wrap,
)
from game.screens.shared import _safe_clear, _safe_rebind

BC = BaseCard  # short alias used in _build_upgrade_comparison_card


# ---- View state machine ----------------------------------------------------
# The forge used to have six independent BooleanProperty flags that could
# contradict each other (e.g. both weapon_upgrade_active AND enchant_active
# True). `view_state` is now the single source of truth; the six flags below
# are derived output kept in sync by `on_view_state` for KV-binding compat.
#
# Allowed transitions (enforced by _set_view via the transition map):
#   shop            <-> shop_preview, inventory_list
#   inventory_list  <-> shop, inventory_detail, equipped_detail
#   inventory_detail -> inventory_list, upgrade, enchant
#   equipped_detail  -> inventory_list, upgrade, enchant
#   upgrade         -> inventory_detail, equipped_detail
#   enchant         -> inventory_detail, equipped_detail
VIEW_STATES = (
    "shop", "shop_preview",
    "inventory_list", "inventory_detail", "equipped_detail",
    "upgrade", "enchant",
)

# Flag tuple order: (show_inventory, _forge_rv_active, _inventory_rv_active,
#                    _show_inv_tabs, weapon_upgrade_active, enchant_active)
_VIEW_FLAGS = {
    "shop":             (False, True,  False, True,  False, False),
    "shop_preview":     (False, False, False, False, False, False),
    "inventory_list":   (True,  False, True,  True,  False, False),
    "inventory_detail": (True,  False, False, False, False, False),
    "equipped_detail":  (True,  False, False, False, False, False),
    "upgrade":          (True,  False, False, False, True,  False),
    "enchant":          (True,  False, False, False, False, True),
}


# Star-imports skip underscore names. Build __all__ dynamically from
# everything imported above so mixin files see BaseScreen, App, etc.
# `_m` is explicitly added (underscore names are skipped by the filter).
import game.theme as _theme_mod  # noqa: F401
import game.models as _m  # module alias for dynamic wire-data refs
__all__ = [n for n in list(globals().keys())
           if not n.startswith('__') and n != 'annotations']
