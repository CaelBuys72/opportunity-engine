const $ = (s, r = document) => r.querySelector(s);
const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
const esc = s => (s == null ? "" : String(s)).replace(/[&<>]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[m]));
const FACTOR_LABELS = {
  demand_evidence: "Demand evidence", pain_importance: "Pain / importance",
  clear_outcome: "Clear outcome", existing_wtp: "Existing WTP",
  solution_gap: "Solution gap", creator_density: "Creator density",
  digital_product_fit: "Product fit",
};
let ACTIVE = null;

// ---- Workspace: only opportunities that have been opened / researched (shared state).
// The full seed universe lives in the Universe Explorer; this dashboard is the
// working set you've actually promoted into Opportunity Intelligence.
const _STAGE_RANK = { distribution_complete: 0, curation_complete: 1, research_complete: 2,
                      research_needs_review: 3, research_pending: 4, opened: 5 };
async function loadWorkspace(activeId) {
  const root = $("#industries");
  let data;
  try {
    const r = await fetch("/api/universe/pipeline");
    if (!r.ok) throw new Error("no server");
    data = await r.json();
  } catch (e) {
    root.innerHTML = '<p class="muted" style="font-size:12px;line-height:1.5">Workspace needs the live server.<br><br>Explore the full universe in the <a href="explorer.html">🌌 Universe Explorer</a>.</p>';
    return;
  }
  const items = data.promoted || [];
  if (!items.length) {
    root.innerHTML = '<p class="muted" style="font-size:12px;line-height:1.5">No opportunities opened yet.<br><br>Open the <a href="explorer.html">🌌 Universe Explorer</a>, pick an opportunity, and click <b>Open in Opportunity Intelligence</b> — it will appear here.</p>';
    return;
  }
  items.sort((a, b) => (_STAGE_RANK[a.pipeline_stage] ?? 9) - (_STAGE_RANK[b.pipeline_stage] ?? 9)
    || (b.priority_score || 0) - (a.priority_score || 0));
  root.innerHTML = "";
  items.forEach(p => {
    const id = p.opportunity_id;
    const rs = p.research_status || "pending";
    const stat = rs === "complete" ? "✓ researched" : rs === "needs_review" ? "◐ needs review" : "○ not researched";
    const curated = p.curation_status && !["not_started", "pending", "failed"].includes(p.curation_status);
    const wrap = el("div", "ws-item");
    const btn = el("button", "pocket-btn" + (id === activeId ? " active" : ""),
      `<span>${esc(p.name || id)}</span><span class="s">${p.priority_score ?? "—"}</span>`);
    btn.dataset.oid = id;
    btn.onclick = () => { history.pushState({}, "", "?focus=" + encodeURIComponent(id)); openUniverseFocus(id); };
    const meta = el("div", "ws-meta",
      `<span class="ws-stat rs-${rs}">${stat}</span>${curated ? ' · <span class="ws-stat rs-complete">curated</span>' : ""}`);
    wrap.append(btn, meta);
    root.appendChild(wrap);
  });
}

async function loadGraph() {
  const root = $("#industries");
  let g;
  try {
    const r = await fetch("/api/graph");
    if (!r.ok) throw new Error("no server");
    g = await r.json();
  } catch (e) {
    // static deploy (no live server): the legacy pocket browser needs the Python
    // backend. The Universe Explorer + opportunity hand-off card work without it.
    root.innerHTML = '<p class="muted" style="font-size:12px;line-height:1.5">Live pocket workflow needs the local server (<code>python3 app/server.py</code>).<br><br>Explore the full universe in the <a href="explorer.html">🌌 Universe Explorer</a>.</p>';
    return;
  }
  root.innerHTML = "";
  if (!g.industries.length) { root.innerHTML = '<p class="muted">No data yet. Run: python3 scripts/run_discovery.py</p>'; return; }
  g.industries.forEach(ind => root.appendChild(renderIndustry(ind)));
}

function renderIndustry(ind) {
  const wrap = el("div", "ind");
  const btn = el("button", null, `<span>${esc(ind.name)}</span><span class="count">${ind.pocket_count} pocket${ind.pocket_count === 1 ? "" : "s"}</span>`);
  const body = el("div", "sub"); body.hidden = true;
  ind.submarkets.forEach(sm => {
    if (!sm.pockets.length && ind.submarkets.length > 1) return; // hide empty submarkets when others have pockets
    body.appendChild(el("h4", null, esc(sm.name)));
    if (!sm.pockets.length) { body.appendChild(el("p", "muted", '<span style="font-size:12px">no pockets yet</span>')); return; }
    sm.pockets.forEach(p => {
      const pb = el("button", "pocket-btn", `<span>${esc(p.title)}</span><span class="s">${p.overall}</span>`);
      pb.dataset.pid = p.id;
      pb.onclick = () => { document.querySelectorAll(".pocket-btn.active").forEach(x => x.classList.remove("active")); pb.classList.add("active"); openPocket(p.id); };
      body.appendChild(pb);
    });
  });
  btn.onclick = () => { body.hidden = !body.hidden; };
  wrap.append(btn, body);
  return wrap;
}

async function openPocket(id) {
  ACTIVE = id;
  const p = await (await fetch("/api/opportunities/" + id)).json();
  const d = $("#detail");
  const s = p.score;
  const factors = Object.entries(FACTOR_LABELS).map(([k, label]) => {
    const f = s.factors[k] || {};
    const val = f.score == null ? "—" : f.score;
    const w = f.score == null ? 0 : (f.score / 10) * 100;
    return `<div class="factor"><span class="name">${label}<span class="basis ${f.basis}">${f.basis}</span></span>
      <span class="bar"><i style="width:${w}%"></i></span><span class="val">${val}</span>
      ${f.rationale ? `<span class="rat">${esc(f.rationale)}</span>` : ""}</div>`;
  }).join("");

  const list = (arr) => arr && arr.length ? `<ul class="clean">${arr.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : '<p class="muted">—</p>';
  const evidence = (p.evidence || []).map(e => `<div class="ev"><p>${esc(e.quote_or_observation)}</p>
      <p class="meta"><span class="basis ${e.basis}">${e.basis}</span> · ${esc(e.source_type)}${e.date ? " · " + esc(e.date) : ""}
      ${e.source_url ? ` · <a href="${esc(e.source_url)}" target="_blank" rel="noopener">source ↗</a>` : " · <em>no URL</em>"}</p></div>`).join("") || '<p class="muted">—</p>';
  const comms = (p.communities || []).map(c => `<a href="${esc(c.url || "#")}" target="_blank" rel="noopener">${esc(c.name)}
      <span class="size">${c.size ? "· " + c.size.toLocaleString() : "· size unknown"}</span></a>`).join("") || '<span class="muted">—</span>';
  const sources = (p.source_urls || []).map(u => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></li>`).join("");

  const researched = ["complete", "needs_review"].includes(p.research_status);
  d.innerHTML = `
    <div class="crumbs">${esc(p.industry_id)} ${p.submarket_id ? "› " + esc(p.submarket_id) : ""}</div>
    <div class="title-row">
      <div><h2 class="title">${esc(p.title)}</h2>
        <span class="badge ${s.confidence}">${s.confidence} confidence</span>
        <span class="badge status">${esc(p.status)}</span>
        <span class="badge rs rs-${p.research_status || "not_started"}">research: ${esc((p.research_status || "not_started").replace("_", " "))}</span>
        ${s.weight_unknown_pct ? `<span class="badge LOW">${s.weight_unknown_pct}% weight unknown</span>` : ""}
      </div>
      <div class="scorebox"><div class="big">${s.overall}<span>/100</span></div></div>
    </div>

    <section class="card"><h3>Audience &amp; problem</h3>
      <div class="kv"><b>Audience</b>${esc(p.audience)}</div>
      <div class="kv"><b>Core problem</b>${esc(p.core_problem)}</div>
      <div class="kv"><b>Desired outcome</b>${esc(p.desired_outcome)}</div>
    </section>

    <section class="card"><h3>Opportunity score</h3><div class="factors">${factors}</div>
      <p class="rat" style="margin-top:10px">${esc(s.confidence_reason)}</p></section>

    <section class="card"><h3>Related problems (clustered)</h3>${list(p.related_problems)}</section>

    <section class="card"><h3>Demand evidence</h3>${evidence}</section>

    <section class="card"><h3>Communities</h3><div class="comm">${comms}</div></section>

    <section class="card"><h3>Existing solutions</h3>${list(p.existing_solutions)}
      <h3 style="margin-top:14px">Solution gaps</h3>${list(p.solution_gaps)}</section>

    <section class="card"><h3>Creator ecosystem</h3><p style="margin:0">${esc(p.creator_ecosystem)}</p>
      <h3 style="margin-top:14px">Digital product fit</h3><p style="margin:0">${esc(p.digital_product_fit)}</p></section>

    ${sources ? `<section class="card"><h3>Sources</h3><ul class="clean">${sources}</ul></section>` : ""}

    <div class="cta">
      <button class="primary" id="research-btn">${researched ? "Re-run research" : "RESEARCH OPPORTUNITY →"}</button>
      ${researched ? `<button class="primary" id="view-btn" style="background:rgba(123,92,255,.25);color:#e9f2ff">Open dossier ▾</button>` : ""}
      <span class="result" id="research-result"></span>
    </div>
    <div id="dossier"></div>`;

  $("#research-btn").onclick = () => runResearch(p.id);
  if (researched) { $("#view-btn").onclick = () => showDossier(p.id); }
}

async function runResearch(id) {
  const rb = $("#research-btn"); rb.disabled = true; rb.textContent = "Researching…";
  const r = await (await fetch(`/api/opportunities/${id}/research`, { method: "POST" })).json();
  rb.disabled = false; rb.textContent = "Re-run research";
  $("#research-result").innerHTML = `Dossier ${r.research_status.replace("_", " ")} · ${r.counts.sources} sources · ${r.counts.claims} traced claims → <code>research/${id}/</code>`;
  showDossier(id);
  loadGraph();
}

async function showDossier(id) {
  const d = await (await fetch(`/api/opportunities/${id}/dossier`)).json();
  const box = $("#dossier");
  if (!d || d.error) { box.innerHTML = '<p class="muted">No dossier yet.</p>'; return; }
  const b = d.product_brief, pl = d.research_plan, ev = (d.evidence || {}).claims || [], sr = (d.sources || {}).sources || [];
  const li = a => (a && a.length ? `<ul class="clean">${a.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : '<p class="muted">—</p>');
  const claims = ev.map(c => `<div class="ev"><p>${esc(c.claim)}</p>
      <p class="meta"><span class="basis ${c.basis}">${c.basis}</span> · ${esc(c.strength)} · ${esc(c.source_type)}
      ${c.interpretation ? " · " + esc(c.interpretation) : ""}</p>
      <p class="meta" style="opacity:.75">“${esc(c.evidence)}”</p></div>`).join("");
  const srcs = sr.map(s => `<li>[T${s.tier}] ${esc(s.label)} ${s.accessible ? "" : '<span class="basis unknown">inaccessible</span>'}
      ${s.url ? `· <a href="${esc(s.url)}" target="_blank" rel="noopener">↗</a>` : ""}</li>`).join("");
  const q = (pl.queries || []).slice(0, 6).map(x => `<li><b>${esc(x.angle)}</b>: <code>${esc(x.query)}</code></li>`).join("");
  box.innerHTML = `
    <section class="card dossier"><h3>🧪 Product brief — ${esc(b.product_format)}</h3>
      <div class="kv"><b>Concept</b>${esc(b.product_concept)}</div>
      <div class="kv"><b>Core transformation</b>${esc(b.core_transformation)}</div>
      <div class="kv"><b>Promise</b>${esc(b.product_promise)}</div>
      <div class="kv"><b>Why this format</b>${esc(b.why_this_format)}</div>
      <div class="kv"><b>Structure</b>${li(b.product_structure)}</div>
      <div class="grid2">
        <div><b class="lbl">Tools</b>${li(b.required_tools)}</div>
        <div><b class="lbl">Templates</b>${li(b.required_templates)}</div>
        <div><b class="lbl">Worksheets</b>${li(b.required_worksheets)}</div>
        <div><b class="lbl">Bonus</b>${li(b.bonus_assets)}</div>
      </div>
      <div class="kv"><b>Do NOT include</b>${li(b.exclude)}</div>
      <div class="kv"><b>Differentiation</b>${li(b.differentiation)}</div>
      <div class="kv"><b>Price</b>${esc(b.price_range)} — <span class="muted">${esc(b.price_rationale)}</span></div>
      <div class="grid2">
        <div><b class="lbl">Objections</b>${li(b.key_objections)}</div>
        <div><b class="lbl">Buying motivations</b>${li(b.key_buying_motivations)}</div>
      </div>
      <div class="kv"><b>Customer language</b>${li(b.key_customer_language)}</div>
      <div class="kv"><b>Evidence summary</b>${esc(b.evidence_summary)}</div>
      <div class="kv"><b>Confidence</b><span class="badge ${b.confidence}">${b.confidence}</span></div>
      <div class="kv"><b>Risks / unknowns</b>${li(b.risks_unknowns)}</div>
    </section>
    <section class="card dossier"><h3>Contradiction / falsification pass</h3>${li((d.analysis || {}).contradictions)}</section>
    <section class="card dossier"><h3>Traced evidence (${ev.length})</h3>${claims || '<p class="muted">—</p>'}</section>
    <section class="card dossier"><h3>Sources (${sr.length})</h3><ul class="clean">${srcs}</ul></section>
    <section class="card dossier"><h3>Research plan — queries</h3><ul class="clean">${q}</ul>
      <b class="lbl">Questions to answer</b>${li(pl.questions)}</section>
    <div class="cta"><button class="primary" id="curate-btn">CURATE PRODUCT →</button>
      <span class="result" id="curate-result"></span></div>
    <div id="curation"></div>`;
  $("#curate-btn").onclick = () => curateProduct(id);
  showCuration(id, true);   // silently show if already curated
  box.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function curateProduct(id) {
  const b = $("#curate-btn"); b.disabled = true; b.textContent = "Curating…";
  const r = await (await fetch(`/api/opportunities/${id}/curate`, { method: "POST" })).json();
  b.disabled = false; b.textContent = "Re-curate";
  if (r.error) { $("#curate-result").innerHTML = `<span style="color:var(--bad)">Refused (honest): ${esc(r.error)}</span>`; $("#curation").innerHTML = ""; return; }
  $("#curate-result").innerHTML = `Spec built · ${r.counts.components} components · ${r.counts.verification_required} need verification · ${r.counts.unresolved} unresolved → <code>research/${id}/curation_dossier.json</code>`;
  showCuration(id);
}

async function showCuration(id, quiet) {
  const res = await fetch(`/api/opportunities/${id}/curation-dossier`);
  if (!res.ok) { if (!quiet) $("#curation").innerHTML = '<p class="muted">No product spec yet.</p>'; return; }
  const c = await res.json();
  const li = a => (a && a.length ? `<ul class="clean">${a.map(x => `<li>${esc(typeof x === "string" ? x : JSON.stringify(x))}</li>`).join("")}</ul>` : '<p class="muted">—</p>');
  const t = c.transformation;
  const comps = c.components.map(x => `<div class="ev"><p><b>${esc(x.name)}</b> — <span class="basis inferred">${esc(x.format)}</span></p>
      <p class="meta">${esc(x.purpose)} · jobs: ${x.maps_to_jobs.join(", ")}</p></div>`).join("");
  const assets = c.asset_requirements.map(a => `<li>${esc(a.for)} → <b>${esc(a.deliverable)}</b>${a.requires_external_verification ? ' <span class="basis unknown">verify</span>' : ""}</li>`).join("");
  const qglob = (c.quality_requirements.global || []).map(x => `<li>${esc(x.req)} <span class="basis ${x.basis === "evidence-backed" ? "observed" : "inferred"}">${esc(x.basis)}</span></li>`).join("");
  const seq = c.production_sequence.map(s => `<li><b>${s.order}.</b> ${esc(s.step)}${s.verification_gate ? ` <span class="basis unknown">gate: ${esc(s.verification_gate)}</span>` : ""}</li>`).join("");
  const verif = c.verification_requirements.map(v => `<li><b>${esc(v.name)}</b> — ${esc(v.reason)} <span class="muted">(by: ${esc(v.verified_by)})</span></li>`).join("") || '<p class="muted">none</p>';
  $("#curation").innerHTML = `
    <section class="card dossier" style="border-color:rgba(82,214,154,.35)"><h3>🏗️ Product spec — ${esc(c.product_format)}</h3>
      <div class="kv"><b>Transformation</b>${esc(t.from_state)} → <b>${esc(t.to_state)}</b></div>
      <div class="kv"><b>Components (${c.components.length})</b>${comps}</div>
      <div class="kv"><b>Asset requirements</b><ul class="clean">${assets}</ul></div>
      <div class="kv"><b>Quality requirements</b><ul class="clean">${qglob}</ul>
        <span class="muted" style="font-size:12px">exclusions preserved: ${(c.quality_requirements.exclusions_preserved || []).length}</span></div>
      <div class="kv"><b>Production sequence</b><ul class="clean">${seq}</ul></div>
      <div class="kv"><b>⚠ Verification requirements</b><ul class="clean">${verif}</ul></div>
      <div class="kv"><b>Unresolved questions</b>${li(c.unresolved_questions)}</div>
      <div class="kv"><b>Basis</b><span class="muted">${c.basis_summary.component_requirements_evidence_backed} evidence-backed · ${c.basis_summary.component_requirements_inferred} inferred requirements</span></div>
      <div class="kv"><b>→ Phase 10 hand-off</b><span class="muted">${esc(c.handoff.consumes)}</span></div>
    </section>
    <div class="cta"><button class="primary" id="dist-btn">VALIDATE DISTRIBUTION →</button>
      <span class="result" id="dist-result"></span></div>
    <div id="distribution"></div>`;
  $("#dist-btn").onclick = () => validateDistribution(id);
  showDistribution(id, true);
}

const VERDICT_CLASS = { STRONG_FIT: "HIGH", MODERATE_FIT: "MEDIUM", WEAK_FIT: "LOW", NEEDS_RESEARCH: "LOW" };

async function validateDistribution(id) {
  const b = $("#dist-btn"); b.disabled = true; b.textContent = "Validating…";
  const r = await (await fetch(`/api/opportunities/${id}/validate-distribution`, { method: "POST" })).json();
  b.disabled = false; b.textContent = "Re-validate";
  if (r.error) { $("#dist-result").innerHTML = `<span style="color:var(--bad)">Refused (honest): ${esc(r.error)}</span>`; return; }
  $("#dist-result").innerHTML = `Verdict: <b>${esc(r.verdict)}</b> · ${r.counts.qualified}/${r.counts.candidates} qualified → <code>research/${id}/creator_validation_dossier.json</code>`;
  showDistribution(id);
}

async function showDistribution(id, quiet) {
  const res = await fetch(`/api/opportunities/${id}/distribution-dossier`);
  if (!res.ok) { if (!quiet) $("#distribution").innerHTML = '<p class="muted">Not validated yet.</p>'; return; }
  const d = await res.json();
  const v = d.verdict, sc = d.score, den = d.distribution_density;
  const li = a => (a && a.length ? `<ul class="clean">${a.map(x => `<li>${esc(typeof x === "string" ? x : JSON.stringify(x))}</li>`).join("")}</ul>` : '<p class="muted">—</p>');
  const dims = Object.entries(sc.dimensions).map(([k, o]) => {
    const val = o.score == null ? "—" : o.score, w = o.score == null ? 0 : (o.score / 10) * 100;
    return `<div class="factor"><span class="name">${k.replace(/_/g, " ")}<span class="basis ${o.basis}">${o.basis}</span></span>
      <span class="bar"><i style="width:${w}%"></i></span><span class="val">${val}</span></div>`;
  }).join("");
  $("#distribution").innerHTML = `
    <section class="card dossier" style="border-color:rgba(123,92,255,.45)">
      <h3>📡 Distribution fit — <span class="badge ${VERDICT_CLASS[v.verdict]}">${esc(v.verdict)}</span> <span class="badge ${v.confidence}">${esc(v.confidence)}</span></h3>
      <div class="kv"><b>Reason</b>${esc(v.reason)}</div>
      <div class="grid2">
        <div><b class="lbl">Qualified creators</b>${v.qualified_creator_count} of ${v.creator_count}</div>
        <div><b class="lbl">Highly qualified</b>${v.highly_qualified_count}</div>
        <div><b class="lbl">Relevant content items</b>${den.relevant_content_count}</div>
        <div><b class="lbl">Score</b>${sc.overall}/100 · ${sc.weight_unknown_pct}% unknown</div>
      </div>
      <div class="kv"><b>Dimensions</b><div class="factors">${dims}</div></div>
      <div class="kv"><b>Strongest creators</b>${li(v.strongest_creators)}</div>
      <div class="kv"><b>Strongest content signals</b>${li(v.strongest_content_signals)}</div>
      <div class="kv"><b>⚠ Falsification — contradictory evidence</b>${li(v.contradictory_evidence)}</div>
      <div class="kv"><b>Major risks</b>${li(v.major_risks)}</div>
      <div class="kv"><b>Unknowns (reduce confidence)</b>${li(v.unknowns)}</div>
      <div class="kv"><b>Next validation action</b>${esc(v.next_action)}</div>
      <div class="kv"><b>→ Phase 10 gate</b><span class="muted">${esc(d.handoff.gate)}</span></div>
    </section>`;
}

// ---- Universe Explorer handoff: /?focus=<universe-opp-id> resolves the opportunity
// (live-first, so dynamically-generated opps work) and runs the Phase-8 workflow:
// Research → dossier → gated Curate. Reuses the existing universe pipeline endpoints.
const _UNK = v => (v == null || v === "" || v === "unknown") ? '<span class="basis unknown">Unknown</span>' : esc(v);
const _liveFirst = async (live, stat) => { try { const r = await fetch(live); if (r.ok) return await r.json(); } catch (e) {} try { const r = await fetch(stat); if (r.ok) return await r.json(); } catch (e) {} return null; };

async function openUniverseFocus(id) {
  const [o, pipe] = await Promise.all([
    _liveFirst("/api/universe/opportunity/" + id, "graph/opportunity/" + id + ".json"),
    fetch("/api/universe/pipeline/" + id).then(r => r.ok ? r.json() : null),
  ]);
  const d = $("#detail");
  if (!o || o.error) { d.innerHTML = `<div class="empty"><h2>Opportunity not found</h2><p class="muted">${esc(id)}</p><p><a href="explorer.html">← Back to Universe Explorer</a></p></div>`; return; }
  // Register into the shared workspace (idempotent, no API spend) so it persists
  // as its own item, then refresh + highlight the sidebar list.
  if (!pipe) { fetch("/api/universe/opportunity/" + encodeURIComponent(id) + "/open", { method: "POST" })
    .then(() => loadWorkspace(id)).catch(() => {}); }
  else { loadWorkspace(id); }
  const s = o.score || {};
  const path = o.path || [];
  const probs = (o.problems || []).map(p => `<li>${esc(p.statement)}</li>`).join("") || '<li class="muted">—</li>';
  const pipeRows = pipe ? `<div class="grid2">
        <div><b class="lbl">Promotion</b>${_UNK(pipe.promotion_status)}</div>
        <div><b class="lbl">Stage</b>${_UNK(pipe.pipeline_stage)}</div>
        <div><b class="lbl">Research</b>${_UNK(pipe.research_status)}</div>
        <div><b class="lbl">Curation</b>${_UNK(pipe.curation_status)}</div></div>` : '<p class="muted">Not promoted into the pipeline yet.</p>';
  d.innerHTML = `
    <div class="crumbs">${esc(path.slice(0, -1).join(" › "))}</div>
    <div class="title-row">
      <div><h2 class="title">${esc(o.name)}</h2>
        <span class="badge status">universe opportunity</span>
        <span class="badge ${s.priority_score >= 60 ? "HIGH" : s.priority_score >= 45 ? "MEDIUM" : "LOW"}">${esc(s.priority_classification || "unknown")}</span>
      </div>
      <div class="scorebox"><div class="big">${s.priority_score ?? "—"}<span>/100</span></div></div>
    </div>
    <section class="card"><h3>Commercial priority (Build 4)</h3>
      <div class="grid2">
        <div><b class="lbl">Commercial score</b>${_UNK(s.commercial_score)}</div>
        <div><b class="lbl">Evidence score</b>${_UNK(s.evidence_score)} ${s.evidence_band ? `<span class="muted">(${esc(s.evidence_band)})</span>` : ""}</div>
        <div><b class="lbl">Priority score</b>${_UNK(s.priority_score)}</div>
        <div><b class="lbl">Priority class</b>${_UNK(s.priority_classification)}</div>
      </div>
      <p class="muted" style="font-size:12px;margin-top:6px">Why we chose to investigate — not evidence of reality. Phase 8 establishes what's actually true.</p>
    </section>
    <section class="card"><h3>Pipeline state</h3>${pipeRows}</section>
    <section class="card"><h3>Member problems (${(o.problems || []).length})</h3><ul class="clean">${probs}</ul></section>
    <div class="cta">
      <button class="primary" id="u-research">${pipe && pipe.research_status ? "Re-run research" : "RESEARCH OPPORTUNITY →"}</button>
      <span class="result" id="u-research-result"></span>
    </div>
    <div id="u-dossier"></div>
    <div class="cta"><a href="explorer.html" style="color:#c9bcff">← Back to Universe Explorer</a></div>`;
  $("#u-research").onclick = () => runUniverseResearch(id);
  showUniverseDossier(id);   // load an existing dossier if present
}

async function runUniverseResearch(id) {
  const b = $("#u-research"), res = $("#u-research-result");
  b.disabled = true; b.textContent = "Researching… (live web, ~1–2 min)";
  res.textContent = "Executing research plan: searching → retrieving pages → answering questions…";
  let r;
  try { r = await (await fetch("/api/universe/opportunity/" + encodeURIComponent(id) + "/research", { method: "POST" })).json(); }
  catch (e) { res.innerHTML = `<span style="color:var(--bad)">Request failed: ${esc(e.message)}</span>`; b.disabled = false; b.textContent = "RESEARCH OPPORTUNITY →"; return; }
  b.disabled = false; b.textContent = "Re-run research";
  if (!r.ok) { res.innerHTML = `<span style="color:var(--bad)">${esc(r.error || "research failed")}</span>`; return; }
  const c = r.counts || {};
  let note = "";
  if (r.execution_error) {
    const quota = /429|quota/i.test(r.execution_error);
    note = ` <span style="color:var(--warn)">· live research couldn't complete (${quota ? "LLM daily quota exceeded — try later or add billing/another key" : esc(r.execution_error)})${r.preserved ? "; prior dossier preserved" : ""}</span>`;
  }
  res.innerHTML = `Research <b>${esc(r.research_status)}</b> · ${c.sources ?? "?"} sources · ${c.critical_unresolved ?? 0} critical unresolved${note}`;
  showUniverseDossier(id);
}

async function showUniverseDossier(id) {
  const box = $("#u-dossier");
  const doss = await fetch("/api/universe/opportunity/" + id + "/dossier").then(r => r.ok ? r.json() : null);
  if (!doss || doss.error) { box.innerHTML = ""; return; }
  const b = doss.product_brief || {}, plan = doss.research_plan || {};
  const qd = doss.questions || {};
  const q = qd.questions || (doss.analysis && doss.analysis.answered_questions) || [];
  const crit = qd.critical_unresolved || [];
  const acc = qd.accounting || plan.accounting || {};
  const pi = qd.product_implications || (doss.analysis && doss.analysis.product_implications) || {};
  const outcome = qd.research_outcome || "";
  const li = a => (a && a.length) ? `<ul class="clean">${a.map(x => `<li>${esc(typeof x === "string" ? x : JSON.stringify(x))}</li>`).join("")}</ul>` : '<p class="muted">—</p>';
  const stCls = s => s === "SUPPORTED" ? "observed" : (s === "UNKNOWN" || s === "CONTRADICTED") ? "unknown" : "inferred";
  const qcard = (list) => list.length ? list.map(x => `<div class="ev"><p>${esc(x.question)}</p>
      <p class="meta"><span class="basis ${stCls(x.status)}">${esc(x.status)}</span> · ${esc(x.confidence || "")} · ${esc(x.answer || "")}</p>
      ${x.product_implication ? `<p class="meta" style="opacity:.8">→ ${esc(x.product_implication)}</p>` : ""}</div>`).join("") : '<p class="muted">—</p>';
  const universal = q.filter(x => (x.question_type || "universal") === "universal");
  const dynamic = q.filter(x => x.question_type === "dynamic");
  const executed = (plan.executed || []).slice(0, 16).map(e => `<li><code>${esc(e.query)}</code> <span class="muted">(${esc(e.intent || "")})</span> → ${e.results} results, ${e.sources_retained} kept</li>`).join("");
  const comps = (pi.must_have_components || []).map(m => `<li>${esc(m.component)} <span class="basis ${m.basis === "observed" ? "observed" : "inferred"}">${esc(m.basis || "inferred")}</span> <span class="muted small">— ${esc(m.buyer_job || "")}</span></li>`).join("");
  const outcomeBadge = outcome === "READY" ? '<span class="badge rs-complete">READY</span>'
    : outcome === "WEAK_NO_PRODUCT" ? '<span class="badge LOW">WEAK / NO CLEAR PRODUCT</span>'
    : '<span class="badge rs-needs_review">NEEDS MORE RESEARCH</span>';
  box.innerHTML = `
    <section class="card dossier"><h3>Research status ${outcomeBadge}</h3>
      <div class="grid2">
        <div><b class="lbl">Search results discovered</b>${acc.search_results_discovered ?? "—"}</div>
        <div><b class="lbl">Unique candidate sources</b>${acc.unique_candidate_sources ?? "—"}</div>
        <div><b class="lbl">Sources selected</b>${acc.sources_selected ?? "—"}</div>
        <div><b class="lbl">Sources retrieved</b>${acc.sources_retrieved ?? "—"}</div>
        <div><b class="lbl">Evidence-bearing sources</b>${acc.evidence_bearing_sources ?? "—"}</div>
        <div><b class="lbl">Critical unresolved</b>${crit.length}</div>
      </div>
      ${crit.length ? `<div class="kv"><b>Unresolved critical questions</b>${li(crit)}</div>` : ""}
    </section>
    <section class="card dossier"><h3>Universal questions</h3>${qcard(universal)}</section>
    <section class="card dossier"><h3>Opportunity-specific questions</h3>${qcard(dynamic)}</section>
    <section class="card dossier"><h3>🧭 Product implications (evidence-based)</h3>
      <div class="kv"><b>Core problem</b>${_UNK(pi.core_problem)}</div>
      <div class="kv"><b>Product mechanism</b>${_UNK(pi.product_mechanism)}</div>
      <div class="kv"><b>Failure modes</b>${li(pi.failure_modes)}</div>
      <div class="kv"><b>Free / good-enough alternatives</b>${li(pi.free_alternatives)}</div>
      <div class="kv"><b>Must-have components</b>${comps ? `<ul class="clean">${comps}</ul>` : '<p class="muted">—</p>'}</div>
      <div class="kv"><b>Do NOT build</b>${li(pi.do_not_build)}</div>
      <div class="kv"><b>Contradictions</b>${li(pi.contradictions)}</div>
    </section>
    <section class="card dossier"><h3>🧪 Product Brief (from executed research)</h3>
      <div class="kv"><b>Concept</b>${_UNK(b.product_concept)}</div>
      <div class="kv"><b>Format</b>${_UNK(b.product_format)} <span class="muted small">${esc(b.why_this_format || "")}</span></div>
      <div class="kv"><b>Price</b>${_UNK(b.price_range)} — <span class="muted">${esc(b.price_rationale || "")}</span></div>
      <div class="kv"><b>Risks / unknowns</b>${li(b.risks_unknowns)}</div>
    </section>
    ${executed ? `<section class="card dossier"><h3>Executed queries</h3><ul class="clean">${executed}</ul>${plan.retrieval ? `<p class="muted small">pages retrieved: ${plan.retrieval.ok} ok · ${plan.retrieval.failed} failed/blocked</p>` : ""}</section>` : ""}
    <div class="cta">
      <button class="primary" id="u-curate">CURATE PRODUCT →</button>
      <span class="result" id="u-curate-result"></span>
    </div>
    <div id="u-curation"></div>
    <div id="u-product"></div>
    <div id="u-creators"></div>`;
  $("#u-curate").onclick = () => curateUniverse(id, false);
  showUniverseProduct(id);
  showUniverseCreators(id);
}

// ---- Creator discovery: live shortlist for outreach (Serper + Groq) ----
async function showUniverseCreators(id) {
  const box = $("#u-creators");
  if (!box) return;
  const d = await fetch("/api/universe/opportunity/" + encodeURIComponent(id) + "/creators")
    .then(r => r.ok ? r.json() : null).catch(() => null);
  let inner;
  if (d && (d.creators || []).length) {
    const rows = d.creators.map(c => {
      const emails = (c.contact_emails || []).length
        ? c.contact_emails.map(e => `<a href="mailto:${esc(e)}">${esc(e)}</a>`).join(", ")
        : '<span class="muted small">no public email</span>';
      const fol = c.est_followers ? ` · ${Number(c.est_followers).toLocaleString()} followers` : "";
      return `<div class="ev"><p><b>${esc(c.name || "creator")}</b>
          <span class="basis ${(c.fit_score || 0) >= 60 ? "observed" : "inferred"}">fit ${esc(c.fit_score || 0)}</span>
          <span class="muted small">${esc(c.platform || "")}${fol}</span></p>
        <p class="meta">${esc(c.why_fit || "")}${c.caution ? ` <span class="unknown">⚠ ${esc(c.caution)}</span>` : ""}</p>
        <p class="meta">${c.url ? `<a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.url)}</a>` : ""} · ${emails}</p></div>`;
    }).join("");
    inner = `<section class="card dossier" style="border-color:rgba(123,92,255,.45)">
        <h3>🎯 Creators <span class="muted small">${d.shortlisted} shortlisted · ${d.with_contact} with contact · ${d.candidates_found} found</span></h3>
        ${rows}
        <div class="cta"><button class="primary" id="u-creators-btn" style="background:rgba(123,92,255,.25);color:#e9f2ff">Re-run discovery</button>
          <span class="result" id="u-creators-result"></span></div>
      </section>`;
  } else {
    inner = `<section class="card dossier">
        <h3>🎯 Creators</h3>
        <p class="muted small">Find creators whose audience is this buyer — live search, ranked by fit, with any public contact details. For outreach.</p>
        <div class="cta"><button class="primary" id="u-creators-btn">FIND CREATORS →</button>
          <span class="result" id="u-creators-result"></span></div>
      </section>`;
  }
  box.innerHTML = inner;
  const b = $("#u-creators-btn");
  if (b) b.onclick = () => discoverCreators(id);
}

async function discoverCreators(id) {
  const b = $("#u-creators-btn"), res = $("#u-creators-result");
  b.disabled = true; b.textContent = "Searching… (live web, ~1–2 min)";
  res.textContent = "Finding creators, checking their pages for contacts, ranking by fit…";
  let r;
  try { r = await (await fetch("/api/universe/opportunity/" + encodeURIComponent(id) + "/discover-creators", { method: "POST" })).json(); }
  catch (e) { res.innerHTML = `<span style="color:var(--bad)">Request failed: ${esc(e.message)}</span>`; b.disabled = false; b.textContent = "FIND CREATORS →"; return; }
  b.disabled = false;
  if (!r.ok) { res.innerHTML = `<span style="color:var(--bad)">${esc(r.error || "discovery failed")}</span>`; b.textContent = "FIND CREATORS →"; return; }
  res.innerHTML = `Found <b>${r.shortlisted}</b> creators (${r.with_contact} with contact) from ${r.candidates_found} results`;
  showUniverseCreators(id);
}

// ---- Build 6: manufacture the actual product files (DOCX/XLSX/CSV/MD bundle) ----
async function showUniverseProduct(id) {
  const box = $("#u-product");
  if (!box) return;
  const m = await fetch("/api/universe/opportunity/" + encodeURIComponent(id) + "/product")
    .then(r => r.ok ? r.json() : null).catch(() => null);
  const li = a => (a && a.length) ? `<ul class="clean">${a.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
  let inner = "";
  if (m) {
    const comps = (m.components || []).map(c => `<div class="ev"><p><b>${esc(c.name)}</b>
        <span class="basis ${c.production_status === "built" ? "observed" : "unknown"}">${esc(c.production_status)}</span>
        <span class="muted small">qa ${esc(c.qa_status)} · ${(c.required_formats || []).join(", ")}</span></p></div>`).join("");
    const dl = m.download_ready
      ? `<a class="handoff" style="display:inline-block;background:rgba(82,214,154,.22);color:#e9f2ff;text-decoration:none"
           href="${(window.OE && window.OE.base) || ""}/api/universe/opportunity/${encodeURIComponent(id)}/product/download">⬇ Download product bundle (.zip)</a>`
      : `<span class="muted small">Bundle not ready — see blocked reasons below.</span>`;
    const tok = m.llm_tokens_used ? ` · <span class="muted small">${m.llm_tokens_used.toLocaleString()} LLM tokens</span>` : "";
    inner = `<section class="card dossier" style="border-color:rgba(82,214,154,.45)">
        <h3>📦 Product <span class="badge ${m.product_status === "release_candidate" ? "rs-complete" : "LOW"}">${esc(m.product_status)}</span>${tok}</h3>
        <div class="kv"><b>Components (${(m.components || []).length})</b>${comps || '<p class="muted">—</p>'}</div>
        ${(m.release_blocked_reasons || []).length ? `<div class="kv"><b>Blocked</b>${li(m.release_blocked_reasons)}</div>` : ""}
        <div class="cta">${dl}
          <button class="primary" id="u-produce" style="background:rgba(123,92,255,.25);color:#e9f2ff">Regenerate product</button>
          <span class="result" id="u-produce-result"></span></div>
      </section>`;
  } else {
    inner = `<section class="card dossier">
        <h3>📦 Product</h3>
        <p class="muted small">Generate the actual product files (documents, spreadsheets, checklists) from the curated spec — bundled as a downloadable .zip. Requires completed curation.</p>
        <div class="cta"><button class="primary" id="u-produce">GENERATE PRODUCT →</button>
          <span class="result" id="u-produce-result"></span></div>
      </section>`;
  }
  box.innerHTML = inner;
  const b = $("#u-produce");
  if (b) b.onclick = () => produceUniverse(id);
}

async function produceUniverse(id) {
  const b = $("#u-produce"), res = $("#u-produce-result");
  b.disabled = true; b.textContent = "Manufacturing… (writing files, ~1–2 min)";
  res.textContent = "Generating real content for each component and building the files…";
  let r;
  try { r = await (await fetch("/api/universe/opportunity/" + encodeURIComponent(id) + "/produce", { method: "POST" })).json(); }
  catch (e) { res.innerHTML = `<span style="color:var(--bad)">Request failed: ${esc(e.message)}</span>`; b.disabled = false; b.textContent = "GENERATE PRODUCT →"; return; }
  b.disabled = false;
  if (!r.ok) { res.innerHTML = `<span style="color:var(--bad)">${esc(r.error || "production failed")}</span>`; b.textContent = "GENERATE PRODUCT →"; return; }
  const built = (r.components || []).filter(c => c.status === "built").length;
  const tok = r.llm_tokens_used ? ` · ${r.llm_tokens_used.toLocaleString()} LLM tokens` : "";
  res.innerHTML = `Built <b>${built}/${(r.components || []).length}</b> components · ${esc(r.product_status)}${r.download_ready ? " · bundle ready" : ""}${tok}`;
  showUniverseProduct(id);
}

async function curateUniverse(id, override) {
  const b = $("#u-curate"), res = $("#u-curate-result");
  b.disabled = true; b.textContent = "Curating…";
  const url = "/api/universe/opportunity/" + encodeURIComponent(id) + "/curate" + (override ? "?override=1" : "");
  let r;
  try { r = await (await fetch(url, { method: "POST" })).json(); }
  catch (e) { res.innerHTML = `<span style="color:var(--bad)">Request failed: ${esc(e.message)}</span>`; b.disabled = false; b.textContent = "CURATE PRODUCT →"; return; }
  b.disabled = false; b.textContent = "CURATE PRODUCT →";
  if (!r.ok) {
    res.innerHTML = `<span style="color:var(--bad)">${esc(r.error)}</span>`;
    if (r.override_available && !override) {
      $("#u-curation").innerHTML = `<div class="cta"><button class="primary" id="u-curate-override" style="background:rgba(255,127,152,.25);color:#e9f2ff">Curate with override →</button><span class="muted small">Records the override + unresolved criticals honestly.</span></div>`;
      $("#u-curate-override").onclick = () => curateUniverse(id, true);
    }
    return;
  }
  res.innerHTML = `Curated${r.override ? " <b>(override)</b>" : ""} · ${r.verification_required ?? 0} verification requirement(s). Product spec ready → <code>research/${esc(id)}/curation_dossier.json</code>`;
  $("#u-curation").innerHTML = "";
}

const _focus = new URLSearchParams(location.search).get("focus");
loadWorkspace(_focus && _focus.startsWith("opp-") ? _focus : null);
if (_focus && _focus.startsWith("opp-")) openUniverseFocus(_focus);
window.addEventListener("popstate", () => {
  const f = new URLSearchParams(location.search).get("focus");
  if (f && f.startsWith("opp-")) openUniverseFocus(f);
});
