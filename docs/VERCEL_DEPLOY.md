# Vercel + Supabase deploy (RouteLog)

## Reality check

| Piece | Where it runs |
|-------|----------------|
| **React UI** | Vercel (static) |
| **Django API** | Vercel (Python / Fluid serverless) |
| **Postgres** | **Not on Vercel** — use your **published Supabase** (or Neon / Vercel Postgres) |

Vercel does **not** host a Postgres server inside the app. Your published Supabase DB is the right approach.

Detected Supabase project URL: `https://dsqyrvkdhakgaavhavun.supabase.co`  
(MCP could not open a live SQL connection — unpause the project if it is sleeping.)

---

## Architecture (2 Vercel projects)

```
Browser  →  routelog-web.vercel.app   (frontend)
                │  VITE_API_BASE
                ▼
            routelog-api.vercel.app   (Django)
                │  DATABASE_URL
                ▼
            Supabase Postgres
```

---

## 1. Supabase connection string

In Supabase Dashboard → **Project Settings → Database**:

1. Unpause project if needed  
2. Copy **URI** (prefer **Transaction pooler** / port `6543` for serverless)  
3. It looks like:

```
postgresql://postgres.[ref]:[PASSWORD]@aws-0-....pooler.supabase.com:6543/postgres?sslmode=require
```

Or direct (port `5432`) for migrations from your laptop:

```
postgresql://postgres:[PASSWORD]@db.[ref].supabase.co:5432/postgres?sslmode=require
```

---

## 2. Deploy API (`backend/`)

```bash
cd spotter-hos/backend
npx vercel link          # create project routelog-api, Root Directory = backend
npx vercel env add DATABASE_URL production
npx vercel env add DJANGO_SECRET_KEY production
npx vercel env add ORS_API_KEY production
npx vercel env add DJANGO_DEBUG production   # value: false
npx vercel env add ALLOWED_HOSTS production  # value: .vercel.app
npx vercel env add CORS_ORIGINS production   # add frontend URL after it exists
npx vercel --prod
```

After deploy, note the URL, e.g. `https://routelog-api.vercel.app`.

Smoke:

```bash
curl https://routelog-api.vercel.app/api/v1/health/
```

---

## 3. Deploy frontend (`frontend/`)

```bash
cd spotter-hos/frontend
npx vercel link          # project routelog-web, Root Directory = frontend
npx vercel env add VITE_API_BASE production
# value: https://routelog-api.vercel.app/api/v1
npx vercel --prod
```

Then set API `CORS_ORIGINS` to your frontend origin, e.g. `https://routelog-web.vercel.app`.

---

## 4. Local migrate against Supabase (optional first step)

```bash
cd backend
source .venv/bin/activate
export DATABASE_URL='postgresql://...sslmode=require'
unset USE_SQLITE
python manage.py migrate
```

Build on Vercel also runs `python manage.py migrate --noinput` via `pyproject.toml`.

---

## Env cheat-sheet (API)

| Variable | Required | Notes |
|----------|----------|--------|
| `DATABASE_URL` | yes | Supabase URI + `sslmode=require` |
| `DJANGO_SECRET_KEY` | yes | random secret |
| `ORS_API_KEY` | recommended | real road routing |
| `DJANGO_DEBUG` | `false` | |
| `ALLOWED_HOSTS` | `.vercel.app` | |
| `CORS_ORIGINS` | frontend URL | |

## Env cheat-sheet (frontend)

| Variable | Required | Notes |
|----------|----------|--------|
| `VITE_API_BASE` | yes | `https://<api>.vercel.app/api/v1` |

---

## PDF / media on Vercel

Disk is ephemeral. PDF download **regenerates from DB** when the file is missing (`TripPdfView`). Media uses `/tmp` when `VERCEL` is set.
