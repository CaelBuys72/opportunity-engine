#!/usr/bin/env python3
"""Phase-1 curation — rescore opportunities from REAL evidence.

Fills the two evidence slots the Build-4 scorer already consumes but that were
empty (which is why every opportunity was capped in the high-70s/low-80s):
  * data/creator_density_inputs/<opp>.json  — creators serving the audience
  * data/commercial_inputs/<opp>.json       — paid-solution (WTP) + complaint/gap signals
Evidence is gathered live (Serper + LLM), honest (only real URLs/items), then the
existing scorer reruns. Scores rise for genuinely-evidenced opportunities and stay
low for weak ones — that IS the curation.

    python3 scripts/rescore_from_evidence.py --limit 1     # test on the top-ranked opp
    python3 scripts/rescore_from_evidence.py --all         # all opportunities (resumable)
    python3 scripts/rescore_from_evidence.py --all --force # re-gather even if inputs exist

Uses global GROQ_API_KEY (preferred) or GEMINI_API_KEY + SERPER_API_KEY from env.
Writes local scores; run scripts/migrate_to_supabase.py afterwards to push to the
deployed app.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import scoring as S            # noqa: E402
import research_engine as RE   # noqa: E402
from universe import UniverseService  # noqa: E402

CD_DIR = ROOT / "data" / "creator_density_inputs"
CI_DIR = ROOT / "data" / "commercial_inputs"


def _ctx(opp, svc):
    a = svc._a.get(opp["audience_id"], {}); s = svc._s.get(opp["submarket_id"], {})
    m = svc._m.get(opp["market_id"], {})
    problems = [p.get("statement") for p in svc.problems_for_opportunity(opp["id"]) if p.get("statement")][:5]
    return {"opportunity": opp["name"], "audience": a.get("name"), "submarket": s.get("name"),
            "market": m.get("name"), "problems": problems,
            "desired_outcome": opp.get("shared_desired_outcome")}


def _fallback_queries(ctx):
    aud = ctx["audience"] or ctx["submarket"] or ctx["market"] or ctx["opportunity"]
    prob = ctx["problems"][0] if ctx["problems"] else aud
    return [f"{aud} youtube creator", f"{aud} tiktok creator",
            f"best {aud} template course or guide", f"{aud} gumroad OR etsy OR whop",
            f"{prob} reddit frustrated", f"{prob} is there a tool"]


def _queries(ctx, clf):
    """LLM-generated queries (much better creator/demand recall); fall back to templates."""
    try:
        system = ("Generate web-search queries to find, for a digital-product opportunity: (a) CREATORS/"
                  "channels whose audience is this buyer, and (b) existing PAID solutions + (c) complaints/"
                  "gaps. Return STRICT JSON {\"queries\":[str,...]} — 6-8 queries mixing creator-finding "
                  "(YouTube/TikTok/Instagram/newsletter) and demand/competition. No prose.")
        data = RE._extract_json(clf.classify(system, json.dumps(ctx, ensure_ascii=False)))
        qs = (data or {}).get("queries") if isinstance(data, dict) else None
        qs = [q for q in (qs or []) if isinstance(q, str) and q.strip()]
        return qs[:8] or _fallback_queries(ctx)
    except Exception:
        return _fallback_queries(ctx)


_SYSTEM = (
    "From web search results, extract EVIDENCE about a digital-product opportunity. Respond with "
    "STRICT JSON: {\"creators\":[{\"platform\":str,\"url\":str,\"handle\":str,\"display_name\":str,"
    "\"audience_relevance\":\"high|medium|low\",\"opportunity_relevance\":\"high|medium|low\"}],"
    "\"wtp\":[{\"type\":\"existing_paid_solution|paid_course|subscription|service_spending|paid_community|software\","
    "\"name\":str,\"url\":str}],\"weakness\":[{\"type\":\"buyer_complaint|solution_gap|poor_review\","
    "\"observation\":str,\"url\":str}]}. Use ONLY items actually present in the results — real URLs, "
    "nothing fabricated. creators = individual creators/channels who serve THIS audience (not brands/"
    "listicles). wtp = existing PAID products/solutions this audience already buys. weakness = real "
    "complaints or gaps with current solutions. Relevance reflects how directly it matches the audience/problem.")


def gather(opp, svc, sp, clf):
    ctx = _ctx(opp, svc)
    qs = _queries(ctx, clf)
    results = []
    for q in qs:
        try:
            hits = sp.search(q, num=8)
        except Exception:
            hits = []
        for h in hits[:8]:
            if h.get("url"):
                results.append({"title": h.get("title"), "url": h.get("url"),
                                "snippet": (h.get("snippet") or "")[:200]})
    data = RE._extract_json(clf.classify(_SYSTEM, json.dumps({"context": ctx, "results": results},
                                                             ensure_ascii=False)))
    if isinstance(data, list):
        data = next((x for x in data if isinstance(x, dict)), {})
    data = data or {}

    cands = [{"platform": c.get("platform"), "url": c.get("url"), "handle": c.get("handle"),
              "display_name": c.get("display_name"),
              "audience_relevance": c.get("audience_relevance", "low"),
              "opportunity_relevance": c.get("opportunity_relevance", "low"),
              "basis": "observed", "source_refs": [c.get("url")] if c.get("url") else []}
             for c in (data.get("creators") or []) if isinstance(c, dict) and c.get("url")]
    CD_DIR.mkdir(parents=True, exist_ok=True)
    (CD_DIR / f"{opp['id']}.json").write_text(json.dumps(
        {"retrieval_method": "serper+llm", "queries_run": len(qs), "candidates": cands}, indent=2))

    ci = []
    for w in (data.get("wtp") or []):
        if isinstance(w, dict) and w.get("type") in S.WTP_TYPES:
            ci.append({"type": w["type"], "name": w.get("name", ""), "url": w.get("url")})
    for w in (data.get("weakness") or []):
        if isinstance(w, dict) and w.get("type") in S.WEAKNESS_TYPES:
            ci.append({"type": w["type"], "observation": w.get("observation", ""), "url": w.get("url")})
    CI_DIR.mkdir(parents=True, exist_ok=True)
    (CI_DIR / f"{opp['id']}.json").write_text(json.dumps({"observations": ci}, indent=2))
    return len(cands), len([c for c in cands if c["opportunity_relevance"] in ("high", "medium")
                            or c["audience_relevance"] in ("high", "medium")]), len(ci)


def main():
    args = sys.argv[1:]
    force = "--force" in args
    limit = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if not ("--all" in args or limit):
        raise SystemExit("usage: rescore_from_evidence.py --all [--force] | --limit N")

    svc = UniverseService()
    sp, clf = RE.get_search_provider(None), RE.get_classifier(None)
    if not sp or not clf:
        raise SystemExit("need SERPER_API_KEY + (GROQ_API_KEY or GEMINI_API_KEY) in env")
    print(f"provider: search={sp.name} classifier={clf.name}")

    opps = list(svc._o.values())
    opps = sorted(opps, key=lambda o: o["id"])
    if limit:
        # score first so we process the currently top-ranked ones
        ranked = {r["opportunity_id"]: r["rank"] for r in svc.ranked_opportunities()}
        opps = sorted(opps, key=lambda o: ranked.get(o["id"], 999))[:limit]

    for i, opp in enumerate(opps, 1):
        done = (CD_DIR / f"{opp['id']}.json").exists() and (CI_DIR / f"{opp['id']}.json").exists()
        if done and not force:
            print(f"[{i}/{len(opps)}] skip (have inputs): {opp['name'][:50]}")
            continue
        try:
            nc, nrel, nci = gather(opp, svc, sp, clf)
            print(f"[{i}/{len(opps)}] {opp['name'][:46]} → {nc} creators ({nrel} relevant), {nci} commercial signals")
        except Exception as e:
            print(f"[{i}/{len(opps)}] ERROR {opp['name'][:40]}: {type(e).__name__}: {e}")

    print("\nRescoring …")
    r = S.run_all()
    print(f"Scored {r['scored']} (v{S.SCORING_VERSION}). Top:")
    for row in r["rankings"][:10]:
        print(f"  P={row['priority_score']:>3} C={row['commercial_score']:>3} "
              f"E={row['evidence_score']:>3} {row['creator_density']:<9} {row['name'][:40]}")


if __name__ == "__main__":
    main()
