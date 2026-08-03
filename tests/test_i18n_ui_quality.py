# Build: 2
"""Acceptance gate for the CONTENT of data/languages/<lang>.json — the UI strings.

test_i18n_data_quality.py guards data_XX.json (enemies, lore, injuries). This
module guards the other file: the 830 keys behind ``t()``. They had no gate at
all, which is how commit 4db9012 shipped raw ``deep_translator.GoogleTranslator``
output for seven languages and nobody noticed for four weeks:

* "Auto-train: ON" -> "Автопоїзд" / "Pociąg automatyczny" — a railway train;
* "{n} fighters ready" -> "{n} винищувачі" / "{n} myśliwce" — fighter aircraft;
* "-{dmg}HP" -> "-{dmg}KM" — horsepower;
* "{name} +{diamonds} dia." -> "+{diamonds} Durchm." — diameter;
* "call" -> "дзвонити" / "Anruf" — a telephone call.

Two kinds of rule live here:

* MECHANICAL (placeholders, BBCode, stat abbreviations, coverage, script,
  uppercase, length) — enforced for every language, because breaking them is a
  bug in any language and half of them break formatting at runtime.
* GLOSSARY (forbidden renderings) — enforced only for languages that declare a
  column in scripts/i18n_glossary.json. A language that has not been
  re-translated yet declares nothing and is not checked, so this gate can land
  before the translation work finishes instead of after.

Failures print the offending keys, not just a count: the next pass has to know
what to fix.
"""
import json
import re
from collections import Counter
from pathlib import Path

import pytest

# Nested-key addressing comes from the game itself — enchant_names and
# help_sections are the two non-flat keys, and the gate must address their
# leaves exactly the way localization, the translation tool and remote patches
# do, or a rule could pass here and fail on a device.
from game.localization import flatten as _flat

# One implementation of scaffolding detection, shared with the merge-time
# quarantine in the tool — the gate and the quarantine must not drift apart.
from scripts.i18n_tool import find_scaffolding

ROOT = Path(__file__).resolve().parents[1]
LANG_DIR = ROOT / "data" / "languages"
GLOSSARY_PATH = ROOT / "scripts" / "i18n_glossary.json"

SOURCE = "en"
MASTER = "ru"
TARGETS = ("ru", "uk", "de", "es", "fr", "it", "pt", "pl")
CYRILLIC_LANGS = ("ru", "uk")

PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]*\}")
BBCODE = re.compile(r"\[/?[a-z]+(?:=[^\]]+)?\]")
# Stat abbreviations are identical in every language by design (see the
# glossary "stats" row). As whole uppercase words they are trivially checkable,
# and losing one means the string now says horsepower or diameter.
STAT_TOKEN = re.compile(r"\b(?:ATK|DEF|HP|STR|AGI|VIT)\b")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
# Russian-only letters: a Ukrainian string containing them was written by
# something that did not know which language it was writing.
RU_ONLY = re.compile(r"[ыэъёЫЭЪЁ]")

# Below this length a translation legitimately equals the English ("ATK", "OK",
# "{n}", "2x"), so the leak rule would be pure noise.
MIN_LEAK_LEN = 12
# Uppercase strings are buttons, tabs and titles in a fixed-width pixel frame.
# Measured against ru, which is the language the layout was designed for.
MAX_UPPER_RATIO = 1.5
# Prose has more room, but 2.5x means the translator wrote its own sentence.
MIN_RATIO, MAX_RATIO = 0.5, 2.5
MIN_RATIO_LEN = 25
SAMPLES = 6


def _lang(code):
    with open(LANG_DIR / f"{code}.json", encoding="utf-8") as fh:
        return _flat(json.load(fh))


def _glossary():
    if not GLOSSARY_PATH.exists():
        return {}
    with open(GLOSSARY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


SRC = _lang(SOURCE)
MST = _lang(MASTER)
GLOSSARY = _glossary()
# A language is held to the content rules once its terminology is decided.
# Until then it is still carrying the 2026-07-01 machine output and failing it
# on wording would only produce noise that nobody can act on; the mechanical
# rules below apply to it regardless, because those break at runtime.
REVIEWED = {code for code in TARGETS
            if any(isinstance(spec, dict) and spec.get(code)
                   for spec in GLOSSARY.get("terms", {}).values())}


def _report(bad, rule, lang):
    shown = "\n".join(f"    {key}: {detail}" for key, detail in bad[:SAMPLES])
    more = f"\n    ... and {len(bad) - SAMPLES} more" if len(bad) > SAMPLES else ""
    return f"{lang}: {len(bad)} {rule} failures\n{shown}{more}"


def _require_reviewed(lang):
    if lang not in REVIEWED:
        pytest.skip(f"{lang} has no glossary column yet — still machine output "
                    f"from {GLOSSARY.get('_gt_commit', '4db9012')}, "
                    f"scheduled for a later translation pass")


def _prose(text):
    """The text minus placeholders and markup — what a human actually reads."""
    return BBCODE.sub("", PLACEHOLDER.sub("", text))


@pytest.fixture(scope="module", params=TARGETS)
def lang(request):
    return request.param


def test_coverage(lang):
    """Every English leaf exists in the target, non-empty, same shape."""
    target = _lang(lang)
    missing = [(key, "absent") for key in SRC if key not in target]
    empty = [(key, "empty") for key in SRC if not target.get(key, "x").strip()]
    bad = missing + empty
    assert not bad, _report(bad, "coverage", lang)


def test_placeholders(lang):
    """{name}/{n}/{dmg} survive intact — a lost brace is a KeyError at runtime."""
    target = _lang(lang)
    bad = []
    for key, source in SRC.items():
        want = sorted(PLACEHOLDER.findall(source))
        got = sorted(PLACEHOLDER.findall(target.get(key, "")))
        if want != got:
            bad.append((key, f"expected {want}, got {got}"))
    assert not bad, _report(bad, "placeholder", lang)


def test_bbcode(lang):
    """[b]/[color=ffd040] markup survives — Kivy renders a broken tag literally."""
    target = _lang(lang)
    bad = []
    for key, source in SRC.items():
        want = sorted(BBCODE.findall(source))
        got = sorted(BBCODE.findall(target.get(key, "")))
        if want != got:
            bad.append((key, f"expected {want}, got {got}"))
    assert not bad, _report(bad, "bbcode", lang)


def test_stat_abbreviations(lang):
    """A stat abbreviation both sources agree on may not go missing.

    pl turned "-{dmg}HP" into "-{dmg}KM" (horsepower) and de turned the
    "dia." of diamonds into "Durchm." (diameter). Only tokens present in BOTH
    ru and en are required: where the two disagree — en writes "STR", ru writes
    "Сила" — either choice is legitimate, and demanding one of them would flag
    style rather than damage. Extra tokens are allowed for the same reason.
    """
    if lang == MASTER:
        pytest.skip("master language defines the convention")
    _require_reviewed(lang)
    target = _lang(lang)
    bad = []
    for key, master in MST.items():
        agreed = Counter(STAT_TOKEN.findall(master))
        agreed &= Counter(STAT_TOKEN.findall(SRC.get(key, "")))
        lost = agreed - Counter(STAT_TOKEN.findall(target.get(key, "")))
        if lost:
            bad.append((key, f"lost {sorted(lost.elements())} from "
                             f"{target.get(key, '')!r}"))
    assert not bad, _report(bad, "stat abbreviation", lang)


def test_mixed_alphabet(lang):
    """No word may mix Cyrillic and Latin letters.

    pl shipped "Złote monety падаją" — three Cyrillic letters spliced into a
    Polish word, which renders as the wrong glyphs or as tofu depending on the
    font atlas.
    """
    target = _lang(lang)
    bad = [(key, repr(text[:60])) for key, text in target.items()
           if re.search(r"[Ѐ-ӿ][A-Za-z]|[A-Za-z][Ѐ-ӿ]", text)]
    assert not bad, _report(bad, "mixed-alphabet", lang)


def test_no_agent_scaffolding_residue(lang):
    """LLM wrapper artifacts must never reach a player-visible string.

    Mechanical, so it applies to every language: a markdown fence or an
    envelope tag renders verbatim on the device regardless of how far the
    language's re-translation has progressed. Detection is shared with the
    merge-time quarantine in scripts/i18n_tool.py.
    """
    target = _lang(lang)
    bad = [(key, f"{reason} in {text[:50]!r}")
           for key, text in target.items()
           for reason in (find_scaffolding(text),) if reason]
    assert not bad, _report(bad, "scaffolding", lang)


def test_no_english_leak(lang):
    """A long string identical to English was never translated at all."""
    _require_reviewed(lang)
    target = _lang(lang)
    bad = [
        (key, repr(source[:60]))
        for key, source in SRC.items()
        if len(source) >= MIN_LEAK_LEN
        and target.get(key, "") == source
        # Strings the master language also leaves in English (item names,
        # "2x GOLD: {t}s") are deliberate, not a gap.
        and MST.get(key) != source
    ]
    assert not bad, _report(bad, "english-leak", lang)


def test_uppercase_preserved(lang):
    """Buttons and tabs written in caps stay in caps.

    Referenced to ru: en writes "HP %" in caps only because of the
    abbreviation, while ru writes "Здоровье %" — that is not a lost button.
    """
    if lang == MASTER:
        pytest.skip("master language defines the casing")
    _require_reviewed(lang)
    target = _lang(lang)
    bad = [
        (key, repr(target.get(key, "")))
        for key, master in MST.items()
        if master.isupper() and len(master) > 2
        and not target.get(key, "").isupper()
    ]
    assert not bad, _report(bad, "uppercase", lang)


def test_length_band(lang):
    """Text far longer or shorter than the Russian original overflows or omits."""
    if lang == MASTER:
        pytest.skip("master language is the reference")
    _require_reviewed(lang)
    target = _lang(lang)
    bad = []
    for key, master in MST.items():
        text = target.get(key, "")
        if not isinstance(master, str) or len(master) < MIN_RATIO_LEN or not text:
            continue
        ratio = len(text) / len(master)
        if not MIN_RATIO <= ratio <= MAX_RATIO:
            bad.append((key, f"{ratio:.2f}x of ru ({len(text)} vs {len(master)})"))
    assert not bad, _report(bad, "length-band", lang)


def test_uppercase_length_band(lang):
    """Caps strings sit in fixed-width pixel frames — they cannot grow freely."""
    if lang == MASTER:
        pytest.skip("master language is the reference")
    _require_reviewed(lang)
    target = _lang(lang)
    bad = []
    for key, master in MST.items():
        text = target.get(key, "")
        if not master.isupper() or len(master) < 4 or not text:
            continue
        ratio = len(text) / len(master)
        if ratio > MAX_UPPER_RATIO:
            bad.append((key, f"{ratio:.2f}x of ru {master!r} -> {text!r}"))
    assert not bad, _report(bad, "uppercase-length", lang)


def test_script(lang):
    """Cyrillic languages stay Cyrillic; Latin ones carry no Cyrillic at all."""
    target = _lang(lang)
    bad = []
    for key, text in target.items():
        if lang in CYRILLIC_LANGS:
            # Only demand Cyrillic where the master has real prose to convert:
            # "{name}: {ench}!" and "ATK" have no words in them, and the
            # placeholder names are not text the player reads.
            master = _prose(MST.get(key, ""))
            if len(master) >= MIN_LEAK_LEN and not CYRILLIC.search(text):
                bad.append((key, f"no Cyrillic in {text!r}"))
        elif CYRILLIC.search(text):
            bad.append((key, f"Cyrillic in {text!r}"))
    assert not bad, _report(bad, "script", lang)


def test_ukrainian_orthography():
    """ы/э/ъ/ё do not exist in Ukrainian — their presence means Russian text."""
    target = _lang("uk")
    bad = [(key, repr(text)) for key, text in target.items() if RU_ONLY.search(text)]
    assert not bad, _report(bad, "uk-orthography", "uk")


def test_forbidden_renderings(lang):
    """Known GoogleTranslate false friends must not come back.

    Read from the glossary so a rule and its reason live in one place, and so
    switching a language on is a data edit rather than a code edit.
    """
    forbidden = GLOSSARY.get("forbidden", {}).get(lang)
    if not forbidden:
        pytest.skip(f"{lang} declares no forbidden renderings yet")
    target = _lang(lang)
    bad = []
    for stem, why in forbidden.items():
        pattern = re.compile(rf"\b{re.escape(stem)}", re.IGNORECASE)
        for key, text in target.items():
            if pattern.search(text):
                bad.append((key, f"{stem!r} in {text[:50]!r} — {why}"))
    assert not bad, _report(bad, "forbidden-rendering", lang)


def test_glossary_covers_every_target_language():
    """Guard against a language quietly shipping with no terminology at all."""
    terms = GLOSSARY.get("terms", {})
    assert terms, "glossary has no terms"
    covered = {code for code in TARGETS
               if any(isinstance(spec, dict) and spec.get(code)
                      for spec in terms.values())}
    # Not an assertion on the full set yet — uk is the pilot and the remaining
    # languages are translated in a later pass. This test exists to make that
    # backlog visible in the test output rather than in someone's memory.
    pending = sorted(set(TARGETS) - covered - {MASTER})
    if pending:
        pytest.skip(f"glossary columns still missing for: {', '.join(pending)}")
