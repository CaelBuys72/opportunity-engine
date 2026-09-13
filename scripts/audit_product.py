#!/usr/bin/env python3
"""Build 6.5/6.6 — product acceptance audit.

Scores are a genuine internal QA judgement (authored below), NOT market
validation. The product-level acceptance_score is COMPUTED from the per-component
scores with fixed weights (reproducible). Release is gated at >=85; below that the
product is marked revision_required. Scores are not tuned to pass.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
AIR = "opp-airbnb-hosts-with-1-5-properties-turnover-and-property-operations"
PDIR = ROOT / "products" / AIR
STATES = ROOT / "data" / "universe" / "pipeline_states.json"

WEIGHTS = {"utility": 0.30, "completeness": 0.20, "usability": 0.20, "cohesion": 0.15, "perceived_value": 0.15}
THRESHOLD = 85
V1 = {"utility": 78.9, "completeness": 73.3, "usability": 82.2, "cohesion": 80.0, "perceived_value": 68.9, "overall": 77.1}

# genuine per-component assessment of the REVISED 8-component product (1-10 each)
COMPONENTS = [
 {"component_id": "cmp-3", "name": "Property Setup Workbook", "independently_useful": "yes",
  "utility": 9, "completeness": 9, "usability": 8, "cohesion": 9, "perceived_value": 8,
  "strengths": ["Single host source-of-truth", "Absorbs the 'sections hosts forget'", "Feeds the guest guide"],
  "weaknesses": ["Field-heavy to fill the first time"], "missing_items": [], "recommended_changes": []},
 {"component_id": "cmp-8", "name": "Welcome Guide for Guests", "independently_useful": "yes",
  "utility": 9, "completeness": 8, "usability": 9, "cohesion": 9, "perceived_value": 8,
  "strengths": ["Warm, guest-facing", "High-visibility asset"], "weaknesses": [],
  "missing_items": ["Optional Wi-Fi QR"], "recommended_changes": []},
 {"component_id": "cmp-2", "name": "Master Turnover SOP", "independently_useful": "yes",
  "utility": 9, "completeness": 9, "usability": 8, "cohesion": 9, "perceived_value": 9,
  "strengths": ["Full turnover standard incl. inspection + escalation", "Merges the old thin steps into one strong asset",
                "Cross-references tracker, log, handoff"],
  "weaknesses": ["Long — a reference, not instant"], "missing_items": [], "recommended_changes": []},
 {"component_id": "cmp-4", "name": "Cleaner Handoff Sheet", "independently_useful": "yes",
  "utility": 8, "completeness": 8, "usability": 8, "cohesion": 9, "perceived_value": 7,
  "strengths": ["One sheet cleaners actually complete", "PDF + editable"], "weaknesses": ["Modest standalone"],
  "missing_items": [], "recommended_changes": []},
 {"component_id": "cmp-7", "name": "Quick Turnover Checklist", "independently_useful": "yes",
  "utility": 8, "completeness": 8, "usability": 9, "cohesion": 9, "perceived_value": 8,
  "strengths": ["One-page field version of the SOP", "Print-and-pin"], "weaknesses": ["Condensed by design"],
  "missing_items": [], "recommended_changes": []},
 {"component_id": "cmp-1", "name": "Supply + Inventory Tracker", "independently_useful": "yes",
  "utility": 9, "completeness": 9, "usability": 9, "cohesion": 9, "perceived_value": 9,
  "strengths": ["Auto reorder flag on a real formula", "Inventory + restock in one", "Usable in <5 min"],
  "weaknesses": ["Single-sheet"], "missing_items": [], "recommended_changes": []},
 {"component_id": "cmp-10", "name": "Damage & Incident Log", "independently_useful": "yes",
  "utility": 8, "completeness": 9, "usability": 8, "cohesion": 9, "perceived_value": 8,
  "strengths": ["Fills a previously-missing workflow", "Distinct job from the tracker", "Simple, no legal claims"],
  "weaknesses": ["Manual logging"], "missing_items": [], "recommended_changes": []},
 {"component_id": "cmp-9", "name": "Guest Message Library", "independently_useful": "yes",
  "utility": 8, "completeness": 8, "usability": 8, "cohesion": 8, "perceived_value": 7,
  "strengths": ["Every booking stage + issue-resolution + late-checkout", "Copy-paste ready"],
  "weaknesses": ["Commoditised content"], "missing_items": [], "recommended_changes": []},
]

SPEC_COMPLIANCE = [
 {"component_id": c, "compliant": True, "attribution": "ok"} for c in
 ["cmp-1", "cmp-2", "cmp-3", "cmp-4", "cmp-7", "cmp-8", "cmp-9", "cmp-10"]]


def dim_avg(dim):
    return round(sum(c[dim] for c in COMPONENTS) / len(COMPONENTS) * 10, 1)


def main():
    dims = {d: dim_avg(d) for d in WEIGHTS}
    acceptance = round(sum(dims[d] * w for d, w in WEIGHTS.items()), 1)
    band = ("strong release candidate" if acceptance >= 85 else
            "usable but improve before release" if acceptance >= 75 else
            "meaningful revision required" if acceptance >= 60 else "do not proceed")
    manifest = json.loads((PDIR / "manifest.json").read_text())
    structural_ok = all(c["production_status"] == "built" and c["qa_status"] == "passed"
                        for c in manifest["components"])
    verification_ok = all(c["verification_status"] != "pending" for c in manifest["components"])
    decision = "release_candidate" if (acceptance >= THRESHOLD and structural_ok
                                       and verification_ok and manifest["bundle_status"] == "complete") \
        else "revision_required"

    (PDIR / "qa" / "component_acceptance.json").write_text(json.dumps(COMPONENTS, indent=2, ensure_ascii=False))
    (PDIR / "qa" / "spec_compliance.json").write_text(json.dumps({
        "revision": "revision-001", "spec_revision_required": False,
        "components": SPEC_COMPLIANCE,
        "note": "Revision-001 resolved the Build-6.5 spec issues: removed padding (cmp-5/cmp-6), merged the "
                "SOP, added the inventory + damage workflows. Residual gap is concept-level (perceived value)."},
        indent=2, ensure_ascii=False))
    (PDIR / "qa" / "buyer_journey.json").write_text(json.dumps({
        "workflow": [{"step": i + 1, "component_id": cid, "action": step, "what_it_does": what, "editable": ed}
                     for i, (cid, step, what, ed, _f) in enumerate(__import__("production").JOURNEY)],
        "start_here": "bundle/START_HERE.md"}, indent=2, ensure_ascii=False))

    v2 = {**dims, "overall": acceptance}
    product_acceptance = {
        "opportunity_id": AIR, "revision": "revision-001",
        "acceptance_score": acceptance, "band": band, "dimension_scores": dims,
        "weights": WEIGHTS, "threshold": THRESHOLD,
        "v1_vs_v2": {d: {"v1": V1[d], "v2": v2[d], "delta": round(v2[d] - V1[d], 1)}
                     for d in ["utility", "completeness", "usability", "cohesion", "perceived_value", "overall"]},
        "structural_qa": "passed" if structural_ok else "failed",
        "verification": "clear" if verification_ok else "pending",
        "bundle_status": manifest["bundle_status"], "decision": decision,
        "remaining_weaknesses": [
            "Perceived value ~79/100 is still the ceiling — a template/checklist kit in a saturated niche; "
            "the wedge is reliability + completeness, not novelty. This is concept-level, not production/spec.",
        ] if acceptance < 85 else [],
        "recommendation": "RELEASE CANDIDATE" if decision == "release_candidate" else "REVISE AGAIN (concept/positioning, not more components)",
    }
    (PDIR / "qa" / "product_acceptance.json").write_text(json.dumps(product_acceptance, indent=2, ensure_ascii=False))

    manifest["release_status"] = decision
    manifest["product_status"] = "release_candidate" if decision == "release_candidate" else "revision_required"
    manifest["acceptance_score"] = acceptance
    manifest["revision"] = "revision-001"
    (PDIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    states = {s["opportunity_id"]: s for s in json.loads(STATES.read_text())}
    if AIR in states:
        states[AIR]["product_build_status"] = "release_candidate" if decision == "release_candidate" else "blocked"
        STATES.write_text(json.dumps(list(states.values()), indent=2, ensure_ascii=False))

    print(f"V2 acceptance: {acceptance}/100  ({band})")
    print(f"{'metric':<16}{'V1':>7}{'V2':>7}{'Δ':>7}")
    for d in ["utility", "completeness", "usability", "cohesion", "perceived_value", "overall"]:
        print(f"  {d:<14}{V1[d]:>7}{v2[d]:>7}{round(v2[d]-V1[d],1):>7}")
    print(f"Decision: {decision} | recommendation: {product_acceptance['recommendation']}")


if __name__ == "__main__":
    main()
