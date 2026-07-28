"""
HOS trip simulator for property-carrying drivers (70h/8-day).

Enforces 11h drive, 14h window, 30-min break, midnight cycle recap,
fuel every 1000 miles, 1h pickup/dropoff. Optional adverse +2h and 34h restart.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from apps.hos.engine.cycle_window import CycleWindow
from apps.hos.engine.grid import normalize_day_segments, totals_from_segments
from apps.hos.engine.limits import (
    DROPOFF_ON_DUTY_HOURS,
    FUEL_EVERY_MILES,
    FUEL_ON_DUTY_HOURS,
    MAX_DRIVE_BEFORE_BREAK_HOURS,
    MIN_BREAK_FROM_DRIVING_HOURS,
    MIN_OFF_FOR_DAILY_RESET_HOURS,
    PICKUP_ON_DUTY_HOURS,
    max_driving_hours,
    max_window_hours,
)
from apps.hos.engine.restart34 import detect_34h_restart
from apps.hos.engine.types import (
    DutySegment,
    DutyStatus,
    DailyLogSheet,
    SimulationResult,
    TripStopEvent,
)


STEP_HOURS = 0.25  # 15-minute resolution matching paper log ticks


def _point_along(coords: list[list[float]], fraction: float) -> tuple[float, float]:
    """coords are [lng, lat]."""
    if not coords:
        return 0.0, 0.0
    if fraction <= 0:
        lng, lat = coords[0]
        return lat, lng
    if fraction >= 1:
        lng, lat = coords[-1]
        return lat, lng
    # Approximate by index
    idx = int(fraction * (len(coords) - 1))
    lng, lat = coords[idx]
    return lat, lng


class HosSimulator:
    def __init__(
        self,
        *,
        trip_start: datetime,
        current_cycle_used_hours: float,
        home_terminal_tz: str = "America/Chicago",
        adverse_conditions: bool = False,
        auto_34h_restart: bool = True,
    ) -> None:
        if trip_start.tzinfo is None:
            trip_start = trip_start.replace(tzinfo=ZoneInfo(home_terminal_tz))
        self.tz_name = home_terminal_tz
        self.tz = ZoneInfo(home_terminal_tz)
        self.clock = trip_start.astimezone(self.tz)
        self.adverse = adverse_conditions
        self.auto_34h = auto_34h_restart
        self.max_drive = max_driving_hours(adverse=adverse_conditions)
        self.max_window = max_window_hours(adverse=adverse_conditions)

        self.cycle = CycleWindow.seed_from_used_hours(
            used_hours=current_cycle_used_hours,
            as_of=self.clock,
            tz_name=home_terminal_tz,
        )

        self.segments: list[DutySegment] = []
        self.stops: list[TripStopEvent] = []
        self.midnight_events = []

        # Daily clocks since last 10h reset
        self.driving_since_reset = 0.0
        self.window_elapsed = 0.0
        self.window_open = False
        self.driving_since_break = 0.0

    def _emit_midnight(self, from_at: datetime, to_at: datetime) -> None:
        ev = self.cycle.ensure_midnight_rollovers(from_at, to_at)
        self.midnight_events.extend(ev)

    def _append_segment(
        self,
        status: DutyStatus,
        hours: float,
        *,
        location: str = "",
        lat: float | None = None,
        lng: float | None = None,
        remark: str = "",
        is_34h: bool = False,
    ) -> DutySegment:
        if hours <= 0:
            raise ValueError("segment hours must be positive")

        # Split across midnights for clean daily logs (optional but nicer)
        remaining = hours
        last_seg = None
        while remaining > 1e-9:
            local = self.clock
            next_midnight = datetime(
                local.year, local.month, local.day, tzinfo=self.tz
            ) + timedelta(days=1)
            room = (next_midnight - local).total_seconds() / 3600.0
            chunk = min(remaining, room if room > 1e-9 else remaining)
            # Prefer 15-min alignment except for tiny remainders
            if chunk > STEP_HOURS and abs(chunk - round(chunk / STEP_HOURS) * STEP_HOURS) > 1e-6:
                aligned = max(STEP_HOURS, round(chunk / STEP_HOURS) * STEP_HOURS)
                if aligned <= room + 1e-9:
                    chunk = min(aligned, remaining)

            if chunk <= 1e-9:
                break

            start = self.clock
            end = start + timedelta(hours=chunk)
            if end <= start:
                break
            self._emit_midnight(start, end)

            seg = DutySegment(
                status=status,
                start_at=start,
                end_at=end,
                location_label=location,
                lat=lat,
                lng=lng,
                remark=remark or f"{status.value} — {location}".strip(" —"),
                is_34h_restart_segment=is_34h,
            )
            self.segments.append(seg)
            last_seg = seg

            if status in (DutyStatus.D, DutyStatus.ON):
                self.cycle.add_on_duty(start, chunk)
                if not self.window_open:
                    self.window_open = True
                    self.window_elapsed = 0.0
                self.window_elapsed += chunk
                if status == DutyStatus.D:
                    self.driving_since_reset += chunk
                    self.driving_since_break += chunk
            elif status in (DutyStatus.OFF, DutyStatus.SB):
                # Breaks from driving can be OFF/SB/ON — ON handled above path separately
                pass

            self.clock = end
            remaining -= chunk

        assert last_seg is not None
        return last_seg

    def _remaining_drive_allowed(self) -> float:
        by_11 = self.max_drive - self.driving_since_reset
        by_14 = self.max_window - self.window_elapsed if self.window_open else self.max_window
        by_break = MAX_DRIVE_BEFORE_BREAK_HOURS - self.driving_since_break
        by_cycle = self.cycle.cycle_remaining(self.clock)
        return max(0.0, min(by_11, by_14, by_break, by_cycle))

    def _take_30_min_break(self, location: str, lat: float, lng: float) -> None:
        self._append_segment(
            DutyStatus.OFF,
            MIN_BREAK_FROM_DRIVING_HOURS,
            location=location,
            lat=lat,
            lng=lng,
            remark=f"30-min rest break — {location}",
        )
        self.driving_since_break = 0.0
        self.stops.append(
            TripStopEvent(
                stop_type="rest",
                label=f"30-min break — {location}",
                lat=lat,
                lng=lng,
                arrive_at=self.segments[-1].start_at,
                depart_at=self.segments[-1].end_at,
                duration_hours=MIN_BREAK_FROM_DRIVING_HOURS,
                duty_status=DutyStatus.OFF.value,
            )
        )

    def _take_10h_reset(self, location: str, lat: float, lng: float) -> None:
        self._append_segment(
            DutyStatus.SB,
            MIN_OFF_FOR_DAILY_RESET_HOURS,
            location=location,
            lat=lat,
            lng=lng,
            remark=f"10-hour sleeper reset — {location}",
        )
        self.driving_since_reset = 0.0
        self.window_elapsed = 0.0
        self.window_open = False
        self.driving_since_break = 0.0
        self.stops.append(
            TripStopEvent(
                stop_type="rest",
                label=f"10h sleeper — {location}",
                lat=lat,
                lng=lng,
                arrive_at=self.segments[-1].start_at,
                depart_at=self.segments[-1].end_at,
                duration_hours=MIN_OFF_FOR_DAILY_RESET_HOURS,
                duty_status=DutyStatus.SB.value,
            )
        )

    def _take_34h_restart(self, location: str, lat: float, lng: float) -> None:
        self._append_segment(
            DutyStatus.OFF,
            34.0,
            location=location,
            lat=lat,
            lng=lng,
            remark=f"34-hour restart — {location}",
            is_34h=True,
        )
        self.cycle.reset_after_34h(self.clock)
        self.driving_since_reset = 0.0
        self.window_elapsed = 0.0
        self.window_open = False
        self.driving_since_break = 0.0
        self.stops.append(
            TripStopEvent(
                stop_type="rest",
                label=f"34h restart — {location}",
                lat=lat,
                lng=lng,
                arrive_at=self.segments[-1].start_at,
                depart_at=self.segments[-1].end_at,
                duration_hours=34.0,
                duty_status=DutyStatus.OFF.value,
            )
        )

    def _ensure_can_work(self, hours_needed: float, location: str, lat: float, lng: float) -> None:
        """If cycle can't fit upcoming on-duty, optionally 34h restart."""
        rem = self.cycle.cycle_remaining(self.clock)
        if rem + 1e-6 >= hours_needed:
            return
        if self.auto_34h:
            self._take_34h_restart(location, lat, lng)
            return
        raise RuntimeError(
            f"Cycle remaining ({rem:.2f}h) insufficient for {hours_needed:.2f}h on-duty"
        )

    def _on_duty_block(
        self,
        hours: float,
        *,
        location: str,
        lat: float,
        lng: float,
        remark: str,
        stop_type: str | None = None,
        stop_label: str | None = None,
    ) -> None:
        self._ensure_can_work(hours, location, lat, lng)
        # On-duty still consumes 14h window
        if self.window_open and self.window_elapsed >= self.max_window - 1e-9:
            self._take_10h_reset(location, lat, lng)
        start = self.clock
        self._append_segment(
            DutyStatus.ON,
            hours,
            location=location,
            lat=lat,
            lng=lng,
            remark=remark,
        )
        if stop_type:
            self.stops.append(
                TripStopEvent(
                    stop_type=stop_type,
                    label=stop_label or remark,
                    lat=lat,
                    lng=lng,
                    arrive_at=start,
                    depart_at=self.clock,
                    duration_hours=hours,
                    duty_status=DutyStatus.ON.value,
                )
            )

    def _drive_hours(
        self,
        hours: float,
        *,
        location: str,
        lat: float,
        lng: float,
        coords: list[list[float]],
        miles_start: float,
        miles_end: float,
        total_trip_miles: float,
    ) -> None:
        remaining = hours
        while remaining > 1e-6:
            allowed = self._remaining_drive_allowed()
            if allowed <= 1e-6:
                # Diagnose which limit hit
                if self.cycle.cycle_remaining(self.clock) <= 1e-6:
                    if self.auto_34h:
                        self._take_34h_restart(location, lat, lng)
                        continue
                    raise RuntimeError("70-hour cycle exhausted")
                if self.driving_since_break + 1e-6 >= MAX_DRIVE_BEFORE_BREAK_HOURS:
                    self._take_30_min_break(location, lat, lng)
                    continue
                # 11h or 14h
                self._take_10h_reset(location, lat, lng)
                continue

            chunk = min(remaining, allowed, STEP_HOURS)
            # Progress fraction along whole trip for marker position
            done_ratio = 0.0
            if total_trip_miles > 0:
                driven = miles_start + (miles_end - miles_start) * (
                    1.0 - remaining / hours if hours else 1.0
                )
                done_ratio = min(1.0, driven / total_trip_miles)
            plat, plng = _point_along(coords, done_ratio)

            self._append_segment(
                DutyStatus.D,
                chunk,
                location=location,
                lat=plat,
                lng=plng,
                remark=f"Driving — {location}",
            )
            remaining -= chunk

            if self.driving_since_break + 1e-6 >= MAX_DRIVE_BEFORE_BREAK_HOURS and remaining > 1e-6:
                self._take_30_min_break(location, plat, plng)

    def run(
        self,
        *,
        current: dict[str, Any],
        pickup: dict[str, Any],
        dropoff: dict[str, Any],
        leg_a_miles: float,
        leg_a_hours: float,
        leg_b_miles: float,
        leg_b_hours: float,
        geometry: list[list[float]],
        approximate_routing: bool = False,
    ) -> SimulationResult:
        """
        current/pickup/dropoff: {label, lat, lng}
        geometry: list of [lng, lat]
        """
        total_miles = leg_a_miles + leg_b_miles
        # Pre-trip off-duty from midnight to start if needed for nice logs
        local_start = self.clock
        day_start = datetime(
            local_start.year, local_start.month, local_start.day, tzinfo=self.tz
        )
        if local_start > day_start:
            # Leading OFF so the daily grid is complete
            self.segments.append(
                DutySegment(
                    status=DutyStatus.OFF,
                    start_at=day_start,
                    end_at=local_start,
                    location_label=current["label"],
                    lat=current["lat"],
                    lng=current["lng"],
                    remark=f"Off duty — {current['label']}",
                )
            )

        self.stops.append(
            TripStopEvent(
                stop_type="origin",
                label=f"Origin — {current['label']}",
                lat=current["lat"],
                lng=current["lng"],
                arrive_at=self.clock,
                depart_at=self.clock,
                duration_hours=0.0,
                duty_status=DutyStatus.ON.value,
            )
        )

        # Deadhead to pickup
        if leg_a_hours > 1e-6:
            self._drive_hours(
                leg_a_hours,
                location=f"{current['label']} → {pickup['label']}",
                lat=pickup["lat"],
                lng=pickup["lng"],
                coords=geometry,
                miles_start=0.0,
                miles_end=leg_a_miles,
                total_trip_miles=total_miles or 1.0,
            )

        # Fuel planning along total distance
        fuel_marks = []
        if total_miles > FUEL_EVERY_MILES:
            n = int(total_miles // FUEL_EVERY_MILES)
            for i in range(1, n + 1):
                fuel_marks.append(i * FUEL_EVERY_MILES)

        miles_driven_plan = leg_a_miles
        fuels_done = 0

        # Pickup on-duty
        self._on_duty_block(
            PICKUP_ON_DUTY_HOURS,
            location=pickup["label"],
            lat=pickup["lat"],
            lng=pickup["lng"],
            remark=f"Pickup — {pickup['label']}",
            stop_type="pickup",
            stop_label=f"Pickup — {pickup['label']}",
        )

        # Insert fuel stops that fall on leg A after the fact is awkward; insert during leg B
        # and any remaining based on cumulative miles.
        def maybe_fuel(cum_miles: float) -> None:
            nonlocal fuels_done
            while fuels_done < len(fuel_marks) and cum_miles + 1e-6 >= fuel_marks[fuels_done]:
                frac = min(1.0, fuel_marks[fuels_done] / (total_miles or 1.0))
                flat, flng = _point_along(geometry, frac)
                label = f"Fuel stop (~{int(fuel_marks[fuels_done])} mi)"
                self._on_duty_block(
                    FUEL_ON_DUTY_HOURS,
                    location=label,
                    lat=flat,
                    lng=flng,
                    remark=label,
                    stop_type="fuel",
                    stop_label=label,
                )
                fuels_done += 1

        maybe_fuel(miles_driven_plan)

        # Loaded leg to dropoff
        if leg_b_hours > 1e-6:
            # Drive in slices so fuel can interrupt — approximate by splitting at fuel mile markers
            remaining_miles = leg_b_miles
            remaining_hours = leg_b_hours
            miles_base = leg_a_miles
            while remaining_miles > 1e-3 and remaining_hours > 1e-6:
                next_fuel_at = None
                if fuels_done < len(fuel_marks):
                    next_fuel_at = fuel_marks[fuels_done]
                if next_fuel_at is not None and next_fuel_at > miles_base:
                    slice_miles = min(remaining_miles, next_fuel_at - miles_base)
                else:
                    slice_miles = remaining_miles
                slice_hours = remaining_hours * (slice_miles / remaining_miles) if remaining_miles else 0
                self._drive_hours(
                    slice_hours,
                    location=f"{pickup['label']} → {dropoff['label']}",
                    lat=dropoff["lat"],
                    lng=dropoff["lng"],
                    coords=geometry,
                    miles_start=miles_base,
                    miles_end=miles_base + slice_miles,
                    total_trip_miles=total_miles or 1.0,
                )
                miles_base += slice_miles
                remaining_miles -= slice_miles
                remaining_hours -= slice_hours
                maybe_fuel(miles_base)

        # Dropoff
        self._on_duty_block(
            DROPOFF_ON_DUTY_HOURS,
            location=dropoff["label"],
            lat=dropoff["lat"],
            lng=dropoff["lng"],
            remark=f"Dropoff — {dropoff['label']}",
            stop_type="dropoff",
            stop_label=f"Dropoff — {dropoff['label']}",
        )

        # Pad to end of final calendar day with OFF
        local = self.clock
        day_end = datetime(local.year, local.month, local.day, tzinfo=self.tz) + timedelta(days=1)
        if day_end > self.clock:
            self._append_segment(
                DutyStatus.OFF,
                (day_end - self.clock).total_seconds() / 3600.0,
                location=dropoff["label"],
                lat=dropoff["lat"],
                lng=dropoff["lng"],
                remark=f"Off duty — {dropoff['label']}",
            )

        daily_logs = self._build_daily_logs(
            total_miles=total_miles,
            origin=current["label"],
            destination=dropoff["label"],
        )
        restarts = detect_34h_restart(self.segments)

        drive_hours = sum(s.duration_hours for s in self.segments if s.status == DutyStatus.D)
        on_hours = sum(
            s.duration_hours for s in self.segments if s.status in (DutyStatus.D, DutyStatus.ON)
        )

        return SimulationResult(
            segments=self.segments,
            stops=self.stops,
            daily_logs=daily_logs,
            midnight_recaps=self.midnight_events + self.cycle.events,
            # dedupe cycle events
            restarts_34h=restarts,
            approximate_routing=approximate_routing,
            summary={
                "total_miles": round(total_miles, 2),
                "total_driving_hours": round(drive_hours, 2),
                "total_on_duty_hours": round(on_hours, 2),
                "days": len(daily_logs),
                "cycle_remaining_at_end": self.cycle.cycle_remaining(
                    self.segments[-1].end_at if self.segments else self.clock
                ),
                "fuel_stops": sum(1 for s in self.stops if s.stop_type == "fuel"),
                "adverse_conditions": self.adverse,
                "max_driving_hours_applied": self.max_drive,
                "max_window_hours_applied": self.max_window,
            },
        )

    def _build_daily_logs(
        self, *, total_miles: float, origin: str, destination: str
    ) -> list[DailyLogSheet]:
        by_day: dict[str, list[DutySegment]] = {}
        for seg in self.segments:
            # Split already done at midnight; bucket by local date of start
            day_key = seg.start_at.astimezone(self.tz).date().isoformat()
            by_day.setdefault(day_key, []).append(seg)

        sheets: list[DailyLogSheet] = []
        day_keys = sorted(by_day.keys())
        miles_per_day = (total_miles / len(day_keys)) if day_keys else 0.0

        for i, day_key in enumerate(day_keys):
            segs = by_day[day_key]
            day_date = segs[0].start_at.astimezone(self.tz).date()
            raw_grid = []
            remarks = []
            for seg in segs:
                if seg.duration_hours <= 1e-9:
                    continue
                local_start = seg.start_at.astimezone(self.tz)
                local_end = seg.end_at.astimezone(self.tz)
                start_hour = local_start.hour + local_start.minute / 60.0 + local_start.second / 3600.0
                end_hour = local_end.hour + local_end.minute / 60.0 + local_end.second / 3600.0
                if local_end.date() > local_start.date():
                    end_hour = 24.0
                elif end_hour <= start_hour + 1e-9:
                    # Zero-length at a clock boundary — skip (never emit 0→24 ghosts)
                    continue
                raw_grid.append(
                    {
                        "status": seg.status.value,
                        "start_hour": round(start_hour, 4),
                        "end_hour": round(end_hour, 4),
                        "remark": seg.remark,
                    }
                )
                if seg.status != DutyStatus.OFF or "break" in seg.remark.lower() or i == 0:
                    remarks.append(
                        {
                            "time": local_start.strftime("%H:%M"),
                            "place": seg.location_label,
                            "note": seg.remark,
                        }
                    )

            grid = normalize_day_segments(raw_grid)
            totals = totals_from_segments(grid)
            # Keep floating error from eating a full status; only nudge OFF if needed
            total_sum = sum(totals.values())
            if abs(total_sum - 24.0) > 0.01:
                totals["off_duty"] = round(totals["off_duty"] + (24.0 - total_sum), 2)

            on_duty_today = round(totals["driving"] + totals["on_duty"], 2)
            sheets.append(
                DailyLogSheet(
                    date=day_key,
                    from_location=origin,
                    to_location=destination,
                    total_miles_driving=round(miles_per_day, 2),
                    segments=grid,
                    totals=totals,
                    remarks=remarks,
                    recap=self.cycle.paper_recap(day_date, on_duty_today),
                )
            )
        return sheets
