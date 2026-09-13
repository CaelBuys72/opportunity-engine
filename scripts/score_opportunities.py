#!/usr/bin/env python3
"""Build 4 — score & rank opportunities (commercial + evidence + priority).

    python3 scripts/score_opportunities.py --all       # score every opportunity, write rankings
    python3 scripts/score_opportunities.py <opp-id>    # score one (prints; does not persist rankings)
    python3 scripts/score_opportunities.py --validate  # validate persisted scores + rankings

Optional single-opp inputs: --commercial-input <file>  --creator-input <file>
Non-mutating: writes data/universe/opportunity_scores.json + opportunity_rankings.json only.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import scoring as S                        # noqa: E402
from universe import UniverseService      # noqa: E402


def _fmt(s):
    return (f"  {s['priority_classification']:<24} P={s['priority_score']:>3}  "
            f"C={s['commercial_score']:>3}  E={s['evidence_score']:>3}  "
            f"density={s['creator_density']:<9}  {s['name']}")


def main():
    args = sys.argv[1:]
    if "--validate" in args:
        try:
            r = S.validate_scores()
        except S.ScoringValidationError as e:
            raise SystemExit(f"✗ Scoring validation FAILED:\n{e}")
        print(f"Scores: {r['scores']} | Rankings: {r['rankings']} | Validation: PASS")
        return

    if "--all" in args:
        r = S.run_all()
        print(f"\nScored {r['scored']} opportunities (scoring_version {S.SCORING_VERSION}).\n")
        print("RANKED (by priority_score):")
        for row in r["rankings"]:
            s = next(x for x in r["scores"] if x["opportunity_id"] == row["opportunity_id"])
            print(f"  {row['rank']:>2}. " + _fmt(s).strip())
        print(f"\nWrote data/universe/opportunity_scores.json + opportunity_rankings.json")
        return

    oid = next((a for a in args if a.startswith("opp-")), None)
    if not oid:
        raise SystemExit("usage: score_opportunities.py --all | <opp-id> | --validate")
    svc = UniverseService()
    opp = svc.get_opportunity(oid)
    if not opp:
        raise SystemExit(f"✗ no opportunity '{oid}'")
    ci = next((args[i + 1] for i, a in enumerate(args) if a == "--commercial-input"), None)
    cr = next((args[i + 1] for i, a in enumerate(args) if a == "--creator-input"), None)
    s = S.score_one(opp, svc, commercial_file=ci, creator_file=cr)
    print(_fmt(s))
    for rf in s["risk_flags"]:
        print(f"      ⚠ {rf['flag']} ({rf['basis']}): {rf['reason']}")


if __name__ == "__main__":
    main()
