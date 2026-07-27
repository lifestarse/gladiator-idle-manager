# Build: 1
"""Render a PassiveSpec into the player-facing rule line.

Numbers live here and only here. They come from the spec's params and are
substituted into an en.json template — never written into the translated prose
in data/languages/data_XX.json.

That split is not stylistic. tests/test_i18n_data_quality.py::
test_numbers_survive_translation freezes every digit run in a base string into
all eight translations, so a magnitude baked into flavour text turns a one-line
rebalance into nine file edits — the trap data/mutators.json is already in and
data/enchantments.json avoids by keeping its descriptions digit-free with the
values in sibling numeric fields. Templates here inherit the enchantment
pattern.
"""
from game.localization import t

from ._shared import *  # noqa: F401,F403


def fmt_amount(value):
    """Format a param for display: drop a pointless trailing ".0".

    2% reads as "2", 2.5% as "2.5". `int` when it is one, because "Heals for
    2.0% of damage" looks like a bug report waiting to happen.
    """
    rounded = round(float(value), 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def render_args(spec):
    """Template kwargs for a spec, per its kind's declared l10n_args."""
    return {kwarg: fmt_amount(spec.params[param] * mult)
            for kwarg, param, mult in spec.kind_def.l10n_args}


def render(spec):
    """The localized rule line for one passive.

    `t()` returns the key itself on a miss and swallows format errors
    (game/localization.py), so a missing template shows up as a visible
    "passive_<kind>" rather than an exception — ugly, and caught by
    tests/test_item_passives.py, but never a crash in a player's hands.
    """
    return t(spec.kind_def.l10n, **render_args(spec))


def render_item(item):
    """Rule lines for every passive on `item`, in `#n` order. [] if none."""
    from ._registry import COMPILED_PASSIVES

    return [render(spec)
            for spec in COMPILED_PASSIVES.get(item.get("id", ""), ())]


def passive_count(item):
    """How many passives `item` carries — for badges and sort keys."""
    from ._registry import COMPILED_PASSIVES

    return len(COMPILED_PASSIVES.get(item.get("id", ""), ()))


# U+2605 BLACK STAR. Verified present in fonts/PressStart2P-Regular.ttf, which
# game/app/_shared.py:55 registers as PixelFont — the default for every label
# in the item grids. ◆ and ⚠ are NOT in it (only in NotoSansSymbols) and would
# render as tofu, the same trap already documented for ✓/✗ at
# game/screens/scripts/blocks.py:97.
#
# A glyph rather than a word because this sits in a grid row beside the name,
# the upgrade level and the enchantment, where there is no room for a term that
# has to work in nine languages. The detail view spells it out in full.
PASSIVE_MARK = "★"


def passive_marker(item):
    """Grid marker for an item's passives: one star each, "" for none."""
    return PASSIVE_MARK * passive_count(item)
