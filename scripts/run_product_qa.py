#!/usr/bin/env python3
"""Build 6 — validate a built product (structural + content QA + gates)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "app"))
import production as P  # noqa: E402
def main():
    oid = next((a for a in sys.argv[1:] if a.startswith("opp-")), None)
    if not oid: raise SystemExit("usage: run_product_qa.py <opp-id>")
    try: r = P.validate_product(oid)
    except P.ProductValidationError as e: raise SystemExit(f"✗ Product QA/validation FAILED:\n{e}")
    print(f"Product QA PASS for {oid} | release_status={r['release_status']}")
if __name__ == "__main__": main()
