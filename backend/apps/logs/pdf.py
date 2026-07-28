"""Generate Drivers Daily Log PDF report (paper-form style) with ReportLab."""

from __future__ import annotations

import io
from typing import Any

from django.core.files.base import ContentFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from apps.hos.engine.grid import normalize_day_segments
from apps.trips.models import Trip


ROW_LABELS = [
    ("OFF", "1. Off Duty", "off_duty"),
    ("SB", "2. Sleeper Berth", "sleeper"),
    ("D", "3. Driving", "driving"),
    ("ON", "4. On Duty (not driving)", "on_duty"),
]


def _hour_x(grid_x: float, grid_w: float, hour: float) -> float:
    return grid_x + (max(0.0, min(24.0, hour)) / 24.0) * grid_w


def _draw_daily_log_page(
    c: canvas.Canvas,
    *,
    page_w: float,
    page_h: float,
    log: dict[str, Any],
    trip: Trip,
    page_index: int,
    page_count: int,
) -> None:
    margin = 0.5 * inch
    y = page_h - margin

    # Header
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Drivers Daily Log (24 hours)")
    c.setFont("Helvetica", 8)
    c.drawRightString(
        page_w - margin,
        y + 4,
        "Original — File at home terminal. Duplicate — retain 8 days.",
    )
    y -= 18

    # Date boxes
    date = str(log.get("date", ""))
    parts = date.split("-")
    year, month, day = (parts + ["", "", ""])[:3] if len(parts) >= 3 else ("", "", "")
    c.setFont("Helvetica", 9)
    box_x = page_w / 2 - 70
    for label, val, w in (("month", month, 36), ("day", day, 36), ("year", year, 48)):
        c.rect(box_x, y - 2, w, 14, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(box_x + w / 2, y + 1, val)
        c.setFont("Helvetica", 7)
        c.drawCentredString(box_x + w / 2, y - 12, f"({label})")
        box_x += w + 8
    y -= 28

    # From / To
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, "From:")
    c.line(margin + 32, y - 2, page_w - margin, y - 2)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 36, y, str(log.get("from_location") or trip.current_address))
    y -= 16
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, "To:")
    c.line(margin + 22, y - 2, page_w - margin, y - 2)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin + 26, y, str(log.get("to_location") or trip.dropoff_address))
    y -= 20

    # Miles / vehicle boxes
    miles = float(log.get("total_miles_driving") or 0)
    box_h = 36
    box1_w = 1.5 * inch
    box2_w = 1.5 * inch
    box3_w = page_w - 2 * margin - box1_w - box2_w - 16
    x = margin
    for w, title, value in (
        (box1_w, "Total Miles Driving Today", f"{miles:.1f}"),
        (box2_w, "Total Mileage Today", f"{miles:.1f}"),
        (box3_w, "Truck/Tractor and Trailer Numbers", "UNIT-RL-001 / TRL-4821 IL"),
    ):
        c.rect(x, y - box_h, w, box_h, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x + 4, y - 16, value)
        c.setFont("Helvetica", 6.5)
        c.drawString(x + 4, y - box_h + 4, title)
        x += w + 8
    y -= box_h + 14

    # Carrier lines
    c.setFont("Helvetica", 9)
    for label, value in (
        ("Name of Carrier or Carriers", "RouteLog Demo Carrier"),
        ("Main Office Address", "100 Dispatch Way, Chicago, IL"),
        ("Home Terminal Address", f"Home terminal · {trip.home_terminal_tz}"),
    ):
        c.line(margin, y - 2, page_w - margin, y - 2)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin + 2, y, value)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.grey)
        c.drawString(margin + 2, y - 11, label)
        c.setFillColor(colors.black)
        y -= 20

    y -= 6

    # Duty grid
    label_w = 1.55 * inch
    totals_w = 0.7 * inch
    grid_x = margin + label_w
    grid_w = page_w - 2 * margin - label_w - totals_w
    header_h = 16
    row_h = 22
    grid_h = row_h * 4

    # Black header
    c.setFillColor(colors.black)
    c.rect(grid_x, y - header_h, grid_w, header_h, stroke=0, fill=1)
    c.rect(grid_x + grid_w, y - header_h, totals_w, header_h, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 6)
    labels = ["Mid", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11",
              "Noon", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
    for i, lab in enumerate(labels):
        c.drawCentredString(grid_x + (i + 0.5) * (grid_w / 24), y - 11, lab)
    c.drawCentredString(grid_x + grid_w + totals_w / 2, y - 11, "Total")
    c.setFillColor(colors.black)

    totals = log.get("totals") or {}
    grid_top = y - header_h

    for i, (_code, label, key) in enumerate(ROW_LABELS):
        row_top = grid_top - i * row_h
        row_bottom = row_top - row_h
        # Alternating row bg
        if i % 2 == 0:
            c.setFillColor(colors.Color(0.96, 0.96, 0.96))
            c.rect(margin, row_bottom, page_w - 2 * margin, row_h, stroke=0, fill=1)
            c.setFillColor(colors.black)
        c.rect(margin, row_bottom, page_w - 2 * margin, row_h, stroke=1, fill=0)
        c.setFont("Helvetica", 8)
        c.drawString(margin + 4, row_bottom + 7, label)
        # hour ticks
        for h in range(25):
            xh = _hour_x(grid_x, grid_w, h)
            c.setStrokeColor(colors.Color(0.3, 0.3, 0.3))
            c.setLineWidth(0.8 if h % 6 == 0 else 0.4)
            c.line(xh, row_bottom, xh, row_top)
            if h < 24:
                for q in (1, 2, 3):
                    xq = _hour_x(grid_x, grid_w, h + q * 0.25)
                    c.setStrokeColor(colors.Color(0.7, 0.7, 0.7))
                    c.setLineWidth(0.3)
                    c.line(xq, row_bottom, xq, row_bottom + row_h * 0.55)
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        val = float(totals.get(key) or 0)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(grid_x + grid_w + totals_w / 2, row_bottom + 7, f"{val:.2f}")

    # Duty polyline — merged, non-overlapping, single continuous stroke
    segments = normalize_day_segments(log.get("segments") or [])
    status_row = {"OFF": 0, "SB": 1, "D": 2, "ON": 3}
    c.setStrokeColor(colors.black)
    c.setLineWidth(2.0)
    c.setLineCap(1)  # round
    c.setLineJoin(1)
    path_started = False
    p = c.beginPath()
    for seg in segments:
        status = seg.get("status", "OFF")
        row_i = status_row.get(status, 0)
        y_line = grid_top - row_i * row_h - row_h / 2
        x0 = _hour_x(grid_x, grid_w, float(seg.get("start_hour", 0)))
        x1 = _hour_x(grid_x, grid_w, float(seg.get("end_hour", 0)))
        if not path_started:
            p.moveTo(x0, y_line)
            path_started = True
        else:
            p.lineTo(x0, y_line)
        p.lineTo(x1, y_line)
    if path_started:
        c.drawPath(p, stroke=1, fill=0)

    # Outer grid border
    c.setLineWidth(1.2)
    c.rect(grid_x, grid_top - grid_h, grid_w, grid_h, stroke=1, fill=0)

    total_sum = sum(float(totals.get(k) or 0) for _, _, k in ROW_LABELS)
    c.setFont("Helvetica", 8)
    c.drawCentredString(
        grid_x + grid_w + totals_w / 2,
        grid_top - grid_h - 10,
        f"={total_sum:.1f}",
    )

    y = grid_top - grid_h - 24

    # Remarks
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Remarks")
    y -= 4
    c.rect(margin, y - 95, page_w - 2 * margin, 95, stroke=1, fill=0)
    c.setFont("Helvetica", 7)
    c.drawString(margin + 6, y - 12, "Shipping Documents:  DVL/Manifest  RL-" + date.replace("-", ""))
    c.drawString(margin + 6, y - 24, "Shipper & Commodity: General freight")
    remarks = log.get("remarks") or []
    ry = y - 38
    c.setFont("Helvetica", 7)
    for r in remarks[:8]:
        line = f"{r.get('time', '')}  {r.get('place', '')} — {r.get('note', '')}"
        if len(line) > 110:
            line = line[:107] + "..."
        c.drawString(margin + 6, ry, line)
        ry -= 9
        if ry < y - 88:
            break
    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColor(colors.grey)
    c.drawCentredString(
        page_w / 2,
        y - 92,
        f"Use time standard of home terminal ({trip.home_terminal_tz}).",
    )
    c.setFillColor(colors.black)
    y -= 110

    # Recap
    recap = log.get("recap") or {}
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Recap: Complete at end of day")
    y -= 14
    on_today = float(recap.get("on_duty_today") or (float(totals.get("driving") or 0) + float(totals.get("on_duty") or 0)))
    c.setFont("Helvetica", 8)
    c.drawString(margin, y, "On duty hours today, Total lines 3 & 4")
    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(page_w - margin, y, f"{on_today:.2f}")
    y -= 12

    col_w = (page_w - 2 * margin - 8) / 2
    for col_i, (title, rows) in enumerate(
        (
            (
                "70 Hour / 8 Day Drivers",
                [
                    ("A. Last 7 days incl. today", recap.get("a_70_last_7_incl_today") or recap.get("a_last_7_including_today")),
                    ("B. Available tomorrow (70−A)", recap.get("b_70_available_tomorrow") or recap.get("b_available_tomorrow")),
                    ("C. Last 8 days incl. today", recap.get("c_70_last_8_incl_today") or recap.get("cycle_used_8_day")),
                ],
            ),
            (
                "60 Hour / 7 Day Drivers",
                [
                    ("A. Last 6 days incl. today", recap.get("a_60_last_6_incl_today")),
                    ("B. Available tomorrow (60−A)", recap.get("b_60_available_tomorrow")),
                    ("C. Last 7 days incl. today", recap.get("c_60_last_7_incl_today")),
                ],
            ),
        )
    ):
        cx = margin + col_i * (col_w + 8)
        c.rect(cx, y - 48, col_w, 52, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(cx + 4, y - 10, title)
        c.setFont("Helvetica", 7)
        ry = y - 22
        for label, val in rows:
            c.drawString(cx + 4, ry, label)
            c.setFont("Helvetica-Bold", 8)
            c.drawRightString(cx + col_w - 4, ry, f"{float(val or 0):.2f}")
            c.setFont("Helvetica", 7)
            ry -= 11

    y -= 62
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawString(
        margin,
        y,
        "*If you took 34 consecutive hours off duty you have 60/70 hours available.",
    )
    c.setFillColor(colors.black)

    # Footer
    c.setFont("Helvetica", 7)
    c.drawString(margin, 0.4 * inch, f"RouteLog · Trip {trip.id}")
    c.drawRightString(page_w - margin, 0.4 * inch, f"Page {page_index}/{page_count}")
    summary = trip.summary or {}
    c.drawCentredString(
        page_w / 2,
        0.4 * inch,
        f"{summary.get('total_miles', '—')} mi · {summary.get('total_driving_hours', '—')}h drive",
    )


def build_trip_pdf_bytes(trip: Trip) -> bytes:
    """Render multi-page PDF; one page per daily log."""
    logs = list(trip.daily_logs.all().order_by("log_date"))
    if not logs:
        raise ValueError("Trip has no daily logs to render")

    buffer = io.BytesIO()
    page_w, page_h = letter
    c = canvas.Canvas(buffer, pagesize=letter)

    # Cover / summary page if multiple days
    c.setFont("Helvetica-Bold", 20)
    c.drawString(0.75 * inch, page_h - inch, "RouteLog — HOS Trip Report")
    c.setFont("Helvetica", 11)
    c.drawString(0.75 * inch, page_h - 1.35 * inch, f"Trip ID: {trip.id}")
    c.drawString(0.75 * inch, page_h - 1.55 * inch, f"From: {trip.current_address}")
    c.drawString(0.75 * inch, page_h - 1.75 * inch, f"Pickup: {trip.pickup_address}")
    c.drawString(0.75 * inch, page_h - 1.95 * inch, f"Dropoff: {trip.dropoff_address}")
    summary = trip.summary or {}
    y = page_h - 2.4 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(0.75 * inch, y, "Summary")
    y -= 18
    c.setFont("Helvetica", 10)
    for label, key in (
        ("Total miles", "total_miles"),
        ("Driving hours", "total_driving_hours"),
        ("On-duty hours", "total_on_duty_hours"),
        ("Log days", "days"),
        ("Fuel stops", "fuel_stops"),
        ("Cycle remaining", "cycle_remaining_at_end"),
    ):
        c.drawString(0.75 * inch, y, f"{label}: {summary.get(key, '—')}")
        y -= 14
    c.setFont("Helvetica", 9)
    c.drawString(0.75 * inch, y - 10, f"Home terminal TZ: {trip.home_terminal_tz}")
    c.drawString(
        0.75 * inch,
        y - 24,
        f"Routing: {'approximate' if trip.approximate_routing else 'OSRM road network'}",
    )
    c.drawString(0.75 * inch, y - 38, f"Adverse conditions: {trip.adverse_conditions}")
    c.showPage()

    payload_logs = [
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
        for d in logs
    ]
    n = len(payload_logs)
    for i, log in enumerate(payload_logs, start=1):
        _draw_daily_log_page(
            c,
            page_w=page_w,
            page_h=page_h,
            log=log,
            trip=trip,
            page_index=i,
            page_count=n,
        )
        c.showPage()

    c.save()
    return buffer.getvalue()


def generate_and_store_trip_pdf(trip: Trip) -> Trip:
    """Build PDF, attach to trip, mark ready."""
    trip.pdf_status = Trip.PdfStatus.PROCESSING
    trip.save(update_fields=["pdf_status", "updated_at"])
    try:
        pdf_bytes = build_trip_pdf_bytes(trip)
        filename = f"routelog-trip-{trip.id}.pdf"
        trip.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
        trip.pdf_status = Trip.PdfStatus.READY
        trip.save(update_fields=["pdf_file", "pdf_status", "updated_at"])
    except Exception:
        trip.pdf_status = Trip.PdfStatus.FAILED
        trip.save(update_fields=["pdf_status", "updated_at"])
        raise
    return trip
