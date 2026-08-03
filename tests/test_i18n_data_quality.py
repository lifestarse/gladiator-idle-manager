# Build: 8
"""Acceptance gate for the CONTENT of data/languages/data_XX.json.

test_data_translations.py proves the overlay pipeline works (right file, right
field, reaches the UI). This module proves the text is an actual translation,
because three generator passes shipped fakes that the pipeline happily
rendered:

* verbatim English copies;
* a localized prefix glued onto the untouched original —
  "Опасный противник арены: A former soldier stripped of rank...";
* invented prose unrelated to the source — lore/the_iron_frontier arrived as
  82 Russian chars ("outer borders of the empire") for 565 English ones about
  scorched earth and twisted metal.

Every rule is measured over every entry of every section in every language on
purpose: spot-checking index [0] and the first five ids is exactly what let the
earlier fakes through. Failures print counts and sample ids so the next pass
knows what to fix.
"""
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pytest

# One implementation of scaffolding detection, shared with the merge-time
# quarantine in the tool — the gate and the quarantine must not drift apart.
from scripts.i18n_tool import find_scaffolding

ROOT = Path(__file__).resolve().parents[1]
LANG_DIR = ROOT / "data" / "languages"
LANGS = ("ru", "uk", "de", "es", "fr", "it", "pt", "pl")
CYRILLIC_LANGS = ("ru", "uk")

# section -> (base file, base top-level key, translated fields)
SECTIONS = {
    "enemies": ("enemies.json", "enemies", ("description",)),
    "injuries": ("injuries.json", "injuries", ("description",)),
    "lore": ("lore.json", "entries", ("title", "text")),
    "enchantments": ("enchantments.json", "enchantments", ("description",)),
    "boss_modifiers": ("boss_modifiers.json", "modifiers", ("description",)),
    "mutators": ("mutators.json", "mutators", ("description",)),
}
# Sections whose entity NAMES the overlay applies (enemy/item names stay
# English by design — see the skip tuples in translationmixin.py).
NAME_SECTIONS = ("injuries", "enchantments", "boss_modifiers", "mutators")

# Short strings ("+30% ATK") legitimately survive unchanged.
MIN_LEAK_LEN = 25
MIN_RATIO_LEN = 60
# No target language here is systematically terser than English: outside this
# band the text was summarized away or padded/invented.
MIN_RATIO, MAX_RATIO = 0.6, 2.5
MAX_DUP_REUSE = 3
SAMPLES = 5
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
MIXED_WORD = re.compile(r"[Ѐ-ӿ][A-Za-z]|[A-Za-z][Ѐ-ӿ]")
DIGITS = re.compile(r"\d+")


def _norm(text):
    """Case/punctuation/whitespace-insensitive form for comparing texts."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    for src, dst in (("—", "--"), ("–", "--"), ("’", "'"),
                     ("“", '"'), ("”", '"')):
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def _by_id(node):
    """Base sections are id-keyed dicts or lists of {'id': ...}."""
    return dict(node) if isinstance(node, dict) else {e["id"]: e for e in node}


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


BASE = {
    name: _by_id(_load(ROOT / "data" / fname)[key])
    for name, (fname, key, _fields) in SECTIONS.items()
}


@pytest.fixture(scope="module")
def translations():
    return {lang: _load(LANG_DIR / f"data_{lang}.json") for lang in LANGS}


def _fields(tr, section):
    """Yield (entry_id, field, base_text, translated_text) for one section."""
    for entry_id, translated in tr.get(section, {}).items():
        base = BASE[section].get(entry_id)
        if not isinstance(base, dict) or not isinstance(translated, dict):
            continue
        for field in SECTIONS[section][2]:
            base_text, tr_text = base.get(field), translated.get(field)
            if isinstance(base_text, str) and isinstance(tr_text, str):
                yield entry_id, field, base_text, tr_text


def _fail(lang, rule, bad, total, hint=""):
    head = f"[{lang}] {rule}: {len(bad)}/{total} fields violate this rule"
    body = "\n".join(f"    {s}" for s in bad[:SAMPLES])
    more = f"\n    ... and {len(bad) - SAMPLES} more" if len(bad) > SAMPLES else ""
    return f"{head}\n{body}{more}" + (f"\n  {hint}" if hint else "")


@pytest.mark.parametrize("lang", LANGS)
def test_no_english_source_leak(lang, translations):
    """The English original must not survive inside the translation."""
    bad, total = [], 0
    for section in SECTIONS:
        for entry_id, field, base_text, tr_text in _fields(translations[lang], section):
            nb, nt = _norm(base_text), _norm(tr_text)
            if len(nb) < MIN_LEAK_LEN:
                continue
            total += 1
            if nb == nt:
                bad.append(f"{section}/{entry_id}.{field}: verbatim English copy")
            elif nb in nt:
                cut = tr_text.lower().find(base_text[:20].lower())
                bad.append(f"{section}/{entry_id}.{field}: English kept, wrapped "
                           f"by {tr_text[:cut].strip()[:40]!r}")
    assert not bad, _fail(
        lang, "english-leak", bad, total,
        "Translate the sentence itself; a localized prefix in front of English "
        "text is not a translation.")


@pytest.mark.parametrize("lang", LANGS)
def test_every_base_entry_is_translated(lang, translations):
    """No gaps: every base entry carries every required field, non-empty."""
    bad, total = [], 0
    for section, (_f, _k, fields) in SECTIONS.items():
        section_tr = translations[lang].get(section, {})
        for entry_id, base in BASE[section].items():
            for field in fields:
                if not isinstance(base.get(field), str):
                    continue
                total += 1
                value = section_tr.get(entry_id, {}).get(field)
                if not isinstance(value, str) or not value.strip():
                    bad.append(f"{section}/{entry_id}.{field}: missing or empty")
    assert not bad, _fail(lang, "coverage", bad, total)


@pytest.mark.parametrize("lang", LANGS)
def test_translation_keys_match_base_schema(lang, translations):
    """Field names must match the base data; ids must exist upstream.

    An earlier pass wrote 'desc' where base and UI read 'description'.
    """
    bad, total = [], 0
    for section, (_f, _k, fields) in SECTIONS.items():
        allowed = set(fields) | {"name"}
        for entry_id, translated in translations[lang].get(section, {}).items():
            total += 1
            if entry_id not in BASE[section]:
                bad.append(f"{section}/{entry_id}: id absent from base data")
            elif not isinstance(translated, dict):
                bad.append(f"{section}/{entry_id}: not an object")
            else:
                for key in translated:
                    if key not in allowed:
                        bad.append(f"{section}/{entry_id}: unknown field {key!r}"
                                   f" (base uses {sorted(allowed)})")
    assert not bad, _fail(lang, "schema", bad, total)


@pytest.mark.parametrize("lang", LANGS)
def test_text_is_in_the_target_language_script(lang, translations):
    """ru/uk must be Cyrillic; Latin-script files must contain none.

    A generator once assigned the Russian dicts to all eight languages.
    """
    bad, total = [], 0
    wants_cyrillic = lang in CYRILLIC_LANGS
    for section in SECTIONS:
        for entry_id, field, base_text, tr_text in _fields(translations[lang], section):
            if len(_norm(base_text)) < MIN_LEAK_LEN:
                continue
            total += 1
            has_cyrillic = bool(CYRILLIC.search(tr_text))
            if wants_cyrillic and not has_cyrillic:
                bad.append(f"{section}/{entry_id}.{field}: no Cyrillic at all")
            elif not wants_cyrillic and has_cyrillic:
                bad.append(f"{section}/{entry_id}.{field}: Cyrillic in a "
                           f"Latin-script language")
    assert not bad, _fail(lang, "script", bad, total)


@pytest.mark.parametrize("lang", LANGS)
def test_no_mixed_alphabet_inside_a_word(lang, translations):
    """Catches Latin lookalikes typed into Cyrillic words ('Kровотечение')."""
    bad = []
    for section in SECTIONS:
        for entry_id, translated in translations[lang].get(section, {}).items():
            for field, value in (translated or {}).items():
                hit = MIXED_WORD.search(value) if isinstance(value, str) else None
                if hit:
                    around = value[max(0, hit.start() - 15):hit.end() + 15]
                    bad.append(f"{section}/{entry_id}.{field}: ...{around}...")
    assert not bad, _fail(lang, "mixed-alphabet", bad, len(bad))


def _skeleton(lang, entry_id, base, tr_text):
    """Translation stripped of everything that varies per entry.

    A template survives the plain duplicate check by splicing the entry's own
    id or name into a constant sentence ("Опасный противник арены (pit_rat):
    свирепый боец..."). Removing the id, the base name, digits and — in the
    Cyrillic files — any Latin run collapses such entries onto one string.
    """
    text = _norm(tr_text)
    parts = [p for p in re.split(r"[_\W]+", entry_id.lower()) if len(p) >= 3]
    parts += [p for p in _norm(base.get("name", "")).split() if len(p) >= 3]
    for part in parts:
        text = text.replace(part, " ")
    if lang in CYRILLIC_LANGS:
        text = re.sub(r"[A-Za-z]+", " ", text)
    text = re.sub(r"\d+|[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text):
    """Content words only: digits and one/two-letter noise carry no meaning."""
    return set(re.findall(r"[^\W\d_]{3,}", _norm(text)))


def _jaccard(left, right):
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


@pytest.mark.parametrize("lang", LANGS)
def test_no_template_filled_duplicates(lang, translations):
    """One sentence reused across entries whose sources differ."""
    bad = []
    for section in SECTIONS:
        seen = {}
        for entry_id, field, base_text, tr_text in _fields(translations[lang], section):
            if len(_norm(base_text)) < MIN_LEAK_LEN:
                continue
            base = BASE[section][entry_id]
            key = _skeleton(lang, entry_id, base, tr_text)
            seen.setdefault(key, []).append((entry_id, _norm(base_text)))
        for text, entries in seen.items():
            sources = len(Counter(src for _id, src in entries))
            if len(entries) >= MAX_DUP_REUSE and sources > 1:
                ids = ", ".join(e for e, _ in entries[:4])
                bad.append(f"{section}: {len(entries)} entries collapse to one "
                           f"sentence ({ids}...) though their sources differ: "
                           f"{text[:60]!r}")
    assert not bad, _fail(
        lang, "duplicate-fill", bad, len(bad),
        "Splicing the entry id or name into a constant sentence is still one "
        "sentence. Translate what the source actually says.")


@pytest.mark.parametrize("lang", CYRILLIC_LANGS)
def test_no_latin_words_in_cyrillic_text(lang, translations):
    """Latin tokens in ru/uk text mean an id or English word leaked in."""
    allowed = {"hp", "atk", "def", "mp", "xp", "ii", "iii", "iv", "vi"}
    bad = []
    for section in SECTIONS:
        for entry_id, field, _base_text, tr_text in _fields(translations[lang], section):
            leaked = [t for t in re.findall(r"[A-Za-z][A-Za-z_]+", tr_text)
                      if t.lower() not in allowed]
            if leaked:
                bad.append(f"{section}/{entry_id}.{field}: Latin tokens {leaked[:3]}")
    assert not bad, _fail(lang, "latin-in-cyrillic", bad, len(bad))


@pytest.mark.parametrize("lang", CYRILLIC_LANGS)
def test_russian_and_ukrainian_are_not_each_other(lang, translations):
    """Orthographies are disjoint: ы/э/ъ/ё are Russian, і/ї/є/ґ Ukrainian."""
    forbidden = "іїєґІЇЄҐ" if lang == "ru" else "ыэъёЫЭЪЁ"
    bad = []
    for section in SECTIONS:
        for entry_id, field, _base_text, tr_text in _fields(translations[lang], section):
            hits = sorted({ch for ch in tr_text if ch in forbidden})
            if hits:
                bad.append(f"{section}/{entry_id}.{field}: letters {hits} "
                           f"do not belong to {lang}")
    assert not bad, _fail(lang, "wrong-slavic-language", bad, len(bad))


@pytest.mark.parametrize("lang", LANGS)
def test_internal_ids_do_not_leak_into_text(lang, translations):
    """Entry ids are internal keys and must never reach the player.

    A generator defeated the duplicate rule by pasting the id into one shared
    sentence: "Опасный противник арены (pit_rat): свирепый боец..." — 600
    identical descriptions that no longer looked identical.
    """
    bad = []
    for section in SECTIONS:
        for entry_id, field, base_text, tr_text in _fields(translations[lang], section):
            haystack, source = _norm(tr_text), _norm(base_text)
            for needle in (entry_id.casefold(), entry_id.replace("_", " ").casefold()):
                # Ids are derived from names, so a lore title legitimately reads
                # "Draven Ashborn". Only an id the SOURCE does not contain was
                # spliced in by a generator.
                if needle in haystack and needle not in source:
                    bad.append(f"{section}/{entry_id}.{field}: contains its own id")
                    break
    assert not bad, _fail(lang, "id-leak", bad, len(bad),
                          "Write the sentence a player should read.")


@pytest.mark.parametrize("lang", LANGS)
def test_translations_are_not_templated(lang, translations):
    """Entries whose sources differ must not share one boilerplate sentence.

    Catches template fill regardless of which token is varied per entry (id,
    name, number): the surrounding wording still collapses into one skeleton.
    """
    bad = []
    for section in SECTIONS:
        entries = [
            (entry_id, _tokens(base), _tokens(tr_text))
            for entry_id, _f, base, tr_text in _fields(translations[lang], section)
            if len(_norm(base)) >= MIN_LEAK_LEN and len(_tokens(tr_text)) >= 6
        ]
        count = len(entries)
        if count < 2:
            continue
        stride = max(1, count // 3)
        for index, (entry_id, src, tr) in enumerate(entries):
            for other in {(index + 1) % count, (index + stride) % count} - {index}:
                other_id, other_src, other_tr = entries[other]
                tr_sim, src_sim = _jaccard(tr, other_tr), _jaccard(src, other_src)
                if tr_sim >= 0.8 and src_sim <= 0.4:
                    bad.append(f"{section}/{entry_id} vs {other_id}: translations "
                               f"{tr_sim:.0%} alike, sources only {src_sim:.0%}")
    assert not bad, _fail(
        lang, "templated", bad, len(bad),
        "Every entry needs its own translation of its own source sentence.")


@pytest.mark.parametrize("lang", LANGS)
def test_entity_names_are_localized(lang, translations):
    """Names the overlay applies must actually be translated.

    Enemy and item names stay English by design (skip tuples in
    game/data_loader/translationmixin.py); these four groups do not — they are
    rendered on the fighter card, in the forge and in arena popups. A generator
    pass once overwrote already-translated names with the English originals.
    """
    bad, total = [], 0
    for section in NAME_SECTIONS:
        section_tr = translations[lang].get(section, {})
        english = 0
        for entry_id, base in BASE[section].items():
            base_name = base.get("name")
            if not isinstance(base_name, str) or not base_name.strip():
                continue
            total += 1
            name = (section_tr.get(entry_id) or {}).get("name")
            if not isinstance(name, str) or not name.strip():
                bad.append(f"{section}/{entry_id}: name missing")
            elif lang in CYRILLIC_LANGS and not CYRILLIC.search(name):
                bad.append(f"{section}/{entry_id}: {name!r} is not {lang}")
            elif _norm(name) == _norm(base_name):
                english += 1
        # A Latin-script language may share a word with English ("Poison" in
        # French); a whole section sharing them is an untranslated section.
        allowed = max(1, len(BASE[section]) // 3)
        if lang not in CYRILLIC_LANGS and english > allowed:
            bad.append(f"{section}: {english}/{len(BASE[section])} names left "
                       f"identical to English (at most {allowed} may coincide)")
    assert not bad, _fail(lang, "entity-names", bad, total)


@pytest.mark.parametrize("lang", LANGS)
def test_no_agent_scaffolding_residue(lang, translations):
    """LLM wrapper artifacts must never reach a player-visible string.

    The batches are translated by LLM agents, and an agent that wraps its
    answer in markdown fences or envelope tags produces a value every other
    rule here accepts: right language, right length, right script — with
    ``` or </content> rendered to the player verbatim. A sister translation
    project accepted 16 chapters with exactly such tails before growing this
    rule; merge-time quarantine (scripts/i18n_tool.py) is the first line,
    this gate is the second.
    """
    bad = []
    for section in SECTIONS:
        for entry_id, translated in translations[lang].get(section, {}).items():
            for field, value in (translated or {}).items():
                reason = find_scaffolding(value) if isinstance(value, str) else None
                if reason:
                    bad.append(f"{section}/{entry_id}.{field}: {reason} "
                               f"in {value[:50]!r}")
    assert not bad, _fail(lang, "scaffolding", bad, len(bad))


@pytest.mark.parametrize("lang", LANGS)
def test_translation_length_is_plausible(lang, translations):
    """Guards against summaries and invented replacements."""
    bad, total = [], 0
    for section in SECTIONS:
        for entry_id, field, base_text, tr_text in _fields(translations[lang], section):
            if len(base_text) < MIN_RATIO_LEN:
                continue
            total += 1
            ratio = len(tr_text) / len(base_text)
            if not MIN_RATIO <= ratio <= MAX_RATIO:
                bad.append(f"{section}/{entry_id}.{field}: {len(tr_text)} vs "
                           f"{len(base_text)} source chars (ratio {ratio:.2f})")
    assert not bad, _fail(
        lang, "length", bad, total,
        "Translate the whole source text; do not summarize or replace it.")


@pytest.mark.parametrize("lang", LANGS)
def test_numbers_survive_translation(lang, translations):
    """Numeric values are content: they must appear in the translation."""
    bad, total = [], 0
    for section in SECTIONS:
        for entry_id, field, base_text, tr_text in _fields(translations[lang], section):
            numbers = DIGITS.findall(base_text)
            if not numbers:
                continue
            total += 1
            missing = [n for n in numbers if n not in tr_text]
            if missing:
                bad.append(f"{section}/{entry_id}.{field}: lost {missing}")
    assert not bad, _fail(lang, "numbers", bad, total)
