#!/usr/bin/env python3
"""Build 5 — explicitly promote a ranked opportunity into the deep pipeline.

    python3 scripts/promote_opportunity.py <opportunity-id>
    python3 scripts/promote_opportunity.py <opportunity-id> --force   # LOW_PRIORITY/INSUFFICIENT_DATA
Promotion = "selected for deeper investigation". NOT validated/profitable/approved.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import pipeline as P  # noqa: E402

def main():
    args = sys.argv[1:]
    oid = next((a for a in args if a.startswith("opp-")), None)
    if not oid:
        raise SystemExit("usage: promote_opportunity.py <opportunity-id> [--force]")
    try:
        st = P.promote(oid, force="--force" in args)
    except P.PipelineError as e:
        raise SystemExit(f"✗ Promotion refused: {e}")
    print(f"✓ Promoted {oid}")
    print(f"  rank #{st['source_rank']} · {st['priority_classification']} · "
          f"C={st['commercial_score']} E={st['evidence_score']} P={st['priority_score']}"
          + (" · OVERRIDE" if st['override'] else ""))
    print(f"  pipeline_stage: {st['pipeline_stage']} (research pending)")
    print(f"  next: python3 scripts/run_pipeline.py {oid} --through research")


if __name__ == "__main__":
    main()
