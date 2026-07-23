"""Build the worked-example OCEL 2.0 fixture (README_worked_example.md).

Two choreography instances exercising pooling and repetition:

    Instance A                          Instance B
    R  Request unlock [Gov]             R  Request unlock [Gov]
    T1   Request transfer [TORN]        T1'  Request transfer [TORN]
    T1   hook [Vault]                   T1'  hook [Vault]
    T1   Respond to transfer [TORN]     T1'  Respond to transfer [TORN]
    R  Respond to unlock [Gov]          T2'  Request transfer [TORN]
                                        T2'  hook [Vault]
                                        T2'  Respond to transfer [TORN]
                                        R  Respond to unlock [Gov]

Roles (OCEL object types): unlock is Proxy → Governance, transfer Governance →
TORN, hook TORN → Vault. Request/response brackets are contained in the scope
they open/close (interface contract I3), so each scope's ≻-first event is its
Request bracket. Timestamps encode ≻ order (base + i ms; spec §I6).

Run:  python build_worked_example.py   →   writes worked_example.json
"""

from __future__ import annotations

import json
from pathlib import Path

Q_INSTANCE = "choreo:instance"
Q_INITIATOR = "choreo:initiator"
Q_PARTICIPANT = "choreo:participant"
Q_MESSAGE = "choreo:message"
Q_CONTAINED_BY = "choreo:contained-by"
Q_CONTAINS = "choreo:contains"
Q_SOURCE = "choreo:source"
Q_TARGET = "choreo:target"

BASE = "2020-01-01T00:00:00"


def _time(ms: int) -> str:
    return f"{BASE}.{ms:03d}Z"


class Builder:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.objects: dict[str, dict] = {}
        self.otypes: set[str] = set()

    def obj(self, oid: str, otype: str) -> str:
        if oid not in self.objects:
            self.objects[oid] = {"id": oid, "type": otype, "attributes": [], "relationships": []}
            self.otypes.add(otype)
        return oid

    def msg(self, mid: str, source: str, target: str, attrs: dict) -> str:
        self.objects[mid] = {
            "id": mid,
            "type": "message",
            "attributes": [{"name": k, "value": v, "time": _time(0)} for k, v in attrs.items()],
            "relationships": [
                {"objectId": source, "qualifier": Q_SOURCE},
                {"objectId": target, "qualifier": Q_TARGET},
            ],
        }
        self.otypes.add("message")
        return mid

    def scope(self, sid: str, name: str) -> str:
        self.objects[sid] = {
            "id": sid,
            "type": "subchoreographyInstance",
            "attributes": [{"name": "name", "value": name, "time": _time(0)}],
            "relationships": [],
        }
        self.otypes.add("subchoreographyInstance")
        return sid

    def contains(self, parent: str, child: str) -> None:
        self.objects[parent]["relationships"].append({"objectId": child, "qualifier": Q_CONTAINS})

    def event(self, eid, etype, ms, init, part, scope, inst, messages) -> None:
        rels = [
            {"objectId": init, "qualifier": Q_INITIATOR},
            {"objectId": part, "qualifier": Q_PARTICIPANT},
            {"objectId": scope, "qualifier": Q_CONTAINED_BY},
            {"objectId": inst, "qualifier": Q_INSTANCE},
        ]
        for mid in messages:
            rels.append({"objectId": mid, "qualifier": Q_MESSAGE})
        self.events.append({
            "id": eid,
            "type": etype,
            "time": _time(ms),
            "attributes": [{"name": "trace_order", "value": ms}],
            "relationships": rels,
        })

    def build(self) -> dict:
        return {
            "objectTypes": [{"name": t, "attributes": []} for t in sorted(self.otypes)],
            "eventTypes": [{"name": t, "attributes": []}
                           for t in sorted({e["type"] for e in self.events})],
            "objects": list(self.objects.values()),
            "events": self.events,
        }


def _instance(b: Builder, suffix: str, transfer_frames: int) -> None:
    """Emit one instance with `transfer_frames` repetitions of the transfer frame."""
    inst = b.obj(f"choreographyInstance:{suffix}", "choreographyInstance")
    proxy = b.obj(f"Proxy{suffix}", "Proxy")
    gov = b.obj(f"Gov{suffix}", "Governance")
    torn = b.obj(f"TORN{suffix}", "TORN")
    vault = b.obj(f"Vault{suffix}", "Vault")

    root = b.scope(f"sub:{suffix}:root", "unlock [Gov]")
    ms = 0

    # R: Request unlock [Gov]  (Proxy → Governance)
    b.event(f"e:{suffix}:R:req", "Request unlock [Gov]", ms, proxy, gov, root, inst,
            [b.msg(f"m:{suffix}:R:req", proxy, gov, {"unlockArg": "1"})]); ms += 1

    for k in range(1, transfer_frames + 1):
        t = b.scope(f"sub:{suffix}:t{k}", "transfer [TORN]")
        b.contains(root, t)
        # Request transfer [TORN]  (Governance → TORN)
        b.event(f"e:{suffix}:t{k}:req", "Request transfer [TORN]", ms, gov, torn, t, inst,
                [b.msg(f"m:{suffix}:t{k}:req", gov, torn, {"amount": "10"})]); ms += 1
        # hook [Vault]  (TORN → Vault) — atomic leaf, two-way
        b.event(f"e:{suffix}:t{k}:hook", "hook [Vault]", ms, torn, vault, t, inst,
                [b.msg(f"m:{suffix}:t{k}:hook:req", torn, vault, {"hookArg": "x"}),
                 b.msg(f"m:{suffix}:t{k}:hook:res", vault, torn, {"output": "ok"})]); ms += 1
        # Respond to transfer [TORN]  (TORN → Governance)
        b.event(f"e:{suffix}:t{k}:res", "Respond to transfer [TORN]", ms, torn, gov, t, inst,
                [b.msg(f"m:{suffix}:t{k}:res", torn, gov, {"output": "1"})]); ms += 1

    # R: Respond to unlock [Gov]  (Governance → Proxy)
    b.event(f"e:{suffix}:R:res", "Respond to unlock [Gov]", ms, gov, proxy, root, inst,
            [b.msg(f"m:{suffix}:R:res", gov, proxy, {"output": "done"})]); ms += 1


def build() -> dict:
    b = Builder()
    _instance(b, "A", transfer_frames=1)
    _instance(b, "B", transfer_frames=2)
    return b.build()


if __name__ == "__main__":
    out = Path(__file__).parent / "worked_example.json"
    out.write_text(json.dumps(build(), indent=2))
    print(f"wrote {out}")
