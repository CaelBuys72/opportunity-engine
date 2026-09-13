#!/usr/bin/env python3
"""Export the Universe Explorer's read API as STATIC JSON files.

Option A deploy: the Explorer is read-only, so instead of needing the Python
server live, we pre-render every response it fetches into plain .json files under
app/web/graph/. The front-end fetches those relative paths, which works both
locally (the Python server serves them as static files) and on static hosts
(Vercel), where no server runs.

    python3 scripts/export_static.py

Re-run this whenever the universe data changes (e.g. after build_universe.py or
after adding markets), commit the regenerated app/web/graph/, and push — the live
site updates on deploy. Deterministic: overwrites the same files each run.

Files written (mirror the live endpoints):
    graph/roots.json                 → all market nodes (initial view)
    graph/node/<id>.json             → children of one node {focus,nodes,edges}
    graph/search.json                → flat index for client-side search
    graph/opportunity/<id>.json      → opportunity detail (+path,+problems,+score)
    graph/problem/<id>.json          → problem detail (+path,+sources)
    graph/pipeline/<id>.json         → pipeline state (promoted opportunities only)
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from universe import UniverseStore, UniverseService          # noqa: E402
from universe_graph import GraphService                      # noqa: E402
import pipeline as PL                                        # noqa: E402

OUT = ROOT / "app" / "web" / "graph"


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False))


def main() -> None:
    svc = UniverseService(UniverseStore())
    gs = GraphService(svc)

    if OUT.exists():
        shutil.rmtree(OUT)                     # clean rebuild (drops stale nodes)
    OUT.mkdir(parents=True, exist_ok=True)

    # roots
    write(OUT / "roots.json", gs.roots())

    # children for every expandable level (markets, submarkets, audiences, problems)
    node_count = 0
    for coll in ("markets", "submarkets", "audiences"):
        for rec in svc.store.list(coll):
            res = gs.children(rec["id"])
            if res is not None:
                write(OUT / "node" / f"{rec['id']}.json", res)
                node_count += 1
    for pid in svc._p:                          # problems → opportunities
        res = gs.children(pid)
        if res is not None:
            write(OUT / "node" / f"{pid}.json", res)
            node_count += 1

    # search index (flat; the front-end filters/ranks client-side)
    write(OUT / "search.json", {"nodes": gs.search_index()})

    # problem detail
    for pid, p in svc._p.items():
        write(OUT / "problem" / f"{pid}.json",
              {**p, "path": svc.path_for_problem(pid), "sources": svc.problem_sources(pid)})

    # opportunity detail
    for oid, o in svc._o.items():
        write(OUT / "opportunity" / f"{oid}.json",
              {**o, "path": svc.path_for_opportunity(oid),
               "problems": svc.problems_for_opportunity(oid),
               "score": svc.score_for_opportunity(oid)})

    # pipeline state (only promoted opportunities have one)
    psvc = PL.PipelineService()
    pipe_count = 0
    for oid in svc._o:
        st = psvc.get_pipeline_state(oid)
        if st:
            write(OUT / "pipeline" / f"{oid}.json", st)
            pipe_count += 1

    print(f"Exported static graph → {OUT.relative_to(ROOT)}")
    print(f"  roots: 1 · node files: {node_count} · problems: {len(svc._p)} · "
          f"opportunities: {len(svc._o)} · pipeline: {pipe_count}")


if __name__ == "__main__":
    main()
