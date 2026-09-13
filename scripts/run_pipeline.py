#!/usr/bin/env python3
"""Build 5 — drive a promoted opportunity through existing Phase 8/9/9.5.

    python3 scripts/run_pipeline.py <opportunity-id> --through research
    python3 scripts/run_pipeline.py <opportunity-id> --through curation
    python3 scripts/run_pipeline.py <opportunity-id> --through distribution
Gates enforced; needs_review/failed stops progression.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import pipeline as P  # noqa: E402

def main():
    args = sys.argv[1:]
    oid = next((a for a in args if a.startswith("opp-")), None)
    through = next((args[i+1] for i, a in enumerate(args) if a == "--through"), "research")
    if not oid:
        raise SystemExit("usage: run_pipeline.py <opportunity-id> --through research|curation|distribution")
    try:
        out = P.run_pipeline(oid, through=through)
    except P.PipelineError as e:
        raise SystemExit(f"✗ Pipeline halted: {e}")
    if "research" in out:
        r = out["research"]
        print(f"  research: {r['research_status']} ({r['counts']['sources']} sources, {r['counts']['claims']} claims)")
    if out.get("stopped_at"):
        print(f"  ⛔ stopped: {out['stopped_at']}")
    if "curation" in out:
        print(f"  curation: {out['curation']['curation_status']} "
              f"({out['curation']['verification_required']} components need external verification)")
    if "distribution" in out:
        d = out["distribution"]
        print(f"  distribution: {d['verdict']} (confidence {d['confidence']}; seeded {d['seeded_candidates']} creators)")


if __name__ == "__main__":
    main()
