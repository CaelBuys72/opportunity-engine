"""Deep, session-researched findings, keyed by pocket id.

Everything here is REAL research gathered this session (Etsy listings read
directly via browser = observed; secondary complaint themes = inferred; items
that could not be retrieved in-app = recorded inaccessible, not fabricated).
Pockets absent from FINDINGS still get a full dossier from their discovery
evidence, but are marked `needs_review` rather than `complete`.

This module is the human/agent research hand-off point. A future automated
retriever would populate the same shape.
"""

FINDINGS = {
    "freelancer-us-tax": {
        # ---- extra traced claims (beyond the discovery evidence on the pocket)
        "extra_claims": [
            {"claim": "A dedicated US 1099 tax spreadsheet sells real volume at a premium price.",
             "evidence": "RunTheCalc '1099 Self-Employed Bookkeeping Spreadsheet': 2.2k sales, 4.7-4.8★ (item avg 4.8/22 reviews), priced ~$17.",
             "source_label": "Etsy listing (RunTheCalc)", "source_type": "marketplace",
             "url": "https://www.etsy.com/listing/1533152672/1099-bookkeeping-spreadsheet-accounting",
             "tier": 3, "basis": "observed", "relevance": "high", "strength": "strong",
             "interpretation": "WTP is proven at ~$17 for a focused, dedicated tool."},
            {"claim": "Category is deep and premium vs generic bookkeeping.",
             "evidence": "'1099 self employed tax tracker quarterly' returns 1,000+ Etsy items; dedicated Schedule-C/quarterly trackers cluster $9-25, well above $1 generic calculators.",
             "source_label": "Etsy search (observed breadth)", "source_type": "marketplace",
             "url": None, "tier": 3, "basis": "observed", "relevance": "high", "strength": "strong",
             "interpretation": "Niche-specific commands a premium; buyers self-select into the tax framing."},
            {"claim": "The market is fragmented — no category-owning brand — but breadth shops own Etsy SEO.",
             "evidence": "PrioriDigitalStudio (carries a self-employed tax tracker): shop 173.8k sales, 11.1k reviews, 4.8★; but item-level review counts on dedicated trackers stay modest (13-112).",
             "source_label": "Etsy listing (PrioriDigitalStudio)", "source_type": "marketplace",
             "url": "https://www.etsy.com/listing/4313117556/tax-deduction-tracker-google-sheets",
             "tier": 3, "basis": "observed", "relevance": "high", "strength": "moderate",
             "interpretation": "No moat, but distribution via Etsy search is dominated by generalist template shops."},
            {"claim": "Specificity outsells generic — regime/profession versions rank as bestsellers.",
             "evidence": "'Self Assessment UK / HMRC' and 'Therapist Bookkeeping' trackers appear among bestsellers next to generic ones.",
             "source_label": "Etsy search (observed)", "source_type": "marketplace",
             "url": None, "tier": 3, "basis": "observed", "relevance": "high", "strength": "moderate",
             "interpretation": "A US-sub-niche angle (content creator / rideshare / trades) is the wedge."},
            {"claim": "Recurring complaint: templates are too simple or too complicated and formulas break.",
             "evidence": "Bookkeeping-template guidance repeatedly notes buyers 'fixing broken formulas', inconsistent categories, wrong balances at tax time.",
             "source_label": "Keeper Tax / bookkeeping template articles", "source_type": "article",
             "url": "https://www.keepertax.com/posts/1099-excel-template",
             "tier": 2, "basis": "inferred", "relevance": "high", "strength": "moderate",
             "interpretation": "Correctness + robustness is the differentiator, not features."},
        ],
        # ---- sources whose primary text could NOT be retrieved in-app this run
        "inaccessible": [
            {"label": "r/freelance / r/tax threads on quarterly estimated taxes (primary user language)",
             "url": "https://www.reddit.com/r/freelance/", "source_type": "reddit", "tier": 1,
             "note": "Reddit thread bodies not retrievable by in-app tools this run; requirement preserved for live retrieval."},
            {"label": "Etsy 1-3★ reviews on top 1099 trackers (complaint mining)",
             "url": "https://www.etsy.com/listing/1533152672/1099-bookkeeping-spreadsheet-accounting", "source_type": "review", "tier": 3,
             "note": "Etsy shows only 'Suggested' (positive) reviews with no public star filter; negatives not extractable at scale."},
        ],
        # ---- synthesis overrides (interpretation, clearly separate from evidence)
        "existing_behaviours": ["Free 1099 templates / generic bookkeeping sheets",
                                 "Spreadsheets built from scratch", "Deferring everything to tax season",
                                 "Bonsai/FreshBooks/Wave subscriptions"],
        "solution_strengths": ["Cheap and instant", "Many options", "Auto-calculation when they work"],
        "solution_weaknesses": ["Too simple OR too complicated", "Formulas break on edit",
                                "Categories don't map to Schedule C", "Generic — not tuned to a specific 1099 trade"],
        "customer_complaints": ["'fixing broken formulas'", "wrong balances at tax time",
                                "missing/inconsistent expense categories"],
        "unmet_needs": ["Correct US SE-tax + quarterly-estimate logic that a non-accountant trusts",
                        "Robust-but-simple middle ground", "Sub-niche category presets"],
        "contradictions": [
            "Free 1099 templates are abundant — risk of a 'free-information' problem for the generic version.",
            "Etsy SEO is owned by high-volume generalist shops — the marketing problem may exceed the product problem.",
            "A subset of freelancers offload this entirely to an accountant and won't buy a tool.",
        ],
        "opportunity_assessment": (
            "Strong, evidence-backed recurring problem with PROVEN willingness-to-pay ($9-25; RunTheCalc 2.2k sales @ ~$17) "
            "and a clear correctness+specificity gap. Main risk is distribution, not demand: incumbents are fragmented but "
            "own Etsy search, and free templates compete. Wedge = a specific US 1099 sub-niche + verifiable correctness "
            "(SE tax, quarterly estimates, Schedule C) + an off-Etsy distribution angle."
        ),
        # ---- product opportunity / brief overrides
        "product_concept": ("A robust-but-simple US 1099 tax & get-paid toolkit for a specific freelancer sub-niche "
                            "(e.g. content creators or rideshare/independent contractors): a spreadsheet that gets the "
                            "SE-tax + quarterly-estimate math right, plus an invoice template and a short setup guide."),
        "core_transformation": "From 'no idea what to set aside and formulas that break' → 'know my quarterly number, "
                               "invoices out, expenses categorised for Schedule C, no tax-season panic'.",
        "product_promise": "Know exactly what to set aside every quarter and get paid on time — without an accountant or a broken spreadsheet.",
        "why_this_format": ("The job is calculation + record-keeping + getting paid, so a spreadsheet/calculator is the "
                            "native core; a short guide covers the rules; an invoice template closes the get-paid loop. "
                            "Not an ebook — the value is in the working tool."),
        "product_structure": ["Auto-calculating spreadsheet (income, expenses, SE tax, quarterly estimate, set-aside %)",
                              "Short setup guide (how the rules work, plain-English)",
                              "Invoice + late-payment follow-up templates"],
        "required_tools": ["Quarterly estimated-tax calculator", "Set-aside % calculator", "Schedule C category mapper"],
        "required_templates": ["Professional invoice", "Late-payment follow-up email"],
        "required_worksheets": ["Quarterly payment scheduler (due dates)", "Deductible-expense checklist by Schedule C line"],
        "required_sections": ["How much to set aside (with worked example)",
                             "When quarterly payments are due", "Schedule C categories in plain English"],
        "bonus_assets": ["Sub-niche category presets (content creator / rideshare / trades)"],
        "exclude": ["Actual tax filing (liability)", "Personalised tax advice", "Generic personal-budgeting bloat", "Filler theory"],
        "differentiation": ["Correct SE-tax + quarterly logic a non-accountant can trust",
                           "Formulas that don't break on edit", "Tuned to a specific US 1099 sub-niche",
                           "Distribution off Etsy (niche community/content), not SEO roulette"],
        "price_range": "$15-25 one-time",
        "price_rationale": "Observed: dedicated US trackers sell at $9-25; RunTheCalc does 2.2k sales at ~$17. "
                          "$15-25 sits in the proven band and above $1 generics without needing subscription justification.",
        "key_customer_language": ["how much do I set aside for quarterly taxes",
                                  "my spreadsheet formulas keep breaking",
                                  "what counts as a deduction", "I always panic at tax time"],
        "key_objections": ["I can find a free 1099 template",
                          "Spreadsheets break when I edit them",
                          "I'll just deal with it at tax time",
                          "My accountant handles this"],
        "key_buying_motivations": ["Avoid IRS penalties / underpayment", "Cashflow clarity (know my real take-home)",
                                  "Stop tax-season panic", "Look professional / get paid on time"],
        "confidence": "MEDIUM",
        "risks_unknowns": ["Distribution is the hard part (incumbents own Etsy SEO) — UNKNOWN best channel",
                          "Tax-logic correctness carries liability; needs careful, disclaimed implementation",
                          "Free templates compete; must be visibly better",
                          "Creator ecosystem size UNKNOWN", "Prevalence UNKNOWN"],
    },
}
