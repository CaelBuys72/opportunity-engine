"""Phase 8 — Opportunity Research Engine.

Turns a selected Profit Pocket into an evidence-backed Product Brief through
modular stages:

    make_request -> make_plan -> gather (sources+evidence) -> synthesize
    -> choose_format -> build_brief -> write dossier

Design:
  * Every stage is a pure function of its inputs, so `gather()` (the only stage
    that would ever touch the network) can later be replaced with live
    Reddit/API retrieval without changing the rest.
  * Content is REAL: it is driven by the pocket's own discovery evidence (always
    present) merged with any deeper session-researched findings registered in
    research_inputs.FINDINGS for that pocket. Nothing is invented.
  * observed / inferred / unknown is preserved on every claim. A source that
    could not be retrieved this run is recorded accessible=False (requirement
    preserved), never back-filled with a guess.
  * If deep findings are absent the dossier is still produced from discovery
    evidence and the pocket is marked `needs_review` (thin), not `complete`.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"

# adapt these angle templates to each pocket at plan time
QUERY_ANGLES = {
    "problem": ['how do I {t}', "I don't know {t}", 'struggling with {t}', "can't figure out {t}"],
    "frustration": ['{t} frustrating', 'hate {t}', 'overwhelmed {t}', 'wish there was {t}'],
    "solution_seeking": ['{t} template', '{t} calculator', '{t} spreadsheet', 'best way to {t}'],
    "complaint": ['{t} too complicated', '{t} too expensive', '{t} doesn\'t work', '{t} confusing'],
}

FORMAT_SIGNALS = {
    "calculator / spreadsheet": ["price", "pricing", "charge", "calculate", "profit", "margin",
                                  "tax", "cost", "estimate", "track", "budget", "income", "expense", "break-even"],
    "fill-in templates / scripts": ["welcome book", "house manual", "menu", "email", "message",
                                    "script", "what to include", "what to write", "resume", "contract", "invoice"],
    "planner / schedule": ["schedule", "routine", "planner", "nap", "wake window", "weekly", "calendar", "stick to"],
    "guide / checklist": ["how do i", "don't know", "overwhelmed", "steps", "first", "checklist",
                          "troubleshoot", "mistakes", "regression", "confusing", "scared"],
}

SUPPORTING_ASSET = {
    "calculator / spreadsheet": "auto-calculating spreadsheet with worked example",
    "fill-in templates / scripts": "editable templates + copy-paste scripts",
    "planner / schedule": "printable + editable planner",
    "guide / checklist": "short decision-tree guide + one-page checklist",
}


# ---------------------------------------------------------------- stages
def make_request(pocket: dict) -> dict:
    return {
        "research_request_id": f"rr-{pocket['id']}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pocket_id": pocket["id"], "title": pocket["title"],
        "industry_id": pocket["industry_id"], "audience": pocket["audience"],
        "core_problem": pocket["core_problem"],
        "desired_outcome": pocket.get("desired_outcome", ""),
        "primary_question": "Do real people experience this problem, what does it look like, "
                            "what outcome do they want, what have they tried, what remains unsolved?",
        "note": "Feeds the Phase-8 research engine.",
    }


def _terms(pocket: dict) -> list[str]:
    # short noun phrases to slot into query templates
    seeds = [pocket["audience"]] + pocket.get("related_problems", [])[:4]
    return [s.lower().strip() for s in seeds if s]


def generate_queries(pocket: dict) -> list[dict]:
    out = []
    terms = _terms(pocket)
    for angle, tmpls in QUERY_ANGLES.items():
        for tmpl in tmpls[:2]:               # 2 per angle keeps it focused
            t = terms[min(len(out) % max(len(terms), 1), len(terms) - 1)] if terms else "this"
            out.append({"angle": angle, "query": tmpl.format(t=t) + " site:reddit.com"})
    return out


def make_plan(pocket: dict, findings: dict | None) -> dict:
    known = [f"Audience: {pocket['audience']}",
             f"Core problem: {pocket['core_problem']}",
             f"Discovery score {pocket['score']['overall']}/100 ({pocket['score']['confidence']} confidence)"]
    known += [f"Evidence on file: {e}" for e in pocket.get("related_problems", [])[:3]]
    unknown = ["True prevalence / how many are affected (UNKNOWN)",
               "Creator ecosystem size (UNKNOWN)"]
    if not findings:
        unknown.append("Primary-community depth not yet retrieved this run")
    return {
        "pocket_id": pocket["id"],
        "known": known,
        "unknown": unknown,
        "validating_evidence": [
            "Multiple independent communities describing the same problem in their own words",
            "People actively asking for tools/templates (solution-seeking language)",
            "Existing paid solutions with real sales AND recurring complaints (gap)",
        ],
        "weakening_evidence": [
            "Problem is rare, mild, or one-off",
            "Free resources already solve it well (free-information problem)",
            "Strong free-sharing culture that resists paying",
            "Existing products already excellent with no complaint pattern",
        ],
        "communities": pocket.get("community_ids", []) or ["(none catalogued yet — investigate niche subs/forums)"],
        "queries": generate_queries(pocket),
        "solutions_to_examine": pocket.get("existing_solutions", []),
        "questions": [
            "Is the problem recurring and painful enough to pay to solve?",
            "What exactly have people already tried, and why did it fall short?",
            "Is a digital product the right form, or is this a service/free-info problem?",
            "What is the single most useful asset we could ship?",
            "What price will the audience tolerate, and on what evidence?",
        ],
    }


def gather(pocket: dict, evidence_records: list[dict], findings: dict | None) -> tuple[list[dict], list[dict]]:
    """Produce sources.json + evidence.json (claim-traced).

    Uses the pocket's own discovery evidence (real) and, if present, deeper
    findings. This is the swap-point for future live retrieval.
    """
    sources, claims = [], []
    seen_src = {}

    def src_for(url, stype, tier, label, accessible=True, note=""):
        key = url or label
        if key in seen_src:
            return seen_src[key]
        sid = f"src-{len(sources)+1}"
        sources.append({"id": sid, "label": label, "url": url, "tier": tier,
                         "source_type": stype, "accessible": accessible, "note": note})
        seen_src[key] = sid
        return sid

    tier_of = {"reddit": 1, "quora": 1, "forum": 1, "youtube": 1, "instagram": 1, "tiktok": 1,
               "article": 2, "review": 3, "marketplace": 3, "other": 2}

    # 1) discovery evidence attached to the pocket
    for e in evidence_records:
        tier = tier_of.get(e.get("source_type", "other"), 2)
        sid = src_for(e.get("source_url"), e.get("source_type", "other"), tier,
                      (e.get("source_url") or e.get("source_type", "source")),
                      accessible=bool(e.get("source_url")),
                      note=e.get("note", ""))
        claims.append({
            "id": f"cl-{len(claims)+1}", "claim": e.get("note") or e["quote_or_observation"][:80],
            "source_id": sid, "evidence": e["quote_or_observation"],
            "source_type": e.get("source_type", "other"),
            "relevance": "high", "strength": "strong" if e["basis"] == "observed" else "moderate",
            "basis": e["basis"], "interpretation": ""})

    # 2) deeper session findings (extra claims + explicitly inaccessible reqs)
    if findings:
        for f in findings.get("extra_claims", []):
            sid = src_for(f.get("url"), f.get("source_type", "other"),
                          f.get("tier", tier_of.get(f.get("source_type", "other"), 2)),
                          f.get("source_label", f.get("url") or "source"),
                          accessible=f.get("accessible", bool(f.get("url"))),
                          note=f.get("note", ""))
            claims.append({
                "id": f"cl-{len(claims)+1}", "claim": f["claim"], "source_id": sid,
                "evidence": f["evidence"], "source_type": f.get("source_type", "other"),
                "relevance": f.get("relevance", "high"), "strength": f.get("strength", "moderate"),
                "basis": f["basis"], "interpretation": f.get("interpretation", "")})
        for req in findings.get("inaccessible", []):
            src_for(req.get("url"), req.get("source_type", "other"),
                    req.get("tier", 1), req["label"], accessible=False,
                    note=req.get("note", "requirement preserved; retrieve later"))
    return sources, claims


def choose_format(pocket: dict) -> dict:
    text = " ".join([pocket.get("core_problem", ""), pocket.get("desired_outcome", ""),
                     " ".join(pocket.get("related_problems", [])),
                     " ".join(pocket.get("solution_gaps", []))]).lower()
    scored = {fmt: sum(text.count(k) for k in kws) for fmt, kws in FORMAT_SIGNALS.items()}
    ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
    primary = ranked[0][0] if ranked[0][1] else "guide / checklist"
    strong = [f for f, s in ranked if s >= max(1, ranked[0][1] * 0.5) and s > 0]
    assets = [SUPPORTING_ASSET[f] for f in strong] or [SUPPORTING_ASSET[primary]]
    is_bundle = len(strong) >= 2
    return {"primary": primary, "is_bundle": is_bundle, "components": strong or [primary],
            "assets": assets, "signal_scores": scored}


def synthesize(pocket: dict, claims: list[dict], findings: dict | None) -> dict:
    obs = [c for c in claims if c["basis"] == "observed"]
    a = {
        "audience": pocket["audience"],
        "recurring_symptoms": pocket.get("related_problems", []),
        "root_problems": [pocket["core_problem"]],
        "desired_outcomes": [pocket.get("desired_outcome", "")],
        "existing_behaviours": (findings or {}).get("existing_behaviours",
            ["Using free templates / generic tools", "Asking peers in communities"]),
        "existing_solutions": pocket.get("existing_solutions", []),
        "solution_strengths": (findings or {}).get("solution_strengths",
            ["Cheap/most already exist", "Instant download"]),
        "solution_weaknesses": (findings or {}).get("solution_weaknesses",
            pocket.get("solution_gaps", [])),
        "customer_complaints": (findings or {}).get("customer_complaints", []),
        "unmet_needs": (findings or {}).get("unmet_needs", pocket.get("solution_gaps", [])),
        "solution_gaps": pocket.get("solution_gaps", []),
        "contradictions": (findings or {}).get("contradictions",
            ["Falsification pass limited to discovery evidence this run — verify free-info/free-sharing risk in primary communities."]),
        "opportunity_assessment": (findings or {}).get("opportunity_assessment",
            f"{len(obs)} observed + {len(claims)-len(obs)} inferred/other claims support a recurring problem "
            f"for {pocket['audience']}. Gap: {'; '.join(pocket.get('solution_gaps', [])[:2]) or 'unknown'}."),
    }
    return a


def build_brief(pocket: dict, analysis: dict, fmt: dict, findings: dict | None) -> dict:
    f = findings or {}
    fmt_label = ("Bundle: " + " + ".join(fmt["components"])) if fmt["is_bundle"] else fmt["primary"]
    price = f.get("price_range", "Unknown — infer from analogous products before pricing")
    return {
        "pocket_id": pocket["id"],
        "product_concept": f.get("product_concept",
            f"A focused {fmt['primary']} that helps {pocket['audience']} {pocket.get('desired_outcome','').rstrip('.').lower()}."),
        "target_customer": pocket["audience"],
        "core_problem": pocket["core_problem"],
        "related_problems": pocket.get("related_problems", []),
        "desired_outcome": pocket.get("desired_outcome", ""),
        "core_transformation": f.get("core_transformation",
            f"From: {pocket['core_problem']}  →  To: {pocket.get('desired_outcome','')}"),
        "product_promise": f.get("product_promise",
            f"Get to '{pocket.get('desired_outcome','')}' without the usual guesswork."),
        "product_format": fmt_label,
        "why_this_format": f.get("why_this_format",
            f"Chosen from problem language, not by default. Signal scores: {fmt['signal_scores']}."),
        "product_structure": f.get("product_structure", fmt["assets"]),
        "required_sections": f.get("required_sections", []),
        "required_tools": f.get("required_tools", []),
        "required_templates": f.get("required_templates", []),
        "required_worksheets": f.get("required_worksheets", []),
        "bonus_assets": f.get("bonus_assets", []),
        "exclude": f.get("exclude", ["Padding/filler theory", "Anything freely available and already good enough"]),
        "existing_alternatives": pocket.get("existing_solutions", []),
        "differentiation": f.get("differentiation", pocket.get("solution_gaps", [])),
        "price_range": price,
        "price_rationale": f.get("price_rationale", "Unknown pricing evidence; do not set a price until validated."),
        "key_customer_language": f.get("key_customer_language", pocket.get("related_problems", [])),
        "key_objections": f.get("key_objections",
            ["I can find this free", "Templates never fit my exact case", "I'll deal with it later"]),
        "key_buying_motivations": f.get("key_buying_motivations",
            ["Save time", "Reduce anxiety/uncertainty", "Look professional / avoid costly mistakes"]),
        "evidence_summary": analysis["opportunity_assessment"],
        "confidence": f.get("confidence", pocket["score"]["confidence"]),
        "risks_unknowns": f.get("risks_unknowns",
            ["Prevalence UNKNOWN", "Creator ecosystem UNKNOWN", "Willingness-to-pay needs primary-community confirmation"]),
    }


# ---------------------------------------------------------------- orchestrator
def _write(pid: str, name: str, obj) -> str:
    import storage
    storage.get_backend().write_dossier_file(pid, name, obj)
    return f"research/{pid}/{name}.json"


def _dossier_file(pid: str, name: str):
    import storage
    return storage.get_backend().read_dossier_file(pid, name)


_FMT_ASSET = {
    "spreadsheet": "auto-calculating spreadsheet with worked example",
    "tracker": "structured tracker with fields + summary view",
    "calculator": "input-driven calculator with a worked example",
    "template": "editable fill-in templates",
    "scripts": "copy-paste scripts",
    "database": "structured database / library (e.g. Notion)",
    "guide": "short decision-tree guide",
    "checklist": "one-page checklist",
    "workbook": "guided workbook with exercises",
    "workflow": "step-by-step workflow / SOP",
    "bundle": "bundle of the above",
    "not_a_good_fit": "(research suggests a digital product may not be the right form)",
}


def _merge_execution(pocket, plan, sources, claims, analysis, fmt, brief, exe):
    """Fold executed-research output into the existing dossier objects in place.
    Product decisions now flow from the evidence-based product_implications synthesis.
    Enriches; never discards the discovery baseline. Returns the format dict."""
    p = exe["parsed"]
    pi = exe.get("product_implications", {}) or {}
    pool = exe.get("analysis_pool", [])
    # 1) evidence sources actually consumed (source-traceable, retrieval status kept)
    idx_to_sid = {}
    for i, c in enumerate(pool):
        sid = f"rsrc-{i+1}"; idx_to_sid[i] = sid
        sources.append({"id": sid, "label": c.get("title") or c["url"], "url": c["url"],
                        "tier": 1 if c.get("source_type") == "question" else 2,
                        "source_type": c.get("source_type"), "intent": c.get("intent"),
                        "accessible": c.get("retrieval_status") == "ok",
                        "retrieval_status": c.get("retrieval_status"),
                        "content_length": c.get("content_length"), "query": c.get("query"),
                        "note": "executed research"})
    for cl in p.get("claims", []):
        ref = cl.get("source_ref")
        sid = idx_to_sid.get(ref) if isinstance(ref, int) else None
        claims.append({"id": f"cl-{len(claims)+1}", "claim": cl.get("claim", "")[:140],
                       "source_id": sid, "evidence": cl.get("evidence", ""),
                       "source_type": (pool[ref].get("source_type") if isinstance(ref, int) and ref < len(pool) else "web"),
                       "relevance": "high", "strength": cl.get("strength", "moderate"),
                       "basis": cl.get("basis", "inferred"),
                       "interpretation": cl.get("evidence_type", ""),
                       "product_implication": cl.get("product_implication", "")})
    # 2) analysis enrichment (all evidence-derived, source-traceable)
    if pi.get("current_behavior"): analysis["existing_behaviours"] = pi["current_behavior"]
    if pi.get("current_solutions"): analysis["existing_solutions"] = pi["current_solutions"]
    if pi.get("failure_modes"): analysis["solution_weaknesses"] = pi["failure_modes"]
    if pi.get("free_alternatives"): analysis["free_alternatives"] = pi["free_alternatives"]
    if pi.get("contradictions"): analysis["contradictions"] = pi["contradictions"]
    if pi.get("desired_outcome"):
        analysis["desired_outcomes"] = [pi["desired_outcome"]]
        if not brief.get("desired_outcome"):
            brief["desired_outcome"] = pi["desired_outcome"]
            brief["core_transformation"] = f"From: {pocket['core_problem']}  →  To: {pi['desired_outcome']}"
    analysis["answered_questions"] = exe["answered_questions"]
    analysis["product_implications"] = pi
    acc = exe.get("accounting", {})
    analysis["opportunity_assessment"] = (
        f"Outcome: {exe.get('research_outcome')}. "
        f"{acc.get('search_results_discovered',0)} results discovered → "
        f"{acc.get('unique_candidate_sources',0)} candidates → {acc.get('sources_retrieved',0)} retrieved → "
        f"{acc.get('evidence_bearing_sources',0)} evidence-bearing. "
        f"Mechanism: {pi.get('product_mechanism','(unresolved)')}")
    # 3) evidence-driven format + components
    pf = pi.get("product_format") or {}
    rec = pf.get("recommended") or fmt.get("primary")
    comps = pf.get("components") or [rec]
    fmt = {"primary": rec, "is_bundle": len(comps) >= 2, "components": comps,
           "assets": comps, "signal_scores": {"basis": pf.get("basis", "inferred"),
                                               "rationale": pf.get("rationale", "")}}
    must = pi.get("must_have_components", [])
    # 4) brief rebuilt from the synthesis
    outcome = exe.get("research_outcome")
    brief["product_format"] = ("Bundle: " + " + ".join(str(c) for c in comps)) if fmt["is_bundle"] else str(rec)
    brief["why_this_format"] = (f"Mechanism → format: {pi.get('product_mechanism','')}. "
                                f"{pf.get('rationale','')} (basis: {pf.get('basis','inferred')})")
    brief["product_structure"] = [f"{m.get('component')} — {m.get('buyer_job','')} "
                                  f"[{m.get('basis','inferred')}]" for m in must] or comps
    brief["required_components_evidence"] = must     # component → job → evidence → basis
    brief["differentiation"] = pi.get("product_opportunity") and [pi["product_opportunity"]] or pi.get("failure_modes", [])
    brief["exclude"] = pi.get("do_not_build", brief.get("exclude", []))
    pr = pi.get("pricing") or {}
    if pr.get("basis") == "observed" and pr.get("values"):
        brief["price_range"] = ", ".join(str(v) for v in pr["values"])
        brief["price_rationale"] = "Observed pricing from executed research."
    else:
        brief["price_range"] = "Unknown — no observed pricing evidence"
        brief["price_rationale"] = "Pricing UNKNOWN; do not set a price until validated."
    if outcome == "WEAK_NO_PRODUCT":
        brief["product_concept"] = ("RESEARCH VERDICT — WEAK / NO CLEAR PRODUCT: "
            + (pi.get("product_opportunity") or "free/good-enough alternatives or weak pain.")
            + "  " + brief.get("product_concept", ""))
    brief["risks_unknowns"] = (["CRITICAL unresolved: " + q for q in exe["critical_unresolved"]]
                               + pi.get("remaining_uncertainty", [])[:5]
                               + pi.get("contradictions", [])[:3])
    brief["evidence_summary"] = analysis["opportunity_assessment"]
    return fmt


def run(pocket: dict, evidence_records: list[dict], findings: dict | None = None,
        creds: dict | None = None, operator: str = "unknown") -> dict:
    """Execute the full pipeline for one pocket. Returns a manifest of files.

    If the operator's search+classify providers are configured, the research PLAN is
    actually EXECUTED (search -> retrieve -> extract -> answer questions) and the
    dossier + Product Brief are built FROM that executed research. Otherwise the
    behaviour is unchanged (thin dossier from discovery evidence)."""
    request = make_request(pocket)
    plan = make_plan(pocket, findings)
    sources, claims = gather(pocket, evidence_records, findings)
    analysis = synthesize(pocket, claims, findings)
    fmt = choose_format(pocket)
    brief = build_brief(pocket, analysis, fmt, findings)

    # ---- execute the plan using the authenticated operator's credentials ----
    exe = None
    try:
        import research_engine as RE
        exe = RE.execute_research(pocket, plan, creds=creds, operator=operator)
    except Exception as e:                       # research runs regardless; record the failure
        plan["execution_error"] = f"{type(e).__name__}: {e}"

    # transient live-research failure with a prior dossier present → preserve it,
    # do not clobber good executed research with a thin fallback.
    prior_brief = _dossier_file(pocket["id"], "product_brief")
    prior_q = _dossier_file(pocket["id"], "questions")
    if exe is None and plan.get("execution_error") and prior_brief and prior_q:
        try:
            crit = (prior_q or {}).get("critical_unresolved", [])
            prev = _dossier_file(pocket["id"], "sources") or {}
            status = "complete" if not crit else "needs_review"
            return {"pocket_id": pocket["id"], "research_status": status, "preserved": True,
                    "counts": {"sources": len(prev.get("sources", [])), "claims": 0,
                               "critical_unresolved": len(crit), "executed": True},
                    "critical_unresolved": crit, "files": {}, "brief": prior_brief,
                    "plan": plan, "note": "live research hit a transient error; prior dossier preserved."}
        except Exception:
            pass  # if preservation read fails, fall through to normal (thin) write
    research_outcome = None
    if exe:
        fmt = _merge_execution(pocket, plan, sources, claims, analysis, fmt, brief, exe)
        plan["executed"] = exe["queries_executed"]
        plan["retrieval"] = exe["retrieval"]
        plan["accounting"] = exe.get("accounting", {})
        plan["dynamic_questions"] = exe.get("dynamic_questions", [])
        status = exe["status"]
        crit_unresolved = exe["critical_unresolved"]
        research_outcome = exe.get("research_outcome")
    else:
        status = "complete" if findings else "needs_review"
        crit_unresolved = [] if findings else [q for q in plan["questions"]]

    files = {
        "research_request": _write(pocket["id"], "research_request", request),
        "research_plan": _write(pocket["id"], "research_plan", plan),
        "sources": _write(pocket["id"], "sources", {"sources": sources}),
        "evidence": _write(pocket["id"], "evidence", {"claims": claims}),
        "analysis": _write(pocket["id"], "analysis", analysis),
        "product_brief": _write(pocket["id"], "product_brief", brief),
        "questions": _write(pocket["id"], "questions",
                            {"questions": analysis.get("answered_questions", []),
                             "critical_unresolved": crit_unresolved,
                             "research_outcome": research_outcome,
                             "accounting": plan.get("accounting", {}),
                             "product_implications": analysis.get("product_implications", {})}),
    }
    return {"pocket_id": pocket["id"], "research_status": status,
            "research_outcome": research_outcome,
            "counts": {"sources": len(sources), "claims": len(claims),
                       "critical_unresolved": len(crit_unresolved),
                       "executed": bool(exe), **(plan.get("accounting", {}))},
            "critical_unresolved": crit_unresolved,
            "files": files, "brief": brief, "plan": plan,
            "sources_list": sources, "claims_list": claims, "analysis": analysis}
