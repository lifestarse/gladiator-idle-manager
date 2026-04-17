"""Generate PNG icon sprites — font glyphs + hand-drawn stat icons."""
import os
from PIL import Image, ImageDraw, ImageFont
from icon_drawing import (draw_sword, draw_lightning, draw_heart, draw_shield, draw_ring, draw_coin, draw_gem, draw_trophy)

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
