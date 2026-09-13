# Operator Test Plan — Universe Explorer

This is **not** a developer QA checklist. It is a guide for **you** (the operator) to
*use* the Universe Explorer manually and discover what actually needs to change.

The goal of these sessions is to generate honest entries in
[`operator_friction_log.md`](operator_friction_log.md) — not to "pass" anything.

## How to launch
```bash
cd opportunity-engine
python3 app/server.py
```
Then open **http://localhost:8777/explorer.html**

(The static graph files are already built. You only need to rebuild — `python3
scripts/build_universe.py && python3 scripts/export_static.py` — if you change the
taxonomy in `scripts/universe_seed.py`.)

Controls: click a node to expand · click again to collapse · **Esc** steps back one
layer · drag the background to pan · scroll to zoom · **Fit** / **Reset** in the top bar.

---

## SESSION 1 — FREE EXPLORATION (≈10 min)
Click around with **no goal**. Open markets that look interesting, drill in, wander.

As you go, note in the friction log anything that:
- confused you ("what's the difference between these two?")
- felt slow or awkward to reach
- made you lose your place
- looked wrong or mislabeled

Don't fix anything. Just record friction.

## SESSION 2 — TARGETED SEARCH
Pick **one market on purpose** (e.g. *Trading, Investing & Crypto*).

Navigate deliberately: **Market → Submarket → Audience.**

Try to reach an audience that feels like a real, fundable opportunity area.
Record:
- Did the submarkets match how you'd naturally divide this market?
- Did any obvious submarket feel *missing*?
- Were the audiences specific enough to picture a real person?

## SESSION 3 — OPPORTUNITY HUNT
Choose **one audience**. Ask, out loud:
1. What problems exist for this audience?
2. What does the system currently *know* (problems / opportunities / scores)?
3. What is missing?

- If problems/opportunities **exist** (try *Independent nail technicians* or
  *Airbnb hosts with 1-5 properties*): open them, read the scores and pipeline state,
  and note whether the info helps you decide.
- If they **don't exist** (most audiences): record **what the next natural action
  should be** from that empty audience — e.g. "there should be a 'generate problems'
  button here", or "I'd want to add a problem I already know about." Don't build it.

## SESSION 4 — PIPELINE HANDOFF
Choose an audience that already has an opportunity (nail or Airbnb), open the
opportunity, and click **Open in Opportunity Intelligence**.

Record the friction between *exploration* and *execution*:
- Did the jump make sense?
- Was anything lost or repeated between the two views?
- What did you expect to be able to *do* on the intelligence side that you couldn't?

## SESSION 5 — NEW TERRITORY
Choose one of the **newly added** audiences with zero problems (e.g. something under
*AI Tools & Automation*, *Sales & Closing*, or *Design & Templates*).

Ask: **"What should I naturally be able to do from here?"**
Write the answer in the friction log. **Do not implement it.** This is the single
most valuable output of the whole exercise — it tells us what the next real feature is.

---

## What "explored" vs "unexplored" looks like
An audience that already has downstream problems shows a small **count badge** (e.g.
`13`) after its label and can be expanded further. An unexplored audience has **no
badge** and terminates — that blank space is *intentional*: it's the map showing you
where the work hasn't happened yet.

## After your sessions
You should have a filled-in friction log. That log — not more code — drives what we
build next.
