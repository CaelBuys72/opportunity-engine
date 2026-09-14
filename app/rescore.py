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


def _relevance(fit) -> str:
    fit = fit or 0
    return "high" if fit >= 60 else "medium" if fit >= 40 else "low"


def _write_density(opp_id: str, creators: list[dict]) -> int:
    cands = [{"platform": c.get("platform"), "url": c.get("url"), "handle": c.get("handle"),
              "display_name": c.get("name"),
              "audience_relevance": _relevance(c.get("fit_score")),
              "opportunity_relevance": _relevance(c.get("fit_score")),
              "basis": "observed", "source_refs": [c.get("url")] if c.get("url") else []}
             for c in creators if c.get("url")]
    CD_DIR.mkdir(parents=True, exist_ok=True)
    (CD_DIR / f"{opp_id}.json").write_text(json.dumps(
        {"retrieval_method": "serper+groq(discover)", "queries_run": 0, "candidates": cands}))
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
    import distribution as DI
    import storage
    from universe import UniverseService
    svc = UniverseService()
    opp = svc._o.get(opp_id)
    if not opp:
        raise ValueError(f"no opportunity '{opp_id}'")
    sp, clf = RE.get_search_provider(creds), RE.get_classifier(creds)
    if not sp or not clf:
        raise ValueError("rescore needs this operator's Serper + Groq keys")

    # density from the real discovery layer (strong recall; skip page fetches)
    disc = DI.discover_creators(opp_id, creds=creds, operator=operator, fetch_contacts=False)
    n_creators = _write_density(opp_id, disc.get("creators", []))
    # demand / WTP / weakness
    n_signals = _write_demand(opp_id, _ctx(opp, svc), sp, clf)

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
