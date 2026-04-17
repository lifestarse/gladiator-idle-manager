# Build: 7
"""Centralized data loader — singleton that loads all JSON data at startup."""

import json
import os
import logging
from collections import defaultdict

_log = logging.getLogger(__name__)


def _data_dir():
    """Return absolute path to data/ directory (project-root/data).

    We are now nested in game/data_loader/_shared.py — three dirname calls
    get us to project root. (Was two when this was game/data_loader.py.)
    """
    return os.path.join(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ),
        "data",
    )


