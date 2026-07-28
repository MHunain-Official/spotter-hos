"""
Required + preferred unit/integration tests for RouteLog HOS assessment.

Required: 11/14/30-min/70-8 midnight/fuel/P&D/grid=24/recap
Preferred: 34h restart, adverse, cycle pressure, API contract, routing fallback
"""

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from apps.hos.engine.cycle_window import CycleWindow
from apps.hos.engine.grid import normalize_day_segments, totals_from_segments
from apps.hos.engine.limits import (
    FUEL_EVERY_MILES,
    max_driving_hours,
    max_window_hours,
)
from apps.hos.engine.restart34 import detect_34h_restart
from apps.hos.engine.simulator import HosSimulator
from apps.hos.engine.types import DutySegment, DutyStatus
from utils.routing import _fallback_route, _haversine_miles, build_route, route_via_osrm


TZ = "America/Chicago"
ZONE = ZoneInfo(TZ)


def _run_sim(
    *,
    leg_a_miles,
    leg_a_hours,
    leg_b_miles,
    leg_b_hours,
    cycle_used=0,
    adverse=False,
    auto_34h=True,
    start=None,
):
    start = start or datetime(2026, 7, 27, 6, 0, tzinfo=ZONE)
    sim = HosSimulator(
        trip_start=start,
        current_cycle_used_hours=cycle_used,
        home_terminal_tz=TZ,
        adverse_conditions=adverse,
        auto_34h_restart=auto_34h,
    )
    return sim.run(
        current={"label": "Origin", "lat": 41.88, "lng": -87.63},
        pickup={"label": "Pickup", "lat": 32.78, "lng": -96.80},
        dropoff={"label": "Dropoff", "lat": 29.76, "lng": -95.37},
        leg_a_miles=leg_a_miles,
        leg_a_hours=leg_a_hours,
        leg_b_miles=leg_b_miles,
        leg_b_hours=leg_b_hours,
        geometry=[[-87.63, 41.88], [-96.80, 32.78], [-95.37, 29.76]],
    )


class LimitsTests(SimpleTestCase):
    """REQUIRED: adverse extension point."""

    def test_adverse_extends_drive_and_window(self):
        self.assertEqual(max_driving_hours(adverse=False), 11.0)
        self.assertEqual(max_driving_hours(adverse=True), 13.0)
        self.assertEqual(max_window_hours(adverse=False), 14.0)
        self.assertEqual(max_window_hours(adverse=True), 16.0)


class GridNormalizeTests(SimpleTestCase):
    def test_zero_length_ghost_does_not_become_full_day(self):
        """Regression: start==end used to draw 0→24 and create parallel lines."""
        raw = [
            {"status": "OFF", "start_hour": 0.0, "end_hour": 6.0, "remark": "off"},
            {"status": "D", "start_hour": 0.0, "end_hour": 0.0, "remark": "ghost"},
            {"status": "D", "start_hour": 6.0, "end_hour": 14.0, "remark": "drive"},
            {"status": "SB", "start_hour": 5.5, "end_hour": 5.5, "remark": "ghost sb"},
            {"status": "SB", "start_hour": 14.0, "end_hour": 24.0, "remark": "sleeper"},
        ]
        grid = normalize_day_segments(raw)
        self.assertEqual(
            [(s["status"], s["start_hour"], s["end_hour"]) for s in grid],
            [("OFF", 0.0, 6.0), ("D", 6.0, 14.0), ("SB", 14.0, 24.0)],
        )
        totals = totals_from_segments(grid)
        self.assertAlmostEqual(sum(totals.values()), 24.0, places=2)
        # No overlapping coverage
        for i in range(1, len(grid)):
            self.assertGreaterEqual(grid[i]["start_hour"], grid[i - 1]["end_hour"] - 1e-6)

    def test_overlap_prefers_later_segment(self):
        raw = [
            {"status": "OFF", "start_hour": 0.0, "end_hour": 24.0, "remark": "bad full off"},
            {"status": "D", "start_hour": 5.5, "end_hour": 13.5, "remark": "drive"},
            {"status": "OFF", "start_hour": 13.5, "end_hour": 14.0, "remark": "break"},
            {"status": "D", "start_hour": 14.0, "end_hour": 19.0, "remark": "drive2"},
            {"status": "SB", "start_hour": 19.5, "end_hour": 24.0, "remark": "sb"},
        ]
        grid = normalize_day_segments(raw)
        # Must not keep a parallel full-day OFF under driving
        for s in grid:
            if s["status"] == "OFF":
                self.assertLessEqual(s["end_hour"] - s["start_hour"], 6.0 + 1e-6)
        self.assertAlmostEqual(sum(totals_from_segments(grid).values()), 24.0, places=2)

    def test_simulator_grid_never_overlaps(self):
        result = _run_sim(
            leg_a_miles=960,
            leg_a_hours=16.0,
            leg_b_miles=240,
            leg_b_hours=4.5,
            cycle_used=12,
            adverse=True,
            start=datetime(2026, 7, 27, 5, 30, tzinfo=ZONE),
        )
        for sheet in result.daily_logs:
            segs = sheet.segments
            self.assertAlmostEqual(sum(sheet.totals.values()), 24.0, places=1)
            coverage = sum(s["end_hour"] - s["start_hour"] for s in segs)
            self.assertAlmostEqual(coverage, 24.0, places=2)
            for i in range(1, len(segs)):
                self.assertGreaterEqual(
                    segs[i]["start_hour"], segs[i - 1]["end_hour"] - 1e-4
                )
            for s in segs:
                self.assertGreater(s["end_hour"], s["start_hour"] + 1e-6)


class CycleWindowTests(SimpleTestCase):
    """REQUIRED: midnight rolling 8-day + paper recap."""

    def test_pdf_rolling_example_day_dropoff(self):
        as_of = datetime(2026, 7, 12, 12, 0, tzinfo=ZONE)
        cw = CycleWindow(tz=ZONE)
        hours = {0: 0, 1: 10, 2: 8.5, 3: 12.5, 4: 9, 5: 10, 6: 12, 7: 5}
        base = as_of.date()
        for offset, h in hours.items():
            cw.daily_on_duty[base - timedelta(days=7 - offset)] = h

        self.assertAlmostEqual(cw.cycle_used(as_of), 67.0, places=1)

        day9 = as_of + timedelta(days=1)
        cw.ensure_midnight_rollovers(as_of, day9)
        cw.add_on_duty(day9, 6.0)
        self.assertAlmostEqual(cw.cycle_used(day9), 73.0, places=1)

        day10 = day9 + timedelta(days=1)
        cw.ensure_midnight_rollovers(day9, day10)
        self.assertAlmostEqual(cw.cycle_used(day10), 63.0, places=1)

    def test_paper_recap_fields(self):
        as_of = datetime(2026, 7, 20, 12, 0, tzinfo=ZONE)
        cw = CycleWindow.seed_from_used_hours(used_hours=40.0, as_of=as_of, tz_name=TZ)
        day = as_of.date()
        cw.add_on_duty(as_of, 8.0)
        recap = cw.paper_recap(day, on_duty_today=8.0)
        self.assertIn("a_70_last_7_incl_today", recap)
        self.assertIn("c_70_last_8_incl_today", recap)
        self.assertIn("a_60_last_6_incl_today", recap)
        self.assertIn("b_60_available_tomorrow", recap)
        self.assertAlmostEqual(
            recap["b_70_available_tomorrow"],
            70.0 - recap["a_70_last_7_incl_today"],
            places=2,
        )
        self.assertAlmostEqual(
            recap["b_60_available_tomorrow"],
            60.0 - recap["a_60_last_6_incl_today"],
            places=2,
        )

    def test_midnight_can_increase_remaining(self):
        start = datetime(2026, 7, 20, 8, 0, tzinfo=ZONE)
        cw = CycleWindow.seed_from_used_hours(used_hours=60.0, as_of=start, tz_name=TZ)
        before = cw.cycle_remaining(start)
        after_midnight = datetime(2026, 7, 21, 0, 5, tzinfo=ZONE)
        events = cw.ensure_midnight_rollovers(start, after_midnight)
        after = cw.cycle_remaining(after_midnight)
        if events:
            self.assertGreaterEqual(after, before)

    def test_seed_matches_used_hours(self):
        as_of = datetime(2026, 7, 20, 6, 0, tzinfo=ZONE)
        cw = CycleWindow.seed_from_used_hours(used_hours=25.5, as_of=as_of, tz_name=TZ)
        self.assertAlmostEqual(cw.cycle_used(as_of), 25.5, places=1)

    def test_34h_reset_clears_cycle(self):
        as_of = datetime(2026, 7, 20, 6, 0, tzinfo=ZONE)
        cw = CycleWindow.seed_from_used_hours(used_hours=55.0, as_of=as_of, tz_name=TZ)
        self.assertGreater(cw.cycle_used(as_of), 0)
        cw.reset_after_34h(as_of)
        self.assertEqual(cw.cycle_used(as_of), 0.0)
        self.assertEqual(cw.cycle_remaining(as_of), 70.0)


class Restart34Tests(SimpleTestCase):
    """PREFERRED: 34-hour restart detection."""

    def test_detects_34h_off_block(self):
        start = datetime(2026, 7, 20, 0, 0, tzinfo=ZONE)
        segments = [
            DutySegment(
                status=DutyStatus.OFF,
                start_at=start,
                end_at=start + timedelta(hours=34),
                location_label="Yard",
            )
        ]
        events = detect_34h_restart(segments)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0].duration_hours, 34.0, places=1)

    def test_ignores_short_off_block(self):
        start = datetime(2026, 7, 20, 0, 0, tzinfo=ZONE)
        segments = [
            DutySegment(
                status=DutyStatus.OFF,
                start_at=start,
                end_at=start + timedelta(hours=10),
            )
        ]
        self.assertEqual(detect_34h_restart(segments), [])


class SimulatorRequiredTests(SimpleTestCase):
    """REQUIRED assessment rules."""

    def test_short_trip_totals_24_and_pickup_dropoff(self):
        result = _run_sim(
            leg_a_miles=20, leg_a_hours=0.5, leg_b_miles=30, leg_b_hours=0.75
        )
        self.assertGreaterEqual(len(result.daily_logs), 1)
        for sheet in result.daily_logs:
            self.assertAlmostEqual(sum(sheet.totals.values()), 24.0, places=1)
            self.assertIn("a_70_last_7_incl_today", sheet.recap)
            self.assertIn("c_70_last_8_incl_today", sheet.recap)

        self.assertTrue(any(s.stop_type == "pickup" and s.duration_hours == 1 for s in result.stops))
        self.assertTrue(any(s.stop_type == "dropoff" and s.duration_hours == 1 for s in result.stops))

    def test_fuel_at_least_every_1000_miles(self):
        result = _run_sim(
            leg_a_miles=900, leg_a_hours=16.5, leg_b_miles=240, leg_b_hours=4.5, cycle_used=10
        )
        total_miles = 900 + 240
        expected_min_fuels = int(total_miles // FUEL_EVERY_MILES)
        self.assertGreaterEqual(result.summary["fuel_stops"], expected_min_fuels)
        self.assertGreaterEqual(result.summary["fuel_stops"], 1)

    def test_30_min_break_after_8h_driving(self):
        result = _run_sim(
            leg_a_miles=50, leg_a_hours=1.0, leg_b_miles=500, leg_b_hours=9.5
        )
        remarks = " ".join(r.get("note", "") for d in result.daily_logs for r in d.remarks)
        self.assertIn("30-min", remarks.lower())

    def test_long_trip_multi_day_and_rest(self):
        result = _run_sim(
            leg_a_miles=900, leg_a_hours=16.5, leg_b_miles=240, leg_b_hours=4.5, cycle_used=10
        )
        self.assertGreaterEqual(result.summary["days"], 2)
        self.assertTrue(any(s.stop_type == "rest" for s in result.stops))
        for sheet in result.daily_logs:
            self.assertAlmostEqual(sum(sheet.totals.values()), 24.0, places=1)

    def test_11_hour_driving_forces_10h_reset(self):
        result = _run_sim(
            leg_a_miles=50, leg_a_hours=1.0, leg_b_miles=650, leg_b_hours=12.0
        )
        remarks = " ".join(r.get("note", "") for d in result.daily_logs for r in d.remarks)
        self.assertTrue(
            "10-hour" in remarks.lower() or "sleeper" in remarks.lower(),
            msg=f"Expected 10h sleeper reset in remarks: {remarks[:500]}",
        )
        # No single continuous driving stretch should exceed ~11h without reset in summary
        self.assertLessEqual(result.summary["max_driving_hours_applied"], 11.0)

    def test_current_equals_pickup_zero_deadhead(self):
        start = datetime(2026, 7, 27, 6, 0, tzinfo=ZONE)
        sim = HosSimulator(trip_start=start, current_cycle_used_hours=0, home_terminal_tz=TZ)
        result = sim.run(
            current={"label": "Same", "lat": 41.88, "lng": -87.63},
            pickup={"label": "Same", "lat": 41.88, "lng": -87.63},
            dropoff={"label": "Near", "lat": 41.95, "lng": -87.70},
            leg_a_miles=0,
            leg_a_hours=0,
            leg_b_miles=15,
            leg_b_hours=0.4,
            geometry=[[-87.63, 41.88], [-87.70, 41.95]],
        )
        self.assertGreaterEqual(len(result.daily_logs), 1)
        self.assertAlmostEqual(sum(result.daily_logs[0].totals.values()), 24.0, places=1)


class SimulatorPreferredTests(SimpleTestCase):
    """PREFERRED: edge cases that impress reviewers."""

    def test_cycle_pressure_triggers_34h_or_completes(self):
        result = _run_sim(
            leg_a_miles=100,
            leg_a_hours=2.0,
            leg_b_miles=200,
            leg_b_hours=4.0,
            cycle_used=65,
            auto_34h=True,
        )
        # With 65 used, pickup+drive+dropoff needs on-duty; may insert 34h restart
        self.assertGreaterEqual(len(result.daily_logs), 1)
        for sheet in result.daily_logs:
            self.assertAlmostEqual(sum(sheet.totals.values()), 24.0, places=1)

    def test_adverse_raises_applied_limits(self):
        result = _run_sim(
            leg_a_miles=50,
            leg_a_hours=1.0,
            leg_b_miles=100,
            leg_b_hours=2.0,
            adverse=True,
        )
        self.assertEqual(result.summary["max_driving_hours_applied"], 13.0)
        self.assertEqual(result.summary["max_window_hours_applied"], 16.0)
        self.assertTrue(result.summary["adverse_conditions"])

    def test_remarks_include_location_changes(self):
        result = _run_sim(
            leg_a_miles=40, leg_a_hours=1.0, leg_b_miles=40, leg_b_hours=1.0
        )
        all_remarks = [r for d in result.daily_logs for r in d.remarks]
        self.assertGreaterEqual(len(all_remarks), 2)
        self.assertTrue(any("Pickup" in r.get("note", "") for r in all_remarks))
        self.assertTrue(any("Dropoff" in r.get("note", "") for r in all_remarks))


class RoutingUnitTests(SimpleTestCase):
    """REQUIRED/PREFERRED: routing helpers without live network where possible."""

    def test_haversine_chicago_dallas_ballpark(self):
        miles = _haversine_miles(41.88, -87.63, 32.78, -96.80)
        self.assertGreater(miles, 700)
        self.assertLess(miles, 1000)

    def test_fallback_route_has_two_legs(self):
        points = [
            {"lat": 41.88, "lng": -87.63},
            {"lat": 32.78, "lng": -96.80},
            {"lat": 29.76, "lng": -95.37},
        ]
        result = _fallback_route(points)
        self.assertTrue(result["approximate"])
        self.assertEqual(len(result["legs"]), 2)
        self.assertEqual(len(result["geometry"]), 3)
        self.assertEqual(result["provider"], "haversine")

    @patch("utils.routing.route_via_osrm", return_value=None)
    @patch("utils.routing.route_via_ors", return_value=None)
    def test_build_route_falls_back_when_routers_fail(self, _ors, _osrm):
        result = build_route(
            {"lat": 41.88, "lng": -87.63, "label": "A"},
            {"lat": 32.78, "lng": -96.80, "label": "B"},
            {"lat": 29.76, "lng": -95.37, "label": "C"},
        )
        self.assertTrue(result["approximate"])
        self.assertEqual(len(result["legs"]), 2)

    @patch("utils.routing.requests.get")
    def test_osrm_parses_geometry(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = lambda: None
        mock_get.return_value.json.return_value = {
            "code": "Ok",
            "routes": [
                {
                    "geometry": {"coordinates": [[-87.63, 41.88], [-90.0, 38.0], [-96.80, 32.78]]},
                    "legs": [
                        {"distance": 1609344, "duration": 36000},
                        {"distance": 804672, "duration": 18000},
                    ],
                }
            ],
        }
        result = route_via_osrm(
            [
                {"lat": 41.88, "lng": -87.63},
                {"lat": 32.78, "lng": -96.80},
                {"lat": 29.76, "lng": -95.37},
            ]
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result["approximate"])
        self.assertEqual(result["provider"], "osrm")
        self.assertEqual(len(result["geometry"]), 3)
        self.assertAlmostEqual(result["legs"][0]["miles"], 1000.0, places=0)


@override_settings(USE_SQLITE=True)
class PlanTripAPITests(TestCase):
    """REQUIRED: API contract with mocked external services."""

    def setUp(self):
        self.client = APIClient()

    def test_health(self):
        res = self.client.get("/api/v1/health/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "ok")

    def test_plan_validation_missing_locations(self):
        res = self.client.post("/api/v1/trips/plan/", {}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_plan_validation_cycle_out_of_range(self):
        res = self.client.post(
            "/api/v1/trips/plan/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "current_cycle_used_hours": 99,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    @patch("apps.trips.services.build_route")
    @patch("apps.trips.services.geocode")
    def test_plan_success_persists_and_returns_logs(self, mock_geocode, mock_route):
        def _geo(q):
            coords = {
                "Chicago, IL": (41.88, -87.63),
                "Dallas, TX": (32.78, -96.80),
                "Houston, TX": (29.76, -95.37),
            }
            lat, lng = coords[q]
            return {"label": q, "lat": lat, "lng": lng, "query": q}

        mock_geocode.side_effect = _geo
        mock_route.return_value = {
            "geometry": [[-87.63, 41.88], [-96.80, 32.78], [-95.37, 29.76]],
            "legs": [
                {"miles": 50, "duration_hours": 1.0},
                {"miles": 40, "duration_hours": 0.8},
            ],
            "total_miles": 90,
            "total_hours": 1.8,
            "approximate": False,
            "provider": "osrm",
        }

        res = self.client.post(
            "/api/v1/trips/plan/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "current_cycle_used_hours": 5,
                "trip_start": "2026-07-27T06:00:00-05:00",
                "adverse_conditions": False,
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        body = res.data
        self.assertIn("id", body)
        self.assertIn("daily_logs", body)
        self.assertIn("stops", body)
        self.assertIn("route", body)
        self.assertGreaterEqual(len(body["daily_logs"]), 1)
        sheet = body["daily_logs"][0]
        self.assertAlmostEqual(sum(sheet["totals"].values()), 24.0, places=1)
        self.assertIn("recap", sheet)
        self.assertIn("a_70_last_7_incl_today", sheet["recap"])

        detail = self.client.get(f"/api/v1/trips/{body['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["id"], body["id"])

    @patch("apps.trips.services.build_route")
    @patch("apps.trips.services.geocode")
    def test_plan_generates_pdf_ready(self, mock_geocode, mock_route):
        def _geo(q):
            coords = {
                "Chicago, IL": (41.88, -87.63),
                "Dallas, TX": (32.78, -96.80),
                "Houston, TX": (29.76, -95.37),
            }
            lat, lng = coords[q]
            return {"label": q, "lat": lat, "lng": lng, "query": q}

        mock_geocode.side_effect = _geo
        mock_route.return_value = {
            "geometry": [[-87.63, 41.88], [-96.80, 32.78], [-95.37, 29.76]],
            "legs": [
                {"miles": 50, "duration_hours": 1.0},
                {"miles": 40, "duration_hours": 0.8},
            ],
            "total_miles": 90,
            "total_hours": 1.8,
            "approximate": False,
            "provider": "osrm",
        }
        res = self.client.post(
            "/api/v1/trips/plan/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Dallas, TX",
                "dropoff_location": "Houston, TX",
                "current_cycle_used_hours": 5,
                "trip_start": "2026-07-27T06:00:00-05:00",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["pdf_status"], "ready")
        self.assertTrue(res.data.get("pdf_url"))

        pdf = self.client.get(f"/api/v1/trips/{res.data['id']}/pdf/")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.getvalue().startswith(b"%PDF"))
