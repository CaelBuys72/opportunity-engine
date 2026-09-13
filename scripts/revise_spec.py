#!/usr/bin/env python3
"""Build 6.6 — Phase-9 product-spec revision (feedback loop from Build-6.5 audit).

Writes a traceable revision record, then cleanly rewrites the active Phase-9 spec
files to the revised 8-component architecture. Does NOT touch research findings,
evidence, scores, or opportunity identity.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIR = "opp-airbnb-hosts-with-1-5-properties-turnover-and-property-operations"
RES = ROOT / "research" / AIR
OUTCOME = "Run reliable, repeatable turnovers with less effort and fewer misses."

# revised active components (order = buyer journey). deliverable drives _required_formats.
REVISED = [
 {"id": "cmp-3", "name": "Property Setup Workbook", "type": "template",
  "format": "editable fill-in template", "deliverable": "Editable document (.docx + PDF) or fillable template",
  "reqs": ["Single host-facing source of truth for every guest-relevant detail.",
           "Includes the sections hosts most often forget (parking, quirks, quiet hours, emergency, nearest pharmacy).",
           "Feeds the guest-facing Welcome Guide."]},
 {"id": "cmp-8", "name": "Welcome Guide for Guests", "type": "template",
  "format": "editable fill-in template", "deliverable": "Editable document (.docx + PDF) or fillable template",
  "reqs": ["Polished, guest-facing; no host-only operational detail.", "Derived from the Property Setup Workbook."]},
 {"id": "cmp-2", "name": "Master Turnover SOP", "type": "template",
  "format": "editable fill-in template", "deliverable": "Editable document (.docx + PDF) or fillable template",
  "reqs": ["Covers the full turnover: entry, room-by-room reset, laundry, kitchen, bathrooms, supplies, damage check, final inspection.",
           "States the guest-ready standard and an issue-escalation path.",
           "Absorbs the former standalone step-by-step order (merged)."]},
 {"id": "cmp-4", "name": "Cleaner Handoff Sheet", "type": "worksheet",
  "format": "structured worksheet (printable + fillable)", "deliverable": "Fillable PDF + printable version",
  "reqs": ["A single sheet the cleaner completes each turnover.", "Records issues and items to reorder."]},
 {"id": "cmp-7", "name": "Quick Turnover Checklist", "type": "template",
  "format": "editable fill-in template", "deliverable": "Editable document (.docx + PDF) or fillable template",
  "reqs": ["One-page field checklist condensed directly from the Master Turnover SOP.", "Print-and-pin with checkboxes."]},
 {"id": "cmp-1", "name": "Supply + Inventory Tracker", "type": "tool",
  "format": "interactive spreadsheet / calculator", "deliverable": "Spreadsheet (Google Sheets + .xlsx export)",
  "reqs": ["Reorder Status auto-flags when Current < Minimum (real formula).",
           "Columns: property, category, item, location, current/min/reorder qty, status, last restocked, notes.",
           "Usable in under 5 minutes with example rows to replace."]},
 {"id": "cmp-10", "name": "Damage & Incident Log", "type": "tool",
  "format": "interactive spreadsheet / calculator", "deliverable": "Spreadsheet (Google Sheets + .xlsx export)",
  "reqs": ["Log each issue: area, severity, description, action taken, status, follow-up.",
           "Distinct job from the tracker — 'what happened and is it resolved?'.",
           "Simple; no legal or insurance claims."]},
 {"id": "cmp-9", "name": "Guest Message Library", "type": "bonus",
  "format": "bonus asset", "deliverable": "Supporting file",
  "reqs": ["Copy-paste templates for every booking stage.",
           "Includes an issue-resolution / apology and a late-checkout snippet."]},
]
RETIRED = ["cmp-5", "cmp-6"]


def main():
    # historical traceability
    (RES / "spec_revisions").mkdir(parents=True, exist_ok=True)
    revision = {
        "revision_id": "revision-001", "opportunity_id": AIR,
        "reason": "Build 6.5 acceptance audit (score 77.1; spec_revision_required)",
        "previous_acceptance_score": 77.1,
        "issues": ["overlap cmp-2/cmp-7 and cmp-3/cmp-8", "cmp-5 and cmp-6 too thin",
                   "missing damage/incident + inventory workflows", "perceived value low", "9-component padding"],
        "changes": ["cmp-1 -> Supply + Inventory Tracker (expanded)",
                    "cmp-2 -> Master Turnover SOP (merged old cmp-2 detailed + cmp-5 steps)",
                    "cmp-3 -> Property Setup Workbook (absorbed old cmp-6)",
                    "cmp-7 -> Quick Turnover Checklist (condensed from SOP)",
                    "cmp-9 -> Guest Message Library (+issue-resolution/late-checkout)"],
        "components_added": ["cmp-10 Damage & Incident Log"],
        "components_removed": RETIRED,
        "components_merged": [{"into": "cmp-2", "from": ["cmp-2(detailed)", "cmp-5(steps)"]},
                             {"into": "cmp-3", "absorbed": ["cmp-6(sections hosts forget)"]}],
        "components_retained_unchanged": ["cmp-4", "cmp-8"],
        "expected_improvements": ["less padding/overlap (cohesion)", "stronger operational core (utility)",
                                  "two missing workflows added (completeness)", "two functional spreadsheets (value)"],
        "research_unchanged": True,
    }
    (RES / "spec_revisions" / "revision-001.json").write_text(json.dumps(revision, indent=2, ensure_ascii=False))

    # rewrite active spec files
    arch = {"opportunity_id": AIR, "revision": "revision-001", "components": [
        {"id": c["id"], "name": c["name"], "type": c["type"], "format": c["format"],
         "purpose": f"{c['name']} — {c['reqs'][0]}", "basis": "inferred",
         "maps_to_jobs": ["job-0"], "maps_to_outcome": OUTCOME,
         "source_field": "revision-001", "unmapped": False,
         "format_basis": "inferred", "format_rationale": "revised per Build-6.5 acceptance audit"}
        for c in REVISED]}
    (RES / "product_architecture.json").write_text(json.dumps(arch, indent=2, ensure_ascii=False))

    specs = {"revision": "revision-001", "specs": [
        {"component_id": c["id"], "name": c["name"], "type": c["type"], "format": c["format"],
         "purpose": f"{c['name']}.", "maps_to_jobs": ["job-0"], "maps_to_outcome": OUTCOME,
         "functional_requirements": [{"req": r, "basis": "inferred"} for r in c["reqs"]],
         "inputs": ["buyer's property details / operational data"],
         "outputs": ["a ready-to-use operational asset"],
         "requires_external_verification": False, "verification_reason": "", "unmapped_flag": False}
        for c in REVISED]}
    (RES / "component_specs.json").write_text(json.dumps(specs, indent=2, ensure_ascii=False))

    assets = {"revision": "revision-001", "assets": [
        {"id": f"asset-{i+1}", "component_id": c["id"], "for": c["name"], "deliverable": c["deliverable"],
         "tooling": "spreadsheet app" if "Spreadsheet" in c["deliverable"] else "doc editor",
         "notes": "", "requires_external_verification": False, "basis": "inferred"}
        for i, c in enumerate(REVISED)]}
    (RES / "asset_requirements.json").write_text(json.dumps(assets, indent=2, ensure_ascii=False))

    seq = [{"order": i + 1, "step": f"Build: {c['name']}", "component_id": c["id"],
            "format": c["format"], "depends_on": [] if i == 0 else [i], "verification_gate": None,
            "basis": "inferred"} for i, c in enumerate(REVISED)]
    seq.append({"order": len(REVISED) + 1, "step": "Assemble bundle + QA against quality_requirements.json",
                "component_id": None, "depends_on": list(range(1, len(REVISED) + 1)),
                "verification_gate": "All flagged components verified", "basis": "inferred"})
    (RES / "production_plan.json").write_text(json.dumps({"revision": "revision-001", "sequence": seq}, indent=2))

    # update curation_dossier lightly (preserve other fields)
    dossier = json.loads((RES / "curation_dossier.json").read_text())
    dossier["revision"] = "revision-001"
    dossier["components"] = [{"id": c["id"], "name": c["name"], "type": c["type"], "format": c["format"],
                             "purpose": f"{c['name']}.", "maps_to_jobs": ["job-0"]} for c in REVISED]
    dossier["production_sequence"] = seq
    dossier["verification_requirements"] = []
    (RES / "curation_dossier.json").write_text(json.dumps(dossier, indent=2, ensure_ascii=False))

    print(f"revision-001 written. Active components: {[c['id'] for c in REVISED]} (retired {RETIRED})")


if __name__ == "__main__":
    main()
