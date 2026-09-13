"""Storage abstraction for the Opportunity Intelligence Engine.

V1 persists each record as one JSON file under data/<collection>/<id>.json.
The Store interface is deliberately small (list/get/put/delete) so a database-
backed implementation can replace JsonStore later without touching callers.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"

COLLECTIONS = ["industries", "opportunities", "evidence", "communities", "creators"]


class Store:
    """Interface. Any backend (JSON, sqlite, postgres) implements these."""

    def list(self, collection: str) -> list[dict]: raise NotImplementedError
    def get(self, collection: str, _id: str) -> dict | None: raise NotImplementedError
    def put(self, collection: str, record: dict) -> dict: raise NotImplementedError
    def delete(self, collection: str, _id: str) -> bool: raise NotImplementedError


class JsonStore(Store):
    def __init__(self, data_dir: Path = DATA):
        self.data_dir = Path(data_dir)

    def _dir(self, collection: str) -> Path:
        d = self.data_dir / collection
        d.mkdir(parents=True, exist_ok=True)
        return d

    def list(self, collection: str) -> list[dict]:
        out = []
        for f in sorted(self._dir(collection).glob("*.json")):
            try:
                out.append(json.loads(f.read_text()))
            except json.JSONDecodeError:
                continue  # skip corrupt files rather than crash the whole app
        return out

    def get(self, collection: str, _id: str) -> dict | None:
        f = self._dir(collection) / f"{_id}.json"
        return json.loads(f.read_text()) if f.exists() else None

    def put(self, collection: str, record: dict) -> dict:
        if "id" not in record:
            raise ValueError("record needs an 'id'")
        f = self._dir(collection) / f"{record['id']}.json"
        f.write_text(json.dumps(record, indent=2, ensure_ascii=False))
        return record

    def delete(self, collection: str, _id: str) -> bool:
        f = self._dir(collection) / f"{_id}.json"
        if f.exists():
            f.unlink()
            return True
        return False


def write_output(relpath: str, payload: Any) -> Path:
    """Write a human/machine-facing artifact under outputs/."""
    p = OUTPUTS / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return p
