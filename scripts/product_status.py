#!/usr/bin/env python3
"""Build 6 — inspect product manifest / production state."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "app"))
import production as P  # noqa: E402
def main():
    oid = next((a for a in sys.argv[1:] if a.startswith("opp-")), None)
    if not oid: raise SystemExit("usage: product_status.py <opp-id>")
    svc = P.ProductService(oid)
    m = svc.get_product_manifest()
    if not m: raise SystemExit(f"no product for {oid}")
    print(f"{oid}\n  product_status={m['product_status']} release={m['release_status']} bundle={m['bundle_status']}")
    print(f"  built: {sum(1 for c in m['components'] if c['production_status']=='built')}/{len(m['components'])}"
          f" | blocked: {len(svc.blocked_components())} | qa_failures: {len(svc.qa_failures())}")
    for c in svc.blocked_components():
        print(f"    ⛔ {c['component_id']} {c['production_status']} {c.get('blocked_formats')}")
if __name__ == "__main__": main()
