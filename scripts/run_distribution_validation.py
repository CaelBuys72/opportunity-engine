#!/usr/bin/env python3
"""Phase 9.5 — validate creator/distribution fit for an opportunity.

    python3 scripts/run_distribution_validation.py freelancer-us-tax

Reads Phase 8/9 artifacts + optional manual creator import at
data/creator_candidates/<id>.json. Fails honestly if the brief is missing.
Returns NEEDS_RESEARCH (not a guess) when there is no candidate evidence.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import distribution                 # noqa: E402
from store import JsonStore         # noqa: E402

store = JsonStore()


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 scripts/run_distribution_validation.py <opportunity-id>")
    opp_id = sys.argv[1].strip()
    try:
        r = distribution.run(opp_id)
    except distribution.DistributionError as e:
        raise SystemExit(f"✗ Distribution validation refused (honest failure): {e}")

    p = store.get("opportunities", opp_id)
    if p:
        p["distribution_verdict"] = r["verdict"]
        store.put("opportunities", p)

    v = r["dossier"]["verdict"]
    c = r["counts"]
    print(f"\n▣ Distribution fit for '{opp_id}': {r['verdict']}  (confidence {r['confidence']})")
    print(f"  {v['reason']}")
    print(f"  candidates: {c['candidates']} | qualified: {c['qualified']} | highly-qualified: {c['highly_qualified']}")
    if v["strongest_creators"]:
        print("  strongest:", "; ".join(v["strongest_creators"]))
    if v["unknowns"]:
        print("  unknowns:")
        for u in v["unknowns"][:6]:
            print(f"    - {u}")
    print(f"  next action: {v['next_action']}")
    print("  files:")
    for _, path in r["files"].items():
        print(f"    - {path}")


if __name__ == "__main__":
    main()
