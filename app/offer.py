"""Build 7 — thin read service over the offer package.

Non-mutating. Reads products/<opp>/offer/*.json produced by scripts/build_offer.py.
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ROOT / "products"


class OfferService:
    def __init__(self, opp_id: str):
        self.opp_id = opp_id
        self.dir = PRODUCTS / opp_id / "offer"

    def exists(self) -> bool:
        return (self.dir / "offer.json").exists()

    def _load(self, name: str):
        f = self.dir / name
        return json.loads(f.read_text()) if f.exists() else None

    def offer(self):
        return self._load("offer.json")

    def pricing(self):
        return self._load("pricing.json")

    def qa(self):
        return self._load("offer_qa.json")

    def distribution_readiness(self):
        return self._load("distribution_readiness.json")

    def qa_passed(self) -> bool:
        q = self.qa()
        return bool(q and q.get("passed"))

    def files(self):
        return sorted(p.name for p in self.dir.glob("*.json")) if self.dir.exists() else []
