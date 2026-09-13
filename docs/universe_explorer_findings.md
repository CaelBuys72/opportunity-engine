# Universe Explorer Findings

Real issues discovered while building and manually testing the Universe Explorer MVP
against the existing canonical universe data. The point of this MVP is partly to
expose flaws through real use — these are **recorded, not (mostly) fixed**.

Categories: DATA MODEL ISSUE · UI ISSUE · WORKFLOW ISSUE · MISSING FIELD ·
RELATIONSHIP ISSUE · SCALING ISSUE · OPPORTUNITY ENGINE ISSUE

## Observations

### Finding 001
- **Type:** RELATIONSHIP ISSUE
- **Node / workflow:** Opportunity nodes / search-focus + graph hierarchy
- **Observation:** Opportunities attach to an audience (`audience_id`) *and* reference
  problems (`problem_ids[]`). In the explorer hierarchy they render as children of a
  **problem** (audience → problem → opportunity), but they are not children of a single
  canonical problem — an opportunity groups several problems. Focusing an opportunity
  therefore required the server to pick one "representative" member problem to reveal it.
- **Impact:** The graph implies a 1:1 problem→opportunity tree, but the real relationship
  is many-to-many (one opportunity clusters N problems; a problem could belong to >1
  opportunity). The current view shows each opportunity once, under the first member
  problem in the focus chain, which understates the clustering.
- **Suggested change:** Decide the canonical shape — either (a) render opportunities as a
  sibling layer off the *audience* with faint links to all member problems, or (b) allow
  an opportunity node to connect to multiple problem parents (multi-edge). Needs a product
  call, not a silent fix.
- **Priority:** Medium
- **Status:** Worked around (server returns a representative member problem in the ancestor chain); recorded for a real decision.

### Finding 002
- **Type:** MISSING FIELD
- **Node / workflow:** Audience nodes / stored downstream counts
- **Observation:** `audiences.json` carries `problem_count`, `opportunity_count`,
  `creator_density`, `research_status` — but for every audience these are still the seed
  defaults (`0`, `0`, `"unknown"`, `"unresearched"`), even for audiences that clearly have
  problems and opportunities (e.g. Airbnb hosts 1-5, Independent nail technicians).
- **Impact:** The stored fields are stale/untrustworthy. The explorer had to **derive all
  counts dynamically** from `problems.json` / `opportunities.json` instead. Anything that
  reads the stored audience counts (or a future UI that trusts them) will be wrong.
- **Suggested change:** Either backfill these fields from the downstream builders and keep
  them in sync, or delete them from the schema so nothing is tempted to trust them.
- **Priority:** Medium
- **Status:** Recorded (explorer derives counts live; stored fields ignored).

### Finding 003
- **Type:** DATA MODEL ISSUE
- **Node / workflow:** Universe coverage / whole graph
- **Observation:** Of 300 audiences, only **5** have any problems and only **5** have any
  opportunities. 63 problems and 16 opportunities exist total. So ~98% of audience branches
  are dead ends when you drill in.
- **Impact:** The universe *taxonomy* is broad (20/100/300) but the *demand layer* is
  extremely sparse. Exploration mostly hits "no further downstream data / Unknown." This is
  honest, but it means the map is 95% empty scaffolding — good for showing where work is
  needed, misleading if read as "coverage."
- **Suggested change:** None yet (per the "do not generate more universe data" rule). This
  finding is exactly the kind of signal the MVP was built to surface: the bottleneck is
  problem/opportunity discovery, not taxonomy breadth.
- **Priority:** High (strategic signal)
- **Status:** Recorded.

### Finding 004
- **Type:** OPPORTUNITY ENGINE ISSUE
- **Node / workflow:** Opportunity detail panel / two parallel opportunity worlds
- **Observation:** There are **two disjoint opportunity datasets**: the canonical universe
  opportunities (`data/universe/opportunities.json`, `opp-…` ids, scored + pipelined) and
  the legacy hand-authored "pockets" (`data/opportunities/*.json`, e.g. `str-host-ops`)
  that the existing Opportunity Intelligence UI (`app/web/index.html`) is actually wired to.
  They cover overlapping territory (both have an Airbnb/STR ops opportunity) but share no IDs.
- **Impact:** "Open in Opportunity Intelligence" can't route a universe opportunity into the
  legacy pocket workflow (research/curation/distribution), because that workflow only knows
  pocket IDs. The handoff currently renders a **read-only** universe intelligence card on the
  same page instead.
- **Suggested change:** Decide whether universe opportunities should become the single source
  of truth and the research/curation/distribution pipeline should consume `opp-…` ids
  directly (retiring the pockets), or keep a deliberate mapping. This is the biggest
  architectural fork the MVP exposed.
- **Priority:** High
- **Status:** Recorded; handoff implemented as a read-only card (thin, no workflow duplication).

### Finding 005
- **Type:** UI ISSUE
- **Node / workflow:** Graph readability at deep expansion
- **Observation:** When an audience with many problems is expanded (e.g. Independent nail
  technicians → 13 problems, each with truncated statements), labels overlap in the dense
  cluster before the layout settles, and problem labels are only readable via hover title.
- **Impact:** The "intentionally chaotic knowledge-map" feel is achieved, but deep clusters
  are momentarily hard to read. Acceptable for an MVP; would not scale past a few dozen
  visible problem nodes.
- **Suggested change:** Optional later — collision-aware label placement, or a "problems as a
  list in the side panel" affordance when a node's child count is high.
- **Priority:** Low
- **Status:** Recorded.

### Finding 006
- **Type:** WORKFLOW ISSUE
- **Node / workflow:** Pipeline state coverage
- **Observation:** Only 2 opportunities (Airbnb Turnover, Nail Pricing) have
  `pipeline_states.json` entries. Every other opportunity honestly shows "Not promoted into
  the pipeline yet" (the pipeline endpoint 404s, handled gracefully). Distribution status on
  the promoted Airbnb opp reads `NEEDS_RESEARCH` even though stage is `distribution_complete`
  — the sub-statuses and the top-level stage can disagree.
- **Impact:** The pipeline state is a bag of independently-set flags with no single
  authoritative "where is this really" field; the UI shows all of them, which reveals the
  inconsistency rather than hiding it.
- **Suggested change:** Consider a derived/validated single status, or document that stage is
  authoritative and sub-statuses are advisory.
- **Priority:** Medium
- **Status:** Recorded.

### Finding 007
- **Type:** UI ISSUE (resolved-in-passing)
- **Node / workflow:** Audience nodes — "explored vs unexplored" signal
- **Observation:** The spec asked for an optional way to visually distinguish audiences
  that have downstream intelligence from those that don't. This already exists for free:
  an audience with problems is `expandable` and renders a **count badge** (e.g. `13`)
  after its label; an unexplored audience has no badge and terminates. No redesign needed.
- **Impact:** After the V1 expansion, 5 / 612 audiences are "explored" and 607 are blank —
  the asymmetry is clearly visible and intentional.
- **Suggested change:** If a stronger signal is wanted later (e.g. a colour/dot for
  "researched" audiences), add it then — not now.
- **Priority:** Low
- **Status:** Working as-is; recorded per the "record instead of build" instruction.

### Finding 008
- **Type:** TAXONOMY ISSUE (boundary notes from Universe Expansion V1)
- **Node / workflow:** New markets vs existing markets — deliberate boundaries
- **Observation:** Several new markets deliberately sit next to existing ones. Boundaries
  were defined rather than merged:
  - **Trading, Investing & Crypto** (active trading/options/crypto/market education) vs
    **Personal Finance › Investing Basics** (passive index/retirement).
  - **AI Tools & Automation** (applied AI for non-engineers/creators/ops) vs
    **Technology & Software** (coding, SaaS building, eng).
  - **Reselling, Flipping & Arbitrage** (reselling as an income business + sourcing) vs
    **E-commerce › Reselling & Flipping** (casual online selling). *Mild overlap — watch.*
  - **Digital Marketing & Agencies** (marketing as a profession/agency) vs
    **Small Business › Local Marketing** (an owner marketing their own shop).
  - **Writing & Publishing** (writing crafts + publishing as product) vs **Freelancing**
    (generic solo-service ops). *Copywriting/Blogging also touch Digital Marketing —
    kept the craft angle in Writing, the conversion angle (CRO) in Marketing.*
  - **Design & Templates** (design as product + service) — *Printables & Digital Products*
    overlaps **E-commerce** selling of digital downloads (creation vs selling angle).
  - **Self-Improvement & Personal Development** (mindset/identity/motivation) vs
    **Health & Wellness › Mental Health** (clinical stress/anxiety) vs **Productivity**
    (systems/tools). "Habits" appears across all three by design, framed differently.
  - **Sales & Closing** (rep/closer skills) vs **Digital Marketing › Lead Generation**
    (generating leads/traffic). "Cold outreach" appears in both (rep vs system angle).
- **Impact:** These are intentional adjacencies, not accidental duplicates. Watch the
  starred ones during operator use — if they cause confusion, that's a real signal to merge.
- **Priority:** Medium (revisit after operator sessions)
- **Status:** Recorded.
