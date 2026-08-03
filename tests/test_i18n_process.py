# Build: 1
"""The wave-process machinery: prewave, blind QA sampling, gate calibration,
and the release check's own checks.

These pin the behaviors the process depends on rather than any particular
content: prewave candidates come only from genuinely new recurring vocabulary,
the QA task file carries no hint of why a key was chosen, calibration counts
land under the right selector, and the release gate recognizes both a healthy
docs/content and a torn one.
"""
import json

import pytest

from scripts import i18n_tool, release_check
from scripts.i18n_tool import _prewave_candidates

# ------------------------------------------------------------------- prewave


def test_prewave_flags_recurring_new_vocabulary():
    new = {"ui:a": "Гладиатор получил сигил силы",
           "ui:b": "Сигил защиты сломан",
           "ui:c": "Обычный текст без новинок"}
    old = ["Гладиатор вышел на арену", "Обычный текст", "текст без новинок"]
    candidates = _prewave_candidates(new, old, known_words=set())
    assert candidates == {"сигил": ["ui:a", "ui:b"]}


def test_prewave_ignores_single_use_and_established_words():
    new = {"ui:a": "Редчайшее слово встречается однажды",
           "ui:b": "Арена ждёт бойцов"}
    old = ["Арена пуста", "На арене тихо", "Арена закрыта", "бойцов манит арена"]
    assert _prewave_candidates(new, old, known_words=set()) == {}


def test_prewave_respects_glossary_and_ignore_list():
    new = {"ui:a": "Сигил силы", "ui:b": "Сигил защиты"}
    old = []
    assert _prewave_candidates(new, old, known_words={"сигил"}) == {}


# ------------------------------------------------- blind QA and calibration


@pytest.fixture
def qa_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(i18n_tool, "QA_DIR", str(tmp_path / "qa"))
    monkeypatch.setattr(i18n_tool, "CALIBRATION_PATH",
                        str(tmp_path / "calibration.json"))
    return tmp_path


def test_qa_task_file_is_blind(qa_dirs):
    """The agent must not be able to read why a key entered the sample."""
    i18n_tool.qa_sample("uk", size=12, seed=42)
    task = json.loads((qa_dirs / "qa" / "qa_uk.json").read_text("utf-8"))
    meta = json.loads((qa_dirs / "qa" / "qa_uk.meta.json").read_text("utf-8"))
    assert set(task["keys"]) == set(meta["selectors"])
    assert "selector" not in json.dumps(task)
    for entry in task["keys"].values():
        assert set(entry) == {"ru", "en", "current"}
    # the sample mixes control keys among risk keys, unmarked
    assert "control" in meta["selectors"].values()
    assert set(meta["selectors"].values()) - {"control"}


def test_qa_report_scores_selectors_and_flags_controls(qa_dirs, capsys):
    qa = qa_dirs / "qa"
    qa.mkdir()
    (qa / "qa_uk.meta.json").write_text(json.dumps({
        "lang": "uk",
        "selectors": {"k1": "machine", "k2": "machine", "k3": "control"},
    }), encoding="utf-8")
    (qa / "qa_uk.verdicts.json").write_text(json.dumps({
        "k1": "homonym: винищувач",
        "k2": "ok",
        "k3": "pos: глагол вместо существительного",
    }), encoding="utf-8")
    i18n_tool.qa_report("uk")
    calibration = json.loads(
        (qa_dirs / "calibration.json").read_text("utf-8"))
    assert calibration["selectors"]["machine"] == {"defects": 1, "clean": 1}
    assert calibration["selectors"]["control"] == {"defects": 1, "clean": 0}
    assert calibration["accepted"]["uk"] == ["k2"]
    assert "КОНТРОЛЬ ПРОБИТ" in capsys.readouterr().out


def test_qa_report_refuses_partial_verdicts(qa_dirs):
    """A key without a verdict is silently accepted defect — refuse that."""
    qa = qa_dirs / "qa"
    qa.mkdir()
    (qa / "qa_uk.meta.json").write_text(json.dumps({
        "lang": "uk", "selectors": {"k1": "machine", "k2": "control"},
    }), encoding="utf-8")
    (qa / "qa_uk.verdicts.json").write_text(json.dumps({"k1": "ok"}),
                                            encoding="utf-8")
    with pytest.raises(SystemExit):
        i18n_tool.qa_report("uk")


# -------------------------------------------------------------- release check


def test_release_check_accepts_the_real_repo():
    """The gate must be green on the content that is actually shipped."""
    fails, _warns = release_check.check_content(release_check.CONTENT_DIR)
    assert fails == []
    fails, _warns = release_check.check_parity(release_check.LANG_DIR)
    assert fails == []


def test_release_check_catches_a_torn_manifest(tmp_path):
    """Missing files and revision drift are exactly what it exists to catch."""
    (tmp_path / "manifest.json").write_text(json.dumps({
        "schema": 1,
        "entries": {
            "pack.uk": {"path": "packs/uk.v3.json", "revision": 3},
            "pack.de": {"path": "packs/de.v1.json", "revision": 2},
        },
    }), encoding="utf-8")
    packs = tmp_path / "packs"
    packs.mkdir()
    # uk.v3 is referenced but absent; de.v1 embeds revision 1, manifest says 2
    (packs / "de.v1.json").write_text(json.dumps(
        {"lang": "de", "revision": 1, "ui": {}, "data": {}}), encoding="utf-8")
    (packs / "orphan.v9.json").write_text("{}", encoding="utf-8")
    fails, warns = release_check.check_content(str(tmp_path))
    assert any("uk.v3.json" in line for line in fails)
    assert any("de.v1.json" in line or "pack.de" in line for line in fails)
    assert any("orphan.v9.json" in line for line in warns)
