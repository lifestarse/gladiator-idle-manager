"""Generate PNG icon sprites — font glyphs + hand-drawn stat icons."""
import os
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansSymbols.ttf")
OUT_DIR = os.path.join(os.path.dirname(__file__), "icons")
os.makedirs(OUT_DIR, exist_ok=True)

SIZE = 64
FONT_SIZE = 48

# === Font-based icons (nav + action) ===

ICONS = {
    "ic_pit":       "\u2694",   # crossed swords
    "ic_squad":     "\u2694",   # crossed swords (squad)
    "ic_anvil":     "\u2692",   # hammer and pick (anvil)
    "ic_hunts":     "\u2316",   # position indicator (hunts)
    "ic_lore":      "\u2605",   # black star
    "ic_more":      "\u25CF",   # black circle
    "ic_play":      "\u25B6",   # right-pointing triangle
    "ic_boss":      "\u25C6",   # black diamond
    "ic_next":      "\u25B7",   # white right-pointing triangle
    "ic_skip":      "\u25B6",   # reuse play
    "ic_up":        "\u25B2",   # up triangle
    "ic_down":      "\u25BC",   # down triangle
    "ic_star":      "\u2605",   # black star
    "ic_diamond":   "\u25C6",   # black diamond
    "ic_square":    "\u25A0",   # black square
    "ic_circle":    "\u25CB",   # white circle
    "ic_expand":    "\u25BC",   # down triangle
    "ic_collapse":  "\u25B6",   # right triangle
    "ic_four_star": "\u2726",   # four-pointed star
}

COLORS = {
    "ic_pit":       (255, 200, 60, 255),
    "ic_squad":     (200, 200, 220, 255),
    "ic_anvil":     (255, 140, 50, 255),
    "ic_hunts":     (100, 200, 100, 255),
    "ic_lore":      (255, 220, 80, 255),
    "ic_more":      (180, 180, 200, 255),
    "ic_play":      (100, 255, 100, 255),
    "ic_boss":      (255, 80, 80, 255),
    "ic_next":      (200, 200, 220, 255),
    "ic_skip":      (255, 220, 80, 255),
    "ic_up":        (100, 200, 255, 255),
    "ic_down":      (100, 200, 255, 255),
    "ic_star":      (255, 220, 80, 255),
    "ic_diamond":   (150, 120, 255, 255),
    "ic_square":    (200, 200, 220, 255),
    "ic_circle":    (180, 220, 255, 255),
    "ic_expand":    (200, 200, 220, 255),
    "ic_collapse":  (200, 200, 220, 255),
    "ic_four_star": (255, 200, 60, 255),
}

font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

for name, char in ICONS.items():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = COLORS.get(name, (255, 255, 255, 255))
    bbox = draw.textbbox((0, 0), char, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (SIZE - tw) // 2 - bbox[0]
    y = (SIZE - th) // 2 - bbox[1]
    draw.text((x, y), char, fill=color, font=font)
    if img.getbbox() is None:
        print(f"WARNING: {name} — fallback circle")
        draw.ellipse([8, 8, SIZE-8, SIZE-8], fill=color)
    path = os.path.join(OUT_DIR, f"{name}.png")
    img.save(path, "PNG")
    print(f"OK: {name}.png")


# === Hand-drawn stat & equipment icons ===

def draw_sword(draw, color, size=64):
    """Sword icon — diagonal blade with crossguard."""
    s = size
    # Blade (thick diagonal line)
    draw.line([(s*0.25, s*0.75), (s*0.75, s*0.15)], fill=color, width=4)
    # Crossguard
    draw.line([(s*0.35, s*0.45), (s*0.65, s*0.55)], fill=color, width=5)
    # Pommel
    draw.ellipse([s*0.18, s*0.72, s*0.32, s*0.86], fill=color)


def draw_lightning(draw, color, size=64):
    """Lightning bolt icon."""
    s = size
    pts = [
        (s*0.55, s*0.08),
        (s*0.30, s*0.45),
        (s*0.48, s*0.45),
        (s*0.38, s*0.92),
        (s*0.72, s*0.38),
        (s*0.52, s*0.38),
    ]
    draw.polygon(pts, fill=color)


def draw_heart(draw, color, size=64):
    """Heart icon."""
    s = size
    # Two circles for the top bumps
    r = s * 0.18
    draw.ellipse([s*0.14, s*0.18, s*0.14+r*2, s*0.18+r*2], fill=color)
    draw.ellipse([s*0.50, s*0.18, s*0.50+r*2, s*0.18+r*2], fill=color)
    # Triangle for the bottom
    draw.polygon([
        (s*0.14, s*0.35),
        (s*0.86, s*0.35),
        (s*0.50, s*0.85),
    ], fill=color)


def draw_shield(draw, color, size=64):
    """Shield icon — rounded top, pointed bottom."""
    s = size
    draw.rounded_rectangle(
        [s*0.18, s*0.10, s*0.82, s*0.55],
        radius=int(s*0.12), fill=color,
    )
    draw.polygon([
        (s*0.18, s*0.50),
        (s*0.82, s*0.50),
        (s*0.50, s*0.90),
    ], fill=color)


def draw_ring(draw, color, size=64):
    """Ring/gem icon — circle with diamond on top."""
    s = size
    # Ring band
    draw.ellipse([s*0.18, s*0.30, s*0.82, s*0.85], outline=color, width=5)
    # Gem on top
    draw.regular_polygon(
        (s*0.50, s*0.25, s*0.14),
        n_sides=4, fill=color, rotation=45,
    )


def draw_coin(draw, color, size=64):
    """Gold coin icon — circle with inner ring."""
    s = size
    draw.ellipse([s*0.12, s*0.12, s*0.88, s*0.88], fill=color)
    darker = (int(color[0]*0.7), int(color[1]*0.7), int(color[2]*0.7), 255)
    draw.ellipse([s*0.22, s*0.22, s*0.78, s*0.78], outline=darker, width=3)
    # G letter in center
    draw.text((s*0.35, s*0.25), "G", fill=darker,
              font=ImageFont.truetype(FONT_PATH, int(s*0.45)))


def draw_gem(draw, color, size=64):
    """Diamond gem icon — hexagonal cut gem."""
    s = size
    # Top facet
    draw.polygon([
        (s*0.30, s*0.35), (s*0.50, s*0.10), (s*0.70, s*0.35),
    ], fill=color)
    # Bottom facet
    lighter = (min(255,int(color[0]*1.3)), min(255,int(color[1]*1.3)),
               min(255,int(color[2]*1.3)), 255)
    draw.polygon([
        (s*0.20, s*0.35), (s*0.80, s*0.35), (s*0.50, s*0.90),
    ], fill=lighter)
    # Top bar
    draw.polygon([
        (s*0.20, s*0.35), (s*0.30, s*0.35), (s*0.50, s*0.10),
    ], fill=color)
    draw.polygon([
        (s*0.70, s*0.35), (s*0.80, s*0.35), (s*0.50, s*0.10),
    ], fill=color)


def draw_trophy(draw, color, size=64):
    """Trophy/cup icon."""
    s = size
    # Cup body
    draw.rounded_rectangle(
        [s*0.22, s*0.10, s*0.78, s*0.55],
        radius=int(s*0.10), fill=color,
    )
    # Handles
    draw.arc([s*0.05, s*0.15, s*0.28, s*0.45], 90, 270, fill=color, width=4)
    draw.arc([s*0.72, s*0.15, s*0.95, s*0.45], 270, 90, fill=color, width=4)
    # Stem
    draw.rectangle([s*0.42, s*0.55, s*0.58, s*0.72], fill=color)
    # Base
    draw.rounded_rectangle(
        [s*0.25, s*0.72, s*0.75, s*0.85],
        radius=int(s*0.04), fill=color,
    )


DRAWN_ICONS = {
    "ic_str":       (draw_sword,     (255, 80, 80, 255)),
    "ic_agi":       (draw_lightning,  (100, 255, 100, 255)),
    "ic_vit":       (draw_heart,     (100, 150, 255, 255)),
    "ic_hp":        (draw_heart,     (255, 60, 60, 255)),
    "ic_weapon":    (draw_sword,     (255, 160, 50, 255)),
    "ic_armor":     (draw_shield,    (100, 150, 255, 255)),
    "ic_accessory": (draw_ring,      (180, 100, 255, 255)),
    "ic_gold":      (draw_coin,      (255, 200, 50, 255)),
    "ic_gem":       (draw_gem,       (100, 200, 255, 255)),
    "ic_trophy":    (draw_trophy,    (255, 200, 50, 255)),
}

for name, (draw_fn, color) in DRAWN_ICONS.items():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_fn(draw, color, SIZE)
    path = os.path.join(OUT_DIR, f"{name}.png")
    img.save(path, "PNG")
    print(f"OK: {name}.png (drawn)")

print(f"\nDone! {len(ICONS) + len(DRAWN_ICONS)} icons generated in {OUT_DIR}")


# === App icon (512x512 for Google Play + buildozer) ===

def generate_app_icon():
    """Generate app launcher icon — gladiator helmet silhouette on dark bg."""
    sizes = [512, 192, 144, 96, 72, 48]
    for sz in sizes:
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        s = sz

        # Dark background circle
        draw.ellipse([0, 0, s, s], fill=(13, 13, 18, 255))

        # Gold border
        draw.ellipse([2, 2, s-2, s-2], outline=(255, 200, 60, 255), width=max(2, s//64))

        # Gladiator helmet (stylized)
        gold = (255, 200, 60, 255)
        dark_gold = (180, 140, 40, 255)

        # Helmet dome
        cx, cy = s * 0.5, s * 0.35
        rx, ry = s * 0.28, s * 0.22
        draw.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], fill=gold)

        # Face plate / visor
        draw.rectangle([s*0.28, s*0.38, s*0.72, s*0.62], fill=gold)

        # Eye slit
        draw.rectangle([s*0.32, s*0.44, s*0.68, s*0.50], fill=(13, 13, 18, 255))

        # Nose guard (vertical line)
        w = max(2, s//32)
        draw.rectangle([s*0.48, s*0.38, s*0.52, s*0.58], fill=dark_gold)

        # Crest (mohawk plume on top)
        crest_pts = [
            (s*0.45, s*0.18),
            (s*0.50, s*0.06),
            (s*0.55, s*0.18),
        ]
        draw.polygon(crest_pts, fill=(255, 80, 60, 255))

        # Cheek guards
        draw.polygon([
            (s*0.22, s*0.45),
            (s*0.28, s*0.38),
            (s*0.28, s*0.62),
            (s*0.22, s*0.58),
        ], fill=dark_gold)
        draw.polygon([
            (s*0.78, s*0.45),
            (s*0.72, s*0.38),
            (s*0.72, s*0.62),
            (s*0.78, s*0.58),
        ], fill=dark_gold)

        # Crossed swords below
        sword_color = (200, 200, 220, 255)
        lw = max(2, s//48)
        draw.line([(s*0.25, s*0.90), (s*0.75, s*0.65)], fill=sword_color, width=lw)
        draw.line([(s*0.75, s*0.90), (s*0.25, s*0.65)], fill=sword_color, width=lw)

        fname = f"icon_{sz}.png"
        path = os.path.join(OUT_DIR, fname)
        img.save(path, "PNG")
        print(f"OK: {fname} (app icon)")


generate_app_icon()
print("App icons generated!")


# === Presplash screen (720x1280 portrait, icon centered on dark bg) ===

def generate_presplash():
    """Generate presplash.png — app icon centered on dark background."""
    W, H = 720, 1280
    BG = (13, 13, 18, 255)
    img = Image.new("RGBA", (W, H), BG)

    # Load the 512 icon and paste it centered
    icon_path = os.path.join(OUT_DIR, "icon_512.png")
    icon = Image.open(icon_path).convert("RGBA")
    icon = icon.resize((256, 256), Image.LANCZOS)
    x = (W - 256) // 2
    y = (H - 256) // 2
    img.paste(icon, (x, y), icon)

    path = os.path.join(os.path.dirname(__file__), "presplash.png")
    img.save(path, "PNG")
    print(f"OK: presplash.png ({W}x{H})")


generate_presplash()
print("Presplash generated!")
