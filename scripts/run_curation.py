#!/usr/bin/env python3
"""Phase 9 — curate a validated Product Brief into a production spec.

    python3 scripts/run_curation.py freelancer-us-tax

Fails honestly (non-zero exit, clear message) if the brief is missing or
incomplete — it will not fabricate the missing information.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import curation                      # noqa: E402
from store import JsonStore          # noqa: E402

store = JsonStore()


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 scripts/run_curation.py <opportunity-id>")
    opp_id = sys.argv[1].strip()
    try:
        r = curation.run(opp_id)
    except curation.CurationError as e:
        raise SystemExit(f"✗ Curation refused (honest failure): {e}")

    # reflect status on the pocket if it exists (non-fatal if not)
    p = store.get("opportunities", opp_id)
    if p:
        p["curation_status"] = "complete"
        store.put("opportunities", p)

    c = r["counts"]
    print(f"\n✓ Product specification for '{opp_id}'  [COMPLETE]")
    print(f"  components: {c['components']} | assets: {c['assets']} | "
          f"verification-required: {c['verification_required']} | unresolved: {c['unresolved']}")
    print("  files:")
    for _, v in r["files"].items():
        print(f"    - {v}")
    if r["dossier"]["verification_requirements"]:
        print("  ⚠ external verification needed:")
        for v in r["dossier"]["verification_requirements"]:
            print(f"    - {v['name']}: {v['reason']}")
    print(f"\n  Hand-off for Phase 10: research/{opp_id}/curation_dossier.json")


if __name__ == "__main__":
    main()
