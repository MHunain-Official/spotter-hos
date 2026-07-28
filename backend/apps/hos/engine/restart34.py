"""34-hour restart detection for the 60/70 weekly cycle."""

from __future__ import annotations

from apps.hos.engine.limits import RESTART_34_HOURS
from apps.hos.engine.types import DutySegment, DutyStatus, Restart34Event


def detect_34h_restart(segments: list[DutySegment]) -> list[Restart34Event]:
    """Scan consecutive OFF+SB runs; emit events when duration ≥ 34h."""
    events: list[Restart34Event] = []
    if not segments:
        return events

    run_start = None
    run_end = None
    run_hours = 0.0

    def flush() -> None:
        nonlocal run_start, run_end, run_hours
        if run_start and run_hours + 1e-6 >= RESTART_34_HOURS:
            events.append(
                Restart34Event(at=run_end or run_start, duration_hours=round(run_hours, 4))
            )
        run_start = None
        run_end = None
        run_hours = 0.0

    for seg in segments:
        if seg.status in (DutyStatus.OFF, DutyStatus.SB):
            if run_start is None:
                run_start = seg.start_at
            run_end = seg.end_at
            run_hours += seg.duration_hours
        else:
            flush()

    flush()
    return events
