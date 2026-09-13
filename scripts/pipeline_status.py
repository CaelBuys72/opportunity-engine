#!/usr/bin/env python3
"""Build 5 — inspect pipeline state.
    python3 scripts/pipeline_status.py <opportunity-id>
    python3 scripts/pipeline_status.py --all
    python3 scripts/pipeline_status.py --validate
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import pipeline as P  # noqa: E402

def _row(s):
    return (f"  {s['opportunity_id']}\n     stage={s['pipeline_stage']} | research={s['research_status']} "
            f"| curation={s['curation_status']} | distribution={s['distribution_status']} "
            f"| promo(P={s['priority_score']},{s['priority_classification']})")

def main():
    args = sys.argv[1:]
    if "--validate" in args:
        try:
            r = P.validate_pipeline()
        except P.PipelineValidationError as e:
            raise SystemExit(f"✗ Pipeline validation FAILED:\n{e}")
        print(f"Pipeline states: {r['pipeline_states']} | Validation: PASS")
        return
    svc = P.PipelineService()
    if "--all" in args:
        rows = svc.promoted_opportunities()
        print(f"{len(rows)} promoted opportunit(y/ies):")
        for s in rows:
            print(_row(s))
        return
    oid = next((a for a in args if a.startswith("opp-")), None)
    st = svc.get_pipeline_state(oid) if oid else None
    if not st:
        raise SystemExit("usage: pipeline_status.py <opportunity-id> | --all | --validate")
    print(_row(st))


if __name__ == "__main__":
    main()
