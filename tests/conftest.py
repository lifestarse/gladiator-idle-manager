# Build: 3
"""Shared test fixtures for Gladiator Idle Manager."""
import sys
import os
import json
import pytest
from unittest.mock import MagicMock

# Mock kivy before any game imports
sys.modules['kivy'] = MagicMock()
sys.modules['kivy.utils'] = MagicMock()
sys.modules['kivy.utils'].platform = 'linux'
sys.modules['kivy.app'] = MagicMock()

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Now we can import game modules
from game.models import Fighter, Enemy, DifficultyScaler, FIGHTER_CLASSES, FORGE_WEAPONS, FORGE_ARMOR, FORGE_ACCESSORIES, RELICS, ENCHANTMENT_TYPES, RARITY_COMMON, RARITY_UNCOMMON, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY
from game.battle import BattleManager, BattlePhase, BattleState
from game.data_loader import data_loader

# Load JSON data and wire into models module globals
data_loader.load_all()
from game.engine import GameEngine
GameEngine._wire_data()

@pytest.fixture
def fighter_factory():
    """Factory for creating fighters with optional class and level."""
    def make(fighter_class="mercenary", level=1, name=None):
        f = Fighter(name=name or "TestFighter", fighter_class=fighter_class)
        for _ in range(level - 1):
            f.level_up()
        return f
    return make

@pytest.fixture
def engine():
    """Fresh GameEngine with mocked save path."""
    import tempfile
    from game.engine import GameEngine
    e = GameEngine()
    e.SAVE_PATH = os.path.join(tempfile.gettempdir(), "test_gladiator_save.json")
    return e

@pytest.fixture
def data_dir():
    return os.path.join(PROJECT_ROOT, "data")

@pytest.fixture
def sample_weapon():
    return {"id": "test_sword", "name": "Test Sword", "slot": "weapon",
            "rarity": "common", "str": 5, "agi": 0, "vit": 0, "cost": 100}

@pytest.fixture
def sample_armor():
    return {"id": "test_armor", "name": "Test Armor", "slot": "armor",
            "rarity": "common", "str": 0, "agi": 5, "vit": 15, "cost": 200}
