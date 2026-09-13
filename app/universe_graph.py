"""Universe Explorer — graph VIEW MODEL over the canonical universe.

This is a READ-ONLY projection. It does NOT own or mutate any universe data —
it joins the same collections UniverseService already reads (markets, submarkets,
audiences, problems, opportunities + score/pipeline side collections) into the
progressive node/edge shape the Explorer front-end consumes.

Hierarchy exposed by expansion:
    market --contains--> submarket --contains--> audience
    audience --has_problem--> problem --forms_opportunity--> opportunity (leaf)

Honesty: counts are DERIVED from data every call (never hardcoded). Missing
downstream data surfaces as 0 / "unknown", never fabricated.
"""
from __future__ import annotations
import json
from collections import defaultdict

from universe import UniverseStore, UniverseService, UNIVERSE_DIR

TYPE_BY_PREFIX = {
    "mkt-": "market",
    "sub-": "submarket",
    "aud-": "audience",
    "prb-": "problem",
    "opp-": "opportunity",
}


def node_type(node_id: str) -> str | None:
    for prefix, t in TYPE_BY_PREFIX.items():
        if node_id.startswith(prefix):
            return t
    return None


def _truncate(s: str, n: int = 80) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


class GraphService:
    """Builds the {focus, nodes, edges} view model with derived counts."""

    def __init__(self, svc: UniverseService | None = None):
        self.svc = svc or UniverseService(UniverseStore())
        s = self.svc
        # ---- derived relationship indexes (built once per request) ----
        self.subs_by_market: dict[str, list[dict]] = defaultdict(list)
        for sub in s._s.values():
            self.subs_by_market[sub["market_id"]].append(sub)

        self.auds_by_sub: dict[str, list[dict]] = defaultdict(list)
        for aud in s._a.values():
            self.auds_by_sub[aud["submarket_id"]].append(aud)

        self.probs_by_aud: dict[str, list[dict]] = defaultdict(list)
        for p in s._p.values():
            self.probs_by_aud[p["audience_id"]].append(p)

        self.opps_by_aud: dict[str, list[dict]] = defaultdict(list)
        self.opps_by_problem: dict[str, list[dict]] = defaultdict(list)
        for o in s._o.values():
            self.opps_by_aud[o["audience_id"]].append(o)
            for pid in o.get("problem_ids", []):
                self.opps_by_problem[pid].append(o)

        # ---- dynamic-expansion metadata (per-node cache state) ----
        f = UNIVERSE_DIR / "expansion_state.json"
        try:
            self._exp = json.loads(f.read_text()) if f.exists() else {}
        except json.JSONDecodeError:
            self._exp = {}
        self._rec_by_type = {"market": s._m, "submarket": s._s, "audience": s._a,
                             "problem": s._p, "opportunity": s._o}

    # nodes at these levels can be grown by live research (Explore Deeper)
    _RESEARCHABLE = {"market", "submarket", "audience"}

    def _annotate(self, node: dict) -> dict:
        """Attach provenance + dynamic-expansion status the Explorer uses to decide
        whether to show 'Explore Deeper'."""
        rec = self._rec_by_type.get(node["type"], {}).get(node["id"], {})
        node["origin"] = rec.get("origin", "seeded")
        node["researchable"] = node["type"] in self._RESEARCHABLE
        st = self._exp.get(node["id"], {})
        node["expansion_status"] = (st.get("expansion_status")
                                    or ("expanded" if node["child_count"] > 0 else "unexplored"))
        if st.get("researched_at"):
            node["researched_at"] = st["researched_at"]
        return node

    # ---------------------------------------------------------------- counts
    def _market_counts(self, market_id: str) -> dict:
        subs = self.subs_by_market.get(market_id, [])
        auds = [a for sub in subs for a in self.auds_by_sub.get(sub["id"], [])]
        probs = sum(len(self.probs_by_aud.get(a["id"], [])) for a in auds)
        opps = sum(len(self.opps_by_aud.get(a["id"], [])) for a in auds)
        return {"submarkets": len(subs), "audiences": len(auds),
                "problems": probs, "opportunities": opps}

    def _submarket_counts(self, submarket_id: str) -> dict:
        auds = self.auds_by_sub.get(submarket_id, [])
        probs = sum(len(self.probs_by_aud.get(a["id"], [])) for a in auds)
        opps = sum(len(self.opps_by_aud.get(a["id"], [])) for a in auds)
        return {"audiences": len(auds), "problems": probs, "opportunities": opps}

    def _audience_counts(self, audience_id: str) -> dict:
        return {"problems": len(self.probs_by_aud.get(audience_id, [])),
                "opportunities": len(self.opps_by_aud.get(audience_id, []))}

    # ---------------------------------------------------------------- node builders
    def _market_node(self, m: dict) -> dict:
        c = self._market_counts(m["id"])
        return {"id": m["id"], "type": "market", "label": m["name"],
                "expandable": c["submarkets"] > 0, "child_count": c["submarkets"],
                "meta": {**c, "description": m.get("description", ""),
                         "basis": m.get("basis", "unknown")}}

    def _submarket_node(self, s: dict) -> dict:
        c = self._submarket_counts(s["id"])
        return {"id": s["id"], "type": "submarket", "label": s["name"],
                "expandable": c["audiences"] > 0, "child_count": c["audiences"],
                "meta": {**c, "market_id": s["market_id"],
                         "basis": s.get("basis", "unknown")}}

    def _audience_node(self, a: dict) -> dict:
        c = self._audience_counts(a["id"])
        return {"id": a["id"], "type": "audience", "label": a["name"],
                "expandable": c["problems"] > 0, "child_count": c["problems"],
                "meta": {**c, "market_id": a.get("market_id"),
                         "submarket_id": a.get("submarket_id"),
                         "creator_density": a.get("creator_density", "unknown"),
                         "research_status": a.get("research_status", "unknown"),
                         "basis": a.get("basis", "unknown")}}

    def _problem_node(self, p: dict) -> dict:
        opp_ct = len(self.opps_by_problem.get(p["id"], []))
        return {"id": p["id"], "type": "problem",
                "label": _truncate(p.get("normalized_problem") or p.get("statement"), 46),
                "expandable": opp_ct > 0, "child_count": opp_ct,
                "meta": {"opportunities": opp_ct,
                         "problem_type": p.get("problem_type", "unknown"),
                         "confidence": p.get("confidence", "unknown"),
                         "evidence_count": p.get("evidence_count", 0),
                         "audience_id": p.get("audience_id")}}

    def _opportunity_node(self, o: dict) -> dict:
        score = self.svc.score_for_opportunity(o["id"]) or {}
        return {"id": o["id"], "type": "opportunity",
                "label": _truncate(o.get("name"), 46),
                "expandable": False, "child_count": 0,
                "meta": {"audience_id": o.get("audience_id"),
                         "problem_count": o.get("problem_count", len(o.get("problem_ids", []))),
                         "commercial_score": score.get("commercial_score"),
                         "priority_score": score.get("priority_score"),
                         "priority_classification": score.get("priority_classification", "unknown")}}

    # ---------------------------------------------------------------- graph queries
    def roots(self) -> dict:
        """Initial view: all markets, no edges. Sorted by downstream richness."""
        nodes = [self._annotate(self._market_node(m)) for m in self.svc.markets()]
        nodes.sort(key=lambda n: (-n["meta"]["opportunities"],
                                  -n["meta"]["problems"], n["label"]))
        return {"focus": None, "nodes": nodes, "edges": []}

    def children(self, node_id: str) -> dict | None:
        """Children of one node as {focus, nodes, edges}. None if node unknown."""
        t = node_type(node_id)
        nodes: list[dict] = []
        edge_type = "contains"
        if t == "market":
            if node_id not in self.svc._m:
                return None
            children = [self._submarket_node(s)
                        for s in self.subs_by_market.get(node_id, [])]
        elif t == "submarket":
            if node_id not in self.svc._s:
                return None
            children = [self._audience_node(a)
                        for a in self.auds_by_sub.get(node_id, [])]
        elif t == "audience":
            if node_id not in self.svc._a:
                return None
            edge_type = "has_problem"
            children = [self._problem_node(p)
                        for p in self.probs_by_aud.get(node_id, [])]
        elif t == "problem":
            if node_id not in self.svc._p:
                return None
            edge_type = "forms_opportunity"
            children = [self._opportunity_node(o)
                        for o in self.opps_by_problem.get(node_id, [])]
        elif t == "opportunity":
            if node_id not in self.svc._o:
                return None
            children = []  # leaf
        else:
            return None

        # keep children stable & readable
        children = [self._annotate(c) for c in children]
        children.sort(key=lambda n: (not n["expandable"], n["label"]))
        edges = [{"source": node_id, "target": c["id"], "type": edge_type}
                 for c in children]
        return {"focus": node_id, "nodes": children, "edges": edges}

    def node(self, node_id: str) -> dict | None:
        """The single node's own view-model record (for focusing search hits)."""
        t = node_type(node_id)
        if t == "market" and node_id in self.svc._m:
            return self._annotate(self._market_node(self.svc._m[node_id]))
        if t == "submarket" and node_id in self.svc._s:
            return self._annotate(self._submarket_node(self.svc._s[node_id]))
        if t == "audience" and node_id in self.svc._a:
            return self._annotate(self._audience_node(self.svc._a[node_id]))
        if t == "problem" and node_id in self.svc._p:
            return self._annotate(self._problem_node(self.svc._p[node_id]))
        if t == "opportunity" and node_id in self.svc._o:
            return self._annotate(self._opportunity_node(self.svc._o[node_id]))
        return None

    def ancestors(self, node_id: str) -> list[str]:
        """Ancestor node IDs from market down to (excluding) node_id."""
        s = self.svc
        t = node_type(node_id)
        if t == "market":
            return []
        if t == "submarket":
            sub = s._s.get(node_id)
            return [sub["market_id"]] if sub else []
        if t == "audience":
            a = s._a.get(node_id)
            return [a["market_id"], a["submarket_id"]] if a else []
        if t == "problem":
            p = s._p.get(node_id)
            return [p["market_id"], p["submarket_id"], p["audience_id"]] if p else []
        if t == "opportunity":
            o = s._o.get(node_id)
            if not o:
                return []
            chain = [o["market_id"], o["submarket_id"], o["audience_id"]]
            # opportunities hang off a PROBLEM node — include one member problem so
            # focusing reveals the opportunity (audience -> problem -> opportunity).
            member = next((pid for pid in o.get("problem_ids", []) if pid in s._p), None)
            if member:
                chain.append(member)
            return chain
        return []

    # ---------------------------------------------------------------- search
    def search_index(self) -> list[dict]:
        """Flat, query-independent index of every node. The front-end filters and
        ranks this client-side, so the same data serves both the live endpoint and
        the static export."""
        s = self.svc
        out: list[dict] = []

        def entry(node_id, label, text):
            out.append({"id": node_id, "type": node_type(node_id),
                        "label": _truncate(label, 70),
                        "text": (text or "").lower(),
                        "path": self._path(node_id),
                        "ancestors": self.ancestors(node_id)})

        for m in s._m.values():
            entry(m["id"], m["name"], m["name"])
        for sub in s._s.values():
            entry(sub["id"], sub["name"], sub["name"])
        for a in s._a.values():
            entry(a["id"], a["name"], a["name"])
        for p in s._p.values():
            entry(p["id"], p.get("statement", ""),
                  p.get("statement", "") + " " + p.get("normalized_problem", ""))
        for o in s._o.values():
            entry(o["id"], o["name"], o["name"] + " " + o.get("description", ""))
        return out

    def search(self, q: str, limit: int = 25) -> list[dict]:
        q = (q or "").strip().lower()
        if not q:
            return []
        order = {"market": 0, "submarket": 1, "audience": 2, "problem": 3, "opportunity": 4}
        hits = [h for h in self.search_index() if q in h["text"]]
        hits.sort(key=lambda h: (h["label"].lower().find(q) != 0, order.get(h["type"], 9)))
        for h in hits:
            h.pop("text", None)          # not needed by the live endpoint response
        return hits[:limit]

    def _path(self, node_id: str) -> list[str]:
        """Human-readable ancestor names (for search-result context)."""
        s = self.svc
        t = node_type(node_id)
        if t == "opportunity":
            return s.path_for_opportunity(node_id) or []
        if t == "problem":
            return s.path_for_problem(node_id) or []
        if t == "audience":
            return s.path_for_audience(node_id) or []
        if t == "submarket":
            sub = s._s.get(node_id)
            if not sub:
                return []
            m = s._m.get(sub["market_id"])
            return [m["name"] if m else "?", sub["name"]]
        if t == "market":
            m = s._m.get(node_id)
            return [m["name"]] if m else []
        return []
