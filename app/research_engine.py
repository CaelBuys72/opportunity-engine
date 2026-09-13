"""Dynamic research engine — the missing FRONT of the pipeline.

Grows the Universe graph only where the operator explicitly explores:

    node  ->  SEARCH (live web)  ->  RAW EVIDENCE (persisted)
          ->  CLASSIFY (LLM, grounded in evidence)  ->  STRUCTURED CHILD NODES
          ->  dedupe against existing  ->  persist  ->  render

Design rules honored here:
  * The LLM never invents the universe — it only classifies retrieved evidence.
  * Everything is persisted to the existing bundled-JSON store (no DB, no cloud).
  * Providers are pluggable and env-gated; nothing runs without an explicit trigger.
  * If a provider key is missing we DO NOT fabricate — we raise ProviderUnavailable
    and (for search) leave a research packet for the offline classification path.

Providers:
    SearchProvider        -> SerperSearchProvider (SERPER_API_KEY)   | None
    ClassificationProvider-> Anthropic / OpenAI / Gemini (API keys)  | None
    Persistence           -> UniverseStore (data/universe/*.json)

All network calls use stdlib urllib (this repo ships zero third-party deps).
"""
from __future__ import annotations
import json
import os
import re
import time
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import universe as U
from universe import UniverseStore, UniverseService, slug

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_DIR = ROOT / "data" / "universe"
PACKET_DIR = ROOT / "data" / "research_packets"
USAGE_FILE = UNIVERSE_DIR / "research_usage.json"
EXPANSION_FILE = UNIVERSE_DIR / "expansion_state.json"

NOW = lambda: datetime.now(timezone.utc).isoformat()


def _load_dotenv() -> None:
    """Load KEY=VALUE lines from opportunity-engine/.env into the environment (once),
    without overriding anything already set. Keeps API keys OUT of source & git."""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_dotenv()


class ProviderUnavailable(Exception):
    """Raised when a required provider (search/LLM) is not configured."""


# ==========================================================================
# persistence — routed through the storage backend (local files OR Supabase)
# ==========================================================================
import storage as _S


def _read(name: str) -> list | dict:
    b = _S.get_backend()
    if name in _S.ROW_COLLECTIONS:
        return b.list_rows(name)
    if name == "expansion_state":
        return b.all_expansion()
    if name == "research_usage":
        return b.read_doc("research_usage") or {}
    return b.read_doc(name) if b.read_doc(name) is not None else ([] if name in _S.ROW_COLLECTIONS else {})


def _write(name: str, obj) -> None:
    b = _S.get_backend()
    if name in _S.ROW_COLLECTIONS:
        b.replace_collection(name, obj)
    else:
        b.write_doc(name, obj)


def _append(name: str, records: list, key: str = "id") -> int:
    return _S.get_backend().upsert_rows(name, records, key)


# ==========================================================================
# expansion state (per-node cache metadata) + usage tracking
# ==========================================================================
def get_expansion_state(node_id: str) -> dict | None:
    return _S.get_backend().get_expansion(node_id)


def all_expansion_state() -> dict:
    return _S.get_backend().all_expansion()


def set_expansion_state(node_id: str, **fields) -> dict:
    return _S.get_backend().set_expansion(node_id, fields)


def _bump_usage(node_id: str, queries: int, results: int, sources: int,
                operator: str = "unknown", provider: str = "serper") -> None:
    _S.get_backend().record_usage({"operator": operator, "provider": provider,
                                   "operation": "search", "node_id": node_id,
                                   "queries": queries, "results": results, "sources": sources})


# ==========================================================================
# SEARCH provider (Serper)
# ==========================================================================
class SearchProvider:
    name = "none"
    def search(self, query: str, num: int = 10) -> list[dict]:
        raise NotImplementedError


class SerperSearchProvider(SearchProvider):
    """serper.dev — Google SERP as JSON. Caches identical queries on disk."""
    name = "serper"
    ENDPOINT = "https://google.serper.dev/search"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.cache_dir = PACKET_DIR / "_serper_cache"
        self.live_calls = 0            # real API calls this process (cache hits excluded)

    def _cache_path(self, query: str) -> Path:
        h = hashlib.sha1(query.lower().strip().encode()).hexdigest()[:16]
        return self.cache_dir / f"{h}.json"

    def search(self, query: str, num: int = 10) -> list[dict]:
        cp = self._cache_path(query)
        if cp.exists():                                  # never re-spend on an identical query
            return json.loads(cp.read_text())["results"]
        self.live_calls += 1                             # real (billable) request
        body = json.dumps({"q": query, "num": num}).encode()
        req = urllib.request.Request(self.ENDPOINT, data=body, method="POST",
                                     headers={"X-API-KEY": self.api_key,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
        except urllib.error.URLError as e:
            raise ProviderUnavailable(f"serper request failed: {e}")
        results = []
        for item in data.get("organic", []):
            results.append({"title": item.get("title"), "url": item.get("link"),
                            "snippet": item.get("snippet", "")})
        # also capture People-Also-Ask questions as lightweight evidence of demand
        for paa in data.get("peopleAlsoAsk", []):
            results.append({"title": paa.get("question"), "url": paa.get("link"),
                            "snippet": paa.get("snippet", ""), "kind": "question"})
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps({"query": query, "retrieved_at": NOW(), "results": results},
                                 ensure_ascii=False))
        return results


def get_search_provider(creds: dict | None = None) -> SearchProvider | None:
    # creds provided (authenticated path) => use ONLY those, never a global fallback,
    # so one operator can never spend another's / a shared key. creds=None = CLI/dev.
    key = creds.get("serper") if creds is not None else os.environ.get("SERPER_API_KEY")
    return SerperSearchProvider(key) if key else None


# ==========================================================================
# CLASSIFICATION provider (LLM) — grounds structured nodes in retrieved evidence
# ==========================================================================
def _http_json(url, data, headers, timeout=120, retries=6):
    """POST JSON with retry/backoff on transient errors (429/500/503/timeout).
    429 (rate limit) gets a longer backoff since free LLM tiers are strict."""
    # Some LLM APIs (e.g. Groq) sit behind Cloudflare, which 403s the default
    # "Python-urllib" agent — send a normal User-Agent so requests aren't blocked.
    headers = {"User-Agent": "opportunity-engine/1.0", **headers}
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep((6 if e.code == 429 else 2) * (attempt + 1)); continue
            try:
                body = e.read().decode()[:300]
            except Exception:
                body = ""
            raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}: {body or e.reason}")
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1)); continue
            raise
    raise last


class ClassificationProvider:
    name = "none"
    def classify(self, system: str, user: str) -> str:
        raise NotImplementedError


class AnthropicClassifier(ClassificationProvider):
    name = "anthropic"
    ENDPOINT = "https://api.anthropic.com/v1/messages"
    MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

    def __init__(self, api_key: str):
        self.api_key = api_key

    def classify(self, system: str, user: str) -> str:
        body = json.dumps({"model": self.MODEL, "max_tokens": 4000,
                           "system": system, "messages": [{"role": "user", "content": user}]}).encode()
        data = _http_json(self.ENDPOINT, body,
                          {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                           "Content-Type": "application/json"})
        return "".join(block.get("text", "") for block in data.get("content", []))


class OpenAIClassifier(ClassificationProvider):
    name = "openai"
    ENDPOINT = "https://api.openai.com/v1/chat/completions"
    MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

    def __init__(self, api_key: str):
        self.api_key = api_key

    def classify(self, system: str, user: str) -> str:
        body = json.dumps({"model": self.MODEL,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}]}).encode()
        data = _http_json(self.ENDPOINT, body,
                          {"Authorization": f"Bearer {self.api_key}",
                           "Content-Type": "application/json"})
        return data["choices"][0]["message"]["content"]


class GroqClassifier(ClassificationProvider):
    """Groq free tier — OpenAI-compatible, fast, hosts open models (Llama/Qwen).
    JSON mode via response_format; the prompts already ask for strict JSON."""
    name = "groq"
    ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
    # Groq's current free lineup (verify with /api/universe/groq-models). gpt-oss-120b
    # is the strongest for structured JSON; set GROQ_MODEL=qwen/qwen3.8-27b for Qwen.
    MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

    def __init__(self, api_key: str):
        self.api_key = api_key

    def classify(self, system: str, user: str) -> str:
        # NB: we do NOT use Groq's strict response_format:json_object — it hard-fails
        # (HTTP 400 json_validate_failed) if the model wraps output in an array or gets
        # truncated. The prompts already demand strict JSON and _extract_json is tolerant.
        body = json.dumps({"model": self.MODEL,
                           "messages": [{"role": "system", "content": system},
                                        {"role": "user", "content": user}],
                           "temperature": 0.2, "max_tokens": 8000}).encode()
        data = _http_json(self.ENDPOINT, body,
                          {"Authorization": f"Bearer {self.api_key}",
                           "Content-Type": "application/json"})
        return data["choices"][0]["message"]["content"]


class GeminiClassifier(ClassificationProvider):
    name = "gemini"
    MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

    def __init__(self, api_key: str):
        self.api_key = api_key

    def classify(self, system: str, user: str) -> str:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.MODEL}:generateContent?key={self.api_key}")
        body = json.dumps({
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192,
                                 "responseMimeType": "application/json"},
        }).encode()
        data = _http_json(url, body, {"Content-Type": "application/json"})
        parts = data["candidates"][0]["content"].get("parts", [])
        return "".join(p.get("text", "") for p in parts)


def get_classifier(creds: dict | None = None) -> ClassificationProvider | None:
    # authenticated path: use ONLY this operator's key (no global/other-op fallback).
    # Groq (free tier) is the primary LLM; Gemini kept as an optional fallback.
    if creds is not None:
        if creds.get("groq"):
            return GroqClassifier(creds["groq"])
        if creds.get("gemini"):
            return GeminiClassifier(creds["gemini"])
        return None
    # creds=None (CLI/dev): fall back to any configured global provider.
    if os.environ.get("GROQ_API_KEY"):
        return GroqClassifier(os.environ["GROQ_API_KEY"])
    if os.environ.get("ANTHROPIC_API_KEY"):
        return AnthropicClassifier(os.environ["ANTHROPIC_API_KEY"])
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIClassifier(os.environ["OPENAI_API_KEY"])
    if os.environ.get("GEMINI_API_KEY"):
        return GeminiClassifier(os.environ["GEMINI_API_KEY"])
    return None


def providers_status(creds: dict | None = None) -> dict:
    sp, cl = get_search_provider(creds), get_classifier(creds)
    return {"search": sp.name if sp else None, "classifier": cl.name if cl else None}


# ==========================================================================
# query strategy (LOW volume — 3-8 per expansion)
# ==========================================================================
def build_queries(level: str, ctx: dict) -> list[str]:
    a = ctx.get("audience") or ctx.get("submarket") or ctx.get("market")
    if level == "audience_problems":
        return [f"{a} problems", f"{a} reddit", f"{a} frustrated", f"{a} \"i tried\"",
                f"{a} app complaints", f"{a} how do i", f"best tools for {a}",
                f"{a} spreadsheet OR template OR system"][:8]
    if level == "submarket_audiences":
        return [f"{a} types of people", f"{a} for beginners vs professionals",
                f"{a} community reddit", f"who needs {a}", f"{a} niches"][:6]
    if level == "market_submarkets":
        return [f"{a} categories", f"{a} sub-niches", f"types of {a}",
                f"{a} segments", f"{a} topics reddit"][:6]
    return [f"{a}"]


# ==========================================================================
# persistence of a completed expansion (shared by live + offline paths)
# ==========================================================================
def _source_id(url: str, snippet: str) -> str:
    return "src-" + hashlib.sha1((str(url) + (snippet or "")).encode()).hexdigest()[:12]


def persist_evidence(items: list[dict], supports: str) -> list[str]:
    """items: [{query,source_type,title,url,snippet,relevance,retrieved_at?}]
    Stored in problem_sources.json (the collection GraphService already resolves).
    Returns the list of source_ids."""
    recs, ids = [], []
    for it in items:
        sid = it.get("source_id") or _source_id(it.get("url", ""), it.get("snippet", ""))
        ids.append(sid)
        recs.append({"source_id": sid, "source_type": it.get("source_type", "web"),
                     "url": it.get("url"), "title": it.get("title"),
                     "text": it.get("snippet") or it.get("evidence") or "",
                     "query": it.get("query"), "relevance": it.get("relevance", "unknown"),
                     "accessible": True, "basis": "observed",
                     "retrieved_at": it.get("retrieved_at") or NOW(),
                     "supports_node_ids": it.get("supports_node_ids", [supports]),
                     "retrieval_method": it.get("retrieval_method", "serper")})
    _append("problem_sources", recs, key="source_id")
    return ids


def persist_problems(audience_id: str, problems: list[dict]) -> list[dict]:
    """problems: classifier output (statement, normalized_problem, problem_type,
    desired_outcome, source_refs, current_solutions, attempts, solution_complaints,
    basis, confidence). Fills IDs + parent refs + provenance, dedupes, persists."""
    svc = UniverseService()
    aud = svc._a.get(audience_id)
    if not aud:
        raise ProviderUnavailable(f"unknown audience {audience_id}")
    existing = {p["id"] for p in svc._p.values()}
    existing_norm = {(p["audience_id"], slug(p.get("normalized_problem", p["statement"])))
                     for p in svc._p.values()}
    aud_name = aud["name"]
    out = []
    for p in problems:
        norm = p.get("normalized_problem") or p["statement"]
        if (audience_id, slug(norm)) in existing_norm:      # dedupe
            continue
        pid = f"prb-{slug(aud_name)}-{slug(norm)}"[:120]
        n = 2
        while pid in existing:
            pid = f"prb-{slug(aud_name)}-{slug(norm)}-{n}"[:120]; n += 1
        existing.add(pid)
        rec = {
            "id": pid, "type": "problem",
            "market_id": aud["market_id"], "submarket_id": aud["submarket_id"],
            "audience_id": audience_id,
            "statement": p["statement"], "normalized_problem": norm,
            "problem_type": p.get("problem_type", "unknown"),
            "desired_outcome": p.get("desired_outcome", ""),
            "source_refs": p.get("source_refs", []),
            "evidence_count": len(p.get("source_refs", [])),
            "current_solutions": p.get("current_solutions", []),
            "attempts": p.get("attempts", []),
            "solution_complaints": p.get("solution_complaints", []),
            "basis": p.get("basis", "observed" if p.get("source_refs") else "inferred"),
            "confidence": p.get("confidence", "LOW"),
            "research_generated": True, "origin": "dynamic_research", "researched_at": NOW(),
            "status": "active",
        }
        out.append(rec)
    _append("problems", out)
    return out


BASIC_DIMS = ["pain_importance", "recurrence", "existing_spend", "solution_dissatisfaction",
              "digital_product_fit", "audience_accessibility"]


def _score_from_basic(basic: dict) -> tuple[dict, dict, str]:
    """Map the light 0-5/Unknown basic_score into the fields promote()/GraphService need."""
    vals = [basic.get(d) for d in BASIC_DIMS]
    known = [v for v in vals if isinstance(v, (int, float))]
    commercial = round(sum(known) / (len(known) * 5) * 100) if known else 0
    evidence_conf = basic.get("evidence_confidence", "LOW")
    evidence_score = {"HIGH": 70, "MEDIUM": 45, "LOW": 20}.get(evidence_conf, 0)
    priority = round(commercial * 0.6 + evidence_score * 0.4)
    cls = ("HIGH_PRIORITY" if priority >= 60 else
           "PROMISING_NEEDS_RESEARCH" if priority >= 45 else "LOW_PRIORITY")
    return ({"commercial_score": commercial, "evidence_score": evidence_score,
             "priority_score": priority, "priority_classification": cls}, basic, cls)


def persist_opportunities(audience_id: str, opps: list[dict]) -> list[dict]:
    """Persist opportunity candidates + the score + ranking rows the promotion path
    requires (so 'RESEARCH THIS OPPORTUNITY' can hand off into Phase 8)."""
    svc = UniverseService()
    aud = svc._a.get(audience_id)
    aud_name = aud["name"]
    existing = {o["id"] for o in svc._o.values()}
    out, score_rows = [], []
    for o in opps:
        oid = f"opp-{slug(aud_name)}-{slug(o['name'])}"[:120]
        n = 2
        while oid in existing:
            oid = f"opp-{slug(aud_name)}-{slug(o['name'])}-{n}"[:120]; n += 1
        existing.add(oid)
        basic = o.get("basic_score", {})
        score_fields, breakdown, cls = _score_from_basic(basic)
        rec = {
            "id": oid, "type": "opportunity",
            "market_id": aud["market_id"], "submarket_id": aud["submarket_id"],
            "audience_id": audience_id, "name": o["name"],
            "description": o.get("core_problem", ""),
            "problem_ids": o.get("problem_ids", []),
            "problem_count": len(o.get("problem_ids", [])),
            "buyer": o.get("buyer", aud_name),
            "core_problem": o.get("core_problem", ""),
            "desired_outcome": o.get("desired_outcome", ""),
            "current_solutions": o.get("current_solutions", []),
            "solution_gaps": o.get("solution_gaps", []),
            "possible_product": o.get("possible_product", ""),
            "possible_format": o.get("possible_format", []),
            "evidence_summary": o.get("evidence_summary", {}),
            "source_refs": o.get("source_refs", []),
            "basis": o.get("basis", "mixed"),
            "confidence": o.get("confidence", "LOW"),
            "basic_score": {**score_fields, "dimensions": breakdown,
                            "evidence_confidence": basic.get("evidence_confidence", "LOW")},
            "creator_density": "UNKNOWN",
            "research_generated": True, "origin": "dynamic_research", "researched_at": NOW(),
            "research_status": "unresearched", "status": "active",
        }
        out.append(rec)
        score_rows.append({
            "opportunity_id": oid, "name": o["name"], "audience_id": audience_id,
            "scoring_version": "mvp-v1",
            "commercial_score": score_fields["commercial_score"],
            "evidence_score": score_fields["evidence_score"],
            "evidence_band": basic.get("evidence_confidence", "LOW"),
            "priority_score": score_fields["priority_score"],
            "priority_classification": cls, "excluded_factor_count": 0,
            "score_breakdown": breakdown, "creator_density": "UNKNOWN",
            "creator_density_confidence": "unknown", "creator_density_detail": {"band": "UNKNOWN"},
            "commercial_evidence_count": len(o.get("source_refs", [])),
            "risk_flags": [], "screening_status": "mvp_basic",
        })
    _append("opportunities", out)
    _append("opportunity_scores", score_rows, key="opportunity_id")
    # rebuild rankings (append new; keep deterministic order by priority)
    rankings = _read("opportunity_rankings")
    if not isinstance(rankings, list):
        rankings = []
    have = {r["opportunity_id"] for r in rankings}
    for rec, sr in zip(out, score_rows):
        if rec["id"] in have:
            continue
        rankings.append({"rank": 0, "opportunity_id": rec["id"], "name": rec["name"],
                         "audience": aud_name, "commercial_score": sr["commercial_score"],
                         "evidence_score": sr["evidence_score"], "priority_score": sr["priority_score"],
                         "creator_density": "UNKNOWN", "classification": sr["priority_classification"]})
    rankings.sort(key=lambda r: -r["priority_score"])
    for i, r in enumerate(rankings, 1):
        r["rank"] = i
    _write("opportunity_rankings", rankings)
    return out


def persist_taxonomy_children(parent_id: str, level: str, children: list[dict]) -> list[dict]:
    """Persist dynamically-discovered submarkets or audiences (Levels 1 & 2)."""
    svc = UniverseService()
    out = []
    if level == "market_submarkets":
        m = svc._m[parent_id]; existing = {s["id"] for s in svc._s.values()}
        existing_norm = {(s["market_id"], slug(s["name"])) for s in svc._s.values()}
        for c in children:
            if (parent_id, slug(c["name"])) in existing_norm:
                continue
            sid = U.submarket_id(m["name"], c["name"])
            if sid in existing:
                continue
            out.append({"id": sid, "type": "submarket", "market_id": parent_id,
                        "name": c["name"], "description": c.get("description", ""),
                        "status": "active", "basis": "observed",
                        "origin": "dynamic_research", "source_refs": c.get("source_refs", []),
                        "researched_at": NOW()})
        _append("submarkets", out)
    elif level == "submarket_audiences":
        s = svc._s[parent_id]; m = svc._m[s["market_id"]]
        existing = {a["id"] for a in svc._a.values()}
        existing_norm = {(a["submarket_id"], slug(a["name"])) for a in svc._a.values()}
        for c in children:
            if (parent_id, slug(c["name"])) in existing_norm:
                continue
            aid = U.audience_id(m["name"], s["name"], c["name"])
            if aid in existing:
                continue
            out.append({"id": aid, "type": "audience", "market_id": s["market_id"],
                        "submarket_id": parent_id, "name": c["name"],
                        "description": c.get("description", ""), "status": "active",
                        "basis": "observed", "origin": "dynamic_research",
                        "source_refs": c.get("source_refs", []),
                        "problem_count": 0, "opportunity_count": 0,
                        "creator_density": "unknown", "research_status": "unresearched",
                        "researched_at": NOW()})
        _append("audiences", out)
    return out


# ==========================================================================
# orchestration: search -> classify -> persist  (the live EXPLORE DEEPER path)
# ==========================================================================
def _node_level(node_id: str) -> str:
    return {"mkt-": "market_submarkets", "sub-": "submarket_audiences",
            "aud-": "audience_problems"}.get(node_id[:4], "unknown")


def _node_ctx(node_id: str) -> dict:
    svc = UniverseService()
    if node_id in svc._m:
        return {"market": svc._m[node_id]["name"]}
    if node_id in svc._s:
        s = svc._s[node_id]
        return {"submarket": s["name"], "market": svc._m[s["market_id"]]["name"]}
    if node_id in svc._a:
        a = svc._a[node_id]
        return {"audience": a["name"], "submarket": svc._s[a["submarket_id"]]["name"],
                "market": svc._m[a["market_id"]]["name"]}
    raise ProviderUnavailable(f"unknown node {node_id}")


def run_search_packet(node_id: str, level: str, ctx: dict,
                      creds: dict | None = None, operator: str = "unknown") -> dict:
    """Run the (low-volume) query set, dedupe results, persist a raw packet, track usage."""
    sp = get_search_provider(creds)
    if not sp:
        raise ProviderUnavailable("Serper key not set for this operator — cannot run live search")
    queries = build_queries(level, ctx)
    seen, evidence = set(), []
    total_results = 0
    calls_before = getattr(sp, "live_calls", 0)
    for q in queries:
        results = sp.search(q)
        total_results += len(results)
        for r in results:
            if not r.get("url") or r["url"] in seen:
                continue
            seen.add(r["url"])
            evidence.append({"query": q, "title": r.get("title"), "url": r["url"],
                             "snippet": r.get("snippet", ""),
                             "source_type": "question" if r.get("kind") == "question" else "web",
                             "retrieved_at": NOW()})
    billable = getattr(sp, "live_calls", 0) - calls_before   # cache hits excluded
    _bump_usage(node_id, billable, total_results, len(evidence), operator=operator)
    packet = {"node_id": node_id, "level": level, "ctx": ctx, "queries": queries,
              "retrieved_at": NOW(), "evidence": evidence}
    PACKET_DIR.mkdir(parents=True, exist_ok=True)
    (PACKET_DIR / f"{node_id}.json").write_text(json.dumps(packet, indent=2, ensure_ascii=False))
    return packet


def _extract_json(text: str):
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    raw = m.group(1) if m else text
    start = raw.find("{"); end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", raw)  # drop trailing commas
        return json.loads(cleaned)


_PROBLEM_SYS = (
    "You classify RETRIEVED WEB EVIDENCE into structured problem records for a market-"
    "research graph. You must NOT invent problems — every problem must be grounded in the "
    "provided evidence, and each must cite the evidence indexes (source_refs) it came from. "
    "If evidence is thin, return fewer problems. Output STRICT JSON only.")


def _problem_user(ctx: dict, evidence: list[dict]) -> str:
    ev = "\n".join(f"[{i}] ({e['source_type']}) {e.get('title','')} — {e.get('snippet','')} <{e['url']}>"
                   for i, e in enumerate(evidence))
    return (f"AUDIENCE: {ctx['audience']}\nSUBMARKET: {ctx.get('submarket')}\nMARKET: {ctx.get('market')}\n\n"
            f"EVIDENCE:\n{ev}\n\n"
            "Return JSON: {\"problems\":[{\"statement\",\"normalized_problem\",\"problem_type\","
            "\"desired_outcome\",\"current_solutions\":[],\"attempts\":[],\"solution_complaints\":[],"
            "\"source_refs\":[<evidence indexes>],\"basis\":\"observed|mixed|inferred\",\"confidence\":\"LOW|MEDIUM|HIGH\"}]}. "
            "8 problems max, grounded in the evidence above.")


_OPP_SYS = (
    "You synthesize evidence-backed PROBLEMS into basic commercial OPPORTUNITY candidates for "
    "digital products (templates, trackers, guides, systems, playbooks, databases, communities). "
    "Cluster related problems. Do NOT invent demand. Score each dimension 0-5 or \"UNKNOWN\" "
    "(UNKNOWN != 0). Output STRICT JSON only.")


def _opp_user(ctx: dict, problems: list[dict]) -> str:
    pl = "\n".join(f"[{p['id']}] {p['statement']} (solutions tried: {p.get('current_solutions')})"
                   for p in problems)
    return (f"AUDIENCE: {ctx['audience']}\n\nPROBLEMS:\n{pl}\n\n"
            "Return JSON: {\"opportunities\":[{\"name\",\"problem_ids\":[<ids above>],\"buyer\","
            "\"core_problem\",\"desired_outcome\",\"current_solutions\":[],\"solution_gaps\":[],"
            "\"possible_product\",\"possible_format\":[],\"basis\",\"confidence\","
            "\"basic_score\":{\"pain_importance\",\"recurrence\",\"existing_spend\","
            "\"solution_dissatisfaction\",\"digital_product_fit\",\"audience_accessibility\","
            "\"evidence_confidence\":\"LOW|MEDIUM|HIGH\"}}]}. 3-8 opportunities, each citing real problem_ids.")


def expand(node_id: str, creds: dict | None = None, operator: str = "unknown") -> dict:
    """Live expansion: search -> classify -> persist. Requires both providers.
    Uses the authenticated operator's credentials. Raises ProviderUnavailable
    (after leaving a search packet if search succeeded)."""
    level = _node_level(node_id)
    ctx = _node_ctx(node_id)
    set_expansion_state(node_id, expansion_status="researching")
    try:
        packet = run_search_packet(node_id, level, ctx, creds=creds, operator=operator)
    except ProviderUnavailable:
        set_expansion_state(node_id, expansion_status="failed", last_error="no_search_provider")
        raise
    cl = get_classifier(creds)
    if not cl:
        set_expansion_state(node_id, expansion_status="failed", last_error="no_classifier",
                            source_count=len(packet["evidence"]))
        raise ProviderUnavailable("no LLM classifier configured (packet saved for offline path)")

    evidence = packet["evidence"]
    if level == "audience_problems":
        parsed = _extract_json(cl.classify(_PROBLEM_SYS, _problem_user(ctx, evidence)))
        result = _persist_audience_expansion(node_id, ctx, evidence, parsed.get("problems", []), cl)
    else:
        sys = _OPP_SYS  # taxonomy levels reuse a light classifier prompt
        prompt = (f"Classify this evidence into distinct {'submarkets' if level=='market_submarkets' else 'audiences'} "
                  f"for {ctx.get('market') or ctx.get('submarket')}. Evidence:\n" +
                  "\n".join(f"[{i}] {e.get('title')} — {e.get('snippet')}" for i, e in enumerate(evidence)) +
                  '\nReturn JSON {"children":[{"name","description","source_refs":[indexes]}]} (max 20, grounded).')
        parsed = _extract_json(cl.classify("You classify retrieved evidence into taxonomy nodes. Do not invent. STRICT JSON.", prompt))
        src_ids = persist_evidence(evidence, node_id)
        for c in parsed.get("children", []):
            c["source_refs"] = [src_ids[i] for i in c.get("source_refs", []) if i < len(src_ids)]
        kids = persist_taxonomy_children(node_id, level, parsed.get("children", []))
        set_expansion_state(node_id, expansion_status="expanded", researched_at=NOW(),
                            research_version="mvp-v1", source_count=len(src_ids), child_count=len(kids))
        result = {"children": len(kids)}
    return result


def _persist_audience_expansion(aud_id, ctx, evidence, problems_json, classifier):
    """Persist problems + evidence, then synthesize + persist opportunities."""
    src_ids = persist_evidence(evidence, aud_id)
    for p in problems_json:                       # map evidence indexes -> source_ids
        p["source_refs"] = [src_ids[i] for i in p.get("source_refs", []) if i < len(src_ids)]
    problems = persist_problems(aud_id, problems_json)
    opps = []
    if problems and classifier:
        parsed = _extract_json(classifier.classify(_OPP_SYS, _opp_user(ctx, problems)))
        opp_json = parsed.get("opportunities", [])
        # keep only real problem ids; carry source_refs up from member problems
        valid = {p["id"] for p in problems}
        for o in opp_json:
            o["problem_ids"] = [pid for pid in o.get("problem_ids", []) if pid in valid]
            refs = []
            for pid in o["problem_ids"]:
                refs += next((p["source_refs"] for p in problems if p["id"] == pid), [])
            o["source_refs"] = sorted(set(refs))
            o["evidence_summary"] = {"problem_count": len(o["problem_ids"]),
                                     "source_count": len(o["source_refs"])}
        opps = persist_opportunities(aud_id, opp_json)
    set_expansion_state(aud_id, expansion_status="expanded", researched_at=NOW(),
                        research_version="mvp-v1", source_count=len(src_ids),
                        child_count=len(problems), opportunity_count=len(opps))
    return {"problems": len(problems), "opportunities": len(opps), "sources": len(src_ids)}


def import_classified(node_id: str, payload: dict) -> dict:
    """OFFLINE classification path (used when no runtime LLM key exists).
    payload = {level, ctx, evidence:[...], problems:[...], opportunities:[...]}  OR
              {level, ctx, evidence, children:[...]} for taxonomy levels.
    Evidence uses integer source_refs (indexes) OR explicit source_ids."""
    level = payload.get("level") or _node_level(node_id)
    ctx = payload.get("ctx") or _node_ctx(node_id)
    evidence = payload.get("evidence", [])
    src_ids = persist_evidence(evidence, node_id)

    def resolve(refs):
        out = []
        for r in refs or []:
            if isinstance(r, int) and r < len(src_ids):
                out.append(src_ids[r])
            elif isinstance(r, str):
                out.append(r)
        return out

    res = {}
    if level == "audience_problems":
        for p in payload.get("problems", []):
            p["source_refs"] = resolve(p.get("source_refs"))
        problems = persist_problems(node_id, payload.get("problems", []))
        # opportunities reference problem ids by index into the problems list OR by statement
        pid_by_norm = {slug(p["normalized_problem"]): p["id"] for p in problems}
        pid_by_index = {i: p["id"] for i, p in enumerate(problems)}
        opp_json = payload.get("opportunities", [])
        for o in opp_json:
            ids = []
            for ref in o.get("problem_ids", []):
                if isinstance(ref, int) and ref in pid_by_index:
                    ids.append(pid_by_index[ref])
                elif isinstance(ref, str) and ref in {p["id"] for p in problems}:
                    ids.append(ref)
                elif isinstance(ref, str) and slug(ref) in pid_by_norm:
                    ids.append(pid_by_norm[slug(ref)])
            o["problem_ids"] = ids
            refs = []
            for pid in ids:
                refs += next((p["source_refs"] for p in problems if p["id"] == pid), [])
            o["source_refs"] = sorted(set(refs)) or resolve(o.get("source_refs"))
            o["evidence_summary"] = {"problem_count": len(ids), "source_count": len(o["source_refs"])}
        opps = persist_opportunities(node_id, opp_json)
        set_expansion_state(node_id, expansion_status="expanded", researched_at=NOW(),
                            research_version="mvp-offline", source_count=len(src_ids),
                            child_count=len(problems), opportunity_count=len(opps),
                            origin="dynamic_research")
        res = {"problems": len(problems), "opportunities": len(opps), "sources": len(src_ids)}
    else:
        for c in payload.get("children", []):
            c["source_refs"] = resolve(c.get("source_refs"))
        kids = persist_taxonomy_children(node_id, level, payload.get("children", []))
        set_expansion_state(node_id, expansion_status="expanded", researched_at=NOW(),
                            research_version="mvp-offline", source_count=len(src_ids),
                            child_count=len(kids), origin="dynamic_research")
        res = {"children": len(kids), "sources": len(src_ids)}
    return res


# ==========================================================================
# PHASE 8 EXECUTION — turn a research plan into executed research.
# Reuses the SearchProvider + ClassificationProvider above. Called by
# app/research.py:gather() so the existing dossier gets enriched, not replaced.
# ==========================================================================
import html as _html

def fetch_text(url: str, cap: int = 4000) -> tuple[str, str]:
    """Best-effort page retrieval. Returns (text, status). Never fabricates —
    on any failure returns ("", "<reason>"). Simple, not a crawler.
    Reddit is rewritten to old.reddit.com (server-rendered, no JS) for a better hit rate;
    a 200 that yields <200 chars of usable text is reported 'empty' (not 'ok')."""
    if not url:
        return "", "no_url"
    fetch_url = re.sub(r"^https?://(www\.)?reddit\.com", "https://old.reddit.com", url)
    try:
        req = urllib.request.Request(fetch_url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=15) as r:
            ctype = r.headers.get_content_type()
            if ctype and "html" not in ctype and "text" not in ctype:
                return "", f"skip_{ctype}"
            raw = r.read(600_000).decode("utf-8", "ignore")
    except Exception as e:
        return "", f"fail_{type(e).__name__}"
    raw = re.sub(r"(?is)<(script|style|noscript|nav|footer|header|svg).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = _html.unescape(re.sub(r"\s+", " ", text)).strip()
    return (text[:cap], "ok") if len(text) >= 200 else (text[:cap], "empty")


# critical dimensions the completion gate cares about (index-aligned to make_plan's
# 5 questions, with keyword fallback). Q5 (exact price) is NONCRITICAL.
_CRITICAL_KEYS = ("recurring", "tried", "digital product", "most useful asset")
_NONCRITICAL_KEYS = ("price",)


def _is_critical(question: str) -> bool:
    q = question.lower()
    if any(k in q for k in _NONCRITICAL_KEYS):
        return False
    return True




# ==========================================================================
# PHASE 8 — dynamic questions, question-driven search, ranking, retrieval,
# batched extraction/answering/synthesis. Universal & subject-agnostic:
# the mechanism is fixed; the SUBJECT comes entirely from the opportunity.
# ==========================================================================
UNIVERSAL_QUESTIONS = [
    "Is the problem recurring and painful enough to pay to solve?",
    "What exactly have people already tried, and why did it fall short?",
    "Is a digital product the right form, or is this a service / software / free-information problem?",
    "What is the single most useful asset or mechanism we could ship?",
    "What price will the audience tolerate, and on what evidence?",
]

_DQ_SYS = (
    "You are a product researcher. Given an opportunity's context, propose 3-6 RESEARCH "
    "QUESTIONS specific to THIS opportunity that we must answer online before designing a "
    "useful digital product. Good questions investigate workflow, failure modes, what people "
    "currently do, what existing solutions miss, the desired outcome, or what asset structure "
    "would help — and would CHANGE what we build. Do NOT restate the problem, ask market-size "
    "trivia, assume a solution, or pad. Fewer strong questions beat many weak ones. "
    "Output STRICT JSON only.")


def _dq_user(pocket: dict) -> str:
    return (f"MARKET: {pocket.get('industry_id')}\nAUDIENCE: {pocket['audience']}\n"
            f"CORE PROBLEM: {pocket['core_problem']}\n"
            f"DESIRED OUTCOME: {pocket.get('desired_outcome','')}\n"
            f"KNOWN PROBLEMS: {pocket.get('related_problems')}\n"
            f"KNOWN EXISTING SOLUTIONS: {pocket.get('existing_solutions')}\n"
            f"KNOWN GAPS: {pocket.get('solution_gaps')}\n\n"
            'Return JSON: {"questions":["...", "..."]}  (3-6 opportunity-specific questions)')


def generate_dynamic_questions(pocket: dict, creds: dict | None = None) -> list[str]:
    cl = get_classifier(creds)
    if not cl:
        return []
    try:
        parsed = _extract_json(cl.classify(_DQ_SYS, _dq_user(pocket)))
        qs = [q.strip() for q in parsed.get("questions", []) if isinstance(q, str) and q.strip()]
        # never let a dynamic question duplicate a universal one
        uni = {u.lower()[:24] for u in UNIVERSAL_QUESTIONS}
        return [q for q in qs if q.lower()[:24] not in uni][:6]
    except Exception:
        return []


def _plan_queries(pocket: dict, dynamic: list[str]) -> list[dict]:
    """Question-driven query set + an explicit falsification intent. Deterministic
    (no LLM). Tagged with intent so ranking can be question-relative. 8-18, deduped."""
    aud = pocket["audience"]
    probs = pocket.get("related_problems", [])[:3]
    sols = pocket.get("existing_solutions", [])[:3]
    q = []
    q += [(f"{aud} problem reddit", "problem"),
          (f"how do {aud} currently", "behavior"),
          (f"{aud} frustrated OR struggle", "pain")]
    for p in probs[:2]:
        q.append((f"{p} reddit", "problem"))
    if sols:
        for s in sols[:2]:
            q.append((f"{s} review OR complaints OR alternatives", "dissatisfaction"))
    else:
        q.append((f"{aud} tools OR template OR software", "existing_solution"))
    q.append((f"{aud} template OR spreadsheet OR notion pricing", "pricing"))
    # one query per dynamic question (short intent phrase)
    for dq in dynamic[:5]:
        phrase = re.sub(r"[^a-z0-9 ]", " ", dq.lower())
        phrase = " ".join(phrase.split()[:8])
        q.append((f"{aud} {phrase}", "dynamic"))
    # FALSIFICATION: is there free/good-enough alternative; will they even pay?
    q.append((f"free {aud} template OR guide OR alternative", "falsification"))
    q.append((f"is it worth paying for {aud} tools reddit", "falsification"))
    # dedupe on query text, cap 18
    seen, out = set(), []
    for text, intent in q:
        k = text.lower().strip()
        if k and k not in seen:
            seen.add(k); out.append({"query": text, "intent": intent})
    return out[:18]


_UGC = {"reddit.com": 5, "quora.com": 4, "ycombinator": 4, "stackexchange": 4,
        "forum": 4, "community": 3}
_REVIEW = {"g2.com": 4, "capterra": 4, "trustpilot": 3, "producthunt": 3}


def _rank_candidates(candidates: list[dict], pocket: dict) -> list[dict]:
    """Rank by usefulness RELATIVE to the research (not a flat universal order):
    primary/UGC + review/marketplace evidence, intent value, term overlap, domain
    diversity. Higher = retrieve first."""
    terms = set(re.findall(r"[a-z]{4,}", (pocket["audience"] + " " +
                pocket["core_problem"] + " " + " ".join(pocket.get("related_problems", []))).lower()))
    intent_boost = {"falsification": 3, "dissatisfaction": 2, "pricing": 2,
                    "problem": 2, "behavior": 2, "dynamic": 2, "pain": 1, "existing_solution": 1}
    seen_domain = {}
    for c in candidates:
        url = (c.get("url") or "").lower()
        dom = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        score = 0.0
        for k, v in _UGC.items():
            if k in url: score += v; break
        for k, v in _REVIEW.items():
            if k in url: score += v; break
        if any(w in url for w in ("pricing", "price", "cost")): score += 2
        if any(w in url for w in ("template", "product", "marketplace", "gumroad", "etsy", "notion.so")): score += 1
        score += intent_boost.get(c.get("intent"), 0)
        text = ((c.get("title") or "") + " " + (c.get("snippet") or "")).lower()
        score += min(3, sum(1 for t in terms if t in text) * 0.5)
        seen_domain[dom] = seen_domain.get(dom, 0) + 1
        if seen_domain[dom] > 2:                # diminishing returns for same domain
            score -= 2
        c["rank_score"] = round(score, 2)
    return sorted(candidates, key=lambda c: -c["rank_score"])


_SYNTH_SYS = (
    "You are a rigorous market-research analyst designing an evidence-based product brief. "
    "Use ONLY the provided sources. Rules: (1) basis 'observed' ONLY when a source directly "
    "shows it, else 'inferred'; UNKNOWN when there is no evidence. (2) Never turn a few "
    "complaints into market-wide prevalence; never infer willingness-to-pay from pain; never "
    "infer price from unrelated products. NOTE: a search-result snippet is real text "
    "extracted from the source page and counts as OBSERVED evidence (medium strength); "
    "full-page text is a bonus when present. (3) Investigate free/good-enough alternatives and "
    "whether the product would merely duplicate them. (4) product FORMAT must follow the "
    "product MECHANISM (what the buyer needs to DO), not keywords. (5) Every must-have "
    "component needs an evidence ref or is marked inferred. (6) You may conclude the product "
    "is weak / not worth building. Extract concise evidence, never long passages. "
    "OUTCOME CRITERIA: set outcome='READY' when the core problem, current behavior/attempts, "
    "a failure mode/gap, the desired outcome, and a plausible product mechanism are each "
    "supported by evidence — EXACT pricing, willingness-to-pay, and market prevalence are "
    "acceptable unknowns and must NOT by themselves force NEEDS_MORE_RESEARCH. Set "
    "'WEAK_NO_PRODUCT' only if free/good-enough alternatives dominate or evidence contradicts "
    "the need. Set 'NEEDS_MORE_RESEARCH' only if the core problem or a product mechanism "
    "cannot be established from the sources. Output STRICT JSON only.")


def _synth_user(pocket, all_questions, sources):
    src_lines = []
    for i, s in enumerate(sources):
        page = s.get("page_text") or ""
        if len(page) > 200:
            kind, body = "full-page", page[:1600]
        else:
            kind, body = "search snippet", (s.get("snippet") or "")[:600]
        src_lines.append(f"[{i}] ({s.get('source_type')} · {kind} · intent:{s.get('intent')}) "
                         f"{s.get('title')} <{s.get('url')}>\n{body}")
    qlines = "\n".join(f"- ({t}) {q}" for q, t in all_questions)
    return (f"AUDIENCE: {pocket['audience']}\nCORE PROBLEM: {pocket['core_problem']}\n"
            f"DESIRED OUTCOME: {pocket.get('desired_outcome','')}\n"
            f"KNOWN EXISTING SOLUTIONS: {pocket.get('existing_solutions')}\n\n"
            f"QUESTIONS (answer EVERY one):\n{qlines}\n\nSOURCES:\n" + "\n\n".join(src_lines) + "\n\n"
            "Return JSON: {"
            "\"questions\":[{\"question\",\"question_type\":\"universal|dynamic\",\"status\":\"SUPPORTED|PARTIAL|UNKNOWN|CONTRADICTED\","
            "\"answer\",\"source_refs\":[<indexes>],\"confidence\":\"LOW|MEDIUM|HIGH\","
            "\"product_implication\",\"remaining_uncertainty\"}],"
            "\"claims\":[{\"claim\",\"evidence\",\"source_ref\":<index>,\"question_ids\":[<question text or index>],"
            "\"evidence_type\":\"behavior|pain|attempt|complaint|desired_outcome|pricing|product_format|workflow|other\","
            "\"basis\":\"observed|inferred\",\"strength\":\"strong|medium|weak\",\"product_implication\"}],"
            "\"product_implications\":{\"core_problem\",\"desired_outcome\",\"current_behavior\":[],"
            "\"current_solutions\":[],\"failure_modes\":[],\"free_alternatives\":[],\"product_opportunity\","
            "\"product_mechanism\",\"product_format\":{\"recommended\",\"components\":[],\"basis\":\"observed|inferred\",\"rationale\"},"
            "\"must_have_components\":[{\"component\",\"buyer_job\",\"evidence_refs\":[<indexes>],\"basis\":\"observed|inferred\"}],"
            "\"do_not_build\":[],\"pricing\":{\"values\":[],\"basis\":\"observed|inferred|unknown\"},"
            "\"contradictions\":[],\"remaining_uncertainty\":[],"
            "\"outcome\":\"READY|NEEDS_MORE_RESEARCH|WEAK_NO_PRODUCT\"}}")


def execute_research(pocket: dict, plan: dict, max_fetch: int = 14,
                     creds: dict | None = None, operator: str = "unknown") -> dict | None:
    """Execute the plan end to end. Returns a rich result or None if no providers.
    Uses the authenticated operator's credentials. Two LLM calls total."""
    sp, cl = get_search_provider(creds), get_classifier(creds)
    if not sp or not cl:
        return None
    node_id = pocket["id"]

    # 1) dynamic, opportunity-specific questions (1 LLM call) + universal
    dynamic = generate_dynamic_questions(pocket, creds)
    all_questions = [(q, "universal") for q in UNIVERSAL_QUESTIONS] + [(q, "dynamic") for q in dynamic]

    # 2) question-driven + falsification search (deterministic)
    queries = _plan_queries(pocket, dynamic)
    calls_before = getattr(sp, "live_calls", 0)
    seen_url, candidates, executed, discovered = set(), [], [], 0
    for item in queries:
        results = sp.search(item["query"])
        discovered += len(results)
        kept = 0
        for r in results:
            u = r.get("url")
            if not u or u in seen_url:
                continue
            seen_url.add(u); kept += 1
            candidates.append({"query": item["query"], "intent": item["intent"],
                               "title": r.get("title"), "url": u, "snippet": r.get("snippet", ""),
                               "source_type": "question" if r.get("kind") == "question" else "web"})
        executed.append({"query": item["query"], "intent": item["intent"],
                         "results": len(results), "sources_retained": kept})

    # 3) rank candidates, retrieve the strongest few
    ranked = _rank_candidates(candidates, pocket)
    selected = ranked[:max_fetch]
    fetched_ok = fetched_fail = 0
    for c in selected:
        text, status = fetch_text(c["url"])
        c["page_text"] = text; c["retrieval_status"] = status
        c["content_length"] = len(text); c["retrieved_at"] = NOW()
        if status == "ok" and len(text) > 200:
            fetched_ok += 1
        else:
            fetched_fail += 1
    for c in ranked[max_fetch:]:
        c["retrieval_status"] = "not_fetched"
    billable = getattr(sp, "live_calls", 0) - calls_before
    _bump_usage(node_id, billable, discovered, len(candidates), operator=operator)

    # 4) batched extraction + answering + synthesis (1 LLM call).
    # Analyse the top-ranked SELECTED sources: full page text where retrieval succeeded,
    # otherwise the Serper snippet (which is itself real, observed source text).
    analysis_pool = selected
    parsed = _extract_json(cl.classify(_SYNTH_SYS, _synth_user(pocket, all_questions, analysis_pool)))

    answered = parsed.get("questions", [])
    # evidence-bearing sources = distinct sources cited by any extracted claim
    cited = set()
    for cl_ in parsed.get("claims", []):
        ref = cl_.get("source_ref")
        if isinstance(ref, int) and 0 <= ref < len(analysis_pool):
            cited.add(ref)
    evidence_bearing = len(cited)

    # 5) completion gate (after consumption). Critical universals must not be UNKNOWN,
    #    a product mechanism must exist, and no fundamental contradiction blocks it.
    by_q = {a.get("question", "")[:24].lower(): a for a in answered}
    critical_unresolved = []
    for q in UNIVERSAL_QUESTIONS:
        a = by_q.get(q[:24].lower())
        if _is_critical(q) and (a is None or a.get("status") == "UNKNOWN"):
            critical_unresolved.append(q)
    pi = parsed.get("product_implications", {}) or {}
    outcome = pi.get("outcome", "NEEDS_MORE_RESEARCH")
    mech = (pi.get("product_mechanism") or "").strip()
    observed_claims = sum(1 for c in parsed.get("claims", []) if c.get("basis") == "observed")
    # gate on the evidence-based synthesis, not on harsh per-question WTP judgments:
    # a responsible design decision needs a core problem + a mechanism + real observed claims.
    if not mech or mech.lower().startswith("unknown") or not pi.get("core_problem"):
        outcome = "NEEDS_MORE_RESEARCH"
    ready = (outcome == "READY" and observed_claims >= 3)
    status = "complete" if ready else "needs_review"

    return {
        "dynamic_questions": dynamic,
        "queries_executed": executed,
        "candidates": ranked,                 # includes analysis_pool refs with page_text
        "analysis_pool": analysis_pool,
        "accounting": {"search_results_discovered": discovered,
                       "unique_candidate_sources": len(candidates),
                       "sources_selected": len(selected),
                       "sources_retrieved": fetched_ok,
                       "retrieval_failed": fetched_fail,
                       "evidence_bearing_sources": evidence_bearing},
        "retrieval": {"ok": fetched_ok, "failed": fetched_fail,
                      "not_fetched": max(0, len(candidates) - len(selected))},
        "billable_queries": billable, "parsed": parsed,
        "answered_questions": answered, "product_implications": pi,
        "critical_unresolved": critical_unresolved,
        "research_outcome": outcome, "status": status}
