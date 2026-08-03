# Build: 2
"""The scaffolding detector shared by the merge quarantine and both gates.

scripts/i18n_tool.py::find_scaffolding is one implementation serving three
call sites: merge()/merge_ui() quarantine dirty fragments before they touch
data/languages/*.json, and the two acceptance gates catch anything that got
there some other way. These tests pin the boundary the patterns must hold:
every known agent-envelope artifact is caught, none of the game's own markup
is — a false positive here would quarantine honest work.
"""
import json

import pytest

from scripts import i18n_tool
from scripts.i18n_tool import _fragment_scaffolding, find_scaffolding


@pytest.mark.parametrize("text,reason", [
    ('```json\n{"a": "б"}\n```', "markdown fence"),
    ("Перевод готов```", "markdown fence"),
    ("Опік</content>", "answer-envelope tag"),
    ("<translation>Опік", "answer-envelope tag"),
    ("<output >Текст", "answer-envelope tag"),
    ('{"entries": {"k": "v"}}', "serialized JSON instead of text"),
    ('  ["Перший", "Другий"]', "serialized JSON instead of text"),
    ("[1] Перший абзац", "numbered-answer marker"),
])
def test_agent_scaffolding_is_caught(text, reason):
    assert find_scaffolding(text) == reason


@pytest.mark.parametrize("text", [
    "[b]Жирний[/b] і [color=ffd040]кольоровий[/color]",  # BBCode markup
    "Залишилось {n} бійців",                             # placeholder
    "g.<name> :=",                                       # script-editor meta-var
    "-{dmg} HP",                                         # stat abbreviation
    "Опасный противник арены: бывший солдат.",           # plain prose
    "УВІМК / ВИМК",                                      # slashes and caps
    "{old} теперь {new}!",                               # braces without quotes
])
def test_game_markup_stays_legal(text):
    assert find_scaffolding(text) is None


def test_fragment_scan_reaches_nested_fields():
    fragment = {"entries": {"key": "```текст```"},
                "enemies:rat": {"name": "Щур", "description": "чисто"}}
    assert _fragment_scaffolding(fragment) == [("entries.key", "markdown fence")]


@pytest.fixture
def quarantine_dirs(tmp_path, monkeypatch):
    """Point the quarantine and its ledger at scratch space."""
    monkeypatch.setattr(i18n_tool, "REJECT_DIR", str(tmp_path / "rejected"))
    monkeypatch.setattr(i18n_tool, "LEDGER_PATH",
                        str(tmp_path / "ledger.jsonl"))
    return tmp_path


def _reject(root, name="uk__misc.json"):
    fragment = root / name
    fragment.write_text("{}", encoding="utf-8")
    i18n_tool._quarantine(str(fragment), [("k", "markdown fence")])
    return fragment


def test_quarantine_moves_the_whole_fragment(quarantine_dirs):
    """Rejected work leaves the merge inputs — status() must not count it."""
    fragment = _reject(quarantine_dirs)
    assert not fragment.exists()
    assert (quarantine_dirs / "rejected" / "uk__misc.json").exists()


def test_quarantine_numbers_attempts_instead_of_overwriting(quarantine_dirs):
    """The pile of quarantined copies IS the retry counter — never clobbered."""
    _reject(quarantine_dirs)
    _reject(quarantine_dirs)
    rejected = quarantine_dirs / "rejected"
    assert (rejected / "uk__misc.json").exists()
    assert (rejected / "uk__misc.2.json").exists()
    assert i18n_tool._reject_attempts("uk__misc.json") == 2


def test_third_quarantine_escalates(quarantine_dirs, capsys):
    """After ESCALATE_AFTER identical failures the answer is not 'retry'."""
    for _attempt in range(i18n_tool.ESCALATE_AFTER):
        _reject(quarantine_dirs)
    assert "ESCALATE" in capsys.readouterr().out


def test_quarantine_lands_in_the_ledger(quarantine_dirs):
    """Outcomes are journaled — success is judged by artifacts, not reports."""
    _reject(quarantine_dirs)
    lines = (quarantine_dirs / "ledger.jsonl").read_text(
        encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    assert entry["event"] == "quarantine"
    assert entry["fragment"] == "uk__misc.json"
    assert entry["attempt"] == 1
