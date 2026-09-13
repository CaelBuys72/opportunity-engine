"""Build 2 — Audience -> Raw Problem Discovery.

Discovers recurring problems for an Audience and stores them as first-class
Problem records anchored to `audience_id`. Does NOT cluster into opportunities
(that is Build 3), score commercial attractiveness, or touch products/creators.

Two honest evidence modes:
  A) Manual import  — data/problem_sources/<audience-id>.json  -> `observed`
     problems that trace to real sources.
  B) Seed-inferred  — candidate problems derived from audience context ->
     `basis:"inferred"`, confidence LOW, no source_refs. Never presented as
     observed.

Retrieval is isolated in gather_problem_sources() (the swap-point for future
web/Reddit/API retrieval). Nothing fabricated: no quotes, URLs, frequencies, or
demand invented; unknown stays unknown.
"""
from __future__ import annotations
import json
from pathlib import Path

import universe as U
from universe import UniverseStore, UniverseService

ROOT = Path(__file__).resolve().parent.parent
IMPORT_DIR = ROOT / "data" / "problem_sources"

PROBLEM_TYPES = {
    "knowledge_gap", "workflow_problem", "financial_problem", "time_problem",
    "acquisition_problem", "retention_problem", "operational_problem",
    "technical_problem", "decision_problem", "compliance_problem",
    "emotional_friction", "quality_problem", "communication_problem",
    "planning_problem", "performance_problem",
}
STOPWORDS = {"the", "and", "for", "with", "your", "you", "how", "what", "that",
             "this", "from", "are", "was", "their", "them", "a", "to", "of",
             "in", "on", "my", "i", "when", "dont", "don", "cant", "can", "not",
             "know", "get", "is", "it", "me", "we", "our"}

# keyword -> problem_type (first match wins; order matters)
_CLASSIFY = [
    (("tax", "irs", "legal", "license", "compliance", "regulation", "rules"), "compliance_problem"),
    (("price", "pricing", "charge", "profit", "money", "cost", "income", "expense", "budget", "cashflow", "rate"), "financial_problem"),
    (("tool", "software", "app", "spreadsheet", "formula", "print", "save", "automat", "integration", "setup"), "technical_problem"),
    (("client", "customer", "lead", "booking", "student", "audience", "find", "acqui", "grow"), "acquisition_problem"),
    (("retain", "repeat", "churn", "review", "loyalty", "rebook"), "retention_problem"),
    (("message", "communicat", "respond", "reply", "script", "email"), "communication_problem"),
    (("coordinat", "manage", "schedul", "turnover", "process", "system", "workflow", "onboard"), "workflow_problem"),
    (("plan", "routine", "calendar", "prep"), "planning_problem"),
    (("time", "busy", "hours", "overwhelm", "juggl"), "time_problem"),
    (("scared", "anxious", "anxiety", "stress", "fear", "confidence", "imposter"), "emotional_friction"),
    (("consistent", "quality", "results", "reliable"), "quality_problem"),
    (("decide", "which", "choose", "should i", "unsure", "confus"), "decision_problem"),
    (("optimi", "improve", "rank", "views", "reach", "performance", "conversion"), "performance_problem"),
    (("know", "understand", "learn", "explain", "guide"), "knowledge_gap"),
]


# ---------------------------------------------------------------- stages
def load_audience(audience_id: str, svc: UniverseService) -> dict:
    a = svc._a.get(audience_id)
    if not a:
        raise ValueError(f"No audience '{audience_id}'. Build the universe first "
                         f"(python3 scripts/build_universe.py).")
    return a


def build_problem_search_profile(audience: dict, svc: UniverseService) -> dict:
    m = svc._m.get(audience["market_id"]); s = svc._s.get(audience["submarket_id"])
    base = " ".join(x for x in [m and m["name"], s and s["name"], audience["name"]] if x)
    core = _content_tokens(base)
    templates = ["{x} problems", "{x} struggling", "{x} advice", "{x} mistakes",
                 "{x} questions", "how do I {x}", "{x} frustrations", "{x} tips"]
    topic = (s["name"] if s else audience["name"]).lower()
    return {"audience_id": audience["id"], "topic": topic, "core_terms": sorted(core),
            "queries": [t.format(x=topic) for t in templates]}


def gather_problem_sources(audience_id: str, import_file: str | None) -> tuple[list[dict], list[dict]]:
    """SWAP-POINT for future live retrieval. V0: manual import only.
    Returns (sources, retrieval_notes). No network -> nothing fabricated."""
    f = Path(import_file) if import_file else (IMPORT_DIR / f"{audience_id}.json")
    if not f.exists():
        return [], [{"retriever": "manual-import", "status": "no_data",
                     "note": f"No import at {f}. Use --seed-inferred, or add real sources."}]
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        return [], [{"retriever": "manual-import", "status": "invalid_json", "note": str(e)}]
    srcs = data.get("sources", data if isinstance(data, list) else [])
    return srcs, [{"retriever": "manual-import", "status": "loaded",
                   "count": len(srcs), "source": str(f)}]


def normalize_sources(sources: list[dict], audience_id: str) -> list[dict]:
    out = []
    for i, s in enumerate(sources, 1):
        out.append({
            "source_id": s.get("source_id") or f"src-{audience_id[:24]}-{i}",
            "source_type": s.get("source_type", "other"),
            "url": s.get("url"), "title": s.get("title", ""),
            "text": s.get("text", ""),
            "accessible": s.get("accessible", bool(s.get("url"))),
            "audience_id": audience_id, "basis": s.get("basis", "observed"),
            "retrieval_method": s.get("retrieval_method", "manual-import"),
            "_problems": s.get("problems", []),   # operator/agent-extracted problems this source evidences
        })
    return out


def _content_tokens(text: str) -> set[str]:
    toks = "".join(c.lower() if c.isalnum() else " " for c in (text or "")).split()
    return {t for t in toks if len(t) > 2 and t not in STOPWORDS}


def _normalize_key(statement: str, provided: str | None) -> str:
    if provided:
        return provided.strip().lower()
    toks = [t for t in _content_tokens(statement)]
    return " ".join(sorted(toks)[:4]) or statement.strip().lower()[:40]


def extract_problem_candidates(sources: list[dict], seed_inferred: list[dict]) -> list[dict]:
    cands = []
    # observed candidates from real sources
    for s in sources:
        for p in s["_problems"]:
            cands.append({"statement": p["statement"],
                          "normalized_problem": p.get("normalized_problem")
                              or _normalize_key(p["statement"], None),
                          "desired_outcome": p.get("desired_outcome"),
                          "problem_type": p.get("problem_type"),
                          "basis": "observed", "source_id": s["source_id"]})
    # inferred candidates from seed (no evidence)
    for p in seed_inferred:
        cands.append({"statement": p["statement"],
                      "normalized_problem": p.get("normalized_problem")
                          or _normalize_key(p["statement"], None),
                      "desired_outcome": p.get("desired_outcome"),
                      "problem_type": p.get("problem_type"),
                      "basis": "inferred", "source_id": None})
    return cands


def deduplicate_problem_candidates(cands: list[dict]) -> list[dict]:
    by_key: dict[str, dict] = {}
    for c in cands:
        key = U.slug(c["normalized_problem"])
        if key not in by_key:
            by_key[key] = {"statement": c["statement"], "normalized_problem": c["normalized_problem"],
                           "desired_outcome": c["desired_outcome"], "problem_type": c["problem_type"],
                           "basis": c["basis"], "source_ids": set(), "_key": key}
        g = by_key[key]
        if c["source_id"]:
            g["source_ids"].add(c["source_id"])
        if c["basis"] == "observed":
            g["basis"] = "observed"   # observed dominates inferred on merge
        # prefer a filled desired_outcome / problem_type if this candidate has one
        g["desired_outcome"] = g["desired_outcome"] or c["desired_outcome"]
        g["problem_type"] = g["problem_type"] or c["problem_type"]
    return list(by_key.values())


def classify_problem_types(problems: list[dict]) -> list[dict]:
    for p in problems:
        if p.get("problem_type") in PROBLEM_TYPES:
            continue
        text = (p["statement"] + " " + p["normalized_problem"]).lower()
        p["problem_type"] = next((t for kws, t in _CLASSIFY if any(k in text for k in kws)),
                                 "operational_problem")
    return problems


def derive_desired_outcomes(problems: list[dict]) -> list[dict]:
    for p in problems:
        if not p.get("desired_outcome"):
            p["desired_outcome"] = f"Confidently handle: {p['normalized_problem']}."
            p["_outcome_derived"] = True
    return problems


def assign_confidence(problems: list[dict]) -> list[dict]:
    for p in problems:
        n = len(p["source_ids"])
        if p["basis"] == "inferred":
            p["confidence"], p["confidence_reason"] = "LOW", "inferred candidate; no observed evidence"
        elif n <= 1:
            p["confidence"], p["confidence_reason"] = "LOW", f"{n} observed source"
        elif n <= 3:
            p["confidence"], p["confidence_reason"] = "MEDIUM", f"{n} independent observed sources"
        else:
            p["confidence"], p["confidence_reason"] = "HIGH", f"{n} independent observed sources"
    return problems


def _build_records(audience: dict, problems: list[dict]) -> list[dict]:
    out = []
    for p in problems:
        pid = f"prb-{U.slug(audience['name'])}-{p['_key']}"
        srcs = sorted(p["source_ids"])
        out.append({
            "id": pid, "type": "problem",
            "market_id": audience["market_id"], "submarket_id": audience["submarket_id"],
            "audience_id": audience["id"],
            "statement": p["statement"], "normalized_problem": p["normalized_problem"],
            "problem_type": p["problem_type"], "desired_outcome": p["desired_outcome"],
            "source_refs": srcs, "evidence_count": len(srcs),
            "basis": p["basis"], "confidence": p["confidence"],
            "confidence_reason": p["confidence_reason"], "status": "active",
        })
    return out


# ---------------------------------------------------------------- validation
class ProblemValidationError(Exception):
    pass


def validate_problems(problems: list[dict], svc: UniverseService,
                      sources_by_id: dict | None = None) -> dict:
    errors = []
    sources_by_id = sources_by_id if sources_by_id is not None else svc._src
    seen = set()
    by_aud_key = {}
    for p in problems:
        pid = p.get("id")
        if not pid:
            errors.append(f"problem without id: {p.get('statement','?')}")
        elif pid in seen:
            errors.append(f"duplicate problem id {pid}")
        seen.add(pid)
        if p.get("market_id") not in svc._m:
            errors.append(f"{pid}: invalid market_id")
        if p.get("submarket_id") not in svc._s:
            errors.append(f"{pid}: invalid submarket_id")
        if p.get("audience_id") not in svc._a:
            errors.append(f"{pid}: invalid/orphan audience_id")
        if p.get("problem_type") not in PROBLEM_TYPES:
            errors.append(f"{pid}: invalid problem_type '{p.get('problem_type')}'")
        if not (p.get("normalized_problem") or "").strip():
            errors.append(f"{pid}: empty normalized_problem")
        if p.get("basis") not in ("observed", "inferred"):
            errors.append(f"{pid}: invalid basis '{p.get('basis')}'")
        refs = p.get("source_refs", [])
        if p.get("basis") == "observed" and not refs:
            errors.append(f"{pid}: observed problem has no evidence (source_refs empty)")
        if p.get("basis") == "inferred" and refs:
            errors.append(f"{pid}: inferred problem must not carry source_refs (would imply observed)")
        for sid in refs:
            if sid not in sources_by_id:
                errors.append(f"{pid}: dangling source_ref {sid}")
        if p.get("evidence_count") != len(refs):
            errors.append(f"{pid}: evidence_count {p.get('evidence_count')} != len(source_refs) {len(refs)}")
        key = (p.get("audience_id"), U.slug(p.get("normalized_problem", "")))
        if key in by_aud_key:
            errors.append(f"{pid}: duplicate normalized problem under audience")
        by_aud_key[key] = pid
    report = {"problems": len(problems),
              "observed": sum(1 for p in problems if p.get("basis") == "observed"),
              "inferred": sum(1 for p in problems if p.get("basis") == "inferred"),
              "errors": errors, "passed": not errors}
    if errors:
        raise ProblemValidationError(f"{len(errors)} problem validation error(s):\n  - "
                                     + "\n  - ".join(errors[:25]))
    return report


# ---------------------------------------------------------------- persistence
def persist_problems(store: UniverseStore, audience_id: str,
                     new_problems: list[dict], new_sources: list[dict]) -> None:
    # replace only THIS audience's slice; keep every other audience's data
    problems = [p for p in store.list("problems") if p["audience_id"] != audience_id]
    problems.extend(new_problems)
    store.put_all("problems", problems)
    src_records = [{k: v for k, v in s.items() if not k.startswith("_")} for s in new_sources]
    sources = [s for s in store.list("problem_sources") if s.get("audience_id") != audience_id]
    sources.extend(src_records)
    store.put_all("problem_sources", sources)


def update_audience_problem_count(store: UniverseStore, audience_id: str) -> int:
    problems = [p for p in store.list("problems") if p["audience_id"] == audience_id]
    count = len(problems)
    auds = store.list("audiences")
    for a in auds:
        if a["id"] == audience_id:
            a["problem_count"] = count
            a["research_status"] = "problems_discovered" if count else "unresearched"
    store.put_all("audiences", auds)
    return count


# ---------------------------------------------------------------- orchestrator
def discover(audience_id: str, import_file: str | None = None,
             seed_inferred: bool = False, seed_lookup: dict | None = None) -> dict:
    store = UniverseStore()
    svc = UniverseService(store)
    audience = load_audience(audience_id, svc)
    profile = build_problem_search_profile(audience, svc)
    sources, retrieval_notes = gather_problem_sources(audience_id, import_file)
    sources = normalize_sources(sources, audience_id)
    seed = (seed_lookup or {}).get(audience_id, []) if seed_inferred else []
    cands = extract_problem_candidates(sources, seed)
    deduped = deduplicate_problem_candidates(cands)
    classify_problem_types(deduped)
    derive_desired_outcomes(deduped)
    assign_confidence(deduped)
    records = _build_records(audience, deduped)

    src_by_id = {s["source_id"]: s for s in sources}
    validate_problems(records, svc, sources_by_id=src_by_id)   # raises on failure
    persist_problems(store, audience_id, records, sources)
    count = update_audience_problem_count(store, audience_id)

    return {"audience_id": audience_id, "path": svc.path_for_audience(audience_id),
            "profile": profile, "retrieval": retrieval_notes,
            "problem_count": count,
            "observed": sum(1 for r in records if r["basis"] == "observed"),
            "inferred": sum(1 for r in records if r["basis"] == "inferred"),
            "problems": records}


def validate_all() -> dict:
    store = UniverseStore()
    svc = UniverseService(store)
    return validate_problems(store.list("problems"), svc, sources_by_id=svc._src)
