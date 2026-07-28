# Spotter AI — Full-Stack HOS Trip Planner

## Assessment Plan (v3 — Highest Marks Edition)

**Goal:** Maximize score under ≤16 work hours / 4 days.  
**Stack:** Django + DRF · React + Vite + TS · **MUI** · Postgres · Redis · Celery (stretch-gated)  
**Deliverables:** GitHub · live VPS URL · 3–5 min Loom  

---

## 0. Scoring Reality (how to win)

Spotter’s brief grades two things hardest:

| What they said | How we interpret it | Weight |
|----------------|---------------------|--------|
| “We will test the hosted version for **accuracy**” | Map stops + HOS logs must look correct on live URL | **Critical** |
| “**UI and UX must be good**… can compensate for some inaccuracies” | Polished MUI + mobile + beautiful log sheets | **Critical** |
| Django + React + map API + multi-day logs | Checklist must-haves | **Required** |
| GitHub + hosted + Loom | Submission gate | **Required** |
| Midnight recap / 34h / Celery / indexes | Not in brief — **Loom bonus** that separates you | **High upside, after Must** |

### Winning formula

```
Highest mark ≈ (Live accuracy × UI polish)  +  Loom seniority story
                ↑ spend 70% of time here      ↑ spend leftover 30%
```

**Rule:** Never sacrifice a working hosted demo for Celery/PDF/34h. Add those only after three canned trips pass on production.

---

## 1. Scope Tiers (plan accordingly)

### MUST — clears the assessment (~10–11h)

Ship these or you fail:

1. **Inputs:** current, pickup, dropoff, cycle used (+ trip start datetime)  
2. **Django API** that geocodes + routes + runs HOS simulator  
3. **Map** with route polyline + **custom** markers (origin / pickup / fuel / rest / dropoff)  
4. **HOS rules (correct enough to survive their tests):**  
   - 11h drive · 14h window · 30-min after 8h drive  
   - 70/8 with **calendar-day rolling window + midnight drop**  
   - Fuel ≤ every 1000 mi · 1h ON pickup · 1h ON dropoff  
   - Multi-day segments; each day totals **24.0**  
5. **SVG Drivers Daily Log** (grid + remarks + recap) — multi-day tabs  
6. **MUI** themed UI, **mobile usable**  
7. **Postgres** (not SQLite) via Docker on VPS  
8. Live HTTPS URL + README + Loom  

### SHOULD — beats average candidates (~3–4h)

Add only after Must works on localhost:

1. MUI **Stepper** (trip progress) + **DataGrid** (day summary)  
2. Unit tests for midnight recap (PDF Days 1–10 fixture) + 11/14/30  
3. Cycle pressure messaging when `used ≥ 60`  
4. Homterminal TZ noted on logs (FMCSA requirement)  
5. LogEntry model + **timestamp indexes** (Loom talking point)  

### STRETCH — top-percentile Loom flex (~2h leftover only)

Gate behind: “3 demo trips green on VPS.”

1. **34h restart** auto-detect + insert when cycle blocks  
2. **Adverse conditions** toggle (default off) + `limits.py` +2h hook  
3. **Celery + Redis** async PDF generate + poll download  
4. Redis geocode cache  

**Cut order if time slips:** PDF → Celery → adverse UI → 34h auto → DataGrid polish → Stepper animations.

---

## 2. Product Objective

Trip planner for **property-carrying** drivers (70h/8-day):

1. Take trip inputs  
2. Output HOS-compliant schedule  
3. Draw map with stops/rests/fuel  
4. Draw filled daily log sheets (and PDF if Stretch lands)  

Assumptions from brief: no adverse by default · fuel every 1,000 mi · 1h P&D.

---

## 3. HOS Engine (accuracy = marks)

Pure Python package `apps/hos/engine/` — **no ORM inside**. Unit-tested. Loom-demoable.

### 3.1 Statuses

| Code | Grid | Counts in 70h? |
|------|------|----------------|
| `OFF` | Off Duty | No |
| `SB` | Sleeper Berth | No |
| `D` | Driving | Yes |
| `ON` | On Duty (not driving) | Yes |

### 3.2 Clocks to enforce (Must)

| Rule | Behavior |
|------|----------|
| 11h driving | Cap drive; then ≥10h OFF/SB |
| 14h window | No driving after 14h from first work |
| 30-min break | After 8 **cumulative** drive hours; consecutive ≥30m OFF/SB/ON |
| 10h reset | ≥10h OFF/SB resets 11 + 14 |
| 70/8 midnight recap | See below — **required for high accuracy marks** |

### 3.3 Midnight Recap (Must — differentiator that also improves accuracy)

Per FMCSA guide: oldest day drops at end of each day; recalculate remaining.

```
daily_on_duty[date] → hours   # ON + D only

At local midnight during simulation:
  1. Finalize yesterday’s total
  2. Drop day that falls outside last 8 calendar dates
  3. Recalculate cycle_remaining = 70 − sum(window)
  4. Emit CycleRecalcEvent (show in UI remarks)
```

Seed `current_cycle_used` into prior days so opening sum matches input, then simulate forward.

**Fixture (from PDF):** Days 1–8 = 67h → Day 9 adds 6 → Days 2–9 = 73 (over 70 if drove) → Day 10 = 0 → Days 3–10 = 63. Unit-test this.

### 3.4 Stretch engine hooks

- **34h restart:** ≥34 consecutive OFF/SB → cycle = 0 (optional auto-insert if trip would stall)  
- **Adverse:** `max_drive = 11 + (2 if adverse else 0)`; same for window 14→16; does **not** raise 70/8; default `false`

MVP rest model: consecutive **10h SB/OFF** (skip full split-sleeper pairing). Document in README.

### 3.5 Simulator flow

```
Geocode → route (current→pickup→dropoff)
→ seed CycleWindow
→ insert 1h ON pickup/dropoff, fuel every ≤1000 mi (~0.5h ON)
→ simulate @ 15-min steps enforcing clocks + midnight rollover
→ emit LogEntries + DailyLogs + map stops
→ (Stretch) enqueue PDF task
```

---

## 4. Architecture (impress without blocking Must)

### Day-1 minimal viable infra

```
docker compose:  db (Postgres) + api (Django) + frontend (Vite/Nginx)
```

Add Redis/worker **only in Stretch phase**.

### Full target (when Stretch lands)

```
Nginx → React static
      → /api → Gunicorn/Django
            → Postgres
            → Redis ← Celery worker (PDF)
```

### Schema (Must models; indexes = Should)

**Driver** — tz, cycle_used cache, last_34h_restart_at  
**Trip** — locations, geometry, summary JSON, adverse flag, pdf_status  
**TripStop** — type, lat/lng, arrive/depart, sequence  
**LogEntry** — status, start_at, end_at, remark *(indexes on driver+start_at)*  
**DailyLog** — date, grid_segments JSON, totals, remarks, recap  

Normalize from day one (cheap). Don’t block UI on PDF fields.

### Repo

```
spotter-hos/
├── docker-compose.yml
├── backend/   # config, apps/{hos,trips,drivers,logs}, utils/
├── frontend/  # MUI theme, features/trip-planner, features/log-viewer
├── deploy/nginx.conf
└── README.md
```

Views thin · math in `hos/engine` · persistence in `trips/services.py`.

---

## 5. API (Must contract)

`POST /api/v1/trips/plan/`

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Houston, TX",
  "current_cycle_used_hours": 12.5,
  "trip_start": "2026-07-27T06:00:00-05:00",
  "adverse_conditions": false,
  "home_terminal_tz": "America/Chicago"
}
```

Response: `summary`, `route.geometry`, `stops[]`, `daily_logs[]` (segments, totals=24, remarks, recap), optional `midnight_recaps[]`.

Also: `GET /health/`, `GET /trips/{id}/`, (Stretch) `GET /trips/{id}/pdf/`.

---

## 6. Map & Logs (UI marks)

### Map

- react-leaflet + OSM  
- OpenRouteService (or OSRM fallback)  
- **Custom markers only** (no default blue pins)  
- Fuel / Rest / Pickup / Dropoff / Origin  

### Log sheets

- SVG matching `blank-paper-log.png`  
- 4 rows × 24h × 15-min ticks · duty lines · totals · remarks · 70/8 recap  
- Multi-day Tabs  
- Print CSS as backup if PDF Stretch slips  

### MUI map (Spotter-aligned)

| Area | Component |
|------|-----------|
| Form | Autocomplete, TextField, DateTimePicker, Slider/field for cycle |
| Progress | Stepper (Should) |
| Summary | DataGrid (Should) |
| Feedback | Alert, Snackbar, CircularProgress |
| Logs | Paper + Tabs + SVG |

**Theme:** asphalt `#0F1419` · paper `#F2EDE4` · amber `#E8A317` · steel `#3D6B8C` · Outfit + IBM Plex Mono. Brand **RouteLog** large on first screen. Mobile: form → map (≥40vh) → logs scroll.

---

## 7. 4-Day / 16-Hour Schedule (highest marks)

### Day 1 — “Something live exists” (4h)

| Block | Time | Outcome |
|-------|------|---------|
| Scaffold | 1.0h | Monorepo, Compose (Postgres+api+frontend), health |
| Models | 0.5h | Driver/Trip/TripStop/LogEntry/DailyLog migrate |
| Routing | 1.5h | Geocode + directions adapter + fixture fallback |
| Thin plan API | 1.0h | Returns geometry + naive stops (even before full HOS) |

**Exit gate:** Postman/curl plan returns a polyline for Chicago→Dallas→Houston.

### Day 2 — “Accuracy” (5h)

| Block | Time | Outcome |
|-------|------|---------|
| HOS simulator | 3.5h | 11/14/30/fuel/P&D/10h reset + CycleWindow midnight |
| Engine tests | 1.0h | PDF rolling example + short/long trip fixtures |
| Wire API | 0.5h | Persist LogEntries + DailyLogs |

**Exit gate:** Unit tests green; API daily_logs totals = 24; fuel appears on long route.

### Day 3 — “UI marks” (4.5h)

| Block | Time | Outcome |
|-------|------|---------|
| MUI shell + form | 1.0h | Themed Plan page |
| Map + custom markers | 1.5h | Results page |
| SVG log sheets | 1.5h | Multi-day, remarks, recap |
| Mobile pass | 0.5h | Fix xs breakpoints |

**Exit gate:** Phone-width usable; logs look professional; map markers custom.

### Day 4 — “Submit + bonus” (2.5h)

| Block | Time | Outcome |
|-------|------|---------|
| VPS deploy + HTTPS | 1.0h | Public URL, 3 canned trips verified |
| Should polish | 0.5h | Stepper and/or DataGrid if stable |
| Stretch (only if green) | 0.5h | 34h **or** adverse toggle **or** Celery PDF — pick **one** |
| Loom + README | 0.5h | Script below |

**Hard stop:** If deploy isn’t done by hour 14.5, freeze features and only polish + record Loom.

---

## 8. Acceptance Trips (run before Loom)

| # | Trip | Assert |
|---|------|--------|
| 1 | Short metro (~50–100 mi) | 1 log day; 1h P&D visible; totals 24 |
| 2 | Chicago → Dallas → Houston | Multi-day; fuel ≥1; rests; map sane |
| 3 | Long ≥1500 mi | Multiple fuel; multiple sheets |
| 4 | Same as #2 with `cycle_used=65` | Remaining/restart messaging; no silent violation |

If #2 fails on VPS, you are not ready to submit.

---

## 9. Loom Script (maximize perceived seniority in 4 min)

1. **0:00–0:20** Live URL → enter Trip #2 → show map + custom icons  
2. **0:20–1:00** Flip multi-day SVG logs; point at 30-min break + 10h sleeper + fuel ON  
3. **1:00–2:00** Code: `CycleWindow` midnight rollover + PDF fixture test (accuracy story)  
4. **2:00–2:45** Schema: LogEntry + timestamp indexes; why Postgres on VPS  
5. **2:45–3:30** MUI + mobile; mention Spotter-aligned stack  
6. **3:30–4:00** One Stretch item if shipped (Celery PDF **or** 34h **or** adverse) + honest tradeoff (10h reset vs split sleeper)

---

## 10. Self-Grade Rubric (before submit)

Score yourself 0–2 on each. Submit only if total ≥ **16/20**.

| Item | 0 | 1 | 2 |
|------|---|---|---|
| Hosted URL works | down | flaky | solid |
| Map + custom stops | missing | default pins | custom + clear labels |
| Multi-day drawn logs | none / PNG only | rough SVG | crisp grid+remarks+recap |
| HOS 11/14/30/fuel/P&D | broken | mostly | matches fixtures |
| Midnight/rolling 70-8 | `70-used` only | day buckets | midnight drop + test |
| MUI + mobile | raw/CSS mess | desktop OK | phone OK + themed |
| Django+React clarity | spaghetti | readable | engine separated |
| README + Loom | missing | basic | architecture called out |
| Demo trips 1–4 | 0–1 pass | 2–3 | all 4 |
| Bonus (34h/adverse/Celery) | none | commented | working one feature |

---

## 11. Locked Defaults

| Decision | Value |
|----------|--------|
| Brand | RouteLog |
| Routing | OpenRouteService; haversine+55mph emergency fallback flagged in UI |
| Start time | 06:00 home-terminal TZ |
| Fuel | 30 min ON |
| Adverse | Off (Stretch toggle) |
| Auto 34h | Stretch only |
| PDF/Celery | Stretch only |
| DB | Postgres always |

---

## 12. Reference Materials

| File | Use |
|------|-----|
| `new-full-stack-dev-assessment.docx` | Official brief |
| `pdfcontent.md` / FMCSA PDF | Rule source + rolling example |
| `blank-paper-log.png` | Log SVG pixel target |
| `fmsca-image.png` | Highlighted TOC scope |
| `readme.md` | Submission instructions |

YouTube: https://www.youtube.com/watch?v=whxe41XYXS8  

---

## 13. One-Line Strategy

> **Day 1 route, Day 2 correct HOS, Day 3 beautiful MUI logs/map, Day 4 deploy+Loom; spend leftover minutes on one senior flex — never the other way around.**

*Document status: v3 Highest Marks — optimized to clear and outrank.*
