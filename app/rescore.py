"""Phase-1 curation runtime — rescore ONE opportunity from real evidence, persist
to shared storage. Density comes from the real creator-discovery layer (Serper+Groq,
strong recall); demand (WTP + weakness) from a focused Serper+Groq pass. Feeds the
two evidence slots the Build-4 scorer already consumes, then rescopes that opp and
upserts its score to storage. Rankings are rebuilt separately once all opps are done.

Honest: only real URLs/items; unknowns stay unknown (which correctly lowers the
score). Uses the signed-in operator's Serper + Groq keys.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CD_DIR = ROOT / "data" / "creator_density_inputs"
CI_DIR = ROOT / "data" / "commercial_inputs"

WTP_TYPES = {"existing_paid_solution", "paid_course", "subscription",
             "service_spending", "paid_community", "software"}
WEAKNESS_TYPES = {"buyer_complaint", "solution_gap", "poor_review"}


def _channel_key(url: str) -> str:
    from urllib.parse import urlparse
    try:
        u = urlparse(url); host = (u.netloc or "").lower().replace("www.", "")
        parts = [p for p in (u.path or "").split("/") if p]
        if parts and any(h in host for h in ("youtube.com", "tiktok.com", "instagram.com", "x.com", "twitter.com")):
            return f"{host}/{parts[0].lower().lstrip('@')}"
        return host
    except Exception:
        return url.lower()


def _discover_creators(ctx: dict, sp, clf) -> list[dict]:
    """Self-contained creator discovery from RAW opportunity context (no product_brief
    needed — works for every opportunity). Serper finds them, Groq classifies relevance."""
    import research_engine as RE
    aud = ctx.get("audience") or ctx.get("submarket") or ctx.get("market") or ctx.get("opportunity")
    try:
        d = RE._extract_json(clf.classify(
            "Generate 6 web-search queries to find CREATORS/channels (YouTube, TikTok, Instagram, "
            "newsletter) whose audience is this buyer with this problem. STRICT JSON {\"queries\":[str,...]}.",
            json.dumps(ctx, ensure_ascii=False)))
        queries = [q for q in ((d or {}).get("queries") or []) if isinstance(q, str) and q.strip()][:6]
    except Exception:
        queries = []
    if not queries:
        queries = [f"{aud} youtube creator", f"{aud} tiktok", f"{aud} instagram creator", f"{aud} newsletter"]

    seen, results = set(), []
    for q in queries:
        try:
            hits = sp.search(q, num=10)
        except Exception:
            hits = []
        for h in hits:
            url = h.get("url") or ""
            k = _channel_key(url)
            if url and k not in seen:
                seen.add(k)
                results.append({"i": len(results), "title": h.get("title"), "url": url,
                                "snippet": (h.get("snippet") or "")[:200]})
    if not results:
        return []
    system = (
        "Classify each web result. A qualifying CREATOR is a real PERSON or creator-led brand "
        "(individual_creator/creator_brand/newsletter/podcast/education_brand) — NOT a SaaS product, "
        "company, marketplace, publication/blog, forum, community platform, aggregator, tool or agency. "
        "Return STRICT JSON {\"creators\":[{\"i\":int,\"entity_type\":str,\"keep\":bool,\"platform\":str,"
        "\"name\":str,\"handle\":str,\"relevance\":\"high|medium|low\"}]}. keep=true ONLY for creator "
        "entity types; a company/platform that merely discusses the topic is NOT a creator. name = the "
        "creator/channel, not a video title.")
    data = RE._extract_json(clf.classify(system, json.dumps(
        {"audience": ctx.get("audience"), "problem": (ctx.get("problems") or [None])[0],
         "results": [{"i": r["i"], "title": r["title"], "url": r["url"], "snippet": r["snippet"]} for r in results]},
        ensure_ascii=False)))
    rows = (data or {}).get("creators") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    import distribution as _DI
    by_i = {r["i"]: r for r in results}
    out = []
    for r in (rows or []):
        if not isinstance(r, dict) or not r.get("keep", True):
            continue
        et = (r.get("entity_type") or "").strip().lower()
        src = by_i.get(r.get("i"))
        if not src:
            continue
        if et and et not in _DI._CREATOR_TYPES:              # entity classification (primary)
            continue
        if _DI._is_non_creator_domain(src.get("url", "")):   # denylist (secondary)
            continue
        rel = r.get("relevance", "low")
        out.append({"platform": r.get("platform"), "url": src["url"], "handle": r.get("handle"),
                    "name": r.get("name") or src.get("title"),
                    "relevance": rel if rel in ("high", "medium", "low") else "low"})
    return out


def _write_density(opp_id: str, creators: list[dict]) -> int:
    cands = [{"platform": c.get("platform"), "url": c.get("url"), "handle": c.get("handle"),
              "display_name": c.get("name"),
              "audience_relevance": c.get("relevance", "low"),
              "opportunity_relevance": c.get("relevance", "low"),
              "basis": "observed", "source_refs": [c.get("url")] if c.get("url") else []}
             for c in creators if c.get("url")]
    CD_DIR.mkdir(parents=True, exist_ok=True)
    (CD_DIR / f"{opp_id}.json").write_text(json.dumps(
        {"retrieval_method": "serper+groq", "queries_run": 0, "candidates": cands}))
    return len(cands)


_DEMAND_SYSTEM = (
    "From web search results, extract EVIDENCE of paid demand and dissatisfaction for a digital-"
    "product opportunity. Respond STRICT JSON {\"wtp\":[{\"type\":\"existing_paid_solution|paid_course|"
    "subscription|service_spending|paid_community|software\",\"name\":str,\"url\":str}],"
    "\"weakness\":[{\"type\":\"buyer_complaint|solution_gap|poor_review\",\"observation\":str,"
    "\"url\":str}]}. Only items actually present in the results — real URLs, nothing fabricated. "
    "wtp = existing PAID products/solutions this audience already buys. weakness = real complaints "
    "or gaps with current solutions.")


def _write_demand(opp_id: str, ctx: dict, sp, clf) -> int:
    aud = ctx.get("audience") or ctx.get("market") or ctx.get("opportunity")
    prob = (ctx.get("problems") or [aud])[0]
    queries = [f"best {aud} template course or guide", f"{aud} gumroad OR etsy OR whop",
               f"{prob} reddit frustrated", f"{prob} is there a tool or app"]
    results = []
    for q in queries:
        try:
            for h in sp.search(q, num=8)[:8]:
                if h.get("url"):
                    results.append({"title": h.get("title"), "url": h.get("url"),
                                    "snippet": (h.get("snippet") or "")[:200]})
        except Exception:
            pass
    import research_engine as RE
    data = RE._extract_json(clf.classify(_DEMAND_SYSTEM, json.dumps({"context": ctx, "results": results},
                                                                    ensure_ascii=False)))
    if isinstance(data, list):
        data = next((x for x in data if isinstance(x, dict)), {})
    data = data or {}
    ci = []
    for w in (data.get("wtp") or []):
        if isinstance(w, dict) and w.get("type") in WTP_TYPES:
            ci.append({"type": w["type"], "name": w.get("name", ""), "url": w.get("url")})
    for w in (data.get("weakness") or []):
        if isinstance(w, dict) and w.get("type") in WEAKNESS_TYPES:
            ci.append({"type": w["type"], "observation": w.get("observation", ""), "url": w.get("url")})
    CI_DIR.mkdir(parents=True, exist_ok=True)
    (CI_DIR / f"{opp_id}.json").write_text(json.dumps({"observations": ci}))
    return len(ci)


def _ctx(opp, svc) -> dict:
    a = svc._a.get(opp["audience_id"], {}); s = svc._s.get(opp["submarket_id"], {})
    m = svc._m.get(opp["market_id"], {})
    problems = [p.get("statement") for p in svc.problems_for_opportunity(opp["id"]) if p.get("statement")][:5]
    return {"opportunity": opp["name"], "audience": a.get("name"), "submarket": s.get("name"),
            "market": m.get("name"), "problems": problems}


def rescore_one(opp_id: str, creds: dict | None = None, operator: str = "unknown") -> dict:
    """Gather real evidence for one opp, rescore it, upsert its score to storage."""
    import scoring as S
    import research_engine as RE
    import storage
    from universe import UniverseService
    svc = UniverseService()
    opp = svc._o.get(opp_id)
    if not opp:
        raise ValueError(f"no opportunity '{opp_id}'")
    sp, clf = RE.get_search_provider(creds), RE.get_classifier(creds, layer="rescore")
    if not sp or not clf:
        raise ValueError("rescore needs this operator's Serper + Groq keys")

    ctx = _ctx(opp, svc)
    # creator density from raw opportunity context (works for every opp; no product_brief needed)
    creators = _discover_creators(ctx, sp, clf)
    n_creators = _write_density(opp_id, creators)
    try:
        RE._bump_usage(f"rescore:{opp_id}", queries=0, results=len(creators),
                       sources=len(creators), operator=operator, provider="serper")
    except Exception:
        pass
    # demand / WTP / weakness
    n_signals = _write_demand(opp_id, ctx, sp, clf)

    score = S.score_one(opp, svc)
    storage.get_backend().upsert_rows("opportunity_scores", [score], key="opportunity_id")
    return {"opportunity_id": opp_id, "name": opp["name"],
            "commercial_score": score["commercial_score"], "evidence_score": score["evidence_score"],
            "priority_score": score["priority_score"], "creator_density": score["creator_density"],
            "priority_classification": score["priority_classification"],
            "creators_found": n_creators, "demand_signals": n_signals}


def rebuild_rankings() -> list[dict]:
    """Recompute rankings from all persisted scores; upsert to storage."""
    import scoring as S
    import storage
    from universe import UniverseService
    svc = UniverseService()
    scores = storage.get_backend().list_rows("opportunity_scores")
    rankings = S.build_rankings(scores, svc)
    storage.get_backend().replace_collection("opportunity_rankings", rankings)
    return rankings
