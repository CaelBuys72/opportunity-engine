# Opportunity Intelligence Engine — V1

The **discovery layer** of a larger pipeline. It finds recurring problems real
people describe, clusters them into commercially meaningful **profit pockets**,
scores/ranks them, and lets you inspect the evidence and select a pocket for
future research. It does **not** create products, research automatically,
contact creators, or touch Whop/affiliates — those are later phases.

Scope note (Capital Engine Playbook): this is an **opportunity queue / research
tool**. Producing a shortlist is allowed; *building* a product from it is a
gated E2 decision, not triggered here.

## Requirements
Python 3.9+ (standard library only — **no pip installs, no npm, no database**).

## Run it
```bash
cd opportunity-engine

# 1. Run discovery to populate data/ (all seed industries, or name some)
python3 scripts/run_discovery.py                 # all 10 seed industries
python3 scripts/run_discovery.py freelancing beauty   # just these

# 2. Start the dashboard
python3 app/server.py
# open http://localhost:8777              → Opportunity Intelligence (legacy pockets)
# open http://localhost:8777/explorer.html → Universe Explorer (interactive graph)
```

## Universe Explorer (interactive graph over the canonical universe)
`explorer.html` is an exploratory spider/knowledge-map over the **same canonical
universe data** (`data/universe/`) — a second interface, not a second database.
Start at the 20 markets and click to expand progressively:

```
Market → Submarket → Audience → Problem → Opportunity
```

- **Progressive expansion:** only explored branches render (click a node to expand
  / collapse). Counts on each node are **derived live** from the data, never hardcoded.
- **Detail panel:** per-type fields; opportunities surface commercial / evidence /
  priority scores, priority classification, creator density, and pipeline state.
  Unknown values display as **Unknown** — never fabricated.
- **Search** across markets, submarkets, audiences, problem statements and
  opportunities; selecting a hit auto-expands its ancestors and centres it.
- **Breadcrumb** shows the current path; click an ancestor to refocus.
- **Open in Opportunity Intelligence** hands an opportunity to the existing page
  (`/?focus=<opp-id>`) as a read-only intelligence card.
- Pan (drag background), zoom (scroll), drag nodes, **Reset**, **Fit**.

Backend (added, read-only view model — canonical storage untouched):
`GET /api/universe/graph[?node=<id>]` → `{focus, nodes, edges}` ·
`GET /api/universe/search?q=<text>`. See `app/universe_graph.py`.

Issues surfaced by real use live in `docs/universe_explorer_findings.md`.

Re-running discovery is safe and additive: it rebuilds candidate pockets but
**preserves any pocket you already selected**, and adding a new industry never
disturbs existing data.

## What you can do in the UI
Sidebar lists industries (ranked by pocket count) → open a submarket → click a
profit pocket. The detail panel shows the **overall score /100**, a
**confidence** badge, the 7 factor scores (each tagged `observed` / `inferred`
/ `unknown`), clustered related problems, demand evidence with source links,
communities, existing solutions & gaps, creator ecosystem, and digital-product
fit. **RESEARCH OPPORTUNITY** marks the pocket `selected` and writes a
structured research request to `outputs/research-requests/`.

## Architecture (deliberately minimal)
```
app/
  server.py         zero-dependency HTTP: JSON API + serves the dashboard
  store.py          Store interface + JsonStore (swap for a DB later, callers unchanged)
  discovery.py      clustering (symptom→problem) + 7-factor weighted scoring + confidence
  research.py       Phase-8 engine: plan→sources→evidence→analysis→brief (modular stages)
  research_inputs.py deep session-researched findings, keyed by pocket id
  web/              index.html · styles.css · app.js  (vanilla, no build step)
data/               one JSON file per record
  industries/ opportunities/ evidence/ communities/ creators/
research/           Phase-8 dossiers, one folder per pocket (6 JSON files)
schemas/            schemas.json — core data model (Industry…ProfitPocket…Score…ProductBrief)
scripts/
  seed_dataset.py   real, source-cited observations for the first run
  run_discovery.py  Phase-6 runner (CLI)
  run_research.py   Phase-8 runner (CLI)
outputs/
  research-requests/ (legacy Phase-7 export; Phase 8 writes to research/ instead)
```

## Scoring model (Phase 5)
Weighted 0–10 factors → 0–100 overall:

| Factor | Weight |
|---|---|
| Demand evidence | 20 |
| Pain / importance | 15 |
| Clear desired outcome | 10 |
| Existing spending / WTP | 15 |
| Solution gap | 15 |
| Creator density / reach | 15 |
| Digital product fit | 10 |

**Honesty rules baked in:** a factor with basis `unknown` has no score, is
excluded from the overall (weight renormalised — "unknown" never masquerades as
"bad"), and drags **confidence** instead. Confidence is HIGH / MEDIUM / LOW,
derived from how many factors are observed vs unknown. Evidence carries source
URLs; inference is labelled. Numbers that were not observed are left unknown,
never invented.

## Data honesty
The seed dataset uses real observations gathered during research: marketplace
sales/ratings read directly from listings (`observed`), and secondary complaint
themes (`inferred`). Creator density and most sales volumes are `unknown`.
Global English-speaking / USD buyers are the target — discovery is **not**
localised to the operator's location.

## Phase 8 — Research engine (pocket → Product Brief)
Turns a selected pocket into an evidence-backed **Product Brief**. Pipeline:
`research_request → research_plan → sources → evidence (claim-traced) →
analysis (incl. falsification pass) → product opportunity → product_brief`.

```bash
python3 scripts/run_research.py                 # list pocket ids + research status
python3 scripts/run_research.py freelancer-us-tax   # run the full pipeline
```
Writes a 6-file dossier to `research/<pocket-id>/`. In the UI, open a pocket and
click **RESEARCH OPPORTUNITY** (runs the pipeline) then **Open dossier** (shows
the brief, falsification pass, traced evidence, sources, and plan queries). A
`research: <status>` badge appears on the pocket.

How content stays real:
- Every pocket has genuine discovery evidence, so any pocket yields a real
  dossier. Deeper session-researched findings live in `app/research_inputs.py`,
  keyed by pocket id — pockets **with** findings become `complete`, those
  **without** become `needs_review` (honest, not fabricated).
- Every claim traces to a source with `observed | inferred | unknown` and a
  strength. Product **format is chosen from the problem language** (keyword
  signal scoring), not defaulted to an ebook. Prices/counts that weren't
  observed stay `Unknown`. Sources that couldn't be retrieved are recorded
  `accessible: false` — the requirement is preserved for later, never guessed.
- `app/research.py` is modular: the single `gather()` stage is the swap-point
  for future live Reddit/API retrieval; nothing else changes.

The `product_brief.json` is the clean hand-off to a future Product Curation
Engine (Phase 9).

## Phase 9 — Curation engine (Product Brief → production spec)
Turns `product_brief.json` into a production-ready **specification** (not the
product). 11 deterministic stages: `load_brief → define_transformation →
derive_jobs_to_be_done → derive_components → select_component_formats →
define_component_requirements → define_asset_requirements →
define_quality_requirements → define_buyer_effort → build_production_plan →
build_curation_dossier`.

```bash
python3 scripts/run_curation.py freelancer-us-tax
```
Writes 7 files to `research/<id>/`: `product_spec`, `product_architecture`,
`component_specs`, `asset_requirements`, `quality_requirements`,
`production_plan`, `curation_dossier`. In the UI, open a pocket's dossier and
click **CURATE PRODUCT**. Endpoints: `POST /api/opportunities/<id>/curate`,
`GET /api/opportunities/<id>/curation-dossier`.

Guarantees:
- **Never defaults to an ebook** — each component's format is chosen from its
  type + the transformation (asserted at build time).
- Every component has a purpose and maps to a job / problem / desired outcome.
- Requirements tagged `evidence-backed` (traceable to a brief field) vs
  `inferred` (a design decision made by the engine).
- Preserves Phase-8 exclusions, risks, unknowns, and **inaccessible sources**
  (as evidence requirements); flags components needing **external verification**
  (tax/legal/financial/health accuracy).
- **Fails honestly**: a missing/incomplete/invalid brief raises `CurationError`
  and writes nothing (CLI exits non-zero; endpoint returns HTTP 422) — it never
  fabricates the missing fields.

`curation_dossier.json` is the Phase-10 hand-off (see below).

## Phase 9.5 — Creator / distribution fit
Answers "are there creators whose audience already contains this product's
buyers?" BEFORE building. 13 modular stages; retrieval is isolated in
`gather_creator_candidates()` (the only swap-point for future live/API/CSV
retrieval).

```bash
python3 scripts/run_distribution_validation.py freelancer-us-tax
```
Writes 8 files to `research/<id>/`: `creator_search_profile`,
`creator_candidates`, `creator_evaluations`, `distribution_evidence`,
`distribution_falsification`, `distribution_analysis`, `distribution_verdict`,
`creator_validation_dossier`. UI: open a pocket's curation card and click
**VALIDATE DISTRIBUTION**. Endpoints: `POST /api/opportunities/<id>/validate-distribution`,
`GET /api/opportunities/<id>/distribution-dossier`.

**Manual creator import** (until live retrieval is wired): drop real creators in
`data/creator_candidates/<id>.json` (`{"candidates":[...]}`, see the
`freelancer-us-tax.json` example) and re-run — processed identically to future
auto-discovered candidates.

Honesty guarantees:
- **No fabrication** of creators/followers/views/comments/URLs. Unknown stays
  `null`/`"unknown"`; every creator fact carries a `source_ref`.
- 8 weighted dimensions; an un-evaluable dimension is UNKNOWN, excluded from the
  overall (weight renormalised) and lowers confidence — never a guessed value.
- **Content relevance is scored separately from follower count** (exact /
  adjacent / weak / irrelevant); repeated relevant views beat one viral video.
- **Falsification is mandatory** (`distribution_falsification.json`): actively
  records why distribution might NOT work, and flags which checks are UNKNOWN.
- Verdict ∈ {STRONG_FIT, MODERATE_FIT, WEAK_FIT, **NEEDS_RESEARCH**}. With no
  candidate data the honest verdict is NEEDS_RESEARCH. Missing brief → HTTP 422
  / non-zero exit, writes nothing.

`creator_validation_dossier.json` is the Phase-10 gate: **outreach may not begin
unless the verdict is MODERATE_FIT or STRONG_FIT.**

## Market Universe (Build 1) — Market → Submarket → Audience
An upstream, first-class taxonomy that will later feed the funnel
(`Audience → Problems → Opportunities → Research → Product → Creators`). Built
separately from the Phase-1 `industries/` model so Phases 1–9.5 are untouched.

```bash
python3 scripts/build_universe.py            # build + validate + persist + summarize
python3 scripts/build_universe.py --validate # validate the persisted universe only
```
Current dataset: **20 markets · 100 submarkets · 300 audiences** (targets, not quotas).

**Model** (three first-class, flat entities with explicit parent IDs):
- `Market` — `{id: mkt-<slug>, type, name, description, status, basis}`
- `Submarket` — `+ market_id`
- `Audience` — `+ market_id, submarket_id` and downstream anchors
  `problem_count`, `opportunity_count`, `creator_density` (`"unknown"`),
  `research_status` (`"unresearched"`).

IDs are **deterministic and namespaced by parent** (`sub-<market>-<submarket>`,
`aud-<market>-<submarket>-<audience>`) → unique, collision-free, idempotent.
All generated nodes are `basis: "inferred"` (taxonomy, not validated demand).
**No market size / audience size / demand / creator counts are invented.**

**Storage:** bundled JSON under `data/universe/{markets,submarkets,audiences}.json`
+ `universe_summary.json`, via `UniverseStore` (interface-compatible with the
repo's `Store` philosophy — swap for a DB later). Generation
(`seed_markets`/`expand_submarkets`/`expand_audiences`) is separate from storage,
so the seed (`scripts/universe_seed.py`) can be replaced by AI generation,
curated files, or datasets. Re-running preserves any downstream Audience fields
later builds wrote.

**Relationships** (`app/universe.py` `UniverseService`): `submarkets_for_market`,
`audiences_for_submarket`, `market_for_audience`, `path_for_audience`, `tree`.
Debug endpoints: `GET /api/universe`, `/api/universe/summary`, `/api/universe/tree`.

**Validation** (`validate_universe`, fails loudly): unique IDs, required fields,
valid parent references, no orphans, no duplicate normalized names under a
parent, valid `basis`/`status`/`type`. No silent repair.

**Relationship to the Phase-1 taxonomy:** the legacy `industries/` model
(nested, audiences are label-only `{id,label}`) still powers Phases 1–9.5. The
Universe is the intended successor upstream layer — mapping is
`industry ≈ market`, embedded submarket ≈ `Submarket`, `{id,label}` audience ≈
`Audience`. Build 2+ can migrate discovery onto the Universe; **no destructive
migration has been done.**

### Market Universe Build 2 — Audience → Raw Problem Discovery
Discovers recurring problems for an Audience and stores them as first-class
`Problem` records anchored to `audience_id`. **Raw problems only — no clustering
into opportunities (Build 3), no scoring, no products/creators.**

```bash
python3 scripts/discover_problems.py <audience-id>                 # observed (auto-import if present)
python3 scripts/discover_problems.py <audience-id> --seed-inferred # + inferred candidates
python3 scripts/discover_problems.py <audience-id> --import <file> # explicit import
python3 scripts/discover_problems.py --validate                   # validate all persisted problems
```

**Two honest evidence modes** (`app/problems.py`, 14 modular stages;
`gather_problem_sources()` is the retrieval swap-point):
- **A) Manual import** — `data/problem_sources/<audience-id>.json` → `observed`
  problems, each tracing to a real source (`source_refs` resolve; no dangling
  refs). See the Airbnb example file.
- **B) Seed-inferred** — `scripts/problem_seed.py` → `basis:"inferred"`,
  confidence `LOW`, **no** source_refs. Never presented as observed.

**Problem schema:** `{id: prb-<aud>-<normslug>, type:"problem", market_id,
submarket_id, audience_id, statement, normalized_problem, problem_type (bounded
vocab), desired_outcome, source_refs[], evidence_count, basis: observed|inferred,
confidence, confidence_reason, status}`. The `normalized_problem` slug is the
dedup key (near-duplicate raw problems collapse; observed dominates inferred on
merge). `evidence_count` = number of distinct observed sources — **not**
population frequency.

**Confidence (deterministic):** inferred → LOW; 1 observed source → LOW; 2–3 →
MEDIUM; 4+ → HIGH. Confidence is evidence strength, not commercial value.

**Storage:** `data/universe/problems.json` + `data/universe/problem_sources.json`
(source registry). Discovery replaces only the target audience's slice
(idempotent), updates that audience's `problem_count` from persisted records, and
sets `research_status:"problems_discovered"`. **Universe rebuild preserves
problems and counts** (problems live outside the markets/submarkets/audiences
files; `problem_count` is a preserved downstream field).

**Service methods** (`UniverseService`): `problems_for_audience`, `get_problem`,
`problem_sources`, `path_for_problem` (Market → Submarket → Audience → Problem).
Debug endpoints: `GET /api/universe/audience/<id>/problems`,
`GET /api/universe/problem/<id>`.

**Validator** (`--validate`): unique problem IDs, valid market/submarket/audience
refs, resolving source_refs, observed⇒has-evidence, inferred⇒no-source_refs,
valid problem_type, non-empty normalized_problem, no duplicate normalized
problems per audience, evidence_count == len(source_refs), no orphans.

### Market Universe Build 3 — Problems → Commercial Opportunity clustering
Groups an audience's related raw problems into coherent **commercial
opportunities** (problem spaces). **Not products** — no formats, calculators,
scores, creator data, or demand claims. Opportunity confidence/basis are
inherited from member problems only.

```bash
python3 scripts/build_opportunities.py <audience-id>            # automatic (deterministic) clustering
python3 scripts/build_opportunities.py <audience-id> --manual   # curated file (data/opportunity_clusters/<id>.json)
python3 scripts/build_opportunities.py --all-test-audiences [--manual]
python3 scripts/build_opportunities.py --validate               # validate all persisted opportunities
```

**Opportunity schema:** `{id: opp-<aud>-<nameslug>, type:"opportunity",
market_id, submarket_id, audience_id, name, description, problem_ids[],
problem_count, shared_desired_outcome, problem_types{}, evidence_summary
{observed_problem_count, inferred_problem_count, source_count}, source_refs[],
basis: observed|inferred|mixed, confidence, confidence_reason,
commercial_status:"unvalidated", creator_density:"unknown", score:null,
research_status:"unresearched", status}`.

**Clustering (`app/opportunities.py`, 16 stages):**
- **Automatic** — deterministic token-Jaccard similarity between problems
  (feature bag = `normalized_problem` + `desired_outcome`, audience/generic words
  stripped) + a small same-`problem_type` bonus; connected components = clusters.
  *Explicitly not grouping by `problem_type` alone.* Singletons and
  covers-~all-problems clusters are rejected (not silently accepted). V0 recall
  is intentionally conservative — see limitations.
- **Manual override** — `data/opportunity_clusters/<audience-id>.json` with
  `{clusters:[{name, problem_normalized:[...] | problem_ids:[...], allow_single?}]}`.
  Both paths share one derive/validate/persist pipeline.

**Basis & confidence (deterministic, evidence-derived):** `basis` = observed /
inferred / **mixed** from member problems. Confidence: inferred-only → LOW; ≥2
problems with ≥1 observed member or ≥2 sources → MEDIUM; ≥3 problems, ≥2 observed
members, ≥2 sources → HIGH. May exceed a single member's confidence via
aggregate evidence, never exceed what the evidence supports. `evidence_summary`
must match members (validator-enforced).

**Storage:** `data/universe/opportunities.json`. Discovery replaces only the
target audience's slice (idempotent), recomputes `audience.opportunity_count`
from persisted records. **Universe rebuild preserves opportunities + count.**

**Service methods:** `opportunities_for_audience`, `get_opportunity`,
`problems_for_opportunity`, `path_for_opportunity` (Market → Submarket →
Audience → Opportunity). Debug endpoints:
`GET /api/universe/audience/<id>/opportunities`,
`GET /api/universe/opportunity/<id>`.

**Validator** (`--validate`): unique ids; valid market/submarket/audience refs;
every member problem exists and shares the audience; `problem_count` matches;
no duplicate members; basis correctly derived; `evidence_summary` matches
members; no duplicate normalized names per audience; valid confidence; defaults
enforced (`commercial_status=unvalidated`, `creator_density=unknown`,
`score=null`, `research_status=unresearched`); no orphans.

### Market Universe Build 4 — Opportunity prioritization (commercial + evidence + priority)
Cheap screening layer that answers **"which opportunities deserve deeper
investigation first?"** — it does NOT prove money. **Non-mutating:** writes side
collections `data/universe/opportunity_scores.json` + `opportunity_rankings.json`
and joins them to opportunities at read time, so Builds 1–3 records and their
validators stay pristine.

```bash
python3 scripts/score_opportunities.py --all        # score all + write rankings
python3 scripts/score_opportunities.py <opp-id>     # score one (with optional --commercial-input/--creator-input)
python3 scripts/score_opportunities.py --validate   # validate scores + rankings
```

**Two independent axes (never collapsed):**
- `commercial_score` (0–100) — attractiveness, from 9 weighted factors.
- `evidence_score` (0–100) — how much we actually know.
- `priority_score = commercial_score × uncertainty_adjustment(evidence_band)`
  with a **floor** (HIGH×1.00, MEDIUM×0.95, LOW×0.85, VERY_LOW×0.75) — so a
  high-potential / low-evidence opportunity is surfaced, not crushed.

**Factors** each carry `{value, confidence, basis, reason, source_refs,
excluded}`. Weights (centralized in `scoring.py`, `scoring_version:"v1"`):
pain_severity 15 · problem_recurrence 10 · desired_outcome_clarity 10 ·
wtp_spending 15 · existing_solution_weakness 10 · productizability 15 ·
audience_accessibility 10 · creator_density 10 · creator_product_alignment 5.

**Unknown ≠ zero, ≠ neutral-drag.** An unknown commercial factor keeps
`value:null` / `confidence:"UNKNOWN"` and is **excluded from `commercial_score`
(remaining weights renormalized)**, so missing evidence lowers *certainty*
(`evidence_score`, `priority`), never attractiveness. Inferred factors are scored
from documented tables (`TYPE_SEVERITY`, `PRODUCTIZABILITY`) and marked
`basis:"inferred"`; observed factors require imported evidence with `source_refs`.

**Classification** (deterministic): `HIGH_PRIORITY` (commercial ≥70 & evidence
HIGH/MEDIUM), `PROMISING_NEEDS_RESEARCH` (commercial ≥70 & evidence LOW/VERY_LOW),
`MODERATE` (45–69), `LOW_PRIORITY` (<45), `INSUFFICIENT_DATA` (≈all factors
unknown). This is why *Commercial 84 / Evidence 18* → PROMISING_NEEDS_RESEARCH,
not LOW_PRIORITY.

**Lightweight creator density** (`app/creator_density.py`) — a **search-yield**
band (NONE/LOW/MEDIUM/HIGH/VERY_HIGH/UNKNOWN), *not a census*, from real
candidates imported to `data/creator_density_inputs/<opp>.json` (retrieval
isolated in `gather_creator_candidates`). **No creator accounts/followers/views
are fabricated** — with no import, density stays `UNKNOWN`. This is the cheap
"does an ecosystem appear to exist?" question, distinct from Phase-9.5's
expensive per-creator qualification.

**Manual commercial evidence** — `data/commercial_inputs/<opp>.json`
(`existing_paid_solution`, `buyer_complaint`, `solution_gap`, …) drives the
`wtp_spending` and `existing_solution_weakness` factors to `observed`.

**Risk flags** (falsification, non-destructive): `creator_ecosystem_absent`,
`no_observed_spending_evidence`, `unvalidated_inferred_cluster`,
`possible_liability_or_service`, `low_evidence`.

**Service methods:** `ranked_opportunities`, `top_opportunities(limit)`,
`score_for_opportunity`, `creator_density_for_opportunity`,
`commercial_evidence_for_opportunity`, `risk_flags_for_opportunity`. Endpoints:
`GET /api/universe/rankings`, `GET /api/universe/opportunity/<id>/score`.

**Validator** (`--validate`): factor ranges, weights sum 100, unknown explicit,
observed factors cite evidence, creator bands valid, commercial/evidence/priority
**reproducible**, classification deterministic, rankings match & ordered, ids
resolve, `scoring_version` present, no identity mutation.

#### Build 5 handoff — Top Opportunity → deeper Research / Curation / Distribution
`opportunity_rankings.json` (sorted by `priority_score`) is the queue. A **top
opportunity** (`HIGH_PRIORITY`, or `PROMISING_NEEDS_RESEARCH` chosen for
investigation) is promoted into the **existing Phase 8→9→9.5 pipeline** by
constructing a Phase-8 research request from its Universe context — its member
problems (`problems_for_opportunity`, with observed `source_refs`), audience path
(`path_for_opportunity`), `shared_desired_outcome`, and `evidence_summary` map
onto the Phase-8 brief's audience / core_problem / desired_outcome / evidence
inputs. Build 5 writes that request into `research/<opportunity-id>/` and runs
Phase 8 (research → brief) → Phase 9 (curation → spec) → Phase 9.5 (distribution,
seeded by this build's real creator-density candidates). Contract: carry
`observed` evidence forward as observed (never invent), keep `commercial_status`
honest (screening ≠ validation), and treat `priority_score` as a queue order, not
proof. Anchor stays the Universe Opportunity id.

### Market Universe Build 5 — Universe → deep pipeline bridge
Promotes a ranked Universe opportunity and drives it through the **existing**
Phase 8 (research) → Phase 9 (curation) → Phase 9.5 (distribution) engines.
Pure orchestration — no engine logic is duplicated. `app/pipeline.py`.

```bash
python3 scripts/promote_opportunity.py <opp-id> [--force]   # select for deeper investigation
python3 scripts/run_pipeline.py <opp-id> --through research|curation|distribution
python3 scripts/pipeline_status.py <opp-id> | --all | --validate
```

**Identity:** the Universe `opp-*` id IS the downstream id — `research/<opp-*>/…`,
curation, and 9.5 all key on it. No second research id is minted. Pipeline state
lives in a **side file** `data/universe/pipeline_states.json` (Build-3/4 records
stay pristine).

**Promotion** = "selected for deeper investigation" (NOT validated/profitable/
approved). Eligible without override: HIGH_PRIORITY, PROMISING_NEEDS_RESEARCH,
MODERATE; LOW_PRIORITY / INSUFFICIENT_DATA require `--force` (recorded as
`override:true`). Idempotent: the `promotion_score_snapshot` is frozen at first
promotion and never rewritten when Build-4 weights change.

**Universe → Phase-8 adapter** (`build_research_request`): audience name, member
problem statements (`related_problems`), `shared_desired_outcome`, synthesized
`core_problem`, Build-4 commercial inputs → `existing_solutions`/`solution_gaps`,
observed member-source URLs → `source_urls`. **Build-4 scores are promotion
metadata only** (`universe_request.json → priority_metadata`), never research
evidence.

**Evidence carry-forward (no laundering):** observed member problems → observed
Phase-8 claims (real `source_id`); inferred problems → inferred claims (no URL).
`observed`/`inferred`/`unknown` preserved end to end. A Universe-originated run
has **no deep findings** unless a real `app/universe_findings.py` entry exists,
so it honestly returns `needs_review` and the gate stops downstream.

**Creator seed (Build-4 → 9.5):** `seed_creator_candidates` converts Build-4
density candidates into a Phase-9.5 import (`data/creator_candidates/<opp>.json`),
deduped by platform+handle. These are **seed only** — Phase 9.5 still performs its
own qualification (Build 4 = "ecosystem appears to exist"; 9.5 = "these creators
are viable").

**Dependency gates:** curation requires `research_status=="complete"` + valid
ProductBrief; distribution requires a ProductBrief; `needs_review`/`failed` stop
progression (surfaced in `pipeline_stage`). Research completion does **not** flip
`commercial_status` to validated. `rescore_requested` is set on research
completion as a future Build-6 hook (no auto-recompute).

**Pipeline service:** `get_pipeline_state`, `promoted_opportunities`,
`research_ready_opportunities`, `blocked_opportunities`, `completed_research`,
`completed_curation`, `distribution_ready`. Endpoints:
`GET /api/universe/pipeline`, `GET /api/universe/pipeline/<opp-id>`.

**Validator** (`pipeline_status.py --validate`): promoted opp + ranking exist;
snapshot internally consistent; canonical id preserved; problem/source refs
resolve; observed claims carry sources (no laundering); gates reflected in state
(no curation-before-research, no distribution-before-brief).

#### Build 6 handoff — Product Specification → production-ready digital product
Input: a completed `research/<opp-id>/` dossier where Phase 9 produced
`product_architecture.json` + `component_specs.json` + `asset_requirements.json`
+ `quality_requirements.json` + `production_plan.json` (and `curation_dossier.json`
with `handoff.must_respect`). Build 6 consumes those to generate the **actual
files** (spreadsheet/calculator, guide/checklist, templates) per component,
following `production_plan` order and honoring `quality_requirements` +
`verification_requirements` (nothing gets released while a component is flagged
for external verification). It must: keep the `opp-*` id as anchor; treat
`priority_score`/scores as context, not proof; not ship any component whose brief
`confidence`/`commercial_status` is still unvalidated without an explicit human
gate; and write products under a new `products/<opp-id>/` tree (never mutate
Universe/research identity). Distribution (9.5) staying `NEEDS_RESEARCH` is a
signal to resolve creator evidence before, not a blocker to, spec→build — but
outreach remains a later phase.

### Market Universe Build 6 — Product Production Engine
Manufactures the **actual product files** from a completed Phase-9 spec. Consumes
the spec; never redesigns it. `app/production.py` (orchestrator + QA + gates +
`ProductService` + validator) + `app/builders.py` (format-specific builders).

```bash
python3 scripts/approve_product_build.py <opp-id>     # human gate: allow production
python3 scripts/build_product.py <opp-id> [--component <id>] [--force]
python3 scripts/run_product_qa.py <opp-id>            # structural + content QA + gate validation
python3 scripts/product_status.py <opp-id>
python3 scripts/approve_product_release.py <opp-id>   # human commercial gate (release_candidate -> approved_for_sale)
```

**Identity & isolation:** product lives only under `products/<opp-id>/`
(`manifest.json`, `production_state.json`, `components/<cid>/`, `bundle/`, `qa/`).
Upstream `research/<opp-id>/` spec files are never mutated; the `opp-*` id stays
the anchor; only `pipeline_states.json.product_build_status` is updated.

**Gates:** production requires promotion + `research_status==complete` +
`curation_status==complete` + **explicit human build approval**
(`product_build_status==approved_to_build`) + all Phase-9 files present. Missing
any → refused before any file is written.

**Builders (real files only):** `openpyxl`→XLSX, `python-docx`→DOCX, +CSV/MD/TXT.
**PDF is rendered only if reportlab/soffice/libreoffice is present** — otherwise
the DOCX master is produced and the PDF format is marked **blocked** (never
faked). A required format that can't be produced keeps the component
`format_blocked` and the release `blocked`.

**QA (two layers):** *structural* (file opens, correct type, sheets/formulas
valid, no `#REF!`, required formats present) + *content* (no forbidden
placeholders `TODO/TBD/PLACEHOLDER/…` — intentional buyer fields like
`[Property Name]` are allowed; no leaked engine terminology `opp-/prb-/basis/
scores`). Source traceability written to `products/<opp-id>/qa/source_traceability.json`.

**Honesty:** observed content stays within source limits; inferred/unknown never
presented as fact; scores never become product claims. `spec_hash` per component
enables **resumable** rebuilds and stale detection; failed components are
recorded without wiping successful work.

**Release gate:** `release_candidate` only when every component is built + QA
passed + no pending external verification + bundle assembled. It never
auto-becomes `approved_for_sale` — that's a separate human command. Pipeline
`product_build_status`: `not_started → approved_to_build → building →
blocked | release_candidate → approved`.

Endpoint: `GET /api/product/<opp-id>`.

#### Build 7 handoff — release-approved product → sellable offer (packaging / pricing / Whop / partner assets)
Input: a product with `release_status == approved_for_sale` under
`products/<opp-id>/bundle/` (real deliverables) + `manifest.json` +
`curation_dossier.json` price band + Build-4 `creator_density`/`priority` context.
Build 7 assembles the **offer**: sales copy + pricing (from the brief's observed
price band, not scores), a packaged/zipped bundle, a Whop-listing draft, and
creator-partnership assets seeded from Phase-9.5 candidates. Constraints: only
operate on `approved_for_sale` products; keep the `opp-*` anchor; do not publish
to Whop or contact creators (that is execution, later still); pricing/claims must
trace to observed evidence; a `NEEDS_RESEARCH` distribution verdict means partner
assets are drafts pending qualification, not send-ready.

### Market Universe Build 6.5 — Product completion + acceptance audit
Finishes Build 6 for the first product and decides if it earns `release_candidate`.
- **PDF fixed** via `reportlab` (real `%PDF` files for cmp-4/5/6) — no fakes.
- **9/9 components built**, bundle **complete** (journey-ordered, friendly filenames, real `START_HERE.md`).
- Production fixes: differentiated the spec's duplicate pairs (cmp-2 detailed vs cmp-7 one-page; cmp-3 host-setup vs cmp-8 guest-welcome), strengthened the tracker.
- **Acceptance audit** (`scripts/audit_product.py`) writes `qa/product_acceptance.json`,
  `qa/component_acceptance.json`, `qa/spec_compliance.json`, `qa/buyer_journey.json`.
  Weighted score (utility 30 / completeness 20 / usability 20 / cohesion 15 / value 15),
  release-gated at **≥85**.
- **Result: 77.1/100 → `revision_required`** (kept out of release; approval still refuses).
  Weaknesses attributed: production (resolved), **specification** (Phase 9 over-specified
  overlapping/guidance components → `spec_revision_required: true`), **concept** (moderate
  perceived value for the price band). No human release approval run.

### Market Universe Build 6.6 — spec revision + targeted rebuild (first feedback loop)
Acceptance evidence (6.5) → Phase-9 spec revision → targeted rebuild → re-audit.
`scripts/revise_spec.py` writes `research/<opp>/spec_revisions/revision-001.json`
and rewrites the active Phase-9 spec files to a tighter **8-component** design:
retired the two thin components (cmp-5/cmp-6), merged the step-by-step guidance
into a **Master Turnover SOP** (cmp-2), absorbed "sections hosts forget" into a
**Property Setup Workbook** (cmp-3), expanded the tracker into a **Supply +
Inventory Tracker** (cmp-1), added a **Damage & Incident Log** (cmp-10), and
broadened cmp-9 into a **Guest Message Library**. Research/evidence/scores/identity
unchanged. Retired components are recorded in the revision and excluded from the
bundle. Re-audit (V2): **77.1 → 84.6** (every dimension up); still under the 85
gate → `revision_required` held (not gamed). Residual gap is concept-level
(perceived value in a saturated niche).

### Market Universe Build 7 — human release override + sellable offer (prep only)
Human decision: **accept with known limitations** (84.6, below the 85 auto-gate).
`approve_release(override=True, override_reason=..., known_limitations=[...])`
records an `approved_with_override` release approval **without mutating historical QA**
(acceptance stays 84.6; the audit still reads `revision_required`); writes
`qa/release_override.json` and advances the manifest to `approved_for_sale`.
CLI: `approve_product_release.py <opp> --override --reason "..." --limitation "..."`.
Then **Build 7** turns the approved product into a market-ready offer:
`scripts/build_offer.py` authors `products/<opp>/offer/` — `positioning`, `naming`,
`offer`, `pricing` (traced to observed Etsy comps, launch **$17** in the $15–25 band,
**never** to internal scores), `sales_copy`, `claim_traceability` (every claim tagged
observed/inferred/product_fact/positioning_language), `whop_listing_draft` (DRAFT,
`do_not_publish`), `creative_briefs`, `creator_partnership` + revenue-share models
(70/30, 50/50, 80/20; platform fee kept a **variable**), `creator_pitch_assets`
(drafts, intentional `[placeholders]`), `distribution_readiness`
(**`assets_ready_creator_research_needed`** — Phase 9.5 still `NEEDS_RESEARCH`, 0
qualified creators). `scripts/validate_offer.py` is a genuine independent QA
(offer↔product match, price traceability, no fake proof/scarcity/$-values, math,
retired components absent, no creator marked qualified) → writes `offer/offer_qa.json`.
`app/offer.py` + `scripts/offer_status.py` read the package. **No publishing, no
outreach, no payment.** Playbook note: still E2 tooling (Stage 0 / E1 = clipping is
the gospel priority) — nothing sold, no spend.

## Extending
- New pocket/industry: add to `scripts/seed_dataset.py`, re-run the runner. (A
  later phase replaces the static seed with live Reddit/forum ingestion.)
- New storage backend: implement the `Store` interface in `store.py`.
- Reserved for later phases: `data/creators/`, and product/campaign objects.
