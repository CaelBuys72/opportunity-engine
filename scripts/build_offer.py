#!/usr/bin/env python3
"""Build 7 — turn the release-approved product into a market-ready SELLABLE OFFER.

Authors the offer package (positioning, offer, pricing, sales copy, claim traceability,
Whop listing draft, creator partnership + pitch drafts, creative briefs, distribution
readiness) under products/<opp>/offer/. Content is DRAFT/prep only.

Honesty rules enforced elsewhere by validate_offer / offer_qa:
- price traces to OBSERVED marketplace evidence, not to internal scores
- every meaningful claim classified: observed | inferred | product_fact | positioning_language
- no fabricated dollar values, no fake scarcity/reviews, no unproven outcome promises
- Phase-9.5 distribution uncertainty stays visible; NO creator marked qualified
- retired cmp-5/cmp-6 never referenced; offer lists only the 8 shipped components

This does NOT publish, contact creators, send anything, or take payment.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
AIR = "opp-airbnb-hosts-with-1-5-properties-turnover-and-property-operations"
PDIR = ROOT / "products" / AIR
RES = ROOT / "research" / AIR
OFFER = PDIR / "offer"

PRIMARY_NAME = "The Turnover System for Airbnb Hosts"
SUBTITLE = "A reliable, cleaner-ready operating kit for hosts with 1–5 properties."
LAUNCH_PRICE = 17
REFERENCE_PRICE = 24  # top of the OBSERVED researched band ($15–25); positioning anchor only

# ---- the 8 shipped components (source of truth = manifest) ----
def shipped_components():
    m = json.loads((PDIR / "manifest.json").read_text())
    return [{"component_id": c["component_id"], "name": c["name"], "type": c["type"],
             "formats": sorted({Path(f).suffix.lstrip(".") for f in c["files"]})}
            for c in m["components"]]


def write(name, obj):
    (OFFER / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def main():
    OFFER.mkdir(parents=True, exist_ok=True)
    comps = shipped_components()
    comp_names = [c["name"] for c in comps]

    # ---------------------------------------------------------------- positioning
    positioning = {
        "opportunity_id": AIR, "revision": "revision-001",
        "target_buyer": "Self-managing Airbnb / short-term-rental hosts with 1–5 properties "
                        "(US-first, English-speaking). Not property-manager-run portfolios, not large operators.",
        "current_state": "Turnovers run from memory and ad-hoc messages. Steps get missed between guests, "
                         "supplies run out, cleaner instructions are inconsistent, and DIY/Canva welcome-book "
                         "templates sometimes fail to save or print — losing the host's work.",
        "desired_state": "A repeatable operating system: every turnover done the same way, a cleaner who can "
                         "follow the standard without hand-holding, supplies tracked before they run out, and a "
                         "guest-ready welcome guide that just works.",
        "core_problem": "Running reliable, repeatable turnovers across cleaner coordination, supply restocking, "
                        "and guest-facing house info — without things falling through the cracks.",
        "product_mechanism": "A connected set of host-facing operational assets (setup workbook → guest guide → "
                             "turnover SOP → cleaner handoff → quick checklist → supply/inventory tracker → "
                             "damage log → message library) in reliable, editable file formats (Docs/Word, "
                             "Sheets/Excel, PDF) — not a fragile design-tool file.",
        "primary_outcome": "Every turnover done the same way, nothing forgotten, no broken templates.",
        "secondary_outcomes": [
            "A cleaner can run the turnover to your standard from one sheet.",
            "You stop running out of guest supplies unexpectedly.",
            "Damage/incidents are logged in one place instead of scattered messages.",
        ],
        "differentiators": [
            {"claim": "Reliability — standard editable formats that won't fail to save/print like a Canva file",
             "basis": "observed", "source": "evidence cl-3 (1-star review: template would not save/print)"},
            {"claim": "Operationally complete, not just a decorative welcome book",
             "basis": "inferred", "source": "analysis.solution_weaknesses / unmet_needs"},
            {"claim": "Standardized so a cleaner can actually follow it",
             "basis": "inferred", "source": "analysis.unmet_needs"},
        ],
        "objections": [
            {"objection": "I already bought a welcome-book template",
             "answer": "This is an operations system (turnover SOP, cleaner handoff, trackers), not another "
                       "welcome book — the guest guide is one part of eight."},
            {"objection": "I can make my own checklist",
             "answer": "You can — this is the assembled, cross-referenced version so you don't have to, and it "
                       "covers the steps hosts most often forget."},
            {"objection": "Another template that'll break?",
             "answer": "Delivered in standard Docs/Sheets/PDF that open and save normally; nothing depends on a "
                       "fragile design tool."},
        ],
        "limitations": [
            "Perceived value is the weakest measured dimension (~80/100); the category is competitive.",
            "This is a template/operations kit, not software or automation — the host still does the work.",
            "Not aimed at property-manager-run or large-portfolio operators.",
            "Distribution is unproven (see distribution_readiness.json).",
        ],
        "proof_available": [
            {"item": "Real marketplace demand + willingness to pay", "basis": "observed",
             "source": "evidence cl-4/cl-5: Etsy 1,000+ paid welcome-book listings, many Bestsellers"},
            {"item": "Concrete reliability pain in the incumbent solution", "basis": "observed",
             "source": "evidence cl-3: 1-star review, template would not save/print"},
            {"item": "The product is built, complete, and QA-passed (8/8 components)", "basis": "product_fact",
             "source": "manifest.json + qa/product_acceptance.json (84.6)"},
        ],
        "proof_missing": [
            "No sales of THIS product yet (zero units sold — validation is the point).",
            "No testimonials or reviews of this product (none exist; do not fabricate).",
            "No proven creator/distribution channel (Phase-9.5 = NEEDS_RESEARCH).",
            "No measured time-saved / review-score outcome data for buyers.",
        ],
    }
    write("positioning.json", positioning)

    # ---------------------------------------------------------------- naming
    naming = {
        "primary_name": PRIMARY_NAME, "subtitle": SUBTITLE,
        "why_primary": "Anchors the exact category (Airbnb host turnovers), frames the outcome as a repeatable "
                       "'system' rather than loose templates, and avoids hype/guru/AI language. Concrete and "
                       "searchable by the buyer's own words ('turnover').",
        "candidates": [
            {"name": "The Turnover System for Airbnb Hosts", "note": "selected — category + system outcome, plain"},
            {"name": "Host Turnover OS", "note": "punchy but 'OS' leans buzzword"},
            {"name": "The Reliable Turnover Kit", "note": "leads on the reliability wedge"},
            {"name": "Turnover Ready: Airbnb Host Operations Kit", "note": "outcome + category"},
            {"name": "The Short-Term Rental Turnover Playbook", "note": "broader STR framing, not just Airbnb"},
            {"name": "Cleaner-Ready: Airbnb Turnover & Setup System", "note": "leads on the cleaner-handoff angle"},
            {"name": "The Host Operations Kit (Airbnb Turnovers)", "note": "operations-first framing"},
            {"name": "Every Turnover the Same Way", "note": "pure promise; less searchable"},
        ],
        "avoided": ["'ultimate'", "fake luxury", "AI buzzwords", "exaggerated claims", "guru naming"],
    }
    write("naming.json", naming)

    # ---------------------------------------------------------------- offer architecture
    jobs = [
        ("Set the property up once", "Property Setup Workbook"),
        ("Give guests a guide that works", "Welcome Guide for Guests"),
        ("Define the turnover standard", "Master Turnover SOP"),
        ("Hand off to a cleaner cleanly", "Cleaner Handoff Sheet"),
        ("Run each turnover in the field", "Quick Turnover Checklist"),
        ("Never run out of supplies", "Supply + Inventory Tracker"),
        ("Track damage & incidents", "Damage & Incident Log"),
        ("Reply to guests fast", "Guest Message Library"),
    ]
    offer = {
        "opportunity_id": AIR, "revision": "revision-001",
        "product_name": PRIMARY_NAME, "subtitle": SUBTITLE,
        "core_product": {
            "what": "One connected turnover & property-operations system for hosts with 1–5 properties.",
            "components": comps,
            "component_count": len(comps),
            "jobs_solved": [{"job": j, "delivered_by": n} for j, n in jobs],
        },
        "bonuses": [
            {"name": "Guest Message Library", "note": "Included as a supporting asset. Labeled a bonus in the "
             "original spec (type=bonus); NOT a relabeled required component and NOT assigned a fake dollar value."}
        ],
        "delivery": {
            "method": "Instant digital download after purchase (no account/tool signup required).",
            "formats": "Editable Word/Google Docs (.docx), Excel/Google Sheets (.xlsx) + .csv, PDF, Markdown.",
            "onboarding": "START_HERE.md walks the buyer through the 8 steps in order.",
            "channel": "Whop listing (draft only — not published).",
        },
        "target_outcome": "Move from ad-hoc, memory-based turnovers to a repeatable, cleaner-ready, "
                          "guest-ready operating system.",
        "price": {"launch": LAUNCH_PRICE, "reference": REFERENCE_PRICE, "currency": "USD", "model": "one-time"},
        "risk_and_limitations": [
            "New product with no sales/reviews yet.",
            "Competitive template category; wedge is reliability + completeness, not novelty.",
            "Host still does the operational work — this is a system, not automation.",
        ],
        "who_it_is_for": [
            "Hosts self-managing 1–5 short-term rentals",
            "Hosts using (or about to hire) a cleaner they need to standardize",
            "Hosts burned by fragile Canva/welcome-book templates",
        ],
        "who_it_is_not_for": [
            "Large portfolios / professional property managers with existing PMS workflows",
            "Hosts who want done-for-you automation or software",
            "Hosts who only want a pretty welcome book and nothing operational",
        ],
    }
    write("offer.json", offer)

    # ---------------------------------------------------------------- pricing
    pricing = {
        "opportunity_id": AIR,
        "launch_price": LAUNCH_PRICE, "reference_price": REFERENCE_PRICE, "currency": "USD",
        "model": "one-time digital purchase",
        "evidence": [
            {"fact": "Etsy 'airbnb welcome book template' returns 1,000+ paid listings, many Bestsellers",
             "basis": "observed", "source": "evidence cl-5"},
            {"fact": "Comparable host welcome-book/checklist bundles sell at ~$14–21+",
             "basis": "observed", "source": "product_brief.price_rationale"},
            {"fact": "Researched target band = $15–25 one-time", "basis": "observed",
             "source": "product_brief.price_range"},
        ],
        "launch_rationale": "Priced at $17 — inside the observed band and deliberately low-friction. The immediate "
                            "objective is validation (one stranger pays), not lifetime-value optimization.",
        "reference_rationale": "$24 sits at the top of the OBSERVED band ($15–25); used only as a positioning "
                               "anchor, not as a fabricated 'was' price or fake discount.",
        "not_used_for_pricing": ["commercial_score", "acceptance_score (84.6)", "evidence_score"],
        "notes": ["Price is traceable ONLY to observed marketplace comps, never to internal scores.",
                  "No lifetime-value / upsell modeling at this stage (validation first)."],
    }
    write("pricing.json", pricing)

    # ---------------------------------------------------------------- sales copy
    sales_copy = {
        "opportunity_id": AIR, "product_name": PRIMARY_NAME,
        "one_sentence_offer": "A reliable, cleaner-ready turnover system for Airbnb hosts with 1–5 properties — "
                              "so every turnover is done the same way, nothing gets forgotten, and no template breaks.",
        "short_description": "Eight connected templates, checklists and trackers that turn ad-hoc, memory-based "
                             "turnovers into a repeatable operating system your cleaner can actually follow. "
                             "Standard editable files (Docs, Sheets, PDF) — not a fragile design-tool export.",
        "full_listing_description": (
            "Running a short-term rental turnover from memory means things get missed — a supply runs out, a step "
            "gets skipped, the cleaner does it differently each time, or the welcome-book template you paid for "
            "won't save or print.\n\n"
            f"{PRIMARY_NAME} is a connected set of eight host-facing assets that give you one repeatable way to "
            "run every turnover: set the property up once, hand your cleaner a standard they can follow, track "
            "supplies before you run out, log any damage, and give guests a welcome guide that just works.\n\n"
            "Everything is delivered in standard, editable formats (Word/Google Docs, Excel/Google Sheets, PDF) "
            "so it opens, edits, saves and prints normally. Start with the included START_HERE guide and work "
            "through the eight steps in order.\n\n"
            "This is an operating system, not software or automation — you still run your turnovers, but now "
            "there's a standard behind them."),
        "feature_benefit": [
            {"feature": "Property Setup Workbook", "benefit": "One source of truth per property — including the "
             "details hosts most often forget."},
            {"feature": "Master Turnover SOP", "benefit": "Your turnover done the same way every time, with a "
             "final-inspection standard."},
            {"feature": "Cleaner Handoff Sheet + Quick Checklist", "benefit": "Your cleaner runs it to your "
             "standard from one page."},
            {"feature": "Supply + Inventory Tracker", "benefit": "Auto-flags what to reorder before you run out."},
            {"feature": "Damage & Incident Log", "benefit": "Every issue tracked in one place, not scattered chats."},
            {"feature": "Welcome Guide + Guest Message Library", "benefit": "Guest-ready info and fast, consistent "
             "replies at every booking stage."},
        ],
        "whats_included": comp_names + ["START_HERE quick-start guide"],
        "who_its_for": offer["who_it_is_for"],
        "who_its_not_for": offer["who_it_is_not_for"],
        "faq": [
            {"q": "What format is it in?", "a": "Editable Word/Google Docs, Excel/Google Sheets (+CSV), PDF and "
             "Markdown. It opens and saves in the normal apps you already use."},
            {"q": "Is this just another welcome book?", "a": "No — the guest guide is one of eight parts. The core "
             "is the turnover operations system (SOP, cleaner handoff, trackers)."},
            {"q": "Will it work for more than one property?", "a": "Yes — the workbook and trackers are set up "
             "per property; it's aimed at hosts with 1–5 listings."},
            {"q": "Do I need special software?", "a": "No. Standard document and spreadsheet apps. No signup, no "
             "subscription."},
            {"q": "Is this automation?", "a": "No. It's a system you run — templates, checklists and trackers — "
             "not software that runs turnovers for you."},
        ],
        "objection_handling": positioning["objections"],
        "cta_variants": [
            "Get the turnover system",
            "Standardize your next turnover",
            "Download the kit",
            "Start running reliable turnovers",
        ],
        "banned_language_note": "Copy is deliberately plain: no hype superlatives, no fake urgency, no invented "
                                "reviews, and no income or booking promises. (Enforced by offer QA.)",
    }
    write("sales_copy.json", sales_copy)

    # ---------------------------------------------------------------- claim traceability
    claim_traceability = {
        "opportunity_id": AIR,
        "legend": {"observed": "backed by observed research evidence",
                   "inferred": "reasoned from research, not directly observed",
                   "product_fact": "verifiable fact about the shipped files",
                   "positioning_language": "framing/marketing phrasing, no factual claim"},
        "claims": [
            {"claim": "Eight connected assets / eight parts", "class": "product_fact",
             "source": "manifest.json (8 components)"},
            {"claim": "Delivered in editable Word/Docs, Excel/Sheets, PDF, Markdown", "class": "product_fact",
             "source": "manifest component files"},
            {"claim": "Supply tracker auto-flags what to reorder", "class": "product_fact",
             "source": "cmp-1 real reorder-status formula"},
            {"claim": "Hosts already pay for welcome-book/checklist templates", "class": "observed",
             "source": "evidence cl-4/cl-5"},
            {"claim": "Incumbent templates fail to save/print (reliability gap)", "class": "observed",
             "source": "evidence cl-3"},
            {"claim": "Cleaner coordination / restocking / house-manual are real recurring problems",
             "class": "observed", "source": "analysis.recurring_symptoms; evidence cl-1/cl-3"},
            {"claim": "Operationally complete, not just decorative", "class": "inferred",
             "source": "analysis.solution_weaknesses / unmet_needs"},
            {"claim": "Every turnover done the same way, nothing forgotten", "class": "positioning_language",
             "source": "product promise — bounded outcome, not a guarantee"},
            {"claim": "A repeatable, cleaner-ready operating system", "class": "positioning_language",
             "source": "positioning framing"},
        ],
        "explicitly_not_claimed": [
            "guaranteed faster turnovers", "increase bookings", "make more money",
            "any income figure", "testimonials/reviews (none exist yet)", "number of current customers",
        ],
    }
    write("claim_traceability.json", claim_traceability)

    # ---------------------------------------------------------------- whop listing draft
    whop = {
        "_status": "DRAFT — not published. Platform-neutral content package; Whop field schema not fabricated.",
        "opportunity_id": AIR,
        "product_name": PRIMARY_NAME,
        "headline": "Run every Airbnb turnover the same way — nothing forgotten, no broken templates.",
        "short_description": sales_copy["short_description"],
        "long_description": sales_copy["full_listing_description"],
        "price": {"amount": LAUNCH_PRICE, "currency": "USD", "type": "one_time",
                  "reference_price": REFERENCE_PRICE},
        "suggested_category": "Real estate / Short-term rental / Templates & tools",
        "suggested_tags": ["airbnb", "short-term rental", "str host", "turnover", "cleaning checklist",
                           "property operations", "welcome guide", "host tools"],
        "included_files": [f"{c['name']} ({', '.join(c['formats'])})" for c in comps] + ["START_HERE.md"],
        "faq": sales_copy["faq"],
        "cta": sales_copy["cta_variants"][0],
        "delivery_description": "Instant digital download. Standard editable files — no signup or subscription.",
        "thumbnail_cover_brief": "see creative_briefs.json → cover / thumbnail",
        "screenshot_mockup_brief": "see creative_briefs.json → mockup / bundle_contents",
        "do_not_publish": True,
    }
    write("whop_listing_draft.json", whop)

    # ---------------------------------------------------------------- creative briefs
    creative_briefs = {
        "_note": "Briefs only. No images generated (no image-production path in repo).",
        "opportunity_id": AIR,
        "briefs": [
            {"asset": "product_cover", "message": "A reliable turnover system for Airbnb hosts",
             "hierarchy": ["Product name", "Subtitle (1–5 properties)", "8-part system cue"],
             "visual_content": "Clean, document-forward; a tidy turned-over room OR a flat-lay of the checklist + "
                               "tracker on a tablet. Calm, trustworthy — not flashy.",
             "required_text": [PRIMARY_NAME, "For hosts with 1–5 properties", "8 templates, checklists & trackers"],
             "dimensions": "1:1 (1080×1080) primary; 16:9 variant for banners", "files_to_show": ["Master Turnover SOP", "Supply + Inventory Tracker"]},
            {"asset": "listing_thumbnail", "message": "Turnover system, at a glance",
             "hierarchy": ["Name", "'8 parts' badge"], "visual_content": "High-contrast, legible at small size.",
             "required_text": [PRIMARY_NAME, "8-part kit"], "dimensions": "square, small-safe", "files_to_show": []},
            {"asset": "product_mockup", "message": "Real, usable files",
             "hierarchy": ["The actual documents/spreadsheet on screen"],
             "visual_content": "Laptop + phone mockup showing the SOP doc and the tracker spreadsheet open.",
             "required_text": [], "dimensions": "16:9", "files_to_show": ["Master Turnover SOP", "Supply + Inventory Tracker", "Cleaner Handoff Sheet"]},
            {"asset": "bundle_contents_visual", "message": "Everything you get",
             "hierarchy": ["8 labeled tiles, one per component"],
             "visual_content": "Grid of 8 tiles with component names + file-type icons.",
             "required_text": comp_names, "dimensions": "4:5", "files_to_show": comp_names},
            {"asset": "creator_promo_visual", "message": "Reliable turnovers, handed to your audience",
             "hierarchy": ["Hook for host audience", "What it solves", "Creator's own CTA slot"],
             "visual_content": "Simple, remixable template a creator can overlay their face/voiceover on.",
             "required_text": ["For hosts with 1–5 properties", "[Creator CTA]"], "dimensions": "9:16 (reel/story)", "files_to_show": ["Quick Turnover Checklist"]},
        ],
    }
    write("creative_briefs.json", creative_briefs)

    # ---------------------------------------------------------------- creator partnership
    creator_partnership = {
        "_status": "DRAFT. Phase-9.5 verdict = NEEDS_RESEARCH; NO creator is qualified or approved here.",
        "opportunity_id": AIR,
        "why_fit": "The product serves self-managing STR hosts; creators in the Airbnb-host / STR-operations / "
                   "Airbnb-cleaning niches reach that exact buyer. Fit is PLAUSIBLE but UNVERIFIED per Phase 9.5.",
        "creator_does": ["Promote via a reel/story/post or email to their host audience",
                         "Use a trackable link/code", "Disclose the partnership per platform rules"],
        "we_provide": ["Ready creative (see creative_briefs)", "Copy angles / hooks",
                       "The product + instant delivery", "Trackable link/code + payout"],
        "revenue_share_models_ref": "revenue_share_scenarios (below in this file)",
        "tracking_requirements": ["Unique link or discount code per creator",
                                  "Attribution window agreed up front", "Payout cadence agreed up front"],
        "audience_fit_criteria": ["Audience is Airbnb/STR hosts (not just travelers or renters)",
                                  "Content touches hosting operations / cleaning / turnover / setup",
                                  "Evidence the audience has the problem (comments/questions), not just follower count"],
        "creator_qualification_requirements": [
            "Resolve Phase-9.5 unknowns first: per-creator relevant-content views + audience-problem signals",
            "Confirm creator does not sell a directly-competing product",
            "Confirm willingness to promote a third-party product",
        ],
        "partnership_risks": [
            "0/6 imported creators currently qualified (audience+problem+content).",
            "55% of distribution scoring weight is UNKNOWN.",
            "Follower counts are observed; relevance to THIS problem is not.",
            "Saturated aesthetics market — creators may already push prettier competing templates.",
        ],
        "revenue_share_scenarios": _rev_share(LAUNCH_PRICE),
    }
    write("creator_partnership.json", creator_partnership)

    # ---------------------------------------------------------------- creator pitch drafts
    pitch = {
        "_status": "DRAFTS ONLY — not sent. Intentional personalization placeholders below.",
        "placeholders": ["[Creator Name]", "[Recent Video Topic]", "[Audience Observation]",
                         "[Product/Audience Fit]", "[Revenue Share]", "[Product Link]"],
        "short_email": {
            "subject": "your [Recent Video Topic] audience + a turnover kit",
            "body": "Hi [Creator Name] — your [Recent Video Topic] content clearly reaches hosts dealing with "
                    "[Audience Observation]. I built a turnover & operations kit for hosts with 1–5 properties "
                    "(SOP, cleaner handoff, supply tracker, welcome guide). Given [Product/Audience Fit], it might "
                    "be genuinely useful to them. Open to a [Revenue Share] partnership — want me to send it over "
                    "so you can judge for yourself?"},
        "longer_email": {
            "subject": "helping your host audience run turnovers (partnership idea)",
            "body": "Hi [Creator Name],\n\nI've been following your [Recent Video Topic] posts — the way your "
                    "audience talks about [Audience Observation] lines up closely with a problem I built a product "
                    "around: running reliable, repeatable turnovers.\n\nIt's an 8-part kit for hosts with 1–5 "
                    "properties: a turnover SOP, cleaner handoff sheet, supply + inventory tracker, damage log, "
                    "property setup workbook, guest welcome guide, quick checklist and a message library — all in "
                    "editable Docs/Sheets/PDF (no fragile design-tool files).\n\nBecause of [Product/Audience Fit], "
                    "I think it could genuinely help your audience, not just sell to them. I'd love to explore a "
                    "[Revenue Share] partnership. No pressure — happy to send you the full kit first so you can "
                    "decide if it's up to your standard.\n\nEither way, thanks for the content.\n\n[Your name]"},
        "instagram_dm": "Hey [Creator Name] — love your [Recent Video Topic] stuff. I built a turnover/ops kit for "
                        "hosts with 1–5 properties and given [Audience Observation] it might actually help your "
                        "audience. Open to a [Revenue Share] partnership — can I send it over for you to check out?",
        "follow_up_1": "Hi [Creator Name] — circling back on the turnover kit. Happy to just send it over free so "
                       "you can see if it fits your audience, no commitment. Want me to?",
        "follow_up_2": "Hey [Creator Name], last nudge — if it's not a fit, all good. If you're curious, the kit + a "
                       "[Revenue Share] split is here whenever: [Product Link]. Thanks either way!",
        "short_partnership_explainer": "What it is: an 8-part turnover & operations kit for Airbnb hosts (1–5 "
                                       "properties). Who it's for: your host audience dealing with [Audience "
                                       "Observation]. How it works: you share it with a trackable [Product Link], we "
                                       "handle delivery, you earn [Revenue Share] on each sale. You can review the "
                                       "full kit before promoting anything.",
        "tone_rule": "Lead with audience fit + value to the creator's audience — never 'we built a product, please "
                     "promote it.' No performance/earnings claims.",
    }
    write("creator_pitch_assets.json", pitch)

    # ---------------------------------------------------------------- distribution readiness
    readiness = {
        "opportunity_id": AIR,
        "state": "assets_ready_creator_research_needed",
        "rationale": "Offer + sales + listing draft + creator materials are prepared, but Phase-9.5 distribution "
                     "verdict is NEEDS_RESEARCH (LOW confidence, 0/6 creators qualified, 55% weight unknown). "
                     "Assets are ready; qualified creators are not.",
        "phase_9_5_verdict": "NEEDS_RESEARCH",
        "phase_9_5_confidence": "LOW",
        "qualified_creator_count": 0,
        "blocking_unknowns": ["per-creator relevant-content views", "audience-problem signals (comments)",
                              "whether creators sell competing products",
                              "whether creators will promote third-party products"],
        "ready": ["positioning", "naming", "offer", "pricing", "sales_copy", "claim_traceability",
                  "whop_listing_draft", "creative_briefs", "creator_partnership", "creator_pitch_assets"],
        "not_ready": ["qualified creator list", "chosen first partners", "any outreach"],
        "honest_note": "This is deliberately NOT 'ready_for_outreach' — that would require resolving the Phase-9.5 "
                       "unknowns first.",
    }
    write("distribution_readiness.json", readiness)

    print(f"✓ offer package written to products/{AIR}/offer/")
    for p in sorted(OFFER.glob("*.json")):
        print(f"    {p.name}")


def _rev_share(price):
    """Model economics at the launch price. Platform fee kept as a VARIABLE (unknown exact Whop fee)."""
    def rows(creator_pct):
        our_pct = 100 - creator_pct
        our_unit = round(price * our_pct / 100, 2)
        creator_unit = round(price * creator_pct / 100, 2)
        return {"creator_pct": creator_pct, "our_pct": our_pct,
                "creator_per_sale_gross": creator_unit, "our_per_sale_gross": our_unit,
                "our_gross_at": {"10": round(our_unit * 10, 2), "50": round(our_unit * 50, 2),
                                 "100": round(our_unit * 100, 2)},
                "creator_gross_at": {"10": round(creator_unit * 10, 2), "50": round(creator_unit * 50, 2),
                                     "100": round(creator_unit * 100, 2)}}
    return {
        "price": price, "currency": "USD",
        "platform_fee": {"value": "UNKNOWN", "handling": "variable f; net = gross × (1 − f). Whop platform + "
                         "payment-processing fee not confirmed from repo — do not fabricate.",
                         "note": "All figures below are GROSS (pre-fee); the fee reduces both shares proportionally."},
        "models": {
            "A_creator_majority_70_30": rows(70),
            "B_equal_50_50": rows(50),
            "C_exclusive_80_20": rows(80),
        },
        "recommendation_note": "For a first validation partner, a creator-majority split (A or C) is the strongest "
                               "incentive; final % is a negotiation, not a fixed fact.",
    }


if __name__ == "__main__":
    main()
