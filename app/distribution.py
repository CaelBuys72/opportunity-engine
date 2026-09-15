"""Phase 9.5 — Creator / Distribution Fit Engine.

Answers ONE question before we build: "Are there creators whose existing
audience already contains the buyers for THIS product, tightly enough that a
partnership is plausible?"

Deterministic, local-first. Retrieval is isolated in gather_creator_candidates()
(the single swap-point for future live/API retrieval). Manual candidates are
read from data/creator_candidates/<opportunity-id>.json.

HARD honesty rules:
  * Never fabricate creators, followers, views, engagement, comments, URLs.
    Unknown stays null / "unknown"; inaccessible sources are recorded, not
    reconstructed.
  * Every creator FACT must carry a source_ref; every score carries a basis
    (observed / inferred / unknown).
  * A dimension that cannot be evaluated is UNKNOWN and lowers confidence — it
    never gets a made-up value, and unknown weight is excluded from the overall.
  * With no candidate data the honest verdict is NEEDS_RESEARCH.
  * Falsification is mandatory: the engine actively records why distribution
    might NOT work, and which of those checks are simply UNKNOWN here.

Live creator discovery (Serper + Groq) and personalised outreach DRAFTS are also
provided (discover_creators / draft_outreach) — drafts only, sent manually.
Does NOT auto-send outreach, build product content, or integrate Whop.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"
IMPORT_DIR = ROOT / "data" / "creator_candidates"

# 8 scoring dimensions (weights sum to 100)
WEIGHTS = {
    "audience_alignment": 20, "problem_alignment": 20, "content_alignment": 15,
    "relevant_view_evidence": 15, "creator_density": 15,
    "approachability": 5, "monetization_signal": 5, "product_content_fit": 5,
}

STOPWORDS = {"the", "and", "for", "with", "your", "you", "how", "what", "that", "this",
             "from", "are", "was", "their", "them", "a", "to", "of", "in", "on", "my"}


class DistributionError(Exception):
    """Raised when inputs are missing/invalid — refuse rather than fabricate."""


def _tok(s: str) -> set[str]:
    s = s or ""
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split()
            if len(w) > 2 and w not in STOPWORDS}


# ------------------------------------------------------------------ 1. load
def load_opportunity(opp_id: str) -> dict:
    import storage
    backend = storage.get_backend()
    brief = backend.read_dossier_file(opp_id, "product_brief")
    if brief is None:
        raise DistributionError(f"No product_brief.json for '{opp_id}'. Run Phases 8+9 first.")
    for req in ("target_customer", "core_problem", "desired_outcome"):
        if not brief.get(req):
            raise DistributionError(f"Brief missing '{req}'; cannot derive a creator profile honestly.")

    def opt(name):
        return backend.read_dossier_file(opp_id, name)
    return {"opp_id": opp_id, "brief": brief, "spec": opt("product_spec"),
            "architecture": opt("product_architecture"), "component_specs": opt("component_specs"),
            "analysis": opt("analysis"), "research_plan": opt("research_plan"),
            "sources": opt("sources")}


# ------------------------------------------------------------------ 2. search profile
def define_creator_search_profile(bundle: dict) -> dict:
    b = bundle["brief"]
    rel = []
    for f in ("key_customer_language", "related_problems"):
        rel += b.get(f, [])
    terms = sorted({w for phrase in [b["target_customer"], b["core_problem"], b["desired_outcome"]] + rel
                    for w in _tok(phrase)})
    # audience-noun heuristics for query building
    audience = b["target_customer"]
    return {
        "opportunity_id": bundle["opp_id"],
        "target_audience": audience,
        "audience_identity": audience,
        "audience_problem": b["core_problem"],
        "desired_outcome": b["desired_outcome"],
        "relevant_terminology": rel[:8],
        "adjacent_terminology": _adjacent_terms(audience),
        "content_topics": (b.get("related_problems", []) + [b["desired_outcome"]])[:8],
        "content_formats": ["short-form video", "long-form video", "carousel/post", "newsletter"],
        "creator_archetypes": _archetypes(audience),
        "creator_categories": _categories(audience),
        "likely_platforms": ["YouTube", "Instagram", "TikTok", "Newsletter/Substack", "X"],
        "exclusion_terms": b.get("exclude", []),
        "search_queries": _queries(audience, rel),
        "_token_bag": terms,
    }


def _adjacent_terms(audience: str) -> list[str]:
    a = audience.lower()
    out = []
    if "freelanc" in a or "1099" in a or "contractor" in a or "self-employed" in a or "self employed" in a:
        out = ["freelance money", "solopreneur finance", "self employed money",
               "freelance business", "creator finance", "gig worker money"]
    return out or ["(derive adjacent terms from audience — none inferred)"]


def _archetypes(audience: str) -> list[str]:
    a = audience.lower()
    if "freelanc" in a or "1099" in a or "self" in a or "contractor" in a:
        return ["freelance educator / coach", "self-employed finance explainer",
                "accountant/CPA creator", "solopreneur / creator-economy educator"]
    return ["niche educator", "practitioner-creator", "community host"]


def _categories(audience: str) -> list[str]:
    return ["personal finance", "freelancing/solopreneurship", "creator economy", "small business"]


def _queries(audience: str, rel: list[str]) -> list[dict]:
    a = audience.lower()
    base = []
    if "freelanc" in a or "1099" in a or "self" in a or "contractor" in a:
        base = ["freelancer taxes youtube creator", "1099 taxes explained creator",
                "self employed taxes tiktok", "freelance finance youtuber",
                "quarterly taxes freelancer instagram", "freelance money creator newsletter"]
    else:
        base = [f"{audience} youtube creator", f"{audience} tiktok"]
    return [{"platform": "multi", "query": q} for q in base]


# ------------------------------------------------------------------ 3. content signals
def define_content_signals(profile: dict) -> dict:
    return {
        "exact_match_terms": profile["relevant_terminology"],
        "adjacent_terms": profile["adjacent_terminology"],
        "weak_terms": profile["content_topics"],
        "exclusion_terms": profile["exclusion_terms"],
        "note": "Classify each creator content item as exact / adjacent / weak / irrelevant.",
    }


# ------------------------------------------------------------------ 4. audience signals
def define_audience_signals(profile: dict) -> dict:
    return {"demand_signals_to_look_for": [
        "comments asking how to solve the problem",
        "requests for a template / calculator / spreadsheet / guide",
        "requests for examples",
        "complaints about existing methods (e.g. 'my spreadsheet breaks')",
        "people describing the pain in their own words",
        "asking where to find a solution / recommendations",
    ], "note": "Generic engagement is NOT demand — require problem-specific signals."}


# ------------------------------------------------------------------ 5. qualification rubric
def define_creator_qualification(profile: dict) -> dict:
    return {"dimensions": WEIGHTS,
            "definitions": {
                "audience_alignment": "Does the creator actually reach the target buyer?",
                "problem_alignment": "Does their audience experience THIS problem?",
                "content_alignment": "Do they repeatedly make content on the problem/outcome/adjacent?",
                "relevant_view_evidence": "Do relevant pieces get meaningful, repeated distribution?",
                "creator_density": "Do multiple creators independently reach this audience/problem?",
                "approachability": "Could a small operator realistically partner with them?",
                "monetization_signal": "Do they already monetize (positive, not required)?",
                "product_content_fit": "Would the product feel like a natural extension of their content?",
            },
            "target_follower_band": "10k-100k (heuristic, not a rule; strong alignment beats size)"}


# ------------------------------------------------------------------ 6. RETRIEVAL (swap point)
def gather_creator_candidates(opp_id: str, profile: dict) -> tuple[list[dict], list[dict]]:
    """The ONLY retrieval stage. V1 = manual/import from
    data/creator_candidates/<opp_id>.json. Returns (candidates, retrieval_notes).
    A future live retriever (search API, browser, platform API, CSV) replaces
    this function body only. No network here → nothing is fabricated."""
    f = IMPORT_DIR / f"{opp_id}.json"
    if not f.exists():
        return [], [{"retriever": "manual-import", "status": "no_data",
                     "note": f"No candidate file at data/creator_candidates/{opp_id}.json and no "
                             "live retriever configured. Import real creators to evaluate."}]
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        return [], [{"retriever": "manual-import", "status": "invalid_json", "note": str(e)}]
    cands = data.get("candidates", data if isinstance(data, list) else [])
    notes = [{"retriever": "manual-import", "status": "loaded", "count": len(cands),
              "source": f"data/creator_candidates/{opp_id}.json"}]
    # normalise minimal shape without inventing anything
    norm = []
    for i, c in enumerate(cands, 1):
        norm.append({
            "id": c.get("id") or f"creator-{i}",
            "name": c.get("name", "unknown"), "platform": c.get("platform", "unknown"),
            "profile_url": c.get("profile_url"), "handle": c.get("handle"),
            "followers": c.get("followers"),
            "followers_basis": "observed" if isinstance(c.get("followers"), int) else "unknown",
            "niche": c.get("niche"), "audience_description": c.get("audience_description"),
            "relevant_content": c.get("relevant_content", []),
            "relevant_view_signals": c.get("relevant_view_signals", []),
            "audience_problem_signals": c.get("audience_problem_signals", []),
            "monetization_signals": c.get("monetization_signals", []),
            "source_refs": c.get("source_refs", []),
            "basis": c.get("basis", "observed"),
        })
    return norm, notes


# ------------------------------------------------------------------ 7-8. evaluate candidates + content
def _classify_content(item: dict, signals: dict) -> str:
    text = _tok((item.get("title", "") + " " + item.get("topic", "")))
    if not text:
        return "unknown"
    if text & _tok(" ".join(signals["exact_match_terms"])):
        return "exact"
    if text & _tok(" ".join(signals["adjacent_terms"])):
        return "adjacent"
    if text & _tok(" ".join(signals["weak_terms"])):
        return "weak"
    return "irrelevant"


def _sub(score, basis, refs, rationale):
    return {"score": score, "basis": basis, "evidence_refs": refs, "rationale": rationale}


def evaluate_creator_candidates(candidates: list[dict], profile: dict, signals: dict) -> list[dict]:
    evals = []
    prof_terms = _tok(" ".join(profile["relevant_terminology"] + [profile["target_audience"]]
                               + profile["adjacent_terminology"]))
    for c in candidates:
        refs = c.get("source_refs", [])
        # content classification
        classified = []
        for item in c.get("relevant_content", []):
            classified.append({**{k: item.get(k) for k in ("url", "title", "topic", "views", "engagement")},
                               "relevance": _classify_content(item, signals),
                               "source_ref": item.get("source_ref")})
        n_exact = sum(1 for x in classified if x["relevance"] == "exact")
        n_adj = sum(1 for x in classified if x["relevance"] == "adjacent")

        # audience_fit
        atext = _tok((c.get("niche") or "") + " " + (c.get("audience_description") or ""))
        if atext:
            overlap = len(atext & prof_terms)
            audience_fit = _sub(min(10, 4 + overlap * 2), "observed" if c["basis"] == "observed" else "inferred",
                                refs, f"{overlap} audience-term overlaps with profile.")
        else:
            audience_fit = _sub(None, "unknown", [], "No niche/audience text provided.")
        # problem_fit
        aps = c.get("audience_problem_signals", [])
        problem_fit = (_sub(min(10, 5 + len(aps) * 2), "observed", refs,
                            f"{len(aps)} problem-specific audience signal(s).")
                       if aps else _sub(None, "unknown", [], "No audience-problem signals captured."))
        # content_fit
        if classified:
            content_fit = _sub(min(10, n_exact * 4 + n_adj * 2), "observed", refs,
                               f"{n_exact} exact + {n_adj} adjacent content items.")
        else:
            content_fit = _sub(None, "unknown", [], "No content items captured.")
        # view_fit — only if numeric views or explicit view signals exist
        views = [x["views"] for x in classified if isinstance(x.get("views"), int)]
        if views:
            relevant_views = [x["views"] for x in classified if isinstance(x.get("views"), int)
                              and x["relevance"] in ("exact", "adjacent")]
            strong = sum(1 for v in relevant_views if v >= 20000)
            view_fit = _sub(min(10, 3 + strong * 3 + (1 if len(relevant_views) >= 2 else 0)),
                            "observed", refs, f"{len(relevant_views)} relevant items w/ views; {strong} >=20k.")
        elif c.get("relevant_view_signals"):
            view_fit = _sub(None, "unknown", refs, "View signals described but not numeric — cannot score.")
        else:
            view_fit = _sub(None, "unknown", [], "No view data.")
        # approachability
        f = c.get("followers")
        if isinstance(f, int):
            band = 9 if 10000 <= f <= 100000 else 7 if f < 10000 else 6 if f <= 500000 else 4
            approach = _sub(band, "observed", refs, f"{f} followers (band heuristic).")
        elif c.get("monetization_signals"):
            approach = _sub(None, "unknown", refs, "Follower count unknown; monetization present.")
        else:
            approach = _sub(None, "unknown", [], "Follower count unknown.")
        # monetization
        mon = c.get("monetization_signals", [])
        monet = (_sub(min(10, 5 + len(mon) * 2), "observed", refs, f"{len(mon)} monetization signal(s).")
                 if mon else _sub(None, "unknown", [], "No monetization signal captured."))
        # product_content_fit (inferred from content+problem where known)
        known = [x["score"] for x in (content_fit, problem_fit) if x["score"] is not None]
        pfit = (_sub(round(sum(known) / len(known)), "inferred", refs,
                     "Derived from content + problem fit.") if known
                else _sub(None, "unknown", [], "Insufficient content/problem data."))

        q = {"audience_fit": audience_fit, "problem_fit": problem_fit, "content_fit": content_fit,
             "view_fit": view_fit, "approachability": approach, "monetization_fit": monet,
             "product_fit": pfit}
        qualified = all(q[k]["score"] is not None and q[k]["score"] >= 6
                        for k in ("audience_fit", "problem_fit", "content_fit"))
        highly = qualified and view_fit["score"] is not None and view_fit["score"] >= 6
        evals.append({"creator_id": c["id"], "name": c["name"], "platform": c["platform"],
                      "classified_content": classified, "qualification": q,
                      "qualified": qualified, "highly_qualified": highly})
    return evals


def evaluate_content_relevance(evals: list[dict]) -> dict:
    counts = {"exact": 0, "adjacent": 0, "weak": 0, "irrelevant": 0, "unknown": 0}
    for e in evals:
        for x in e["classified_content"]:
            counts[x["relevance"]] = counts.get(x["relevance"], 0) + 1
    return {"counts": counts, "total_content_items": sum(counts.values()),
            "basis": "observed" if sum(counts.values()) else "unknown"}


def evaluate_audience_alignment(evals: list[dict]) -> dict:
    def mean(key):
        vals = [e["qualification"][key]["score"] for e in evals
                if e["qualification"][key]["score"] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None
    return {"audience_fit_mean": mean("audience_fit"), "problem_fit_mean": mean("problem_fit"),
            "basis": "observed" if any(e["qualification"]["audience_fit"]["score"] is not None
                                       for e in evals) else "unknown"}


# ------------------------------------------------------------------ 10. density
def evaluate_distribution_density(evals: list[dict], content_rel: dict) -> dict:
    n = len(evals)
    nq = sum(1 for e in evals if e["qualified"])
    nhq = sum(1 for e in evals if e["highly_qualified"])
    known_f = [e for e in evals]  # placeholder; follower dist computed in verdict from candidates
    density_score = 0 if nq == 0 else 4 if nq <= 2 else 7 if nq <= 5 else 9
    return {"creator_count": n, "qualified_creator_count": nq, "highly_qualified_count": nhq,
            "relevant_content_count": content_rel["counts"]["exact"] + content_rel["counts"]["adjacent"],
            "density_score": density_score,
            "basis": "inferred",
            "rationale": "Counts are observed for the imported set, but representativeness of the "
                         "true creator ecosystem is inferred (import is not a census)."}


# ------------------------------------------------------------------ 11. falsification (mandatory)
def identify_distribution_risks(bundle: dict, evals: list[dict], density: dict) -> dict:
    b = bundle["brief"]
    contradictory, unknown_checks, risks = [], [], []
    analysis = bundle.get("analysis") or {}

    # carry Phase-8 contradictions (evidence-backed context)
    for c in analysis.get("contradictions", []):
        contradictory.append({"claim": c, "basis": "inferred", "source": "phase8.analysis.contradictions"})
    for r in b.get("risks_unknowns", []):
        risks.append({"risk": r, "basis": "evidence-backed", "source": "brief.risks_unknowns"})

    checks = {
        "low_relevant_engagement": "creators discuss topic but relevant content underperforms",
        "audience_prefers_free": "audience rejects paid products / prefers free info",
        "creators_sell_competing": "creators already sell competing products",
        "audience_mismatch": "creator audience differs from the actual buyer",
        "views_without_relevance": "high views but low problem relevance",
        "fragmented_audience": "audience too fragmented across many micro-niches",
        "wont_promote_third_party": "creators unlikely to promote a third-party product",
        "demand_without_creators": "strong problem demand but weak creator ecosystem",
    }
    # evaluate what the available data can actually judge
    has_views = any(e["qualification"]["view_fit"]["score"] is not None for e in evals)
    if evals and not has_views:
        unknown_checks.append({"check": "low_relevant_engagement", "why": "no view data imported"})
        unknown_checks.append({"check": "views_without_relevance", "why": "no view data imported"})
    if not evals:
        for k in checks:
            unknown_checks.append({"check": k, "why": "no creator candidates to evaluate"})
    else:
        if density["qualified_creator_count"] == 0:
            contradictory.append({"claim": "No imported creator qualified on audience+problem+content.",
                                  "basis": "observed", "source": "phase9.5.evaluations"})
        if density["qualified_creator_count"] < 3 and b.get("confidence") in ("HIGH", "MEDIUM"):
            risks.append({"risk": "demand_without_creators: brief shows demand but few qualified creators found so far.",
                          "basis": "inferred", "source": "cross-check"})
        # checks we can't judge from import alone:
        for k in ("audience_prefers_free", "creators_sell_competing", "wont_promote_third_party", "fragmented_audience"):
            unknown_checks.append({"check": k, "why": "requires primary community/creator inspection not available this run"})

    return {"checklist": checks, "contradictory_evidence": contradictory,
            "unknown_checks": unknown_checks, "risks": risks}


# ------------------------------------------------------------------ scoring
def _score_dimensions(audience_al, density, content_rel, evals) -> dict:
    def agg(key):
        vals = [e["qualification"][key]["score"] for e in evals
                if e["qualification"][key]["score"] is not None]
        return (round(sum(vals) / len(vals), 1), "observed") if vals else (None, "unknown")

    aud, aud_b = agg("audience_fit")
    prob, prob_b = agg("problem_fit")
    cont, cont_b = agg("content_fit")
    view, view_b = agg("view_fit")
    appr, appr_b = agg("approachability")
    mon, mon_b = agg("monetization_fit")
    pfit, pfit_b = agg("product_fit")
    dens = density["density_score"] if evals else None
    dims = {
        "audience_alignment": (aud, aud_b), "problem_alignment": (prob, prob_b),
        "content_alignment": (cont, cont_b), "relevant_view_evidence": (view, view_b),
        "creator_density": (dens, "inferred" if evals else "unknown"),
        "approachability": (appr, appr_b), "monetization_signal": (mon, mon_b),
        "product_content_fit": (pfit, pfit_b),
    }
    out = {}
    for name, (score, basis) in dims.items():
        out[name] = {"score": score, "weight": WEIGHTS[name],
                     "basis": basis if score is not None else "unknown"}
    known_w = sum(d["weight"] for d in out.values() if d["score"] is not None)
    overall = round(sum((d["score"] / 10) * d["weight"] for d in out.values() if d["score"] is not None)
                    / known_w * 100, 1) if known_w else 0.0
    unknown_pct = 100 - known_w
    n_obs = sum(1 for d in out.values() if d["basis"] == "observed")
    conf = "HIGH" if (unknown_pct <= 20 and n_obs >= 5) else "LOW" if unknown_pct >= 50 else "MEDIUM"
    return {"dimensions": out, "overall": overall, "weight_unknown_pct": unknown_pct, "confidence": conf}


# ------------------------------------------------------------------ 12. verdict
def build_distribution_verdict(candidates, evals, score, density, falsification, bundle) -> dict:
    n = len(candidates)
    nq = density["qualified_creator_count"]
    nhq = density["highly_qualified_count"]
    strongest = sorted([e for e in evals if e["qualified"]],
                       key=lambda e: (e["highly_qualified"], e["qualification"]["content_fit"]["score"] or 0),
                       reverse=True)[:5]
    strongest_names = [f"{e['name']} ({e['platform']})" for e in strongest]
    content_sig = []
    for e in strongest:
        for x in e["classified_content"]:
            if x["relevance"] in ("exact", "adjacent"):
                content_sig.append(f"{e['name']}: {x.get('title') or x.get('topic')} "
                                   f"[{x['relevance']}{', ' + str(x['views']) + ' views' if isinstance(x.get('views'), int) else ''}]")
    unknowns = [f"{u['check']} ({u['why']})" for u in falsification["unknown_checks"]]
    if score["weight_unknown_pct"]:
        unknowns.append(f"{score['weight_unknown_pct']}% of scoring weight is UNKNOWN.")

    # gating logic — unknowns dominate the decision, never optimism
    if n == 0:
        verdict, reason, action = ("NEEDS_RESEARCH",
            "No creator candidates available (no live retriever, no manual import). Nothing can be validated.",
            "Import real creators to data/creator_candidates/<id>.json (or wire live retrieval), then re-run.")
    elif score["weight_unknown_pct"] >= 50 or nq == 0:
        verdict, reason, action = ("NEEDS_RESEARCH",
            f"{nq} qualified of {n} imported; {score['weight_unknown_pct']}% of weight is unknown "
            "(views/audience-problem data largely missing). Not enough to conclude.",
            "Capture per-creator relevant-content views + audience-problem signals (comments), then re-run.")
    elif score["overall"] >= 70 and nhq >= 3:
        verdict, reason, action = ("STRONG_FIT",
            f"{nhq} highly-qualified creators with relevant, repeatedly-viewed content.",
            "Proceed toward Phase 10; shortlist top creators for outreach validation.")
    elif score["overall"] >= 45:
        verdict, reason, action = ("MODERATE_FIT",
            f"{nq} qualified creators; alignment present but evidence partial.",
            "Validate with 5 creator conversations / capture view+comment evidence before building.")
    else:
        verdict, reason, action = ("WEAK_FIT",
            "Alignment or density too low on available evidence.",
            "Reconsider distribution path or pocket before investing in the build.")

    supporting = []
    if density["relevant_content_count"]:
        supporting.append(f"{density['relevant_content_count']} relevant (exact/adjacent) content items across imports.")
    if nq:
        supporting.append(f"{nq} creator(s) qualified on audience+problem+content.")
    return {
        "opportunity_id": bundle["opp_id"], "verdict": verdict,
        "confidence": score["confidence"], "reason": reason,
        "creator_count": n, "qualified_creator_count": nq, "highly_qualified_count": nhq,
        "strongest_creators": strongest_names,
        "strongest_content_signals": content_sig[:6],
        "supporting_evidence": supporting,
        "contradictory_evidence": [c["claim"] for c in falsification["contradictory_evidence"]],
        "unknowns": unknowns,
        "major_risks": [r["risk"] for r in falsification["risks"]],
        "next_action": action,
    }


# ------------------------------------------------------------------ 13. dossier
def build_creator_validation_dossier(bundle, profile, verdict, score, density,
                                     content_rel, audience_al, falsification, retrieval_notes) -> dict:
    b = bundle["brief"]
    return {
        "opportunity_id": bundle["opp_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product_concept": b.get("product_concept", ""),
        "target_audience": profile["target_audience"],
        "verdict": verdict,
        "score": score,
        "distribution_density": density,
        "content_relevance": content_rel,
        "audience_alignment": audience_al,
        "falsification": falsification,
        "retrieval": retrieval_notes,
        "carried_forward": {
            "exclusions": b.get("exclude", []),
            "risks_unknowns": b.get("risks_unknowns", []),
            "phase8_contradictions": (bundle.get("analysis") or {}).get("contradictions", []),
        },
        "handoff": {
            "for": "Phase 10+ Creator Outreach (NOT built here)",
            "consumes": "creator_validation_dossier.json + creator_evaluations.json + distribution_verdict.json",
            "gate": "Do not begin outreach unless verdict is MODERATE_FIT or STRONG_FIT; "
                    "NEEDS_RESEARCH/WEAK_FIT must be resolved first.",
            "must_respect": ["verdict.next_action", "carried_forward.exclusions",
                             "falsification.unknown_checks (resolve before outreach)"],
        },
    }


# ------------------------------------------------------------------ orchestrator
def _write(opp_id: str, name: str, obj) -> str:
    import storage
    storage.get_backend().write_dossier_file(opp_id, name, obj)
    return f"research/{opp_id}/{name}.json"


def run(opp_id: str) -> dict:
    bundle = load_opportunity(opp_id)
    profile = define_creator_search_profile(bundle)
    content_signals = define_content_signals(profile)
    audience_signals = define_audience_signals(profile)
    qualification = define_creator_qualification(profile)
    candidates, retrieval_notes = gather_creator_candidates(opp_id, profile)
    evals = evaluate_creator_candidates(candidates, profile, content_signals)
    content_rel = evaluate_content_relevance(evals)
    audience_al = evaluate_audience_alignment(evals)
    density = evaluate_distribution_density(evals, content_rel)
    falsification = identify_distribution_risks(bundle, evals, density)
    score = _score_dimensions(audience_al, density, content_rel, evals)
    verdict = build_distribution_verdict(candidates, evals, score, density, falsification, bundle)
    dossier = build_creator_validation_dossier(bundle, profile, verdict, score, density,
                                               content_rel, audience_al, falsification, retrieval_notes)

    profile_out = {k: v for k, v in profile.items() if not k.startswith("_")}
    profile_out.update({"content_signals": content_signals, "audience_signals": audience_signals,
                        "qualification_rubric": qualification})
    files = {
        "creator_search_profile": _write(opp_id, "creator_search_profile", profile_out),
        "creator_candidates": _write(opp_id, "creator_candidates",
                                     {"candidates": candidates, "retrieval": retrieval_notes}),
        "creator_evaluations": _write(opp_id, "creator_evaluations", {"evaluations": evals}),
        "distribution_evidence": _write(opp_id, "distribution_evidence",
                                        {"content_relevance": content_rel, "audience_alignment": audience_al,
                                         "distribution_density": density}),
        "distribution_falsification": _write(opp_id, "distribution_falsification", falsification),
        "distribution_analysis": _write(opp_id, "distribution_analysis", score),
        "distribution_verdict": _write(opp_id, "distribution_verdict", verdict),
        "creator_validation_dossier": _write(opp_id, "creator_validation_dossier", dossier),
    }
    return {"opportunity_id": opp_id, "verdict": verdict["verdict"], "confidence": verdict["confidence"],
            "counts": {"candidates": len(candidates), "qualified": density["qualified_creator_count"],
                       "highly_qualified": density["highly_qualified_count"]},
            "files": files, "dossier": dossier}


# ==================================================================
# LIVE CREATOR DISCOVERY (Serper finds them, Groq scores fit, contacts
# extracted from public pages only — nothing fabricated). Produces a
# ranked shortlist ready for outreach. Uses the operator's own keys.
# ==================================================================
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _channel_key(url: str) -> str:
    """Dedupe creators by channel, not by individual video/post URL."""
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
        host = (u.netloc or "").lower().replace("www.", "")
        parts = [p for p in (u.path or "").split("/") if p]
        if "youtube.com" in host and parts:
            return f"{host}/{parts[0].lower()}"            # /@handle or /channel/ID or /c/name
        if any(h in host for h in ("tiktok.com", "instagram.com", "x.com", "twitter.com")) and parts:
            return f"{host}/{parts[0].lower().lstrip('@')}"
        return host                                        # blogs/newsletters: one per domain
    except Exception:
        return url.lower()


def _channel_root(url: str) -> str:
    """Truncate a post/video URL to the creator's channel/profile root (still the real
    URL, just shortened) so outreach links point at the creator, not one post."""
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
        host = (u.netloc or "").lower()
        parts = [p for p in (u.path or "").split("/") if p]
        base = f"{u.scheme or 'https'}://{u.netloc}"
        if "youtube.com" in host and parts:
            if parts[0] in ("channel", "c", "user") and len(parts) > 1:
                return f"{base}/{parts[0]}/{parts[1]}"
            if parts[0].startswith("@"):
                return f"{base}/{parts[0]}"
        if any(h in host for h in ("tiktok.com", "instagram.com", "x.com", "twitter.com")) and parts:
            return f"{base}/{parts[0]}"
        return url
    except Exception:
        return url


def _creator_queries(clf, brief: dict, profile: dict) -> list[str]:
    """Groq-generate creator-search queries for ANY niche; fall back to the profile's."""
    fallback = [q["query"] for q in profile.get("search_queries", []) if q.get("query")]
    fallback += [f"{profile['target_audience']} youtube creator",
                 f"{profile['target_audience']} tiktok", f"{profile['target_audience']} newsletter"]
    try:
        system = ("You build web-search queries to FIND CREATORS (YouTubers, TikTokers, "
                  "Instagram, newsletter authors) whose audience is a given buyer with a given "
                  "problem. Return STRICT JSON: {\"queries\": [str, ...]} — 8 varied queries across "
                  "platforms that would surface such creators. No prose.")
        user = json.dumps({"buyer": brief.get("target_customer"), "problem": brief.get("core_problem"),
                           "outcome": brief.get("desired_outcome")}, ensure_ascii=False)
        import research_engine as RE
        data = RE._extract_json(clf.classify(system, user))
        qs = (data or {}).get("queries") if isinstance(data, dict) else None
        qs = [q for q in (qs or []) if isinstance(q, str) and q.strip()]
        return (qs or fallback)[:8]
    except Exception:
        return fallback[:8]


# email domains that are NOT a creator's own contact (aggregators, agencies, tooling)
_EMAIL_DENY = ("feedspot.com", "example.com", "sentry.io", "wixpress.com", "domain.com",
               "yourdomain.com", "email.com", "mailchimp.com", "squarespace.com",
               "audiencly.com", "viralnation.com", "sentry-next.wixpress.com")


def _is_creator_email(e: str) -> bool:
    el = e.lower()
    if el.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return False
    return not any(d in el for d in _EMAIL_DENY)


def _niche_terms(clf, brief: dict) -> list[str]:
    """Concise SEARCH terms a person would actually type to find these creators
    (e.g. 'dungeon master', 'tabletop RPG') — NOT the verbose buyer description, which
    returns nothing. This is what makes the email-intent queries surface real bios."""
    fallback = [w for w in (brief.get("target_customer") or "").split()
                if w.lower() not in STOPWORDS][:3]
    try:
        import research_engine as RE
        system = ("Give the 3-4 SHORT search terms a normal person types to find CREATORS for "
                  "this audience/problem — the niche words, not the buyer description. E.g. buyer "
                  "'game masters trying to reduce prep time' -> [\"dungeon master\",\"tabletop rpg\","
                  "\"D&D DM\"]. STRICT JSON {\"terms\":[str,...]}. 1-3 words each, no prose.")
        user = json.dumps({"buyer": brief.get("target_customer"), "problem": brief.get("core_problem")},
                          ensure_ascii=False)
        data = RE._extract_json(clf.classify(system, user))
        terms = [t.strip() for t in ((data or {}).get("terms") or []) if isinstance(t, str) and t.strip()]
        return (terms or [" ".join(fallback)])[:4]
    except Exception:
        return [" ".join(fallback)] if fallback else []


def _platform_queries(terms: list[str]) -> list[str]:
    """Build channel-finding + EMAIL-INTENT queries from concise NICHE TERMS (validated:
    Google snippets carry the bio email for creators who publish one to get work)."""
    qs = []
    for t in terms[:3]:
        qs += [
            f"site:youtube.com {t} creator",
            f"site:instagram.com {t}",
            f"{t} youtuber business inquiries email",   # email-intent (proven to surface bios)
            f"{t} creator email gmail.com",
            f"{t} newsletter OR podcast contact email",
        ]
    return [q for q in qs if q.strip()]


# contact-route link patterns (found in the creator's own page text)
_LINK_PATTERNS = {
    "link_hub": r"https?://(?:linktr\.ee|beacons\.ai|bio\.link|linkin\.bio|link\.bio|solo\.to|tap\.bio|komi\.io)/[^\s\"'<>)]+",
    "instagram": r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+",
    "x": r"https?://(?:www\.)?(?:twitter|x)\.com/[A-Za-z0-9_]+",
    "tiktok": r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.]+",
    "contact_page": r"https?://[^\s\"'<>)]+/(?:contact|about|work-with|collab)[^\s\"'<>)]*",
}
_LINK_RE = {k: re.compile(v, re.I) for k, v in _LINK_PATTERNS.items()}


def _contact_page_url(channel_root: str) -> str:
    """For YouTube, the /about tab is where business email lives; else the root itself."""
    try:
        if "youtube.com" in channel_root and "/about" not in channel_root:
            return channel_root.rstrip("/") + "/about"
    except Exception:
        pass
    return channel_root


def _extract_contacts(text: str, channel_url: str) -> dict:
    """Pull every REAL, observed reach route from a creator's page text: emails first,
    then link-hubs / socials / contact pages. The channel URL itself is always a route
    (comment / DM). Nothing invented — only what appears in the fetched text."""
    text = text or ""
    emails = sorted({e for e in _EMAIL_RE.findall(text)
                     if not e.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))})[:3]
    links = {}
    for kind, rx in _LINK_RE.items():
        m = rx.search(text)
        if m:
            links[kind] = m.group(0)
    # reach method, best-first
    if emails:
        method, primary = "email", emails[0]
    elif links.get("link_hub"):
        method, primary = "link_hub", links["link_hub"]
    elif links.get("contact_page"):
        method, primary = "contact_page", links["contact_page"]
    elif any(k in links for k in ("instagram", "x", "tiktok")):
        method = "dm"
        primary = links.get("instagram") or links.get("x") or links.get("tiktok")
    else:
        method, primary = "platform", channel_url        # comment / on-platform DM
    return {"emails": emails, "links": links, "method": method, "primary": primary}


def _score_creators(clf, brief: dict, items: list[dict]) -> list[dict]:
    """Groq scores each search hit for creator-fit. Returns per-index scoring; we merge
    back the real URL + regex-found emails so nothing is invented."""
    import research_engine as RE
    compact = [{"i": it["i"], "title": it.get("title"), "url": it.get("url"),
                "snippet": (it.get("snippet") or "")[:300],
                "page_excerpt": (it.get("page_text") or "")[:600]} for it in items]
    system = (
        "You evaluate web-search results to identify real individual CREATORS/channels whose "
        "audience matches the buyer and who make content on the problem. For EACH item return an "
        "object; respond with STRICT JSON {\"creators\":[{\"i\":int,\"keep\":bool,"
        "\"confidence\":\"high|medium|low\",\"name\":str,\"platform\":str,\"handle\":str,"
        "\"niche\":str,\"est_followers\":int|null,\"why_fit\":str,\"fit_score\":int(0-100),"
        "\"caution\":str}]}. Rules: "
        "'name' MUST be the CREATOR/channel/author (the YouTube channel, the person, the newsletter), "
        "NOT the title of a single video or post. "
        "keep=true for ANY plausible individual creator/channel/author/podcast/newsletter — even if "
        "you must infer the creator behind a single video, and even if the fit is only moderate. Set "
        "confidence=low for those inferred/borderline ones, medium for probable, high for a clearly "
        "identified creator who squarely fits. "
        "keep=false ONLY for things that are clearly NOT one creator: marketplaces, app-store pages, "
        "listicles/round-up articles, news sites, agencies, retail brands, or generic company pages. "
        "est_followers ONLY if explicitly present, else null. Never invent numbers, handles or emails. "
        "fit_score = audience match + problem/content match + approachability.")
    user = json.dumps({"buyer": brief.get("target_customer"), "problem": brief.get("core_problem"),
                       "product": brief.get("product_concept") or brief.get("desired_outcome"),
                       "results": compact}, ensure_ascii=False)
    data = RE._extract_json(clf.classify(system, user))
    rows = (data or {}).get("creators") if isinstance(data, dict) else (data if isinstance(data, list) else None)
    by_i = {it["i"]: it for it in items}
    out = []
    for r in (rows or []):
        if not isinstance(r, dict) or not r.get("keep", True):
            continue
        src = by_i.get(r.get("i"))
        if not src:
            continue
        conf = r.get("confidence")
        out.append({
            "name": r.get("name") or src.get("title"), "platform": r.get("platform"),
            "handle": r.get("handle"),
            "url": _channel_root(src.get("url", "")),                  # creator root (real, truncated)
            "source_url": src.get("url"),                              # the exact hit from Serper
            "niche": r.get("niche"), "est_followers": r.get("est_followers"),
            "why_fit": r.get("why_fit"), "fit_score": r.get("fit_score") or 0,
            "confidence": conf if conf in ("high", "medium", "low") else "medium",
            "caution": r.get("caution"),
            # email from the search snippet (primary); about/link-hub fetch tops up if empty
            "contact_emails": list(src.get("snippet_emails") or []),
            "email_source": "snippet" if src.get("snippet_emails") else None,
            "contacts": None,
            "found_via": src.get("query"),
        })
    return out


CONTACT_FETCH_LIMIT = 15   # fetch contact pages for at most this many kept creators (latency guard)


def discover_creators(opp_id: str, creds: dict | None = None, operator: str = "unknown",
                      max_candidates: int = 45, fetch_contacts: bool = True) -> dict:
    """Live creator shortlist for outreach: Serper search -> page fetch for contacts ->
    Groq fit-scoring. Honest: only real URLs, only publicly-found emails."""
    import research_engine as RE
    sp, clf = RE.get_search_provider(creds), RE.get_classifier(creds, layer="creator")
    if not sp or not clf:
        raise DistributionError("creator discovery needs this operator's Serper and Groq keys")
    bundle = load_opportunity(opp_id)
    profile = define_creator_search_profile(bundle)
    brief = bundle["brief"]
    # concise niche terms drive both semantic + email-intent queries (the verbose buyer
    # description returns no bios; niche terms like "dungeon master" do)
    terms = _niche_terms(clf, brief)
    queries = list(dict.fromkeys(_creator_queries(clf, brief, profile) + _platform_queries(terms)))[:16]

    seen, results = set(), []
    for q in queries:
        try:
            hits = sp.search(q, num=15)
        except Exception:
            hits = []
        for h in hits:
            url = h.get("url") or ""
            if not url:
                continue
            k = _channel_key(url)
            if k in seen:
                continue
            seen.add(k)
            # bio/contact emails often sit right in the Google snippet (validated)
            snip_emails = sorted({e for e in _EMAIL_RE.findall(h.get("snippet") or "")
                                  if _is_creator_email(e)})[:3]
            results.append({**h, "query": q, "snippet_emails": snip_emails})
    try:
        RE._bump_usage(f"creators:{opp_id}", queries=len(queries), results=len(results),
                       sources=len(results), operator=operator, provider="serper")
    except Exception:
        pass

    # Score a LARGE pool on title+snippet (one LLM call, no page fetches yet) so a noisy
    # first page of results doesn't starve the shortlist. Put email-bearing results FIRST
    # so the pool cap can never truncate a creator who already exposed a contact email.
    results.sort(key=lambda r: 1 if r.get("snippet_emails") else 0, reverse=True)
    pool = results[:max_candidates]
    for i, r in enumerate(pool):
        r["i"] = i
        r["page_text"] = ""
    creators = _score_creators(clf, brief, pool) if pool else []

    # Contact: the snippet email (if any) is already attached. TOP-UP only the creators
    # that still lack an email by fetching their channel/about/link-hub page once.
    if fetch_contacts:
        need = [c for c in creators if not c.get("contact_emails")][:CONTACT_FETCH_LIMIT]
        for c in need:
            page = _contact_page_url(c.get("url") or c.get("source_url") or "")
            try:
                text, status = RE.fetch_text(page, cap=4000)
            except Exception:
                text, status = "", "error"
            contacts = _extract_contacts(text if status == "ok" else "", c.get("url") or "")
            c["contacts"] = contacts
            if contacts["emails"]:
                c["contact_emails"] = contacts["emails"]
                c["email_source"] = "page"
        for c in creators:
            if c.get("contact_emails"):
                c["reach_method"] = "email"
                if not c.get("contacts"):
                    c["contacts"] = {"emails": c["contact_emails"], "links": {},
                                     "method": "email", "primary": c["contact_emails"][0]}
            else:
                c["reach_method"] = (c.get("contacts") or {}).get("method") or "platform"

    # Rank EMAIL-FIRST (your outreach is email), then a soft 10k-100k follower band, then fit.
    def _rank_key(c):
        has_email = 1 if c.get("contact_emails") else 0
        f = c.get("est_followers")
        in_band = 1 if (isinstance(f, int) and 10000 <= f <= 100000) else 0
        return (has_email, in_band, c.get("fit_score") or 0)
    creators.sort(key=_rank_key, reverse=True)

    dossier = {
        "opportunity_id": opp_id, "generated_at": _now(),
        "audience": brief.get("target_customer"), "queries": queries,
        "candidates_found": len(results), "shortlisted": len(creators),
        "with_email": sum(1 for c in creators if c.get("contact_emails")),
        "with_any_contact": sum(1 for c in creators
                                if (c.get("reach_method") or "platform") != "platform"),
        "in_follower_band": sum(1 for c in creators
                                if isinstance(c.get("est_followers"), int)
                                and 10000 <= c["est_followers"] <= 100000),
        "by_confidence": {lvl: sum(1 for c in creators if c.get("confidence") == lvl)
                          for lvl in ("high", "medium", "low")},
        "creators": creators,
        "note": "Email-first: creators with a public email (from their bio/snippet) rank first, "
                "then a soft 10k-100k follower preference, then fit. Emails are observed-only "
                "(never invented). Some creators are only reachable on-platform; verify before outreach.",
    }
    _write(opp_id, "creator_shortlist", dossier)
    return dossier


def get_creator_shortlist(opp_id: str) -> dict | None:
    import storage
    return storage.get_backend().read_dossier_file(opp_id, "creator_shortlist")


# ==================================================================
# OUTREACH DRAFTS — Groq drafts a personalised message per shortlisted
# creator. DRAFTS ONLY: the human reviews and SENDS manually. Never
# auto-send / mass-blast from real accounts. Includes a status tracker.
# ==================================================================
_OUTREACH_STATUSES = ("draft", "sent", "replied", "skip")


def draft_outreach(opp_id: str, creds: dict | None = None, operator: str = "unknown") -> dict:
    import research_engine as RE
    clf = RE.get_classifier(creds, layer="creator")
    if not clf:
        raise DistributionError("outreach drafting needs this operator's Groq key")
    shortlist = get_creator_shortlist(opp_id)
    creators = (shortlist or {}).get("creators") or []
    if not creators:
        raise DistributionError("no creator shortlist yet — run Find Creators first")
    brief = load_opportunity(opp_id)["brief"]

    compact = [{"i": i, "name": c.get("name"), "platform": c.get("platform"),
                "niche": c.get("niche"), "why_fit": c.get("why_fit")} for i, c in enumerate(creators)]
    system = (
        "You write SHORT, genuine, non-spammy outreach from a small independent maker to a creator, "
        "proposing they share/recommend a digital product their audience would value (affiliate / "
        "light partnership). For EACH creator return STRICT JSON {\"drafts\":[{\"i\":int,"
        "\"subject\":str,\"message\":str}]}. message = 60-110 words, personalised to the creator and "
        "their audience, references what they actually make, ONE clear ask, warm and human (not "
        "salesy), no fake flattery, no placeholders like [name] or [channel] — use the real name. "
        "Plain text, no markdown.")
    user = json.dumps({"product": brief.get("product_concept"),
                       "promise": brief.get("product_promise") or brief.get("desired_outcome"),
                       "buyer": brief.get("target_customer"), "creators": compact}, ensure_ascii=False)
    data = RE._extract_json(clf.classify(system, user))
    rows = (data or {}).get("drafts") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    by_i = {d.get("i"): d for d in (rows or []) if isinstance(d, dict)}

    drafts = []
    for i, c in enumerate(creators):
        d = by_i.get(i) or {}
        contacts = c.get("contacts") or {}
        drafts.append({
            "creator": c.get("name"), "platform": c.get("platform"), "url": c.get("url"),
            "handle": c.get("handle"), "contact_emails": c.get("contact_emails", []),
            "reach_method": c.get("reach_method") or contacts.get("method"),
            "reach_via": contacts.get("primary") or c.get("url"),
            "contact_links": contacts.get("links") or {},
            "fit_score": c.get("fit_score"), "confidence": c.get("confidence"),
            "subject": d.get("subject") or f"Idea for your {c.get('platform', '')} audience",
            "message": d.get("message") or "",
            "status": "draft",
        })
    dossier = {"opportunity_id": opp_id, "generated_at": _now(),
               "product": brief.get("product_concept"), "count": len(drafts), "drafts": drafts,
               "note": "DRAFTS ONLY — review, tweak, and SEND MANUALLY from your own account. "
                       "Do not mass-automate sending (bans + platform ToS)."}
    _write(opp_id, "outreach_drafts", dossier)
    return dossier


def get_outreach(opp_id: str) -> dict | None:
    import storage
    return storage.get_backend().read_dossier_file(opp_id, "outreach_drafts")


def set_outreach_status(opp_id: str, index: int, status: str) -> dict:
    import storage
    if status not in _OUTREACH_STATUSES:
        raise DistributionError(f"status must be one of {_OUTREACH_STATUSES}")
    backend = storage.get_backend()
    d = backend.read_dossier_file(opp_id, "outreach_drafts")
    drafts = (d or {}).get("drafts") or []
    if not isinstance(index, int) or not (0 <= index < len(drafts)):
        raise DistributionError("bad draft index")
    drafts[index]["status"] = status
    backend.write_dossier_file(opp_id, "outreach_drafts", d)
    return {"index": index, "status": status}
