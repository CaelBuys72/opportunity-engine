#!/usr/bin/env python3
"""Build 6 — manufacture product files from the Phase-9 spec (gated)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT / "app"))
import production as P  # noqa: E402
def main():
    args = sys.argv[1:]
    oid = next((a for a in args if a.startswith("opp-")), None)
    comp = next((args[i+1] for i,a in enumerate(args) if a == "--component"), None)
    if not oid: raise SystemExit("usage: build_product.py <opp-id> [--component <id>] [--force]")
    try: m = P.build_product(oid, only_component=comp, force="--force" in args)
    except P.ProductionError as e: raise SystemExit(f"✗ Production refused/halted: {e}")
    print(f"\n▣ Product build: {oid}")
    for c in m["components"]:
        bl = f" BLOCKED({c['blocked_formats'][0]['format']})" if c["blocked_formats"] else ""
        print(f"  {c['component_id']:<7} {c['production_status']:<14} qa={c['qa_status']:<7} "
              f"fmt={','.join(c['required_formats'])}{bl}  {c['name']}")
    print(f"  bundle: {m['bundle_status']} | release: {m['release_status']}")
    for r in m["release_blocked_reasons"]: print(f"    ⛔ {r}")
    print(f"  (pdf capability: {m['capabilities']['pdf']})")
if __name__ == "__main__": main()
