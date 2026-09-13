"""Optional deep Phase-8 findings for Universe-originated opportunities.

Keyed by Universe opportunity id. An entry here means real observed research
exists for that opportunity, so Phase 8 returns 'complete' (else 'needs_review').
Everything below is grounded in evidence genuinely observed this session for the
Airbnb host-ops space; nothing is invented. Opportunities WITHOUT an entry stay
needs_review — that is the honest default.
"""

FINDINGS = {
    "opp-airbnb-hosts-with-1-5-properties-turnover-and-property-operations": {
        "opportunity_assessment": (
            "Small Airbnb hosts repeatedly need a reliable turnover system (cleaning/turnover, "
            "a guest-ready house manual, supply restocking). Observed: hosts already pay for "
            "welcome-book/checklist templates on Etsy (1,000+ listings, many Bestsellers) and a real "
            "1-star review shows those Canva templates failing to save/print — a reliability gap. "
            "Demand and spending are real; the open question is distribution, not whether the problem exists."),
        "existing_behaviours": ["Buying Canva welcome-book/checklist templates on Etsy",
                                "Ad-hoc cleaner coordination", "DIY house-manual docs"],
        "solution_strengths": ["Cheap, instant templates exist", "Attractive designs"],
        "solution_weaknesses": ["Canva templates fail on save/print (lost work)",
                                "Pretty but not operationally complete", "No turnover/restock system"],
        "customer_complaints": ["'could not print after personalizing and would not save. I lost hours of work.'"],
        "unmet_needs": ["A turnover system that won't break like a Canva file",
                        "Standardized checklists cleaners actually follow", "Restock tracking"],
        "contradictions": ["Etsy welcome-book market is saturated on aesthetics; differentiation must be "
                           "reliability + operational completeness, not looks.",
                           "Distribution likely harder than the product (creator ecosystem exists but "
                           "promotion is unproven — see Build-4 density MEDIUM, not qualified)."],
        "product_concept": ("A reliable turnover & property-operations kit for hosts with 1-5 listings: "
                            "standardized cleaning/turnover checklists, a guest-ready house manual, and a "
                            "supply-restock tracker — delivered so it won't break like the Canva templates hosts complain about."),
        "core_transformation": "From error-prone, ad-hoc turnovers and unclear house manuals -> a standardized, "
                               "reliable turnover system nothing falls through.",
        "product_promise": "Every turnover done the same way, nothing forgotten, no broken templates.",
        "why_this_format": ("The job is repeatable operations + reference, so a checklist/tracker + house-manual "
                            "bundle fits — not an ebook. Reliability (no save/print failures) is the wedge."),
        "product_structure": ["Turnover/cleaning checklist (printable + fillable)",
                             "Guest-ready house manual template", "Supply restock tracker"],
        "required_sections": ["Turnover step-by-step", "House-manual sections hosts forget"],
        "required_tools": ["Supply restock tracker"],
        "required_templates": ["Cleaning/turnover checklist", "House manual"],
        "required_worksheets": ["Cleaner handoff sheet"],
        "bonus_assets": ["Guest message snippets for checkout"],
        "exclude": ["Pretty-but-fragile Canva-only formats", "Padding/theory", "Anything freely adequate already"],
        "differentiation": ["Reliability (no save/print failures)", "Operationally complete, not just decorative",
                           "Standardization a cleaner can follow"],
        "price_range": "$15-25 one-time",
        "price_rationale": "Observed: Etsy host welcome-book/checklist bundles sell at ~$14-21+; this sits in the proven band.",
        "key_customer_language": ["template wouldn't save", "cleaners miss steps", "what goes in a house manual"],
        "key_objections": ["I already bought a welcome-book template", "I can make my own checklist",
                          "another template that'll break?"],
        "key_buying_motivations": ["Protect reviews", "Save turnover time", "Stop things being forgotten"],
        "confidence": "MEDIUM",
        "risks_unknowns": ["Distribution/promotion unproven (creator density MEDIUM, not qualified)",
                          "Welcome-book market saturated — must be visibly more reliable/complete",
                          "Some hosts use a property manager and won't buy tools"],
        "extra_claims": [
            {"claim": "Hosts already pay for welcome-book/checklist templates.",
             "evidence": "Etsy 'airbnb welcome book template' returns 1,000+ paid listings, many Bestsellers.",
             "source_label": "Etsy marketplace (observed 2026-09-08)", "source_type": "marketplace",
             "url": None, "tier": 3, "basis": "observed", "relevance": "high", "strength": "moderate",
             "interpretation": "Willingness-to-pay for host operational assets is real."},
        ],
        "inaccessible": [
            {"label": "r/airbnb / r/AirBnBHosts turnover threads (primary host language)",
             "url": "https://www.reddit.com/r/AirBnBHosts/", "source_type": "reddit", "tier": 1,
             "note": "Reddit thread bodies not retrievable in-app this run; retrieve later."},
        ],
    },
}
