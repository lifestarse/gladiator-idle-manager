"""
Grimy medieval color theme — Darkest Dungeon / Fear & Hunger inspired.
Muted, desaturated, oppressive. Iron and dried blood.
"""

# Background layers — deep, almost black, with brown undertone
BG_DARK = (0.05, 0.04, 0.04, 1)       # near-black with warmth
BG_CARD = (0.09, 0.07, 0.06, 1)       # dark leather brown
BG_CARD_ACTIVE = (0.12, 0.09, 0.06, 1)  # slightly lit card
BG_ELEVATED = (0.11, 0.09, 0.08, 1)   # raised surface

# Accent colors — muted, desaturated, like old paint and rust
ACCENT_GOLD = (0.72, 0.58, 0.22, 1)     # tarnished gold, not shiny
ACCENT_GREEN = (0.35, 0.52, 0.28, 1)    # sickly moss green
ACCENT_RED = (0.65, 0.15, 0.12, 1)      # dried blood
ACCENT_BLUE = (0.28, 0.38, 0.52, 1)     # cold steel blue
ACCENT_PURPLE = (0.42, 0.22, 0.45, 1)   # bruise purple
ACCENT_CYAN = (0.32, 0.48, 0.46, 1)     # verdigris / oxidized copper

# Text — parchment tones, not pure white
TEXT_PRIMARY = (0.78, 0.72, 0.62, 1)     # dirty parchment
TEXT_SECONDARY = (0.48, 0.42, 0.36, 1)   # faded ink
TEXT_MUTED = (0.30, 0.26, 0.22, 1)       # barely visible

# HP bars — blood and bile
HP_PLAYER = (0.45, 0.55, 0.25, 1)       # sickly yellow-green
HP_PLAYER_BG = (0.12, 0.14, 0.08, 1)
HP_ENEMY = (0.60, 0.12, 0.10, 1)        # dark blood
HP_ENEMY_BG = (0.18, 0.06, 0.05, 1)

# Buttons — worn, muted
BTN_FIGHT = (0.55, 0.12, 0.10, 1)       # blood button
BTN_FIGHT_GLOW = (0.60, 0.15, 0.12, 0.2)
BTN_PRIMARY = (0.25, 0.35, 0.48, 1)     # cold iron
BTN_SUCCESS = (0.28, 0.42, 0.22, 1)     # dark moss
BTN_DISABLED = (0.14, 0.12, 0.10, 1)    # charcoal

# Nav — almost invisible separation
NAV_BG = (0.06, 0.05, 0.04, 1)
NAV_ACTIVE = (0.72, 0.58, 0.22, 1)      # tarnished gold
NAV_INACTIVE = (0.30, 0.26, 0.22, 1)

# Separator
DIVIDER = (0.15, 0.12, 0.10, 1)         # dark rust line

# Rarity colors — also desaturated
RARITY_COMMON_CLR = (0.45, 0.40, 0.35, 1)
RARITY_UNCOMMON_CLR = (0.30, 0.50, 0.25, 1)
RARITY_RARE_CLR = (0.25, 0.40, 0.65, 1)
RARITY_EPIC_CLR = (0.50, 0.25, 0.55, 1)
RARITY_LEGENDARY_CLR = (0.72, 0.58, 0.22, 1)
