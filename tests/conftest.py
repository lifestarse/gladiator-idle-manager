# Build: 1
"""pytest fixtures. CRITICAL: every test that creates a GameEngine must use
the `engine` fixture (or `tmp_save_path`) so SAVE_PATH points at a tempfile.
Never let a test run against ~/.gladiator_idle_save.json.
"""
import os
import sys
import tempfile

import pytest

# Ensure project root is importable.
_PROJ_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)


@pytest.fixture
def tmp_save_path(tmp_path):
    """A safe save-path for tests. Auto-cleans via tmp_path."""
    return str(tmp_path / "test_save.json")


@pytest.fixture
def engine(tmp_save_path):
    """Fresh GameEngine rooted at an isolated tempfile save path.

    Rule: NEVER construct GameEngine() with default save path in tests.
    That path is ~/.gladiator_idle_save.json — real user save.
    """
    from game.engine import GameEngine
    eng = GameEngine(save_path=tmp_save_path)
    return eng
