#!/usr/bin/env python3
"""Phase 6 — run discovery across one or more industries.

Usage:
    python3 scripts/run_discovery.py                # all seed industries
    python3 scripts/run_discovery.py freelancing    # one industry
    python3 scripts/run_discovery.py beauty fitness # several

Idempotent & additive: re-running rebuilds candidate records but PRESERVES a
pocket already marked selected/researching (so a human selection is never
clobbered by a fresh run). Adding a new industry never touches existing ones.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

from store import JsonStore          # noqa: E402
from discovery import cluster, compute_score, rank  # noqa: E402
import seed_dataset as seed          # noqa: E402

store = JsonStore()


def run(industries: list[str]) -> list[dict]:
    selected = set(industries) if industries else {i["id"] for i in seed.INDUSTRIES}
    unknown = selected - {i["id"] for i in seed.INDUSTRIES}
    if unknown:
        print(f"! unknown industries ignored: {sorted(unknown)}")
    selected &= {i["id"] for i in seed.INDUSTRIES}

    # industries
    for ind in seed.INDUSTRIES:
        if ind["id"] in selected:
            rec = dict(ind)
            rec["status"] = "explored"
            store.put("industries", rec)

    pockets_out = []
    used_communities = set()
    for p in seed.POCKETS:
        if p["industry_id"] not in selected:
            continue
        # evidence
        for ob in p["observations"]:
            store.put("evidence", {k: ob[k] for k in
                      ("id", "quote_or_observation", "source_type", "source_url",
                       "basis", "date", "note") if k in ob})
        problems = cluster(p["observations"])
        score = compute_score(p["factors"])

        existing = store.get("opportunities", p["id"])
        status = existing["status"] if existing and existing["status"] in (
            "selected", "researching", "archived") else "candidate"

        pocket = {
            "id": p["id"], "title": p["title"], "industry_id": p["industry_id"],
            "submarket_id": p.get("submarket_id"), "origin": "seed-run",
            "audience": p["audience"], "core_problem": p["core_problem"],
            "desired_outcome": p.get("desired_outcome", ""),
            "related_problems": p.get("related_problems", []),
            "problems": problems,
            "evidence_ids": [ob["id"] for ob in p["observations"]],
            "community_ids": p.get("community_ids", []),
            "existing_solutions": p.get("existing_solutions", []),
            "solution_gaps": p.get("solution_gaps", []),
            "creator_ecosystem": p.get("creator_ecosystem", "unknown"),
            "digital_product_fit": p.get("digital_product_fit", ""),
            "source_urls": p.get("source_urls", []),
            "score": score, "status": status,
        }
        store.put("opportunities", pocket)
        pockets_out.append(pocket)
        used_communities.update(p.get("community_ids", []))

    # communities actually referenced
    for c in seed.COMMUNITIES:
        if c["id"] in used_communities:
            store.put("communities", c)

    return rank(pockets_out)


def main():
    ranked = run([a.lower() for a in sys.argv[1:]])
    print(f"\nDiscovery complete — {len(ranked)} candidate pocket(s):\n")
    for i, p in enumerate(ranked, 1):
        s = p["score"]
        print(f"{i:>2}. {p['score']['overall']:>5}  [{s['confidence']:^6}] {p['title']}")
        if s["weight_unknown_pct"]:
            print(f"      ({s['weight_unknown_pct']}% of weight unknown — {s['confidence_reason']})")
    print(f"\nData written under data/. Start the UI: python3 app/server.py")


if __name__ == "__main__":
    main()
