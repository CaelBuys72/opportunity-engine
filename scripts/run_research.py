#!/usr/bin/env python3
"""Phase 8 — run the research engine against a selected pocket.

    python3 scripts/run_research.py freelancer-us-tax
    python3 scripts/run_research.py            # lists pocket ids

Writes the dossier to research/<pocket-id>/ and updates the pocket's
research_status (complete if deep findings exist, else needs_review).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from store import JsonStore          # noqa: E402
import research                      # noqa: E402
from research_inputs import FINDINGS  # noqa: E402

store = JsonStore()


def run_one(pid: str) -> dict:
    pocket = store.get("opportunities", pid)
    if not pocket:
        raise SystemExit(f"! no pocket '{pid}'. Run discovery first.")
    ev = {e["id"]: e for e in store.list("evidence")}
    records = [ev[i] for i in pocket.get("evidence_ids", []) if i in ev]
    result = research.run(pocket, records, FINDINGS.get(pid))
    pocket["status"] = "researching" if result["research_status"] == "needs_review" else "selected"
    pocket["research_status"] = result["research_status"]
    store.put("opportunities", pocket)
    return result


def main():
    if len(sys.argv) < 2:
        print("pockets:")
        for p in store.list("opportunities"):
            print(f"  {p['id']:28} rs={p.get('research_status','not_started')}")
        return
    r = run_one(sys.argv[1].strip())
    b = r["brief"]
    print(f"\n✓ Research dossier for '{r['pocket_id']}'  [{r['research_status'].upper()}]")
    print(f"  sources: {r['counts']['sources']}   traced claims: {r['counts']['claims']}")
    print(f"  format : {b['product_format']}")
    print(f"  price  : {b['price_range']}")
    print(f"  files  :")
    for k, v in r["files"].items():
        print(f"    - {v}")
    print(f"\n  Open the dossier in the UI (RESEARCH panel) or read research/{r['pocket_id']}/product_brief.json")


if __name__ == "__main__":
    main()
