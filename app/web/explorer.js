// Universe Explorer — lightweight vanilla SVG force graph over canonical universe data.
// Zero dependencies. Progressive expansion; only explored branches are rendered.
const $ = (s, r = document) => r.querySelector(s);
const SVGNS = "http://www.w3.org/2000/svg";
const esc = s => (s == null ? "" : String(s)).replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
const api = async p => (await fetch(p)).json();
// Prefer the LIVE server endpoint (reflects dynamically-researched nodes immediately);
// fall back to the committed static JSON (works on a static host with no server).
async function apiFirst(live, staticPath) {
  try {
    const r = await fetch(live);
    if (r.ok) return await r.json();
  } catch (e) { /* fall through to static */ }
  return api(staticPath);
}

// text-label nodes (learn-anything style) — base size per layer, gently boosted by richness
const NODE_FS = { market: 12.5, submarket: 11.5, audience: 11, problem: 10.5, opportunity: 11 };
// font size encodes hierarchy (base) + a SMALL importance nudge, so busy topics read
// slightly larger without the contrast being extreme.
function fontSize(n) {
  const m = n.meta || {}, base = NODE_FS[n.type] || 11;
  let boost = 0;
  if (n.type === "market") boost = (m.opportunities || 0) * 1.1 + (m.problems || 0) * 0.15;
  else if (n.type === "submarket") boost = (m.opportunities || 0) * 0.9 + (m.problems || 0) * 0.12;
  else if (n.type === "audience") boost = (m.opportunities || 0) * 0.7 + (m.problems || 0) * 0.15;
  else if (n.type === "problem") boost = (m.opportunities || 0) * 0.9 + (m.evidence_count || 0) * 0.4;
  else if (n.type === "opportunity") boost = (m.priority_score || 0) / 30;
  return Math.round((base + Math.min(boost, 5)) * 10) / 10;
}
const UNKNOWNS = new Set([null, undefined, "", "unknown", "UNKNOWN", "Unknown"]);
const val = x => UNKNOWNS.has(x) ? '<span class="unknown">Unknown</span>' : esc(x);
const short = (s, n = 22) => { s = s || ""; return s.length <= n ? s : s.slice(0, n - 1) + "…"; };

// ---- graph state ----
const nodes = new Map();      // id -> {...meta, x,y,vx,vy, expanded, parent, fixed}
const edges = new Map();      // "src|tgt" -> {source,target,type}
let selected = null;
let activeSet = null;         // ids of the focused realm (its subtree); null = show all evenly
let hoverId = null;           // id under the cursor (highlights it + neighbours)
let view = { x: 0, y: 0, k: 1 };   // pan/zoom transform
let W = 0, H = 0;                   // real element size (for fit / pan / zoom mapping)
const VW = 1280, VH = 760;         // virtual layout space (physics is DOM-size independent)
const PAD = 95;                    // keep nodes (and their labels) off the box edges

const svg = $("#graph");
const gRoot = document.createElementNS(SVGNS, "g");   // pan/zoom group
const gEdges = document.createElementNS(SVGNS, "g");
const gNodes = document.createElementNS(SVGNS, "g");
gRoot.append(gEdges, gNodes);
svg.append(gRoot);

function resize() {
  const r = svg.getBoundingClientRect();
  W = r.width || svg.clientWidth || 900;
  H = r.height || svg.clientHeight || 600;
}
window.addEventListener("resize", () => { resize(); });

// ---------------------------------------------------------------- data ops
function addNode(n, parent, ax, ay) {
  if (nodes.has(n.id)) return nodes.get(n.id);
  const jitter = () => (Math.random() - 0.5) * 160;
  const x = (ax ?? VW / 2) + jitter(), y = (ay ?? VH / 2) + jitter();
  // each node drifts toward its own home → a shapeless, area-filling scatter.
  // children home near their parent; roots are re-homed across the box in loadRoots.
  const rec = Object.assign({}, n, {
    x, y, hx: x, hy: y,
    vx: 0, vy: 0, expanded: false, parent: parent ?? null, fixed: false,
  });
  nodes.set(n.id, rec);
  return rec;
}
function addEdge(e) { edges.set(e.source + "|" + e.target, e); }

async function loadRoots() {
  nodes.clear(); edges.clear(); selected = null; activeSet = null; hoverId = null;
  const g = await apiFirst("/api/universe/graph", "graph/roots.json");
  // scatter market homes across the WHOLE box (no ring/disc) so the cloud fills the
  // area and has room to grow — force + collision keep them apart around those homes.
  g.nodes.forEach(n => {
    const rec = addNode(n, null, VW / 2, VH / 2);
    rec.x = rec.hx = PAD + Math.random() * (VW - 2 * PAD);
    rec.y = rec.hy = PAD + Math.random() * (VH - 2 * PAD);
  });
  settle(); draw();                 // first pass places nodes + measures label boxes
  settle(140); positionOnly();      // second pass separates using measured sizes
  renderBreadcrumb(); renderPanel(null);
  requestAnimationFrame(fit);       // fit once the real element size is laid out
}

async function expand(id) {
  const node = nodes.get(id);
  if (!node || !node.expandable) return;
  if (node.expanded) { collapse(id); return; }
  const g = await apiFirst("/api/universe/graph?node=" + encodeURIComponent(id),
                           "graph/node/" + id + ".json").catch(() => null);
  if (!g || g.error) return;
  const fresh = new Set(g.nodes.map(c => c.id));
  g.nodes.forEach(c => addNode(c, id, node.x, node.y));
  g.edges.forEach(addEdge);
  node.expanded = true;
  computeActive();    // fold the new children into the focused realm
  draw();             // measure the new labels
  // seed a clean dispersion of the NEW children only — pin already-settled nodes so
  // nothing that's on screen teleports; the live sim keeps animating afterwards.
  const pinned = [];
  for (const n of nodes.values()) if (!fresh.has(n.id) && !n.fixed) { n.fixed = true; pinned.push(n); }
  settle(90);
  pinned.forEach(n => { n.fixed = false; });
  positionOnly();
}

function descendants(id) {
  const out = [];
  for (const n of nodes.values()) if (n.parent === id) { out.push(n.id, ...descendants(n.id)); }
  return out;
}
function collapse(id) {
  const kids = descendants(id);
  const kill = new Set(kids);
  kids.forEach(k => nodes.delete(k));
  for (const key of [...edges.keys()]) {
    const e = edges.get(key);
    if (kill.has(e.target) || kill.has(e.source)) edges.delete(key);
  }
  const node = nodes.get(id); if (node) node.expanded = false;
  if (selected && !nodes.has(selected)) { selected = null; renderPanel(null); }
  computeActive(); reheat(); draw();
}

// focus a node from search: expand its ancestor chain so its position is understandable
async function focusNode(id, ancestors) {
  if (!nodes.size) await loadRoots();
  for (const anc of (ancestors || [])) {
    const n = nodes.get(anc);
    if (n && n.expandable && !n.expanded) await expand(anc);
  }
  const target = nodes.get(id);
  if (target) { select(id); centerOn(target); }
}

// ---------------------------------------------------------------- force sim
// Velocity/inertia model: node repulsion + soft central attraction + parent↔child
// springs + label collision + pointer repulsion + a tiny idle drift, integrated with
// damping. No node has a fixed position — every (x,y) emerges from the simulation.
const REPULSE = 6400;    // node–node repulsion (disperses the cloud)
const CENTER_K = 0.0042; // weak elastic tether toward the centre (never a snap-back)
const SPRING_K = 0.02;   // parent↔child cohesion for expanded branches
const SPRING_LEN = 98;
const DAMP = 0.84;       // velocity decay → inertia / weighted feel
const MAX_V = 7;         // speed cap (stability)
const IDLE = 0.16;       // tiny perpetual drift so it looks alive but still settles
const CURSOR_R = 165;    // hover-repulsion radius around the hovered node (virtual units)
const CURSOR_K = 6;      // hover-repulsion strength (stronger the closer they are)
// per-layer push multiplier — softer on the denser submarket/audience layers
const HOVER_PUSH = { market: 1, submarket: 0.4, audience: 0.4, problem: 0.7, opportunity: 0.7 };
const COLLIDE_PAD = 9;   // gap enforced between label boxes

function reheat() {}      // no-op: the simulation runs continuously now

function physics() {
  const arr = [...nodes.values()];
  const cx = VW / 2, cy = VH / 2;
  for (const n of arr) { n.ax = 0; n.ay = 0; }

  // node repulsion (many-body): REPULSE / d^2, capped for stability
  for (let i = 0; i < arr.length; i++) {
    const a = arr[i];
    for (let j = i + 1; j < arr.length; j++) {
      const b = arr[j];
      let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
      if (d2 < 1) { const ang = Math.random() * 6.283; dx = Math.cos(ang); dy = Math.sin(ang); d2 = 1; }
      const d = Math.sqrt(d2), f = Math.min(REPULSE / d2, 4), ux = dx / d, uy = dy / d;
      a.ax += ux * f; a.ay += uy * f; b.ax -= ux * f; b.ay -= uy * f;
    }
  }
  // parent↔child spring keeps an expanded branch cohesive
  for (const e of edges.values()) {
    const a = nodes.get(e.source), b = nodes.get(e.target);
    if (!a || !b) continue;
    let dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.5;
    const f = (d - SPRING_LEN) * SPRING_K, ux = dx / d, uy = dy / d;
    a.ax += ux * f; a.ay += uy * f; b.ax -= ux * f; b.ay -= uy * f;
  }
  // soft central attraction (elastic tether). With a realm focused, the active branch
  // is drawn in a little more and the other realms are eased outward.
  for (const n of arr) {
    if (activeSet && !activeSet.has(n.id)) {
      n.ax += (n.x - cx) * 0.010; n.ay += (n.y - cy) * 0.010;    // gently outward
    } else {
      const k = activeSet ? CENTER_K * 1.7 : CENTER_K;
      n.ax += (cx - n.x) * k; n.ay += (cy - n.y) * k;
    }
  }
  // HOVER REPULSION: only when the cursor is ON a node — its surrounding nodes are
  // pushed away from it (stronger the closer they are). Nodes settle back on mouse-out.
  // Push is softened on the denser submarket/audience layers.
  if (hoverId) {
    const h = nodes.get(hoverId);
    if (h) {
      const mult = HOVER_PUSH[h.type] ?? 1;
      for (const n of arr) {
        if (n.id === hoverId || n.fixed) continue;
        let dx = n.x - h.x, dy = n.y - h.y, d = Math.hypot(dx, dy) || 1;
        if (d < CURSOR_R) { const f = CURSOR_K * mult * (1 - d / CURSOR_R); n.ax += (dx / d) * f; n.ay += (dy / d) * f; }
      }
    }
  }
  // tiny idle drift — keeps it alive; damping + attraction still let it settle
  for (const n of arr) { n.ax += (Math.random() - 0.5) * IDLE; n.ay += (Math.random() - 0.5) * IDLE; }

  // integrate with damping + speed cap (a dragged node is pinned)
  for (const n of arr) {
    if (n.fixed) { n.vx = 0; n.vy = 0; continue; }
    n.vx = (n.vx + n.ax) * DAMP;
    n.vy = (n.vy + n.ay) * DAMP;
    const sp = Math.hypot(n.vx, n.vy);
    if (sp > MAX_V) { n.vx = n.vx / sp * MAX_V; n.vy = n.vy / sp * MAX_V; }
    n.x += n.vx; n.y += n.vy;
  }
  separate(arr);   // positional label collision (dispersion, no overlap)
  bound(arr);      // keep every node fully inside the container
}

// axis-aligned bounding-box separation over measured label sizes (n.w / n.h)
function separate(arr) {
  for (let i = 0; i < arr.length; i++) {
    const a = arr[i]; if (!a.w) continue;
    for (let j = i + 1; j < arr.length; j++) {
      const b = arr[j]; if (!b.w) continue;
      const ox = (a.w + b.w) / 2 + COLLIDE_PAD - Math.abs(a.x - b.x);
      const oy = (a.h + b.h) / 2 + COLLIDE_PAD - Math.abs(a.y - b.y);
      if (ox > 0 && oy > 0) {                       // boxes overlap → push apart
        if (ox < oy) {                              // resolve on the smaller axis
          const s = (a.x < b.x ? -1 : 1) * ox / 2;
          if (!a.fixed) a.x += s; if (!b.fixed) b.x -= s;
        } else {
          const s = (a.y < b.y ? -1 : 1) * oy / 2;
          if (!a.fixed) a.y += s; if (!b.fixed) b.y -= s;
        }
      }
    }
  }
}

// keep each node fully inside the container, accounting for its own size; a node that
// hits a wall has its outward velocity zeroed so it doesn't stick or jitter.
function bound(arr) {
  for (const n of arr) {
    const hw = (n.w || 40) / 2, hh = (n.h || 16) / 2;
    const minX = PAD + hw, maxX = VW - PAD - hw, minY = PAD + hh, maxY = VH - PAD - hh;
    if (n.x < minX) { n.x = minX; if (n.vx < 0) n.vx = 0; }
    else if (n.x > maxX) { n.x = maxX; if (n.vx > 0) n.vx = 0; }
    if (n.y < minY) { n.y = minY; if (n.vy < 0) n.vy = 0; }
    else if (n.y > maxY) { n.y = maxY; if (n.vy > 0) n.vy = 0; }
  }
}

// initial settle before the first paint
function settle(iters = 240) {
  for (let i = 0; i < iters; i++) physics();
}
function tick() { physics(); positionOnly(); requestAnimationFrame(tick); }

// ---------------------------------------------------------------- rendering
function applyView() { gRoot.setAttribute("transform", `translate(${view.x},${view.y}) scale(${view.k})`); }
function positionOnly() {
  for (const n of nodes.values()) {
    const el = n._g; if (!el) continue;
    el.setAttribute("transform", `translate(${n.x},${n.y})`);
  }
  for (const e of edges.values()) {
    const a = nodes.get(e.source), b = nodes.get(e.target);
    if (!a || !b || !e._l) continue;
    e._l.setAttribute("x1", a.x); e._l.setAttribute("y1", a.y);
    e._l.setAttribute("x2", b.x); e._l.setAttribute("y2", b.y);
  }
}

function draw() {
  applyView();
  // edges
  gEdges.innerHTML = "";
  for (const e of edges.values()) {
    const l = document.createElementNS(SVGNS, "line");
    l.setAttribute("class", "edge edge-" + e.type);
    gEdges.appendChild(l); e._l = l;
  }
  // nodes (text labels — the label IS the node)
  gNodes.innerHTML = "";
  for (const n of nodes.values()) {
    const g = document.createElementNS(SVGNS, "g");
    g.setAttribute("class", "node node-" + n.type);
    const fs = fontSize(n);
    // transparent hit box behind the text (sized after we measure the label)
    const hit = document.createElementNS(SVGNS, "rect");
    hit.setAttribute("class", "hit");
    g.appendChild(hit);
    // small accent dot only for opportunities (scored end-points), tinted by priority
    if (n.type === "opportunity") {
      const dot = document.createElementNS(SVGNS, "circle");
      dot.setAttribute("r", 3.5); dot.setAttribute("cx", 0); dot.setAttribute("cy", 0);
      const ps = n.meta && n.meta.priority_score;
      dot.setAttribute("class", "odot " + (ps >= 60 ? "hi" : ps >= 45 ? "mid" : "lo"));
      g.appendChild(dot);
    }
    const label = document.createElementNS(SVGNS, "text");
    label.setAttribute("class", "node-label");
    label.setAttribute("x", n.type === "opportunity" ? 8 : 0);
    label.setAttribute("y", 0);
    label.setAttribute("style", "font-size:" + fs + "px");
    const main = document.createElementNS(SVGNS, "tspan");
    main.textContent = short(n.label, n.type === "market" ? 28 : 24);
    label.appendChild(main);
    if (n.expandable && !n.expanded) {                 // dim child-count suffix
      const cnt = document.createElementNS(SVGNS, "tspan");
      cnt.setAttribute("class", "count-suffix");
      cnt.textContent = "  " + (n.child_count > 99 ? "99+" : n.child_count);
      label.appendChild(cnt);
    }
    const title = document.createElementNS(SVGNS, "title");
    title.textContent = n.label;
    g.append(label, title);
    g.setAttribute("transform", `translate(${n.x},${n.y})`);
    n._g = g; n._hit = hit; n._label = label;
    wireNode(g, n);
    gNodes.appendChild(g);
  }
  measureNodes();
  applyEmphasis();
}

// measure label boxes (for hit target + collision); needs nodes in the DOM
function measureNodes() {
  for (const n of nodes.values()) {
    if (!n._label) continue;
    let bb; try { bb = n._label.getBBox(); } catch (e) { continue; }
    n.w = bb.width + 10; n.h = bb.height + 6;
    const hit = n._hit;
    hit.setAttribute("x", bb.x - 5); hit.setAttribute("y", bb.y - 3);
    hit.setAttribute("width", bb.width + 10); hit.setAttribute("height", bb.height + 6);
  }
}

// apply focus-dim + hover-highlight classes without rebuilding the DOM
function applyEmphasis() {
  const nb = hoverId ? neighbours(hoverId) : null;
  for (const n of nodes.values()) {
    if (!n._g) continue;
    const cl = n._g.classList;
    cl.toggle("sel", selected === n.id);
    // hover only PUSHES + highlights (no dim); the realm focus is what dims.
    cl.toggle("dim", !!(activeSet && !activeSet.has(n.id)));
    cl.toggle("hot", !!(nb && nb.has(n.id)));
  }
  for (const e of edges.values()) {
    if (!e._l) continue;
    const inHover = nb && (e.source === hoverId || e.target === hoverId);
    const dimFocus = activeSet && !(activeSet.has(e.source) && activeSet.has(e.target));
    e._l.classList.toggle("hot", !!inHover);
    e._l.classList.toggle("dim", !!(!inHover && dimFocus));
  }
}

function neighbours(id) {
  const s = new Set([id]);
  for (const e of edges.values()) {
    if (e.source === id) s.add(e.target);
    if (e.target === id) s.add(e.source);
  }
  return s;
}

// ---------------------------------------------------------------- interaction
function wireNode(g, n) {
  let moved = false, dragging = false, sx = 0, sy = 0;
  g.addEventListener("pointerdown", ev => {
    ev.stopPropagation(); dragging = true; moved = false;
    n.fixed = true; sx = ev.clientX; sy = ev.clientY;
    g.setPointerCapture(ev.pointerId);
  });
  g.addEventListener("pointermove", ev => {
    if (!dragging) return;
    if (Math.abs(ev.clientX - sx) + Math.abs(ev.clientY - sy) > 3) moved = true;
    const rect = svg.getBoundingClientRect();
    n.x = (ev.clientX - rect.left - view.x) / view.k;
    n.y = (ev.clientY - rect.top - view.y) / view.k;
    positionOnly();
  });
  g.addEventListener("pointerup", ev => {
    dragging = false; n.fixed = false; reheat();
    if (!moved) { select(n.id); if (n.expandable) expand(n.id); }
  });
  g.addEventListener("pointerenter", () => { hoverId = n.id; reheat(); applyEmphasis(); });
  g.addEventListener("pointerleave", () => { if (hoverId === n.id) { hoverId = null; reheat(); applyEmphasis(); } });
}

// the focused realm = the top-level (market) ancestor's whole visible subtree
function computeActive() {
  if (!selected || !nodes.has(selected)) { activeSet = null; return; }
  let root = nodes.get(selected);
  while (root && root.parent && nodes.has(root.parent)) root = nodes.get(root.parent);
  if (!root) { activeSet = null; return; }
  const set = new Set();
  const add = id => { set.add(id); for (const n of nodes.values()) if (n.parent === id) add(n.id); };
  add(root.id);
  activeSet = set;
}

function select(id) {
  selected = id;
  computeActive();
  applyEmphasis();
  renderPanel(id);
  renderBreadcrumb();
}

function centerOn(n) {
  view.k = Math.max(view.k, 1);
  view.x = W / 2 - n.x * view.k;
  view.y = H / 2 - n.y * view.k;
  applyView();
}

function fit() {
  if (!nodes.size) return;
  resize();
  let minX = 1e9, minY = 1e9, maxX = -1e9, maxY = -1e9;
  for (const n of nodes.values()) { minX = Math.min(minX, n.x); minY = Math.min(minY, n.y); maxX = Math.max(maxX, n.x); maxY = Math.max(maxY, n.y); }
  const pad = 80, bw = (maxX - minX) + pad * 2, bh = (maxY - minY) + pad * 2;
  view.k = Math.min(2, Math.max(0.25, Math.min(W / bw, H / bh)));
  view.x = W / 2 - ((minX + maxX) / 2) * view.k;
  view.y = H / 2 - ((minY + maxY) / 2) * view.k;
  applyView();
}

// pan + zoom on background
(function panzoom() {
  let panning = false, px = 0, py = 0;
  svg.addEventListener("pointerdown", ev => { panning = true; px = ev.clientX; py = ev.clientY; svg.setPointerCapture(ev.pointerId); });
  svg.addEventListener("pointermove", ev => { if (!panning) return; view.x += ev.clientX - px; view.y += ev.clientY - py; px = ev.clientX; py = ev.clientY; applyView(); });
  svg.addEventListener("pointerup", ev => { panning = false; });
  svg.addEventListener("wheel", ev => {
    ev.preventDefault();
    const rect = svg.getBoundingClientRect();
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    const factor = ev.deltaY < 0 ? 1.12 : 1 / 1.12;
    const nk = Math.min(3, Math.max(0.2, view.k * factor));
    view.x = mx - (mx - view.x) * (nk / view.k);
    view.y = my - (my - view.y) * (nk / view.k);
    view.k = nk; applyView();
  }, { passive: false });
})();

// ---------------------------------------------------------------- breadcrumb
async function renderBreadcrumb() {
  const bc = $("#breadcrumb");
  if (!selected) { bc.innerHTML = '<span class="muted">Markets</span>'; return; }
  const n = nodes.get(selected);
  const chain = [];
  let cur = n;
  while (cur) { chain.unshift(cur); cur = cur.parent ? nodes.get(cur.parent) : null; }
  bc.innerHTML = '<span class="crumb muted" data-id="__root">Markets</span>' +
    chain.map(c => ` <span class="sep">›</span> <span class="crumb" data-id="${esc(c.id)}">${esc(short(c.label, 28))}</span>`).join("");
  bc.querySelectorAll(".crumb").forEach(el => el.onclick = () => {
    const id = el.dataset.id;
    if (id === "__root") { const r = nodes.get([...nodes.keys()][0]); fit(); return; }
    const t = nodes.get(id); if (t) { select(id); centerOn(t); }
  });
}

// ---------------------------------------------------------------- detail panel
async function renderPanel(id) {
  const panel = $("#panel");
  if (!id) { panel.innerHTML = '<div class="panel-empty"><h2>Nothing selected</h2><p class="muted">Click any node to inspect it. Start with a market, drill down to an opportunity, then open it in Opportunity Intelligence.</p></div>'; return; }
  const n = nodes.get(id);
  if (!n) { panel.innerHTML = ""; return; }
  const t = n.type, m = n.meta || {};
  panel.innerHTML = `<div class="panel-load muted">Loading…</div>`;
  const kv = (label, v) => `<div class="pkv"><b>${esc(label)}</b><span>${v}</span></div>`;
  const head = (kicker, name) => `<div class="ptype ${t}">${kicker}</div><h2 class="pname">${esc(name)}</h2>`;

  const originTag = n.origin === "dynamic_research" ? ' <span class="chip cls">researched</span>' : "";
  if (t === "market") {
    panel.innerHTML = head("Market", n.label) + originTag +
      `<p class="pdesc">${val(m.description)}</p>` +
      `<section class="pcard">${kv("Submarkets", m.submarkets)}${kv("Audiences", m.audiences)}${kv("Problems", m.problems)}${kv("Opportunities", m.opportunities)}${kv("Basis", val(m.basis))}</section>` +
      expandHint(n);
    wireExplore(n);
  } else if (t === "submarket") {
    const parent = nodes.get(n.parent);
    panel.innerHTML = head("Submarket", n.label) + originTag +
      `<section class="pcard">${kv("Parent market", val(parent ? parent.label : m.market_id))}${kv("Audiences", m.audiences)}${kv("Problems", m.problems)}${kv("Opportunities", m.opportunities)}${kv("Basis", val(m.basis))}</section>` +
      expandHint(n);
    wireExplore(n);
  } else if (t === "audience") {
    const path = ancestorLabels(n);
    panel.innerHTML = head("Audience", n.label) + originTag +
      `<section class="pcard">${kv("Market", val(path[0]))}${kv("Submarket", val(path[1]))}${kv("Problems", m.problems)}${kv("Opportunities", m.opportunities)}${kv("Creator density", val(m.creator_density))}${kv("Research status", val(m.research_status))}</section>` +
      expandHint(n);
    wireExplore(n);
  } else if (t === "problem") {
    const p = await apiFirst("/api/universe/problem/" + id, "graph/problem/" + id + ".json");
    const opps = [...edges.values()].filter(e => e.source === id).map(e => nodes.get(e.target)).filter(Boolean);
    const listCard = (title, arr) => (arr && arr.length) ? `<section class="pcard"><b class="pcard-h">${title}</b><ul class="plist">${arr.map(x => `<li>${esc(x)}</li>`).join("")}</ul></section>` : "";
    const sources = p.sources || [];
    const srcCard = sources.length ? `<section class="pcard"><b class="pcard-h">Evidence (${sources.length})</b>${sources.map(s => `<div class="ev"><a href="${esc(s.url || "#")}" target="_blank" rel="noopener">${esc(s.title || s.url || "source")}</a><div class="muted small">${esc(s.source_type || "web")} · ${esc((s.text || "").slice(0, 140))}</div></div>`).join("")}</section>` : "";
    panel.innerHTML = head("Problem", p.statement || n.label) + originTag +
      `<section class="pcard">${kv("Problem type", val(p.problem_type))}${kv("Desired outcome", val(p.desired_outcome))}${kv("Basis", val(p.basis))}${kv("Confidence", val(p.confidence))}${kv("Evidence count", p.evidence_count ?? 0)}</section>` +
      listCard("What people currently do", p.current_solutions) +
      listCard("What they've tried", p.attempts) +
      listCard("Complaints about existing solutions", p.solution_complaints) +
      srcCard +
      (opps.length ? `<section class="pcard"><b class="pcard-h">Related opportunities</b>${opps.map(o => `<button class="plink" data-id="${esc(o.id)}">${esc(o.label)} →</button>`).join("")}</section>`
        : `<p class="muted small">Expand this problem to see related opportunities.</p>`);
    panel.querySelectorAll(".plink").forEach(b => b.onclick = () => { const tn = nodes.get(b.dataset.id); if (tn) { select(b.dataset.id); centerOn(tn); } });
  } else if (t === "opportunity") {
    const [o, pipe] = await Promise.all([
      apiFirst("/api/universe/opportunity/" + id, "graph/opportunity/" + id + ".json"),
      fetch("/api/universe/pipeline/" + id).then(r => r.ok ? r.json() : fetch("graph/pipeline/" + id + ".json").then(r2 => r2.ok ? r2.json() : null)),
    ]);
    const s = o.score || {};
    const path = o.path || [];
    panel.innerHTML = head("Opportunity", o.name || n.label) +
      `<section class="pcard">${kv("Audience", val(path[2]))}${kv("Related problems", (o.problems || []).length)}${kv("Basis", val(o.basis))}${kv("Confidence", val(o.confidence))}</section>` +
      `<section class="pcard scorecard">
        <b class="pcard-h">Scoring</b>
        ${kv("Commercial score", scoreChip(s.commercial_score))}
        ${kv("Evidence score", scoreChip(s.evidence_score) + (s.evidence_band ? ` <span class="muted small">(${esc(s.evidence_band)})</span>` : ""))}
        ${kv("Priority score", scoreChip(s.priority_score))}
        ${kv("Priority class", classChip(s.priority_classification))}
        ${kv("Creator density", val((s.creator_density_detail && s.creator_density_detail.band) || (pipe && pipe.promotion_score_snapshot && pipe.promotion_score_snapshot.creator_density)))}
      </section>` +
      `<section class="pcard">
        <b class="pcard-h">Pipeline state</b>
        ${pipe ? (
          kv("Promotion", val(pipe.promotion_status)) +
          kv("Stage", val(pipe.pipeline_stage)) +
          kv("Research", val(pipe.research_status)) +
          kv("Curation", val(pipe.curation_status)) +
          kv("Distribution", val(pipe.distribution_status)) +
          kv("Product build", val(pipe.product_build_status))
        ) : '<p class="muted small">Not promoted into the pipeline yet.</p>'}
      </section>` +
      (o.possible_product || (o.possible_format && o.possible_format.length) || (o.solution_gaps && o.solution_gaps.length) ?
        `<section class="pcard"><b class="pcard-h">Product angle</b>${kv("Possible product", val(o.possible_product))}${kv("Formats", (o.possible_format && o.possible_format.length) ? esc(o.possible_format.join(", ")) : val(""))}${(o.solution_gaps && o.solution_gaps.length) ? `<div class="pkv"><b>Solution gaps</b><span></span></div><ul class="plist">${o.solution_gaps.map(g => `<li>${esc(g)}</li>`).join("")}</ul>` : ""}</section>` : "") +
      (o.problems && o.problems.length ? `<section class="pcard"><b class="pcard-h">Member problems (${o.problems.length})</b><ul class="plist">${o.problems.map(pr => `<li>${esc(pr.statement)}</li>`).join("")}</ul></section>` : "") +
      `<button class="handoff" id="research-btn">🔬 Research This Opportunity →</button>
       <p class="muted small" id="research-status">Hands this opportunity into the existing deep research pipeline (Phase 8).</p>
       <button class="handoff" id="handoff" style="background:rgba(123,92,255,.22);color:#e9f2ff">Open in Opportunity Intelligence →</button>`;
    $("#handoff").onclick = () => { window.location.href = "index.html?focus=" + encodeURIComponent(id); };
    $("#research-btn").onclick = async () => {
      const rb = $("#research-btn"), st = $("#research-status");
      rb.disabled = true; rb.textContent = "Researching…"; st.textContent = "Promoting + running Phase-8 research…";
      let r;
      try { r = await (await fetch("/api/universe/opportunity/" + encodeURIComponent(id) + "/research", { method: "POST" })).json(); }
      catch (e) { st.innerHTML = `<span class="unknown">Request failed: ${esc(e.message)}</span>`; rb.disabled = false; rb.textContent = "🔬 Research This Opportunity →"; return; }
      rb.disabled = false; rb.textContent = "Re-run research";
      if (!r.ok) { st.innerHTML = `<span class="unknown">${esc(r.error)}</span>`; return; }
      st.innerHTML = `Research <b>${esc(r.research_status)}</b>${r.counts ? ` · ${r.counts.sources ?? "?"} sources · ${r.counts.claims ?? "?"} claims` : ""} → saved to <code>research/${esc(id)}/</code>. Open in Opportunity Intelligence to inspect.`;
      select(id);   // refresh pipeline state in the panel
    };
  }
}

function expandHint(n) {
  if (n.expandable) return `<p class="muted small">${n.expanded ? "Expanded" : "Click the node to expand"} · ${n.child_count} child node${n.child_count === 1 ? "" : "s"}.</p>`;
  if (n.researchable && n.expansion_status !== "expanded")
    return `<button class="handoff explore" id="explore-btn">🔎 Explore Deeper</button>
      <p class="muted small" id="explore-status">Runs live web search → collects evidence → generates ${n.type === "audience" ? "problems &amp; opportunities" : "child nodes"}, saved permanently.</p>`;
  return `<p class="muted small">No further downstream data. <span class="unknown">Unknown / not yet generated.</span></p>`;
}
// wire the Explore-Deeper button (dynamic research) for the currently-shown node
function wireExplore(n) {
  const btn = $("#explore-btn"); if (!btn) return;
  btn.onclick = async () => {
    const st = $("#explore-status");
    btn.disabled = true; btn.textContent = "Searching…";
    st.innerHTML = "Searching the web → analyzing evidence → structuring results…";
    let r;
    try {
      r = await (await fetch("/api/universe/expand/" + encodeURIComponent(n.id), { method: "POST" })).json();
    } catch (e) { st.innerHTML = `<span class="unknown">Request failed: ${esc(e.message)}</span>`; btn.disabled = false; btn.textContent = "🔎 Explore Deeper"; return; }
    if (!r.ok) {
      btn.disabled = false; btn.textContent = "🔎 Explore Deeper";
      st.innerHTML = `<span class="unknown">${esc(r.error || "Research unavailable")}</span>` +
        (r.hint ? `<br><span class="muted small">${esc(r.hint)}</span>` : "");
      return;
    }
    st.innerHTML = `Saved · ${r.problems ?? r.children ?? 0} node(s)${r.opportunities != null ? " · " + r.opportunities + " opportunities" : ""} · ${r.sources ?? 0} sources.`;
    n.expandable = true; n.expanded = false; n.expansion_status = "expanded";
    await expand(n.id);      // load the freshly-saved children into the graph
    select(n.id);            // re-render panel (now shows children + counts)
  };
}
function ancestorLabels(n) {
  const out = []; let cur = n.parent ? nodes.get(n.parent) : null;
  while (cur) { out.unshift(cur.label); cur = cur.parent ? nodes.get(cur.parent) : null; }
  return out;
}
const scoreChip = v => (v == null) ? '<span class="unknown">Unknown</span>' : `<span class="chip s${v >= 60 ? "hi" : v >= 45 ? "mid" : "lo"}">${v}</span>`;
const classChip = v => UNKNOWNS.has(v) ? '<span class="unknown">Unknown</span>' : `<span class="chip cls">${esc(v)}</span>`;

// ---------------------------------------------------------------- search
// The whole search index is a single static file, loaded once and filtered
// client-side — so search works with no server (static deploy) and instantly.
let searchTimer = null, searchIndex = null;
const TYPE_ORDER = { market: 0, submarket: 1, audience: 2, problem: 3, opportunity: 4 };
const searchBox = $("#search"), searchRes = $("#search-results");
async function getSearchIndex() {
  if (!searchIndex) { try { searchIndex = (await apiFirst("/api/universe/search-index", "graph/search.json")).nodes || []; } catch (e) { searchIndex = []; } }
  return searchIndex;
}
searchBox.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = searchBox.value.trim().toLowerCase();
  if (q.length < 2) { searchRes.hidden = true; return; }
  searchTimer = setTimeout(async () => {
    const idx = await getSearchIndex();
    const results = idx.filter(r => r.text.includes(q))
      .sort((a, b) => (a.label.toLowerCase().indexOf(q) !== 0) - (b.label.toLowerCase().indexOf(q) !== 0)
        || (TYPE_ORDER[a.type] ?? 9) - (TYPE_ORDER[b.type] ?? 9))
      .slice(0, 25);
    if (!results.length) { searchRes.innerHTML = '<div class="sr-empty muted">No matches</div>'; searchRes.hidden = false; return; }
    const byId = {};
    searchRes.innerHTML = results.map(r => {
      byId[r.id] = r.ancestors || [];
      return `<button class="sr" data-id="${esc(r.id)}"><span class="sr-type ${r.type}">${r.type}</span>
        <span class="sr-label">${esc(r.label)}</span>
        <span class="sr-path muted">${esc((r.path || []).slice(0, -1).join(" › "))}</span></button>`;
    }).join("");
    searchRes.hidden = false;
    searchRes.querySelectorAll(".sr").forEach(b => b.onclick = async () => {
      searchRes.hidden = true; searchBox.value = "";
      await focusNode(b.dataset.id, byId[b.dataset.id]);
    });
  }, 120);
});
document.addEventListener("click", e => { if (!searchRes.contains(e.target) && e.target !== searchBox) searchRes.hidden = true; });

// ---------------------------------------------------------------- controls
$("#reset-btn").onclick = () => loadRoots();
$("#fit-btn").onclick = () => fit();
// Esc → step back up one layer (unless typing in the search box)
function backOneLayer() {
  if (!selected) return;                       // already at the top-level market view
  const n = nodes.get(selected);
  if (!n) return;
  if (n.expanded) collapse(selected);          // hide the current node's children
  if (n.parent && nodes.has(n.parent)) {
    select(n.parent);                          // step selection up to the parent
  } else {                                     // a market → deselect back to bare markets
    selected = null; computeActive(); applyEmphasis(); renderPanel(null); renderBreadcrumb();
  }
}
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && document.activeElement !== searchBox) { searchRes.hidden = true; backOneLayer(); }
});

// ---------------------------------------------------------------- boot
resize();
requestAnimationFrame(tick);
loadRoots();
