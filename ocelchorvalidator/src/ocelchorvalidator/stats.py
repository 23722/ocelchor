"""Statistics for paper evaluation — dataset characterization + constraint results."""

from __future__ import annotations

from dataclasses import dataclass

from ocelchorvalidator.constraints import ConstraintResult
from ocelchorvalidator.index import OcelIndex


@dataclass
class LogStats:
    """Per-log statistics for Table A in the paper."""

    # Identity
    file_name: str

    # Dataset characterization (Table A)
    num_vars: int  # distinct choreo:instance values
    num_events: int  # all events (= e_choreos)
    num_messages: int  # distinct objects appearing as choreo:message
    num_scoping_objects: int  # distinct subchoreographyInstance objects
    num_participants: int  # distinct objects as choreo:initiator or choreo:participant
    num_e2o: int   # total E2O relations across all events
    num_o2o: int   # total O2O relations across all objects
    num_e2o_m: int   # E2O relations with qualifier choreo:message
    num_e2o_cb: int  # E2O relations with qualifier choreo:contained-by
    num_o2o_c: int   # O2O relations with qualifier choreo:contains

    # Constraint validation (Table A + detail report)
    constraint_results: dict[str, ConstraintResult]

    @property
    def constraints_all_passed(self) -> bool:
        return all(r.passed for r in self.constraint_results.values())

    @property
    def violated_constraints(self) -> list[str]:
        return [cid for cid, r in self.constraint_results.items() if not r.passed]

    @property
    def total_elements_checked(self) -> int:
        return sum(r.elements_checked for r in self.constraint_results.values())


def compute_stats(
    file_name: str,
    ocel: dict,
    idx: OcelIndex,
    constraint_results: dict[str, ConstraintResult],
) -> LogStats:
    """Compute dataset characterization + attach constraint results for one log."""
    # num_vars: distinct choreo:instance object IDs across all events
    instance_ids: set[str] = set()
    message_ids: set[str] = set()
    participant_ids: set[str] = set()

    for e in ocel["events"]:
        for r in e.get("relationships", []):
            q = r["qualifier"]
            oid = r["objectId"]
            if q == "choreo:instance":
                instance_ids.add(oid)
            elif q == "choreo:message":
                message_ids.add(oid)
            elif q in ("choreo:initiator", "choreo:participant"):
                participant_ids.add(oid)

    num_e2o = sum(len(rels) for rels in idx.e2o.values())
    num_o2o = sum(len(rels) for rels in idx.o2o.values())
    num_e2o_m  = sum(1 for rels in idx.e2o.values() for _, q in rels if q == "choreo:message")
    num_e2o_cb = sum(1 for rels in idx.e2o.values() for _, q in rels if q == "choreo:contained-by")
    num_o2o_c  = sum(1 for rels in idx.o2o.values() for _, q in rels if q == "choreo:contains")

    return LogStats(
        file_name=file_name,
        num_vars=len(instance_ids),
        num_events=len(ocel["events"]),
        num_messages=len(message_ids),
        num_scoping_objects=len(idx.scoping_objects),
        num_participants=len(participant_ids),
        num_e2o=num_e2o,
        num_o2o=num_o2o,
        num_e2o_m=num_e2o_m,
        num_e2o_cb=num_e2o_cb,
        num_o2o_c=num_o2o_c,
        constraint_results=constraint_results,
    )
