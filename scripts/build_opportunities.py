#!/usr/bin/env python3
"""Build 3 — cluster an audience's raw problems into commercial opportunities.

    python3 scripts/build_opportunities.py <audience-id>              # automatic clustering
    python3 scripts/build_opportunities.py <audience-id> --manual     # manual file (data/opportunity_clusters/<id>.json)
    python3 scripts/build_opportunities.py <audience-id> --manual <f> # explicit manual file
    python3 scripts/build_opportunities.py --all-test-audiences [--manual]
    python3 scripts/build_opportunities.py --validate                # validate all persisted opportunities
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import opportunities as O                  # noqa: E402

TEST_AUDIENCES = [
    "aud-travel-and-hospitality-short-term-rentals-airbnb-hosts-with-1-5-properties",
    "aud-beauty-and-personal-care-nail-services-independent-nail-technicians",
    "aud-freelancing-and-solopreneurship-freelance-operations-and-admin-freelancers-with-inconsistent-irregular-income",
    "aud-content-creation-and-creator-economy-short-form-video-creators-trying-to-post-consistently-on-reels-tiktok",
    "aud-pets-and-animal-care-dog-training-new-puppy-owners-in-the-first-weeks",
]


def run_one(aid, mode, manual_file):
    r = O.cluster(aid, manual_file=manual_file, mode=mode)
    print(f"\n▣ {' -> '.join(r['path'])}   [{r['mode']}]")
    print(f"  {r['problem_count']} problems -> {r['opportunity_count']} opportunities")
    for o in r["opportunities"]:
        print(f"    - {o['name']}  ({o['problem_count']} problems · basis={o['basis']} · {o['confidence']})")
    for rej in r["rejected"]:
        print(f"    ✗ rejected: {rej.get('name', rej.get('members'))} — {rej['reason']}")
    return r


def main():
    args = sys.argv[1:]
    if "--validate" in args:
        try:
            r = O.validate_all()
        except O.OpportunityValidationError as e:
            raise SystemExit(f"✗ Opportunity validation FAILED:\n{e}")
        print(f"Opportunities: {r['opportunities']} | observed: {r['observed']} | "
              f"inferred: {r['inferred']} | mixed: {r['mixed']} | Validation: PASS")
        return

    manual = "--manual" in args
    manual_file = None
    if manual:
        i = args.index("--manual")
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            manual_file = args[i + 1]
    mode = "manual" if manual else "auto"

    try:
        if "--all-test-audiences" in args:
            for aid in TEST_AUDIENCES:
                run_one(aid, mode, None)
        else:
            aid = next((a for a in args if a.startswith("aud-")), None)
            if not aid:
                raise SystemExit("usage: build_opportunities.py <audience-id> [--manual [file]] | --all-test-audiences | --validate")
            run_one(aid, mode, manual_file)
    except (ValueError, O.OpportunityValidationError) as e:
        raise SystemExit(f"✗ Clustering refused (honest failure): {e}")


if __name__ == "__main__":
    main()
