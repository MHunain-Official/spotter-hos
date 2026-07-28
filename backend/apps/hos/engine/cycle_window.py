"""
FMCSA 70-hour / 8-day rolling calendar-day window with midnight recap.

Do NOT use a naive continuous 192-hour sum as the only cycle check.
At local midnight, the oldest day drops off and remaining hours are recalculated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apps.hos.engine.limits import CYCLE_LIMIT_HOURS, CYCLE_WINDOW_DAYS
from apps.hos.engine.types import CycleRecalcEvent


@dataclass
class CycleWindow:
    """Rolling 8 calendar-day on-duty accumulator (home-terminal local time)."""

    tz: ZoneInfo
    daily_on_duty: dict[date, float] = field(default_factory=dict)
    events: list[CycleRecalcEvent] = field(default_factory=list)
    _last_local_date: date | None = None

    @classmethod
    def seed_from_used_hours(
        cls,
        *,
        used_hours: float,
        as_of: datetime,
        tz_name: str = "America/Chicago",
    ) -> "CycleWindow":
        """
        Seed prior days so the opening 8-day sum equals ``used_hours``.

        Puts the bulk on the most recent prior day so midnight rollover
        during a multi-day trip can free hours (the junior-bug trap).
        """
        tz = ZoneInfo(tz_name)
        local = as_of.astimezone(tz)
        window = cls(tz=tz)
        window._last_local_date = local.date()

        remaining = max(0.0, min(float(used_hours), CYCLE_LIMIT_HOURS))
        # Distribute into prior 7 days (not including today) so today starts fresh
        # but the rolling sum matches the assessment input.
        day = local.date() - timedelta(days=1)
        chunks: list[tuple[date, float]] = []
        while remaining > 1e-6 and len(chunks) < CYCLE_WINDOW_DAYS - 1:
            chunk = min(14.0, remaining)  # realistic daily cap for seed
            chunks.append((day, chunk))
            remaining -= chunk
            day -= timedelta(days=1)
        if remaining > 1e-6:
            # Dump leftover on oldest chunk day
            if chunks:
                d, h = chunks[-1]
                chunks[-1] = (d, h + remaining)
            else:
                chunks.append((local.date() - timedelta(days=1), remaining))

        for d, h in chunks:
            window.daily_on_duty[d] = round(h, 4)

        return window

    def window_dates(self, local_day: date) -> list[date]:
        return [local_day - timedelta(days=i) for i in range(CYCLE_WINDOW_DAYS - 1, -1, -1)]

    def cycle_used(self, at: datetime) -> float:
        local_day = at.astimezone(self.tz).date()
        return round(sum(self.daily_on_duty.get(d, 0.0) for d in self.window_dates(local_day)), 4)

    def cycle_remaining(self, at: datetime) -> float:
        return round(CYCLE_LIMIT_HOURS - self.cycle_used(at), 4)

    def add_on_duty(self, at: datetime, hours: float) -> None:
        if hours <= 0:
            return
        local_day = at.astimezone(self.tz).date()
        self.daily_on_duty[local_day] = round(self.daily_on_duty.get(local_day, 0.0) + hours, 4)

    def ensure_midnight_rollovers(self, from_at: datetime, to_at: datetime) -> list[CycleRecalcEvent]:
        """
        Advance clock across any local midnights between from_at and to_at,
        emitting recalculation events when the oldest day drops off.
        """
        emitted: list[CycleRecalcEvent] = []
        if to_at <= from_at:
            return emitted

        local_from = from_at.astimezone(self.tz)
        local_to = to_at.astimezone(self.tz)

        # Walk each midnight strictly after local_from's date up through local_to's date.
        cursor_date = local_from.date()
        while cursor_date < local_to.date():
            midnight = datetime(
                cursor_date.year, cursor_date.month, cursor_date.day, tzinfo=self.tz
            ) + timedelta(days=1)
            new_day = midnight.date()
            dropped_date = new_day - timedelta(days=CYCLE_WINDOW_DAYS)
            dropped_hours = self.daily_on_duty.get(dropped_date, 0.0)
            # Day falls out of the 8-day window; keep historical record but exclude via window_dates.
            new_remaining = self.cycle_remaining(midnight)
            event = CycleRecalcEvent(
                at=midnight,
                dropped_date=dropped_date.isoformat(),
                dropped_hours=round(dropped_hours, 4),
                new_remaining=new_remaining,
            )
            if dropped_hours > 0:
                self.events.append(event)
                emitted.append(event)
            cursor_date = new_day

        self._last_local_date = local_to.date()
        return emitted

    def sum_last_n_including_today(self, day: date, n: int) -> float:
        """Sum on-duty hours for the last ``n`` calendar days including today."""
        days = [day - timedelta(days=i) for i in range(n - 1, -1, -1)]
        return round(sum(self.daily_on_duty.get(d, 0.0) for d in days), 4)

    def a_last_7_including_today(self, day: date) -> float:
        """Paper log 70/8 column A: on-duty last 7 days including today."""
        return self.sum_last_n_including_today(day, 7)

    def paper_recap(self, day: date, on_duty_today: float) -> dict[str, float]:
        """
        Fields matching the Drivers Daily Log recap block.

        70 Hour / 8 Day:
          A = last 7 incl today, B = 70 - A, C = last 8 incl today
        60 Hour / 7 Day (shown for form fidelity; assessment uses 70/8):
          A = last 6 incl today, B = 60 - A, C = last 7 incl today
        """
        a70 = self.sum_last_n_including_today(day, 7)
        c70 = self.sum_last_n_including_today(day, 8)
        a60 = self.sum_last_n_including_today(day, 6)
        c60 = self.sum_last_n_including_today(day, 7)
        return {
            "on_duty_today": round(on_duty_today, 2),
            # 70/8
            "a_70_last_7_incl_today": a70,
            "b_70_available_tomorrow": round(70.0 - a70, 2),
            "c_70_last_8_incl_today": c70,
            # 60/7 (form columns — not enforced for assessment cycle)
            "a_60_last_6_incl_today": a60,
            "b_60_available_tomorrow": round(60.0 - a60, 2),
            "c_60_last_7_incl_today": c60,
            # backwards-compatible aliases
            "a_last_7_including_today": a70,
            "b_available_tomorrow": round(70.0 - a70, 2),
            "cycle_used_8_day": c70,
        }

    def reset_after_34h(self, at: datetime) -> None:
        """34-hour restart: weekly cycle back to zero."""
        self.daily_on_duty.clear()
        self._last_local_date = at.astimezone(self.tz).date()
