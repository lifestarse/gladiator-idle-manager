# Build: 3
"""Tests for data translations (achievements, expeditions, tutorial, enemies, etc.)."""
import json
import re
import pytest
from game.engine import GameEngine
from game.localization import set_language, get_language, t, SUPPORTED_LANGUAGES
from game.data_loader import data_loader
import game.achievements as A


@pytest.fixture(autouse=True)
def restore_localization():
    """Ensure data translations are reset to Russian after each test to prevent test leakage."""
    yield
    set_language("ru")
    data_loader._loaded = False
    data_loader.load_all()
    data_loader.apply_translations("ru")
    GameEngine._wire_data()


def test_load_with_russian_language_key(tmp_save_path):
    """Save containing 'language': 'ru' loads achievements in Russian."""
    save_data = {"gold": 100, "language": "ru"}
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f)

    eng = GameEngine(save_path=tmp_save_path)
    eng.load()
    assert A.ACHIEVEMENTS[0]["name"] == "Первая кровь"


def test_load_without_language_key_defaults_to_effective_language(tmp_save_path):
    """Save without 'language' key still applies translations for effective language (default ru)."""
    save_data = {"gold": 100}
    with open(tmp_save_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f)

    eng = GameEngine(save_path=tmp_save_path)
    eng.load()
    assert A.ACHIEVEMENTS[0]["name"] != "First Blood"
    assert A.ACHIEVEMENTS[0]["name"] == "Первая кровь"


def test_switch_language_ru_to_en():
    """Reloading data loader and applying 'en' translations restores English achievement names."""
    set_language("en")
    data_loader._loaded = False
    data_loader.load_all()
    data_loader.apply_translations("en")
    GameEngine._wire_data()

    assert A.ACHIEVEMENTS[0]["name"] == "First Blood"


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_tutorial_keys_present_in_all_languages(lang):
    """Verify all 31 tutorial keys exist and are non-empty across all supported languages."""
    set_language(lang)
    step_ids = [
        ("welcome", 4),
        ("first_win", 3),
        ("hire_fighter", 3),
        ("discover_forge", 3),
        ("discover_hunts", 3),
        ("first_death", 3),
        ("discover_boss", 3),
    ]
    for step_id, line_count in step_ids:
        title_key = f"tut_{step_id}_title"
        title_val = t(title_key)
        assert title_val != title_key, f"Missing title key {title_key} in {lang}"
        assert len(title_val) > 0

        for line_idx in range(line_count):
            line_key = f"tut_{step_id}_l{line_idx}"
            line_val = t(line_key)
            assert line_val != line_key, f"Missing line key {line_key} in {lang}"
            assert len(line_val) > 0


def test_enemy_name_remains_english_and_data_loaded():
    """Enemy names remain in English while data sections are populated."""
    set_language("ru")
    data_loader._loaded = False
    data_loader.load_all()
    data_loader.apply_translations("ru")
    GameEngine._wire_data()

    enemies = data_loader.enemies
    assert len(enemies) > 0
    # Enemy names must remain English per design preference
    assert enemies[0]["name"] in ("Pit Rat", "Starving Slave", "Gutter Thief", "Chained Wretch")


@pytest.mark.parametrize("lang", ["ru", "uk"])
def test_data_sections_contain_cyrillic(lang):
    """Verify that enemies, injuries, lore, mutators, boss_modifiers, and enchantments contain Cyrillic text."""
    set_language(lang)
    data_loader._loaded = False
    data_loader.load_all()
    data_loader.apply_translations(lang)

    cyrillic_pattern = re.compile(r"[\u0400-\u04FF]")

    # Check enemies description
    enemies = data_loader.enemies
    assert len(enemies) > 0
    assert bool(cyrillic_pattern.search(enemies[0].get("description", "")))

    # Check injuries description
    injuries = data_loader.injuries
    assert len(injuries) > 0
    assert bool(cyrillic_pattern.search(injuries[0].get("description", "")))

    # Check lore title & text
    lore = data_loader.lore
    assert len(lore) > 0
    assert bool(cyrillic_pattern.search(lore[0].get("title", "")))
    assert bool(cyrillic_pattern.search(lore[0].get("text", "")))

    # Check enchantments description
    enchantments = list(data_loader.enchantments.values())
    assert len(enchantments) > 0
    assert bool(cyrillic_pattern.search(enchantments[0].get("description", "")))

    # Check boss modifiers description
    boss_mods = list(data_loader.boss_modifiers.values())
    assert len(boss_mods) > 0
    assert bool(cyrillic_pattern.search(boss_mods[0].get("description", "")))

    # Check mutators description
    mutators = list(data_loader.mutators.values())
    assert len(mutators) > 0
    assert bool(cyrillic_pattern.search(mutators[0].get("description", "")))


@pytest.mark.parametrize("lang", ["ru", "uk"])
def test_data_sections_anti_placeholder_against_english_base(lang):
    """Spot check 3-5 entries per section ensuring translated text is not equal to base English."""
    set_language(lang)
    data_loader._loaded = False
    data_loader.load_all()
    data_loader.apply_translations(lang)

    base_enemies = json.load(open("data/enemies.json", encoding="utf-8"))["enemies"]
    base_injuries = json.load(open("data/injuries.json", encoding="utf-8"))["injuries"]
    base_lore = json.load(open("data/lore.json", encoding="utf-8"))["entries"]

    # Enemies spot check (5 entries)
    enemies = data_loader.enemies
    for idx in range(min(5, len(enemies))):
        assert enemies[idx].get("description") != base_enemies[idx].get("description")

    # Injuries spot check (5 entries)
    injuries = data_loader.injuries
    for idx in range(min(5, len(injuries))):
        assert injuries[idx].get("description") != base_injuries[idx].get("description")

    # Lore spot check (5 entries)
    lore = data_loader.lore
    for idx in range(min(5, len(lore))):
        assert lore[idx].get("title") != base_lore[idx].get("title")
        assert lore[idx].get("text") != base_lore[idx].get("text")

