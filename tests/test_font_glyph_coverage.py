# Build: 2
"""Gate: every translated string must be drawable by the pixel font.

The app registers two fonts, both named by
game.localization._BUNDLED_FONT_FILES: PixelFont (PressStart2P) carries
headers, numbers, buttons, toasts and item/perk descriptions; BodyFont
(DroidSans) carries a handful of long paragraphs.
A codepoint the chosen font lacks is not substituted — Kivy draws a tofu
square, and nothing in the render path complains.

PressStart2P is the narrower of the two, and almost every string can end
up in it (AutoShrinkLabel — the toast, the stat-help popup, most cells —
defaults to font_name='PixelFont'), so its cmap is the bar for the whole
translation set. That is a real constraint, not an accident: the fonts
shipped in fonts/ are the contract, and a translator reaching for a
glyph outside it has to extend the font, not the string.

Shipped offenders this gate was written after: U+2212 MINUS SIGN in the
scripting editor's minus operators, U+26A0 WARNING SIGN on the save-failure
toasts, U+1F3C6 TROPHY on the T15 record toast, and U+200B ZERO WIDTH SPACE
left behind by machine translation. Every one rendered as a blank square on
device.

Scope: data/languages/*.json — both the UI files (xx.json) and the
content files (data_xx.json), whose descriptions render in PixelFont too.
String literals hardcoded in screen modules are out of scope here.
"""
import glob
import json
import os
import re

import pytest

_PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LANG_DIR = os.path.join(_PROJ_ROOT, "data", "languages")
_PIXEL_FONT = os.path.join(_PROJ_ROOT, "fonts", "PressStart2P-Regular.ttf")

# Invisible by definition: a cmap check cannot speak for them (the pixel
# font happens to map U+00AD, and would draw it as a visible hyphen), and
# they are never intentional in a translation.
_ZERO_WIDTH = {
    0x00AD,  # SOFT HYPHEN
    0x200B,  # ZERO WIDTH SPACE
    0x200C,  # ZERO WIDTH NON-JOINER
    0x200D,  # ZERO WIDTH JOINER
    0x200E,  # LEFT-TO-RIGHT MARK
    0x200F,  # RIGHT-TO-LEFT MARK
    0x2060,  # WORD JOINER
    0xFEFF,  # ZERO WIDTH NO-BREAK SPACE / BOM
}

# U+00A0 NBSP is deliberately allowed: French typography needs it before
# ! ? : and it is present in both fonts.


def _lang_files():
    return sorted(glob.glob(os.path.join(_LANG_DIR, "*.json")))


def _iter_strings(node, path=""):
    """Yield (json_path, string) for every string value in the tree."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_strings(value, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _iter_strings(value, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _pixel_font_cmap():
    pytest.importorskip(
        "fontTools", reason="fontTools not installed — glyph gate skipped")
    from fontTools.ttLib import TTFont
    return set(TTFont(_PIXEL_FONT).getBestCmap())


def test_all_translated_strings_use_only_glyphs_present_in_pixel_font():
    cmap = _pixel_font_cmap()
    offenders = {}
    for path in _lang_files():
        for key, value in _iter_strings(_load(path)):
            # Whitespace is layout, not a glyph: "\n" carries paragraph
            # breaks in the help bodies and never reaches the rasterizer.
            bad = {c for c in value if not c.isspace() and ord(c) not in cmap}
            if bad:
                offenders[f"{os.path.basename(path)}:{key}"] = sorted(
                    f"U+{ord(c):04X}" for c in bad)
    assert not offenders, (
        "translations use glyphs PressStart2P lacks — these render as tofu "
        f"squares on device: {offenders}"
    )


def test_no_zero_width_characters_in_translations():
    """Machine translation leaves these behind; they are invisible in an
    editor and, for U+200B, tofu in the pixel font."""
    offenders = {}
    for path in _lang_files():
        for key, value in _iter_strings(_load(path)):
            bad = {c for c in value if ord(c) in _ZERO_WIDTH}
            if bad:
                offenders[f"{os.path.basename(path)}:{key}"] = sorted(
                    f"U+{ord(c):04X}" for c in bad)
    assert not offenders, (
        f"zero-width / format characters in translated strings: {offenders}"
    )


def _norm(path):
    return os.path.normcase(os.path.abspath(path))


def test_gate_checks_the_font_the_app_actually_registers():
    """Keeps the gate honest if the pixel font is ever swapped out.

    Read from the same table the app registers, so a swap cannot leave the
    cmap check above speaking for the retired file.
    """
    from game.localization import _BUNDLED_FONT_FILES
    registered = _BUNDLED_FONT_FILES.get("PixelFont")
    assert registered and _norm(registered) == _norm(_PIXEL_FONT), (
        "PixelFont registration changed — point this gate at the new file: "
        f"{_BUNDLED_FONT_FILES}"
    )


def test_font_registration_has_a_single_source():
    """A second list of file names would win at import and lose on the first
    set_language(), leaving the gate pointed at a font the device stopped
    drawing — the exact split this gate exists to make impossible."""
    shared = os.path.join(_PROJ_ROOT, "game", "app", "_shared.py")
    with open(shared, "r", encoding="utf-8") as f:
        source = f.read()
    assert "_BUNDLED_FONT_FILES" in source, (
        "game/app/_shared.py must register from "
        "game.localization._BUNDLED_FONT_FILES"
    )
    stray = re.findall(r"LabelBase\.register\([^)]*\)", source)
    assert not stray, (
        "font file names are named once, in game.localization — "
        f"game/app/_shared.py registers its own: {stray}"
    )
