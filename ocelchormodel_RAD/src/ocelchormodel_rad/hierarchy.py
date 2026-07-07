"""Hierarchy: recorded, not reconstructed (spec §B3).

Containment is read straight off the log (choreo:contained-by / choreo:contains);
there is no interval heuristic. Well-nestedness is guaranteed by the hard gates
C11 (≤1 direct scope per event) and C14 (≤1 parent, acyclic), asserted in reader.

Flat logs (no scoping objects — e.g. the Corradini XES-derived logs) yield
enclosing-scope chains of length 0, so discovery degrades gracefully to flat
inductive mining.
"""

from __future__ import annotations

from ocelchormodel_rad.reader import Event, Model


def is_flat(model: Model) -> bool:
    """A log with no scoping objects (all event paths have length 1)."""
    return not model.scopes


def enclosing_scopes(model: Model, e: Event) -> list[str]:
    """Enclosing scope ids of event ``e``, outermost → innermost (spec §B2.4).

    Length 0 for events directly under the instance and for every event of a
    flat log. Walks up choreo:contains (child → parent); C14 guarantees the
    walk is finite and acyclic.
    """
    chain: list[str] = []
    sid = e.scope_id
    while sid is not None:
        chain.append(sid)
        sid = model.scope_parent.get(sid)
    chain.reverse()  # outermost first
    return chain


def scope_path(model: Model, scope_id: str) -> list[str]:
    """Containment path of scope ids from the root scope down to ``scope_id``."""
    chain: list[str] = []
    sid: str | None = scope_id
    while sid is not None:
        chain.append(sid)
        sid = model.scope_parent.get(sid)
    chain.reverse()
    return chain
