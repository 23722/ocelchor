"""Tests for the plain ↔ _collab cross-check."""

from __future__ import annotations

from pathlib import Path

import pytest

from xescol2ocelchor.crosscheck import crosscheck, discover_collab_pair

# Plain (Corradini et al.) inputs live under the package's data/input/;
# their _collab.xes ground-truth siblings live alongside the tests as
# tests/data/<...>_collab.xes (added separately so they don't clutter the
# extractor's input directory).
DATA_PLAIN = Path(__file__).parent.parent / "data" / "input"
DATA_COLLAB = Path(__file__).parent / "data"


@pytest.mark.parametrize("dataset", [
    "real1", "real2", "real3", "real4", "real5", "healthcare", "smartagriculture",
])
def test_crosscheck_full_agreement_per_dataset(dataset):
    plain = DATA_PLAIN / f"collectivelog_{dataset}.xes"
    collab = DATA_COLLAB / f"collectivelog_{dataset}_collab.xes"
    if not (plain.exists() and collab.exists()):
        pytest.skip(f"{dataset} pair not present")

    result = crosscheck(plain, collab)

    # Spec §6: expected 100% agreement.
    assert result.agreement_pct == 100.0, (
        f"{dataset}: {result.messages_compared - result.messages_agreeing} mismatches; "
        f"first: {result.mismatches[:1]}"
    )
    # Every message id in plain must also appear in collab (and vice versa).
    assert result.only_in_plain == []
    assert result.only_in_collab == []


def test_discover_collab_pair_returns_sibling(tmp_path):
    # discover_collab_pair looks for a sibling next to the plain file, so the
    # test stages both files in a temp dir rather than depending on the
    # package's data layout (where plain and collab files live in different
    # directories).
    plain = tmp_path / "collectivelog_real1.xes"
    collab = tmp_path / "collectivelog_real1_collab.xes"
    plain.write_text("<log/>")
    collab.write_text("<log/>")
    paired = discover_collab_pair(plain)
    assert paired is not None
    assert paired.name == "collectivelog_real1_collab.xes"


def test_discover_collab_pair_returns_none_when_absent(tmp_path):
    f = tmp_path / "noparrtner.xes"
    f.write_text("<log/>")
    assert discover_collab_pair(f) is None
