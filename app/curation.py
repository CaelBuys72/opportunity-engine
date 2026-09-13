"""Phase 9 — Product Curation Engine.

Transforms a validated Phase-8 Product Brief into a production-ready product
SPECIFICATION (not the product itself). Deterministic, local-first, no network.

Pipeline (each stage a pure function of its inputs):
  load_brief -> define_transformation -> derive_jobs_to_be_done -> derive_components
  -> select_component_formats -> define_component_requirements -> define_asset_requirements
  -> define_quality_requirements -> define_buyer_effort -> build_production_plan
  -> build_curation_dossier

Guarantees:
  * Fails HONESTLY on a malformed brief (raises CurationError listing what's
    missing) instead of fabricating fields.
  * Never defaults to an ebook; formats are chosen from component nature +
    the brief's transformation.
  * Every component has a purpose and maps to a job / problem / desired outcome.
  * Requirements are tagged basis: "evidence-backed" (traceable to a brief field
    Phase 8 derived from evidence) vs "inferred" (a design decision made here).
  * Preserves Phase-8 exclusions, risks, unknowns, and evidence requirements
    (incl. inaccessible sources), and flags components needing external
    verification (tax/legal/financial/health/medical accuracy).
  * Does not generate product content, creator outreach, or Whop integration.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "research"

REQUIRED_FIELDS = ["pocket_id", "product_concept", "product_format",
                   "core_transformation", "desired_outcome", "core_problem"]
COMPONENT_SOURCE_FIELDS = ["required_tools", "required_templates",
                           "required_worksheets", "required_sections",
                           "product_structure", "bonus_assets"]

# component type -> concrete production format (ebook is never a default)
TYPE_FORMAT = {
    "tool": "interactive spreadsheet / calculator",
    "template": "editable fill-in template",
    "worksheet": "structured worksheet (printable + fillable)",
    "reference": "concise reference guide page",   # a page, not a long ebook
    "asset": "supporting asset",
    "bonus": "bonus asset",
}
SOURCE_TYPE = {
    "required_tools": "tool", "required_templates": "template",
    "required_worksheets": "worksheet", "required_sections": "reference",
    "product_structure": "asset", "bonus_assets": "bonus",
}
# words that force external professional verification
VERIFY_TRIGGERS = ["tax", "se-tax", "se tax", "schedule c", "quarterly", "irs",
                   "deduction", "legal", "contract", "financial", "health",
                   "medical", "estimate", "liability", "compliance"]


class CurationError(Exception):
    """Raised when the brief cannot be curated honestly (missing/invalid input)."""


# ------------------------------------------------------------------ helpers
def _tokens(s: str) -> set[str]:
    return {w for w in "".join(c.lower() if c.isalnum() else " " for c in s).split() if len(w) > 3}


def _needs_verification(text: str) -> tuple[bool, str]:
    t = text.lower()
    for kw in VERIFY_TRIGGERS:
        if kw in t:
            return True, (f"Touches '{kw}' — domain accuracy (tax/legal/financial/health) "
                          "must be verified by a qualified professional before release.")
    return False, ""


# ------------------------------------------------------------------ stages
def load_brief(opp_id: str) -> dict:
    import storage
    brief = storage.get_backend().read_dossier_file(opp_id, "product_brief")
    if not brief:
        raise CurationError(f"No product_brief for '{opp_id}'. Run Phase 8 first "
                            f"(python3 scripts/run_research.py {opp_id}).")

    missing = [k for k in REQUIRED_FIELDS if not brief.get(k)]
    if missing:
        raise CurationError(f"Brief is incomplete — missing/empty required fields: {missing}. "
                            "Refusing to curate rather than invent them.")
    if not any(brief.get(k) for k in COMPONENT_SOURCE_FIELDS):
        raise CurationError("Brief has no component sources (required_tools/templates/worksheets/"
                            "sections/product_structure/bonus_assets are all empty). "
                            "Nothing to derive components from — refusing to fabricate a product.")
    if "ebook" in str(brief.get("product_format", "")).lower():
        # allowed only if the brief itself explicitly justifies it; otherwise flag
        brief.setdefault("_warnings", []).append(
            "Brief format mentions 'ebook' — curation will still choose formats per component.")
    return brief


def define_transformation(brief: dict) -> dict:
    ct = brief["core_transformation"]
    frm, to = ct, ""
    for sep in ["→", "->", "To:"]:
        if sep in ct:
            parts = ct.split(sep, 1)
            frm, to = parts[0].replace("From:", "").strip(" .:"), parts[1].strip(" .:")
            break
    return {"from_state": frm, "to_state": to or brief["desired_outcome"],
            "promise": brief.get("product_promise", ""),
            "core_problem": brief["core_problem"],
            "desired_outcome": brief["desired_outcome"], "basis": "evidence-backed"}


def derive_jobs_to_be_done(brief: dict) -> list[dict]:
    jobs = [{"id": "job-0", "statement": f"Achieve: {brief['desired_outcome']}",
             "source": "desired_outcome", "basis": "evidence-backed"}]
    for i, rp in enumerate(brief.get("related_problems", []), 1):
        jobs.append({"id": f"job-{i}", "statement": f"Resolve: {rp}",
                     "source": "related_problem", "basis": "evidence-backed"})
    return jobs


def _map_to_jobs(text: str, jobs: list[dict]) -> list[str]:
    tok = _tokens(text)
    hits = [j["id"] for j in jobs if j["id"] != "job-0" and _tokens(j["statement"]) & tok]
    return hits or ["job-0"]   # always maps to the overall outcome at minimum


def derive_components(brief: dict, jobs: list[dict]) -> list[dict]:
    comps, seen = [], set()
    for field in COMPONENT_SOURCE_FIELDS:
        for item in brief.get(field, []):
            key = item.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            ctype = SOURCE_TYPE[field]
            mapped = _map_to_jobs(item, jobs)
            comps.append({
                "id": f"cmp-{len(comps)+1}", "name": item, "type": ctype,
                "source_field": field,
                "purpose": f"{ctype.capitalize()} that helps the buyer: "
                           f"{item.rstrip('.')}.",
                "maps_to_jobs": mapped,
                "maps_to_outcome": brief["desired_outcome"],
                "unmapped": mapped == ["job-0"] and field not in ("required_sections",),
                "basis": "evidence-backed",   # the item itself came from the brief
            })
    return comps


def select_component_formats(components: list[dict], brief: dict) -> list[dict]:
    for c in components:
        fmt = TYPE_FORMAT.get(c["type"], "supporting asset")
        # refine bonus/asset by wording
        low = c["name"].lower()
        if c["type"] == "bonus":
            if "preset" in low or "variant" in low:
                fmt = "preset / variant pack for the core tool"
            elif "checklist" in low:
                fmt = "one-page checklist"
        if c["type"] == "asset":
            if "spreadsheet" in low or "calculat" in low:
                fmt = TYPE_FORMAT["tool"]
            elif "template" in low:
                fmt = TYPE_FORMAT["template"]
            elif "guide" in low:
                fmt = TYPE_FORMAT["reference"]
        c["format"] = fmt
        c["format_basis"] = "inferred"       # a design decision
        c["format_rationale"] = (f"Chosen from component type '{c['type']}' and the "
                                  f"transformation; deliberately not an ebook.")
    assert not any("ebook" in c["format"].lower() for c in components), "ebook must never be a component format"
    return components


def define_component_requirements(components: list[dict], brief: dict) -> list[dict]:
    complaint_text = " ".join(brief.get("key_objections", []) +
                              brief.get("related_problems", []) +
                              brief.get("differentiation", [])).lower()
    specs = []
    for c in components:
        needs_v, reason = _needs_verification(c["name"] + " " + c["purpose"])
        reqs = []
        # evidence-backed requirements pulled from brief complaints/differentiation
        if "formula" in complaint_text and c["type"] in ("tool", "worksheet"):
            reqs.append({"req": "Formulas must not break when the buyer edits inputs "
                                 "(protect/lock calculation cells).", "basis": "evidence-backed"})
        if c["type"] == "tool":
            reqs.append({"req": "All calculations auto-update from a single input area.",
                         "basis": "inferred"})
            reqs.append({"req": "Include one fully worked example the buyer can copy.",
                         "basis": "inferred"})
        if c["type"] == "template":
            reqs.append({"req": "Editable fields clearly marked; no design tool lock-in "
                                 "(offer an editable + a ready-to-send format).", "basis": "inferred"})
        if c["type"] == "reference":
            reqs.append({"req": "Plain-English, skimmable; one screen per concept, no filler.",
                         "basis": "evidence-backed" if "plain" in complaint_text else "inferred"})
        spec = {
            "component_id": c["id"], "name": c["name"], "type": c["type"],
            "format": c["format"], "purpose": c["purpose"],
            "maps_to_jobs": c["maps_to_jobs"], "maps_to_outcome": c["maps_to_outcome"],
            "functional_requirements": reqs,
            "inputs": _infer_io(c, brief)[0], "outputs": _infer_io(c, brief)[1],
            "requires_external_verification": needs_v,
            "verification_reason": reason,
            "unmapped_flag": c.get("unmapped", False),
        }
        specs.append(spec)
    return specs


def _infer_io(c: dict, brief: dict) -> tuple[list, list]:
    if c["type"] == "tool":
        return (["buyer-entered figures (income, expenses, dates)"],
                ["calculated result the buyer acts on (e.g. amount to set aside, totals)"])
    if c["type"] == "worksheet":
        return (["buyer's own situation / entries"], ["a completed, decision-ready worksheet"])
    if c["type"] == "template":
        return (["buyer's details slotted into marked fields"], ["a finished, ready-to-use document"])
    return ([], [])


def define_asset_requirements(components: list[dict]) -> list[dict]:
    assets = []
    for c in components:
        fmt = c["format"]
        if "spreadsheet" in fmt or "calculator" in fmt or "preset" in fmt:
            producible = {"deliverable": "Spreadsheet (Google Sheets + .xlsx export)",
                          "tooling": "spreadsheet app", "notes": "protect formula cells"}
        elif "template" in fmt:
            producible = {"deliverable": "Editable document (.docx + PDF) or fillable template",
                          "tooling": "doc editor", "notes": "mark editable fields"}
        elif "worksheet" in fmt:
            producible = {"deliverable": "Fillable PDF + printable version", "tooling": "doc/pdf",
                          "notes": ""}
        elif "reference" in fmt or "checklist" in fmt:
            producible = {"deliverable": "Short PDF (one concept per page)", "tooling": "doc/pdf",
                          "notes": "no long-form ebook"}
        else:
            producible = {"deliverable": "Supporting file", "tooling": "tbd", "notes": ""}
        assets.append({
            "id": f"asset-{len(assets)+1}", "component_id": c["id"], "for": c["name"],
            **producible,
            "requires_external_verification": _needs_verification(c["name"] + c["purpose"])[0],
            "basis": "inferred",
        })
    return assets


def define_quality_requirements(brief: dict, components: list[dict]) -> dict:
    glob = []
    diff = " ".join(brief.get("differentiation", [])).lower()
    if "correct" in diff or any(_needs_verification(c["name"])[0] for c in components):
        glob.append({"req": "Every calculation/claim verified correct against current, cited rules "
                             "before release.", "basis": "evidence-backed",
                     "source": "brief.differentiation / risks"})
    if "formula" in " ".join(brief.get("related_problems", [])).lower():
        glob.append({"req": "No broken formulas on edit — stress-test with bad/blank inputs.",
                     "basis": "evidence-backed", "source": "brief.related_problems"})
    glob.append({"req": "Time-to-first-value under ~15 minutes; usable without a manual.",
                 "basis": "inferred", "source": "buyer-effort principle"})
    glob.append({"req": "Honor exclusions verbatim (see exclusions list); scope stays tight.",
                 "basis": "evidence-backed", "source": "brief.exclude"})
    return {"global": glob, "exclusions_preserved": brief.get("exclude", [])}


def define_buyer_effort(components: list[dict]) -> dict:
    per = []
    for c in components:
        mins = ["Ship with a prefilled worked example"] if c["type"] in ("tool", "worksheet") else []
        if c["type"] == "tool":
            mins += ["Single input area", "Dropdowns instead of free-typing where possible"]
        if c["type"] == "template":
            mins += ["Provide a ready-to-send version, not only an editable one"]
        per.append({"component_id": c["id"], "name": c["name"],
                    "effort_level": "low" if mins else "medium",
                    "effort_minimizers": mins or ["Keep to one screen / one task"],
                    "basis": "inferred"})
    return {"overall_target": "Buyer reaches first useful result in one sitting, no setup call.",
            "per_component": per, "basis": "inferred"}


def build_production_plan(components: list[dict], assets: list[dict]) -> dict:
    order = {"tool": 1, "worksheet": 2, "template": 3, "reference": 4, "asset": 5, "bonus": 6}
    seq, n = [], 0
    for c in sorted(components, key=lambda x: order.get(x["type"], 9)):
        n += 1
        gate = ("EXTERNAL VERIFICATION required before this component is releasable"
                if _needs_verification(c["name"] + c["purpose"])[0] else None)
        seq.append({"order": n, "step": f"Build: {c['name']}", "component_id": c["id"],
                    "format": c["format"], "depends_on": [] if n == 1 else [n - 1],
                    "verification_gate": gate, "basis": "inferred"})
    seq.append({"order": n + 1, "step": "Assemble bundle + QA against quality_requirements.json",
                "component_id": None, "depends_on": list(range(1, n + 1)),
                "verification_gate": "All flagged components verified", "basis": "inferred"})
    return {"sequence": seq}


def build_curation_dossier(opp_id, brief, transformation, jobs, components, comp_specs,
                           assets, quality, effort, plan, evidence_requirements) -> dict:
    verification = [{"component_id": s["component_id"], "name": s["name"],
                     "reason": s["verification_reason"], "verified_by": "qualified professional (unresolved)"}
                    for s in comp_specs if s["requires_external_verification"]]
    unresolved = list(brief.get("risks_unknowns", []))
    if "unknown" in brief.get("price_range", "").lower():
        unresolved.append("Price not finalized — brief price is Unknown.")
    unmapped = [s["name"] for s in comp_specs if s["unmapped_flag"]]
    if unmapped:
        unresolved.append(f"Components mapped only to the overall outcome (weak job fit): {unmapped}")
    if verification:
        unresolved.append("External verification pending for: "
                          + ", ".join(v["name"] for v in verification))
    eb = sum(1 for s in comp_specs for r in s["functional_requirements"] if r["basis"] == "evidence-backed")
    inf = sum(1 for s in comp_specs for r in s["functional_requirements"] if r["basis"] == "inferred")
    return {
        "opportunity_id": opp_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product_concept": brief["product_concept"],
        "product_format": brief["product_format"],
        "transformation": transformation,
        "jobs_to_be_done": jobs,
        "components": [{"id": c["id"], "name": c["name"], "type": c["type"],
                        "format": c["format"], "purpose": c["purpose"],
                        "maps_to_jobs": c["maps_to_jobs"]} for c in components],
        "asset_requirements": assets,
        "quality_requirements": quality,
        "buyer_effort": effort,
        "production_sequence": plan["sequence"],
        "verification_requirements": verification,
        "unresolved_questions": unresolved,
        "carried_forward": {
            "exclusions": brief.get("exclude", []),
            "risks_unknowns": brief.get("risks_unknowns", []),
            "differentiation": brief.get("differentiation", []),
            "evidence_requirements": evidence_requirements,
        },
        "basis_summary": {"component_requirements_evidence_backed": eb,
                          "component_requirements_inferred": inf,
                          "note": "evidence-backed = traceable to a Phase-8 brief field; "
                                  "inferred = design decision made by the curation engine."},
        "handoff": {"consumes": "product_architecture.json + component_specs.json + "
                                "asset_requirements.json + quality_requirements.json + production_plan.json",
                    "for": "Phase 10 Product Builder",
                    "must_respect": ["verification_requirements", "carried_forward.exclusions",
                                     "quality_requirements", "unresolved_questions"]},
    }


# ------------------------------------------------------------------ evidence requirements (Phase 8 carry-over)
def _load_evidence_requirements(opp_id: str) -> list[dict]:
    """Preserve Phase-8 sources that were inaccessible (requirement, not fabricated)."""
    import storage
    doc = storage.get_backend().read_dossier_file(opp_id, "sources") or {}
    srcs = doc.get("sources", [])
    return [{"label": s["label"], "url": s.get("url"), "note": s.get("note", ""),
             "status": "must be retrieved/verified later"}
            for s in srcs if not s.get("accessible", True)]


# ------------------------------------------------------------------ orchestrator
def _write(opp_id: str, name: str, obj) -> str:
    import storage
    storage.get_backend().write_dossier_file(opp_id, name, obj)
    return f"research/{opp_id}/{name}.json"


def run(opp_id: str) -> dict:
    """Execute all 11 stages. Raises CurationError on malformed input (honest failure)."""
    brief = load_brief(opp_id)
    transformation = define_transformation(brief)
    jobs = derive_jobs_to_be_done(brief)
    components = derive_components(brief, jobs)
    components = select_component_formats(components, brief)
    comp_specs = define_component_requirements(components, brief)
    assets = define_asset_requirements(components)
    quality = define_quality_requirements(brief, components)
    effort = define_buyer_effort(components)
    plan = build_production_plan(components, assets)
    evidence_requirements = _load_evidence_requirements(opp_id)
    dossier = build_curation_dossier(opp_id, brief, transformation, jobs, components,
                                     comp_specs, assets, quality, effort, plan, evidence_requirements)

    product_spec = {
        "opportunity_id": opp_id, "product_concept": brief["product_concept"],
        "product_format": brief["product_format"], "transformation": transformation,
        "promise": brief.get("product_promise", ""), "target_customer": brief.get("target_customer", ""),
        "price_range": brief.get("price_range", "Unknown"),
        "price_rationale": brief.get("price_rationale", ""),
        "confidence": brief.get("confidence", "UNKNOWN"),
        "jobs_to_be_done": jobs, "differentiation": brief.get("differentiation", []),
        "exclusions": brief.get("exclude", []),
    }
    files = {
        "product_spec": _write(opp_id, "product_spec", product_spec),
        "product_architecture": _write(opp_id, "product_architecture",
                                        {"opportunity_id": opp_id, "components": components}),
        "component_specs": _write(opp_id, "component_specs", {"specs": comp_specs}),
        "asset_requirements": _write(opp_id, "asset_requirements", {"assets": assets}),
        "quality_requirements": _write(opp_id, "quality_requirements", quality),
        "production_plan": _write(opp_id, "production_plan", plan),
        "curation_dossier": _write(opp_id, "curation_dossier", dossier),
    }
    return {"opportunity_id": opp_id, "curation_status": "complete",
            "counts": {"components": len(components), "assets": len(assets),
                       "verification_required": len(dossier["verification_requirements"]),
                       "unresolved": len(dossier["unresolved_questions"])},
            "files": files, "dossier": dossier}
