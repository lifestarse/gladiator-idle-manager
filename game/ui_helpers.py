# Build: 44
"""Dynamic UI builders for all screens — minimalist CardWidget style."""

import time

from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from kivy.uix.popup import Popup
from game.widgets import CardWidget, MinimalButton, MinimalBar, AutoShrinkLabel, GladiatorAvatar
from game.theme import *
from game.models import RARITY_COLORS, fmt_num
from game.localization import t
from game.constants import LOW_HP_THRESHOLD

_HOLD_MS = 100  # minimum hold time in ms to open popup


def bind_text_wrap(label):
    """Make a Kivy Label wrap text to its widget size. Call after construction."""
    label.bind(size=lambda w, s: setattr(w, "text_size", s))

_CLASS_COLORS = {
    "mercenary": ACCENT_GREEN,
    "assassin": ACCENT_RED,
    "tank": ACCENT_BLUE,
    "berserker": ACCENT_RED,
    "retiarius": ACCENT_CYAN,
    "medicus": ACCENT_PURPLE,
}


from contextlib import contextmanager

def _invalidate_grid_cache(grid):
    """Wipe every _*_key cache stored on a grid widget."""
    for attr in list(vars(grid)):
        if attr.endswith('_key'):
            setattr(grid, attr, None)


@contextmanager
def grid_batch(grid):
    """Context manager: unbinds minimum_height during widget adds, rebinds after.
    Usage:
        with grid_batch(grid):
            grid.clear_widgets()
            grid.add_widget(...)
    """
    _invalidate_grid_cache(grid)
    grid.unbind(minimum_height=grid.setter('height'))
    try:
        yield grid
    finally:
        grid.height = grid.minimum_height
        grid.bind(minimum_height=grid.setter('height'))


def build_back_btn(callback):
    """Standard back button used across all detail views."""
    btn = MinimalButton(
        text=t("back_btn"), btn_color=BTN_PRIMARY, font_size=sp(11),
        size_hint_y=None, height=dp(48),
    )
    btn.bind(on_press=lambda *a: callback())
    return btn


def make_styled_popup(title, content, size_hint=(0.92, 0.75)):
    """Popup styled with game theme colours."""
    return Popup(
        title=title, content=content,
        size_hint=size_hint,
        title_size=sp(12),
        background_color=popup_color(BG_CARD),
        title_color=popup_color(ACCENT_GOLD),
        separator_color=popup_color(ACCENT_GOLD),
    )


def make_dynamic_label(text, font_size="11sp", color=TEXT_SECONDARY,
                       padding=dp(16), halign="left"):
    """Label that auto-wraps and auto-sizes height to content."""
    lbl = AutoShrinkLabel(
        text=text, font_size=font_size, color=color,
        size_hint_y=None, halign=halign, valign="top", markup=True,
    )
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w - padding, None)))
    lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)))
    return lbl


def _batch_fill_grid(grid, widgets):
    """Add widgets to grid with only one layout pass instead of N.

    Unbinds the minimum_height→height KV rule before the loop so that
    each add_widget() does NOT trigger a full layout recalculation.
    Sets height once at the end, then rebinds.
    Skips reparenting if widgets are already the grid's children.
    """
    # Skip if already showing these exact widgets in order
    if (grid.children and len(grid.children) == len(widgets)
            and all(a is b for a, b in zip(reversed(grid.children), widgets))):
        return
    _invalidate_grid_cache(grid)
    grid.unbind(minimum_height=grid.setter('height'))
    grid.clear_widgets()
    for w in widgets:
        if w.parent:
            w.parent.remove_widget(w)
        grid.add_widget(w)
    grid.height = grid.minimum_height
    grid.bind(minimum_height=grid.setter('height'))


def _bind_long_tap(widget, callback):
    """Bind simple tap (with scroll protection) to fire callback on touch_up."""
    def _on_down(w, touch):
        if not w.collide_point(*touch.pos):
            return False
        touch.ud.setdefault('_tap_t', {})[id(w)] = True
        return False  # don't consume — let scroll etc. work

    def _on_up(w, touch):
        if touch.grab_current is not None:
            return False
        if not w.collide_point(*touch.pos):
            return False
        if hasattr(touch, 'ox') and hasattr(touch, 'oy'):
            dx = abs(touch.x - touch.ox)
            dy = abs(touch.y - touch.oy)
            if dx > dp(8) or dy > dp(8):
                return False
        if not touch.ud.get('_tap_t', {}).get(id(w)):
            return False
        callback(w)
        return True

    widget.bind(on_touch_down=_on_down)
    widget.bind(on_touch_up=_on_up)


def build_tab_row(tabs, current, on_select, active_color=None, inactive_color=None,
                  height=None, font_size=sp(10)):
    """Build a horizontal row of tab buttons.

    Args:
        tabs: list of (value, display_text) pairs
        current: currently active value
        on_select: callable(value) called when a tab is pressed
        active_color: RGBA for the active button background (default: ACCENT_RED)
        inactive_color: RGBA for inactive buttons (default: BTN_DISABLED)
        height: row height (default: dp(36))
        font_size: button font size
    Returns:
        BoxLayout row widget
    """
    if active_color is None:
        active_color = ACCENT_RED
    if inactive_color is None:
        inactive_color = BTN_DISABLED
    if height is None:
        height = dp(36)

    row = BoxLayout(size_hint_y=None, height=height, spacing=dp(4))
    for value, label_text in tabs:
        active = (value == current)
        btn = MinimalButton(
            text=label_text, font_size=font_size,
            btn_color=active_color if active else inactive_color,
            text_color=TEXT_PRIMARY if active else TEXT_MUTED,
        )
        btn.bind(on_press=lambda inst, v=value: on_select(v))
        row.add_widget(btn)
    return row


def _debug_border(widget, color=(1, 0, 0, 1)):
    from kivy.graphics import Color, Line
    def _update(*args):
        widget.canvas.after.clear()
        with widget.canvas.after:
            Color(*color)
            Line(rectangle=(widget.x, widget.y, widget.width, widget.height), width=1)
    widget.bind(pos=_update, size=_update)
    return widget


def _auto_text_size(label):
    bind_text_wrap(label)
    return label


def _diamond_label(amount, font_size="12sp", color=ACCENT_CYAN):
    """BoxLayout with number + diamond icon (icon to the right), vertically centered."""
    from kivy.uix.anchorlayout import AnchorLayout
    anchor = AnchorLayout(size_hint=(1, 1), anchor_x="center", anchor_y="center")
    box = BoxLayout(
        orientation="horizontal", size_hint=(None, None),
        spacing=0, height=dp(28),
    )
    box.bind(minimum_width=box.setter("width"))
    lbl = AutoShrinkLabel(
        text=str(amount), font_size=font_size, bold=True,
        color=color, halign="right", valign="middle",
        size_hint_x=None,
    )
    lbl.bind(texture_size=lbl.setter("size"))
    box.add_widget(lbl)
    box.add_widget(Image(
        source="sprites/icons/ic_gem.png", fit_mode="contain",
        size_hint=(None, None), width=dp(18), height=dp(18),
    ))
    anchor.add_widget(box)
    return anchor


# ============================================================
#  ROSTER CARD VIEW (RecycleView viewclass)
# ============================================================

_roster_callbacks = {}
"""Callbacks registered by RosterScreen.on_enter.
Keys: 'show_detail', 'dismiss' → callable(fighter_index: int)
"""


class RosterCardView(RecycleDataViewBehavior, CardWidget):
    """RecycleView viewclass for roster cards.

    A small pool of these is kept alive by RecycleView (only visible rows
    + a buffer).  refresh_view_attrs() updates visuals in-place so no
    widget construction happens during scrolling.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'horizontal')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(84))
        kwargs.setdefault('padding', [dp(8), dp(10)])
        kwargs.setdefault('spacing', dp(6))
        super().__init__(**kwargs)
        self._fighter_index = 0
        self._dismiss_cb = None

        ROW_H = dp(56)

        # Avatar
        self._avatar = GladiatorAvatar(
            fighter_class="mercenary",
            accent_color=list(ACCENT_GREEN),
            tier=1,
            size_hint=(None, None),
            width=dp(48), height=dp(52),
        )

        # Name
        self._name_lbl = AutoShrinkLabel(
            font_size="12sp", bold=True, color=list(TEXT_PRIMARY),
            halign="left", size_hint_x=None, width=dp(130),
            size_hint_y=None, height=ROW_H,
        )
        self._name_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))

        # Level
        self._level_lbl = AutoShrinkLabel(
            font_size="11sp", bold=True, color=list(ACCENT_GOLD),
            halign="left", size_hint_x=None, width=dp(56),
            size_hint_y=None, height=ROW_H,
        )
        self._level_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))

        # Third slot (dismiss btn / away label / empty)
        self._dismiss_btn = MinimalButton(
            text="X", btn_color=list(ACCENT_RED), font_size=sp(11),
            size_hint_x=None, width=dp(36),
        )
        self._away_lbl = AutoShrinkLabel(
            font_size="11sp", color=list(ACCENT_CYAN), halign="center",
            size_hint_x=None, width=dp(44), size_hint_y=None, height=ROW_H,
        )
        self._away_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self._empty_lbl = Label(size_hint_x=None, width=0)
        self._slot = 'empty'

        # Spacer pushes stats to the right
        self._spacer = Label(size_hint_x=1)

        # Stats: HP only — compact, fixed width
        ICON_W = dp(90)
        self._stat_box = BoxLayout(
            orientation="horizontal", spacing=dp(2),
            size_hint_x=None, width=ICON_W + dp(4),
            size_hint_y=None, height=ROW_H,
        )
        self._hp_row = _icon_label("sprites/icons/ic_hp.png", 0, (1, 0.3, 0.3, 1), font_size="11sp", height=ROW_H)
        self._stat_box.add_widget(self._hp_row)

        # Plus indicator — available stat/perk points
        self._plus_icon = Image(
            source="icons/ic_plus.png", fit_mode="contain",
            size_hint=(None, None), width=dp(18), height=dp(18),
            opacity=0,
        )

        self.add_widget(self._avatar)
        self.add_widget(self._name_lbl)
        self.add_widget(self._level_lbl)
        self.add_widget(self._plus_icon)
        self.add_widget(self._empty_lbl)
        self.add_widget(self._spacer)
        self.add_widget(self._stat_box)

        # Long-tap opens fighter detail popup
        _bind_long_tap(self, lambda w: self._on_tap())

    def _on_tap(self):
        cb = _roster_callbacks.get('show_detail')
        if cb:
            cb(self._fighter_index)

    def _set_slot(self, slot):
        """Swap the last element (dismiss/away/empty) in the card row."""
        if self._slot == slot:
            return
        if self._slot == 'dismiss':
            self.remove_widget(self._dismiss_btn)
        elif self._slot == 'away':
            self.remove_widget(self._away_lbl)
        else:
            self.remove_widget(self._empty_lbl)
        if slot == 'dismiss':
            self.add_widget(self._dismiss_btn)
        elif slot == 'away':
            self.add_widget(self._away_lbl)
        else:
            self.add_widget(self._empty_lbl)
        self._slot = slot

    def refresh_view_attrs(self, rv, index, data):
        """Called by RecycleView when this instance is (re)assigned to a row."""
        self._fighter_index = data['index']

        # Avatar sprite by class
        fc = data.get('fighter_class', 'mercenary')
        self._avatar.fighter_class = fc
        self._avatar.accent_color = list(_CLASS_COLORS.get(fc, ACCENT_GREEN))
        self._avatar.tier = data.get('level', 1)
        self._avatar.is_wounded = bool(data.get('injuries', 0))

        # Card background — directly update canvas Color objects
        if not data['alive']:
            self._bg_color.rgba = (0.15, 0.08, 0.08, 1)
            self._br_color.rgba = list(ACCENT_RED)
        else:
            self._bg_color.rgba = list(BG_CARD)
            self._br_color.rgba = list(DIVIDER)

        # Name label
        if not data['alive']:
            self._name_lbl.text = f"{data['name']} [{t('dead_tag')}]"
            self._name_lbl.color = list(ACCENT_RED)
        elif data['on_expedition']:
            self._name_lbl.text = data['name']
            self._name_lbl.color = list(ACCENT_CYAN)
        else:
            self._name_lbl.text = data['name']
            self._name_lbl.color = list(TEXT_PRIMARY)

        # Level label
        self._level_lbl.text = f"LV {data['level']}"

        # Third slot
        if not data['alive']:
            self._set_slot('dismiss')
            if self._dismiss_cb is not None:
                self._dismiss_btn.unbind(on_press=self._dismiss_cb)
            idx = data['index']
            self._dismiss_cb = lambda inst, i=idx: (
                _roster_callbacks.get('dismiss') and _roster_callbacks['dismiss'](i)
            )
            self._dismiss_btn.bind(on_press=self._dismiss_cb)
        elif data['on_expedition']:
            self._set_slot('away')
            self._away_lbl.text = t('away_tag')
        else:
            self._set_slot('empty')

        # Plus icon — available upgrades
        has_upgrades = data['alive'] and (
            data.get('unused_points', 0) > 0 or data.get('perk_points', 0) > 0
        )
        self._plus_icon.opacity = 1 if has_upgrades else 0

        # Stat label
        self._hp_row.children[0].text = fmt_num(data['hp'])
        # Do NOT call super().refresh_view_attrs — it would auto-setattr all data
        # keys onto this widget, overwriting CardWidget.active etc.
        # refresh_view_layout is still inherited from RecycleDataViewBehavior.


# ============================================================
#  ROSTER
# ============================================================

def _icon_label(icon_src, text, color, font_size="11sp", height=dp(28)):
    """Helper: icon image + label in a horizontal box."""
    row = BoxLayout(size_hint_y=None, height=height, spacing=0)
    ico = Image(source=icon_src, fit_mode="contain",
                size_hint=(None, 1), width=height * 0.8)
    ico.color = [1, 1, 1, 1]
    row.add_widget(ico)
    lbl = AutoShrinkLabel(text=str(text), font_size=font_size, bold=True,
                color=color, halign="left", valign="middle")
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    row.add_widget(lbl)
    return row


def build_roster_card(data, roster_screen):
    """Minimal card: name, level, STR/AGI/HP icons. Tap to open detail popup."""
    from game.widgets import BaseCard

    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(72),
                    padding=[dp(10), dp(6)], spacing=dp(4))

    if not data["alive"]:
        card.card_color = (0.15, 0.08, 0.08, 1)
        card.border_color = ACCENT_RED

    idx = data["index"]

    if not data["alive"]:
        name_text = f"{data['name']} [{t('dead_tag')}]"
        name_color = ACCENT_RED
    elif data["on_expedition"]:
        name_text = data["name"]
        name_color = ACCENT_CYAN
    else:
        name_text = data["name"]
        name_color = TEXT_PRIMARY

    # Row 1: Name + Level + status/dismiss
    status_widget = Label(size_hint_x=0.25)
    if not data["alive"]:
        status_widget = MinimalButton(
            text="X", btn_color=ACCENT_RED, font_size=sp(11), size_hint_x=0.25,
        )
        status_widget.bind(on_press=lambda inst, i=idx: roster_screen.dismiss(i))
    elif data["on_expedition"]:
        status_widget = _auto_text_size(AutoShrinkLabel(
            text=t("away_tag"), font_size="10sp", color=ACCENT_CYAN,
            halign="right", size_hint_x=0.25,
        ))
    card.add_text_row(
        (name_text, sp(11), True, name_color, 0.55),
        (f"LV {data['level']}", sp(11), True, ACCENT_GOLD, 0.2),
        status_widget,
        height=dp(34),
    )

    # Row 2: HP
    card.add_icon_labels([
        ("sprites/icons/ic_hp.png", fmt_num(data['hp']), (1, 0.3, 0.3, 1), sp(8)),
    ], height=dp(28), spacing=dp(8))

    _bind_long_tap(card, lambda w, i=idx: roster_screen.show_fighter_detail(i))
    return card


def refresh_roster_grid(roster_screen):
    rv = roster_screen.ids.get('roster_rv')
    if not rv:
        return
    rv.data = [dict(d) for d in roster_screen.gladiators_data]


# ============================================================
#  UNIFIED ITEM CARD
# ============================================================


def build_item_info_card(item, subtitle=None, subtitle_color=None, fighter=None, equipped_on=None, on_tap=None):
    """Unified item info card — 3 rows: name, subtitle, total stats."""
    import game.models as _m
    from game.models import item_display_name, calc_item_stats
    from game.widgets import BaseCard

    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)
    slot = item.get("slot", "?")

    display_name = item_display_name(item) if slot in ("weapon", "armor", "accessory", "relic") else item.get("name", "?")
    upgrade_lvl = item.get("upgrade_level", 0)
    level_display = f"+{upgrade_lvl}" if upgrade_lvl > 0 else ""
    ench = item.get("enchantment", "")
    ench_display = ""
    if ench:
        ench_data = _m.ENCHANTMENT_TYPES.get(ench)
        ench_display = f"[{ench_data['name']}]" if ench_data else f"[{ench}]"
    if subtitle:
        slot_rarity = subtitle
    else:
        slot_rarity = f"{t('slot_' + slot + '_upper')} [{t('rarity_' + rarity + '_upper')}]"
    s, a, v = calc_item_stats(item, fighter)

    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(75),
                    padding=[dp(12), dp(8)], spacing=dp(4))
    card.border_color = rcolor

    # Row 1: name | +level | [enchantment]
    row1 = BoxLayout(size_hint_y=0.35, spacing=dp(4))
    name_lbl = AutoShrinkLabel(
        text=display_name, font_size=sp(12), bold=True, color=rcolor,
        halign="left", size_hint_x=None, width=1,
    )
    name_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row1.add_widget(name_lbl)
    level_lbl = AutoShrinkLabel(
        text=level_display, font_size=sp(10), bold=True, color=ACCENT_GOLD,
        halign="left", size_hint_x=None, width=dp(28),
    )
    level_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row1.add_widget(level_lbl)
    ench_lbl = AutoShrinkLabel(
        text=ench_display, font_size=sp(11), bold=True, color=ACCENT_PURPLE,
        halign="left", size_hint_x=None, width=1,
    )
    ench_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row1.add_widget(ench_lbl)
    card.add_widget(row1)

    # Row 2: slot/rarity | equipped fighter
    row2 = BoxLayout(size_hint_y=0.25, spacing=dp(4))
    sr_lbl = AutoShrinkLabel(
        text=slot_rarity, font_size=sp(11), color=subtitle_color or TEXT_MUTED,
        halign="left", size_hint_x=None, width=1,
    )
    sr_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
    row2.add_widget(sr_lbl)
    if equipped_on:
        eq_lbl = AutoShrinkLabel(
            text=equipped_on, font_size=sp(11), bold=True, color=ACCENT_CYAN,
            halign="left", size_hint_x=None, width=1,
        )
        eq_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row2.add_widget(eq_lbl)
    card.add_widget(row2)

    # Row 3: stat icons
    row3 = BoxLayout(size_hint_y=0.40, spacing=dp(8))
    ico_h = dp(16)
    stat_items = []
    if s > 0:
        stat_items.append(("sprites/icons/ic_str.png", fmt_num(s)))
    if a > 0:
        stat_items.append(("sprites/icons/ic_agi.png", fmt_num(a)))
    if v > 0:
        stat_items.append(("sprites/icons/ic_vit.png", fmt_num(v)))
    for icon_src, val_text in stat_items:
        lbl = AutoShrinkLabel(
            text=val_text, font_size=sp(10), bold=True, color=ACCENT_GREEN,
            halign="left", valign="middle",
            size_hint_x=None, width=1,
        )
        lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row3.add_widget(lbl)
        row3.add_widget(Image(source=icon_src, fit_mode="contain",
                              size_hint=(None, 1), width=ico_h))
    if not (s or a or v):
        row3.add_widget(_auto_text_size(AutoShrinkLabel(
            text="—", font_size=sp(10), color=TEXT_MUTED, halign="left",
        )))
    card.add_widget(row3)

    if on_tap:
        card.bind(on_press=on_tap)
    return card


# ============================================================
#  FORGE
# ============================================================

def build_forge_card(item, forge_screen):
    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)

    wrapper = BoxLayout(
        orientation="vertical",
        size_hint_y=None, height=dp(114),
        spacing=dp(4),
    )

    from kivy.app import App
    def _tap(inst, it=item):
        # Shop tap always opens pristine shop preview (never the
        # upgraded/enchanted inventory copy — use ИНВЕНТАРЬ for that).
        App.get_running_app().open_shop_preview(it)
    wrapper.add_widget(build_item_info_card(item, on_tap=_tap))

    affordable = item["affordable"]
    buy_btn = MinimalButton(
        text=t("buy_btn_price", price=fmt_num(item['cost'])), font_size=sp(11),
        size_hint_y=None, height=dp(32),
        btn_color=rcolor if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gold.png",
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: forge_screen.buy(iid))
    wrapper.add_widget(buy_btn)
    return wrapper


def _get_card_cache(forge_screen):
    """Get or create the permanent {item_id: card} cache."""
    cache = getattr(forge_screen, '_card_by_id', None)
    if cache is None:
        cache = {}
        forge_screen._card_by_id = cache
    return cache


# ------------------------------------------------------------------
#  RecycleView viewclass — forge shop card. Widgets pre-created once,
#  refresh_view_attrs just updates text/color/visibility. Allows
#  RecycleView to virtualize (only ~10 cards exist at any time, rest
#  recycled on scroll).
# ------------------------------------------------------------------

class ForgeCardView(RecycleDataViewBehavior, BoxLayout):
    """RecycleView viewclass for forge shop cards."""

    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        kwargs.setdefault('height', dp(114))
        kwargs.setdefault('spacing', dp(4))
        super().__init__(**kwargs)
        self._iid = ''
        self._forge_screen = None

        # --- Info card (75dp) ---
        from game.widgets import BaseCard
        self._info = BaseCard(
            orientation="vertical", size_hint_y=None, height=dp(75),
            padding=[dp(12), dp(8)], spacing=dp(4),
        )

        # Row 1: name | level | enchantment
        row1 = BoxLayout(size_hint_y=0.35, spacing=dp(4))
        self._name_lbl = AutoShrinkLabel(
            font_size=sp(12), bold=True, halign="left",
            size_hint_x=None, width=1,
        )
        self._name_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row1.add_widget(self._name_lbl)
        self._level_lbl = AutoShrinkLabel(
            font_size=sp(10), bold=True, color=list(ACCENT_GOLD),
            halign="left", size_hint_x=None, width=dp(28),
        )
        self._level_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row1.add_widget(self._level_lbl)
        self._ench_lbl = AutoShrinkLabel(
            font_size=sp(11), bold=True, color=list(ACCENT_PURPLE),
            halign="left", size_hint_x=None, width=1,
        )
        self._ench_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row1.add_widget(self._ench_lbl)
        self._info.add_widget(row1)

        # Row 2: slot/rarity label
        row2 = BoxLayout(size_hint_y=0.25, spacing=dp(4))
        self._sr_lbl = AutoShrinkLabel(
            font_size=sp(11), color=list(TEXT_MUTED),
            halign="left", size_hint_x=None, width=1,
        )
        self._sr_lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
        row2.add_widget(self._sr_lbl)
        self._info.add_widget(row2)

        # Row 3: stat icons — pre-create all 3 pairs + "—" fallback
        self._row3 = BoxLayout(size_hint_y=0.40, spacing=dp(8))

        def _mk_stat(icon_src):
            lbl = AutoShrinkLabel(
                font_size=sp(10), bold=True, color=list(ACCENT_GREEN),
                halign="left", valign="middle", size_hint_x=None, width=1,
            )
            lbl.bind(texture_size=lambda w, ts: setattr(w, 'width', ts[0]))
            ico = Image(source=icon_src, fit_mode="contain",
                        size_hint=(None, 1), width=dp(16))
            return lbl, ico
        self._str_lbl, self._str_ico = _mk_stat("sprites/icons/ic_str.png")
        self._agi_lbl, self._agi_ico = _mk_stat("sprites/icons/ic_agi.png")
        self._vit_lbl, self._vit_ico = _mk_stat("sprites/icons/ic_vit.png")
        self._no_stat_lbl = AutoShrinkLabel(
            text="—", font_size=sp(10), color=list(TEXT_MUTED), halign="left",
        )
        self._info.add_widget(self._row3)
        self.add_widget(self._info)

        # Buy button (32dp)
        self._buy_btn = MinimalButton(
            font_size=sp(11), size_hint_y=None, height=dp(32),
            icon_source="sprites/icons/ic_gold.png",
        )
        self._buy_btn.bind(on_press=self._on_buy_press)
        self.add_widget(self._buy_btn)

        # Tap on info card → open item detail
        _bind_long_tap(self._info, lambda w: self._on_info_tap())

    def refresh_view_attrs(self, rv, index, data):
        """Called by RecycleView when this instance should display new data.
        Do NOT call super — that would auto-setattr all data keys."""
        self._iid = data.get('iid', '')
        self._forge_screen = data.get('_forge')
        rcolor = list(data.get('rarity_color', TEXT_PRIMARY))
        self._info.border_color = rcolor

        self._name_lbl.text = data.get('name', '')
        self._name_lbl.color = rcolor

        lvl = data.get('upgrade_level', 0)
        self._level_lbl.text = f"+{lvl}" if lvl > 0 else ""
        self._ench_lbl.text = data.get('ench_display', '')
        self._sr_lbl.text = data.get('slot_rarity_text', '')

        # Stats row — clear and re-add only the stats that are > 0
        self._row3.clear_widgets()
        s = data.get('s', 0)
        a = data.get('a', 0)
        v = data.get('v', 0)
        if s > 0:
            self._str_lbl.text = str(s)
            self._row3.add_widget(self._str_lbl)
            self._row3.add_widget(self._str_ico)
        if a > 0:
            self._agi_lbl.text = str(a)
            self._row3.add_widget(self._agi_lbl)
            self._row3.add_widget(self._agi_ico)
        if v > 0:
            self._vit_lbl.text = str(v)
            self._row3.add_widget(self._vit_lbl)
            self._row3.add_widget(self._vit_ico)
        if not (s or a or v):
            self._row3.add_widget(self._no_stat_lbl)

        # Buy button
        affordable = data.get('affordable', False)
        self._buy_btn.text = data.get('buy_text', '')
        self._buy_btn.btn_color = rcolor if affordable else list(BTN_DISABLED)
        self._buy_btn.text_color = list(BG_DARK) if affordable else list(TEXT_MUTED)

    def _on_buy_press(self, inst):
        if self._forge_screen and self._iid:
            self._forge_screen.buy(self._iid)

    def _on_info_tap(self):
        """Shop tap always shows the pristine shop preview — even if the
        player already owns a (possibly upgraded/enchanted) copy. The
        upgraded inventory copy is accessible from the ИНВЕНТАРЬ tab."""
        from kivy.app import App
        app = App.get_running_app()
        item = next(
            (i for i in app.engine.get_forge_items() if i['id'] == self._iid),
            None,
        )
        if item:
            app.open_shop_preview(item)


def _forge_item_to_rv_data(item, forge_screen):
    """Convert engine forge item dict to ForgeCardView data dict."""
    import game.models as _m
    from game.models import calc_item_stats, item_display_name

    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)
    slot = item.get("slot", "?")
    ench_id = item.get("enchantment", "")
    ench_display = ""
    if ench_id:
        ench_data = _m.ENCHANTMENT_TYPES.get(ench_id)
        ench_display = f"[{ench_data['name']}]" if ench_data else f"[{ench_id}]"
    slot_rarity = f"{t('slot_' + slot + '_upper')} [{t('rarity_' + rarity + '_upper')}]"
    s, a, v = calc_item_stats(item, None)
    return {
        'iid': item['id'],
        '_forge': forge_screen,
        'name': item_display_name(item),
        'rarity_color': list(rcolor),
        'upgrade_level': item.get('upgrade_level', 0),
        'ench_display': ench_display,
        'slot_rarity_text': slot_rarity,
        's': s, 'a': a, 'v': v,
        'affordable': item.get('affordable', False),
        'buy_text': t('buy_btn_price', price=fmt_num(item['cost'])),
    }


def refresh_forge_grid(forge_screen):
    """Populate forge shop list. Uses RecycleView (forge_rv) if available,
    falls back to legacy GridLayout (forge_grid) otherwise."""
    items = forge_screen.forge_items

    # Prefer RecycleView — virtualizes to ~10 visible widgets
    rv = forge_screen.ids.get("forge_rv")
    if rv is not None:
        rv.data = [_forge_item_to_rv_data(i, forge_screen) for i in items]
        return

    # Legacy path: GridLayout with pre-built cached cards (all 130 in tree)
    grid = forge_screen.ids.get("forge_grid")
    if not grid:
        return
    item_ids = [i["id"] for i in items]

    # Build missing cards (once per item, cached forever)
    cache = _get_card_cache(forge_screen)
    for item in items:
        iid = item["id"]
        if iid not in cache:
            cache[iid] = build_forge_card(item, forge_screen)

    # Collect cards in display order and update affordability
    cards = []
    for item in items:
        card = cache[item["id"]]
        rcolor = RARITY_COLORS.get(item.get("rarity", "common"), TEXT_PRIMARY)
        affordable = item["affordable"]
        buy_btn = card.children[0]
        buy_btn.btn_color = rcolor if affordable else BTN_DISABLED
        buy_btn.text_color = BG_DARK if affordable else TEXT_MUTED
        cards.append(card)

    # Skip re-layout if already showing the same cards in same order
    if (hasattr(grid, '_item_ids') and grid._item_ids == item_ids
            and len(grid.children) == len(cards)):
        return

    grid._item_ids = item_ids
    _batch_fill_grid(grid, cards)


# ============================================================
#  EXPEDITIONS
# ============================================================

def build_expedition_card(exp, fighters, expedition_screen):
    from game.widgets import BaseCard
    from game.models import SHARD_TIERS

    card = BaseCard(orientation="vertical", size_hint_y=None, height=dp(190),
                    padding=[dp(12), dp(8)], spacing=dp(6))

    card.add_text_row(
        (exp["name"], sp(11), True, ACCENT_PURPLE, 0.7),
        (exp["duration_text"], sp(10), False, TEXT_SECONDARY, 0.3),
        size_hint_y=0.3,
    )
    card.add_label(exp["desc"], font_size=sp(11), color=TEXT_MUTED, halign="left", size_hint_y=0.2)
    card.add_text_row(
        (f"Lv.{exp['min_level']}+", sp(11), False, ACCENT_CYAN, 0.33),
        (t("danger_label", v=f"{exp['danger']:.0%}"), sp(11), False, ACCENT_RED, 0.34),
        (t("relic_chance", v=f"{exp['relic_chance']:.0%}"), sp(11), False, ACCENT_GOLD, 0.33),
        size_hint_y=0.2,
    )

    shard_info = SHARD_TIERS.get(exp["id"])
    relic_pct = int(exp.get("relic_chance", 0) * 100)
    reward_parts = []
    if shard_info:
        tier = shard_info["tier"]
        _key = f"shard_tier_{tier}_name"
        _translated = t(_key)
        reward_parts.append(_translated if _translated != _key else shard_info["name"])
    reward_parts.append(f"{t('relic_slot')} ({relic_pct}%)")
    card.add_label(" + ".join(reward_parts), font_size=sp(10), color=ACCENT_GOLD, size_hint_y=0.12)

    eligible = [f for f in fighters if f["level"] >= exp["min_level"]]
    if eligible:
        send_btn = MinimalButton(text=t("send_btn"), font_size=sp(11), btn_color=ACCENT_PURPLE)
        def _open_send_popup(inst, elig=eligible, eid=exp["id"], scr=expedition_screen):
            _show_send_fighter_popup(elig, eid, scr)
        send_btn.bind(on_press=_open_send_popup)
        card.add_button_row([send_btn], height=dp(190 * 0.25))
    else:
        card.add_label(t("no_eligible"), font_size=sp(11), color=TEXT_MUTED, size_hint_y=0.25)
    return card


def build_expedition_status_card(status):
    from game.widgets import BaseCard

    card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(44),
                    padding=[dp(10), dp(4)], spacing=dp(6))
    card.border_color = ACCENT_CYAN
    card.add_text_row(
        (status["fighter_name"], sp(8), True, ACCENT_CYAN, 0.30),
        (status["expedition_name"], sp(7), False, TEXT_SECONDARY, 0.45),
        (status["remaining_text"], sp(8), True, ACCENT_GOLD, 0.25),
    )
    return card


def _show_send_fighter_popup(eligible, expedition_id, expedition_screen):
    """Popup to select which fighter to send on expedition."""
    from kivy.uix.scrollview import ScrollView

    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    content = BoxLayout(orientation="vertical", spacing=dp(8),
                        padding=dp(12), size_hint_y=None)
    content.bind(minimum_height=content.setter("height"))

    popup = Popup(
        title=t("send_btn"),
        title_color=list(ACCENT_PURPLE)[:3] + [1],
        title_size=sp(11),
        content=scroll,
        size_hint=(0.85, None),
        height=dp(80 + len(eligible) * 54),
        background_color=list(BG_CARD)[:3] + [1],
        separator_color=list(ACCENT_PURPLE)[:3] + [1],
        auto_dismiss=True,
    )

    for f_data in eligible:
        btn = MinimalButton(
            text=f"{f_data['name']}  LV{f_data['level']}",
            font_size=sp(11),
            btn_color=ACCENT_PURPLE,
            size_hint_y=None, height=dp(44),
        )
        def _send(inst, fi=f_data["index"], eid=expedition_id):
            popup.dismiss()
            expedition_screen.send(fi, eid)
        btn.bind(on_press=_send)
        content.add_widget(btn)

    scroll.add_widget(content)
    popup.open()


def refresh_expedition_grid(expedition_screen):
    grid = expedition_screen.ids.get("expedition_grid")
    if not grid:
        return

    tab = getattr(expedition_screen, "expedition_tab", "missions")
    if tab == "missions":
        # Build cache key from status data (remaining times change every tick)
        status_key = tuple((s["fighter_name"], s["remaining_text"]) for s in expedition_screen.status_data)
        if status_key == getattr(grid, '_exp_status_key', None) and grid.children:
            return
        grid._exp_status_key = status_key
        cards = [build_expedition_status_card(s)
                 for s in expedition_screen.status_data]
    else:
        # Available expeditions — only rebuild if data changed
        exp_key = tuple(e["id"] for e in expedition_screen.expeditions_data)
        fighters_key = tuple((f["index"], f["level"]) for f in expedition_screen.fighters_for_send)
        full_key = (exp_key, fighters_key)
        if full_key == getattr(grid, '_exp_hunts_key', None) and grid.children:
            return
        grid._exp_hunts_key = full_key
        cards = [
            build_expedition_card(exp, expedition_screen.fighters_for_send, expedition_screen)
            for exp in expedition_screen.expeditions_data
        ]
    _batch_fill_grid(grid, cards)


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
        text=f"{fmt_num(item['cost'])}", font_size=sp(11), size_hint_x=0.35,
        btn_color=ACCENT_BLUE if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gold.png",
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: shop_screen.buy(iid))

    card.add_widget(info)
    card.add_widget(buy_btn)
    return card


def refresh_shop_grid(shop_screen):
    grid = shop_screen.ids.get("shop_grid")
    if not grid:
        return
    cards = [build_shop_card(item, shop_screen) for item in shop_screen.items_data]
    _batch_fill_grid(grid, cards)


# ============================================================
#  BATTLE FIGHTERS PANEL (ArenaScreen — individual HP bars)
# ============================================================

def build_total_hp_row(summary_text, total_hp, total_max, is_expanded, toggle_callback):
    """Total HP summary bar — tap the bar itself to expand/collapse."""
    from kivy.uix.behaviors import ButtonBehavior

    BAR_H = dp(52)
    centered = f"{summary_text}({max(0, total_hp)}/{total_max})"

    container = RelativeLayout(size_hint_y=None, height=BAR_H)
    hp_pct = max(0, total_hp) / max(1, total_max)
    is_low = hp_pct < LOW_HP_THRESHOLD

    bar = MinimalBar(
        pos_hint={"x": 0, "y": 0}, size_hint=(1, 1),
        value=hp_pct,
        bar_color=HP_PLAYER if not is_low else ACCENT_RED,
        bg_color=HP_PLAYER_BG,
    )
    container.add_widget(bar)

    lbl = AutoShrinkLabel(
        text=centered, font_size="11sp", bold=True,
        color=TEXT_PRIMARY, halign="center", valign="middle",
        pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(1, 1),
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    container.add_widget(lbl)

    # Tap the bar to toggle detail (hold 100ms)
    _bind_long_tap(container, toggle_callback)

    return container


def _build_hp_bar_widget(name, hp, max_hp, bar_color, bg_color, height=dp(40),
                         on_tap=None):
    """HP bar with name and HP centered inside. Optionally tappable."""
    hp_pct = max(0, hp) / max(1, max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD

    container = RelativeLayout(size_hint_y=None, height=height)

    bar = MinimalBar(
        pos_hint={"x": 0, "y": 0}, size_hint=(1, 1),
        value=hp_pct,
        bar_color=bar_color if not is_low else ACCENT_RED,
        bg_color=bg_color,
    )
    container.add_widget(bar)
    container._bar = bar  # keep ref for flash animation

    centered = f"{name}  ({max(0, hp)}/{max_hp})"
    lbl = AutoShrinkLabel(
        text=centered, font_size="11sp", bold=True,
        color=TEXT_PRIMARY, halign="center", valign="middle",
        pos_hint={"center_x": 0.5, "center_y": 0.5}, size_hint=(1, 1),
    )
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    container.add_widget(lbl)

    if on_tap:
        _bind_long_tap(container, on_tap)

    return container


def flash_hp_bar(bar_widget, flash_color=ACCENT_RED):
    """Flash a bar red briefly to show damage taken."""
    from kivy.animation import Animation
    if not hasattr(bar_widget, '_bar') or bar_widget._bar is None:
        return
    bar = bar_widget._bar
    orig = list(bar.bg_color)
    bar.bg_color = list(flash_color)
    anim = Animation(duration=0.15)
    anim.bind(on_complete=lambda *a: setattr(bar, 'bg_color', orig))
    anim.start(bar)


def build_fighter_hp_row(fighter, index, heal_cost, can_afford, heal_callback,
                         on_tap=None):
    """Individual fighter HP bar — tappable for heal."""
    BAR_H = dp(48)

    bar_widget = _build_hp_bar_widget(
        fighter.name, fighter.hp, fighter.max_hp,
        HP_PLAYER, HP_PLAYER_BG, height=BAR_H,
        on_tap=on_tap,
    )
    return bar_widget


def build_unit_card(name, hp, max_hp, border_color=DIVIDER,
                    name_color=TEXT_PRIMARY, hp_color=(1, 0.3, 0.3, 1),
                    avatar_color=None, tier=1, level=None,
                    skill_text=None, fighter_class="mercenary",
                    on_tap=None):
    """Single universal unit card — identical to RosterCardView layout.
    Used on arena, roster detail, and anywhere a unit card is needed.
    Layout: [Avatar | Name | LV X | Skill | spacer | HP icon+number]
    """
    ROW_H = dp(56)

    card = CardWidget(
        orientation="horizontal", size_hint_y=None, height=dp(84),
        padding=[dp(8), dp(10)], spacing=dp(6),
    )
    card.border_color = border_color

    hp_pct = max(0, hp) / max(1, max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD

    # --- Identical to RosterCardView.__init__ ---

    # Avatar
    avatar = GladiatorAvatar(
        fighter_class=fighter_class,
        accent_color=list(avatar_color or ACCENT_GREEN),
        tier=tier,
        size_hint=(None, None),
        width=dp(48), height=dp(52),
    )
    card.add_widget(avatar)

    # Name
    name_lbl = AutoShrinkLabel(
        text=name, font_size="12sp", bold=True, color=name_color,
        halign="left", size_hint_x=None, width=dp(130),
        size_hint_y=None, height=ROW_H,
    )
    name_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    card.add_widget(name_lbl)

    # Level
    level_lbl = AutoShrinkLabel(
        font_size="11sp", bold=True, color=list(ACCENT_GOLD),
        halign="left", size_hint_x=None, width=dp(56),
        size_hint_y=None, height=ROW_H,
    )
    level_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
    if level is not None:
        level_lbl.text = f"LV {level}"
    card.add_widget(level_lbl)

    # Skill badge (arena only, hidden by default)
    skill_badge = AutoShrinkLabel(
        font_size="11sp", bold=True, color=list(TEXT_MUTED),
        halign="center", size_hint_x=None, width=dp(40) if skill_text else 0,
        size_hint_y=None, height=ROW_H,
        opacity=1 if skill_text else 0,
    )
    if skill_text:
        skill_badge.text = skill_text
        skill_badge.color = list(ACCENT_CYAN if skill_text == "RDY" else TEXT_MUTED)
    skill_badge.bind(size=lambda w, s: setattr(w, 'text_size', s))
    card.add_widget(skill_badge)

    # Spacer
    card.add_widget(Label(size_hint_x=1))

    # HP icon + number — identical to RosterCardView
    stat_box = BoxLayout(
        orientation="horizontal", spacing=dp(2),
        size_hint_x=None, width=dp(94),
        size_hint_y=None, height=ROW_H,
    )
    hp_row = _icon_label(
        "sprites/icons/ic_hp.png",
        fmt_num(max(0, hp)),
        ACCENT_RED if is_low else hp_color,
        font_size="11sp", height=ROW_H,
    )
    stat_box.add_widget(hp_row)
    card.add_widget(stat_box)

    # Expose refs for in-place updates
    card._avatar = avatar
    card._name_lbl = name_lbl
    card._level_lbl = level_lbl
    card._skill_badge = skill_badge
    card._hp_lbl = hp_row.children[0]  # the label inside _icon_label

    if on_tap:
        _bind_long_tap(card, on_tap)

    return card


def build_fighter_pit_card(fighter, on_tap=None, skill_text=None):
    """Fighter card — uses build_unit_card (same as roster)."""
    fc = getattr(fighter, "fighter_class", "mercenary")
    return build_unit_card(
        fighter.name, max(0, fighter.hp), fighter.max_hp,
        name_color=TEXT_PRIMARY if fighter.alive and fighter.hp > 0 else ACCENT_RED,
        avatar_color=_CLASS_COLORS.get(fc, ACCENT_GREEN),
        tier=getattr(fighter, "tier", 1),
        level=getattr(fighter, "level", 1),
        skill_text=skill_text, fighter_class=fc, on_tap=on_tap,
    )


def build_enemy_hp_row(enemy, show_stats=False, on_tap=None):
    """Enemy card — uses build_unit_card (same layout as fighters)."""
    fc = getattr(enemy, "fighter_class", "mercenary")
    return build_unit_card(
        enemy.name, max(0, enemy.hp), enemy.max_hp,
        border_color=ACCENT_RED,
        name_color=ACCENT_RED,
        avatar_color=ACCENT_RED,
        tier=getattr(enemy, "tier", 1),
        level=getattr(enemy, "level", None),
        fighter_class=fc, on_tap=on_tap,
    )


def update_fighter_pit_card(card, fighter, skill_text=None):
    """Update unit card in-place."""
    hp_pct = max(0, fighter.hp) / max(1, fighter.max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD
    card._name_lbl.color = TEXT_PRIMARY if fighter.alive and fighter.hp > 0 else ACCENT_RED
    card._hp_lbl.text = fmt_num(max(0, fighter.hp))
    card._hp_lbl.color = ACCENT_RED if is_low else (1, 0.3, 0.3, 1)
    badge = card._skill_badge
    if badge and skill_text is not None:
        badge.text = skill_text
        badge.color = list(ACCENT_CYAN if skill_text == "RDY" else TEXT_MUTED)
        badge.width = dp(40)
        badge.opacity = 1


def update_enemy_hp_row(row, enemy):
    """Update unit card in-place."""
    hp_pct = max(0, enemy.hp) / max(1, enemy.max_hp)
    is_low = hp_pct < LOW_HP_THRESHOLD
    row._hp_lbl.text = fmt_num(max(0, enemy.hp))
    row._hp_lbl.color = ACCENT_RED if is_low else (1, 0.3, 0.3, 1)


# ============================================================
#  BATTLE LOG (ArenaScreen)
# ============================================================

# ============================================================
#  ACHIEVEMENTS (LoreScreen)
# ============================================================

def build_achievement_card(ach):
    from game.widgets import BaseCard
    from kivy.uix.anchorlayout import AnchorLayout

    unlocked = ach.get("unlocked", False)
    card = BaseCard(orientation="horizontal", size_hint_y=None, height=dp(75),
                    padding=[dp(10), dp(6)], spacing=dp(8))
    if unlocked:
        card.border_color = ACCENT_GOLD
        card.card_color = (0.12, 0.12, 0.08, 1)

    info = BoxLayout(orientation="vertical", size_hint_x=0.7, spacing=dp(4))
    name_color = ACCENT_GOLD if unlocked else TEXT_SECONDARY
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=ach["name"], font_size="11sp", bold=True,
        color=name_color, halign="left", size_hint_y=0.5,
    )))
    info.add_widget(_auto_text_size(AutoShrinkLabel(
        text=ach["desc"], font_size="10sp",
        color=TEXT_MUTED, halign="left", size_hint_y=0.5,
    )))

    reward = AnchorLayout(size_hint_x=0.3, anchor_x="center", anchor_y="center")
    if unlocked:
        reward.add_widget(AutoShrinkLabel(
            text=t("done_label"), font_size="12sp", bold=True,
            color=ACCENT_GREEN, halign="center", valign="middle",
            size_hint=(1, 1),
        ))
    else:
        reward.add_widget(_diamond_label(ach["diamonds"]))

    card.add_widget(info)
    card.add_widget(reward)
    return card


def refresh_achievement_grid(lore_screen):
    grid = lore_screen.ids.get("lore_grid")
    if not grid:
        return
    data = lore_screen.achievements_data
    unlock_hash = tuple(ach.get("unlocked", False) for ach in data)
    if (lore_screen._achievement_widgets
            and len(lore_screen._achievement_widgets) == len(data)
            and lore_screen._achievement_unlock_hash == unlock_hash):
        # Re-parent cached widgets (no construction, no layout spam)
        _batch_fill_grid(grid, lore_screen._achievement_widgets)
        return
    cards = [build_achievement_card(ach) for ach in data]
    lore_screen._achievement_widgets = cards
    lore_screen._achievement_unlock_hash = unlock_hash
    _batch_fill_grid(grid, cards)


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
        text=f"{item['cost']}", font_size=sp(11),
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
        buy_btn.bind(on_press=_buy)
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
        text=str(item["cost"]), font_size=sp(10), size_hint_x=0.45,
        btn_color=ACCENT_CYAN if affordable else BTN_DISABLED,
        text_color=BG_DARK if affordable else TEXT_MUTED,
        icon_source="sprites/icons/ic_gem.png",
    )
    buy_btn.bind(on_press=lambda inst, iid=item["id"]: lore_screen.buy_diamond_item(iid))
    card.add_widget(buy_btn)
    return card


def refresh_diamond_shop_grid(lore_screen):
    grid = lore_screen.ids.get("lore_grid")
    if not grid:
        return
    items = lore_screen.diamond_shop_data
    from game.base_screen import BaseScreen
    shop_key = tuple((it["id"], it.get("affordable", False)) for it in items)
    if not BaseScreen._needs_rebuild(grid, '_dshop_key', shop_key, require_children=True):
        return
    cards = [build_diamond_shop_card(item, lore_screen) for item in items]
    _batch_fill_grid(grid, cards)
