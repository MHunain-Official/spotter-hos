# Business Rules & SDLC Checklist

## Assessment requirements → implementation

| Requirement | Status | Where |
|-------------|--------|--------|
| Django + React | ✅ | `backend/`, `frontend/` |
| Inputs: current, pickup, dropoff, cycle used | ✅ | `PlanTripSerializer`, TripPlanForm |
| Map with route + stops/rests | ✅ | ORS/OSRM geometry + custom markers |
| Multi-day drawn daily logs | ✅ | `DailyLogSheet` paper form |
| Property-carrying 70h/8-day | ✅ | `CycleWindow`, simulator |
| Fuel ≤ every 1,000 miles | ✅ | `FUEL_EVERY_MILES` + fuel stops |
| 1h pickup + 1h dropoff on-duty | ✅ | `PICKUP_ON_DUTY_HOURS` / `DROPOFF` |
| No adverse by default | ✅ | toggle default false |
| Hosted + GitHub + Loom | ⏳ | See `docs/SUBMISSION.md` |

## FMCSA / paper-log business rules

| Rule | Status | Notes |
|------|--------|--------|
| 11-hour driving limit | ✅ | `max_driving_hours` |
| 14-hour window | ✅ | no driving after window |
| 30-min break after 8h cumulative drive | ✅ | OFF break inserted |
| 10h OFF/SB resets 11/14 | ✅ | sleeper reset |
| Midnight rolling 8-day recap | ✅ | `CycleWindow.ensure_midnight_rollovers` |
| 34h restart | ✅ | auto when cycle blocks |
| Adverse +2h extension point | ✅ | `limits.py` + UI toggle |
| Grid totals = 24.0 · no overlaps | ✅ | `grid.normalize_day_segments` |
| Remarks at duty changes | ✅ | city/place + note |
| Recap A/B/C for 70/8 | ✅ | paper form fields |
| Recap A/B/C for 60/7 (display) | ✅ | form fidelity; cycle uses 70/8 |
| Home terminal timezone | ✅ | logs + remarks note |
| Road path (not straight line) | ✅ | ORS preferred · OSRM · haversine last |

## Automated tests

```bash
./scripts/run_tests.sh
# 29 tests — required HOS rules + grid normalize + preferred edge cases + API
```

See `apps/hos/tests/test_engine.py`.

## Paper log fidelity (`docs/blank-paper-log.png`)

| Form section | Status |
|--------------|--------|
| Title + date (month/day/year) | ✅ |
| Filing instructions | ✅ |
| From / To | ✅ |
| Miles driving + total mileage boxes | ✅ |
| Vehicle / trailer box | ✅ |
| Carrier / office / home terminal lines | ✅ |
| Black 24h header (Mid–Noon–Mid) | ✅ |
| 4 duty rows + 15-min ticks | ✅ |
| Continuous duty line (no parallel statuses) | ✅ |
| Total Hours column (=24) | ✅ |
| Remarks + shipping docs | ✅ |
| Home terminal time note | ✅ |
| Recap on-duty today (lines 3&4) | ✅ |
| 70/8 A·B·C | ✅ |
| 60/7 A·B·C | ✅ |
| 34h restart footnote | ✅ |
