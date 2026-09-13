#!/usr/bin/env python3
"""Idempotent import of the local seeded/generated Universe + research into Supabase.

Reads the LOCAL files directly and upserts them into Supabase via the same storage
interface used at runtime. Preserves IDs / parent relationships / provenance and is
safe to re-run (everything is an upsert; no duplicate rows).

Prereqs (env):
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY     # target project
Run:
    python3 scripts/migrate_to_supabase.py          # migrate everything
    python3 scripts/migrate_to_supabase.py --dry    # show what WOULD migrate

First run the schema in migrations/supabase_schema.sql.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
import storage  # noqa: E402

DRY = "--dry" in sys.argv


def main():
    if not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")):
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.")
    local = storage.LocalBackend()
    dest = None if DRY else storage.SupabaseBackend(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    def push_rows(coll):
        rows = local.list_rows(coll)
        print(f"  {coll}: {len(rows)} rows")
        if rows and dest:
            dest.upsert_rows(coll, rows)

    print("Universe row-collections:")
    for coll in sorted(storage.ROW_COLLECTIONS):
        push_rows(coll)

    print("Expansion state:")
    exp = local.all_expansion()
    print(f"  {len(exp)} nodes")
    if dest:
        for node_id, data in exp.items():
            dest.set_expansion(node_id, data)

    print("Singleton docs:")
    for name in ("pipeline_states", "research_usage", "universe_summary"):
        doc = local.read_doc(name)
        if doc is not None:
            print(f"  {name}")
            if dest:
                dest.write_doc(name, doc)

    print("Research/curation dossiers:")
    rdir = storage.RESEARCH_DIR
    count = 0
    if rdir.exists():
        for opp_dir in sorted(p for p in rdir.iterdir() if p.is_dir()):
            files = list(opp_dir.glob("*.json"))
            count += len(files)
            if dest:
                import json
                for f in files:
                    try:
                        dest.write_dossier_file(opp_dir.name, f.stem, json.loads(f.read_text()))
                    except json.JSONDecodeError:
                        print(f"    ! skipped invalid JSON: {f}")
    print(f"  {count} dossier files across research/")

    print("\nDRY RUN — nothing written." if DRY else "\nMigration complete (idempotent).")


if __name__ == "__main__":
    main()
