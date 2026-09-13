// Two-operator auth for the deployed app. Self-contained: renders a login overlay
// when the server has auth enabled and no valid session, plus an operator badge +
// logout. Same-origin by default; set window.OE_API_BASE (before this script) to a
// backend URL for a split Vercel-frontend / persistent-backend deployment.
(function () {
  const BASE = (window.OE_API_BASE || "").replace(/\/$/, "");
  const api = (p, opts = {}) => fetch(BASE + p, { credentials: "include", ...opts });
  window.OE = { base: BASE, api };

  const css = `
  #oe-badge{position:fixed;top:8px;right:12px;z-index:9999;font:12px system-ui,sans-serif;
    color:#c9bcff;background:rgba(8,10,18,.75);border:1px solid rgba(255,255,255,.12);
    border-radius:20px;padding:5px 12px;display:flex;gap:10px;align-items:center;backdrop-filter:blur(6px)}
  #oe-badge b{color:#fff;text-transform:capitalize}
  #oe-badge button{background:none;border:none;color:#9db6dd;cursor:pointer;font:inherit;text-decoration:underline}
  #oe-login{position:fixed;inset:0;z-index:10000;background:rgba(3,3,7,.9);display:flex;
    align-items:center;justify-content:center;font:14px system-ui,sans-serif;color:#e9f2ff}
  #oe-login .box{background:#0c1424;border:1px solid rgba(255,255,255,.12);border-radius:14px;
    padding:26px 24px;width:320px;box-shadow:0 20px 60px rgba(0,0,0,.6)}
  #oe-login h2{margin:0 0 4px;font-size:18px}
  #oe-login p{margin:0 0 16px;color:#9db6dd;font-size:12px}
  #oe-login label{display:block;font-size:12px;color:#9db6dd;margin:10px 0 4px}
  #oe-login select,#oe-login input{width:100%;background:rgba(13,21,39,.9);border:1px solid rgba(255,255,255,.12);
    border-radius:8px;color:#e9f2ff;font:inherit;padding:9px 11px;box-sizing:border-box}
  #oe-login button.go{width:100%;margin-top:16px;background:linear-gradient(90deg,#7b5cff,#a78bff);
    color:#0a0714;border:none;font-weight:700;padding:11px;border-radius:9px;cursor:pointer}
  #oe-login .err{color:#ff7f98;font-size:12px;margin-top:10px;min-height:14px}`;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);

  function badge(op) {
    const b = document.createElement("div"); b.id = "oe-badge";
    b.innerHTML = `<span>operator</span><b>${op}</b><button id="oe-logout">logout</button>`;
    document.body.appendChild(b);
    b.querySelector("#oe-logout").onclick = async () => {
      await api("/api/auth/logout", { method: "POST" }); location.reload();
    };
  }

  function overlay() {
    const o = document.createElement("div"); o.id = "oe-login";
    o.innerHTML = `<div class="box">
      <h2>Opportunity Engine</h2><p>Private — operator sign in</p>
      <label>Operator</label>
      <select id="oe-op"><option value="cael">Cael</option><option value="sheylyn">Sheylyn</option></select>
      <label>Password</label><input id="oe-pw" type="password" autocomplete="current-password">
      <button class="go" id="oe-go">Sign in</button>
      <div class="err" id="oe-err"></div></div>`;
    document.body.appendChild(o);
    const err = o.querySelector("#oe-err");
    const submit = async () => {
      err.textContent = "";
      const r = await api("/api/auth/login", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ operator: o.querySelector("#oe-op").value,
                               password: o.querySelector("#oe-pw").value }) });
      if (r.ok) { location.reload(); } else { err.textContent = "Invalid credentials"; }
    };
    o.querySelector("#oe-go").onclick = submit;
    o.querySelector("#oe-pw").addEventListener("keydown", e => { if (e.key === "Enter") submit(); });
    o.querySelector("#oe-pw").focus();
  }

  async function init() {
    let me;
    try { me = await (await api("/api/auth/me")).json(); }
    catch (e) { return; }               // backend unreachable (e.g. static-only) — leave page as-is
    window.OE.operator = me.operator;
    if (me.auth_enabled && !me.authenticated) { overlay(); return; }
    if (me.operator) badge(me.operator);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
