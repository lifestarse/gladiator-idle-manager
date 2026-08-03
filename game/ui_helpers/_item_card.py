# Build: 6
"""ui_helpers._item_card — item info card builder."""
from ._imports import *  # noqa: F401,F403
from ._widgets import _auto_text_size
from kivy.uix.scrollview import ScrollView
from game.constants import FIGHTER_ATK_PER_STR, FIGHTER_HP_PER_VIT
from game.passives import passive_count, render_item


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

    display_name = item_display_name(item) if slot in SLOTS else item.get("name", "?")
    upgrade_lvl = item.get("upgrade_level", 0)
    level_display = f"+{upgrade_lvl}" if upgrade_lvl > 0 else ""
    ench = item.get("enchantment", "")
    ench_display = ""
    if ench:
        ench_data = _m.ENCHANTMENT_TYPES.get(ench)
        ench_display = f"[{ench_data['name']}]" if ench_data else f"[{ench}]"
    if subtitle:
        slot_rarity = subtitle
    elif slot in SLOTS:
        slot_rarity = f"{t(SLOTS[slot].label_keys['upper'])} [{t('rarity_' + rarity + '_upper')}]"
    else:
        slot_rarity = f"{t('slot_' + slot + '_upper')} [{t('rarity_' + rarity + '_upper')}]"
    s, a, v = calc_item_stats(item)

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
#  ITEM STATS POPUP — tap-on-card detail in detail/equipped/preview views
# ============================================================


def show_item_stats_popup(item):
    """Popup that spells out the item's stats in plain language.

    Triggered by tapping the item card while already inside the item-detail,
    equipped-detail, or shop-preview view. The compact card up top only shows
    icons + numbers, which testers found unintuitive — this popup names each
    stat and explains the per-point effect.
    """
    import game.models as _m
    from game.models import item_display_name, calc_item_stats

    rarity = item.get("rarity", "common")
    rcolor = RARITY_COLORS.get(rarity, TEXT_PRIMARY)
    title = item_display_name(item)
    upgrade_lvl = item.get("upgrade_level", 0)
    if upgrade_lvl > 0:
        title = f"{title} +{upgrade_lvl}"

    s, a, v = calc_item_stats(item)

    lines = []
    if s > 0:
        lines.append(t("item_stat_str_line", n=s, atk=s * FIGHTER_ATK_PER_STR))
    if a > 0:
        lines.append(t("item_stat_agi_line", n=a))
    if v > 0:
        lines.append(t("item_stat_vit_line", n=v, **{"def": v, "hp": v * FIGHTER_HP_PER_VIT}))
    if not lines:
        lines.append(t("item_no_stats"))

    if upgrade_lvl > 0:
        lines.append(t("item_upgrade_bonus_note", lvl=upgrade_lvl))

    ench = item.get("enchantment", "")
    if ench:
        ench_data = _m.ENCHANTMENT_TYPES.get(ench)
        ench_name = ench_data["name"] if ench_data else ench
        lines.append(t("item_enchant_line", name=ench_name))

    # Passives sit between the enchantment (also a granted power, but bought)
    # and the flavour text. Rule lines first, then the item's own prose, so a
    # player reading top-down gets the mechanic before the story about it.
    passive_lines = render_item(item)
    if passive_lines:
        lines.append(t("item_passive_header"))
        lines.extend(f"  • {line}" for line in passive_lines)
        special = item.get("special_effect", "")
        if special:
            lines.append(special)

    desc = item.get("description", "")
    if desc:
        lines.append(desc)

    body_text = "\n\n".join(lines)

    content = BoxLayout(orientation="vertical", size_hint_y=None,
                        padding=[dp(12), dp(10)], spacing=dp(6))
    content.bind(minimum_height=content.setter("height"))

    lbl = AutoShrinkLabel(
        text=body_text, font_size=sp(11),
        color=TEXT_SECONDARY, halign="left", valign="top",
        markup=True, size_hint_y=None,
    )
    lbl.bind(width=lambda inst, w: setattr(inst, "text_size", (w, None)))
    lbl.bind(texture_size=lambda inst, ts: setattr(inst, "height", ts[1] + dp(8)))
    content.add_widget(lbl)

    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    scroll.add_widget(content)

    popup = Popup(
        title=title,
        title_color=popup_color(rcolor),
        title_size=sp(13),
        content=scroll,
        size_hint=(0.92, 0.7),
        background_color=popup_color(BG_CARD),
        separator_color=popup_color(rcolor),
        auto_dismiss=True,
    )
    popup.open()
    return popup
