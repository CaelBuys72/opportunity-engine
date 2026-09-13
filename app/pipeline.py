"""Build 5 — Universe -> deep pipeline bridge (orchestration only).

Promotes a ranked Universe opportunity and drives it through the EXISTING
engines (Phase 8 research, Phase 9 curation, Phase 9.5 distribution). No domain
logic lives here — it only adapts Universe context into each engine's contract,
enforces stage gates, and tracks pipeline state.

Anchor: the Universe `opp-*` id is the canonical downstream id — research lives
in research/<opp-id>/, curation and distribution key on the same id. No second
research id is minted.

Honesty carried through:
  * Build-4 scores are PROMOTION METADATA, never research evidence.
  * observed problem evidence -> observed Phase-8 claims (real sources);
    inferred problems -> inferred claims (no URL) — never laundered to observed.
  * A Universe-originated Phase-8 run has NO deep findings unless a real
    universe_findings entry exists, so it honestly returns needs_review and the
    gate STOPS downstream progression.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone

def NOW() -> str:
    return datetime.now(timezone.utc).isoformat()

import universe as U
from universe import UniverseStore, UniverseService
import research as R
import curation as C
import distribution as D

ROOT = Path(__file__).resolve().parent.parent
STATES_FILE = ROOT / "data" / "universe" / "pipeline_states.json"
CREATOR_SEED_DIR = ROOT / "data" / "creator_candidates"          # Phase-9.5 import dir
CREATOR_INPUT_DIR = ROOT / "data" / "creator_density_inputs"     # Build-4 inputs
COMMERCIAL_DIR = ROOT / "data" / "commercial_inputs"
RESEARCH_DIR = ROOT / "research"

ELIGIBLE = {"HIGH_PRIORITY", "PROMISING_NEEDS_RESEARCH", "MODERATE"}
_EV_TO_BRIEF_CONF = {"HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW", "VERY_LOW": "LOW"}


class PipelineError(Exception):
    pass


# ---------------------------------------------------------------- state store
def _load_states() -> dict:
    import storage
    rows = storage.get_backend().read_doc("pipeline_states") or []
    return {s["opportunity_id"]: s for s in rows}


def _save_states(states: dict) -> None:
    import storage
    storage.get_backend().write_doc("pipeline_states", list(states.values()))


# ---------------------------------------------------------------- promotion
def promote(opp_id: str, force: bool = False, promoted_by: str = "manual") -> dict:
    svc = UniverseService()
    opp = svc.get_opportunity(opp_id)
    if not opp:
        raise PipelineError(f"no opportunity '{opp_id}'")
    score = svc.score_for_opportunity(opp_id)
    if not score:
        raise PipelineError(f"'{opp_id}' has no Build-4 score — run scoring first.")
    rank = next((r["rank"] for r in svc.ranked_opportunities() if r["opportunity_id"] == opp_id), None)
    if rank is None:
        raise PipelineError(f"'{opp_id}' not in rankings.")
    cls = score["priority_classification"]
    if cls not in ELIGIBLE and not force:
        raise PipelineError(f"'{opp_id}' is {cls}; promote requires --force for this class.")

    states = _load_states()
    existing = states.get(opp_id)
    if existing and existing.get("promotion_status") == "promoted":
        # idempotent: preserve the ORIGINAL promotion snapshot; do not rewrite history
        return existing

    snapshot = {"scoring_version": score.get("scoring_version"),
                "commercial_score": score["commercial_score"],
                "evidence_score": score["evidence_score"],
                "priority_score": score["priority_score"],
                "priority_classification": cls,
                "creator_density": score["creator_density"], "source_rank": rank}
    states[opp_id] = {
        "opportunity_id": opp_id, "universe_opportunity_id": opp_id, "research_id": opp_id,
        "promotion_status": "promoted", "source_rank": rank,
        "priority_classification": cls,
        "commercial_score": score["commercial_score"], "evidence_score": score["evidence_score"],
        "priority_score": score["priority_score"],
        "promoted_by": promoted_by, "override": bool(force and cls not in ELIGIBLE),
        "promotion_score_snapshot": snapshot,
        "pipeline_stage": "research_pending",
        "research_status": "pending", "curation_status": "not_started",
        "distribution_status": "not_started", "product_build_status": "not_started",
        "commercial_status": "unvalidated", "rescore_requested": False,
    }
    _save_states(states)
    return states[opp_id]


# ---------------------------------------------------------------- adapter (Universe -> Phase-8)
def _commercial_inputs(opp_id: str) -> list[dict]:
    f = COMMERCIAL_DIR / f"{opp_id}.json"
    return json.loads(f.read_text()).get("observations", []) if f.exists() else []


def build_research_request(opp_id: str, svc: UniverseService):
    """Returns (pocket, evidence_records, universe_request) for Phase 8. Pure adapter."""
    opp = svc.get_opportunity(opp_id)
    aud = svc._a[opp["audience_id"]]
    members = svc.problems_for_opportunity(opp_id)
    score = svc.score_for_opportunity(opp_id) or {}

    evidence_records, seed_source_refs = [], []
    for p in members:
        if p["basis"] == "observed" and p.get("source_refs"):
            for sid in p["source_refs"]:
                src = svc._src.get(sid)
                if not src:
                    continue
                evidence_records.append({
                    "id": sid, "quote_or_observation": src.get("text") or p["statement"],
                    "source_type": src.get("source_type", "other"), "source_url": src.get("url"),
                    "basis": "observed", "date": src.get("date"),
                    "note": p["normalized_problem"]})
                seed_source_refs.append(sid)
        else:
            evidence_records.append({
                "id": f"infprb-{p['id']}", "quote_or_observation": p["statement"],
                "source_type": "other", "source_url": None, "basis": "inferred", "date": None,
                "note": "inferred upstream problem (Build 2) — context, not observed evidence"})
    # dedupe evidence by id
    seen, deduped = set(), []
    for e in evidence_records:
        if e["id"] not in seen:
            deduped.append(e); seen.add(e["id"])
    evidence_records = deduped

    commercial = _commercial_inputs(opp_id)
    existing_solutions = [c.get("name", c["type"]) for c in commercial if c.get("type") == "existing_paid_solution"]
    solution_gaps = [c.get("observation", "") for c in commercial if c.get("type") in ("solution_gap", "buyer_complaint")]
    source_urls = sorted({src.get("url") for sid in seed_source_refs
                          if (src := svc._src.get(sid)) and src.get("url")})
    density = (score.get("creator_density_detail") or {})
    top = [p["normalized_problem"] for p in members[:3]]
    core_problem = (f"{aud['name']} face a related cluster of problems around "
                    f"{opp['name'].lower()} — e.g. {', '.join(top)}.")

    pocket = {
        "id": opp_id, "title": opp["name"], "industry_id": opp["market_id"],
        "audience": aud["name"], "core_problem": core_problem,
        "desired_outcome": opp.get("shared_desired_outcome") or opp.get("desired_outcome") or "",
        "related_problems": [p["statement"] for p in members],
        "existing_solutions": existing_solutions, "solution_gaps": solution_gaps,
        "source_urls": source_urls, "community_ids": [],
        "creator_ecosystem": density.get("reason", "unknown"),
        "digital_product_fit": "",
        "score": {"overall": score.get("priority_score", 0),
                  "confidence": _EV_TO_BRIEF_CONF.get(score.get("evidence_band", "VERY_LOW"), "LOW")},
    }
    universe_request = {
        "universe_opportunity_id": opp_id, "origin": "market_universe",
        "market_id": opp["market_id"], "submarket_id": opp["submarket_id"],
        "audience_id": opp["audience_id"], "opportunity_name": opp["name"],
        "member_problem_ids": opp["problem_ids"],
        "seed_source_refs": sorted(set(seed_source_refs)),
        "seed_commercial_evidence_refs": [c.get("url") or c.get("name", "") for c in commercial],
        "seed_creator_candidate_refs": density.get("candidate_refs", []),
        "priority_metadata": {  # METADATA ONLY — never research evidence
            "commercial_score": score.get("commercial_score"),
            "evidence_score": score.get("evidence_score"),
            "priority_score": score.get("priority_score"),
            "priority_classification": score.get("priority_classification"),
            "note": "Why we chose to investigate — NOT evidence of reality."},
    }
    return pocket, evidence_records, universe_request


# ---------------------------------------------------------------- creator seed (Build-4 -> Phase-9.5)
def _norm_handle(h):
    return (h or "").lstrip("@").strip().lower()


def seed_creator_candidates(opp_id: str) -> int:
    """Convert Build-4 density candidates into a Phase-9.5 import file, deduped
    by platform+handle (or url). Seed only — 9.5 still evaluates them itself."""
    src = CREATOR_INPUT_DIR / f"{opp_id}.json"
    if not src.exists():
        return 0
    cands = json.loads(src.read_text()).get("candidates", [])
    out, seen = [], set()
    for c in cands:
        key = (c.get("platform", ""), _norm_handle(c.get("handle")) or (c.get("url") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        mon = c.get("monetization_signal")
        out.append({
            "id": c.get("creator_id"), "name": c.get("display_name") or c.get("handle") or "unknown",
            "platform": c.get("platform", "unknown"), "profile_url": c.get("url"),
            "handle": c.get("handle"), "followers": c.get("followers"),
            "niche": None,
            "audience_description": f"seed relevance audience={c.get('audience_relevance')} "
                                    f"opportunity={c.get('opportunity_relevance')}",
            "relevant_content": [], "relevant_view_signals": [], "audience_problem_signals": [],
            "monetization_signals": [] if mon in (None, "unknown", "none") else [mon],
            "source_refs": c.get("source_refs", []), "basis": c.get("basis", "observed"),
        })
    CREATOR_SEED_DIR.mkdir(parents=True, exist_ok=True)
    dest = CREATOR_SEED_DIR / f"{opp_id}.json"
    payload = {"_note": "Seeded from Build-4 creator-density candidates (Phase-9.5 still evaluates).",
               "_seeded_from": str(src.relative_to(ROOT)), "candidates": out}
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return len(out)


# ---------------------------------------------------------------- stage runners (call existing engines)
def _require_promoted(opp_id: str) -> dict:
    st = _load_states().get(opp_id)
    if not st or st.get("promotion_status") != "promoted":
        raise PipelineError(f"'{opp_id}' is not promoted. Run promote_opportunity.py first.")
    return st


def run_research(opp_id: str, creds: dict | None = None, operator: str = "unknown") -> dict:
    _require_promoted(opp_id)
    svc = UniverseService()
    pocket, evidence, universe_request = build_research_request(opp_id, svc)
    import storage
    storage.get_backend().write_dossier_file(opp_id, "universe_request", universe_request)
    try:
        import universe_findings
        findings = universe_findings.FINDINGS.get(opp_id)
    except Exception:
        findings = None
    result = R.run(pocket, evidence, findings, creds=creds, operator=operator)
    rs = result["research_status"]           # complete | needs_review
    states = _load_states()
    st = states[opp_id]
    st["research_status"] = rs
    st["pipeline_stage"] = "research_complete" if rs == "complete" else "research_needs_review"
    st["rescore_requested"] = st.get("rescore_requested") or (rs == "complete")  # future Build-6 hook
    _save_states(states)
    exec_err = (result.get("plan") or {}).get("execution_error")
    if result.get("research_outcome"):
        st["research_outcome"] = result["research_outcome"]; _save_states(states)
    return {"research_status": rs, "counts": result["counts"], "files": result["files"],
            "research_outcome": result.get("research_outcome"),
            "execution_error": exec_err, "preserved": result.get("preserved", False),
            "blocked": rs != "complete"}


def run_curation(opp_id: str, override: bool = False) -> dict:
    st = _require_promoted(opp_id)
    if st["research_status"] != "complete" and not override:
        raise PipelineError(f"gate: research_status is '{st['research_status']}' — "
                            "curation requires completed research (or an explicit override).")
    try:
        result = C.run(opp_id)              # raises CurationError if brief missing/invalid
    except C.CurationError as e:
        states = _load_states(); states[opp_id]["curation_status"] = "failed"; _save_states(states)
        raise PipelineError(f"curation failed: {e}")
    states = _load_states()
    states[opp_id]["curation_status"] = "complete"
    states[opp_id]["pipeline_stage"] = "curation_complete"
    if override and st["research_status"] != "complete":
        states[opp_id]["curation_override"] = {"override": True,
            "research_status_at_curation": st["research_status"], "at": NOW()}
    _save_states(states)
    return {"curation_status": "complete", "override": bool(override and st["research_status"] != "complete"),
            "verification_required": len(result["dossier"]["verification_requirements"])}


def run_distribution(opp_id: str) -> dict:
    st = _require_promoted(opp_id)
    brief = RESEARCH_DIR / opp_id / "product_brief.json"
    if st["research_status"] != "complete" or not brief.exists():
        raise PipelineError("gate: Phase 9.5 needs a valid ProductBrief (complete research first).")
    seeded = seed_creator_candidates(opp_id)
    try:
        result = D.run(opp_id)              # Phase 9.5 does its own evaluation of the seeded pool
    except D.DistributionError as e:
        states = _load_states(); states[opp_id]["distribution_status"] = "failed"; _save_states(states)
        raise PipelineError(f"distribution failed: {e}")
    verdict = result["verdict"]
    states = _load_states()
    states[opp_id]["distribution_status"] = verdict
    states[opp_id]["pipeline_stage"] = "distribution_complete"
    _save_states(states)
    return {"seeded_candidates": seeded, "verdict": verdict, "confidence": result["confidence"]}


STAGE_ORDER = ["research", "curation", "distribution"]


def run_pipeline(opp_id: str, through: str = "research") -> dict:
    if through not in STAGE_ORDER:
        raise PipelineError(f"--through must be one of {STAGE_ORDER}")
    steps = STAGE_ORDER[:STAGE_ORDER.index(through) + 1]
    out = {}
    for stage in steps:
        if stage == "research":
            out["research"] = run_research(opp_id)
            if out["research"]["blocked"]:
                out["stopped_at"] = "research (needs_review) — downstream gated"
                break
        elif stage == "curation":
            out["curation"] = run_curation(opp_id)
        elif stage == "distribution":
            out["distribution"] = run_distribution(opp_id)
    return out


# ---------------------------------------------------------------- pipeline state service
class PipelineService:
    def __init__(self):
        self.states = _load_states()

    def get_pipeline_state(self, opp_id): return self.states.get(opp_id)
    def promoted_opportunities(self): return [s for s in self.states.values() if s["promotion_status"] == "promoted"]
    def research_ready_opportunities(self): return [s for s in self.states.values() if s["research_status"] == "pending"]
    def blocked_opportunities(self): return [s for s in self.states.values()
                                             if s["research_status"] == "needs_review" or "failed" in
                                             (s["curation_status"], s["distribution_status"])]
    def completed_research(self): return [s for s in self.states.values() if s["research_status"] == "complete"]
    def completed_curation(self): return [s for s in self.states.values() if s["curation_status"] == "complete"]
    def distribution_ready(self): return [s for s in self.states.values()
                                          if s["research_status"] == "complete" and s["curation_status"] == "complete"]


# ---------------------------------------------------------------- validation
class PipelineValidationError(Exception):
    pass


def validate_pipeline() -> dict:
    svc = UniverseService()
    states = _load_states()
    errors = []
    for oid, st in states.items():
        opp = svc.get_opportunity(oid)
        if not opp:
            errors.append(f"{oid}: pipeline state references non-existent opportunity")
            continue
        if st["universe_opportunity_id"] != oid or st["research_id"] != oid:
            errors.append(f"{oid}: canonical id not preserved")
        rank = next((r["rank"] for r in svc.ranked_opportunities() if r["opportunity_id"] == oid), None)
        if rank is None:
            errors.append(f"{oid}: no ranking entry")
        score = svc.score_for_opportunity(oid) or {}
        snap = st.get("promotion_score_snapshot", {})
        # snapshot is frozen at promotion time; it must be internally consistent
        for k in ("commercial_score", "evidence_score", "priority_score"):
            if snap.get(k) != st.get(k):
                errors.append(f"{oid}: snapshot {k} inconsistent with promotion record")
        # dependency gates reflected in state
        if st["curation_status"] == "complete" and st["research_status"] != "complete":
            errors.append(f"{oid}: curation complete without completed research")
        if st["distribution_status"] not in ("not_started",) and st["research_status"] != "complete":
            errors.append(f"{oid}: distribution ran without completed research")
        # research outputs (if any) trace back to this opportunity id
        req = RESEARCH_DIR / oid / "universe_request.json"
        if req.exists():
            u = json.loads(req.read_text())
            if u.get("universe_opportunity_id") != oid:
                errors.append(f"{oid}: research provenance id mismatch")
            for pid in u.get("member_problem_ids", []):
                if pid not in svc._p:
                    errors.append(f"{oid}: member problem {pid} does not resolve")
            for sid in u.get("seed_source_refs", []):
                if sid not in svc._src:
                    errors.append(f"{oid}: seed source {sid} does not resolve")
        # evidence non-laundering: observed claims must have real sources; inferred must not
        ev_file = RESEARCH_DIR / oid / "evidence.json"
        if ev_file.exists():
            for c in json.loads(ev_file.read_text()).get("claims", []):
                if c["basis"] == "observed" and not c.get("source_id"):
                    errors.append(f"{oid}: observed claim without source (laundering)")
    report = {"pipeline_states": len(states), "errors": errors, "passed": not errors}
    if errors:
        raise PipelineValidationError(f"{len(errors)} error(s):\n  - " + "\n  - ".join(errors[:25]))
    return report
