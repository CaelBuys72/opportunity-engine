"""Build 4 — LIGHTWEIGHT creator / distribution density.

Answers only: "Does a relevant creator ecosystem APPEAR to exist around this
opportunity's audience?" — a cheap screening signal, NOT Phase-9.5 per-creator
qualification (which stays separate and expensive).

Density is a SEARCH-YIELD signal, never a census. It is derived only from real
creator candidates manually imported to data/creator_density_inputs/<opp>.json.
No accounts, followers, views, emails, or counts are fabricated: with no import,
density is UNKNOWN (never NONE, never 0).
"""
from __future__ import annotations
import json
from pathlib import Path

from universe import UniverseService

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "data" / "creator_density_inputs"

# relevant-candidate count -> band (search yield, not population)
def _band(relevant: int, has_data: bool) -> str:
    if not has_data:
        return "UNKNOWN"
    if relevant == 0:
        return "NONE"
    if relevant <= 3:
        return "LOW"
    if relevant <= 8:
        return "MEDIUM"
    if relevant <= 20:
        return "HIGH"
    return "VERY_HIGH"


def build_creator_search_profile(opp: dict, svc: UniverseService) -> dict:
    m = svc._m.get(opp["market_id"]); s = svc._s.get(opp["submarket_id"])
    a = svc._a.get(opp["audience_id"])
    concepts = [x for x in [m and m["name"], s and s["name"], a and a["name"], opp["name"]] if x]
    return {"opportunity_id": opp["id"], "concepts": concepts,
            "note": "concepts derived from market/submarket/audience/opportunity; generic, not hardcoded"}


def gather_creator_candidates(opp_id: str, import_file: str | None) -> tuple[list[dict], dict]:
    """SWAP-POINT for future live retrieval. V0: manual import only."""
    f = Path(import_file) if import_file else (INPUT_DIR / f"{opp_id}.json")
    if not f.exists():
        return [], {"retrieval_method": "manual-import", "status": "no_data",
                    "queries_run": 0, "note": f"No creator input at {f}."}
    data = json.loads(f.read_text())
    cands = data.get("candidates", [])
    meta = {"retrieval_method": data.get("retrieval_method", "manual-import"),
            "status": "loaded", "queries_run": data.get("queries_run", 0),
            "note": data.get("note", "")}
    norm = []
    for i, c in enumerate(cands, 1):
        norm.append({
            "creator_id": c.get("creator_id") or f"cd-{opp_id[:20]}-{i}",
            "platform": c.get("platform", "unknown"), "handle": c.get("handle"),
            "url": c.get("url"), "display_name": c.get("display_name"),
            "audience_relevance": c.get("audience_relevance", "unknown"),
            "opportunity_relevance": c.get("opportunity_relevance", "unknown"),
            "followers": c.get("followers"),          # null unless observed
            "recent_view_evidence": c.get("recent_view_evidence", []),
            "contact_route": c.get("contact_route", "unknown"),
            "monetization_signal": c.get("monetization_signal", "unknown"),
            "basis": c.get("basis", "observed"), "source_refs": c.get("source_refs", []),
        })
    return norm, meta


def assess_density(opp_id: str, candidates: list[dict], meta: dict) -> dict:
    has_data = meta["status"] == "loaded"
    relevant = [c for c in candidates
                if c["opportunity_relevance"] in ("high", "medium")
                or c["audience_relevance"] in ("high", "medium")]
    band = _band(len(relevant), has_data)
    if not has_data:
        conf, basis = "UNKNOWN", "unknown"
        reason = "No creator evidence imported; density unknown (not zero)."
    else:
        conf, basis = "MEDIUM", "observed"
        reason = (f"Search-yield signal: {len(candidates)} candidate(s) imported, "
                  f"{len(relevant)} relevant to this audience/opportunity. "
                  f"NOT a census of the market.")
    return {
        "opportunity_id": opp_id, "queries_run": meta.get("queries_run", 0),
        "candidates_discovered": len(candidates), "relevant_candidates": len(relevant),
        "density_band": band, "basis": basis, "confidence": conf,
        "retrieval_method": meta.get("retrieval_method", "manual-import"),
        "reason": reason,
        "candidate_refs": [c["creator_id"] for c in relevant],
        "candidates": candidates,
    }


def density_for(opp_id: str, import_file: str | None = None) -> dict:
    cands, meta = gather_creator_candidates(opp_id, import_file)
    return assess_density(opp_id, cands, meta)
