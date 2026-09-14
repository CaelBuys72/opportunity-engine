"""Build 6 — Product Production Engine.

Manufactures REAL files from a completed Phase-9 spec. Consumes the spec, does
not redesign it. Orchestration is separate from format builders (app/builders.py).

Gates: promotion + research_complete + curation_complete + human build approval
(product_build_status == 'approved_to_build') + Phase-9 files present. External-
verification-flagged components may be drafted but never enter release. PDF (or any
format the environment can't render) is marked BLOCKED, never faked — a required
format that can't be produced keeps release BLOCKED. No placeholder/unsupported
content; scores never become product claims. Product lives only under
products/<opp-id>/; upstream research/spec files are never mutated.
"""
from __future__ import annotations
import hashlib
import json
import re
import shutil
from pathlib import Path

import builders as B
from universe import UniverseService

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "research"
PRODUCTS = ROOT / "products"
STATES_FILE = ROOT / "data" / "universe" / "pipeline_states.json"

FORBIDDEN = re.compile(r"\b(TODO|TBD|PLACEHOLDER|LOREM IPSUM|INSERT HERE|EXAMPLE TEXT)\b"
                       r"|\[(write|add|insert|todo|fill in later|complete)\b[^\]]*\]", re.I)
ENGINE_LEAK = re.compile(r"\b(prb-|opp-|aud-|src-|source_ref|evidence_count|basis|inferred|"
                         r"priority_score|commercial_score|scoring_version)\b")


class ProductionError(Exception):
    pass


# ---------------------------------------------------------------- state helpers (reuse pipeline states)
def _load_states() -> dict:
    import storage
    rows = storage.get_backend().read_doc("pipeline_states") or []
    return {s["opportunity_id"]: s for s in rows}


def _save_states(states: dict) -> None:
    import storage
    storage.get_backend().write_doc("pipeline_states", list(states.values()))


def _set_build_status(opp_id: str, status: str) -> None:
    states = _load_states()
    if opp_id in states:
        states[opp_id]["product_build_status"] = status
        _save_states(states)


# ---------------------------------------------------------------- spec loading + gate
def _load_spec(opp_id: str) -> dict:
    import storage
    backend = storage.get_backend()
    need = ["product_brief", "product_architecture", "component_specs",
            "asset_requirements", "quality_requirements", "production_plan", "curation_dossier"]
    out = {}
    for n in need:
        obj = backend.read_dossier_file(opp_id, n)
        if obj is None:
            raise ProductionError(f"missing Phase-9 spec file '{n}' — curate the product first.")
        out[n] = obj
    # evidence + brief power real content generation; evidence is optional
    out["evidence"] = backend.read_dossier_file(opp_id, "evidence") or {}
    return out


def validate_build_gate(opp_id: str, for_approval: bool = False) -> dict:
    svc = UniverseService()
    if not svc.get_opportunity(opp_id):
        raise ProductionError(f"no opportunity '{opp_id}'")
    st = _load_states().get(opp_id)
    if not st:
        raise ProductionError(f"'{opp_id}' not promoted (no pipeline state).")
    if st.get("research_status") != "complete":
        raise ProductionError(f"gate: research_status is '{st.get('research_status')}' (need complete).")
    if st.get("curation_status") != "complete":
        raise ProductionError(f"gate: curation_status is '{st.get('curation_status')}' (need complete).")
    if not for_approval and st.get("product_build_status") not in ("approved_to_build", "building", "blocked", "qa", "release_candidate", "approved"):
        raise ProductionError("gate: human build approval required — run approve_product_build.py first.")
    return st


def approve_build(opp_id: str) -> dict:
    validate_build_gate(opp_id, for_approval=True)
    _set_build_status(opp_id, "approved_to_build")
    return {"opportunity_id": opp_id, "product_build_status": "approved_to_build"}


# ---------------------------------------------------------------- format requirements
def _required_formats(deliverable: str, comp_type: str) -> set[str]:
    d = deliverable.lower()
    if "spreadsheet" in d:
        return {"xlsx", "csv"}
    if "or fillable template" in d:
        return {"docx"}
    if "fillable pdf" in d or "short pdf" in d:
        return {"docx"}   # no-PDF build: deliver an editable DOCX (user can export to PDF)
    if "supporting file" in d:
        return {"md"} if comp_type == "bonus" else {"docx"}
    return {"docx"}


def _spec_hash(spec_entry: dict) -> str:
    return hashlib.sha256(json.dumps(spec_entry, sort_keys=True).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- content (real, honest, operational)
def _content(cid: str, name: str, prop="[Property Name]") -> dict:
    """Returns {kind, title, blocks?, sheet?, csv?}. Operational template content —
    intentional [fields] for the buyer are allowed; no production placeholders."""
    T = name
    if cid == "cmp-1":  # Supply restock tracker (xlsx)
        hdr = ["Property", "Category", "Item", "Storage Location", "Current Qty", "Minimum Qty",
               "Reorder Qty", "Reorder Status", "Last Restocked", "Notes"]
        exrows = [["Beach House", "Bathroom", "Toilet paper", "Hall closet", 4, 8, 12, "", "2026-09-01", "bulk from Costco"],
                  ["Beach House", "Consumables", "Coffee pods", "Kitchen cupboard", 25, 20, 20, "", "2026-09-05", ""],
                  ["Beach House", "Bathroom", "Hand soap refill", "Under sink", 1, 4, 6, "", "", ""],
                  ["Beach House", "Consumables", "Trash bags", "Pantry", 0, 2, 4, "", "", ""]]
        return {"kind": "xlsx", "title": T, "sheet": {
            "name": "Supply + Inventory Tracker",
            "instructions": "One row per item. Enter Current Qty, Minimum Qty and (optionally) Reorder Qty. "
                            "Reorder Status auto-flags 'REORDER' when Current drops to or below Minimum. "
                            "Rows below are examples — replace them with your own.",
            "headers": hdr, "rows": exrows,
            "formulas": {8: '=IF(AND(E{row}<>"",F{row}<>""),IF(E{row}<=F{row},"REORDER","OK"),"")'}},
            "csv_headers": hdr, "csv_rows": exrows[:2]}
    if cid == "cmp-7":  # one-page quick checklist (distinct from the detailed cmp-2)
        return {"kind": "docx", "title": f"Quick Turnover Checklist — {prop}", "blocks": [
            {"type": "para", "text": "Print this and keep it by the door. It's the field version of the "
                                     "Master Turnover SOP — for the full detail and standards, see the SOP."},
            {"type": "field", "label": "Cleaner"}, {"type": "field", "label": "Date"},
            {"type": "heading", "text": "Every turnover"},
            {"type": "check", "items": ["Strip & remake all beds with fresh linen",
                "Bathrooms — toilet, shower, mirror; restock toilet paper & towels",
                "Kitchen — counters, sink, fridge cleared, dishes done",
                "Living areas — dust, vacuum, mop, reset furniture",
                "Restock consumables (check the Supply Restock Tracker)",
                "Empty all bins", "Lights off · thermostat set · doors locked · lockbox reset",
                "Photograph any damage, then mark the listing ready"]}]}
    if cid == "cmp-2":  # Master Turnover SOP (merges old detailed checklist + step-by-step)
        return {"kind": "docx", "title": f"Master Turnover SOP — {prop}", "blocks": [
            {"type": "para", "text": "Your end-to-end standard for turning the property around between guests — "
                                     "use it to train, stay consistent, and set the bar for cleaners. The one-page "
                                     "Quick Turnover Checklist is the field version of this SOP."},
            {"type": "heading", "text": "1. Before arrival"},
            {"type": "bullet", "items": ["Confirm checkout time and that guests have departed",
                "Check the next booking and any special requests", "Bring linens, supplies and the quick checklist"]},
            {"type": "heading", "text": "2. Entry & first walkthrough"},
            {"type": "bullet", "items": ["Open blinds/windows for airflow",
                "Walk every room; note damage or lost-and-found (record it in the Damage & Incident Log)",
                "Start laundry first so it runs while you clean"]},
            {"type": "heading", "text": "3. Bedrooms"},
            {"type": "check", "items": ["Strip & remake beds with fresh linen", "Fresh pillowcases",
                "Check under beds & nightstands", "Tidy wardrobe & hangers"]},
            {"type": "heading", "text": "4. Bathrooms"},
            {"type": "check", "items": ["Disinfect toilet", "Clean shower/tub & glass", "Clean mirrors",
                "Restock toilet paper & fresh towels", "Empty bins"]},
            {"type": "heading", "text": "5. Kitchen"},
            {"type": "check", "items": ["Wipe counters & backsplash", "Clean sink & taps",
                "Clear fridge of guest leftovers", "Run/empty dishwasher", "Confirm utensil & crockery count"]},
            {"type": "heading", "text": "6. Living areas & floors"},
            {"type": "check", "items": ["Dust surfaces", "Reset furniture & cushions",
                "Check remotes & batteries", "Vacuum then mop — floors last"]},
            {"type": "heading", "text": "7. Supplies"},
            {"type": "para", "text": "Restock consumables and update the Supply + Inventory Tracker — reorder "
                                     "anything the tracker flags."},
            {"type": "heading", "text": "8. Damage check"},
            {"type": "para", "text": "Photograph any damage or missing items and record it in the Damage & "
                                     "Incident Log with severity and the action you took."},
            {"type": "heading", "text": "9. Final inspection — the guest-ready standard"},
            {"type": "check", "items": ["Every room looks like the listing photos",
                "No guest traces (hair, crumbs, bins)", "Lights off · thermostat set · windows & doors locked",
                "Keys / lockbox reset", "Welcome Guide visible and correct"]},
            {"type": "heading", "text": "10. Issue escalation"},
            {"type": "bullet", "items": ["Minor (low supplies, small wear): note it and continue",
                "Moderate (stain, broken small item): log it and message the host",
                "Urgent (leak, safety, major damage): stop and call the host immediately (see the Cleaner Handoff Sheet)"]},
            {"type": "heading", "text": "11. Completion handoff"},
            {"type": "para", "text": "Complete the Cleaner Handoff Sheet, note anything to reorder, and mark the listing ready."}]}
    if cid == "cmp-3":  # Property Setup Workbook (host-facing source of truth; absorbs old cmp-6)
        return {"kind": "docx", "title": f"Property Setup Workbook — {prop}", "blocks": [
            {"type": "para", "text": "Fill this in once per property — it's your single source of truth. "
                                     "Everything a guest might ask lives here, so you never answer the same "
                                     "question twice. The polished, guest-facing 'Welcome Guide' is built from this."},
            {"type": "heading", "text": "WiFi"},
            {"type": "field", "label": "Network name"}, {"type": "field", "label": "Password"},
            {"type": "heading", "text": "Check-in & check-out"},
            {"type": "field", "label": "Check-in time"}, {"type": "field", "label": "Check-out time"},
            {"type": "field", "label": "Entry / lockbox instructions"},
            {"type": "heading", "text": "Appliances (how each works)"},
            {"type": "field", "label": "Coffee machine"}, {"type": "field", "label": "Thermostat / heating"},
            {"type": "field", "label": "Washer / dryer"},
            {"type": "heading", "text": "Trash & recycling"},
            {"type": "field", "label": "Collection day & bin location"},
            {"type": "heading", "text": "House rules"},
            {"type": "field", "label": "Max guests"}, {"type": "field", "label": "Quiet hours"},
            {"type": "heading", "text": "Sections hosts most often forget"},
            {"type": "field", "label": "Parking / permits"},
            {"type": "field", "label": "Quirks & what NOT to touch (e.g. that one switch)"},
            {"type": "field", "label": "Heating/AC controls in plain language"},
            {"type": "field", "label": "Nearby essentials (pharmacy, grocery, ATM)"},
            {"type": "heading", "text": "Emergency & contact"},
            {"type": "field", "label": "Host phone"}, {"type": "field", "label": "Local emergency number"},
            {"type": "field", "label": "Nearest pharmacy / hospital"}]}
    if cid == "cmp-8":  # GUEST-facing polished welcome manual
        return {"kind": "docx", "title": f"Welcome to {prop}", "blocks": [
            {"type": "para", "text": "We're so glad you're here — here's everything you need for a comfortable stay."},
            {"type": "heading", "text": "Getting connected"},
            {"type": "field", "label": "WiFi network"}, {"type": "field", "label": "WiFi password"},
            {"type": "heading", "text": "Making yourself at home"},
            {"type": "bullet", "items": ["Coffee & tea are in the kitchen — help yourself",
                "Extra towels & linens: [location]", "Heating / AC: [simple instruction]"]},
            {"type": "heading", "text": "A few house rules"},
            {"type": "bullet", "items": ["No smoking indoors, please", "Quiet hours [10pm–8am]",
                "Please treat the space like your own home"]},
            {"type": "heading", "text": "Explore nearby"},
            {"type": "bullet", "items": ["Our favourite coffee: [place]", "Great dinner nearby: [place]",
                "Closest grocery: [place]"]},
            {"type": "heading", "text": "Checking out"},
            {"type": "field", "label": "Check-out time"},
            {"type": "para", "text": "On your way out: please start the dishwasher, bag the trash, and pop the "
                                     "keys back in the lockbox. That's it!"},
            {"type": "heading", "text": "Need anything?"},
            {"type": "field", "label": "Host name & phone"},
            {"type": "para", "text": "Message us anytime — we're happy to help make your stay great."}]}
    if cid == "cmp-4":  # cleaner handoff sheet (pdf-required -> docx master)
        return {"kind": "docx", "title": "Cleaner Handoff Sheet", "blocks": [
            {"type": "field", "label": "Date"}, {"type": "field", "label": "Cleaner name"},
            {"type": "field", "label": "Property / unit"}, {"type": "field", "label": "Time started"},
            {"type": "field", "label": "Time finished"},
            {"type": "heading", "text": "Confirmed complete"},
            {"type": "check", "items": ["All rooms cleaned", "All linens changed", "Consumables restocked",
                "Damage / issues checked"]},
            {"type": "heading", "text": "Issues found / photos taken"},
            {"type": "para", "text": "________________________________________________"},
            {"type": "para", "text": "________________________________________________"},
            {"type": "heading", "text": "Items to reorder"},
            {"type": "para", "text": "________________________________________________"},
            {"type": "field", "label": "Cleaner signature"}]}
    if cid == "cmp-5":  # turnover step-by-step (pdf-required -> docx master)
        return {"kind": "docx", "title": "Turnover: Step-by-Step", "blocks": [
            {"type": "number", "items": ["Confirm checkout and that guests have departed.",
                "Initial walkthrough — note any damage or lost-and-found items.",
                "Strip all linens and start laundry first.", "Reset the kitchen.",
                "Clean bathrooms.", "Make up bedrooms and reset living areas.",
                "Restock consumables using the Supply Restock Tracker.",
                "Do floors last — vacuum then mop.",
                "Final checks: locks, thermostat, lights, keys/lockbox.",
                "Photograph the finished space and mark the listing ready."]}]}
    if cid == "cmp-6":  # house-manual sections hosts forget (pdf-required -> docx master)
        return {"kind": "docx", "title": "House-Manual Sections Hosts Forget", "blocks": [
            {"type": "bullet", "items": ["WiFi network & password in large, easy-to-read text",
                "Trash & recycling day and exact bin location", "Parking specifics and permits",
                "Quirky appliance instructions (that one tricky switch)",
                "Heating / air-conditioning controls", "Clear check-out steps",
                "Emergency number and how to reach the host", "Nearby essentials: pharmacy, grocery, ATM",
                "Quiet hours and noise expectations", "Anything guests should NOT touch or do"]}]}
    if cid == "cmp-9":  # guest message snippets (bonus -> md)
        return {"kind": "md", "title": "Guest Message Snippets", "blocks": [
            {"type": "heading", "text": "Booking confirmation"},
            {"type": "para", "text": "Hi [Guest], thanks for booking [Property]! I'll send check-in details "
                                     "the day before arrival. Any questions in the meantime, just message me."},
            {"type": "heading", "text": "Pre-arrival (day before)"},
            {"type": "para", "text": "Hi [Guest], you're all set for tomorrow. Check-in is from [time]. "
                                     "Address: [address]. WiFi and the full house manual are inside. Safe travels!"},
            {"type": "heading", "text": "Check-in day"},
            {"type": "para", "text": "Welcome! Entry: [lockbox/instructions]. The house manual is on the "
                                     "[counter/table]. Message me anytime."},
            {"type": "heading", "text": "Check-out reminder"},
            {"type": "para", "text": "Hi [Guest], hope you enjoyed your stay! Check-out is [time]. Before you go: "
                                     "start the dishwasher, bag the trash, and leave the keys in the lockbox. Thank you!"},
            {"type": "heading", "text": "Review request"},
            {"type": "para", "text": "It was a pleasure hosting you, [Guest]! If you have a moment, a quick review "
                                     "really helps. Hope to host you again."},
            {"type": "heading", "text": "Something went wrong (issue resolution)"},
            {"type": "para", "text": "Hi [Guest], I'm so sorry about [issue] — thank you for flagging it. "
                                     "Here's what I'm doing right now: [action]. Please bear with me and let me "
                                     "know if there's anything else I can do to make your stay comfortable."},
            {"type": "heading", "text": "Late check-out request"},
            {"type": "para", "text": "Hi [Guest], I can offer a late check-out until [time] for [fee/complimentary]. "
                                     "Just confirm and I'll update the cleaning schedule. Enjoy the extra time!"}]}
    if cid == "cmp-10":  # Damage & Incident Log (spreadsheet)
        hdr = ["Property", "Date", "Area / Room", "Issue", "Severity", "Reported / Discovered By",
               "Description", "Action Taken", "Status", "Follow-Up Needed", "Reference / Photo Link", "Notes"]
        exrows = [["Beach House", "2026-09-06", "Bathroom", "Cracked shower glass", "Moderate", "Cleaner",
                   "Hairline crack lower left panel", "Photographed; messaged host", "Open", "Get quote", "", ""],
                  ["Beach House", "2026-09-06", "Kitchen", "Missing wine glasses (2)", "Minor", "Cleaner",
                   "2 of 6 missing after checkout", "Noted; replace from spares", "Resolved", "No", "", "from spares"]]
        return {"kind": "xlsx", "title": T, "sheet": {
            "name": "Damage + Incident Log",
            "instructions": "Log anything that goes wrong: one row per issue. Use Severity (Minor / Moderate / "
                            "Urgent) and Status (Open / In progress / Resolved). Rows below are examples.",
            "headers": hdr, "rows": exrows},
            "csv_headers": hdr, "csv_rows": exrows}
    # fallback
    return {"kind": "docx", "title": T, "blocks": [{"type": "para", "text": name}]}


def _generate_content(opp_id: str, comp: dict, cspec: dict, deliverable: str,
                      required: set, spec: dict, creds: dict | None) -> dict:
    """LLM-generate real, buyer-ready content for one component, shaped for the
    format builders. Works for ANY opportunity (no hardcoded templates). Raises on
    failure so the component is honestly marked failed rather than stubbed."""
    import research_engine as RE
    clf = RE.get_classifier(creds, layer="product")
    if clf is None:
        raise ProductionError("no LLM credential available to generate product content "
                              "(operator needs a Gemini key)")
    brief = spec.get("product_brief", {}) or {}
    dossier = spec.get("curation_dossier", {}) or {}
    transformation = dossier.get("transformation", {}) or {}
    ev = spec.get("evidence", {}) or {}
    claims = ev.get("claims", []) if isinstance(ev, dict) else []
    ev_lines = [c.get("claim") for c in claims[:8] if isinstance(c, dict) and c.get("claim")]

    is_sheet = bool({"xlsx", "csv"} & set(required))
    kind = "xlsx" if is_sheet else "docx"
    context = {
        "product_concept": brief.get("product_concept") or dossier.get("product_concept"),
        "buyer": brief.get("target_customer") or brief.get("audience"),
        "transformation": f"{transformation.get('from_state', '')} -> {transformation.get('to_state', '')}",
        "component_name": comp.get("name"),
        "component_purpose": comp.get("purpose", "") or cspec.get("purpose", ""),
        "deliverable": deliverable,
        "jobs": comp.get("maps_to_jobs", []) or cspec.get("maps_to_jobs", []),
        "evidence_highlights": ev_lines,
    }
    rules = ("Write REAL, specific, immediately-usable content for the buyer described. "
             "Be concrete and practical, grounded in the buyer's world and the evidence highlights. "
             "Buyer-fillable blanks in [square brackets] are allowed (e.g. [Your business name]). "
             "NEVER output unfinished placeholders like [write here], [insert], TODO, TBD, lorem ipsum "
             "or 'example text'. NEVER mention internal ids, scores, 'basis', 'evidence' or any "
             "engine/analysis terminology. Return STRICT JSON only, no prose around it.")
    if kind == "xlsx":
        system = ("You manufacture a working spreadsheet template. " + rules +
                  ' Output schema: {"title": str, "sheet": {"name": str (<=31 chars), '
                  '"instructions": str, "headers": [str,...], "rows": [[cell,...], ...]}}. '
                  "6-14 columns and 3-6 realistic example rows the buyer can replace.")
    else:
        system = ("You manufacture a polished, finished document. " + rules +
                  ' Output schema: {"title": str, "blocks": [ {"type":"heading","text":str} | '
                  '{"type":"para","text":str} | {"type":"bullet","items":[str,...]} | '
                  '{"type":"check","items":[str,...]} | {"type":"field","label":str} ]}. '
                  "Produce a complete, well-structured document (headings, guidance, checklists/bullets "
                  "where useful) — genuinely valuable on its own.")
    user = json.dumps(context, ensure_ascii=False)

    def _gen(sys_prompt):
        d = RE._extract_json(clf.classify(sys_prompt, user))
        if isinstance(d, list) and d:          # model wrapped the object in an array
            d = next((x for x in d if isinstance(x, dict)), None)
        return d

    data = _gen(system)
    if not isinstance(data, dict):
        data = _gen(system + " Return a SINGLE JSON object (not an array), valid JSON only.")
    if not isinstance(data, dict):
        raise ProductionError(f"content generation returned invalid JSON for '{comp.get('name')}'")

    title = data.get("title") or comp.get("name") or "Product"
    if kind == "xlsx":
        sheet = data.get("sheet") or {}
        headers = sheet.get("headers") or []
        rows = sheet.get("rows") or []
        if not headers:
            raise ProductionError(f"generated spreadsheet for '{comp.get('name')}' has no columns")
        sheet.setdefault("name", title[:31]); sheet.setdefault("instructions", "")
        sheet["headers"], sheet["rows"] = headers, rows
        return {"kind": "xlsx", "title": title, "sheet": sheet,
                "csv_headers": headers, "csv_rows": rows}
    blocks = data.get("blocks") or []
    if not blocks:
        raise ProductionError(f"generated document for '{comp.get('name')}' has no content")
    return {"kind": "docx", "title": title, "blocks": blocks}


# ---------------------------------------------------------------- component build
def _produce_formats(cdir: Path, content: dict, required: set[str]) -> tuple[list[str], list[dict]]:
    files, blocked = [], []
    stem = "artifact"
    # xlsx + csv
    if "xlsx" in required:
        p = B.build_xlsx(cdir / f"{stem}.xlsx", [content["sheet"]])
        files.append(str(p.relative_to(PRODUCTS)))
    if "csv" in required:
        p = B.build_csv(cdir / f"{stem}.csv", content["csv_headers"], content["csv_rows"])
        files.append(str(p.relative_to(PRODUCTS)))
    if "md" in required:
        p = B.build_markdown(cdir / f"{stem}.md", content["title"], content["blocks"])
        files.append(str(p.relative_to(PRODUCTS)))
    if "docx" in required:
        p = B.build_docx(cdir / f"{stem}.docx", content["title"], content["blocks"])
        files.append(str(p.relative_to(PRODUCTS)))
    if "pdf" in required:
        # render the REAL PDF directly from content; also keep an editable DOCX master
        master = B.build_docx(cdir / f"{stem}.docx", content["title"], content["blocks"])
        files.append(str(master.relative_to(PRODUCTS)))
        pdf, tool = B.build_pdf(cdir / f"{stem}.pdf", content["title"], content["blocks"])
        if pdf:
            files.append(str(pdf.relative_to(PRODUCTS)))
        else:
            blocked.append({"format": "pdf", "reason": tool,
                            "note": "DOCX master produced; PDF consumable pending a real renderer."})
    return files, blocked


def _qa_component(cdir: Path, content: dict, required: set[str], files: list[str]) -> dict:
    structural, contentq = [], []
    produced_formats = {Path(f).suffix.lstrip(".") for f in files}
    for fmt in required:
        if fmt not in produced_formats:
            structural.append(f"required format '{fmt}' not produced")
    for f in files:
        p = PRODUCTS / f
        suf = p.suffix.lower()
        if suf == ".xlsx":
            structural += B.validate_xlsx(p, [content["sheet"]["name"]] if content.get("sheet") else None)
        elif suf == ".docx":
            structural += B.validate_docx(p)
        elif suf == ".pdf":
            structural += B.validate_pdf(p)
        # content QA on text-readable files
        text = ""
        if suf in (".md", ".csv"):
            text = p.read_text(errors="ignore")
        elif suf == ".docx":
            from docx import Document
            text = "\n".join(pp.text for pp in [Document(p)] for pp in [] ) or \
                   "\n".join(par.text for par in Document(p).paragraphs)
        if text:
            if FORBIDDEN.search(text):
                contentq.append(f"{f}: forbidden placeholder/unfinished content")
            if ENGINE_LEAK.search(text):
                contentq.append(f"{f}: internal engine terminology leaked to buyer")
    return {"structural": structural, "content": contentq,
            "qa_status": "passed" if not structural and not contentq else "failed"}


def _qa_text_blocks(blocks: list) -> dict:
    """Content QA for document components that go into the ebook (no file yet)."""
    parts = []
    for b in blocks or []:
        parts.append(b.get("text", "")); parts.append(b.get("label", ""))
        parts.extend(str(x) for x in (b.get("items", []) or []))
    text = "\n".join(p for p in parts if p)
    issues = []
    if not text.strip():
        issues.append("empty document content")
    if FORBIDDEN.search(text):
        issues.append("forbidden placeholder/unfinished content")
    if ENGINE_LEAK.search(text):
        issues.append("internal engine terminology leaked to buyer")
    return {"structural": [], "content": issues, "qa_status": "passed" if not issues else "failed"}


# ---------------------------------------------------------------- orchestrator
def _dep_order(plan: dict, arch: dict) -> list[str]:
    seq = [s for s in plan["sequence"] if s.get("component_id")]
    order = [s["component_id"] for s in sorted(seq, key=lambda s: s["order"])]
    valid = {c["id"] for c in arch["components"]}
    for s in seq:  # validate refs + deps
        if s["component_id"] not in valid:
            raise ProductionError(f"production_plan references unknown component {s['component_id']}")
        for d in s.get("depends_on", []):
            if isinstance(d, int) and d > len(plan["sequence"]):
                raise ProductionError(f"invalid dependency index {d}")
    return order


def build_product(opp_id: str, creds: dict | None = None, operator: str = "unknown",
                  only_component: str | None = None, force: bool = False) -> dict:
    validate_build_gate(opp_id)
    import research_engine as _RE
    _tok0 = _RE.llm_tokens_used(operator)
    spec = _load_spec(opp_id)
    _set_build_status(opp_id, "building")
    pdir = PRODUCTS / opp_id
    (pdir / "components").mkdir(parents=True, exist_ok=True)
    (pdir / "qa").mkdir(parents=True, exist_ok=True)

    arch = spec["product_architecture"]
    comps = {c["id"]: c for c in arch["components"]}
    cspecs = {c["component_id"]: c for c in spec["component_specs"]["specs"]}
    assets = {a["component_id"]: a for a in spec["asset_requirements"]["assets"]}
    order = _dep_order(spec["production_plan"], arch)

    manifest_path = pdir / "manifest.json"
    prev = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    prev_comps = {c["component_id"]: c for c in prev["components"]} if prev else {}

    manifest_components, traceability = [], []
    for cid in order:
        if only_component and cid != only_component:
            if cid in prev_comps:            # keep previously built component untouched
                manifest_components.append(prev_comps[cid])
            continue
        comp = comps[cid]
        cspec = cspecs.get(cid, {})
        deliverable = assets.get(cid, {}).get("deliverable", "")
        required = _required_formats(deliverable, comp["type"])
        verify = bool(cspec.get("requires_external_verification"))
        shash = _spec_hash(cspec)
        cdir = pdir / "components" / cid

        # resumable: skip if already built with same spec hash, files present, and (for
        # ebook chapters) the generated content.json still on disk. Unless --force.
        prevc = prev_comps.get(cid)
        content_ok = (pdir / "components" / cid / "content.json").exists() \
            if (prevc and prevc.get("role") == "chapter") else True
        if (not force and prevc and prevc.get("spec_hash") == shash
                and prevc.get("production_status") == "built" and content_ok
                and all((PRODUCTS / f).exists() for f in prevc.get("files", []))):
            manifest_components.append(prevc)
            continue

        if cdir.exists():
            shutil.rmtree(cdir)
        cdir.mkdir(parents=True, exist_ok=True)
        role = "tool" if bool({"xlsx", "csv"} & set(required)) else "chapter"
        try:
            content = _generate_content(opp_id, comp, cspec, deliverable, required, spec, creds)
            (cdir / "content.json").write_text(json.dumps(content, ensure_ascii=False))
            if role == "tool":
                # spreadsheets/trackers stay as separate editable files
                files, blocked = _produce_formats(cdir, content, required & {"xlsx", "csv"})
                qa = _qa_component(cdir, content, required & {"xlsx", "csv"}, files)
            else:
                # document components become chapters in the combined ebook — QA the text now
                files, blocked = [], []
                qa = _qa_text_blocks(content.get("blocks", []))
            status = "qa_failed" if qa["qa_status"] == "failed" else ("format_blocked" if blocked else "built")
        except Exception as e:
            files, blocked, qa, status = [], [], {"structural": [f"builder crashed: {e}"],
                                                  "content": [], "qa_status": "failed"}, "failed"

        manifest_components.append({
            "component_id": cid, "name": comp["name"], "type": comp["type"], "role": role,
            "purpose": comp.get("purpose", ""), "required_formats": sorted(required),
            "verification_required": verify,
            "verification_status": "pending" if verify else "not_required",
            "spec_hash": shash, "files": files, "blocked_formats": blocked,
            "production_status": status, "qa_status": qa["qa_status"],
            "qa_detail": qa})
        traceability.append({"component_id": cid, "based_on": "phase9 component_spec + product_brief",
                             "basis": "observed" if opp_id in json.dumps(spec["product_brief"]) else "inferred"})

    # release gate
    all_built = all(c["production_status"] == "built" for c in manifest_components)
    verif_pending = any(c["verification_status"] == "pending" for c in manifest_components)
    qa_ok = all(c["qa_status"] == "passed" for c in manifest_components)
    blocked_reasons = []
    for c in manifest_components:
        if c["production_status"] != "built":
            blocked_reasons.append(f"{c['component_id']}: {c['production_status']}"
                                   + (f" ({c['blocked_formats'][0]['format']})" if c["blocked_formats"] else ""))
    if verif_pending:
        blocked_reasons.append("external verification pending")

    bundle_status, release_status = _assemble_bundle(pdir, manifest_components, spec, creds=creds)
    if all_built and qa_ok and not verif_pending and bundle_status == "complete":
        release_status = "release_candidate"
    else:
        release_status = "blocked"

    manifest = {
        "opportunity_id": opp_id, "product_name": spec["product_brief"].get("product_concept", opp_id)[:80],
        "product_status": "release_candidate" if release_status == "release_candidate" else "blocked",
        "spec_source": f"research/{opp_id}/", "components": manifest_components,
        "bundle_status": bundle_status, "release_status": release_status,
        "release_blocked_reasons": blocked_reasons,
        "llm_tokens_used": _RE.llm_tokens_used(operator) - _tok0,
        "capabilities": {"pdf": B.pdf_available()[1]},
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    (pdir / "qa" / "source_traceability.json").write_text(json.dumps(traceability, indent=2, ensure_ascii=False))
    (pdir / "production_state.json").write_text(json.dumps(
        {"opportunity_id": opp_id, "release_status": release_status, "bundle_status": bundle_status,
         "components": {c["component_id"]: c["production_status"] for c in manifest_components}}, indent=2))

    # persist to shared object storage so the bundle + manifest survive restarts and
    # are downloadable by either operator (Render's local disk is ephemeral).
    import io, zipfile
    import storage as _S
    backend = _S.get_backend()
    bdir = pdir / "bundle"
    bundle_key = None
    if bdir.exists() and any(p.is_file() for p in bdir.rglob("*")):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(bdir.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(bdir))
        bundle_key = f"{opp_id}/product_bundle.zip"
        backend.put_object(bundle_key, buf.getvalue(), "application/zip")
    manifest["bundle_key"] = bundle_key
    manifest["download_ready"] = bool(bundle_key)
    manifest["built_by"] = operator
    backend.write_dossier_file(opp_id, "product_manifest", manifest)

    _set_build_status(opp_id, "release_candidate" if release_status == "release_candidate" else "blocked")
    return manifest


def get_manifest(opp_id: str) -> dict | None:
    """Read the persisted product manifest (shared storage)."""
    import storage
    return storage.get_backend().read_dossier_file(opp_id, "product_manifest")


def get_bundle(opp_id: str) -> bytes | None:
    """Fetch the produced product bundle ZIP from shared storage."""
    import storage
    m = get_manifest(opp_id) or {}
    key = m.get("bundle_key") or f"{opp_id}/product_bundle.zip"
    return storage.get_backend().get_object(key)


def _cover_prompt(title: str, transformation: dict) -> str:
    return ("Professional ebook cover background art, modern and clean, abstract and "
            f"tasteful, evoking: {title}. Calm premium colour palette, soft depth, "
            "subtle gradient, plenty of empty space at the top for a title. "
            "NO text, NO words, NO letters, NO logos.")


def _assemble_bundle(pdir: Path, components: list[dict], spec: dict,
                     creds: dict | None = None) -> tuple[str, str]:
    """One sellable ebook PDF (document components as chapters, with an optional
    AI cover) + editable tool files (spreadsheets) + a short START_HERE."""
    bdir = pdir / "bundle"
    if bdir.exists():
        shutil.rmtree(bdir)
    bdir.mkdir(parents=True, exist_ok=True)
    brief = spec.get("product_brief", {}) or {}
    dossier = spec.get("curation_dossier", {}) or {}
    title = brief.get("product_concept") or dossier.get("product_concept") or "Your Product"
    transformation = dossier.get("transformation", {}) or {}
    subtitle = brief.get("product_promise") or transformation.get("to_state") or ""

    chapters, tools, excluded = [], [], []
    for c in components:
        cid = c["component_id"]
        if not (c["production_status"] == "built" and c["qa_status"] == "passed"):
            excluded.append(cid); continue
        if c.get("role") == "tool":
            safe = re.sub(r"[^A-Za-z0-9 _-]+", "-", c.get("name") or cid).strip()[:70]
            for f in c["files"]:
                src = PRODUCTS / f
                dest = bdir / f"{safe}{src.suffix}"
                shutil.copy(src, dest); tools.append(dest.name)
        else:
            cj = pdir / "components" / cid / "content.json"
            if cj.exists():
                data = json.loads(cj.read_text())
                chapters.append({"title": c.get("name") or data.get("title") or cid,
                                 "blocks": data.get("blocks", [])})

    ebook_name = None
    if chapters:
        safe_title = re.sub(r"[^A-Za-z0-9 _-]+", "-", title).strip()[:60] or "Ebook"
        cover = None
        try:
            import research_engine as _RE
            imgp = _RE.get_image_provider(creds)
            if imgp:
                cover = imgp.cover(_cover_prompt(title, transformation))  # None on failure → typographic cover
                if cover is None and getattr(imgp, "last_error", None):
                    (pdir / "qa").mkdir(parents=True, exist_ok=True)
                    (pdir / "qa" / "cover_error.txt").write_text(str(imgp.last_error))
        except Exception as e:
            cover = None
            try:
                (pdir / "qa").mkdir(parents=True, exist_ok=True)
                (pdir / "qa" / "cover_error.txt").write_text(str(e))
            except Exception:
                pass
        try:
            B.build_ebook_pdf(bdir / f"{safe_title}.pdf", title, subtitle, chapters, cover_image=cover)
            ebook_name = f"{safe_title}.pdf"
        except Exception as e:                       # never fake it — surface as no ebook
            ebook_name = None
            (pdir / "qa" / "ebook_error.txt").write_text(str(e))

    blocks = [{"type": "para", "text": f"This kit contains "
               + ("your ebook" if ebook_name else "your files")
               + (f" plus {len(tools)} editable tool file(s)." if tools else ".")}]
    if ebook_name:
        blocks.append({"type": "para", "text": f"Start with **{ebook_name}** — it's the main product."})
    if tools:
        blocks.append({"type": "heading", "text": "Editable tools (open in Excel or Google Sheets)"})
        blocks.append({"type": "bullet", "items": tools})
    B.build_markdown(bdir / "START_HERE.md", "Start Here", blocks)

    has_content = bool(ebook_name or tools)
    status = "complete" if has_content and not excluded else ("partial" if has_content else "empty")
    return status, "blocked"


# ---------------------------------------------------------------- release approval
AUTO_THRESHOLD = 85


def approve_release(opp_id: str, override: bool = False,
                    override_reason: str | None = None,
                    known_limitations: list[str] | None = None) -> dict:
    """Approve a product for sale.

    Normal path: release_status must be 'release_candidate' (acceptance >= threshold).
    Human-override path: a product held at 'revision_required' (acceptance < threshold)
    may be approved ONLY with override=True and an explicit override_reason. The override
    records WHY and the known limitations, and NEVER mutates historical QA — the acceptance
    score and audit decision are preserved exactly as recorded.
    """
    import datetime
    pdir = PRODUCTS / opp_id
    mf = pdir / "manifest.json"
    if not mf.exists():
        raise ProductionError("no product manifest — build first.")
    manifest = json.loads(mf.read_text())
    status = manifest["release_status"]
    acceptance = manifest.get("acceptance_score")

    if status == "release_candidate":
        approval_kind = "approved_automatic"
    elif override:
        if status != "revision_required":
            raise ProductionError(f"cannot override: release_status is '{status}', "
                                  "override is only for a 'revision_required' product.")
        if not override_reason or not override_reason.strip():
            raise ProductionError("override requires an explicit override_reason.")
        approval_kind = "approved_with_override"
    else:
        raise ProductionError(f"cannot approve: release_status is '{status}' "
                              f"(reasons: {manifest.get('release_blocked_reasons')}). "
                              "Approval requires a release_candidate, or an explicit "
                              "human override (override=True, override_reason=...).")

    # never mutate historical QA — only advance the release gate
    manifest["release_status"] = "approved_for_sale"
    manifest["product_status"] = "approved"
    record = {
        "opportunity_id": opp_id,
        "release_approval": approval_kind,
        "acceptance_score": acceptance,
        "automatic_threshold": AUTO_THRESHOLD,
        "override": approval_kind == "approved_with_override",
        "approved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if approval_kind == "approved_with_override":
        record["override_reason"] = override_reason.strip()
        record["known_limitations"] = known_limitations or []
        record["preserved_qa"] = {
            "note": "Historical QA is NOT altered by this override. The audit still records "
                    f"acceptance_score={acceptance} and decision=revision_required.",
            "acceptance_audit": "qa/product_acceptance.json",
        }
    manifest["release_approval"] = record
    mf.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    (pdir / "qa" / "release_override.json").write_text(json.dumps(record, indent=2, ensure_ascii=False))
    _set_build_status(opp_id, "approved")
    return record


# ---------------------------------------------------------------- product service
class ProductService:
    def __init__(self, opp_id: str):
        self.opp_id = opp_id
        self.dir = PRODUCTS / opp_id
        self.manifest = json.loads((self.dir / "manifest.json").read_text()) if (self.dir / "manifest.json").exists() else None

    def get_product_manifest(self): return self.manifest
    def get_production_state(self):
        f = self.dir / "production_state.json"
        return json.loads(f.read_text()) if f.exists() else None
    def components_for_product(self): return self.manifest["components"] if self.manifest else []
    def blocked_components(self): return [c for c in self.components_for_product()
                                          if c["production_status"] != "built"]
    def qa_failures(self): return [c for c in self.components_for_product() if c["qa_status"] == "failed"]
    def release_ready(self): return bool(self.manifest and self.manifest["release_status"] == "release_candidate")
    def product_files(self): return [f for c in self.components_for_product() for f in c["files"]]


# ---------------------------------------------------------------- validator
class ProductValidationError(Exception):
    pass


def validate_product(opp_id: str) -> dict:
    svc = UniverseService()
    errors = []
    if not svc.get_opportunity(opp_id):
        errors.append("opportunity does not exist")
    st = _load_states().get(opp_id)
    if not st:
        errors.append("no pipeline state")
    else:
        if st.get("research_status") != "complete":
            errors.append("research not complete")
        if st.get("curation_status") != "complete":
            errors.append("curation not complete")
    mf = PRODUCTS / opp_id / "manifest.json"
    if not mf.exists():
        errors.append("no product manifest")
        raise ProductValidationError("\n  - ".join(["product validation:"] + errors))
    manifest = json.loads(mf.read_text())
    if manifest["opportunity_id"] != opp_id:
        errors.append("product identity mismatch")
    arch = json.loads((RESEARCH / opp_id / "product_architecture.json").read_text())
    valid_ids = {c["id"] for c in arch["components"]}
    for c in manifest["components"]:
        if c["component_id"] not in valid_ids:
            errors.append(f"{c['component_id']}: not a valid Phase-9 component")
        if not c.get("spec_hash"):
            errors.append(f"{c['component_id']}: missing spec_hash")
        for f in c["files"]:
            if not (PRODUCTS / f).exists():
                errors.append(f"{c['component_id']}: recorded file missing {f}")
            else:
                suf = Path(f).suffix.lower()
                if suf == ".xlsx" and B.validate_xlsx(PRODUCTS / f):
                    errors.append(f"{c['component_id']}: invalid xlsx")
                if suf == ".docx" and B.validate_docx(PRODUCTS / f):
                    errors.append(f"{c['component_id']}: invalid docx")
        # qa state matches results
        detail = c.get("qa_detail", {})
        expect = "passed" if not detail.get("structural") and not detail.get("content") else "failed"
        if c["qa_status"] != expect:
            errors.append(f"{c['component_id']}: qa_status inconsistent with detail")
        if c["verification_status"] == "pending" and manifest["release_status"] == "release_candidate":
            errors.append(f"{c['component_id']}: pending verification but release_candidate")
    # release candidate only when all built + qa passed + no pending verification
    if manifest["release_status"] == "release_candidate":
        if any(c["production_status"] != "built" or c["qa_status"] != "passed"
               for c in manifest["components"]):
            errors.append("release_candidate with unbuilt/failed components")
    report = {"opportunity_id": opp_id, "errors": errors, "passed": not errors,
              "release_status": manifest["release_status"]}
    if errors:
        raise ProductValidationError(f"{len(errors)} error(s):\n  - " + "\n  - ".join(errors[:25]))
    return report
