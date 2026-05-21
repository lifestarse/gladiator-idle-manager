# Build: 8
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


def _validate_ids(items, filename, required=("id",)):
    """Validate a list of dict items: warn on missing required keys and
    duplicate ids. Does not mutate input or drop items — first occurrence
    of a duplicate id wins downstream in _load_keyed; here we just surface
    the problem in logs so typos in data/*.json are noticed.
    """
    seen = set()
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            _log.warning(
                "[DataLoader] %s[%d] is not a dict: %r", filename, idx, item
            )
            continue
        for key in required:
            if key not in item:
                _log.warning(
                    "[DataLoader] %s[%d] missing '%s': %s",
                    filename, idx, key, item.get("name", "<no name>"),
                )
        item_id = item.get("id")
        if item_id is None:
            continue
        if item_id in seen:
            _log.warning(
                "[DataLoader] %s: duplicate id '%s' (index %d)",
                filename, item_id, idx,
            )
        else:
            seen.add(item_id)


