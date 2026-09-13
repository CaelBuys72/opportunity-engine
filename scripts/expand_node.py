#!/usr/bin/env python3
"""Expand a Universe node — the CLI twin of the Explorer's "Explore Deeper".

    # Live (needs SERPER_API_KEY + an LLM key): search -> classify -> persist
    python3 scripts/expand_node.py aud-...-people-overwhelmed-by-their-to-do-list

    # Search only (Serper set, no LLM): persist a raw packet for offline classification
    python3 scripts/expand_node.py <node_id> --packet-only

    # Offline import (no keys): persist a hand/agent-classified payload
    python3 scripts/expand_node.py <node_id> --import path/to/classified.json

The classified.json shape (audience level):
    { "level": "audience_problems", "ctx": {...},
      "evidence": [{"query","source_type","title","url","snippet"}...],
      "problems": [{"statement","normalized_problem","problem_type","desired_outcome",
                    "current_solutions":[],"attempts":[],"solution_complaints":[],
                    "source_refs":[<evidence indexes>],"basis","confidence"}...],
      "opportunities": [{"name","problem_ids":[<problem indexes|ids>],"buyer","core_problem",
                    "desired_outcome","current_solutions":[],"solution_gaps":[],
                    "possible_product","possible_format":[],"basis","confidence",
                    "basic_score":{...}}...] }
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import research_engine as RE  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("node_id")
    ap.add_argument("--import", dest="imp", help="path to a classified payload JSON")
    ap.add_argument("--packet-only", action="store_true", help="run search, save packet, stop")
    args = ap.parse_args()

    if args.imp:
        payload = json.loads(Path(args.imp).read_text())
        res = RE.import_classified(args.node_id, payload)
        print("imported (offline):", json.dumps(res))
        return

    if args.packet_only:
        level = RE._node_level(args.node_id)
        ctx = RE._node_ctx(args.node_id)
        packet = RE.run_search_packet(args.node_id, level, ctx)
        print(f"packet saved: {len(packet['evidence'])} evidence items → "
              f"data/research_packets/{args.node_id}.json")
        return

    try:
        res = RE.expand(args.node_id)
        print("expanded (live):", json.dumps(res))
    except RE.ProviderUnavailable as e:
        print(f"ProviderUnavailable: {e}", file=sys.stderr)
        print(f"providers: {RE.providers_status()}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
