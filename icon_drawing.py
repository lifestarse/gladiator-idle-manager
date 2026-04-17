# Build: 1
"""Primitive icon drawing functions (split from generate_icons.py)."""
import os
from PIL import Image, ImageDraw, ImageFont

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

