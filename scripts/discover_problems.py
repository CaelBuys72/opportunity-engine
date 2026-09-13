#!/usr/bin/env python3
"""Build 2 — discover raw problems for an audience.

    python3 scripts/discover_problems.py <audience-id>                 # import if present, else nothing
    python3 scripts/discover_problems.py <audience-id> --seed-inferred # add inferred candidates
    python3 scripts/discover_problems.py <audience-id> --import <file> # explicit import file
    python3 scripts/discover_problems.py --validate                   # validate all persisted problems

Modes combine: --import (or auto data/problem_sources/<id>.json) yields OBSERVED
problems; --seed-inferred adds INFERRED candidates. Both are stored honestly.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))

import problems as P                       # noqa: E402
from problem_seed import SEED as PROBLEM_SEED  # noqa: E402


def main():
    args = sys.argv[1:]
    if "--validate" in args:
        try:
            r = P.validate_all()
        except P.ProblemValidationError as e:
            raise SystemExit(f"✗ Problem validation FAILED:\n{e}")
        print(f"Problems: {r['problems']} | observed: {r['observed']} | inferred: {r['inferred']} | Validation: PASS")
        return

    if not args or args[0].startswith("--"):
        raise SystemExit("usage: python3 scripts/discover_problems.py <audience-id> [--seed-inferred] [--import <file>]")
    audience_id = args[0]
    seed_inferred = "--seed-inferred" in args
    import_file = None
    if "--import" in args:
        i = args.index("--import")
        import_file = args[i + 1] if i + 1 < len(args) else None

    try:
        r = P.discover(audience_id, import_file=import_file,
                       seed_inferred=seed_inferred, seed_lookup=PROBLEM_SEED)
    except (ValueError, P.ProblemValidationError) as e:
        raise SystemExit(f"✗ Discovery refused (honest failure): {e}")

    print(f"\n▣ Problem discovery: {' -> '.join(r['path'])}")
    print(f"  problems: {r['problem_count']}  (observed: {r['observed']}, inferred: {r['inferred']})")
    print(f"  retrieval: {r['retrieval'][0]['status']} ({r['retrieval'][0].get('count','-')} source(s))")
    obs = [p for p in r["problems"] if p["basis"] == "observed"]
    if obs:
        print("  observed problems (traced to sources):")
        for p in obs:
            print(f"    - [{p['confidence']}] {p['normalized_problem']} · {p['problem_type']} · {p['evidence_count']} src")
    print(f"  sample inferred: " + "; ".join(p["normalized_problem"] for p in r["problems"] if p["basis"] == "inferred")[:220])
    print(f"  stored in data/universe/problems.json ; audience.problem_count updated -> {r['problem_count']}")


if __name__ == "__main__":
    main()
