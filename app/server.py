#!/usr/bin/env python3
"""Zero-dependency HTTP server: JSON API + static dashboard.

    python3 app/server.py          # serves http://localhost:8777

API
    GET  /api/graph                       industries -> submarkets -> pockets (joined)
    GET  /api/opportunities               all pockets (ranked)
    GET  /api/opportunities/<id>          one pocket, evidence & communities resolved
    POST /api/opportunities/<id>/select   mark selected + write research-request JSON
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from store import JsonStore, write_output  # noqa: E402
from discovery import rank                 # noqa: E402
import research                            # noqa: E402
from research_inputs import FINDINGS       # noqa: E402
import curation                            # noqa: E402
import distribution                        # noqa: E402
from universe import UniverseStore, UniverseService  # noqa: E402
import storage                             # noqa: E402
import auth                                # noqa: E402

store = JsonStore()
WEB = ROOT / "app" / "web"
RESEARCH_DIR = ROOT / "research"
PORT = int(os.environ.get("PORT", "8777"))
# comma-separated allowed origins for a split frontend (Vercel) → backend (this host)
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()]


def build_graph() -> dict:
    industries = {i["id"]: i for i in store.list("industries")}
    pockets = rank(store.list("opportunities"))
    by_sub: dict = {}
    for p in pockets:
        by_sub.setdefault((p["industry_id"], p.get("submarket_id")), []).append({
            "id": p["id"], "title": p["title"],
            "overall": p["score"]["overall"], "confidence": p["score"]["confidence"],
            "status": p["status"], "research_status": p.get("research_status", "not_started"),
        })
    out = []
    for ind in industries.values():
        subs = []
        for sm in ind.get("submarkets", []):
            subs.append({"id": sm["id"], "name": sm["name"],
                         "audiences": sm.get("audiences", []),
                         "pockets": by_sub.get((ind["id"], sm["id"]), [])})
        # pockets with no/unknown submarket
        loose = by_sub.get((ind["id"], None), [])
        if loose:
            subs.append({"id": None, "name": "(unsorted)", "audiences": [], "pockets": loose})
        out.append({"id": ind["id"], "name": ind["name"],
                    "description": ind.get("description", ""),
                    "status": ind.get("status", "seed"), "submarkets": subs,
                    "pocket_count": sum(len(s["pockets"]) for s in subs)})
    out.sort(key=lambda i: (-i["pocket_count"], i["name"]))
    return {"industries": out}


def resolve_pocket(pid: str) -> dict | None:
    p = store.get("opportunities", pid)
    if not p:
        return None
    ev = {e["id"]: e for e in store.list("evidence")}
    com = {c["id"]: c for c in store.list("communities")}
    p = dict(p)
    p["evidence"] = [ev[i] for i in p.get("evidence_ids", []) if i in ev]
    p["communities"] = [com[i] for i in p.get("community_ids", []) if i in com]
    return p


def select_pocket(pid: str) -> dict | None:
    p = store.get("opportunities", pid)
    if not p:
        return None
    p["status"] = "selected"
    store.put("opportunities", p)
    resolved = resolve_pocket(pid)
    request = {
        "research_request_id": f"rr-{pid}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pocket_id": pid, "title": p["title"], "industry_id": p["industry_id"],
        "audience": p["audience"], "core_problem": p["core_problem"],
        "desired_outcome": p.get("desired_outcome", ""),
        "related_problems": p.get("related_problems", []),
        "solution_gaps": p.get("solution_gaps", []),
        "score": p["score"],
        "evidence": resolved["evidence"], "communities": resolved["communities"],
        "source_urls": p.get("source_urls", []),
        "note": "Phase-8 research input. Discovery layer only marks intent; the research engine is not built yet.",
    }
    path = write_output(f"research-requests/rr-{pid}.json", request)
    return {"status": "selected", "research_request": str(path.relative_to(ROOT)), "request": request}


def run_research(pid: str, creds: dict | None = None, operator: str = "unknown") -> dict | None:
    pocket = store.get("opportunities", pid)
    if not pocket:
        return None
    ev = {e["id"]: e for e in store.list("evidence")}
    records = [ev[i] for i in pocket.get("evidence_ids", []) if i in ev]
    result = research.run(pocket, records, FINDINGS.get(pid), creds=creds, operator=operator)
    pocket["status"] = "researching" if result["research_status"] == "needs_review" else "selected"
    pocket["research_status"] = result["research_status"]
    store.put("opportunities", pocket)
    return result


def read_dossier(pid: str) -> dict | None:
    full = storage.get_backend().read_dossier(pid)
    if not full:
        return None
    return {name: full.get(name) for name in
            ("research_request", "research_plan", "sources", "evidence",
             "analysis", "product_brief", "questions")}


def run_curation(pid: str, override: bool = False):
    """Returns dossier dict, or {'error': ...} on honest failure (never fabricates).
    Phase-9 gate: blocks normal curation while Phase-8 is NEEDS_REVIEW due to
    unresolved CRITICAL research, unless an explicit override is passed."""
    p = store.get("opportunities", pid)
    rs = (p or {}).get("research_status")
    if rs != "complete" and not override:
        return {"error": "Phase-8 research is not COMPLETE (status: "
                         f"{rs or 'none'}). Resolve critical research or curate with override.",
                "curation_status": "blocked", "research_status": rs,
                "override_available": True}
    try:
        result = curation.run(pid)
    except curation.CurationError as e:
        return {"error": str(e), "curation_status": "failed"}
    if p:
        p["curation_status"] = "complete"
        if override and rs != "complete":
            from datetime import datetime, timezone
            p["curation_override"] = {"override": True, "research_status_at_curation": rs,
                                      "at": datetime.now(timezone.utc).isoformat()}
        store.put("opportunities", p)
    return result


def read_curation_dossier(pid: str) -> dict | None:
    return storage.get_backend().read_dossier_file(pid, "curation_dossier")


def run_distribution(pid: str):
    try:
        result = distribution.run(pid)
    except distribution.DistributionError as e:
        return {"error": str(e), "verdict": "REFUSED"}
    p = store.get("opportunities", pid)
    if p:
        p["distribution_verdict"] = result["verdict"]
        store.put("opportunities", p)
    return result


def read_distribution_dossier(pid: str) -> dict | None:
    return storage.get_backend().read_dossier_file(pid, "creator_validation_dossier")


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin")
        if origin and (origin in CORS_ORIGINS or "*" in CORS_ORIGINS):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def _send(self, code: int, body: bytes, ctype: str, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200, extra=None):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json", extra)

    def log_message(self, *a):  # quieter console
        pass

    # ---- auth helpers ----
    def _cookies(self) -> dict:
        raw = self.headers.get("Cookie", "")
        out = {}
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1); out[k] = v
        return out

    def _session_token(self):
        return self._cookies().get(auth.COOKIE)

    def _operator(self):
        """Authoritative operator for this request (from server session), or None."""
        return auth.current_operator(self._session_token())

    def _require_operator(self):
        """Return operator or send 401. Mutating/quota routes must call this."""
        op = self._operator()
        if not op:
            self._json({"error": "authentication required", "auth_required": True}, 401)
            return None
        return op

    def do_OPTIONS(self):
        self._send(204, b"", "text/plain")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/graph":
            return self._json(build_graph())
        # Market Universe (Build 1) — minimal read-only debug endpoints
        if path == "/api/universe/summary":
            f = ROOT / "data" / "universe" / "universe_summary.json"
            return self._json(json.loads(f.read_text()) if f.exists()
                              else {"error": "not built — run scripts/build_universe.py"},
                              200 if f.exists() else 404)
        if path == "/api/universe/tree":
            return self._json({"tree": UniverseService(UniverseStore()).tree()})
        # Universe Explorer (graph view model) — progressive expansion
        if path == "/api/universe/graph":
            from universe_graph import GraphService
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
            gs = GraphService()
            node = unquote(params.get("node", ""))
            if node:
                res = gs.children(node)
                return self._json(res) if res else self._json({"error": "no such node"}, 404)
            return self._json(gs.roots())
        if path.startswith("/api/universe/opportunity/") and path.endswith("/dossier"):
            oid = unquote(path.split("/")[4])
            d = read_dossier(oid)
            return self._json(d) if d else self._json({"error": "no dossier"}, 404)
        if path.startswith("/api/universe/opportunity/") and path.endswith("/curation-dossier"):
            oid = unquote(path.split("/")[4])
            d = read_curation_dossier(oid)
            return self._json(d) if d else self._json({"error": "no curation dossier"}, 404)
        if path.startswith("/api/universe/opportunity/") and path.endswith("/product/download"):
            if not self._require_operator():
                return
            oid = unquote(path.split("/")[4])
            import production as PR
            data = PR.get_bundle(oid)
            if not data:
                return self._json({"error": "no product bundle — generate the product first"}, 404)
            fn = f"{oid[:60]}-product.zip"
            return self._send(200, data, "application/zip",
                              extra={"Content-Disposition": f'attachment; filename="{fn}"'})
        if path.startswith("/api/universe/opportunity/") and path.endswith("/product"):
            oid = unquote(path.split("/")[4])
            import production as PR
            m = PR.get_manifest(oid)
            return self._json(m) if m else self._json({"error": "no product yet"}, 404)
        if path.startswith("/api/universe/opportunity/") and path.endswith("/creators"):
            oid = unquote(path.split("/")[4])
            import distribution as DI
            d = DI.get_creator_shortlist(oid)
            return self._json(d) if d else self._json({"error": "no creator shortlist yet"}, 404)
        if path.startswith("/api/universe/opportunity/") and path.endswith("/outreach"):
            oid = unquote(path.split("/")[4])
            import distribution as DI
            d = DI.get_outreach(oid)
            return self._json(d) if d else self._json({"error": "no outreach drafts yet"}, 404)
        if path == "/api/auth/me":
            op = self._operator()
            return self._json({"operator": op, "authenticated": bool(op),
                               "auth_enabled": auth.auth_enabled()})
        if path == "/api/universe/providers":
            import research_engine as RE
            op = self._operator()
            creds = auth.resolve_operator_credentials(op) if op else None
            usage = RE._read("research_usage")
            return self._json({"operator": op, "providers": RE.providers_status(creds),
                               "usage": usage if isinstance(usage, dict) else {}})
        if path == "/api/universe/storage-info":
            # diagnostic: which storage backend is actually active + is Supabase configured
            return self._json({
                "backend": storage.get_backend().name,
                "STORAGE_BACKEND_env": os.environ.get("STORAGE_BACKEND", "(unset)"),
                "supabase_url_set": bool(os.environ.get("SUPABASE_URL")),
                "supabase_key_set": bool(os.environ.get("SUPABASE_SERVICE_ROLE_KEY")),
            })
        if path == "/api/universe/groq-models":
            # diagnostic: list the Groq models the signed-in operator's key can use
            op = self._require_operator()
            if not op:
                return
            creds = auth.resolve_operator_credentials(op)
            if not creds.get("groq"):
                return self._json({"error": f"{op} has no Groq key"}, 503)
            import urllib.request as _u, urllib.error as _ue
            req = _u.Request("https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {creds['groq']}",
                                      "User-Agent": "opportunity-engine/1.0"})
            try:
                with _u.urlopen(req, timeout=20) as r:
                    data = json.loads(r.read())
                ids = sorted(m.get("id") for m in data.get("data", []))
                return self._json({"models": ids})
            except _ue.HTTPError as e:
                return self._json({"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}, 502)
        if path == "/api/universe/search-index":
            from universe_graph import GraphService
            return self._json({"nodes": GraphService().search_index()})
        if path == "/api/universe/search":
            from universe_graph import GraphService
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
            q = unquote(params.get("q", "").replace("+", " "))
            return self._json({"query": q, "results": GraphService().search(q)})
        if path.startswith("/api/universe/audience/") and path.endswith("/problems"):
            aid = path.split("/")[4]
            svc = UniverseService(UniverseStore())
            if aid not in svc._a:
                return self._json({"error": "no such audience"}, 404)
            return self._json({"audience_id": aid, "path": svc.path_for_audience(aid),
                               "problems": svc.problems_for_audience(aid)})
        if path.startswith("/api/universe/problem/"):
            pid = path.split("/")[4]
            svc = UniverseService(UniverseStore())
            p = svc.get_problem(pid)
            if not p:
                return self._json({"error": "no such problem"}, 404)
            return self._json({**p, "path": svc.path_for_problem(pid),
                               "sources": svc.problem_sources(pid)})
        if path.startswith("/api/universe/audience/") and path.endswith("/opportunities"):
            aid = path.split("/")[4]
            svc = UniverseService(UniverseStore())
            if aid not in svc._a:
                return self._json({"error": "no such audience"}, 404)
            return self._json({"audience_id": aid, "path": svc.path_for_audience(aid),
                               "opportunities": svc.opportunities_for_audience(aid)})
        if path == "/api/universe/rankings":
            svc = UniverseService(UniverseStore())
            return self._json({"scoring_version": "v1", "rankings": svc.ranked_opportunities()})
        if path == "/api/universe/pipeline":
            import pipeline as PL
            svc = UniverseService(UniverseStore())
            promoted = []
            for st in PL.PipelineService().promoted_opportunities():
                oid = st.get("opportunity_id", "")
                o = svc.get_opportunity(oid)
                row = dict(st)
                row["name"] = (o or {}).get("name")
                row["path"] = svc.path_for_opportunity(oid) if o else []
                promoted.append(row)
            return self._json({"promoted": promoted})
        if path == "/api/universe/explored":
            # Everything the operator team has touched: expanded graph nodes +
            # opened/researched opportunities. Read-only; no API spend.
            import pipeline as PL
            store = UniverseStore()
            svc = UniverseService(store)
            names = {}
            for coll in ("markets", "submarkets", "audiences", "problems"):
                for r in store.list(coll):
                    names[r["id"]] = r.get("name") or r.get("statement") or r["id"]
            ex = storage.get_backend().all_expansion()
            expanded = [{"node_id": nid, "name": names.get(nid, nid),
                         "expansion_status": v.get("expansion_status"),
                         "opportunity_count": v.get("opportunity_count"),
                         "child_count": v.get("child_count"),
                         "source_count": v.get("source_count"),
                         "researched_at": v.get("researched_at")}
                        for nid, v in ex.items() if v.get("expansion_status") == "expanded"]
            expanded.sort(key=lambda e: e.get("researched_at") or "", reverse=True)
            opportunities = []
            for st in PL.PipelineService().promoted_opportunities():
                oid = st.get("opportunity_id", "")
                o = svc.get_opportunity(oid)
                opportunities.append({"opportunity_id": oid, "name": (o or {}).get("name"),
                                      "priority_score": st.get("priority_score"),
                                      "priority_classification": st.get("priority_classification"),
                                      "research_status": st.get("research_status"),
                                      "curation_status": st.get("curation_status"),
                                      "pipeline_stage": st.get("pipeline_stage")})
            return self._json({"expanded_nodes": expanded, "opportunities": opportunities})
        if path.startswith("/api/universe/pipeline/"):
            import pipeline as PL
            oid = path.split("/")[4]
            st = PL.PipelineService().get_pipeline_state(oid)
            return self._json(st) if st else self._json({"error": "not promoted"}, 404)
        if path.startswith("/api/product/"):
            import production as PR
            oid = path.split("/")[3]
            m = PR.ProductService(oid).get_product_manifest()
            return self._json(m) if m else self._json({"error": "no product"}, 404)
        if path.startswith("/api/universe/opportunity/") and path.endswith("/score"):
            oid = path.split("/")[4]
            svc = UniverseService(UniverseStore())
            s = svc.score_for_opportunity(oid)
            return self._json(s) if s else self._json({"error": "not scored"}, 404)
        if path.startswith("/api/universe/opportunity/"):
            oid = path.split("/")[4]
            svc = UniverseService(UniverseStore())
            o = svc.get_opportunity(oid)
            if not o:
                return self._json({"error": "no such opportunity"}, 404)
            return self._json({**o, "path": svc.path_for_opportunity(oid),
                               "problems": svc.problems_for_opportunity(oid),
                               "score": svc.score_for_opportunity(oid)})
        if path == "/api/universe":
            svc = UniverseService(UniverseStore())
            return self._json({"markets": len(svc.markets()),
                               "submarkets": len(svc.store.list("submarkets")),
                               "audiences": len(svc.store.list("audiences"))})
        if path == "/api/opportunities":
            return self._json({"opportunities": rank(store.list("opportunities"))})
        if path.startswith("/api/opportunities/") and path.endswith("/dossier"):
            pid = path.split("/")[3]
            d = read_dossier(pid)
            return self._json(d) if d else self._json({"error": "no dossier"}, 404)
        if path.startswith("/api/opportunities/") and path.endswith("/curation-dossier"):
            pid = path.split("/")[3]
            d = read_curation_dossier(pid)
            return self._json(d) if d else self._json({"error": "no curation dossier"}, 404)
        if path.startswith("/api/opportunities/") and path.endswith("/distribution-dossier"):
            pid = path.split("/")[3]
            d = read_distribution_dossier(pid)
            return self._json(d) if d else self._json({"error": "no distribution dossier"}, 404)
        if path.startswith("/api/opportunities/"):
            pid = path.rsplit("/", 1)[-1]
            p = resolve_pocket(pid)
            return self._json(p) if p else self._json({"error": "not found"}, 404)
        # static (mirror Vercel: "/" -> explorer, extensionless clean URLs -> .html)
        rel = "explorer.html" if path in ("/", "") else path.lstrip("/")
        f = (WEB / rel).resolve()
        if not (f.exists() and f.is_file()) and "." not in rel.rsplit("/", 1)[-1]:
            f = (WEB / (rel + ".html")).resolve()   # /dashboard -> dashboard.html
        if WEB in f.parents and f.exists() and f.is_file():
            ctype = {"html": "text/html", "css": "text/css", "js": "application/javascript",
                     "json": "application/json"}.get(
                f.suffix.lstrip("."), "application/octet-stream")
            return self._send(200, f.read_bytes(), ctype + "; charset=utf-8")
        return self._send(404, b"not found", "text/plain")

    def _body_json(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", "0"))
            return json.loads(self.rfile.read(n) or b"{}") if n else {}
        except Exception:
            return {}

    def do_POST(self):
        path = self.path.split("?")[0]
        # ---- auth ----
        if path == "/api/auth/login":
            b = self._body_json()
            token = auth.login(b.get("operator", ""), b.get("password", ""))
            if not token:
                return self._json({"ok": False, "error": "invalid credentials"}, 401)
            cookie = (f"{auth.COOKIE}={token}; HttpOnly; Path=/; Max-Age={auth.SESSION_TTL}; "
                      "SameSite=None; Secure")
            return self._json({"ok": True, "operator": auth.resolve_session(token)},
                              extra={"Set-Cookie": cookie})
        if path == "/api/auth/logout":
            auth.logout(self._session_token())
            return self._json({"ok": True},
                              extra={"Set-Cookie": f"{auth.COOKIE}=; HttpOnly; Path=/; Max-Age=0; SameSite=None; Secure"})
        # ---- Dynamic research (Explore Deeper): live search -> classify -> persist ----
        if path.startswith("/api/universe/expand/"):
            op = self._require_operator()
            if not op:
                return
            node_id = unquote(path.split("/")[4])
            import research_engine as RE
            creds = auth.resolve_operator_credentials(op)
            if not RE.get_search_provider(creds) or not RE.get_classifier(creds):
                return self._json({"ok": False, "operator": op,
                                   "error": f"{op} is missing a Serper and/or Groq key on the server",
                                   "providers": RE.providers_status(creds)}, 503)
            if not storage.get_backend().claim_expansion(node_id, op):
                return self._json({"ok": False, "error": "another operator is exploring this node; "
                                   "reload shortly to load the result", "in_progress": True}, 409)
            try:
                res = RE.expand(node_id, creds=creds, operator=op)
                storage.get_backend().release_expansion(node_id)   # clear claim, keep result
                return self._json({"ok": True, "node_id": node_id, "operator": op, **res})
            except RE.ProviderUnavailable as e:
                storage.get_backend().release_expansion(node_id)
                st = RE.get_expansion_state(node_id) or {}
                return self._json({"ok": False, "error": str(e),
                                   "providers": RE.providers_status(creds),
                                   "packet_saved": st.get("source_count", 0) > 0}, 503)
            except Exception as e:
                storage.get_backend().release_expansion(node_id)
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        # ---- Hand a (generated) universe opportunity into the existing Phase-8 pipeline ----
        if path.startswith("/api/universe/opportunity/") and path.endswith("/open"):
            # Register an opportunity into the shared workspace (idempotent, no API spend).
            op = self._require_operator()
            if not op:
                return
            oid = unquote(path.split("/")[4])
            import pipeline as PL
            try:
                st = PL.promote(oid, force=True, promoted_by=op)
                return self._json({"ok": True, "opportunity_id": oid, "operator": op, "state": st})
            except Exception as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 422)
        if path.startswith("/api/universe/opportunity/") and path.endswith("/research"):
            op = self._require_operator()
            if not op:
                return
            oid = unquote(path.split("/")[4])
            import pipeline as PL
            creds = auth.resolve_operator_credentials(op)
            try:
                PL.promote(oid, force=True)
                res = PL.run_research(oid, creds=creds, operator=op)
                return self._json({"ok": True, "opportunity_id": oid, "operator": op, **res})
            except Exception as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 422)
        # ---- Phase-9 curation for a universe opportunity (gated on Phase-8 completion) ----
        if path.startswith("/api/universe/opportunity/") and path.endswith("/curate"):
            op = self._require_operator()
            if not op:
                return
            oid = unquote(path.split("/")[4])
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            override = "override=1" in qs or "override=true" in qs
            import pipeline as PL
            try:
                res = PL.run_curation(oid, override=override)
                return self._json({"ok": True, "opportunity_id": oid, "operator": op, **res})
            except PL.PipelineError as e:
                return self._json({"ok": False, "error": str(e), "curation_status": "blocked",
                                   "override_available": True}, 422)
            except Exception as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        # ---- Build 6: manufacture the actual product files (uses operator's LLM key) ----
        if path.startswith("/api/universe/opportunity/") and path.endswith("/produce"):
            op = self._require_operator()
            if not op:
                return
            oid = unquote(path.split("/")[4])
            creds = auth.resolve_operator_credentials(op)
            import research_engine as RE, production as PR
            if not RE.get_classifier(creds):
                return self._json({"ok": False, "operator": op,
                                   "error": f"{op} is missing a Groq key on the server",
                                   "providers": RE.providers_status(creds)}, 503)
            try:
                PR.approve_build(oid)                       # one-click: auto-approve the build gate
                m = PR.build_product(oid, creds=creds, operator=op)
                comps = [{"name": c["name"], "status": c["production_status"], "qa": c["qa_status"],
                          "formats": c["required_formats"]} for c in m["components"]]
                return self._json({"ok": True, "opportunity_id": oid, "operator": op,
                                   "product_status": m["product_status"],
                                   "bundle_status": m["bundle_status"],
                                   "download_ready": m.get("download_ready", False),
                                   "llm_tokens_used": m.get("llm_tokens_used", 0),
                                   "release_blocked_reasons": m.get("release_blocked_reasons", []),
                                   "components": comps})
            except PR.ProductionError as e:
                return self._json({"ok": False, "error": str(e)}, 422)
            except Exception as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        # ---- Creator discovery: live shortlist for outreach (operator's Serper + Groq) ----
        if path.startswith("/api/universe/opportunity/") and path.endswith("/discover-creators"):
            op = self._require_operator()
            if not op:
                return
            oid = unquote(path.split("/")[4])
            creds = auth.resolve_operator_credentials(op)
            import research_engine as RE, distribution as DI
            if not RE.get_search_provider(creds) or not RE.get_classifier(creds):
                return self._json({"ok": False, "operator": op,
                                   "error": f"{op} is missing a Serper and/or Groq key on the server",
                                   "providers": RE.providers_status(creds)}, 503)
            try:
                d = DI.discover_creators(oid, creds=creds, operator=op)
                return self._json({"ok": True, "opportunity_id": oid, "operator": op,
                                   "candidates_found": d["candidates_found"],
                                   "shortlisted": d["shortlisted"], "with_contact": d["with_contact"],
                                   "creators": d["creators"]})
            except DI.DistributionError as e:
                return self._json({"ok": False, "error": str(e)}, 422)
            except Exception as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        # ---- Outreach drafts (Groq); DRAFTS ONLY, sent manually ----
        if path.startswith("/api/universe/opportunity/") and path.endswith("/draft-outreach"):
            op = self._require_operator()
            if not op:
                return
            oid = unquote(path.split("/")[4])
            creds = auth.resolve_operator_credentials(op)
            import research_engine as RE, distribution as DI
            if not RE.get_classifier(creds):
                return self._json({"ok": False, "operator": op,
                                   "error": f"{op} is missing a Groq key on the server",
                                   "providers": RE.providers_status(creds)}, 503)
            try:
                d = DI.draft_outreach(oid, creds=creds, operator=op)
                return self._json({"ok": True, "opportunity_id": oid, "operator": op,
                                   "count": d["count"], "drafts": d["drafts"]})
            except DI.DistributionError as e:
                return self._json({"ok": False, "error": str(e)}, 422)
            except Exception as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        if path.startswith("/api/universe/opportunity/") and path.endswith("/outreach-status"):
            op = self._require_operator()
            if not op:
                return
            oid = unquote(path.split("/")[4])
            body = self._body_json()
            import distribution as DI
            try:
                res = DI.set_outreach_status(oid, int(body.get("index", -1)), str(body.get("status", "")))
                return self._json({"ok": True, **res})
            except DI.DistributionError as e:
                return self._json({"ok": False, "error": str(e)}, 422)
            except Exception as e:
                return self._json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)
        if path.startswith("/api/opportunities/") and path.endswith("/select"):
            if not self._require_operator():
                return
            pid = path.split("/")[3]
            res = select_pocket(pid)
            return self._json(res) if res else self._json({"error": "not found"}, 404)
        if path.startswith("/api/opportunities/") and path.endswith("/research"):
            op = self._require_operator()
            if not op:
                return
            pid = path.split("/")[3]
            res = run_research(pid, creds=auth.resolve_operator_credentials(op), operator=op)
            return self._json(res) if res else self._json({"error": "not found"}, 404)
        if path.startswith("/api/opportunities/") and path.endswith("/curate"):
            if not self._require_operator():
                return
            pid = path.split("/")[3]
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            override = "override=1" in qs or "override=true" in qs
            res = run_curation(pid, override=override)
            code = 422 if res.get("error") else 200
            return self._json(res, code)
        if path.startswith("/api/opportunities/") and path.endswith("/validate-distribution"):
            pid = path.split("/")[3]
            res = run_distribution(pid)
            code = 422 if res.get("error") else 200
            return self._json(res, code)
        return self._json({"error": "unknown endpoint"}, 404)


def main():
    # 0.0.0.0 so cloud hosts (Render/Railway/Fly) can route to the port; still
    # reachable locally at http://localhost:PORT. Override with HOST if needed.
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"Opportunity Intelligence Engine → http://localhost:{PORT} (bound {host})")
    print("Ctrl+C to stop.")
    ThreadingHTTPServer((host, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
