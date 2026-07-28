# Submission checklist

Spotter asks for **three links** when you upload the answer:

1. GitHub repository  
2. Live hosted URL  
3. 3–5 minute Loom walkthrough  

## 1. GitHub

```bash
cd spotter-hos
git init
# confirm .env is ignored
git status
git add .
git commit -m "RouteLog: Spotter HOS trip planner (Django + React)"
# create repo on GitHub, then:
git branch -M main
git remote add origin git@github.com:<YOU>/spotter-hos.git
git push -u origin main
```

**Never commit** `.env` (contains `ORS_API_KEY` / DB passwords).

## 2. Hosted URL (Vercel + Supabase)

Prefer **two Vercel projects** + your published Supabase DB:

1. API from `backend/` → `DATABASE_URL` = Supabase URI  
2. UI from `frontend/` → `VITE_API_BASE` = `https://<api>.vercel.app/api/v1`

Full steps: [`docs/VERCEL_DEPLOY.md`](VERCEL_DEPLOY.md)

**Note:** Postgres is **not** hosted inside Vercel — use Supabase (already published).

Before recording Loom, verify acceptance trips on the **public** URL:

| # | Trip | Assert |
|---|------|--------|
| 1 | Short metro | 1 log day; 1h P&D; totals 24 |
| 2 | Chicago → Dallas → Houston | Multi-day; fuel; rests; clean duty line |
| 3 | Long ≥1500 mi | Multiple fuel + sheets |
| 4 | Same as #2 with cycle used = 65 | Restart / remaining messaging |

## 3. Loom (≈4 min)

Script from `ASSESSMENT_PLAN.md` §9:

1. Live URL → plan CHI→DAL→HOU → map + markers  
2. Multi-day logs → 30-min break, sleeper, fuel ON, totals = 24, **one continuous line**  
3. Code: `CycleWindow` midnight + `grid.normalize_day_segments`  
4. Schema: `LogEntry` indexes · Postgres on VPS  
5. MUI + mobile  
6. One stretch: 34h **or** adverse **or** PDF download + honest tradeoff (10h reset vs split sleeper)

## Local demo (before host)

```bash
# API
cd backend && source .venv/bin/activate
USE_SQLITE=true python manage.py runserver 0.0.0.0:8000

# UI (other terminal)
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173
