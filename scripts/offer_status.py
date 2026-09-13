#!/usr/bin/env python3
"""Build 7 — inspect the offer package for an opportunity."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "app"))
import offer as O  # noqa: E402


def main():
    oid = next((a for a in sys.argv[1:] if a.startswith("opp-")), None)
    if not oid:
        raise SystemExit("usage: offer_status.py <opp-id>")
    svc = O.OfferService(oid)
    if not svc.exists():
        raise SystemExit(f"no offer for {oid} — run build_offer.py first")
    o = svc.offer()
    pr = svc.pricing()
    dr = svc.distribution_readiness()
    print(f"{oid}")
    print(f"  product: {o['product_name']}")
    print(f"  price: ${pr['launch_price']} launch (ref ${pr['reference_price']}) {pr['currency']} {pr['model']}")
    print(f"  components in offer: {o['core_product']['component_count']}")
    print(f"  offer QA: {'PASS' if svc.qa_passed() else 'FAIL / not run'}")
    print(f"  distribution readiness: {dr['state']} (Phase 9.5: {dr['phase_9_5_verdict']}, "
          f"qualified creators: {dr['qualified_creator_count']})")
    print(f"  files: {', '.join(svc.files())}")


if __name__ == "__main__":
    main()
