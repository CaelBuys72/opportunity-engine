"""Market Universe — Build 1 (Market -> Submarket -> Audience).

First-class, flat taxonomy entities (each with explicit parent IDs), kept
SEPARATE from the Phase-1 `industries/` model so Phases 1-9.5 are untouched.
This layer is the future upstream anchor: an Audience gets a stable identity so
Build 2+ can attach problems, opportunities, scores, and creator density to it.

Persistence is bundled JSON under data/universe/ via UniverseStore, which mirrors
the existing JsonStore method philosophy (list/get/put) so a DB backend can later
replace it without touching callers.

Honesty: generated nodes are `basis: "inferred"` (taxonomy, not validated
demand). No market size / audience size / demand / creator counts are invented —
those fields stay unknown/0 until real downstream evidence exists.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_DIR = ROOT / "data" / "universe"
VALID_BASIS = {"observed", "inferred", "unknown"}
VALID_STATUS = {"active", "archived"}
VALID_TYPES = {"market", "submarket", "audience"}
# downstream fields on Audience that later builds own — preserved across re-runs
AUDIENCE_DOWNSTREAM = ("problem_count", "opportunity_count", "creator_density", "research_status")


def slug(s: str) -> str:
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return re.sub(r"-+", "-", s)


def market_id(name: str) -> str:
    return f"mkt-{slug(name)}"


def submarket_id(market_name: str, name: str) -> str:
    return f"sub-{slug(market_name)}-{slug(name)}"


def audience_id(market_name: str, submarket_name: str, name: str) -> str:
    return f"aud-{slug(market_name)}-{slug(submarket_name)}-{slug(name)}"


# ---------------------------------------------------------------- store
class UniverseStore:
    """Bundled-JSON store; interface-compatible with the repo's Store philosophy."""

    COLLECTIONS = ("markets", "submarkets", "audiences")

    def __init__(self, data_dir: Path = UNIVERSE_DIR):
        self.dir = Path(data_dir)
        import storage
        self._backend = storage.get_backend()

    def list(self, collection: str) -> list[dict]:
        return self._backend.list_rows(collection)

    def get(self, collection: str, _id: str) -> dict | None:
        return self._backend.get_row(collection, _id)

    def put_all(self, collection: str, records: list[dict]) -> None:
        # whole-collection replace (used by the seed builder); upserts under the hood
        self._backend.replace_collection(collection, records)


# ---------------------------------------------------------------- relationship service
class UniverseService:
    """Relationship lookups + traversal over the three collections."""

    def __init__(self, store: UniverseStore | None = None):
        self.store = store or UniverseStore()
        self._m = {r["id"]: r for r in self.store.list("markets")}
        self._s = {r["id"]: r for r in self.store.list("submarkets")}
        self._a = {r["id"]: r for r in self.store.list("audiences")}
        # Build 2 — problems + their sources (empty until discovery runs)
        self._p = {r["id"]: r for r in self.store.list("problems")}
        self._src = {r["source_id"]: r for r in self.store.list("problem_sources")}
        # Build 3 — opportunities
        self._o = {r["id"]: r for r in self.store.list("opportunities")}
        # Build 4 — scores + rankings (side collections; opportunities.json stays pristine)
        self._score = {r["opportunity_id"]: r for r in self.store.list("opportunity_scores")}
        self._rankings = self.store.list("opportunity_rankings")

    def markets(self) -> list[dict]:
        return list(self._m.values())

    def submarkets_for_market(self, market_id: str) -> list[dict]:
        return [s for s in self._s.values() if s["market_id"] == market_id]

    def audiences_for_submarket(self, submarket_id: str) -> list[dict]:
        return [a for a in self._a.values() if a["submarket_id"] == submarket_id]

    def market_for_audience(self, audience_id: str) -> dict | None:
        a = self._a.get(audience_id)
        return self._m.get(a["market_id"]) if a else None

    def path_for_audience(self, audience_id: str) -> list[str] | None:
        a = self._a.get(audience_id)
        if not a:
            return None
        m = self._m.get(a["market_id"])
        s = self._s.get(a["submarket_id"])
        return [m["name"] if m else "?", s["name"] if s else "?", a["name"]]

    # ---- Build 2: problems ----
    def problems_for_audience(self, audience_id: str) -> list[dict]:
        return [p for p in self._p.values() if p["audience_id"] == audience_id]

    def get_problem(self, problem_id: str) -> dict | None:
        return self._p.get(problem_id)

    def problem_sources(self, problem_id: str) -> list[dict]:
        p = self._p.get(problem_id)
        if not p:
            return []
        return [self._src[sid] for sid in p.get("source_refs", []) if sid in self._src]

    def path_for_problem(self, problem_id: str) -> list[str] | None:
        p = self._p.get(problem_id)
        if not p:
            return None
        m = self._m.get(p["market_id"])
        s = self._s.get(p["submarket_id"])
        a = self._a.get(p["audience_id"])
        return [m["name"] if m else "?", s["name"] if s else "?",
                a["name"] if a else "?", p["statement"]]

    # ---- Build 3: opportunities ----
    def opportunities_for_audience(self, audience_id: str) -> list[dict]:
        return [o for o in self._o.values() if o["audience_id"] == audience_id]

    def get_opportunity(self, opportunity_id: str) -> dict | None:
        return self._o.get(opportunity_id)

    def problems_for_opportunity(self, opportunity_id: str) -> list[dict]:
        o = self._o.get(opportunity_id)
        if not o:
            return []
        return [self._p[pid] for pid in o.get("problem_ids", []) if pid in self._p]

    def path_for_opportunity(self, opportunity_id: str) -> list[str] | None:
        o = self._o.get(opportunity_id)
        if not o:
            return None
        m = self._m.get(o["market_id"]); s = self._s.get(o["submarket_id"])
        a = self._a.get(o["audience_id"])
        return [m["name"] if m else "?", s["name"] if s else "?",
                a["name"] if a else "?", o["name"]]

    # ---- Build 4: scoring / prioritization (read-side; joins side collections) ----
    def score_for_opportunity(self, opportunity_id: str) -> dict | None:
        return self._score.get(opportunity_id)

    def creator_density_for_opportunity(self, opportunity_id: str) -> dict | None:
        s = self._score.get(opportunity_id)
        return s.get("creator_density_detail") if s else None

    def commercial_evidence_for_opportunity(self, opportunity_id: str) -> list[dict]:
        f = ROOT / "data" / "commercial_inputs" / f"{opportunity_id}.json"
        if not f.exists():
            return []
        return json.loads(f.read_text()).get("observations", [])

    def risk_flags_for_opportunity(self, opportunity_id: str) -> list[dict]:
        s = self._score.get(opportunity_id)
        return s.get("risk_flags", []) if s else []

    def ranked_opportunities(self) -> list[dict]:
        return list(self._rankings)

    def top_opportunities(self, limit: int = 10) -> list[dict]:
        return self._rankings[:limit]

    def tree(self) -> list[dict]:
        out = []
        for m in sorted(self._m.values(), key=lambda x: x["name"]):
            subs = []
            for s in sorted(self.submarkets_for_market(m["id"]), key=lambda x: x["name"]):
                subs.append({"id": s["id"], "name": s["name"],
                             "audiences": [{"id": a["id"], "name": a["name"]}
                                           for a in self.audiences_for_submarket(s["id"])]})
            out.append({"id": m["id"], "name": m["name"], "submarkets": subs})
        return out


# ---------------------------------------------------------------- validator
class UniverseValidationError(Exception):
    pass


def validate_universe(markets: list[dict], submarkets: list[dict], audiences: list[dict]) -> dict:
    """Returns a report; raises UniverseValidationError on hard failures."""
    errors: list[str] = []

    def check_ids(records, label):
        seen = set()
        for r in records:
            rid = r.get("id")
            if not rid:
                errors.append(f"{label}: record without id: {r}")
            elif rid in seen:
                errors.append(f"{label}: duplicate id {rid}")
            seen.add(rid)
        return seen

    m_ids = check_ids(markets, "market")
    s_ids = check_ids(submarkets, "submarket")
    a_ids = check_ids(audiences, "audience")

    required = {"market": ("id", "type", "name", "status", "basis"),
                "submarket": ("id", "type", "market_id", "name", "status", "basis"),
                "audience": ("id", "type", "market_id", "submarket_id", "name", "status", "basis")}

    def check_fields(records, kind):
        for r in records:
            for f in required[kind]:
                if not r.get(f) and r.get(f) != 0:
                    errors.append(f"{kind} {r.get('id','?')}: missing/empty '{f}'")
            if r.get("type") != kind:
                errors.append(f"{kind} {r.get('id','?')}: type != '{kind}'")
            if r.get("basis") not in VALID_BASIS:
                errors.append(f"{kind} {r.get('id','?')}: invalid basis '{r.get('basis')}'")
            if r.get("status") not in VALID_STATUS:
                errors.append(f"{kind} {r.get('id','?')}: invalid status '{r.get('status')}'")

    check_fields(markets, "market")
    check_fields(submarkets, "submarket")
    check_fields(audiences, "audience")

    # referential integrity (also catches orphans + broken parents)
    for s in submarkets:
        if s.get("market_id") not in m_ids:
            errors.append(f"submarket {s.get('id')}: orphan / invalid market_id {s.get('market_id')}")
    for a in audiences:
        if a.get("market_id") not in m_ids:
            errors.append(f"audience {a.get('id')}: invalid market_id {a.get('market_id')}")
        if a.get("submarket_id") not in s_ids:
            errors.append(f"audience {a.get('id')}: orphan / invalid submarket_id {a.get('submarket_id')}")
        else:
            parent = next(s for s in submarkets if s["id"] == a["submarket_id"])
            if parent.get("market_id") != a.get("market_id"):
                errors.append(f"audience {a.get('id')}: market_id disagrees with its submarket's market_id")

    # no duplicate normalized names under the same parent
    def dup_names(records, parent_key):
        seen = {}
        for r in records:
            key = (r.get(parent_key), (r.get("name") or "").strip().lower())
            if key in seen:
                errors.append(f"duplicate normalized name '{r.get('name')}' under {parent_key}={r.get(parent_key)}")
            seen[key] = r.get("id")
    dup_names(submarkets, "market_id")
    dup_names(audiences, "submarket_id")

    report = {
        "markets": len(markets), "submarkets": len(submarkets), "audiences": len(audiences),
        "duplicate_ids": sum(1 for e in errors if "duplicate id" in e),
        "broken_references": sum(1 for e in errors if "orphan" in e or "invalid market_id" in e
                                 or "invalid submarket_id" in e),
        "errors": errors, "passed": not errors,
    }
    if errors:
        raise UniverseValidationError(
            f"{len(errors)} validation error(s):\n  - " + "\n  - ".join(errors[:25]))
    return report
