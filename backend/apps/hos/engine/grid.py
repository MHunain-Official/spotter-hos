"""Normalize daily-log grid segments into a single non-overlapping 0–24 timeline."""

from __future__ import annotations

from typing import Any


STATUS_KEYS = {
    "OFF": "off_duty",
    "SB": "sleeper",
    "D": "driving",
    "ON": "on_duty",
}


def _clip(h: float) -> float:
    return max(0.0, min(24.0, float(h)))


def normalize_day_segments(
    raw: list[dict[str, Any]],
    *,
    eps: float = 1e-6,
) -> list[dict[str, Any]]:
    """
    Build a clean paper-log timeline:
    - drop zero-length / invalid segments
    - clip to [0, 24]
    - resolve overlaps (later segment wins)
    - fill gaps with OFF
    - merge consecutive same-status blocks
    """
    cleaned: list[tuple[float, float, str, str]] = []
    for seg in raw:
        status = str(seg.get("status") or "OFF").upper()
        if status not in STATUS_KEYS:
            status = "OFF"
        start = _clip(seg.get("start_hour", 0))
        end = _clip(seg.get("end_hour", 0))
        # Midnight wrap: end stored as 0 while start is evening
        if end + eps < start and end <= eps:
            end = 24.0
        if end <= start + eps:
            continue
        cleaned.append((start, end, status, str(seg.get("remark") or "")))

    if not cleaned:
        return [
            {
                "status": "OFF",
                "start_hour": 0.0,
                "end_hour": 24.0,
                "remark": "Off duty",
            }
        ]

    cleaned.sort(key=lambda t: (t[0], t[1]))

    # Sweep-line: later segments overwrite earlier ones on overlap
    # Represent day as ordered non-overlapping pieces via events
    pieces: list[tuple[float, float, str, str]] = []
    for start, end, status, remark in cleaned:
        if not pieces:
            pieces.append((start, end, status, remark))
            continue
        next_pieces: list[tuple[float, float, str, str]] = []
        for p0, p1, pst, prm in pieces:
            if p1 <= start + eps or p0 >= end - eps:
                next_pieces.append((p0, p1, pst, prm))
                continue
            # overlap — keep non-overlapping sides of existing piece
            if p0 < start - eps:
                next_pieces.append((p0, start, pst, prm))
            if p1 > end + eps:
                next_pieces.append((end, p1, pst, prm))
        next_pieces.append((start, end, status, remark))
        next_pieces.sort(key=lambda t: (t[0], t[1]))
        pieces = next_pieces

    # Fill gaps [0,24] with OFF
    filled: list[tuple[float, float, str, str]] = []
    cursor = 0.0
    for start, end, status, remark in pieces:
        if start > cursor + eps:
            filled.append((cursor, start, "OFF", "Off duty"))
        filled.append((max(cursor, start), end, status, remark))
        cursor = max(cursor, end)
    if cursor < 24.0 - eps:
        filled.append((cursor, 24.0, "OFF", "Off duty"))

    # Merge consecutive same status
    merged: list[dict[str, Any]] = []
    for start, end, status, remark in filled:
        if end <= start + eps:
            continue
        if (
            merged
            and merged[-1]["status"] == status
            and abs(merged[-1]["end_hour"] - start) <= 1e-4
        ):
            merged[-1]["end_hour"] = round(end, 4)
            if remark and not merged[-1].get("remark"):
                merged[-1]["remark"] = remark
        else:
            merged.append(
                {
                    "status": status,
                    "start_hour": round(start, 4),
                    "end_hour": round(end, 4),
                    "remark": remark,
                }
            )
    return merged


def totals_from_segments(segments: list[dict[str, Any]]) -> dict[str, float]:
    totals = {"off_duty": 0.0, "sleeper": 0.0, "driving": 0.0, "on_duty": 0.0}
    for seg in segments:
        key = STATUS_KEYS.get(str(seg.get("status", "OFF")).upper(), "off_duty")
        totals[key] += float(seg["end_hour"]) - float(seg["start_hour"])
    return {k: round(v, 2) for k, v in totals.items()}
