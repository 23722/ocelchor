"""Statistics collection and reporting."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from trace2choreo.models import OcelEvent, OcelObject, Trace


@dataclass
class Stats:
    """Tracks conversion statistics."""
    traces_processed: int = 0
    total_events: int = 0
    total_objects: int = 0
    events_by_type: dict[str, int] = field(default_factory=dict)
    objects_by_type: dict[str, int] = field(default_factory=dict)
    total_e2o: int = 0
    total_o2o: int = 0


def collect_stats(
    traces: list[Trace],
    events: list[OcelEvent],
    objects: list[OcelObject],
) -> Stats:
    """Collect statistics from transformation results."""
    stats = Stats()
    stats.traces_processed = len(traces)
    stats.total_events = len(events)
    stats.total_objects = len(objects)

    for event in events:
        stats.events_by_type[event.type] = stats.events_by_type.get(event.type, 0) + 1
        stats.total_e2o += len(event.e2o)

    for obj in objects:
        stats.objects_by_type[obj.type] = stats.objects_by_type.get(obj.type, 0) + 1
        stats.total_o2o += len(obj.o2o)

    return stats


def print_stats(stats: Stats) -> None:
    """Print a formatted summary of conversion statistics."""
    out = sys.stderr
    out.write("\n--- Statistics ---\n")
    out.write(f"Traces processed:  {stats.traces_processed}\n")
    out.write(f"Events generated:  {stats.total_events}\n")
    out.write(f"Objects generated: {stats.total_objects}\n")
    out.write(f"E2O relations:     {stats.total_e2o}\n")
    out.write(f"O2O relations:     {stats.total_o2o}\n")

    if stats.events_by_type:
        out.write("\nEvents by type:\n")
        for t, count in sorted(stats.events_by_type.items()):
            out.write(f"  {t}: {count}\n")

    if stats.objects_by_type:
        out.write("\nObjects by type:\n")
        for t, count in sorted(stats.objects_by_type.items()):
            out.write(f"  {t}: {count}\n")
