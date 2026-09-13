# Deploying the Opportunity Engine (shared, two-operator MVP)

This is the **persistent, shared** deployment: Cael and Sheylyn each sign in, work
against **one shared Universe + research + curation state**, and every stored
result loads for the other operator with **zero API spend**. New research/curation
work spends the **signed-in operator's own** Gemini + Serper quota — never the
other operator's.

## Topology

```
  Browser ──▶  Vercel (static frontend: app/web/*)
                 │  /api/*  and  /graph/*   are proxied (same-origin, keeps the
                 ▼          login cookie first-party)
              Render (persistent Python backend: app/server.py)
                 │  STORAGE_BACKEND=supabase
                 ▼
              Supabase (Postgres — the shared durable state)
```

- **Frontend on Vercel** — static files only, no build step.
- **Backend on Render** (or Railway/Fly) — a long-running process. It must be
  persistent because a single research run takes 1–3 min, which exceeds Vercel
  serverless timeouts. **Vercel Pro is NOT required** — the free/Hobby plan serves
  the static frontend and the proxy rewrites fine.
- **Supabase** — the one shared database. Free tier is sufficient for the MVP.

All Gemini/Serper calls happen **server-side only**. API keys live in Render env
vars, are never returned to the browser, never committed, never persisted in
Supabase, never logged. Passwords are stored only as PBKDF2 hashes.

---

## Deployment checklist (do these in order)

### 1. Create the Supabase project
1. supabase.com → **New project**. Note the project **URL** and, under
   **Project Settings → API**, the **`service_role` key** (secret — backend only).
2. Open **SQL Editor**, paste the entire contents of
   [`migrations/supabase_schema.sql`](migrations/supabase_schema.sql), **Run**.
   This creates: `documents`, `expansion_state`, `exploration_claims`,
   `dossier_files`, `usage_events`, `sessions` (RLS on; the service-role key
   bypasses it — never ship that key to the frontend).

### 2. Seed Supabase with the current local Universe + research
From your machine (one time):
```bash
export SUPABASE_URL='https://<project>.supabase.co'
export SUPABASE_SERVICE_ROLE_KEY='<service_role key>'
python3 scripts/migrate_to_supabase.py --dry   # preview what will upload
python3 scripts/migrate_to_supabase.py         # actually upload (idempotent)
```
Re-runnable any time — everything is an upsert, no duplicate rows.

### 3. Create the two login passwords (hashes only)
```bash
python3 scripts/make_password_hash.py 'cael-chosen-password'
python3 scripts/make_password_hash.py 'sheylyn-chosen-password'
```
Copy each printed `pbkdf2_sha256$...` string. The plaintext is never stored.

### 4. Deploy the backend on Render
1. Push this repo to GitHub.
2. Render → **New → Web Service** → connect the repo. `render.yaml` supplies the
   start command (`python3 app/server.py`); the env vars below are marked
   `sync:false`, so set their **values** in the Render dashboard:

   | Env var | Value |
   |---|---|
   | `STORAGE_BACKEND` | `supabase` (already set) |
   | `SUPABASE_URL` | your project URL |
   | `SUPABASE_SERVICE_ROLE_KEY` | the service_role secret |
   | `CAEL_PASSWORD_HASH` | hash from step 3 |
   | `SHEYLYN_PASSWORD_HASH` | hash from step 3 |
   | `CAEL_GEMINI_API_KEY` | Cael's Gemini key |
   | `CAEL_SERPER_API_KEY` | Cael's Serper key |
   | `SHEYLYN_GEMINI_API_KEY` | Sheylyn's Gemini key (add when she provides it) |
   | `SHEYLYN_SERPER_API_KEY` | Sheylyn's Serper key |
   | `CORS_ALLOW_ORIGINS` | your Vercel URL, e.g. `https://opp-engine.vercel.app` |

   > Setting **any** `*_PASSWORD_HASH` turns auth ON. Until Sheylyn's keys are
   > added she can log in and read all shared results (zero API), but her own
   > research/expand calls fail cleanly with a "missing credential" error — they
   > will **never** silently fall back to Cael's keys.
3. Deploy. Note the backend URL, e.g. `https://opportunity-engine.onrender.com`.

### 5. Wire the frontend proxy and deploy on Vercel
1. Edit [`vercel.json`](vercel.json): replace **both** `REPLACE-WITH-BACKEND-HOST`
   occurrences with your Render host (no protocol duplication — keep `https://`):
   ```json
   { "source": "/api/:path*",   "destination": "https://opportunity-engine.onrender.com/api/:path*" },
   { "source": "/graph/:path*", "destination": "https://opportunity-engine.onrender.com/graph/:path*" }
   ```
   Commit + push. (The proxy keeps `/api` same-origin so the login cookie stays
   first-party — no third-party-cookie problems.)
2. Vercel → **New Project** → import the repo. Framework: **Other**; Build
   command: **none**; Output directory: **`app/web`** (all encoded in
   `vercel.json`). Deploy.
3. Confirm `CORS_ALLOW_ORIGINS` on Render matches the final Vercel URL.

### 6. First production login + verification
1. Open the Vercel URL → the login overlay appears (auth is on). Sign in as
   **Cael**. The operator badge shows "cael".
2. **Verify secrets are not exposed** (open DevTools → Network):
   - `GET /api/auth/me` returns `{operator, authenticated, auth_enabled}` — **no keys**.
   - `GET /api/universe/providers` returns provider **names/status only** — no key values.
   - Search the whole page source / JS for your key strings → **zero matches**.
   - The login cookie is `HttpOnly` (not readable from `document.cookie`).

### 7. The shared-cache + per-operator quota test (the STOP condition)
1. **Cael** explores/expands a node that has no stored result → uses **Cael's**
   keys → result persists to Supabase.
2. Reload / open a researched opportunity → its dossier loads with **zero API**
   (served from Supabase).
3. **Sheylyn** signs in (own browser/incognito) → opens the node Cael just did →
   sees his result with **zero API spend**.
4. Sheylyn expands a *different* new node → uses **Sheylyn's** keys (check
   `usage_events` in Supabase: rows attributed to `sheylyn`, none borrowing Cael's).
5. Refresh an existing result: on API failure the prior good dossier is
   **preserved** (no clobber).

If all five hold, the shared two-operator MVP is live.

---

## Updating the live site later
- **Universe/taxonomy change:** run `scripts/migrate_to_supabase.py` again to push
  new rows to Supabase (backend reads Supabase live — no redeploy needed for data).
- **Frontend change:** push to GitHub → Vercel auto-deploys.
- **Backend code change:** push to GitHub → Render auto-deploys.

## Local development (unchanged, no auth, no Supabase)
```bash
python3 app/server.py      # STORAGE_BACKEND defaults to local; auth off; operator=cael
```
Open `http://localhost:8777/explorer.html`. Uses local `data/` + `research/`
files and your global `GEMINI_API_KEY` / `SERPER_API_KEY` from the environment.

## What is / isn't shared state
- ✅ Universe (markets→opportunities), scores, rankings — Supabase `documents`.
- ✅ Research dossiers, curation briefs, distribution profiles — `dossier_files`.
- ✅ Expansion results + exploration claims (concurrency) + usage attribution.
- ✅ Sessions (login) — `sessions`.
- ⚠️ **Product build artifacts** (`app/production.py`) still write real product
  files to the backend's local disk (binaries/manifests — object-storage territory,
  out of scope for this shared-state MVP). They work on the single backend host but
  are not replicated to Supabase. Migrate to object storage when Build-6 goes shared.
