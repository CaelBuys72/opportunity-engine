# Phase-8 Infra Completion Report — Shared, Two-Operator Deployed MVP

**Goal:** turn the local-first app into a persistent, shared, two-operator
(Cael + Sheylyn) deployable MVP: Supabase shared storage, lightweight private
auth, per-operator Gemini + Serper credentials, Vercel-ready, cache-first
(stored results load with zero API spend; new work spends the signed-in
operator's own keys).

**Status: COMPLETE and locally verified.** What remains is *your* infrastructure
setup (create Supabase project, add keys, deploy) — the literal steps are in
[`DEPLOY.md`](../DEPLOY.md).

---

## 1. What was built

| # | Item | Where | Status |
|---|---|---|---|
| 1 | Storage abstraction (Local + Supabase, one interface) | `app/storage.py` | ✅ |
| 2 | Two-operator auth (PBKDF2, opaque sessions, HttpOnly cookies) | `app/auth.py` | ✅ |
| 3 | Per-operator credential resolver, **no cross-operator fallback** | `app/auth.py` + provider factories | ✅ |
| 4 | Universe reads/writes routed through backend | `app/universe.py` | ✅ |
| 5 | Research engine persistence + providers creds-aware | `app/research_engine.py` | ✅ |
| 6 | Research / curation / distribution dossiers via backend | `app/research.py`, `app/curation.py`, `app/distribution.py` | ✅ |
| 7 | Pipeline state via backend; operator threaded through | `app/pipeline.py` | ✅ |
| 8 | Server: auth endpoints, operator-gated mutations, CORS, cookies | `app/server.py` | ✅ |
| 9 | Concurrency: atomic exploration claim (no double-spend) | `storage.claim_expansion` + server expand | ✅ |
| 10 | Per-operator usage attribution | `usage_events` + `_bump_usage(operator, provider)` | ✅ |
| 11 | Frontend login overlay + operator badge + logout | `app/web/auth.js` (both HTML pages) | ✅ |
| 12 | Supabase schema | `migrations/supabase_schema.sql` | ✅ |
| 13 | Idempotent local→Supabase migration | `scripts/migrate_to_supabase.py` | ✅ |
| 14 | Password-hash generator | `scripts/make_password_hash.py` | ✅ |
| 15 | Vercel static + proxy config | `vercel.json` | ✅ |
| 16 | Persistent backend host config | `render.yaml` | ✅ |
| 17 | Secrets excluded from git | `.gitignore` | ✅ |
| 18 | Deployment guide + checklist | `DEPLOY.md` | ✅ |
| 19 | Infra test suite | `tests/test_infra.py` (25/25 pass) | ✅ |

## 2. Security guarantees (all enforced)

- API keys are **server-side only** — never in frontend JS, API responses,
  Supabase, logs, storage, error messages, or committed to git. Verified:
  `/api/auth/me` and `/api/universe/providers` return names/status only.
- **No cross-operator key fallback.** The provider factory uses *only* the
  passed creds on the authenticated path (`creds is not None` → never reads the
  global `.env` key). Verified by test: Sheylyn (no key) resolves `null/null` and
  her expand fails cleanly — it does not borrow Cael's key.
- Global `GEMINI_API_KEY`/`SERPER_API_KEY` fallback exists **only in open
  (non-auth) local-dev mode**.
- Passwords stored only as `pbkdf2_sha256$iters$salt$hash`. Sessions are opaque
  tokens in HttpOnly cookies. Backend is authoritative for operator identity —
  `?operator=` / request JSON is never trusted for identity.

## 3. Cache-first behavior (verified)

- Stored Universe, dossiers, scores, rankings load through the backend with **no
  provider calls** — confirmed by a test that reads a cached result with
  providers disabled.
- New expand/research uses the signed-in operator's keys and persists the result.
- On refresh failure, the prior good dossier is **preserved** (no-clobber path).

## 4. Regression checks (all pass, this session)

```
static export ............ 947 node files, 101 problems, 36 opportunities  ✅
infra tests .............. 25 passed, 0 failed                              ✅
open-mode server ......... auth off, operator=cael, 30 markets, dossiers OK ✅
Build-4 scores ........... intact (71/62/67)                                ✅
distribution (migrated) .. loads brief via storage OK                       ✅
backend switch ........... local (default) / supabase (env) both instantiate ✅
auth switch .............. enabled when *_PASSWORD_HASH set                 ✅
all modules .............. py_compile OK                                    ✅
```

## 5. Known limitations / not-yet-migrated

- **`app/production.py` (Build-6 product artifacts)** still writes real product
  files (binaries, manifests) to the backend's local disk. These are
  object-storage territory, out of scope for the shared-*state* MVP. They work on
  the single persistent backend host but are not replicated to Supabase. Flagged
  in `DEPLOY.md`; migrate to object storage when Build-6 goes shared.
- Page-retrieval hit rate is low on bot-blocking sites, so **search snippets are
  the primary evidence** (this is by design and honestly accounted for in Phase-8;
  not an infra issue).
- **Not live-tested against a real Supabase project** (you don't have one yet) —
  the Supabase backend is exercised by unit tests and instantiates cleanly, but
  the first real round-trip happens during your deploy (step 7 in `DEPLOY.md`).

## 6. Your next actions (all in DEPLOY.md, in order)

1. Create the Supabase project; run `migrations/supabase_schema.sql`.
2. `python3 scripts/migrate_to_supabase.py` (seed shared state).
3. `python3 scripts/make_password_hash.py '<pw>'` for each operator.
4. Deploy backend on Render; set env vars (keys, hashes, Supabase, CORS).
5. Point `vercel.json` at the Render host; deploy frontend on Vercel.
6. Log in as Cael; verify no secrets in DevTools.
7. Run the Cael→Sheylyn shared-cache + per-operator-quota test.

Sheylyn's keys can be added to Render whenever she provides them — until then she
can log in and read everything (zero API); her own new research fails cleanly
rather than spending Cael's quota.
