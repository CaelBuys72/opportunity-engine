"""Discovery + clustering + scoring logic.

Pipeline the runner drives:
  observations (real quotes w/ source URLs)
    -> cluster() groups them into underlying problems
    -> a ProfitPocket bundles an audience + related problems + evidence
    -> compute_score() produces factor + overall scores + confidence

Design rules enforced here:
  * Nothing numeric is invented. A factor with basis 'unknown' has score=None
    and is EXCLUDED from the overall (weight renormalised), never counted as 0,
    so 'we don't know' never masquerades as 'this is bad'. The unknown weight
    is reported separately and drags confidence, not the score.
  * Evidence and inference stay distinguishable at the factor level.
"""
from __future__ import annotations
from collections import defaultdict

# Phase 5 weights (sum = 100)
WEIGHTS = {
    "demand_evidence": 20,
    "pain_importance": 15,
    "clear_outcome": 10,
    "existing_wtp": 15,
    "solution_gap": 15,
    "creator_density": 15,
    "digital_product_fit": 10,
}
FACTOR_ORDER = list(WEIGHTS.keys())


def cluster(observations: list[dict]) -> list[dict]:
    """Roll individual symptoms up into underlying problems.

    Each observation may carry `problem_key` (curated) and `problem_statement`.
    Observations sharing a key collapse into one Problem with its symptoms and
    evidence_ids gathered — this is the symptom -> related -> cluster step.
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for ob in observations:
        key = ob.get("problem_key") or ob["quote_or_observation"][:40].lower()
        if key not in groups:
            groups[key] = {
                "id": f"prob-{key}",
                "statement": ob.get("problem_statement", key),
                "symptoms": [],
                "evidence_ids": [],
            }
            order.append(key)
        g = groups[key]
        if ob["quote_or_observation"] not in g["symptoms"]:
            g["symptoms"].append(ob["quote_or_observation"])
        if ob["id"] not in g["evidence_ids"]:
            g["evidence_ids"].append(ob["id"])
    return [groups[k] for k in order]


def _normalise_factors(factors: dict) -> dict:
    """Ensure every factor exists with a weight and a valid basis."""
    out = {}
    for name in FACTOR_ORDER:
        f = dict(factors.get(name, {}))
        f["weight"] = WEIGHTS[name]
        basis = f.get("basis", "unknown")
        if basis == "unknown":
            f["score"] = None
        f.setdefault("basis", basis)
        f.setdefault("rationale", "")
        out[name] = f
    return out


def derive_confidence(factors: dict) -> tuple[str, str]:
    n_obs = sum(1 for f in factors.values() if f["basis"] == "observed")
    n_unk = sum(1 for f in factors.values() if f["basis"] == "unknown")
    demand = factors["demand_evidence"]["basis"]
    wtp = factors["existing_wtp"]["basis"]
    if n_obs >= 5 and demand == "observed":
        level = "HIGH"
    elif n_unk >= 3 or demand == "unknown":
        level = "LOW"
    else:
        level = "MEDIUM"
    reason = f"{n_obs}/7 factors observed, {n_unk}/7 unknown; demand={demand}, WTP={wtp}."
    return level, reason


def compute_score(factors: dict) -> dict:
    factors = _normalise_factors(factors)
    known_weight = sum(f["weight"] for f in factors.values() if f["score"] is not None)
    if known_weight > 0:
        raw = sum((f["score"] / 10) * f["weight"]
                  for f in factors.values() if f["score"] is not None)
        overall = round(raw / known_weight * 100, 1)
    else:
        overall = 0.0
    unknown_weight = 100 - known_weight
    level, reason = derive_confidence(factors)
    return {
        "factors": factors,
        "overall": overall,
        "confidence": level,
        "confidence_reason": reason,
        "weight_unknown_pct": unknown_weight,
    }


def rank(pockets: list[dict]) -> list[dict]:
    return sorted(pockets, key=lambda p: p["score"]["overall"], reverse=True)
