"""Cross-check the extractor's reconstruction against the ``_collab`` ground truth.

For each ``(trace, msgInstanceId)`` pair in the plain file, the extractor
reconstructs the message *source* (sender ``org:group``) and *target* set
(receiver ``org:group``\\ s). The ``_collab`` variant of the same dataset
encodes that information directly via ``collab:participant`` on each event
(plus ``collab:fromParticipant`` / ``collab:toParticipant``).

Expected agreement per spec §6 is **100%** for every dataset; any mismatch
is an extractor bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from xescol2ocelchor.reader import load_xes


@dataclass
class MessageRecord:
    """The source and target set reconstructed for one ``(trace, msgInstanceId)`` pair."""
    trace: str
    msg_instance_id: str
    source: str | None
    targets: tuple[str, ...]  # sorted, deduplicated


@dataclass
class Mismatch:
    trace: str
    msg_instance_id: str
    plain_source: str | None
    collab_source: str | None
    plain_targets: tuple[str, ...]
    collab_targets: tuple[str, ...]


@dataclass
class CrosscheckResult:
    plain_path: Path
    collab_path: Path
    messages_compared: int = 0
    messages_agreeing: int = 0
    only_in_plain: list[tuple[str, str]] = field(default_factory=list)
    only_in_collab: list[tuple[str, str]] = field(default_factory=list)
    mismatches: list[Mismatch] = field(default_factory=list)

    @property
    def agreement_pct(self) -> float:
        if self.messages_compared == 0:
            return 100.0
        return 100.0 * self.messages_agreeing / self.messages_compared


def crosscheck(plain_path: Path, collab_path: Path) -> CrosscheckResult:
    """Compare a plain XES file's reconstruction with its ``_collab`` counterpart."""
    plain_records = _records_from_plain(load_xes(plain_path))
    collab_records = _records_from_collab(load_xes(collab_path))

    result = CrosscheckResult(plain_path=plain_path, collab_path=collab_path)
    plain_keys = set(plain_records)
    collab_keys = set(collab_records)

    result.only_in_plain = sorted(plain_keys - collab_keys)
    result.only_in_collab = sorted(collab_keys - plain_keys)

    for key in sorted(plain_keys & collab_keys):
        p = plain_records[key]
        c = collab_records[key]
        result.messages_compared += 1
        if p.source == c.source and p.targets == c.targets:
            result.messages_agreeing += 1
        else:
            result.mismatches.append(Mismatch(
                trace=key[0],
                msg_instance_id=key[1],
                plain_source=p.source,
                collab_source=c.source,
                plain_targets=p.targets,
                collab_targets=c.targets,
            ))
    return result


def _records_from_plain(traces) -> dict[tuple[str, str], MessageRecord]:
    """Build ``(trace, msgId) → MessageRecord`` from the plain XES file.

    Source = ``org:group`` of the send event; targets = sorted distinct
    ``org:group``\\ s of all matching receive events.
    """
    out: dict[tuple[str, str], MessageRecord] = {}
    for tr in traces:
        sends: dict[str, str] = {}
        receivers: dict[str, list[str]] = {}
        for ev in tr.events:
            if not ev.msg_instance_id:
                continue
            if ev.msg_type == "send":
                sends[ev.msg_instance_id] = ev.org_group
            elif ev.msg_type == "receive":
                receivers.setdefault(ev.msg_instance_id, []).append(ev.org_group)
        for mid, src in sends.items():
            tgts = tuple(sorted(set(receivers.get(mid, []))))
            out[(tr.concept_name, mid)] = MessageRecord(
                trace=tr.concept_name, msg_instance_id=mid,
                source=src, targets=tgts,
            )
    return out


def _records_from_collab(traces) -> dict[tuple[str, str], MessageRecord]:
    """Build ``(trace, msgId) → MessageRecord`` from the ``_collab`` XES file.

    Uses ``collab:participant`` (carried on every event) for both ends:
    source = ``collab:participant`` of the send event; targets = sorted
    distinct ``collab:participant`` values of matching receive events.
    """
    out: dict[tuple[str, str], MessageRecord] = {}
    for tr in traces:
        sends: dict[str, str] = {}
        receivers: dict[str, list[str]] = {}
        for ev in tr.events:
            if not ev.msg_instance_id:
                continue
            collab_participant = ev.attributes.get("collab:participant", ev.org_group)
            if ev.msg_type == "send":
                sends[ev.msg_instance_id] = collab_participant
            elif ev.msg_type == "receive":
                receivers.setdefault(ev.msg_instance_id, []).append(collab_participant)
        for mid, src in sends.items():
            tgts = tuple(sorted(set(receivers.get(mid, []))))
            out[(tr.concept_name, mid)] = MessageRecord(
                trace=tr.concept_name, msg_instance_id=mid,
                source=src, targets=tgts,
            )
    return out


def discover_collab_pair(plain_path: Path) -> Path | None:
    """Given ``foo.xes``, return the sibling ``foo_collab.xes`` if it exists."""
    candidate = plain_path.with_name(plain_path.stem + "_collab" + plain_path.suffix)
    return candidate if candidate.exists() else None
