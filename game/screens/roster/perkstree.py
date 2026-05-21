# Build: 1
"""Perk tree RV data assembly — pure data builder, no screen state."""
from ._screen_imports import *  # noqa: F401,F403
from ._screen_imports import _m


def build_perk_tree_data(f, fighter_idx, expanded):
    """Assemble the heterogeneous row-dict list for perk_tree_rv."""
    from game.ui_helpers import _measure_perk_card_height
    data = []

    data.append({
        'viewclass': 'PerkTreeLabelView',
        'text': f"{f.class_name} — {t('perks_btn')}",
        'font_size': '11sp', 'bold': True, 'color': ACCENT_CYAN,
        'height': dp(30),
    })

    data.append({
        'viewclass': 'PerkTreeLabelView',
        'text': t("perk_points_label", n=f.perk_points),
        'font_size': '10sp', 'bold': False,
        'color': ACCENT_GOLD if f.perk_points > 0 else TEXT_MUTED,
        'height': dp(30),
    })

    cls_data = _m.FIGHTER_CLASSES.get(f.fighter_class, {})
    passive = cls_data.get("passive_ability")
    if passive:
        data.append({
            'viewclass': 'PerkTreePerkCardView',
            'perk_id': f"__passive_{f.fighter_class}",
            'fighter_idx': fighter_idx,
            'state': 'unlocked',
            'name': f"{t('perk_passive_label')}: {passive['name']}",
            'desc': passive.get('description', ''),
            'btn_text': '',
            'height': _measure_perk_card_height(passive.get('description', '')),
        })

    all_perks = []
    for cid, cdata in _m.FIGHTER_CLASSES.items():
        for perk in cdata.get("perk_tree", []):
            all_perks.append((cid, perk))
    own_perks = [(cid, p) for cid, p in all_perks if cid == f.fighter_class]
    cross_perks = [(cid, p) for cid, p in all_perks if cid != f.fighter_class]

    for section_label, perks, section_key in [
        ("", own_perks, "own"),
        (t("perk_cross_class", mult="2"), cross_perks, "cross"),
    ]:
        if not perks:
            continue
        if section_label:
            data.append({
                'viewclass': 'PerkTreeLabelView',
                'text': section_label,
                'font_size': '10sp', 'bold': True, 'color': TEXT_MUTED,
                'height': dp(26),
            })

        tiers = {}
        for cid, perk in perks:
            tiers.setdefault(perk.get("tier", 1), []).append((cid, perk))

        for tier_num in sorted(tiers.keys()):
            tier_key = f"{section_key}_t{tier_num}"
            is_open = expanded.get(tier_key, False)
            arrow = "v" if is_open else ">"
            tier_perks = tiers[tier_num]
            unlocked_count = sum(1 for _, p in tier_perks if p["id"] in f.unlocked_perks)

            data.append({
                'viewclass': 'PerkTreeTierButtonView',
                'tier_key': tier_key,
                'fighter_idx': fighter_idx,
                'text': f"{arrow}  {t('perk_tier_label', n=tier_num)}  "
                        f"({unlocked_count}/{len(tier_perks)})",
                'height': dp(30),
            })

            if not is_open:
                continue

            for cid, perk in tier_perks:
                is_cross = (cid != f.fighter_class)
                pid = perk["id"]
                is_unlocked = pid in f.unlocked_perks
                cost = perk["cost"]
                if is_cross:
                    cost = int(cost * perk.get("cross_class_cost_mult", 2.0))
                can_unlock = not is_unlocked and f.perk_points >= cost
                if is_unlocked:
                    state = 'unlocked'
                    name_text = f"{perk['name']}  [{t('perk_unlocked')}]"
                elif can_unlock:
                    state = 'can_unlock'
                    name_text = perk['name']
                else:
                    state = 'locked'
                    name_text = perk['name']
                data.append({
                    'viewclass': 'PerkTreePerkCardView',
                    'perk_id': pid,
                    'fighter_idx': fighter_idx,
                    'state': state,
                    'name': name_text,
                    'desc': perk.get('description', ''),
                    'btn_text': t("perk_unlock_btn", cost=cost),
                    'height': _measure_perk_card_height(perk.get('description', '')),
                })

    return data
