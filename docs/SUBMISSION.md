# Submission checklist

Spotter asks for **three links** when you upload the answer:

1. GitHub repository  
2. Live hosted URL  
3. 3–5 minute Loom walkthrough  

## Live links (ready)

| Deliverable | URL |
|-------------|-----|
| **GitHub** | https://github.com/MHunain-Official/spotter-hos |
| **Live app (UI)** | https://spotter-hos-web.vercel.app |
| **API** | https://spotter-hos-api.vercel.app |
| **Health** | https://spotter-hos-api.vercel.app/api/v1/health/ |

## Remaining

1. **Loom 3–5 min** — script in `ASSESSMENT_PLAN.md` §9  
2. **Supabase `DATABASE_URL`** — replace temporary `USE_SQLITE` on the API so data persists across cold starts. Dashboard → Project Settings → Database → URI, then:

```bash
cd backend
printf '%s' 'YOUR_SUPABASE_URI?sslmode=require' | npx vercel env add DATABASE_URL production
npx vercel env rm USE_SQLITE production
npx vercel --prod
```

## Acceptance trips (run on live URL before Loom)

| # | Trip | Assert |
|---|------|--------|
| 1 | Short metro | 1 log day; 1h P&D; totals 24 |
| 2 | Chicago → Dallas → Houston | Multi-day; fuel; rests; clean duty line |
| 3 | Long ≥1500 mi | Multiple fuel + sheets |
| 4 | Same as #2 with cycle used = 65 | Restart / remaining messaging |

## Loom (~4 min)

Script from `ASSESSMENT_PLAN.md` §9:

1. Live URL → plan CHI→DAL→HOU → map + markers  
2. Multi-day logs → 30-min break, sleeper, fuel ON, totals = 24  
3. Code: `CycleWindow` midnight + `grid.normalize_day_segments`  
4. Schema / Vercel + Supabase story  
5. MUI + mobile  
6. Stretch: PDF / 34h / adverse + honest tradeoff  

## Local demo

```bash
cd backend && source .venv/bin/activate
USE_SQLITE=true python manage.py runserver 0.0.0.0:8000

cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```
