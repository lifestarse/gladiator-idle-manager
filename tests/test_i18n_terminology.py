# Build: 1
"""Bidirectional terminology consistency — collisions one-way rules cannot see.

test_i18n_ui_quality.py enforces the glossary one way: the chosen rendering is
used, forbidden renderings are not. This module closes the opposite direction,
which a sister translation project learned to check the hard way — its one-way
rule let seven player-visible collisions through before a reverse check
existed:

* GLOSSARY: two different terms must not share one rendering in a language —
  a player who sees one word for two mechanics cannot tell them apart.
* DATA NAMES, one section: two entries with different source names must not
  share one localized name — two injuries both called «Перелом» read as one.
* DATA NAMES, whole file: one source name must not render two different ways —
  the same effect on two screens reads as two different mechanics.

Legitimate exceptions are DATA, not code: the "collisions_ok" block of
scripts/i18n_glossary.json holds every reviewed decision with its reason
(ru itself uses «уровень» for both tier and level on purpose). A decision
recorded as data survives any regeneration of the glossary; a decision made
silently inside a generator is re-litigated by the next generator.
"""
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pytest

from tests.test_i18n_data_quality import BASE, LANGS, NAME_SECTIONS

ROOT = Path(__file__).resolve().parents[1]
LANG_DIR = ROOT / "data" / "languages"
GLOSSARY_PATH = ROOT / "scripts" / "i18n_glossary.json"
SAMPLES = 5


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


GLOSSARY = _load(GLOSSARY_PATH)
COLLISIONS_OK = GLOSSARY.get("collisions_ok", {})
# Languages that declared a glossary column; ru is among them by design —
# the master language is where deliberate homonyms are decided.
GLOSSARY_LANGS = sorted({
    code
    for spec in GLOSSARY.get("terms", {}).values() if isinstance(spec, dict)
    for code in spec if code in LANGS
})


def _norm(text):
    return unicodedata.normalize("NFKC", text).casefold().strip()


def _headword(column_value):
    """The bare rendering out of an instructional glossary column.

    Columns are agent-facing instructions — «боєць (мн. бійці) — НЕ
    «винищувач»» — so the comparable part is what precedes the first
    annotation.
    """
    return _norm(re.split(r"[—(]", column_value)[0])


def _names(lang):
    """(section, entry_id, base_name, localized_name) across NAME_SECTIONS."""
    translations = _load(LANG_DIR / f"data_{lang}.json")
    rows = []
    for section in NAME_SECTIONS:
        for entry_id, entry in translations.get(section, {}).items():
            base_name = BASE[section].get(entry_id, {}).get("name")
            name = (entry or {}).get("name")
            if isinstance(base_name, str) and isinstance(name, str) \
                    and name.strip():
                rows.append((section, entry_id, base_name, name))
    return rows


def _fail(lang, rule, bad, whitelist):
    shown = "\n".join(f"    {line}" for line in bad[:SAMPLES])
    more = f"\n    ... and {len(bad) - SAMPLES} more" if len(bad) > SAMPLES else ""
    return (f"[{lang}] {rule}: {len(bad)} collisions\n{shown}{more}\n  "
            f"A deliberate homonym goes into collisions_ok.{whitelist} of "
            f"{GLOSSARY_PATH.name} with its reason; anything else is a defect "
            f"to re-translate.")


@pytest.mark.parametrize("lang", GLOSSARY_LANGS)
def test_glossary_renderings_do_not_collide(lang):
    """Two glossary terms sharing one rendering hide a mechanic from players."""
    allowed = COLLISIONS_OK.get("shared_rendering", {}).get(lang, {})
    seen = defaultdict(list)
    for term, spec in GLOSSARY["terms"].items():
        column = spec.get(lang) if isinstance(spec, dict) else None
        if isinstance(column, str) and column.strip():
            seen[_headword(column)].append(term)
    bad = [f"{head!r} <- terms {terms}" for head, terms in sorted(seen.items())
           if len(terms) > 1 and head not in allowed]
    assert not bad, _fail(lang, "glossary-collision", bad, "shared_rendering")


@pytest.mark.parametrize("lang", LANGS)
def test_different_entities_do_not_share_a_name(lang):
    """Within a section, distinct source names keep distinct localized names."""
    allowed = COLLISIONS_OK.get("shared_name", {}).get(lang, {})
    rows = _names(lang)
    bad = []
    for section in NAME_SECTIONS:
        seen = defaultdict(list)
        for sec, entry_id, base_name, name in rows:
            if sec == section:
                seen[_norm(name)].append((entry_id, base_name))
        for name, entries in sorted(seen.items()):
            if name in allowed:
                continue
            if len({_norm(base) for _entry, base in entries}) > 1:
                bad.append(f"{section}: {name!r} <- {entries}")
    assert not bad, _fail(lang, "shared-name", bad, "shared_name")


@pytest.mark.parametrize("lang", LANGS)
def test_one_source_name_renders_one_way(lang):
    """One source name, one rendering — across every section of the file."""
    allowed = COLLISIONS_OK.get("variant_renderings", {}).get(lang, {})
    renderings, where = defaultdict(set), defaultdict(list)
    for section, entry_id, base_name, name in _names(lang):
        renderings[_norm(base_name)].add(_norm(name))
        where[_norm(base_name)].append(f"{section}/{entry_id}: {name!r}")
    bad = [f"{base!r} -> {sorted(forms)} ({'; '.join(where[base][:4])})"
           for base, forms in sorted(renderings.items())
           if len(forms) > 1 and base not in allowed]
    assert not bad, _fail(lang, "variant-rendering", bad, "variant_renderings")


def test_whitelist_entries_carry_reasons():
    """An exception without a reason is not a decision — it is a suppression."""
    bad = []
    for block, per_lang in COLLISIONS_OK.items():
        if block == "_doc" or not isinstance(per_lang, dict):
            continue
        for lang, entries in per_lang.items():
            if not isinstance(entries, dict):
                bad.append(f"{block}.{lang}: must map word -> reason")
                continue
            for word, reason in entries.items():
                if not isinstance(reason, str) or len(reason.strip()) < 10:
                    bad.append(f"{block}.{lang}.{word!r}: reason is missing")
    assert not bad, "collisions_ok entries without reasons:\n  " + "\n  ".join(bad)
