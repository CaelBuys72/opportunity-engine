"""Storage abstraction — the single seam between the working pipeline and where
state lives. Two backends implement one interface:

    LocalBackend    — the exact local files used today (data/universe/*.json,
                      research/<opp>/*.json). Zero behaviour change for local dev/tests.
    SupabaseBackend — the shared, durable runtime store for the deployed app, over
                      Supabase's PostgREST HTTP API using stdlib urllib (no new deps).

Selected by env: STORAGE_BACKEND=local (default) | supabase.

Nothing here knows about research/curation logic — it only reads/writes the
collections, per-node expansion state, dossier files, usage, sessions, and an
atomic exploration claim used for two-operator concurrency.

Canonical IDs, node shapes and the research/<opp>/<name>.json dossier layout are
preserved 1:1 across both backends.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_DIR = ROOT / "data" / "universe"
RESEARCH_DIR = ROOT / "research"
NOW = lambda: datetime.now(timezone.utc).isoformat()

# universe collections stored as ROW sets (list of dicts keyed by "id")
ROW_COLLECTIONS = {"markets", "submarkets", "audiences", "problems", "opportunities",
                   "opportunity_scores", "opportunity_rankings", "problem_sources"}

# Collections whose unique row id lives under a field other than "id".
ROW_ID_KEYS = {"opportunity_scores": "opportunity_id",
               "opportunity_rankings": "opportunity_id",
               "problem_sources": "source_id"}


class StorageError(Exception):
    pass


def apply_usage(u: dict, event: dict) -> dict:
    """Fold one usage event into the rolling research_usage aggregate (search + LLM).
    Shared by both backends so the numbers match everywhere."""
    if not isinstance(u, dict):
        u = {}
    u["events_count"] = u.get("events_count", 0) + 1
    u["total_search_requests"] = u.get("total_search_requests", 0) + event.get("queries", 0)
    u["total_results"] = u.get("total_results", 0) + event.get("results", 0)
    u["total_llm_calls"] = u.get("total_llm_calls", 0) + event.get("calls", 0)
    u["total_llm_tokens"] = u.get("total_llm_tokens", 0) + event.get("tokens", 0)
    u["total_images"] = u.get("total_images", 0) + event.get("images", 0)
    by = u.setdefault("by_operator", {})
    op = by.setdefault(event.get("operator", "unknown"),
                       {"queries": 0, "results": 0, "llm_calls": 0, "llm_tokens": 0, "images": 0})
    op["queries"] = op.get("queries", 0) + event.get("queries", 0)
    op["results"] = op.get("results", 0) + event.get("results", 0)
    op["llm_calls"] = op.get("llm_calls", 0) + event.get("calls", 0)
    op["llm_tokens"] = op.get("llm_tokens", 0) + event.get("tokens", 0)
    op["images"] = op.get("images", 0) + event.get("images", 0)
    u["last_request_at"] = NOW()
    return u


# ==========================================================================
# interface
# ==========================================================================
class StorageBackend:
    name = "base"
    # --- universe row-collections ---
    def list_rows(self, collection: str) -> list[dict]: raise NotImplementedError
    def get_row(self, collection: str, _id: str) -> dict | None:
        return next((r for r in self.list_rows(collection) if r.get("id") == _id), None)
    def upsert_rows(self, collection: str, records: list[dict], key: str = "id") -> int: raise NotImplementedError
    def replace_collection(self, collection: str, records: list[dict]) -> None: raise NotImplementedError
    # --- per-node dynamic-expansion state ---
    def get_expansion(self, node_id: str) -> dict | None: raise NotImplementedError
    def all_expansion(self) -> dict: raise NotImplementedError
    def set_expansion(self, node_id: str, fields: dict) -> dict: raise NotImplementedError
    def claim_expansion(self, node_id: str, operator: str) -> bool:
        """Atomically claim a node for generation. True = you own it; False = already claimed."""
        raise NotImplementedError
    def release_expansion(self, node_id: str) -> None: raise NotImplementedError
    # --- research/curation/product dossier files: research/<opp>/<name>.json ---
    def read_dossier(self, opp_id: str) -> dict | None: raise NotImplementedError
    def read_dossier_file(self, opp_id: str, name: str): raise NotImplementedError
    def write_dossier_file(self, opp_id: str, name: str, obj) -> None: raise NotImplementedError
    # --- small singleton docs (pipeline_states, research_usage aggregate) ---
    def read_doc(self, name: str): raise NotImplementedError
    def write_doc(self, name: str, obj) -> None: raise NotImplementedError
    # --- usage attribution ---
    def record_usage(self, event: dict) -> None: raise NotImplementedError
    # --- sessions ---
    def put_session(self, token: str, operator: str, expires_at: float) -> None: raise NotImplementedError
    def get_session(self, token: str) -> dict | None: raise NotImplementedError
    def delete_session(self, token: str) -> None: raise NotImplementedError
    # --- binary object store (produced product bundles) ---
    def put_object(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None: raise NotImplementedError
    def get_object(self, path: str) -> bytes | None: raise NotImplementedError


# ==========================================================================
# LOCAL backend — byte-compatible with today's files
# ==========================================================================
class LocalBackend(StorageBackend):
    name = "local"

    def _cpath(self, name: str) -> Path:
        return UNIVERSE_DIR / f"{name}.json"

    def _read_json(self, path: Path, default):
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return default

    def _write_json(self, path: Path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))

    def list_rows(self, collection):
        d = self._read_json(self._cpath(collection), [])
        return d if isinstance(d, list) else []

    def upsert_rows(self, collection, records, key=None):
        key = key or ROW_ID_KEYS.get(collection, "id")
        existing = self.list_rows(collection)
        by_id = {r.get(key): r for r in existing}
        added = 0
        for r in records:
            if r.get(key) not in by_id:
                added += 1
            by_id[r.get(key)] = {**by_id.get(r.get(key), {}), **r}
        self._write_json(self._cpath(collection), list(by_id.values()))
        return added

    def replace_collection(self, collection, records):
        self._write_json(self._cpath(collection), records)

    def get_expansion(self, node_id):
        return self._read_json(self._cpath("expansion_state"), {}).get(node_id)

    def all_expansion(self):
        d = self._read_json(self._cpath("expansion_state"), {})
        return d if isinstance(d, dict) else {}

    def set_expansion(self, node_id, fields):
        st = self.all_expansion()
        cur = st.get(node_id, {}); cur.update(fields); st[node_id] = cur
        self._write_json(self._cpath("expansion_state"), st)
        return cur

    def claim_expansion(self, node_id, operator):
        st = self.all_expansion()
        cur = st.get(node_id, {})
        if cur.get("expansion_status") == "researching":
            # stale-claim guard: allow re-claim after 10 min
            started = cur.get("claim_at", 0)
            if isinstance(started, (int, float)) and (time.time() - started) < 600:
                return False
        cur.update({"expansion_status": "researching", "claimed_by": operator,
                    "claim_at": time.time()})
        st[node_id] = cur
        self._write_json(self._cpath("expansion_state"), st)
        return True

    def release_expansion(self, node_id):
        st = self.all_expansion()
        if node_id in st and st[node_id].get("expansion_status") == "researching":
            st[node_id]["expansion_status"] = "failed"
            self._write_json(self._cpath("expansion_state"), st)

    def read_dossier(self, opp_id):
        d = RESEARCH_DIR / opp_id
        if not d.exists():
            return None
        out = {}
        for f in d.glob("*.json"):
            try:
                out[f.stem] = json.loads(f.read_text())
            except json.JSONDecodeError:
                pass
        return out or None

    def read_dossier_file(self, opp_id, name):
        f = RESEARCH_DIR / opp_id / f"{name}.json"
        return json.loads(f.read_text()) if f.exists() else None

    def write_dossier_file(self, opp_id, name, obj):
        d = RESEARCH_DIR / opp_id
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False))

    def read_doc(self, name):
        return self._read_json(self._cpath(name), None)

    def write_doc(self, name, obj):
        self._write_json(self._cpath(name), obj)

    def record_usage(self, event):
        u = self._read_json(self._cpath("research_usage"), {})
        self._write_json(self._cpath("research_usage"), apply_usage(u, event))

    # sessions: a small local file (dev only)
    def _sessions(self):
        return self._read_json(UNIVERSE_DIR / "_sessions.json", {})

    def put_session(self, token, operator, expires_at):
        s = self._sessions(); s[token] = {"operator": operator, "expires_at": expires_at}
        self._write_json(UNIVERSE_DIR / "_sessions.json", s)

    def get_session(self, token):
        s = self._sessions().get(token)
        if not s:
            return None
        if s.get("expires_at", 0) < time.time():
            self.delete_session(token); return None
        return s

    def delete_session(self, token):
        s = self._sessions(); s.pop(token, None)
        self._write_json(UNIVERSE_DIR / "_sessions.json", s)

    def put_object(self, path, data, content_type="application/octet-stream"):
        p = ROOT / "products" / "_bundles" / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get_object(self, path):
        p = ROOT / "products" / "_bundles" / path
        return p.read_bytes() if p.exists() else None


# ==========================================================================
# SUPABASE backend — PostgREST over stdlib urllib (no third-party deps)
# ==========================================================================
class SupabaseBackend(StorageBackend):
    name = "supabase"

    def __init__(self, url: str, service_key: str):
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = service_key

    def _req(self, method, path, params="", body=None, prefer=None):
        url = f"{self.base}/{path}" + (f"?{params}" if params else "")
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
                   "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else []
        except urllib.error.HTTPError as e:
            raise StorageError(f"supabase {method} {path} -> {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            raise StorageError(f"supabase {method} {path} -> {e}")

    # --- universe rows (table: documents) ---
    def list_rows(self, collection):
        rows = self._req("GET", "documents",
                         f"collection=eq.{collection}&select=data&limit=100000")
        return [r["data"] for r in rows]

    def get_row(self, collection, _id):
        rows = self._req("GET", "documents",
                         f"collection=eq.{collection}&id=eq.{_id}&select=data")
        return rows[0]["data"] if rows else None

    def upsert_rows(self, collection, records, key=None):
        if not records:
            return 0
        key = key or ROW_ID_KEYS.get(collection, "id")
        payload = [{"collection": collection, "id": r.get(key),
                    "parent_id": r.get("parent_id") or r.get("market_id") or r.get("submarket_id")
                                 or r.get("audience_id"),
                    "data": r, "updated_at": NOW()} for r in records]
        self._req("POST", "documents", "", payload,
                  prefer="resolution=merge-duplicates,return=minimal")
        return len(payload)

    def replace_collection(self, collection, records):
        # upsert new/changed; (row deletes are rare here and skipped for MVP safety)
        self.upsert_rows(collection, records)

    # --- expansion_state (table: expansion_state) ---
    def get_expansion(self, node_id):
        rows = self._req("GET", "expansion_state", f"node_id=eq.{node_id}&select=data")
        return rows[0]["data"] if rows else None

    def all_expansion(self):
        rows = self._req("GET", "expansion_state", "select=node_id,data&limit=100000")
        return {r["node_id"]: r["data"] for r in rows}

    def set_expansion(self, node_id, fields):
        cur = self.get_expansion(node_id) or {}
        cur.update(fields)
        self._req("POST", "expansion_state", "",
                  [{"node_id": node_id, "status": cur.get("expansion_status"),
                    "data": cur, "updated_at": NOW()}],
                  prefer="resolution=merge-duplicates,return=minimal")
        return cur

    def claim_expansion(self, node_id, operator):
        # atomic: insert into exploration_claims (node_id PK); empty result = already claimed
        got = self._req("POST", "exploration_claims", "",
                        [{"node_id": node_id, "operator": operator, "claimed_at": NOW()}],
                        prefer="resolution=ignore-duplicates,return=representation")
        if not got:
            return False
        self.set_expansion(node_id, {"expansion_status": "researching", "claimed_by": operator})
        return True

    def release_expansion(self, node_id):
        self._req("DELETE", "exploration_claims", f"node_id=eq.{node_id}")

    # --- dossier files (table: dossier_files) ---
    def read_dossier(self, opp_id):
        rows = self._req("GET", "dossier_files", f"opp_id=eq.{opp_id}&select=name,data")
        return {r["name"]: r["data"] for r in rows} or None

    def read_dossier_file(self, opp_id, name):
        rows = self._req("GET", "dossier_files", f"opp_id=eq.{opp_id}&name=eq.{name}&select=data")
        return rows[0]["data"] if rows else None

    def write_dossier_file(self, opp_id, name, obj):
        self._req("POST", "dossier_files", "",
                  [{"opp_id": opp_id, "name": name, "data": obj, "updated_at": NOW()}],
                  prefer="resolution=merge-duplicates,return=minimal")

    # --- singleton docs (table: documents, collection='_doc') ---
    def read_doc(self, name):
        rows = self._req("GET", "documents", f"collection=eq._doc&id=eq.{name}&select=data")
        return rows[0]["data"] if rows else None

    def write_doc(self, name, obj):
        self._req("POST", "documents", "",
                  [{"collection": "_doc", "id": name, "data": obj, "updated_at": NOW()}],
                  prefer="resolution=merge-duplicates,return=minimal")

    def record_usage(self, event):
        # audit row + keep the rolling aggregate the UI reads live (was frozen before)
        self._req("POST", "usage_events", "", [{**event, "created_at": NOW()}],
                  prefer="return=minimal")
        try:
            self.write_doc("research_usage", apply_usage(self.read_doc("research_usage") or {}, event))
        except Exception:
            pass   # aggregate is best-effort; the audit row is the source of truth

    def put_session(self, token, operator, expires_at):
        self._req("POST", "sessions", "",
                  [{"token": token, "operator": operator, "expires_at": expires_at}],
                  prefer="resolution=merge-duplicates,return=minimal")

    def get_session(self, token):
        rows = self._req("GET", "sessions", f"token=eq.{token}&select=operator,expires_at")
        if not rows:
            return None
        s = rows[0]
        if float(s.get("expires_at", 0)) < time.time():
            self.delete_session(token); return None
        return {"operator": s["operator"], "expires_at": s["expires_at"]}

    def delete_session(self, token):
        self._req("DELETE", "sessions", f"token=eq.{token}")

    # --- binary object store: Supabase Storage bucket "products" ---
    _BUCKET = "products"

    def _ensure_bucket(self):
        base = self.base.rsplit("/rest/v1", 1)[0]
        url = f"{base}/storage/v1/bucket"
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
                   "Content-Type": "application/json"}
        body = json.dumps({"id": self._BUCKET, "name": self._BUCKET, "public": False}).encode()
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code not in (400, 409):        # already-exists is fine
                raise StorageError(f"supabase create bucket -> {e.code}: {e.read().decode()[:200]}")
        except urllib.error.URLError as e:
            raise StorageError(f"supabase create bucket -> {e}")

    def put_object(self, path, data, content_type="application/octet-stream"):
        self._ensure_bucket()
        base = self.base.rsplit("/rest/v1", 1)[0]
        url = f"{base}/storage/v1/object/{self._BUCKET}/{path}"
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
                   "Content-Type": content_type, "x-upsert": "true"}
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            raise StorageError(f"supabase put_object -> {e.code}: {e.read().decode()[:200]}")
        except urllib.error.URLError as e:
            raise StorageError(f"supabase put_object -> {e}")

    def get_object(self, path):
        base = self.base.rsplit("/rest/v1", 1)[0]
        url = f"{base}/storage/v1/object/{self._BUCKET}/{path}"
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        req = urllib.request.Request(url, method="GET", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise StorageError(f"supabase get_object -> {e.code}: {e.read().decode()[:200]}")
        except urllib.error.URLError as e:
            raise StorageError(f"supabase get_object -> {e}")


# ==========================================================================
# selection
# ==========================================================================
_BACKEND: StorageBackend | None = None


def get_backend() -> StorageBackend:
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    kind = os.environ.get("STORAGE_BACKEND", "local").lower()
    if kind == "supabase":
        url = os.environ.get("SUPABASE_URL")
        skey = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not skey:
            raise StorageError("STORAGE_BACKEND=supabase but SUPABASE_URL / "
                               "SUPABASE_SERVICE_ROLE_KEY are not set")
        _BACKEND = SupabaseBackend(url, skey)
    else:
        _BACKEND = LocalBackend()
    return _BACKEND
