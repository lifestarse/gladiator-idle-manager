# Build: 4
"""
Grimy medieval color theme — Darkest Dungeon / Fear & Hunger inspired.
Muted, desaturated, oppressive. Iron and dried blood.
"""

# Background layers — deep, almost black, with brown undertone
BG_DARK = (0.05, 0.04, 0.04, 1)  # near-black with warmth
BG_CARD = (0.09, 0.07, 0.06, 1)  # dark leather brown
BG_CARD_ACTIVE = (0.12, 0.09, 0.06, 1)  # slightly lit card
BG_ELEVATED = (0.11, 0.09, 0.08, 1)  # raised surface

# Accent colors — muted, desaturated, like old paint and rust
ACCENT_GOLD = (0.14, 0.42, 0.16, 1)  # dim tarnished gold
ACCENT_GREEN = (0.48, 0.38, 0.20, 1)  # murky moss
ACCENT_RED = (0.48, 0.10, 0.08, 1)  # dark clotted blood
ACCENT_BLUE = (0.18, 0.26, 0.38, 1)  # blackened steel
ACCENT_PURPLE = (0.30, 0.14, 0.34, 1)  # deep bruise
ACCENT_CYAN = (0.22, 0.35, 0.33, 1)  # tarnished copper

# Text — parchment tones, not pure white
TEXT_PRIMARY = (0.72, 0.66, 0.56, 1)  # aged parchment
TEXT_SECONDARY = (0.42, 0.36, 0.30, 1)  # faded ink
TEXT_MUTED = (0.26, 0.22, 0.18, 1)  # barely visible

# HP bars — blood and bile
HP_PLAYER = (0.32, 0.40, 0.18, 1)  # dark bile green
HP_PLAYER_BG = (0.10, 0.12, 0.06, 1)
HP_ENEMY = (0.45, 0.08, 0.06, 1)  # blackened blood
HP_ENEMY_BG = (0.14, 0.04, 0.03, 1)

# Buttons — grimy, oppressive
BTN_FIGHT = (0.40, 0.08, 0.06, 1)  # dark blood button
BTN_FIGHT_GLOW = (0.45, 0.10, 0.08, 0.15)
BTN_PRIMARY = (0.16, 0.22, 0.32, 1)  # cold dark iron
BTN_SUCCESS = (0.18, 0.30, 0.14, 1)  # swamp moss
BTN_DISABLED = (0.10, 0.09, 0.07, 1)  # ash

# Nav — almost invisible separation
NAV_BG = (0.05, 0.04, 0.03, 1)
NAV_ACTIVE = (0.58, 0.46, 0.16, 1)  # dim gold
NAV_INACTIVE = (0.24, 0.20, 0.16, 1)

# Separator
DIVIDER = (0.12, 0.10, 0.08, 1)  # dark rust line

# Rarity colors — also desaturated
RARITY_COMMON_CLR = (0.38, 0.34, 0.28, 1)
RARITY_UNCOMMON_CLR = (0.22, 0.38, 0.18, 1)
RARITY_RARE_CLR = (0.18, 0.30, 0.50, 1)
RARITY_EPIC_CLR = (0.38, 0.18, 0.42, 1)
RARITY_LEGENDARY_CLR = (0.58, 0.46, 0.16, 1)


def popup_color(rgba_tuple):
    """Convert a theme RGBA tuple to Kivy Popup background_color list format."""
    return list(rgba_tuple)[:3] + [1]
