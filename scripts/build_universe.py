#!/usr/bin/env python3
"""Build 1 — generate & persist the Market Universe (Market -> Submarket -> Audience).

    python3 scripts/build_universe.py            # build + validate + persist + summarize
    python3 scripts/build_universe.py --validate # validate persisted universe only

Idempotent: deterministic IDs mean re-running overwrites the same records rather
than duplicating. Downstream Audience fields (problem_count, opportunity_count,
creator_density, research_status) written by later builds are PRESERVED across
re-runs. Generation is separate from storage so the seed can later be swapped
for AI generation / curated files / datasets.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

import universe as U                       # noqa: E402
from universe import (UniverseStore, UniverseService, validate_universe,   # noqa: E402
                      UniverseValidationError, VALID_BASIS)
from universe_seed import SEED             # noqa: E402


# ---------------- generation stages (pure; no storage) ----------------
def seed_markets(seed: dict) -> list[dict]:
    return [{"id": U.market_id(name), "type": "market", "name": name,
             "description": data.get("description", ""), "status": "active", "basis": "inferred"}
            for name, data in seed.items()]


def expand_submarkets(seed: dict) -> list[dict]:
    out = []
    for mname, data in seed.items():
        for sname in data["submarkets"]:
            out.append({"id": U.submarket_id(mname, sname), "type": "submarket",
                        "market_id": U.market_id(mname), "name": sname,
                        "description": "", "status": "active", "basis": "inferred"})
    return out


def expand_audiences(seed: dict) -> list[dict]:
    out = []
    for mname, data in seed.items():
        for sname, auds in data["submarkets"].items():
            for aname in auds:
                out.append({
                    "id": U.audience_id(mname, sname, aname), "type": "audience",
                    "market_id": U.market_id(mname), "submarket_id": U.submarket_id(mname, sname),
                    "name": aname, "description": "", "status": "active", "basis": "inferred",
                    # downstream anchors — honest defaults, no fabricated data
                    "problem_count": 0, "opportunity_count": 0,
                    "creator_density": "unknown", "research_status": "unresearched"})
    return out


def _merge_preserving_downstream(new: list[dict], existing: list[dict], keys) -> list[dict]:
    old = {r["id"]: r for r in existing}
    for rec in new:
        prev = old.get(rec["id"])
        if prev:
            for k in keys:
                if k in prev:
                    rec[k] = prev[k]   # keep values later builds may have written
    return new


def persist_universe(store: UniverseStore, markets, submarkets, audiences) -> None:
    audiences = _merge_preserving_downstream(
        audiences, store.list("audiences"), U.AUDIENCE_DOWNSTREAM)
    store.put_all("markets", markets)
    store.put_all("submarkets", submarkets)
    store.put_all("audiences", audiences)


def summarize_universe(report: dict, store: UniverseStore) -> dict:
    svc = UniverseService(store)
    summary = {
        "markets": report["markets"], "submarkets": report["submarkets"],
        "audiences": report["audiences"], "broken_references": report["broken_references"],
        "duplicate_ids": report["duplicate_ids"], "validation": "PASS" if report["passed"] else "FAIL",
        "avg_submarkets_per_market": round(report["submarkets"] / max(report["markets"], 1), 1),
        "avg_audiences_per_submarket": round(report["audiences"] / max(report["submarkets"], 1), 1),
        "sample_paths": [" -> ".join(svc.path_for_audience(a["id"]))
                         for a in list(svc._a.values())[:3]],
    }
    store.dir.mkdir(parents=True, exist_ok=True)
    import json
    (store.dir / "universe_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def build(store: UniverseStore) -> dict:
    markets = seed_markets(SEED)
    submarkets = expand_submarkets(SEED)
    audiences = expand_audiences(SEED)
    report = validate_universe(markets, submarkets, audiences)   # raises on failure
    persist_universe(store, markets, submarkets, audiences)
    return report


def validate_only(store: UniverseStore) -> dict:
    return validate_universe(store.list("markets"), store.list("submarkets"), store.list("audiences"))


def main():
    store = UniverseStore()
    validate_mode = "--validate" in sys.argv[1:]
    try:
        report = validate_only(store) if validate_mode else build(store)
    except UniverseValidationError as e:
        raise SystemExit(f"✗ Universe validation FAILED:\n{e}")
    summary = summarize_universe(report, store)
    print(f"\nMarkets: {summary['markets']}")
    print(f"Submarkets: {summary['submarkets']}")
    print(f"Audiences: {summary['audiences']}")
    print(f"Broken references: {summary['broken_references']}")
    print(f"Duplicate IDs: {summary['duplicate_ids']}")
    print(f"Validation: {summary['validation']}")
    print(f"(~{summary['avg_submarkets_per_market']} submarkets/market, "
          f"~{summary['avg_audiences_per_submarket']} audiences/submarket)")
    print("Sample paths:")
    for p in summary["sample_paths"]:
        print(f"  {p}")
    print(f"\nPersisted to data/universe/ (+ universe_summary.json).")


if __name__ == "__main__":
    main()
