# Build: 5
"""
Pixel art RPG color theme — SNES-era inspired.
Rich saturated accents, warm indigo backgrounds, cream text.
"""

# Background layers — deep indigo, not pure black
BG_DARK = (0.08, 0.05, 0.13, 1)         # deep indigo-black
BG_CARD = (0.13, 0.09, 0.20, 1)         # dark violet-brown card
BG_CARD_ACTIVE = (0.18, 0.12, 0.26, 1)  # lit card
BG_ELEVATED = (0.16, 0.11, 0.23, 1)     # raised surface

# Accent colors — saturated, SNES-vivid
ACCENT_GOLD = (0.93, 0.78, 0.18, 1)     # bright gold
ACCENT_GREEN = (0.20, 0.70, 0.30, 1)    # emerald green
ACCENT_RED = (0.85, 0.15, 0.15, 1)      # blood crimson
ACCENT_BLUE = (0.20, 0.45, 0.85, 1)     # royal blue
ACCENT_PURPLE = (0.60, 0.25, 0.80, 1)   # vivid purple
ACCENT_CYAN = (0.20, 0.75, 0.80, 1)     # teal/cyan

# Text — warm cream, high contrast
TEXT_PRIMARY = (0.93, 0.90, 0.82, 1)     # cream white
TEXT_SECONDARY = (0.62, 0.56, 0.50, 1)   # muted tan
TEXT_MUTED = (0.35, 0.30, 0.28, 1)       # dim brown

# HP bars — vivid
HP_PLAYER = (0.15, 0.72, 0.25, 1)       # bright green
HP_PLAYER_BG = (0.06, 0.18, 0.08, 1)    # dark green bg
HP_ENEMY = (0.82, 0.12, 0.12, 1)        # bright red
HP_ENEMY_BG = (0.22, 0.05, 0.05, 1)     # dark red bg

# Buttons
BTN_FIGHT = (0.75, 0.12, 0.12, 1)       # red fight
BTN_FIGHT_GLOW = (0.85, 0.15, 0.15, 0.20)
BTN_PRIMARY = (0.18, 0.30, 0.58, 1)     # blue
BTN_SUCCESS = (0.15, 0.55, 0.20, 1)     # green
BTN_DISABLED = (0.14, 0.12, 0.18, 1)    # muted indigo

# Nav
NAV_BG = (0.06, 0.04, 0.10, 1)
NAV_ACTIVE = (0.93, 0.78, 0.18, 1)      # gold
NAV_INACTIVE = (0.40, 0.35, 0.30, 1)

# Separator
DIVIDER = (0.22, 0.18, 0.30, 1)         # purple-tinted line

# Rarity colors — saturated RPG rarity scheme
RARITY_COMMON_CLR = (0.55, 0.55, 0.50, 1)     # gray
RARITY_UNCOMMON_CLR = (0.20, 0.72, 0.30, 1)   # green
RARITY_RARE_CLR = (0.25, 0.50, 0.90, 1)       # blue
RARITY_EPIC_CLR = (0.65, 0.25, 0.85, 1)       # purple
RARITY_LEGENDARY_CLR = (0.95, 0.75, 0.15, 1)  # gold


def popup_color(rgba_tuple):
    """Convert a theme RGBA tuple to Kivy Popup background_color list format."""
    return list(rgba_tuple)[:3] + [1]
