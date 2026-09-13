#!/usr/bin/env python3
"""Build 6/7 — human commercial gate: approve a release_candidate for sale.

Normal:   approve_product_release.py <opp-id>
Override: approve_product_release.py <opp-id> --override --reason "..." [--limitation "..." ...]

The override path approves a below-threshold ('revision_required') product with an
explicit human reason. It NEVER alters the recorded acceptance score or audit history.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "app"))
import production as P  # noqa: E402


def main():
    args = sys.argv[1:]
    oid = next((a for a in args if a.startswith("opp-")), None)
    if not oid:
        raise SystemExit("usage: approve_product_release.py <opp-id> [--override --reason ... [--limitation ...]]")
    override = "--override" in args
    reason = None
    limitations = []
    for i, a in enumerate(args):
        if a == "--reason" and i + 1 < len(args):
            reason = args[i + 1]
        if a == "--limitation" and i + 1 < len(args):
            limitations.append(args[i + 1])
    try:
        r = P.approve_release(oid, override=override, override_reason=reason,
                              known_limitations=limitations or None)
    except P.ProductionError as e:
        raise SystemExit(f"✗ Release approval refused: {e}")
    print(f"✓ Release approved for sale: {oid}")
    print(f"  kind={r['release_approval']}  acceptance={r['acceptance_score']}  "
          f"threshold={r['automatic_threshold']}  override={r['override']}")
    if r.get("override_reason"):
        print(f"  reason: {r['override_reason']}")
        for lim in r.get("known_limitations", []):
            print(f"    - known limitation: {lim}")


if __name__ == "__main__":
    main()
