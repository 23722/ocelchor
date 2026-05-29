"""Tests for the plain ↔ _collab cross-check."""

from __future__ import annotations

from pathlib import Path

import pytest

from xescol2ocelchor.crosscheck import crosscheck, discover_collab_pair

DATA = Path(__file__).parent.parent / "data" / "input"


@pytest.mark.parametrize("dataset", [
    "real1", "real2", "real3", "real4", "real5", "healthcare", "smartagriculture",
])
def test_crosscheck_full_agreement_per_dataset(dataset):
    plain = DATA / f"collectivelog_{dataset}.xes"
    collab = DATA / f"collectivelog_{dataset}_collab.xes"
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


def test_discover_collab_pair_returns_sibling():
    plain = DATA / "collectivelog_real1.xes"
    if not plain.exists():
        pytest.skip("real1 not present")
    paired = discover_collab_pair(plain)
    assert paired is not None
    assert paired.name == "collectivelog_real1_collab.xes"


def test_discover_collab_pair_returns_none_when_absent(tmp_path):
    f = tmp_path / "noparrtner.xes"
    f.write_text("<log/>")
    assert discover_collab_pair(f) is None
