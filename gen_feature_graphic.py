"""Generate a 1024x500 feature graphic for Google Play Store."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import os

W, H = 1024, 500

img = Image.new("RGB", (W, H), "#1a0000")
draw = ImageDraw.Draw(img)

# Dark red radial gradient background
cx, cy = W // 2, H // 2
max_dist = math.sqrt(cx**2 + cy**2)
for y in range(H):
    for x in range(W):
        dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        t = dist / max_dist
        r = int(140 * (1 - t) + 20 * t)
        g = int(10 * (1 - t) + 0 * t)
        b = int(10 * (1 - t) + 0 * t)
        img.putpixel((x, y), (r, g, b))

draw = ImageDraw.Draw(img)

# Subtle diagonal lines pattern overlay
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
for i in range(-H, W + H, 40):
    odraw.line([(i, 0), (i + H, H)], fill=(255, 255, 255, 8), width=1)
img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
draw = ImageDraw.Draw(img)

# Draw decorative arena arc at bottom
for i in range(3):
    offset = i * 4
    alpha_color = (200 + i * 20, 160 + i * 20, 50, 30 + i * 10)
    arc_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    arc_draw = ImageDraw.Draw(arc_overlay)
    arc_draw.ellipse(
        [W // 2 - 600 - offset, H - 80 - offset, W // 2 + 600 + offset, H + 400 + offset],
        outline=alpha_color,
        width=2,
    )
    img = Image.alpha_composite(img.convert("RGBA"), arc_overlay).convert("RGB")

draw = ImageDraw.Draw(img)

# Load and place the icon
icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon_512.png")
icon = Image.open(icon_path).convert("RGBA")

# Create a glow effect behind the icon
icon_size = 220
icon_resized = icon.resize((icon_size, icon_size), Image.LANCZOS)

# Glow
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
glow_draw = ImageDraw.Draw(glow)
glow_cx, glow_cy = W // 2 - 160, H // 2
for radius in range(150, 0, -2):
    alpha = int(40 * (1 - radius / 150))
    glow_draw.ellipse(
        [glow_cx - radius, glow_cy - radius, glow_cx + radius, glow_cy + radius],
        fill=(220, 170, 50, alpha),
    )
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

# Paste icon
icon_x = W // 2 - 160 - icon_size // 2
icon_y = H // 2 - icon_size // 2
img_rgba = img.convert("RGBA")
img_rgba.paste(icon_resized, (icon_x, icon_y), icon_resized)
img = img_rgba.convert("RGB")
draw = ImageDraw.Draw(img)

# Text - try to use a bold font
text_x = W // 2 + 60

# Try system fonts
font_paths = [
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

title_font = None
sub_font = None
for fp in font_paths:
    if os.path.exists(fp):
        title_font = ImageFont.truetype(fp, 52)
        sub_font = ImageFont.truetype(fp, 24)
        break

if title_font is None:
    title_font = ImageFont.load_default()
    sub_font = ImageFont.load_default()

# Title: "GLADIATOR" and "IDLE MANAGER" on two lines
title1 = "GLADIATOR"
title2 = "IDLE MANAGER"

# Draw text shadow
shadow_offset = 3
draw.text((text_x + shadow_offset, 140 + shadow_offset), title1, fill=(0, 0, 0), font=title_font)
draw.text((text_x + shadow_offset, 200 + shadow_offset), title2, fill=(0, 0, 0), font=title_font)

# Gold gradient text effect - main title
draw.text((text_x, 140), title1, fill=(255, 215, 80), font=title_font)
draw.text((text_x, 200), title2, fill=(230, 190, 60), font=title_font)

# Tagline
tagline = "Train. Fight. Conquer."
draw.text((text_x + shadow_offset, 280 + shadow_offset), tagline, fill=(0, 0, 0), font=sub_font)
draw.text((text_x, 280), tagline, fill=(200, 180, 150), font=sub_font)

# Decorative line under tagline
draw.line([(text_x, 315), (text_x + 280, 315)], fill=(220, 170, 50, 128), width=2)

# Small crossed swords decorative elements
sword_y = 340
draw.line([(text_x + 120, sword_y), (text_x + 160, sword_y + 20)], fill=(180, 160, 120), width=2)
draw.line([(text_x + 160, sword_y), (text_x + 120, sword_y + 20)], fill=(180, 160, 120), width=2)

out_path = os.path.join(os.path.dirname(__file__), "feature_graphic.png")
img.save(out_path, "PNG")
print(f"Saved: {out_path}")
print(f"Size: {img.size}")
