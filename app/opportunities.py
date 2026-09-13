"""Build 3 — Raw Problems -> Commercial Opportunity clustering.

Groups related raw problems for ONE audience into coherent commercial
opportunities (problem spaces). Does NOT produce product ideas/formats, scores,
creator data, or demand claims.

Two paths, one pipeline:
  * automatic — deterministic token-similarity clustering (explainable, no ML dep)
  * manual    — data/opportunity_clusters/<audience-id>.json (human/agent-curated)
Both run through the same derive/validate/persist stages.

Honesty: an Opportunity's basis/evidence/confidence are inherited from its member
problems only. No demand / market size / WTP / creator density / revenue invented.
All Build-3 opportunities start commercial_status="unvalidated", creator_density
="unknown", score=null.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

import universe as U
from universe import UniverseStore, UniverseService

ROOT = Path(__file__).resolve().parent.parent
MANUAL_DIR = ROOT / "data" / "opportunity_clusters"

SIM_THRESHOLD = 0.20          # Jaccard floor to link two problems
TYPE_BONUS = 0.12             # added when two problems share problem_type
TOO_BROAD_FRACTION = 0.85     # a single cluster covering ~all problems is too broad
# generic/filler tokens that must NOT create false links
GENERIC = {"uncertainty", "confusion", "unclear", "difficulty", "difficult", "handling",
           "based", "problem", "issue", "hard", "help", "manage", "managing", "confidently",
           "handle", "consistent", "inconsistent", "hosts", "techs", "owners", "creators",
           "freelancers", "clients", "client", "puppy", "content", "airbnb", "nail"}
STOP = {"the", "and", "for", "with", "your", "you", "how", "what", "that", "this", "from",
        "are", "was", "their", "them", "a", "to", "of", "in", "on", "my", "i", "when",
        "dont", "don", "cant", "can", "not", "know", "get", "is", "it", "me", "we", "our",
        "per", "vs", "or", "an", "be", "no", "into", "keep", "every"}


class OpportunityValidationError(Exception):
    pass


def _tokens(*texts: str) -> set[str]:
    toks = set()
    for t in texts:
        for w in "".join(c.lower() if c.isalnum() else " " for c in (t or "")).split():
            if len(w) > 2 and w not in STOP and w not in GENERIC:
                toks.add(w)
    return toks


# ---------------------------------------------------------------- stages
def load_audience(audience_id: str, svc: UniverseService) -> dict:
    a = svc._a.get(audience_id)
    if not a:
        raise ValueError(f"No audience '{audience_id}'.")
    return a


def load_problems(audience_id: str, svc: UniverseService) -> list[dict]:
    return svc.problems_for_audience(audience_id)


def build_problem_similarity_features(problems: list[dict]) -> dict[str, set]:
    return {p["id"]: _tokens(p["normalized_problem"], p.get("desired_outcome", ""))
            for p in problems}


def _sim(a: set, b: set, same_type: bool) -> float:
    if not a or not b:
        return 0.0
    j = len(a & b) / len(a | b)
    return j + (TYPE_BONUS if same_type else 0.0)


def generate_candidate_clusters(problems: list[dict], feats: dict) -> list[list[str]]:
    """Connected components over edges whose similarity >= threshold."""
    ids = [p["id"] for p in problems]
    ptype = {p["id"]: p["problem_type"] for p in problems}
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(len(ids)):
        for k in range(i + 1, len(ids)):
            a, b = ids[i], ids[k]
            if _sim(feats[a], feats[b], ptype[a] == ptype[b]) >= SIM_THRESHOLD:
                union(a, b)
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def merge_near_duplicate_clusters(clusters: list[list[str]]) -> list[list[str]]:
    # connected components are already disjoint; merge any that share members (manual case)
    merged, used = [], set()
    for i, c in enumerate(clusters):
        if i in used:
            continue
        cur = set(c)
        for k in range(i + 1, len(clusters)):
            if k in used and clusters[k]:
                continue
            if cur & set(clusters[k]):
                cur |= set(clusters[k]); used.add(k)
        merged.append(sorted(cur))
    return merged


def reject_bad_clusters(clusters: list[list[str]], total_problems: int,
                        allow_single: bool = False) -> tuple[list[list[str]], list[dict]]:
    kept, rejected = [], []
    for c in clusters:
        if len(c) == 0:
            rejected.append({"members": c, "reason": "empty"})
        elif len(c) == 1 and not allow_single:
            rejected.append({"members": c, "reason": "too narrow (single problem)"})
        elif total_problems >= 4 and len(c) >= max(1, int(total_problems * TOO_BROAD_FRACTION)):
            rejected.append({"members": c, "reason": "too broad (covers ~all audience problems)"})
        else:
            kept.append(c)
    return kept, rejected


def derive_opportunity_name(member_problems: list[dict], provided: str | None = None) -> str:
    if provided:
        return provided.strip()
    counts = Counter()
    for p in member_problems:
        for t in _tokens(p["normalized_problem"]):
            counts[t] += 1
    top = [w for w, _ in counts.most_common(3)]
    if not top:
        return "Unnamed problem space"
    return " & ".join(w.capitalize() for w in top[:2]) if len(top) >= 2 else top[0].capitalize()


def derive_shared_outcome(member_problems: list[dict], provided: str | None = None) -> str:
    if provided:
        return provided.strip()
    outs = [p.get("desired_outcome", "") for p in member_problems if p.get("desired_outcome")]
    uniq = list(dict.fromkeys(outs))[:3]
    return "A shared outcome across member problems: " + " ".join(uniq) if uniq else "unknown"


def summarize_problem_types(member_problems: list[dict]) -> dict:
    return dict(Counter(p["problem_type"] for p in member_problems))


def derive_evidence_summary(member_problems: list[dict], svc: UniverseService) -> dict:
    observed = sum(1 for p in member_problems if p["basis"] == "observed")
    inferred = sum(1 for p in member_problems if p["basis"] == "inferred")
    srcs = set()
    for p in member_problems:
        srcs.update(p.get("source_refs", []))
    return {"observed_problem_count": observed, "inferred_problem_count": inferred,
            "source_count": len(srcs), "source_refs": sorted(srcs)}


def assign_basis(ev: dict) -> str:
    o, i = ev["observed_problem_count"], ev["inferred_problem_count"]
    return "observed" if o and not i else "inferred" if i and not o else "mixed"


def assign_confidence(ev: dict, n_problems: int) -> tuple[str, str]:
    o, u = ev["observed_problem_count"], ev["source_count"]
    if o == 0:
        return "LOW", f"inferred-only cluster ({n_problems} problems, 0 observed, {u} sources)"
    if n_problems >= 3 and o >= 2 and u >= 2:
        return "HIGH", f"{n_problems} problems, {o} observed members across {u} independent sources"
    if n_problems >= 2 and (o >= 1 or u >= 2):
        return "MEDIUM", f"{n_problems} problems, {o} observed, {u} sources"
    return "LOW", f"{n_problems} problems, {o} observed, {u} sources"


def _build_record(audience: dict, name: str, member_problems: list[dict],
                  svc: UniverseService, shared_outcome: str | None = None) -> dict:
    ev = derive_evidence_summary(member_problems, svc)
    basis = assign_basis(ev)
    conf, reason = assign_confidence(ev, len(member_problems))
    return {
        "id": f"opp-{U.slug(audience['name'])}-{U.slug(name)}", "type": "opportunity",
        "market_id": audience["market_id"], "submarket_id": audience["submarket_id"],
        "audience_id": audience["id"], "name": name,
        "description": f"Commercial problem space for {audience['name']}: {name}.",
        "problem_ids": [p["id"] for p in member_problems], "problem_count": len(member_problems),
        "shared_desired_outcome": derive_shared_outcome(member_problems, shared_outcome),
        "problem_types": summarize_problem_types(member_problems),
        "evidence_summary": {k: ev[k] for k in ("observed_problem_count", "inferred_problem_count", "source_count")},
        "source_refs": ev["source_refs"],
        "basis": basis, "confidence": conf, "confidence_reason": reason,
        "commercial_status": "unvalidated", "creator_density": "unknown",
        "score": None, "research_status": "unresearched", "status": "active",
    }


# ---------------------------------------------------------------- validation
def validate_opportunities(opps: list[dict], svc: UniverseService) -> dict:
    errors = []
    seen_ids, seen_names = set(), {}
    for o in opps:
        oid = o.get("id")
        if not oid:
            errors.append("opportunity without id")
        elif oid in seen_ids:
            errors.append(f"duplicate opportunity id {oid}")
        seen_ids.add(oid)
        for k, coll in (("market_id", svc._m), ("submarket_id", svc._s), ("audience_id", svc._a)):
            if o.get(k) not in coll:
                errors.append(f"{oid}: invalid {k}")
        pids = o.get("problem_ids", [])
        if not pids:
            errors.append(f"{oid}: zero problems")
        if len(pids) != len(set(pids)):
            errors.append(f"{oid}: duplicate member problem ids")
        if o.get("problem_count") != len(pids):
            errors.append(f"{oid}: problem_count != len(problem_ids)")
        members = []
        for pid in pids:
            p = svc._p.get(pid)
            if not p:
                errors.append(f"{oid}: member problem {pid} does not exist")
                continue
            members.append(p)
            if p["audience_id"] != o.get("audience_id"):
                errors.append(f"{oid}: member {pid} belongs to a different audience")
        # evidence summary must match members
        if members:
            ev = derive_evidence_summary(members, svc)
            es = o.get("evidence_summary", {})
            if (es.get("observed_problem_count") != ev["observed_problem_count"] or
                    es.get("inferred_problem_count") != ev["inferred_problem_count"] or
                    es.get("source_count") != ev["source_count"]):
                errors.append(f"{oid}: evidence_summary does not match member problems")
            if o.get("basis") != assign_basis(ev):
                errors.append(f"{oid}: basis not correctly derived")
        if o.get("confidence") not in ("LOW", "MEDIUM", "HIGH"):
            errors.append(f"{oid}: invalid confidence")
        if o.get("commercial_status") != "unvalidated":
            errors.append(f"{oid}: commercial_status must default to 'unvalidated'")
        if o.get("creator_density") != "unknown":
            errors.append(f"{oid}: creator_density must default to 'unknown'")
        if o.get("score") is not None:
            errors.append(f"{oid}: score must default to null")
        if o.get("research_status") != "unresearched":
            errors.append(f"{oid}: research_status must default to 'unresearched'")
        key = (o.get("audience_id"), U.slug(o.get("name", "")))
        if key in seen_names:
            errors.append(f"{oid}: duplicate normalized opportunity name under audience")
        seen_names[key] = oid
    report = {"opportunities": len(opps),
              "observed": sum(1 for o in opps if o["basis"] == "observed"),
              "inferred": sum(1 for o in opps if o["basis"] == "inferred"),
              "mixed": sum(1 for o in opps if o["basis"] == "mixed"),
              "errors": errors, "passed": not errors}
    if errors:
        raise OpportunityValidationError(f"{len(errors)} error(s):\n  - " + "\n  - ".join(errors[:25]))
    return report


# ---------------------------------------------------------------- persistence
def persist_opportunities(store: UniverseStore, audience_id: str, new_opps: list[dict]) -> None:
    keep = [o for o in store.list("opportunities") if o["audience_id"] != audience_id]
    keep.extend(new_opps)
    store.put_all("opportunities", keep)


def update_audience_opportunity_count(store: UniverseStore, audience_id: str) -> int:
    opps = [o for o in store.list("opportunities") if o["audience_id"] == audience_id]
    count = len(opps)
    auds = store.list("audiences")
    for a in auds:
        if a["id"] == audience_id:
            a["opportunity_count"] = count
    store.put_all("audiences", auds)
    return count


# ---------------------------------------------------------------- orchestrator
def _resolve_manual(audience_id: str, svc: UniverseService, manual_file: str | None):
    f = Path(manual_file) if manual_file else (MANUAL_DIR / f"{audience_id}.json")
    if not f.exists():
        return None
    data = json.loads(f.read_text())
    by_norm = {p["normalized_problem"].strip().lower(): p["id"]
               for p in svc.problems_for_audience(audience_id)}
    valid_ids = {p["id"] for p in svc.problems_for_audience(audience_id)}
    clusters = []
    for c in data.get("clusters", []):
        pids = list(c.get("problem_ids", []))
        for nm in c.get("problem_normalized", []):
            pid = by_norm.get(nm.strip().lower())
            if not pid:
                raise ValueError(f"manual cluster '{c.get('name')}' references unknown normalized problem '{nm}'")
            pids.append(pid)
        bad = [p for p in pids if p not in valid_ids]
        if bad:
            raise ValueError(f"manual cluster '{c.get('name')}' references problem(s) not in this audience: {bad}")
        clusters.append({"name": c["name"], "problem_ids": sorted(set(pids)),
                         "shared_desired_outcome": c.get("shared_desired_outcome"),
                         "allow_single": c.get("allow_single", False)})
    return clusters


def cluster(audience_id: str, manual_file: str | None = None, mode: str = "auto") -> dict:
    store = UniverseStore()
    svc = UniverseService(store)
    audience = load_audience(audience_id, svc)
    problems = load_problems(audience_id, svc)
    by_id = {p["id"]: p for p in problems}
    if not problems:
        raise ValueError(f"audience '{audience_id}' has no problems (run Build 2 first).")

    manual = _resolve_manual(audience_id, svc, manual_file) if mode == "manual" else None
    rejected = []
    if manual is not None:
        records = []
        for c in manual:
            members = [by_id[p] for p in c["problem_ids"]]
            if len(members) == 1 and not c["allow_single"]:
                rejected.append({"name": c["name"], "reason": "too narrow (single problem); set allow_single to keep"})
                continue
            records.append(_build_record(audience, c["name"], members, svc, c["shared_desired_outcome"]))
    else:  # automatic
        feats = build_problem_similarity_features(problems)
        clusters = generate_candidate_clusters(problems, feats)
        clusters = merge_near_duplicate_clusters(clusters)
        kept, rejected = reject_bad_clusters(clusters, len(problems))
        records = []
        for c in kept:
            members = [by_id[p] for p in c]
            records.append(_build_record(audience, derive_opportunity_name(members), members, svc))

    validate_opportunities(records, svc)      # raises on failure
    persist_opportunities(store, audience_id, records)
    count = update_audience_opportunity_count(store, audience_id)
    return {"audience_id": audience_id, "path": svc.path_for_audience(audience_id),
            "mode": "manual" if manual is not None else "auto",
            "problem_count": len(problems), "opportunity_count": count,
            "rejected": rejected, "opportunities": records}


def validate_all() -> dict:
    store = UniverseStore()
    return validate_opportunities(store.list("opportunities"), UniverseService(store))
