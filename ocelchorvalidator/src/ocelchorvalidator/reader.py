"""OCEL 2.0 JSON reader."""

from __future__ import annotations

import json
from pathlib import Path

_REQUIRED_KEYS = {"objectTypes", "eventTypes", "objects", "events"}


def read_ocel(path: Path) -> dict:
    """Load and return the raw OCEL 2.0 JSON as a dict.

    Raises:
        ValueError: if the file is not valid JSON or is missing required keys.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Cannot read {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a JSON object at top level, got {type(data).__name__}"
        )

    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        raise ValueError(
            f"Missing required OCEL 2.0 keys in {path}: {sorted(missing)}"
        )

    return data
