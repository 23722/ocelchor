"""Tests for ocelchormodel.reader.

Verifies that OCEL 2.0 JSON files are loaded correctly and that
malformed or missing input produces clear error messages.

Why these tests matter:
  The reader is the entry point of the pipeline. If it silently
  accepts bad input, all downstream modules may produce wrong output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ocelchormodel.reader import read_ocel

DATA_DIR = Path(__file__).parent / "data"


class TestReadOcel:
    def test_loads_successfully(self):
        """A valid OCEL file returns a dict."""
        data = read_ocel(DATA_DIR / "swap_1_ocel.json")
        assert isinstance(data, dict)

    def test_has_required_keys(self):
        """The dict contains the four OCEL 2.0 top-level keys."""
        data = read_ocel(DATA_DIR / "swap_1_ocel.json")
        assert set(data.keys()) >= {"objectTypes", "eventTypes", "objects", "events"}

    def test_missing_key_raises_value_error(self, tmp_path):
        """An OCEL file missing a required key is rejected."""
        bad = {"objectTypes": [], "eventTypes": [], "objects": []}  # missing "events"
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match="events"):
            read_ocel(f)

    def test_invalid_json_raises_value_error(self, tmp_path):
        """A file that isn't valid JSON is rejected."""
        f = tmp_path / "broken.json"
        f.write_text("{not valid json}")
        with pytest.raises(ValueError):
            read_ocel(f)

    def test_missing_file_raises_value_error(self, tmp_path):
        """A non-existent path is rejected."""
        with pytest.raises(ValueError):
            read_ocel(tmp_path / "nonexistent.json")
