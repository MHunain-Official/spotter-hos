# RouteLog — Spotter AI Full-Stack HOS Assessment

Django + React (MUI) trip planner for property-carrying CMV drivers (70h / 8-day).

## Live

| | |
|--|--|
| **App** | https://spotter-hos-web.vercel.app |
| **API** | https://spotter-hos-api.vercel.app |
| **GitHub** | https://github.com/MHunain-Official/spotter-hos |

## Features

- Inputs: current / pickup / dropoff / cycle used / trip start / adverse toggle
- OpenStreetMap + routing (OpenRouteService if `ORS_API_KEY` set, else OSRM / haversine fallback)
- HOS engine: 11h drive, 14h window, 30-min break, fuel every 1,000 mi, 1h pickup & dropoff
- **Midnight recap** rolling 8-day cycle window (`CycleWindow`)
- Non-overlapping **Drivers Daily Log** grid (merged segments, continuous duty line)
- 34h restart when cycle would stall (auto)
- Adverse conditions extension (+2h drive/window when toggled; **default off**)
- SVG paper logs + PDF download + MUI Stepper / DataGrid
- Postgres-ready models with **LogEntry timestamp indexes** (SQLite for local/dev)

## Quick start (local)

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# For local without Docker Postgres:
echo "USE_SQLITE=true" >> .env
# Optional: set ORS_API_KEY in repo-root .env or backend/.env
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# Frontend (other terminal)
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173

### Postgres (preferred for VPS demo)

```bash
# docker compose up -d db
export POSTGRES_HOST=127.0.0.1 POSTGRES_DB=routelog POSTGRES_USER=routelog POSTGRES_PASSWORD=routelog
# unset USE_SQLITE
python manage.py migrate
```

## API

`POST /api/v1/trips/plan/`

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Houston, TX",
  "current_cycle_used_hours": 12.5,
  "trip_start": "2026-07-27T06:00:00-05:00",
  "adverse_conditions": false
}
```

`GET /api/v1/health/` · `GET /api/v1/trips/{id}/` · `GET /api/v1/trips/{id}/pdf/`

## Tests

```bash
./scripts/run_tests.sh
# or: cd backend && USE_SQLITE=true python manage.py test apps.hos.tests.test_engine -v 2
```

**29 tests** covering required HOS rules, grid non-overlap, midnight 70/8, API, routing fallbacks.

## Architecture (Loom talking points)

1. Pure Python HOS engine under `apps/hos/engine/` — no ORM in calculator  
2. `CycleWindow` recalculates at local midnight when oldest day drops  
3. `grid.normalize_day_segments` — one status at a time on the paper log  
4. `LogEntry` indexes on `(driver, start_at)` for 8-day window queries  

**Tradeoff:** consecutive 10h sleeper/off reset (full split-sleeper pairing deferred).

## Deploy (Vercel + Supabase)

Vercel hosts the **UI + Django API**. Your **published Postgres** (Supabase) is the database — Vercel does not run Postgres inside the app.

See [`docs/VERCEL_DEPLOY.md`](docs/VERCEL_DEPLOY.md).

## Docs

| Doc | Purpose |
|-----|---------|
| [`docs/VERCEL_DEPLOY.md`](docs/VERCEL_DEPLOY.md) | Vercel + Supabase deploy |
| [`docs/BUSINESS_RULES_AND_SDLC.md`](docs/BUSINESS_RULES_AND_SDLC.md) | Rules ↔ code map |
| [`docs/COMPLIANCE_AUDIT.md`](docs/COMPLIANCE_AUDIT.md) | Pass/fail vs official brief |
| [`docs/SUBMISSION.md`](docs/SUBMISSION.md) | GitHub · host · Loom steps |
| [`docs/ASSESSMENT_PLAN.md`](docs/ASSESSMENT_PLAN.md) | v3 plan + Loom script |
| [`docs/blank-paper-log.png`](docs/blank-paper-log.png) | Paper form reference |
