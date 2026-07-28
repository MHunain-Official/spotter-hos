"""Trip planning service — geocode, route, simulate HOS, persist."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.drivers.models import Driver
from apps.hos.engine import HosSimulator
from apps.logs.models import DailyLog, LogEntry
from apps.trips.models import Trip, TripStop
from utils.geocode import GeocodeError, geocode
from utils.routing import build_route


class PlanTripError(Exception):
    pass


def _parse_start(value: str | None, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    if value:
        dt = parse_datetime(value)
        if dt is None:
            raise PlanTripError("Invalid trip_start datetime")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.astimezone(tz)
    # Default: today 06:00 local
    now = datetime.now(tz)
    return now.replace(hour=6, minute=0, second=0, microsecond=0)


@transaction.atomic
def plan_trip(payload: dict[str, Any]) -> dict[str, Any]:
    current_q = (payload.get("current_location") or "").strip()
    pickup_q = (payload.get("pickup_location") or "").strip()
    dropoff_q = (payload.get("dropoff_location") or "").strip()
    if not current_q or not pickup_q or not dropoff_q:
        raise PlanTripError("current_location, pickup_location, and dropoff_location are required")

    try:
        used = float(payload.get("current_cycle_used_hours", 0))
    except (TypeError, ValueError) as exc:
        raise PlanTripError("current_cycle_used_hours must be a number") from exc
    if used < 0 or used > 70:
        raise PlanTripError("current_cycle_used_hours must be between 0 and 70")

    tz_name = payload.get("home_terminal_tz") or "America/Chicago"
    adverse = bool(payload.get("adverse_conditions", False))
    auto_34 = bool(payload.get("auto_34h_restart", True))
    trip_start = _parse_start(payload.get("trip_start"), tz_name)

    try:
        current = geocode(current_q)
        pickup = geocode(pickup_q)
        dropoff = geocode(dropoff_q)
    except GeocodeError as exc:
        raise PlanTripError(str(exc)) from exc

    # Prefer short labels for UI
    current["label"] = current_q
    pickup["label"] = pickup_q
    dropoff["label"] = dropoff_q

    routed = build_route(current, pickup, dropoff)
    legs = routed["legs"]
    if len(legs) == 1:
        leg_a_miles, leg_a_hours = 0.0, 0.0
        leg_b_miles, leg_b_hours = legs[0]["miles"], legs[0]["duration_hours"]
    else:
        leg_a_miles, leg_a_hours = legs[0]["miles"], legs[0]["duration_hours"]
        leg_b_miles, leg_b_hours = legs[1]["miles"], legs[1]["duration_hours"]

    simulator = HosSimulator(
        trip_start=trip_start,
        current_cycle_used_hours=used,
        home_terminal_tz=tz_name,
        adverse_conditions=adverse,
        auto_34h_restart=auto_34,
    )
    try:
        result = simulator.run(
            current=current,
            pickup=pickup,
            dropoff=dropoff,
            leg_a_miles=leg_a_miles,
            leg_a_hours=leg_a_hours,
            leg_b_miles=leg_b_miles,
            leg_b_hours=leg_b_hours,
            geometry=routed["geometry"],
            approximate_routing=routed.get("approximate", False),
        )
    except RuntimeError as exc:
        raise PlanTripError(str(exc)) from exc

    driver = Driver.objects.create(
        display_name="RouteLog Driver",
        home_terminal_tz=tz_name,
        current_cycle_used_hours=Decimal(str(round(used, 2))),
    )

    trip = Trip.objects.create(
        driver=driver,
        status=Trip.Status.READY,
        current_address=current_q,
        pickup_address=pickup_q,
        dropoff_address=dropoff_q,
        current_lat=current["lat"],
        current_lng=current["lng"],
        pickup_lat=pickup["lat"],
        pickup_lng=pickup["lng"],
        dropoff_lat=dropoff["lat"],
        dropoff_lng=dropoff["lng"],
        current_cycle_used_hours=Decimal(str(round(used, 2))),
        adverse_conditions=adverse,
        auto_34h_restart=auto_34,
        trip_start_at=trip_start,
        home_terminal_tz=tz_name,
        route_geometry=routed["geometry"],
        summary={
            **result.summary,
            "routing_provider": routed.get("provider", "unknown"),
            "midnight_recaps": [
                {
                    "at": e.at.isoformat(),
                    "dropped_date": e.dropped_date,
                    "dropped_hours": e.dropped_hours,
                    "new_remaining": e.new_remaining,
                }
                for e in result.midnight_recaps
            ],
            "restarts_34h": [
                {"at": e.at.isoformat(), "duration_hours": e.duration_hours}
                for e in result.restarts_34h
            ],
        },
        approximate_routing=result.approximate_routing,
        pdf_status=Trip.PdfStatus.SKIPPED,
    )

    for i, stop in enumerate(result.stops):
        TripStop.objects.create(
            trip=trip,
            stop_type=stop.stop_type,
            label=stop.label,
            lat=stop.lat,
            lng=stop.lng,
            arrive_at=stop.arrive_at,
            depart_at=stop.depart_at,
            sequence=i,
        )

    for seg in result.segments:
        LogEntry.objects.create(
            trip=trip,
            driver=driver,
            status=seg.status.value,
            start_at=seg.start_at,
            end_at=seg.end_at,
            duration_minutes=max(0, int(seg.duration_hours * 60)),
            location_label=seg.location_label,
            lat=seg.lat,
            lng=seg.lng,
            remark=seg.remark,
            is_34h_restart_segment=seg.is_34h_restart_segment,
        )

    daily_payload = []
    for sheet in result.daily_logs:
        DailyLog.objects.create(
            trip=trip,
            log_date=sheet.date,
            from_location=sheet.from_location,
            to_location=sheet.to_location,
            total_miles_driving=Decimal(str(sheet.total_miles_driving)),
            grid_segments=sheet.segments,
            totals=sheet.totals,
            remarks=sheet.remarks,
            recap=sheet.recap,
        )
        daily_payload.append(
            {
                "date": sheet.date,
                "from_location": sheet.from_location,
                "to_location": sheet.to_location,
                "total_miles_driving": sheet.total_miles_driving,
                "segments": sheet.segments,
                "totals": sheet.totals,
                "remarks": sheet.remarks,
                "recap": sheet.recap,
            }
        )

    driver.current_cycle_used_hours = Decimal(
        str(round(70 - result.summary.get("cycle_remaining_at_end", 0), 2))
    )
    driver.save(update_fields=["current_cycle_used_hours", "updated_at"])

    # Generate paper-style daily log PDF report
    try:
        from apps.logs.pdf import generate_and_store_trip_pdf

        generate_and_store_trip_pdf(trip)
        trip.refresh_from_db()
    except Exception:  # noqa: BLE001
        trip.pdf_status = Trip.PdfStatus.FAILED
        trip.save(update_fields=["pdf_status", "updated_at"])

    return serialize_trip(trip, daily_payload=daily_payload)


def serialize_trip(trip: Trip, daily_payload: list | None = None) -> dict[str, Any]:
    if daily_payload is None:
        daily_payload = [
            {
                "date": d.log_date.isoformat(),
                "from_location": d.from_location,
                "to_location": d.to_location,
                "total_miles_driving": float(d.total_miles_driving),
                "segments": d.grid_segments,
                "totals": d.totals,
                "remarks": d.remarks,
                "recap": d.recap,
            }
            for d in trip.daily_logs.all()
        ]

    stops = [
        {
            "type": s.stop_type,
            "label": s.label,
            "lat": s.lat,
            "lng": s.lng,
            "arrive_at": s.arrive_at.isoformat(),
            "depart_at": s.depart_at.isoformat(),
            "duration_hours": round((s.depart_at - s.arrive_at).total_seconds() / 3600.0, 2),
        }
        for s in trip.stops.all()
    ]

    summary = dict(trip.summary or {})
    return {
        "id": str(trip.id),
        "status": trip.status,
        "pdf_status": trip.pdf_status,
        "pdf_url": trip.pdf_file.url if trip.pdf_file else None,
        "approximate_routing": trip.approximate_routing,
        "routing_provider": (trip.summary or {}).get("routing_provider"),
        "adverse_conditions": trip.adverse_conditions,
        "home_terminal_tz": trip.home_terminal_tz,
        "summary": summary,
        "route": {
            "geometry": trip.route_geometry,
            "legs": [],
        },
        "stops": stops,
        "daily_logs": daily_payload,
        "inputs": {
            "current_location": trip.current_address,
            "pickup_location": trip.pickup_address,
            "dropoff_location": trip.dropoff_address,
            "current_cycle_used_hours": float(trip.current_cycle_used_hours),
            "trip_start": trip.trip_start_at.isoformat(),
        },
    }
