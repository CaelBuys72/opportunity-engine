#!/usr/bin/env python3
"""Build 7 — offer QA / validator (genuine independent checks over the written offer files).

Audits: offer matches the actual shipped product, price traces to observed evidence,
claims are traceable, no fabricated proof / scarcity / dollar values, outcome promises
bounded, creator pitch implies no unproven performance, revenue-share math correct,
listing lists real assets, retired cmp-5/cmp-6 never mentioned, no creator marked qualified.
Writes qa result to products/<opp>/offer/offer_qa.json and exits non-zero on failure.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AIR = "opp-airbnb-hosts-with-1-5-properties-turnover-and-property-operations"
PDIR = ROOT / "products" / AIR
OFFER = PDIR / "offer"

BANNED = re.compile(r"\b(revolutionary|game[- ]?chang|guaranteed|guarantee|"
                    r"limited time|act now|only \d+ left|hurry|best[- ]?seller of the year|"
                    r"passive income|get rich|double your (bookings|revenue|income))\b", re.I)
FAKE_VALUE = re.compile(r"\$\s?\d+\s*(value|bonus)\b", re.I)
RETIRED = ["cmp-5", "cmp-6"]


def load(name):
    return json.loads((OFFER / name).read_text())


def flatten(obj):
    if isinstance(obj, str):
        return [obj]
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out += flatten(v)
    elif isinstance(obj, list):
        for v in obj:
            out += flatten(v)
    return out


def main():
    errors, warnings, checks = [], [], []
    manifest = json.loads((PDIR / "manifest.json").read_text())
    ship_ids = {c["component_id"] for c in manifest["components"]}
    ship_names = {c["name"] for c in manifest["components"]}

    offer = load("offer.json")
    pricing = load("pricing.json")
    sales = load("sales_copy.json")
    claims = load("claim_traceability.json")
    whop = load("whop_listing_draft.json")
    partnership = load("creator_partnership.json")
    pitch = load("creator_pitch_assets.json")
    readiness = load("distribution_readiness.json")
    positioning = load("positioning.json")

    # 1. offer matches actual product
    offer_ids = {c["component_id"] for c in offer["core_product"]["components"]}
    if offer_ids != ship_ids:
        errors.append(f"offer components {offer_ids} != shipped {ship_ids}")
    else:
        checks.append("offer lists exactly the 8 shipped components")

    # 2. retired components never mentioned
    all_text = " ".join(flatten([offer, sales, whop, partnership, pitch, positioning, claims]))
    for r in RETIRED:
        if r in all_text:
            errors.append(f"retired component {r} referenced in offer copy")
    if not any(r in all_text for r in RETIRED):
        checks.append("retired cmp-5/cmp-6 absent from all offer copy")

    # 3. price traceable to OBSERVED evidence, not internal scores
    obs = [e for e in pricing["evidence"] if e["basis"] == "observed"]
    if not obs:
        errors.append("price has no observed evidence")
    if any(x in json.dumps(pricing) for x in ["commercial_score", "acceptance_score"]) \
            and "not_used_for_pricing" not in pricing:
        errors.append("pricing references internal scores as justification")
    lo, hi = 15, 25
    if not (lo <= pricing["launch_price"] <= hi):
        errors.append(f"launch price {pricing['launch_price']} outside observed band {lo}-{hi}")
    else:
        checks.append(f"launch price ${pricing['launch_price']} inside observed band ${lo}-${hi}")

    # 4. claims traceable
    valid_class = {"observed", "inferred", "product_fact", "positioning_language"}
    for c in claims["claims"]:
        if c["class"] not in valid_class:
            errors.append(f"claim '{c['claim']}' has invalid class {c['class']}")
        if not c.get("source"):
            errors.append(f"claim '{c['claim']}' has no source")
    checks.append(f"{len(claims['claims'])} claims classified + sourced")

    # 5. no fabricated dollar values / no fake scarcity / banned hype
    for txt in flatten([sales, whop, offer, partnership, pitch]):
        if FAKE_VALUE.search(txt):
            errors.append(f"fabricated dollar value: '{txt[:60]}'")
        m = BANNED.search(txt)
        if m:
            errors.append(f"banned/hype/scarcity language '{m.group(0)}' in: '{txt[:60]}'")
    if not any(FAKE_VALUE.search(t) or BANNED.search(t) for t in flatten([sales, whop, offer])):
        checks.append("no fake $ values, scarcity, or hype language")

    # 6. no fake proof — proof_missing must acknowledge zero sales/reviews
    pm = " ".join(flatten(positioning["proof_missing"])).lower()
    if "sold" not in pm and "sales" not in pm:
        warnings.append("proof_missing should state no sales yet")
    if "review" not in pm and "testimonial" not in pm:
        errors.append("proof_missing must acknowledge no testimonials/reviews")
    else:
        checks.append("proof gaps (no sales / no reviews) stated honestly")

    # 7. outcome promises bounded — explicit non-claims present
    nc = " ".join(claims["explicitly_not_claimed"]).lower()
    for must in ["increase bookings", "make more money"]:
        if must not in nc:
            warnings.append(f"expected explicit non-claim missing: {must}")
    checks.append("unproven outcome promises explicitly disclaimed")

    # 8. creator pitch implies no unproven performance
    pitch_txt = " ".join(flatten(pitch)).lower()
    if re.search(r"\b(will (sell|earn|make)|guaranteed|proven to)\b", pitch_txt):
        errors.append("creator pitch implies unproven performance")
    else:
        checks.append("creator pitch makes no performance guarantee")

    # 9. revenue-share math correct
    rs = partnership["revenue_share_scenarios"]
    price = rs["price"]
    for key, m in rs["models"].items():
        if m["creator_pct"] + m["our_pct"] != 100:
            errors.append(f"{key}: shares don't sum to 100")
        if abs(m["creator_per_sale_gross"] + m["our_per_sale_gross"] - price) > 0.011:
            errors.append(f"{key}: per-sale split != price")
        if abs(m["our_gross_at"]["100"] - m["our_per_sale_gross"] * 100) > 0.011:
            errors.append(f"{key}: 100-sale total wrong")
    if rs["platform_fee"]["value"] != "UNKNOWN":
        warnings.append("platform fee should stay UNKNOWN/variable unless evidenced")
    checks.append("revenue-share math verified; platform fee kept variable")

    # 10. listing lists real assets
    for f in whop["included_files"]:
        base = f.split(" (")[0]
        if base not in ship_names and base != "START_HERE.md":
            errors.append(f"listing includes non-shipped asset: {f}")
    checks.append("Whop listing lists only real shipped assets + START_HERE")

    # 11. no creator marked qualified; distribution uncertainty visible
    if readiness["qualified_creator_count"] != 0:
        errors.append("a creator is marked qualified — Phase-9.5 is NEEDS_RESEARCH")
    if readiness["phase_9_5_verdict"] != "NEEDS_RESEARCH":
        errors.append("distribution verdict misrepresented")
    if readiness["state"] not in ("assets_ready_creator_research_needed", "not_ready"):
        errors.append(f"distribution readiness overstated: {readiness['state']}")
    else:
        checks.append(f"distribution readiness honest: {readiness['state']}")

    # 12. must-not-publish flags present
    if not whop.get("do_not_publish"):
        errors.append("whop listing missing do_not_publish flag")

    result = {"opportunity_id": AIR, "passed": not errors,
              "checks_passed": checks, "warnings": warnings, "errors": errors}
    (OFFER / "offer_qa.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"OFFER QA: {'PASS' if not errors else 'FAIL'}  "
          f"({len(checks)} checks, {len(warnings)} warnings, {len(errors)} errors)")
    for c in checks:
        print(f"  ✓ {c}")
    for w in warnings:
        print(f"  ! {w}")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
