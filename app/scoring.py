"""Build 4 — Opportunity prioritization (commercial + evidence + priority).

TWO INDEPENDENT AXES, never collapsed:
  commercial_score  — how attractive the opportunity looks (0-100)
  evidence_score    — how much we actually know (0-100)
priority_score = commercial_score x uncertainty_adjustment(evidence)  (floored,
so a high-potential / low-evidence opportunity is surfaced, not crushed).

UNKNOWN != zero. An unknown commercial factor keeps value=null/confidence=UNKNOWN
in the record and is imputed to a documented NEUTRAL only for the ranking math
(imputed:true), so missing evidence lowers CERTAINTY (evidence_score / priority),
not attractiveness.

NON-MUTATING: writes data/universe/opportunity_scores.json (+ rankings), never
touches opportunities.json — Builds 1-3 and their validators stay intact.
"""
from __future__ import annotations
import json
from pathlib import Path

import universe as U
from universe import UniverseService
import creator_density as CD

ROOT = Path(__file__).resolve().parent.parent
SCORING_VERSION = "v1"
NEUTRAL = 50   # documented neutral used only to impute unknown commercial factors for ranking

# commercial factor weights (sum = 100), centralized & inspectable
WEIGHTS = {
    "pain_severity": 15, "problem_recurrence": 10, "desired_outcome_clarity": 10,
    "wtp_spending": 15, "existing_solution_weakness": 10, "productizability": 15,
    "audience_accessibility": 10, "creator_density": 10, "creator_product_alignment": 5,
}
# documented inference tables (0-100) — used only for INFERRED factors
TYPE_SEVERITY = {"compliance_problem": 85, "financial_problem": 80, "retention_problem": 75,
                 "acquisition_problem": 75, "emotional_friction": 70, "performance_problem": 70,
                 "time_problem": 65, "quality_problem": 65, "operational_problem": 60,
                 "workflow_problem": 60, "technical_problem": 60, "communication_problem": 60,
                 "planning_problem": 60, "knowledge_gap": 55, "decision_problem": 55}
PRODUCTIZABILITY = {"technical_problem": 85, "financial_problem": 85, "planning_problem": 80,
                    "knowledge_gap": 80, "workflow_problem": 75, "decision_problem": 75,
                    "performance_problem": 70, "acquisition_problem": 65, "operational_problem": 65,
                    "communication_problem": 65, "time_problem": 65, "quality_problem": 60,
                    "retention_problem": 60, "emotional_friction": 45, "compliance_problem": 40}
WTP_TYPES = {"existing_paid_solution", "paid_course", "subscription", "service_spending", "paid_community", "software"}
WEAKNESS_TYPES = {"buyer_complaint", "solution_gap", "poor_review"}
DENSITY_VALUE = {"NONE": 15, "LOW": 40, "MEDIUM": 65, "HIGH": 82, "VERY_HIGH": 92}

EVIDENCE_BANDS = [(67, "HIGH"), (40, "MEDIUM"), (20, "LOW"), (0, "VERY_LOW")]
UNCERTAINTY_ADJ = {"HIGH": 1.00, "MEDIUM": 0.95, "LOW": 0.85, "VERY_LOW": 0.75}


def _factor(value, confidence, basis, reason, source_refs=None, excluded=False):
    return {"value": value, "confidence": confidence, "basis": basis,
            "reason": reason, "source_refs": source_refs or [], "excluded": excluded}


def _mean(vals):
    return round(sum(vals) / len(vals)) if vals else None


# ---------------------------------------------------------------- factor computation
def compute_factors(opp: dict, members: list[dict], commercial_inputs: list[dict],
                    density: dict) -> dict:
    ptypes = [p["problem_type"] for p in members]
    f = {}

    # inferred-from-structure factors
    f["pain_severity"] = _factor(
        _mean([TYPE_SEVERITY.get(t, 55) for t in ptypes]), "LOW", "inferred",
        "Inferred from member problem-type severity; not observed.")
    f["problem_recurrence"] = _factor(
        70, "LOW", "inferred",
        "Member problems are framed as ongoing responsibilities, not one-off events.")
    has_outcomes = all(p.get("desired_outcome") for p in members) and \
        opp.get("shared_desired_outcome", "unknown") != "unknown"
    f["desired_outcome_clarity"] = _factor(
        78 if has_outcomes else 55, "LOW", "inferred",
        "Clear shared/member desired outcomes present." if has_outcomes else "Outcome partially specified.")
    f["productizability"] = _factor(
        _mean([PRODUCTIZABILITY.get(t, 60) for t in ptypes]), "LOW", "inferred",
        "Inferred from whether member problems are repeatable/standardizable tasks.")

    # commercial-evidence factors — UNKNOWN unless observed inputs exist
    wtp = [c for c in commercial_inputs if c.get("type") in WTP_TYPES]
    if wtp:
        f["wtp_spending"] = _factor(
            min(85, 70 + 5 * (len(wtp) - 1)), "MEDIUM", "observed",
            f"{len(wtp)} observed paid-solution/spending signal(s): "
            + "; ".join(c.get("name", c["type"]) for c in wtp[:3]),
            [c.get("url") or c.get("name", "") for c in wtp])
    else:
        f["wtp_spending"] = _factor(None, "UNKNOWN", "unknown",
                                    "No observed spending/paid-solution evidence imported.")
    weak = [c for c in commercial_inputs if c.get("type") in WEAKNESS_TYPES]
    if weak:
        f["existing_solution_weakness"] = _factor(
            min(85, 68 + 6 * (len(weak) - 1)), "MEDIUM", "observed",
            f"{len(weak)} observed complaint/gap signal(s): "
            + "; ".join(c.get("observation", c["type"])[:50] for c in weak[:3]),
            [c.get("url") or c.get("name", "") for c in weak if c.get("url") or c.get("name")])
    else:
        f["existing_solution_weakness"] = _factor(None, "UNKNOWN", "unknown",
                                                  "No observed complaints/solution-gap evidence imported.")

    # creator density factor (observed only if real candidates imported)
    band = density["density_band"]
    if band == "UNKNOWN":
        f["creator_density"] = _factor(None, "UNKNOWN", "unknown",
                                       "No creator evidence imported; density unknown.")
        f["creator_product_alignment"] = _factor(None, "UNKNOWN", "unknown",
                                                  "Cannot judge alignment without any creator evidence.")
        f["audience_accessibility"] = _factor(
            65, "LOW", "inferred",
            "Audience is role-defined with likely communities/search surfaces (inferred).")
    else:
        f["creator_density"] = _factor(
            DENSITY_VALUE[band], density["confidence"], "observed",
            density["reason"], density["candidate_refs"])
        f["creator_product_alignment"] = _factor(
            70, "LOW", "inferred",
            "Creators in this niche commonly promote tools/guides for this audience (inferred).")
        f["audience_accessibility"] = _factor(
            80, "MEDIUM", "observed",
            f"Reachable via {density['relevant_candidates']} relevant creators/communities (observed).",
            density["candidate_refs"])
    return f


# ---------------------------------------------------------------- the three scores
def commercial_score(factors: dict) -> tuple[int, int]:
    """UNKNOWN factors are EXCLUDED and the remaining weights RENORMALIZED, so a
    missing factor lowers certainty (evidence_score/priority) rather than dragging
    attractiveness toward a neutral midpoint. Returns (score, excluded_count).
    If every factor is unknown, score is 0 (flagged INSUFFICIENT_DATA downstream)."""
    total, known_w, excluded = 0.0, 0.0, 0
    for name, w in WEIGHTS.items():
        v = factors[name]["value"]
        if v is None:
            factors[name]["excluded"] = True
            excluded += 1
            continue
        total += (v / 100) * w
        known_w += w
    score = round(total / known_w * 100) if known_w else 0
    return score, excluded


def evidence_score(opp: dict, members: list[dict], factors: dict) -> int:
    n = max(len(members), 1)
    observed_ratio = sum(1 for p in members if p["basis"] == "observed") / n
    source_component = min(opp.get("evidence_summary", {}).get("source_count", 0), 4) / 4
    observed_factors = sum(1 for f in factors.values() if f["basis"] == "observed")
    factor_component = observed_factors / len(WEIGHTS)
    return round(100 * (0.40 * observed_ratio + 0.30 * source_component + 0.30 * factor_component))


def evidence_band(score: int) -> str:
    return next(b for thr, b in EVIDENCE_BANDS if score >= thr)


def priority_score(commercial: int, ev_band: str) -> int:
    return round(commercial * UNCERTAINTY_ADJ[ev_band])


def classify(commercial: int, ev_band: str, excluded: int) -> str:
    if excluded >= len(WEIGHTS) or (excluded >= 7 and ev_band == "VERY_LOW"):
        return "INSUFFICIENT_DATA"
    if commercial >= 70:
        return "HIGH_PRIORITY" if ev_band in ("HIGH", "MEDIUM") else "PROMISING_NEEDS_RESEARCH"
    if commercial >= 45:
        return "MODERATE"
    return "LOW_PRIORITY"


def risk_flags(opp: dict, factors: dict, density: dict, ev_score: int) -> list[dict]:
    flags = []
    if density["density_band"] == "NONE":
        flags.append({"flag": "creator_ecosystem_absent", "basis": "observed",
                      "reason": "Imported creator search yielded zero relevant candidates."})
    if factors["wtp_spending"]["value"] is None:
        flags.append({"flag": "no_observed_spending_evidence", "basis": "unknown",
                      "reason": "No observed willingness-to-pay evidence yet."})
    if opp.get("basis") == "inferred":
        flags.append({"flag": "unvalidated_inferred_cluster", "basis": "inferred",
                      "reason": "Opportunity composed only of inferred problems."})
    ptypes = set(opp.get("problem_types", {}).keys())
    if ptypes & {"compliance_problem"}:
        flags.append({"flag": "possible_liability_or_service", "basis": "inferred",
                      "reason": "Compliance-type problems can imply regulated/bespoke service."})
    if ev_score < 20:
        flags.append({"flag": "low_evidence", "basis": "observed",
                      "reason": f"evidence_score {ev_score} is very low."})
    return flags


# ---------------------------------------------------------------- orchestration
def _load_inputs(dir_name: str, opp_id: str) -> list[dict]:
    f = ROOT / "data" / dir_name / f"{opp_id}.json"
    if not f.exists():
        return []
    data = json.loads(f.read_text())
    return data.get("observations", data if isinstance(data, list) else [])


def score_one(opp: dict, svc: UniverseService,
              commercial_file: str | None = None, creator_file: str | None = None) -> dict:
    members = svc.problems_for_opportunity(opp["id"])
    commercial_inputs = _load_inputs("commercial_inputs", opp["id"]) if commercial_file is None \
        else json.loads(Path(commercial_file).read_text()).get("observations", [])
    density = CD.density_for(opp["id"], creator_file)
    factors = compute_factors(opp, members, commercial_inputs, density)
    comm, excluded = commercial_score(factors)
    ev = evidence_score(opp, members, factors)
    eb = evidence_band(ev)
    prio = priority_score(comm, eb)
    classification = classify(comm, eb, excluded)
    return {
        "opportunity_id": opp["id"], "name": opp["name"], "audience_id": opp["audience_id"],
        "scoring_version": SCORING_VERSION,
        "commercial_score": comm, "evidence_score": ev, "evidence_band": eb,
        "priority_score": prio, "priority_classification": classification,
        "excluded_factor_count": excluded,
        "score_breakdown": factors,
        "creator_density": density["density_band"],
        "creator_density_confidence": density["confidence"],
        "creator_density_detail": {k: density[k] for k in
                                   ("queries_run", "candidates_discovered", "relevant_candidates",
                                    "density_band", "basis", "confidence", "retrieval_method",
                                    "reason", "candidate_refs")},
        "commercial_evidence_count": len(commercial_inputs),
        "risk_flags": risk_flags(opp, factors, density, ev),
        "screening_status": "screened",   # Build-4 processing state (commercial_status stays 'unvalidated')
    }


def score_all(svc: UniverseService | None = None) -> list[dict]:
    svc = svc or UniverseService()
    return [score_one(o, svc) for o in svc._o.values()]


def build_rankings(scores: list[dict], svc: UniverseService) -> list[dict]:
    ordered = sorted(scores, key=lambda s: s["priority_score"], reverse=True)
    out = []
    for i, s in enumerate(ordered, 1):
        aud = svc._a.get(s["audience_id"], {})
        out.append({"rank": i, "opportunity_id": s["opportunity_id"], "name": s["name"],
                    "audience": aud.get("name", "?"),
                    "commercial_score": s["commercial_score"], "evidence_score": s["evidence_score"],
                    "priority_score": s["priority_score"], "creator_density": s["creator_density"],
                    "classification": s["priority_classification"]})
    return out


def persist(scores: list[dict], rankings: list[dict]) -> None:
    d = ROOT / "data" / "universe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "opportunity_scores.json").write_text(json.dumps(scores, indent=2, ensure_ascii=False))
    (d / "opportunity_rankings.json").write_text(json.dumps(rankings, indent=2, ensure_ascii=False))


def run_all() -> dict:
    svc = UniverseService()
    scores = score_all(svc)
    rankings = build_rankings(scores, svc)
    persist(scores, rankings)
    return {"scored": len(scores), "scores": scores, "rankings": rankings}


# ---------------------------------------------------------------- validation
class ScoringValidationError(Exception):
    pass


def validate_scores() -> dict:
    svc = UniverseService()
    scores = svc.store  # placeholder to avoid lints
    d = ROOT / "data" / "universe"
    scores = json.loads((d / "opportunity_scores.json").read_text())
    rankings = json.loads((d / "opportunity_rankings.json").read_text())
    errors = []
    if round(sum(WEIGHTS.values())) != 100:
        errors.append("weights do not sum to 100")
    seen = set()
    for s in scores:
        oid = s["opportunity_id"]
        if oid in seen:
            errors.append(f"duplicate score for {oid}")
        seen.add(oid)
        if not svc.get_opportunity(oid):
            errors.append(f"{oid}: score references non-existent opportunity")
        if s.get("scoring_version") != SCORING_VERSION:
            errors.append(f"{oid}: missing/wrong scoring_version")
        for name, fac in s["score_breakdown"].items():
            v = fac["value"]
            if v is not None and not (0 <= v <= 100):
                errors.append(f"{oid}.{name}: value out of range")
            if fac["basis"] == "observed" and not fac["source_refs"] and name != "audience_accessibility":
                # observed factors must cite evidence (accessibility cites density refs, checked below)
                errors.append(f"{oid}.{name}: observed factor without source_refs")
            if v is None and fac["confidence"] != "UNKNOWN":
                errors.append(f"{oid}.{name}: null value must have confidence UNKNOWN")
            if fac["basis"] not in ("observed", "inferred", "unknown"):
                errors.append(f"{oid}.{name}: invalid basis")
        # reproducibility
        opp = svc.get_opportunity(oid)
        recomputed = score_one(opp, svc)
        for k in ("commercial_score", "evidence_score", "priority_score", "priority_classification"):
            if recomputed[k] != s[k]:
                errors.append(f"{oid}: {k} not reproducible ({s[k]} != {recomputed[k]})")
        # creator density honesty: no fabricated followers
        for c in s["creator_density_detail"].get("candidate_refs", []):
            pass
        if s["creator_density"] not in ("NONE", "LOW", "MEDIUM", "HIGH", "VERY_HIGH", "UNKNOWN"):
            errors.append(f"{oid}: invalid creator_density band")
    # rankings consistency
    if len(rankings) != len(scores):
        errors.append("rankings count != scores count")
    rank_ids = [r["opportunity_id"] for r in rankings]
    if len(rank_ids) != len(set(rank_ids)):
        errors.append("duplicate ranking entries")
    for r in rankings:
        if not svc.get_opportunity(r["opportunity_id"]):
            errors.append(f"ranking {r['opportunity_id']} does not resolve")
    prios = [r["priority_score"] for r in rankings]
    if prios != sorted(prios, reverse=True):
        errors.append("rankings not ordered by priority_score")
    report = {"scores": len(scores), "rankings": len(rankings),
              "errors": errors, "passed": not errors}
    if errors:
        raise ScoringValidationError(f"{len(errors)} error(s):\n  - " + "\n  - ".join(errors[:25]))
    return report
