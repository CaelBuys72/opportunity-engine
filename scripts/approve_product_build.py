#!/usr/bin/env python3
"""Build 6 — human gate: approve an opportunity for actual production."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "app"))
import production as P  # noqa: E402
def main():
    oid = next((a for a in sys.argv[1:] if a.startswith("opp-")), None)
    if not oid: raise SystemExit("usage: approve_product_build.py <opp-id>")
    try: r = P.approve_build(oid)
    except P.ProductionError as e: raise SystemExit(f"✗ Build approval refused: {e}")
    print(f"✓ Approved to build: {oid}  (product_build_status={r['product_build_status']})")
    print(f"  next: python3 scripts/build_product.py {oid}")
if __name__ == "__main__": main()
