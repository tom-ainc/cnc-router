// core.js: the page framework of the systems-engineering skill. The same file in every project.
//
// It loads viewer_data.json (the 3D model and how the page shows it) and systems.json (requirements, product
// tree, interfaces, assumptions, results), then the components that viewer_data.json lists, in order. It draws
// the 3D view, the block diagram, the requirements, product tree, interfaces and assumptions tabs, and keeps them
// in step: selecting a requirement, a part or a block shows it everywhere.
//
// A component is a script that calls Page.component({...}) (see the skill's page.md):
//   id, tab, pane, after     its tab's label, its pane's id, and the tab it goes after (else at the end)
//   stage                    html for a panel under the 3D view (shown while its tab is; give it class "stage-panel")
//   init(Page)               once the core is built: add meshes, listen to events
//   render()                 after the core's first render: fill its pane
//   enter(), exit()          its tab was opened, or left
//   claimsReq(id), focusReq(id)   a requirement it shows better than the core does (a build step, a simulation)
//   filterLabel(focus)       what the diagram's focus leaves in its pane, for the bar above the tabs
//   drives: true             it can take over the meshes' visibility and colour; it sets Page.driver while it does
// Events: Page.on("frame", fn(now)), on("pose", fn(pose)), on("focus", fn(focus)), on("tab", fn(paneId)).
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const fmt = (v, d) => v == null ? "–" : (Math.abs(v) >= 100 || d === 0 ? Math.round(v).toLocaleString("en-AU") : (+v.toPrecision(3)).toString());
  const store = { get(k, d) { try { return localStorage.getItem(k) ?? d; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  const handlers = {};
  const Page = window.Page = {
    $, css, fmt, store, comps: [], driver: null, hold: false,
    // a data file beside the page, or null
    file(name) { return fetch(name).then(r => r.ok ? r.json() : null).catch(() => null); },
    on(ev, fn) { (handlers[ev] ||= []).push(fn); },
    emit(ev, ...a) { for (const f of handlers[ev] || []) { try { f(...a); } catch (e) { console.error(ev, e); } } },
    component(c) { this.comps.push(c); },
    style(text) { const el = document.createElement("style"); el.textContent = text; document.head.appendChild(el); },
  };
  const loadScript = (src) => new Promise((ok, no) => {
    const s = document.createElement("script"); s.src = src; s.onload = ok; s.onerror = () => no(new Error("could not load " + src)); document.body.appendChild(s);
  });
  (async function boot() {
    let V, S;
    try {
      [V, S] = await Promise.all([fetch("viewer_data.json").then(r => r.json()), fetch("systems.json").then(r => r.json())]);
      // golf's viewer: the runtime `golf bundle` wrote (V.golf), else the copy beside the page
      // (V.cinema names it; a folder `golf bundle` wrote has its own copy; else the one the skill ships, page/cinema/)
      Page.cinema = await import(new URL(V.cinema || (V.golf_bundle ? V.golf + "/cinema.js" : "cinema/cinema.js"), location.href).href);
      // confirm.js (what waits on the user, and every assumption) is part of the core; then the project's components
      for (const src of ["confirm.js", ...(V.components || []).filter(c => c !== "confirm.js")]) await loadScript(src);
    } catch (e) {
      $("err").style.display = "block"; $("err").textContent = "The page did not load: " + e.message; return;
    }
    try { await main(V, S); }
    catch (e) { console.error(e); $("err").style.display = "block"; $("err").textContent = "The page stopped: " + e.message; }
  })();

  async function main(V, S) {
  V.parts ||= {}; V.viz ||= {};
  if (V.title) { document.title = V.title; $("title").textContent = V.title; }
  $("subtitle").textContent = V.subtitle || "";
  // what the agent is doing: a band under the header, while the work goes on
  if (V.progress && (V.progress.now || V.progress.done)) {
    const g = V.progress, el = document.createElement("div");
    el.className = "progress-band";
    el.innerHTML = [g.done && `<span><b>Done</b> ${g.done}</span>`, g.now && `<span><b>Now</b> ${g.now}</span>`, g.next && `<span><b>Next</b> ${g.next}</span>`,
      (V.ask || []).length && `<span><button type="button" class="lk" id="pg-ask">${V.ask.length} question${V.ask.length > 1 ? "s" : ""} for you</button></span>`,
      g.at && `<span class="at">updated ${g.at}</span>`].filter(Boolean).join("");
    document.querySelector("header").after(el);
    Page.style(`.progress-band { display: flex; flex-wrap: wrap; gap: 4px 18px; padding: 6px 16px; font-size: 12.5px; background: var(--accent-soft); border-bottom: 1px solid var(--line); }
      .progress-band b { font-weight: 600; margin-right: 4px; } .progress-band .at { margin-left: auto; color: var(--muted); }
      .progress-band button { background: none; border: 0; padding: 0; font: inherit; font-weight: 600; }`);
    $("pg-ask")?.addEventListener("click", () => showTab("p-conf"));
  }
  // no 3D model yet: the requirements, diagram and tabs take the whole page
  if (!Object.keys(V.parts).length && !V.golf) Page.style("main { grid-template-columns: minmax(0, 1fr) !important; } .stage { display: none !important; }");
  Page.style(".item.pick { cursor: pointer; border-left: 3px solid transparent; } .item.pick:hover { background: color-mix(in srgb, var(--accent-soft) 55%, transparent); } .item.pick.sel { background: var(--accent-soft); border-left-color: var(--accent); } #dg-svg svg { max-height: 360px; } #panes { display: contents; } .tabs { flex-wrap: wrap; } .tabs button { white-space: nowrap; }");
  // ------------------------------------------------------------- systems data
  const reqs = S.requirements;
  const res = Object.fromEntries(S.results.map(r => [r.requirement, r]));
  const nodes = Object.fromEntries(S.nodes.map(n => [n.id, n]));
  const status = (id) => { const s = (res[id] || {}).status; return s === "pass" ? "pass" : s === "fail" ? "fail" : "open"; };
  const statusWord = { pass: "Pass", fail: "Fail", open: "Not checked by model" };
  // how far a result can be trusted: a pass is the model's prediction; only a test of the real thing validates
  const STANDING = { fail: ["FAIL", "fail"], test_fail: ["Fails in test", "fail"], not_verified: ["Not verified", "fail"], draft: ["Pass, draft", "open"],
                     provisional: ["Pass, provisional", "open"], not_checked: ["For a person", "neutral"], credible: ["Pass, credible", "pass"], validated: ["Validated", "pass"] };
  const standing = (id) => (res[id] || {}).standing || (status(id) === "pass" ? "draft" : status(id) === "fail" ? "fail" : "not_checked");
  const partToNode = {};
  S.nodes.forEach(n => (n.shows || []).forEach(p => { partToNode[p] = n.id; }));
  const nodeParts = (id) => id === "P" ? [] : (nodes[id]?.shows || []);
  const reqsOfNode = (nid) => reqs.filter(r => r.applies_to.includes(nid));

  // tally
  const counts = { pass: 0, fail: 0, open: 0 }, sc = {};
  reqs.forEach(r => { counts[status(r.id)]++; sc[standing(r.id)] = (sc[standing(r.id)] || 0) + 1; });
  const unconf = S.assumptions.filter(a => !a.confirmed).length;
  $("tally").innerHTML = ["fail", "test_fail", "not_verified", "draft", "provisional", "credible", "validated", "not_checked"].filter(k => sc[k])
      .map(k => `<span class="pill ${STANDING[k][1]}" title="${k === "draft" ? "the requirement or its limit is not confirmed by you" : k === "provisional" ? "rests on something not confirmed, a model not checked, or a guess that could flip it" : ""}">${sc[k]} ${STANDING[k][0].toLowerCase()}</span>`).join("") +
    `<span class="pill neutral" title="nothing is done until it is tested on the real thing">${sc.validated || 0} validated</span>` +
    `<span class="pill neutral">${unconf} of ${S.assumptions.length} assumptions unconfirmed</span>`;

  // stat tiles: each opens the requirement behind it
  // V.tiles: [{label, value, unit, req, note, digits}]; digits fixes the decimals, else fmt
  const tiles = (V.tiles || []).map(t => [t.label, t.digits != null ? (+t.value).toFixed(t.digits) : fmt(t.value), t.unit || "", t.req || "", t.note || ""]);
  $("stats").innerHTML = tiles.map(([k, v, u, r, x]) =>
    `<div class="stat" tabindex="0" data-req="${r}"><div class="k">${k}</div><div class="v">${v} <small>${u} ${x}</small></div></div>`).join("");
  $("stats").querySelectorAll(".stat").forEach(el => {
    const go = () => { if (!el.dataset.req) return; showTab("p-req"); selectReq(el.dataset.req, true); };
    el.addEventListener("click", go); el.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  });

  // requirements list
  function reqRow(r) {
    const x = res[r.id] || {}, s = status(r.id), sd = standing(r.id);
    let meta = `<span class="pill ${STANDING[sd][1]}">${STANDING[sd][0]}</span>`;
    let bar = "";
    if (r.method === "outside") {
      meta += `<span>${(r.extra && r.extra.why) || ""}</span>`;
    } else if (r.limit != null && x.measured != null) {
      const u = r.unit ? " " + r.unit : "";
      const op = r.kind === "max" ? "≤" : r.kind === "min" ? "≥" : "=";
      meta += `<span>measured <span class="num">${fmt(x.measured)}${u}</span></span><span>limit <span class="num">${op} ${fmt(r.limit)}${u}</span></span>`;
      if (x.margin != null && r.unit !== "mm^3") meta += `<span>margin <span class="num">${fmt(x.margin)}${u}</span></span>`;
      if (x.cases && x.cases.length > 1) meta += `<span>worst of ${x.cases.length} cases</span>`;
      if (r.limit !== 0 && r.kind !== "equal") {
        const hi = Math.max(Math.abs(x.measured), Math.abs(r.limit)) * 1.15;
        bar = `<div class="bar ${s === "fail" ? "fail" : ""}"><i style="width:${Math.min(100, Math.abs(x.measured) / hi * 100)}%"></i><b style="left:${Math.abs(r.limit) / hi * 100}%"></b></div>`;
      }
    } else if (x.measured != null) {
      meta += `<span class="num">${fmt(x.measured)}</span>`;
    }
    const ev = x.evidence && x.evidence.tool ? `<dt>How it was computed</dt><dd>${x.evidence.tool}</dd><dt>Leaves out</dt><dd>${x.evidence.leaves_out}</dd>` : "";
    const before = x.before && x.before.margin != null && x.margin != null && Math.abs(x.before.margin - x.margin) > 1e-6
      ? `<dt>Before the last change</dt><dd>margin ${fmt(x.before.margin)} ${r.unit || ""}</dd>` : "";
    const cases = x.cases && x.cases.length > 1
      ? `<dt>Cases</dt><dd><table>${worstCases(x.cases, r).map(c => `<tr><td>${c.case}</td><td class="num">${fmt(c.measured)}</td><td>${c.status}</td></tr>`).join("")}</table></dd>` : "";
    const parts = r.applies_to.map(n => `<span class="chip" data-node="${n}">${n === "P" ? "whole machine" : n}</span>`).join(" ");
    return `<div class="req" tabindex="0" data-req="${r.id}" id="row-${r.id}">
      <div class="id">${r.id}</div><div class="txt">${r.text}</div>
      <div class="meta">${meta}</div>${bar}
      <dl class="detail"><dt>About</dt><dd>${parts}</dd><dt>Source</dt><dd>${{ stated: "stated by you", implied: "implied by what it is for (not confirmed)", assumed: "a limit I chose (not confirmed)" }[r.source] || r.source}, checked by ${r.method}</dd>
      ${(x.why || []).length && sd !== "credible" ? `<dt>Not trusted further because</dt><dd><ul class="why">${x.why.map(w => `<li>${w}</li>`).join("")}</ul></dd>` : ""}
      ${(x.validations || []).length ? `<dt>Tested</dt><dd>${x.validations.map(v => `${v.how} ${v.date}: ${fmt(v.measured)} ${v.unit}`).join("<br>")}</dd>` : ""}${ev}${before}${cases}</dl>
    </div>`;
  }
  function worstCases(cs, r) {
    const key = (c) => c.margin == null ? 0 : c.margin;
    return [...cs].sort((a, b) => key(a) - key(b)).slice(0, 8);
  }
  let reqFilter = null;
  // grouping: by topic, product tree, status, how it is verified, or margin; plus a text search
  let groupBy = store.get("reqGroup", "topic"), reqQuery = "";
  const collapsed = new Set();
  const topicOf = {};
  Object.entries(V.req_topics || {}).forEach(([t, ids]) => ids.forEach(id => { topicOf[id] = t; }));
  const treeOrder = [];
  (function walk(id, depth) { treeOrder.push([id, depth]); S.nodes.filter(n => n.parent === id).forEach(n => walk(n.id, depth + 1)); })("P", 0);
  function relMargin(r) {
    const x = res[r.id] || {};
    if (x.margin == null || r.limit == null || r.unit === "mm^3" || !r.limit) return null;
    return x.margin / Math.abs(r.limit);
  }
  const GROUPS = {
    topic: { label: "Topic", groups: (r) => [topicOf[r.id] || "Other"], order: [...Object.keys(V.req_topics || {}), "Other"] },
    tree: { label: "Product tree", groups: (r) => r.applies_to, order: treeOrder.map(([id]) => id),
            name: (id) => { const d = (treeOrder.find(t => t[0] === id) || [id, 0])[1]; return "\u2003".repeat(d) + (id === "P" ? "Whole machine" : `${id} · ${nodes[id]?.name || ""}`); } },
    status: { label: "Standing", groups: (r) => [STANDING[standing(r.id)][0]], order: ["FAIL", "Fails in test", "Not verified", "Pass, draft", "Pass, provisional", "Pass, credible", "Validated", "For a person"] },
    method: { label: "How it's verified", groups: (r) => [{ measure: "Measured on the model", simulate: "Calculated", outside: "Needs a person (test, inspection)" }[r.method] || r.method],
              order: ["Measured on the model", "Calculated", "Needs a person (test, inspection)"] },
    margin: { label: "Margin", groups: (r) => {
                const s = status(r.id); if (s === "fail") return ["Failing"]; if (s === "open") return ["Not checked by model"];
                const m = relMargin(r); return [m == null ? "Pass / fail checks (no margin)" : m < 0.1 ? "Tight: under 10 % margin" : m < 0.3 ? "10 to 30 % margin" : "Over 30 % margin"]; },
              order: ["Failing", "Tight: under 10 % margin", "10 to 30 % margin", "Over 30 % margin", "Pass / fail checks (no margin)", "Not checked by model"] },
    none: { label: "None (requirement order)", groups: () => ["All requirements"], order: ["All requirements"] },
  };
  function renderReqs() {
    let list = reqFilter ? reqs.filter(r => reqFilter.ids.includes(r.id)) : reqs;
    const q = reqQuery.trim().toLowerCase();
    if (q) list = list.filter(r => (r.id + " " + r.text + " " + (topicOf[r.id] || "") + " " + r.applies_to.join(" ")).toLowerCase().includes(q));
    const G = GROUPS[groupBy] || GROUPS.topic;
    const buckets = new Map();
    for (const r of list) for (const k of G.groups(r)) { if (!buckets.has(k)) buckets.set(k, []); buckets.get(k).push(r); }
    const keys = [...G.order.filter(k => buckets.has(k)), ...[...buckets.keys()].filter(k => !G.order.includes(k))];
    const seen = new Set();
    let html = `<div class="reqbar"><label for="req-group">Group by</label><select id="req-group">${Object.entries(GROUPS).map(([k, g]) => `<option value="${k}"${k === groupBy ? " selected" : ""}>${g.label}</option>`).join("")}</select>
      <input id="req-q" type="search" placeholder="Search requirements" value="${reqQuery.replace(/"/g, "&quot;")}" aria-label="Search requirements">
      <button type="button" id="req-fold">${keys.every(k => collapsed.has(groupBy + ":" + k)) ? "Expand all" : "Collapse all"}</button></div>`;
    for (const k of keys) {
      const rs = buckets.get(k), key = groupBy + ":" + k, shut = !q && collapsed.has(key);     // a search opens every group
      const c = { pass: 0, fail: 0, open: 0 }; rs.forEach(r => c[status(r.id)]++);
      const counts = (c.fail ? `<span class="pill fail">${c.fail} fail</span>` : "") + (c.pass ? `<span class="pill pass" title="pass">${c.pass}</span>` : "") + (c.open ? `<span class="pill open" title="not checked by model">${c.open}</span>` : "");
      if (groupBy !== "none") html += `<div class="grp" data-key="${key}" tabindex="0" role="button" aria-expanded="${!shut}"><span class="tw">${shut ? "▶" : "▼"}</span><span class="gn">${G.name ? G.name(k) : k}</span><span class="gc">${counts}</span></div>`;
      html += `<div class="grp-body"${shut && groupBy !== "none" ? " hidden" : ""}>` + rs.map(r => { const row = reqRow(r); if (seen.has(r.id)) return row.replace(` id="row-${r.id}"`, ""); seen.add(r.id); return row; }).join("") + `</div>`;
    }
    if (!keys.length) html += `<div class="empty">No requirements match.</div>`;
    $("p-req").innerHTML = html;
    $("req-group").addEventListener("change", e => { groupBy = e.target.value; store.set("reqGroup", groupBy); renderReqs(); });
    $("req-q").addEventListener("input", e => { reqQuery = e.target.value; const pos = e.target.selectionStart; renderReqs(); const el = $("req-q"); el.focus(); el.setSelectionRange(pos, pos); });
    $("req-fold").addEventListener("click", () => { const all = keys.every(k => collapsed.has(groupBy + ":" + k)); keys.forEach(k => all ? collapsed.delete(groupBy + ":" + k) : collapsed.add(groupBy + ":" + k)); renderReqs(); });
    $("p-req").querySelectorAll(".grp").forEach(el => {
      const go = () => { const k = el.dataset.key; collapsed.has(k) ? collapsed.delete(k) : collapsed.add(k); renderReqs(); };
      el.addEventListener("click", go); el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
    $("p-req").querySelectorAll(".req").forEach(el => {
      el.addEventListener("click", (e) => {
        if (e.target.closest(".chip")) { selectNode(e.target.closest(".chip").dataset.node); return; }
        selectReq(el.dataset.req === selReq ? null : el.dataset.req);
      });
      el.addEventListener("keydown", e => { if (e.key === "Enter") selectReq(el.dataset.req === selReq ? null : el.dataset.req); });
    });
    if (selReq) $("row-" + selReq)?.classList.add("sel");
  }
  $("filter-x").addEventListener("click", () => setFocus(null));

  // product tree
  function renderTree() {
    const kids = (id) => S.nodes.filter(n => n.parent === id);
    const row = (n, depth) => {
      const rl = reqsOfNode(n.id).map(r => `<span class="chip ${status(r.id)}" data-req="${r.id}">${r.id}</span>`).join("");
      return `<div class="node" data-node="${n.id}" tabindex="0" style="padding-left:${14 + depth * 14}px">
        <div class="id">${n.id}</div><div>${n.name}${n.bought ? ` <span class='pill neutral'>${V.bought_word || "bought"}</span>` : ""}</div>
        <div class="m">${n.mass_kg != null ? n.mass_kg + " kg" : (S.totals[n.id] ? S.totals[n.id].mass_kg.toFixed(0) + " kg total" : "")}</div>
        <div class="links">${rl}</div></div>` + kids(n.id).map(k => row2(k, depth + 1)).join("");
    };
    const keep = (n) => !focus || n.id === "P" || focus.nodes.has(n.id);
    const row2 = (n, depth) => keep(n) ? row(n, depth) : kids(n.id).map(k => row2(k, depth + 1)).join("");
    $("p-tree").innerHTML = row2(nodes.P, 0);
    $("p-tree").querySelectorAll(".node").forEach(el => el.classList.toggle("sel", !!focus && focus.nodes.has(el.dataset.node)));
    $("p-tree").querySelectorAll(".node").forEach(el => el.addEventListener("click", e => {
      const chip = e.target.closest(".chip");
      if (chip) { showTab("p-req"); selectReq(chip.dataset.req, true); return; }
      selectNode(el.dataset.node);
    }));
  }
  // ---- items in the tabs that show themselves in 3D: an interface lights both sides, an assumption the parts of the
  // requirements it feeds, a flow its block. Clicking the selected one again goes back to the diagram's focus.
  let selItem = null;
  const ifName = (x) => x.startsWith("external:") ? x.slice(9) + " (outside)" : (x === "P" ? V.whole || "whole system" : x);
  function ifaceParts(i) {
    const side = (x) => x.startsWith("external:") ? ((DG.ext || {})[x.slice(9)] || [0, 0, []])[2].flatMap(nodeParts) : x === "P" ? [] : nodeParts(x);
    return [...side(i.a), ...side(i.b)];
  }
  function reqParts(id) {
    const r = reqs.find(q => q.id === id), z = (V.viz || {})[id] || {};
    return r ? (z.parts && z.parts.length ? z.parts : r.applies_to.flatMap(nodeParts)) : [];
  }
  function affectsOf(a) { return a.affects || []; }
  function showItem(kind, id) {
    if (Page.driver) return;
    if (!id || selItem === kind + ":" + id) { selItem = null; markItems(); applyFocusView(); return; }
    selItem = kind + ":" + id; clearAnnot();
    if (kind === "if") {
      const i = S.interfaces.find(q => q.id === id), ps = ifaceParts(i);
      highlight(ps.length ? ps : null);
      Page.note(`<b>${i.id}</b> ${ifName(i.a)} ↔ ${ifName(i.b)} · ${i.kind}<br><span style="color:var(--muted)">${i.text}${i.keeps ? "; keeps " + i.keeps : ""}</span>`);
      const L = DG_LINKS.find(l => l.items.includes(i));
      document.querySelectorAll("#dg-svg .dg-link").forEach(g => g.classList.toggle("on", !!L && g.dataset.key === linkKey(L)));
    } else if (kind === "as") {
      const a = S.assumptions.find(q => q.id === id), ps = [...new Set(affectsOf(a).flatMap(reqParts))];
      highlight(ps.length ? ps : null);
      Page.note(`<b>${a.id}</b> ${a.confirmed ? "" : `<span class="pill open">not confirmed</span> `}${a.text}` +
        (affectsOf(a).length ? `<br><span style="color:var(--muted)">Feeds ${affectsOf(a).join(", ")}${ps.length ? "; their parts are lit" : ""}</span>` : `<br><span style="color:var(--muted)">Not tied to a requirement</span>`));
    } else if (kind === "flow") {
      const ps = nodeParts(id); highlight(ps.length ? ps : null);
      Page.note(`<b>${id}</b> ${(nodes[id] || {}).name || ""}`);
    }
    markItems();
  }
  function markItems() {
    document.querySelectorAll("[data-item]").forEach(el => el.classList.toggle("sel", el.dataset.item === selItem));
  }
  function bindItems(el) {
    el.querySelectorAll("[data-item]").forEach(d => d.addEventListener("click", (e) => {
      if (e.target.closest("[data-req]")) return;
      const [k, id] = d.dataset.item.split(":"); showItem(k, id);
    }));
    el.querySelectorAll("[data-req]").forEach(c => c.addEventListener("click", (e) => { e.stopPropagation(); showTab("p-req"); selectReq(c.dataset.req, true); }));
    markItems();
  }
  function renderInterfaces() {
    const its = focus ? S.interfaces.filter(i => focus.ifaces.has(i.id)) : S.interfaces;
    const bl = focus ? S.blocks.filter(b => b.node === "P" || focus.nodes.has(b.node)) : S.blocks;
    $("p-if").innerHTML = (its.length ? "" : `<div class="empty">No interfaces.</div>`) + its.map(i => `<div class="item pick" data-item="if:${i.id}" tabindex="0"><div class="id">${i.id}</div>
      <div><b>${ifName(i.a)}</b> ↔ <b>${ifName(i.b)}</b> · ${i.kind}<br>${i.text}</div>
      ${i.keeps ? `<div class="why">keeps: ${i.keeps}</div>` : ""}</div>`).join("") +
      (bl.length ? `<div class="section-h">Flows</div>` : "") + bl.map(b => `<div class="item pick" data-item="flow:${b.node}" tabindex="0"><div class="id">${b.node}</div>
      <div>in: ${b.inputs.map(p => p.name + (p.unit ? " (" + p.unit + ")" : "")).join(", ")}<br>out: ${b.outputs.map(p => p.name).join(", ")}</div></div>`).join("");
    bindItems($("p-if"));
  }
  const asShown = () => focus ? S.assumptions.filter(a => affectsOf(a).some(id => focus.reqs.has(id))) : S.assumptions;
  // tabs: the core's four, and each component's, placed after the tab it names
  let activeTab = "p-req";
  function showTab(id) {
    document.querySelectorAll(".tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.pane === id));
    document.querySelectorAll(".pane").forEach(p => p.hidden = p.id !== id);
    activeTab = id;
    for (const c of Page.comps) if (c.pane && c.pane !== id && c._on) { c._on = false; c.exit && c.exit(); }
    for (const c of Page.comps) if (c.pane === id && !c._on) { c._on = true; c.enter && c.enter(); }
    updateFilterBar();
    Page.emit("tab", id);
  }

  function renderTabs() {
    const tabs = [["p-req", "t-req", "Requirements"], ["p-tree", "t-tree", "Product tree"], ["p-if", "t-if", "Interfaces"]];
    const after = {};
    for (const c of Page.comps) {
      if (!c.pane) continue;
      // after its anchor, and after the tabs placed there before it, so tabs keep the order they load in
      const t = [c.pane, c.tabId || "t-" + c.pane.replace(/^p-/, ""), c.tab || c.id], k = c.after ? tabs.findIndex(x => x[0] === c.after) : -1;
      if (k >= 0) { after[c.after] = (after[c.after] || 0) + 1; tabs.splice(k + after[c.after], 0, t); } else tabs.push(t);
      if (c.stage) $("ctl").insertAdjacentHTML("beforebegin", c.stage);
    }
    $("tabs").innerHTML = tabs.map(([p, id, l]) => `<button role="tab" aria-selected="${p === activeTab}" data-pane="${p}" id="${id}">${l}</button>`).join("");
    $("panes").innerHTML = tabs.map(([p]) => `<div class="pane" id="${p}" role="tabpanel"${p === activeTab ? "" : " hidden"}></div>`).join("");
    document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.pane)));
  }
  // ------------------------------------------------------------- 3D: golf's viewer (Cinema JS)
  // The model's parts are golf instances from the bundle (V.golf: the folder `golf bundle` wrote), or meshes given in
  // V.parts (p, t) for a design with no golf model; components add their own (cable chains, fasteners) as meshes,
  // and lines, tubes and labels as overlay shapes. Every one is an item: Page.items[name], with its group, its
  // visibility, opacity and outline, and an offset; the core places it from the pose.
  const view = $("view");
  const C = Page.cinema;
  const stageEl = document.createElement("div"); stageEl.id = "cinema"; view.prepend(stageEl);
  Page.style("#cinema { position: absolute; inset: 0; } #view { position: relative; }");
  const viewer = C.createViewer(stageEl, { theme: "light", partsList: false, viewCube: false, measure: false, preloadKernel: false, background: css("--viewer") || undefined });
  // the model's own frame in the world: V.frame {translate: [x, y, z], rotate: [rx, ry, rz] degrees, X then Y then Z}
  const FR = V.frame || {}, T0 = FR.translate || [0, 0, 0];
  const R = (function () {
    const [a, b, c] = (FR.rotate || [0, 0, 0]).map(d => d * Math.PI / 180);
    const ca = Math.cos(a), sa = Math.sin(a), cb = Math.cos(b), sb = Math.sin(b), cc = Math.cos(c), sc = Math.sin(c);
    return [cb * cc, -cb * sc, sb, sa * sb * cc + ca * sc, -sa * sb * sc + ca * cc, -sa * cb, -ca * sb * cc + sa * sc, ca * sb * sc + sa * cc, ca * cb];
  })();
  const rot = (v) => [R[0] * v[0] + R[1] * v[1] + R[2] * v[2], R[3] * v[0] + R[4] * v[1] + R[5] * v[2], R[6] * v[0] + R[7] * v[1] + R[8] * v[2]];
  const add3 = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  // moving groups: V.groups {name: [[axis, [dx, dy, dz], scale, ref], ...]}: the group moves by dir * scale * (pose[axis] - ref)
  // summed over its terms, in the model's frame. "fixed" does not move; "world" parts are in the world, not the frame.
  const axes = V.axes || [];
  const pose = Object.fromEntries(axes.map(a => [a.id, a.start ?? a.range[0]]));
  const poseOf = (p) => Array.isArray(p) ? Object.fromEntries(axes.map((a, i) => [a.id, p[i]])) : { ...pose, ...p };
  function groupOffset(g) {
    const o = [0, 0, 0];
    for (const [ax, d, k, ref] of (V.groups || {})[g] || []) { const s = (k ?? 1) * ((pose[ax] ?? 0) - (ref ?? 0)); o[0] += d[0] * s; o[1] += d[1] * s; o[2] += d[2] * s; }
    return o;
  }
  // a point in a group's frame, in the world, where the pose has it
  function toWorld(p, g) { return g === "world" ? p.slice(0, 3) : add3(rot(add3(p, groupOffset(g))), T0); }
  const groupWorld = (g) => g === "world" ? [0, 0, 0] : rot(groupOffset(g));
  const frameVec = (v, frame) => frame === "world" ? v : rot(v);

  const items = {};
  function makeItem(name, f) {
    const it = { name, group: "fixed", vis: true, op: 1, hot: false, off: [0, 0, 0], ...f };
    items[name] = it; return it;
  }
  // meshes the page makes (a design with no golf model, motors golf cannot read, fasteners, chain links) are drawn as
  // instances too: they are written as one OBJ model, loaded once the components have added theirs
  const pendingObj = [];
  function addMesh(name, { positions, triangles, color = "#a0a4a8", group = "fixed", info = "", kind = "made" }) {
    // a still shape in its group's frame (or the world, for "world"), moved with its group like any part
    const w = group === "world", P = new Array(positions.length);
    for (let i = 0; i < positions.length; i += 3) {
      const q = w ? [positions[i], positions[i + 1], positions[i + 2]] : add3(rot([positions[i], positions[i + 1], positions[i + 2]]), T0);
      P[i] = q[0]; P[i + 1] = q[1]; P[i + 2] = q[2];
    }
    pendingObj.push({ name, P, T: triangles, color });
    V.parts[name] ||= { info, kind, group };
    return makeItem(name, { kind: "inst", group, color });
  }
  function addBody(name, { positions, triangles, color = "#a0a4a8", info, kind = "bought" }) {
    // a rigid shape in its own frame, placed by placeBody (position and rotation in the world), as a chain's links
    pendingObj.push({ name, P: positions, T: triangles, color });
    if (info) V.parts[name] ||= { info, kind };
    return makeItem(name, { kind: "inst", body: true, color, pos: [0, 0, 0], rotd: [0, 0, 0] });
  }
  // place a body: M is its rotation as a 3x3 row-major matrix in the world
  function placeBody(name, pos, M) {
    const it = items[name]; if (!it) return;
    const b = Math.asin(Math.max(-1, Math.min(1, M[2]))), a = Math.atan2(-M[5], M[8]), c = Math.atan2(-M[1], M[0]);
    it.pos = pos; it.rotd = [a, b, c].map(v => v * 180 / Math.PI); sync(it);
  }
  async function loadPageObjects() {
    if (!pendingObj.length) return;
    let txt = "", vi = 1;
    for (const o of pendingObj) {
      txt += `o ${o.name}\n`;
      for (let i = 0; i < o.P.length; i += 3) txt += `v ${o.P[i].toFixed(3)} ${o.P[i + 1].toFixed(3)} ${o.P[i + 2].toFixed(3)}\n`;
      for (let i = 0; i < o.T.length; i += 3) txt += `f ${o.T[i] + vi} ${o.T[i + 1] + vi} ${o.T[i + 2] + vi}\n`;
      vi += o.P.length / 3;
    }
    const md = await viewer.load(new File([txt], "page.obj", { type: "text/plain" }));
    models.push(md);
    for (const o of pendingObj) { const it = items[o.name]; it.inst = md.find(o.name); if (it.inst) { it.model = md; it.inst.style({ color: o.color }); sync(it); } }
    pendingObj.length = 0;
  }
  // a shape item: overlay shapes (tubes, lines) made by a function of the pose, in world mm, drawn with the item's opacity
  function addShapes(name, make, { group = "fixed", info = "", kind = "bought" } = {}) {
    const it = makeItem(name, { kind: "shapes", group, make });
    V.parts[name] ||= { info, kind, group };
    return it;
  }
  // Tubes are slow for the viewer to rebuild (about 0.15 ms a point), so while the pose is moving (a slider, an
  // animation, the simulation) they are drawn as lines, and as tubes again once it has been still for a moment.
  let shapesDirty = true, lastMove = 0, tubesOwed = false;
  function drawShapes() {
    const moving = performance.now() - lastMove < 250;
    if (!shapesDirty && !(tubesOwed && !moving)) return;
    shapesDirty = false; tubesOwed = moving;
    const out = [];
    for (const it of Object.values(items)) if (it.kind === "shapes" && it.vis && it.op > 0.02) {
      for (const s of it.make(it) || []) {
        const style = { ...(s.style || {}), opacity: (s.style?.opacity ?? 1) * it.op, ...(it.hot ? { color: css("--accent") } : {}) };
        out.push(moving && s.type === "tube" ? { type: "line", points: s.points, style: { ...style, width: 3 } } : { ...s, style });
      }
    }
    viewer.setOverlay("items", out.length ? out : null);
  }
  // push an item's state to the viewer
  function sync(it) {
    if (it.inst) {
      const st = { visible: it.vis, opacity: it.op, outline: it.hot ? css("--accent") : "none" };
      if (it.body) { st.position = add3(it.pos, it.off); st.rotation = it.rotd; }
      else st.position = add3(groupWorld(it.group), it.off);
      // send only what changed: each style call costs the viewer work, and the outline most
      const last = it.sent || {}, d = {};
      for (const k of Object.keys(st)) if (String(st[k]) !== String(last[k])) d[k] = st[k];
      if (Object.keys(d).length) { it.inst.style(d); it.sent = st; }
    } else if (it.kind === "shapes") shapesDirty = true;
  }
  // what components set: shown or not, faint or not, outlined (in this step), and an offset from where the pose has it
  function setItem(name, st) {
    const it = items[name]; if (!it) return;
    if (st.visible != null) it.vis = st.visible;
    if (st.opacity != null) it.op = st.opacity;
    if (st.hot != null) it.hot = st.hot;
    if (st.offset) it.off = frameVec(st.offset, st.frame || "local");
    sync(it);
  }
  // the part a name belongs to: a chain link "x_chain.12" belongs to "x_chain"
  function ownerOf(n) { let m = n; while (m && !(m in V.parts) && !(m in partToNode) && m.includes(".")) m = m.slice(0, m.lastIndexOf(".")); return (m in V.parts) || (m in partToNode) ? m : n; }

  // the golf model, or the parts' own meshes
  let model = null, models = [];
  if (V.golf) {
    // every model in the bundle: a large design is shown in several runs, each one model
    const b = await (await fetch(V.golf + "/bundle.json")).json();
    models = await Promise.all(Object.values(b.models).map(m => viewer.load(V.golf + "/" + m.path)));
    model = models[0];
    for (const md of models) (function walk(n) { for (const c of n.children || []) { if (c.children && c.children.length) walk(c); else if (c.name) makeItem(c.name, { kind: "inst", inst: c, model: md, group: (V.parts[c.name] || {}).group || "fixed" }); } })(md);
  }
  for (const [name, P] of Object.entries(V.parts)) {
    if (items[name] || !(P.p || P.shared)) continue;
    let pos = (P.shared ? V.shared[P.shared] : P).p, tri = (P.shared ? V.shared[P.shared] : P).t;
    if (P.loc) { const L = P.loc, q = new Array(pos.length); for (let i = 0; i < pos.length; i += 3) { const x = pos[i], y = pos[i + 1], z = pos[i + 2]; q[i] = L[0] * x + L[1] * y + L[2] * z + L[3]; q[i + 1] = L[4] * x + L[5] * y + L[6] * z + L[7]; q[i + 2] = L[8] * x + L[9] * y + L[10] * z + L[11]; } pos = q; }
    addMesh(name, { positions: pos, triangles: tri, color: P.colour, group: P.group || "fixed", info: P.info, kind: P.kind });
  }
  // an instance's name from a pick hit's path
  const nameAt = (hit) => {
    if (!hit || !models.length) return null;
    if (hit.name) return hit.name;
    for (const md of hit.model ? [models.find(m => m === hit.model || m.name === hit.model || m.modelName === hit.model) || models[0]] : models) {
      const i = md.instance ? md.instance(hit.instance) : null; if (i && i.name) return ownerOf(i.name);
    }
    return null;
  };

  function applyPose() {
    for (const it of Object.values(items)) if (!it.body && (it.group !== "fixed" || it.off.some(Boolean))) sync(it);
    Page.emit("pose", pose);
    shapesDirty = true; lastMove = performance.now();
    for (const a of axes) {
      const el = $("ax-" + a.id); if (!el) continue;
      el.value = pose[a.id]; $("ax-" + a.id + "-v").textContent = Math.round(pose[a.id]) + " " + (a.unit ?? "mm");
    }
  }
  $("ctl").insertAdjacentHTML("afterbegin", axes.map(a => `<label for="ax-${a.id}"><span class="row">${a.label || a.id} <span class="num" id="ax-${a.id}-v"></span></span><input id="ax-${a.id}" type="range" step="${a.step || 1}"></label>`).join(""));
  axes.forEach(a => {
    const el = $("ax-" + a.id); el.min = a.range[0]; el.max = a.range[1];
    el.addEventListener("input", () => { stopAnim(); pose[a.id] = +el.value; applyPose(); });
  });
  if (!axes.length) $("ctl").hidden = true;

  // highlight: the chosen parts keep their colour and are outlined, everything else goes faint
  const accent = () => css("--accent");
  // a name picks that part, or every part whose name starts with it and a dot ("y_carriage" picks "y_carriage.y_plate")
  function expand(names) {
    const out = new Set();
    for (const n of names || []) for (const m of Object.keys(items)) if (m === n || m.startsWith(n.endsWith(".") ? n : n + ".")) out.add(m);
    return out;
  }
  function highlight(names) {
    const on = expand(names);
    for (const [n, it] of Object.entries(items)) { it.op = !on.size || on.has(n) ? 1 : 0.12; it.hot = on.has(n); sync(it); }
  }

  // dimension lines, marks and labels: overlay shapes in world mm, drawn over the model
  let annot = [];
  const drawAnnot = () => viewer.setOverlay("annot", annot.length ? annot : null);
  function clearAnnot() { annot = []; drawAnnot(); }
  function addLabel(pos, text, cls) { annot.push({ type: "label", position: pos, text, style: { color: cls === "cg" ? css("--fail") : css("--ink"), depth: "front" } }); drawAnnot(); }
  function addDim(a, b, text) {
    const col = accent();
    annot.push({ type: "line", points: [a, b], arrows: "both", style: { color: col, width: 2, depth: "front" } });
    annot.push({ type: "point", position: a, diameter: 8, style: { color: col, depth: "front" } }, { type: "point", position: b, diameter: 8, style: { color: col, depth: "front" } });
    addLabel([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2], text);
  }
  function addCG(p, text) {
    const col = css("--fail");
    annot.push({ type: "point", position: p, diameter: 16, style: { color: col, depth: "front" } });
    annot.push({ type: "line", points: [p, [p[0], p[1], 0]], style: { color: col, width: 1.5, dash: [8, 6], depth: "front" } });
    addLabel([p[0], p[1], p[2] + 90], text, "cg");
  }

  // the floor grid: V.floor {x: [lo, hi], y: [lo, hi], step, major} in mm, else fitted round the model
  function makeFloor(fl) {
    const st = fl.step || 100, mj = fl.major || 1000, sh = [], ink = css("--ink") || "#333";
    for (let x = fl.x[0]; x <= fl.x[1] + 1e-6; x += st) sh.push({ type: "line", points: [[x, fl.y[0], 0], [x, fl.y[1], 0]], style: { color: ink, opacity: Math.abs(x % mj) > 1e-6 ? 0.12 : 0.3, width: 1 } });
    for (let y = fl.y[0]; y <= fl.y[1] + 1e-6; y += st) sh.push({ type: "line", points: [[fl.x[0], y, 0], [fl.x[1], y, 0]], style: { color: ink, opacity: Math.abs(y % mj) > 1e-6 ? 0.12 : 0.3, width: 1 } });
    viewer.setOverlay("floor", sh);
  }
  function bounds() {
    const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    const grow = (p) => { for (let k = 0; k < 3; k++) { lo[k] = Math.min(lo[k], p[k]); hi[k] = Math.max(hi[k], p[k]); } };
    for (const it of Object.values(items)) {
      if (it.inst) { const b = it.inst.bounds(); if (b && isFinite(b.min[0])) { grow(b.min); grow(b.max); } }

    }
    return isFinite(lo[0]) ? { min: lo, max: hi } : { min: [-500, -500, 0], max: [500, 500, 500] };
  }
  // camera views: V.views {name: {dir, height, target, label}}; without them, iso, side and front are fitted to the model
  let VIEWS = V.views;
  function fitViews() {
    const b = bounds(), c = [0, 1, 2].map(k => (b.min[k] + b.max[k]) / 2), r = Math.hypot(...[0, 1, 2].map(k => b.max[k] - b.min[k])) * 1.2 || 1000;
    if (!VIEWS) VIEWS = { iso: { dir: [-0.5, -0.72, 0.45], height: r, target: c }, side: { dir: [-1, 0, 0], height: r * 0.8, target: c }, front: { dir: [0, -1, 0], height: r, target: c } };
    if (!V.floor) { const st = 1000; makeFloor({ x: [Math.floor((b.min[0] - 500) / st) * st, Math.ceil((b.max[0] + 500) / st) * st], y: [Math.floor((b.min[1] - 500) / st) * st, Math.ceil((b.max[1] + 500) / st) * st] }); }
  }
  function setView(kind) {
    const v = VIEWS[kind] || VIEWS[Object.keys(VIEWS)[0]], n = Math.hypot(...v.dir);
    viewer.camera.projection = "orthographic";
    viewer.camera.set({ target: v.target, position: v.target.map((t, k) => t + v.dir[k] / n * 15000), up: [0, 0, 1], height: v.height });
  }

  // motion
  let anim = null;
  function stopAnim() { anim = null; }
  function animateTo(goal, ms, then) {
    goal = poseOf(goal);
    const from = { ...pose }, t0 = performance.now();
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    anim = (now) => {
      const t = reduce ? 1 : Math.min(1, (now - t0) / ms), e = t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      for (const k of Object.keys(pose)) if (goal[k] != null) pose[k] = from[k] + (goal[k] - from[k]) * e;
      applyPose();
      if (t >= 1) { anim = null; if (then) then(); }
    };
  }
  function sequence(goals, i = 0) {
    if (i >= goals.length) return;
    const [g, ms] = goals[i];
    animateTo(g, ms, () => sequence(goals, i + 1));
  }
  // a sweep shows the travel a check covers: V.sweeps {name: [[axis, value or null for where it started, ms], ...]}
  function sweep(kind) {
    const p = { ...pose };
    sequence((V.sweeps || {})[kind]?.map(([ax, v, ms]) => [{ ...p, [ax]: v ?? p[ax] }, ms]) || []);
  }
  // buttons under the sliders: V.buttons [{label, pose, ms} or {label, seq: [[pose, ms], ...]}]
  (V.buttons || []).forEach((b, i) => {
    const el = document.createElement("button"); el.type = "button"; el.id = "b-" + i; el.textContent = b.label;
    el.onclick = () => b.seq ? sequence(b.seq.map(([p, ms]) => [poseOf(p), ms])) : animateTo(b.pose, b.ms || 1200);
    $("ctl-btns").appendChild(el);
  });

  // ------------------------------------------------------------- selection: requirement <-> parts
  let selReq = null, selNode = null;
  function openGroupOf(id) {
    const r = reqs.find(q => q.id === id); if (!r) return;
    let changed = false;
    for (const k of (GROUPS[groupBy] || GROUPS.topic).groups(r)) if (collapsed.delete(groupBy + ":" + k)) changed = true;
    if (changed) renderReqs();
  }
  function selectReq(id, scroll) {
    // a component that shows this requirement better (a build step, a simulation) takes it
    const owner = id && Page.comps.find(c => c.claimsReq && c.claimsReq(id));
    if (owner) { if (owner.pane) showTab(owner.pane); owner.focusReq(id); return; }
    if (id) openGroupOf(id);
    if (Page.driver && activeTab !== "p-req") showTab("p-req");
    selReq = id; selNode = null;
    document.querySelectorAll(".req").forEach(el => el.classList.toggle("sel", el.dataset.req === id));
    document.querySelectorAll(".node").forEach(el => el.classList.remove("sel"));
    viewReq(id);
    if (scroll && id) $("row-" + id)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  // a requirement in 3D, from any tab: its pose, its parts lit, its dimensions and marks, and a note
  function viewReq(id) {
    selItem = null; markItems();
    clearAnnot();
    if (!id) { highlight(null); $("note").classList.remove("show"); return; }
    const r = reqs.find(q => q.id === id), z = (V.viz || {})[id] || {};
    // the check's own parts when it names them, else every part of the nodes it is about
    const parts = new Set(z.parts && z.parts.length ? z.parts : r.applies_to.flatMap(nodeParts));
    highlight(parts.size ? [...parts] : null);
    (z.dims || []).forEach(([a, b, t]) => addDim(a, b, t));
    (z.marks || []).forEach(([p, t]) => addCG(p, t));
    if (z.view) setView(z.view);
    if (z.pose) animateTo(z.pose, 900, z.sweep ? () => sweep(z.sweep) : null);
    const x = res[id] || {}, s = status(id);
    $("note").innerHTML = `<b>${id}</b> · <span class="pill ${STANDING[standing(id)][1]}">${STANDING[standing(id)][0]}</span> ${r.text}` +
      (z.sweep ? ` <br><span style="color:var(--muted)">Showing the travel the check covers.</span>` : "") +
      (x.case ? `<br><span style="color:var(--muted)">Worst case: ${x.case}</span>` : "");
    $("note").classList.add("show");
  }
  function selectNode(nid) { setFocus(nid ? { type: "node", id: nid } : null); }
  $("v-clear").onclick = () => { setFocus(null); selectReq(null); };

  // picking in the viewer: a click selects the part's block; hovering names the part
  let down = null, hoverT = 0;
  stageEl.addEventListener("pointerdown", e => { down = [e.clientX, e.clientY]; });
  async function pickName(e) {
    try { const hits = await viewer.pickAt(e); return nameAt((hits || [])[0]); } catch (err) { return null; }
  }
  stageEl.addEventListener("pointerup", async e => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
    const n = await pickName(e); if (n && partToNode[n]) selectNode(partToNode[n]);
  });
  stageEl.addEventListener("pointermove", async e => {
    const now = performance.now(); if (now - hoverT < 120) return; hoverT = now;
    const n = await pickName(e), h = $("hover");
    if (!n) { h.style.display = "none"; return; }
    const r = view.getBoundingClientRect();
    h.textContent = n + (partToNode[n] ? " · " + partToNode[n] : "") + (V.parts[n] && V.parts[n].info ? " — " + V.parts[n].info : "");
    h.style.left = (e.clientX - r.left + 12) + "px"; h.style.top = (e.clientY - r.top + 12) + "px"; h.style.display = "block";
  });
  stageEl.addEventListener("pointerleave", () => { $("hover").style.display = "none"; });

  // ------------------------------------------------------------- block diagram: always on top, it sets the focus every tab filters by
  // and shows what the 3D view shows: blocks fade with their parts, the current build step's blocks are outlined
  // the layout: V.diagram {nodes: {id: [x, y]}, ext: {name: [x, y, [touches]]}, W, H, w, h, frame: [x, y, w, h], size: [w, h]};
  // without one, the top-level blocks go in a grid with the things outside down the left
  const DG = V.diagram || (function auto() {
    const top = S.nodes.filter(n => n.parent === "P"), cols = Math.max(1, Math.ceil(Math.sqrt(top.length))), W = 128, H = 54;
    const nodes = {}; top.forEach((n, i) => { nodes[n.id] = [104 + (i % cols) * (W + 50), 30 + Math.floor(i / cols) * (H + 26)]; });
    const outs = [...new Set(S.interfaces.filter(i => i.b.startsWith("external:")).map(i => i.b.slice(9)))];
    const topOf = (id) => { let n = nodes[id] ? id : null, q = S.nodes.find(m => m.id === id); while (!n && q && q.parent) { if (nodes[q.parent]) n = q.parent; q = S.nodes.find(m => m.id === q.parent); } return n; };
    const ext = {}; outs.forEach((e, i) => { ext[e] = [8, 24 + i * 50, [...new Set(S.interfaces.filter(f => f.b === "external:" + e).map(f => topOf(f.a)).filter(Boolean))]]; });
    const rows = Math.ceil(top.length / cols), h = Math.max(30 + rows * (H + 26), 24 + outs.length * 50 + 10);
    return { nodes, ext, W, H, w: 76, h: 24, frame: [96, 4, 30 + cols * (W + 50), h - 8], size: [140 + cols * (W + 50), h] };
  })();
  const DGF = DG.frame || [96, 4, 508, 306], DGS = DG.size || [700, 314];
  const KIND_COL = { mechanical: "var(--muted)", electrical: "#d08a1c", fluid: "#2f7fbf" };
  const linkKey = (L) => [L.a, L.b].sort().join("|");
  const dgName = (x) => x.startsWith("ext:") ? x.slice(4) + " (outside)" : `${x} · ${nodes[x]?.name.split(/[:,(]/)[0] || ""}`;
  let dgSel = null, focus = null;
  function dgNodeStatus(id) {
    const c = { pass: 0, fail: 0, open: 0 };
    reqsOfNode(id).forEach(r => c[status(r.id)]++);
    return c;
  }
  const DG_LINKS = (function () {
    const m = new Map();
    const add = (a, b, i) => { const k = [a, b].sort().join("|"); if (!m.has(k)) m.set(k, { a, b, items: [], kinds: new Set() }); m.get(k).items.push(i); m.get(k).kinds.add(i.kind); };
    for (const i of S.interfaces) {
      if (i.a === i.b) continue;
      if (i.b.startsWith("external:")) { const e = i.b.slice(9); for (const t of (DG.ext[e] || [0, 0, []])[2]) add("ext:" + e, t, i); continue; }
      add(i.a, i.b, i);
    }
    return [...m.values()];
  })();
  function dgPos(id) {
    if (id.startsWith("ext:")) { const e = DG.ext[id.slice(4)]; return [e[0], e[1], DG.w, DG.h]; }
    const p = DG.nodes[id]; return [p[0], p[1], DG.W, DG.H];
  }
  function dgEdge(a, b) {
    const [ax, ay, aw, ah] = dgPos(a), [bx, by, bw, bh] = dgPos(b);
    const ca = [ax + aw / 2, ay + ah / 2], cb = [bx + bw / 2, by + bh / 2];
    const clip = (c, w, h, t) => {           // where the line from c towards t leaves the box
      const dx = t[0] - c[0], dy = t[1] - c[1];
      const s = Math.min(Math.abs((w / 2) / (dx || 1e-9)), Math.abs((h / 2) / (dy || 1e-9)));
      return [c[0] + dx * s, c[1] + dy * s];
    };
    return [clip(ca, aw, ah, cb), clip(cb, bw, bh, ca)];
  }
  function renderDiagram() {
    const isSel = (id) => dgSel && dgSel.type === "node" && dgSel.id === id;
    let svg = `<svg viewBox="0 0 ${DGS[0]} ${DGS[1]}" role="img" aria-label="Block diagram: the machine's blocks, the things outside it and the interfaces between them. Click one to filter the tabs below.">
      <defs><marker id="dg-dot" viewBox="0 0 6 6" refX="3" refY="3" markerUnits="userSpaceOnUse" markerWidth="7" markerHeight="7"><circle cx="3" cy="3" r="2.4" fill="var(--muted)"/></marker></defs>
      <rect x="${DGF[0]}" y="${DGF[1]}" width="${DGF[2]}" height="${DGF[3]}" rx="12" class="dg-frame"/>
      <text x="${DGF[0] + 10}" y="${DGF[1] + 16}" class="dg-ft">P · ${V.whole || "whole system"}</text>`;
    const badges = [];
    for (const L of DG_LINKS) {
      const [[x1, y1], [x2, y2]] = dgEdge(L.a, L.b);
      const kind = L.kinds.size === 1 ? [...L.kinds][0] : (L.kinds.has("electrical") ? "electrical" : "mechanical");
      const key = linkKey(L);
      const sel = dgSel && dgSel.type === "link" && dgSel.key === key;
      const on = dgSel && dgSel.type === "node" && (L.a === dgSel.id || L.b === dgSel.id);
      let mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
      for (const t of [0.5, 0.3, 0.7, 0.2, 0.8]) {   // keep count badges apart
        mx = x1 + (x2 - x1) * t; my = y1 + (y2 - y1) * t;
        if (L.items.length < 2 || badges.every(([bx, by]) => Math.hypot(bx - mx, by - my) > 19)) break;
      }
      if (L.items.length > 1) badges.push([mx, my]);
      svg += `<g class="dg-link${sel ? " sel" : ""}${on ? " on" : ""}" data-key="${key}" data-a="${L.a}" data-b="${L.b}" tabindex="0" role="button" aria-label="${L.items.length} interfaces between ${L.a} and ${L.b}">
        <title>${L.items.map(i => `${i.id} ${i.kind}: ${i.text}`).join("\n")}</title>
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="hit"/>
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${KIND_COL[kind]}" stroke-width="${1.5 + Math.min(4, L.items.length)}" ${L.kinds.has("fluid") && L.kinds.size > 1 ? 'stroke-dasharray="7 4"' : ""} marker-start="url(#dg-dot)" marker-end="url(#dg-dot)"/>
        ${L.items.length > 1 ? `<circle cx="${mx}" cy="${my}" r="8.5" class="dg-badge"/><text x="${mx}" y="${my + 3.5}" class="dg-bt">${L.items.length}</text>` : ""}
      </g>`;
    }
    for (const [e, [x, y]] of Object.entries(DG.ext)) {
      const id = "ext:" + e;
      svg += `<g class="dg-ext${isSel(id) ? " sel" : ""}" data-node="${id}" tabindex="0" role="button" aria-label="outside: ${e}">
        <rect x="${x}" y="${y}" width="${DG.w}" height="${DG.h}" rx="12"/><text x="${x + DG.w / 2}" y="${y + DG.h / 2 + 4}">${e}</text></g>`;
    }
    for (const [id, [x, y]] of Object.entries(DG.nodes)) {
      const n = nodes[id]; if (!n) continue;
      const c = dgNodeStatus(id), worst = c.fail ? "fail" : c.open ? "open" : "pass";
      const kg = n.mass_kg != null ? `${Math.round(n.mass_kg)} kg` : "";
      const nm = n.name.split(/[:,(]/)[0], short = nm.length > 20 ? nm.slice(0, 19).trim() + "…" : nm;
      const pills = [["fail", c.fail], ["pass", c.pass], ["open", c.open]].filter(([, v]) => v);
      let px = x + 10;
      svg += `<g class="dg-node ${worst}${isSel(id) ? " sel" : ""}" data-node="${id}" tabindex="0" role="button" aria-label="${id}: ${n.name}">
        <title>${id} · ${n.name}${kg ? " · " + kg : ""}\n${c.pass} pass, ${c.fail} fail, ${c.open} not checked by model</title>
        <rect x="${x}" y="${y}" width="${DG.W}" height="${DG.H}" rx="7"/><rect x="${x}" y="${y}" width="5" height="${DG.H}" rx="2" class="bar"/>
        <text x="${x + 11}" y="${y + 16}" class="id">${id}</text><text x="${x + DG.W - 7}" y="${y + 16}" class="kg">${kg}</text>
        <text x="${x + 11}" y="${y + 30}" class="nm">${short}</text>`;
      for (const [s, v] of pills) { const w = 9 + String(v).length * 7; svg += `<rect x="${px}" y="${y + 36}" width="${w}" height="13" rx="6.5" class="pl ${s}"/><text x="${px + w / 2}" y="${y + 46}" class="pt ${s}">${v}</text>`; px += w + 4; }
      svg += `</g>`;
    }
    svg += `</svg>`;
    $("dg-svg").innerHTML = svg;
    dgLast = "";
    $("dg-svg").querySelectorAll("[data-node]").forEach(el => {
      const go = () => { const id = el.dataset.node; setFocus(isSel(id) ? null : { type: "node", id }); };
      el.addEventListener("click", go); el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
    $("dg-svg").querySelectorAll(".dg-link").forEach(el => {
      const go = () => { const k = el.dataset.key; setFocus(dgSel && dgSel.key === k ? null : { type: "link", key: k }); };
      el.addEventListener("click", go); el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
    });
  }
  $("dg-legend").innerHTML = Object.entries(KIND_COL).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join("") +
    `<span class="dg-hint">faded: hidden or faint in 3D${Page.comps.some(c => c.drives) ? " · outlined: in this build step" : ""}</span>`;
  const dgOpen = () => !$("dg").classList.contains("shut");
  $("dg-fold").addEventListener("click", () => {
    const shut = $("dg").classList.toggle("shut");
    $("dg-fold").textContent = shut ? "Show" : "Hide"; $("dg-fold").setAttribute("aria-expanded", !shut);
    store.set("dgShut", shut ? "1" : "");
  });
  if (store.get("dgShut", "")) { $("dg").classList.add("shut"); $("dg-fold").textContent = "Show"; $("dg-fold").setAttribute("aria-expanded", "false"); }

  // the focus: what a block, line or outside thing stands for in every tab
  function focusOf(sel) {
    if (!sel) return null;
    let ns, items, label;
    if (sel.type === "link") {
      const L = DG_LINKS.find(l => linkKey(l) === sel.key); if (!L) return null;
      ns = [L.a, L.b].filter(x => !x.startsWith("ext:")); items = L.items;
      label = `${dgName(L.a)} ↔ ${dgName(L.b)}`;
    } else if (sel.id.startsWith("ext:")) {
      const e = sel.id.slice(4);
      ns = (DG.ext[e] || [0, 0, []])[2]; items = S.interfaces.filter(i => i.b === "external:" + e);
      label = `${e} (outside), touching ${ns.join(" and ")}`;
    } else {
      ns = [sel.id]; items = DG_LINKS.filter(l => l.a === sel.id || l.b === sel.id).flatMap(l => l.items);
      label = dgName(sel.id);
    }
    const nset = new Set(ns);
    return { sel, nodes: nset, ifaces: new Set(items.map(i => i.id)), label,
             reqs: new Set(reqs.filter(r => r.applies_to.some(n => nset.has(n))).map(r => r.id)) };
  }
  // which block a part belongs to: its own name, or the part or assembly name it sits under
  const nodeOfName = {};
  function nodeOfPart(name) {
    if (name in nodeOfName) return nodeOfName[name];
    let hit = null;
    for (const n of S.nodes) for (const e of n.shows || []) if (name === e || name.startsWith(e + ".") || e.startsWith(name + ".")) hit = hit || n.id;
    return nodeOfName[name] = hit;
  }
  function focusParts() { return focus ? [...focus.nodes].flatMap(nodeParts) : []; }
  function applyFocusView() {
    if (Page.driver) return;                  // a component that drives the meshes (the build) draws its own state
    clearAnnot();
    const parts = focusParts();
    highlight(parts.length ? parts : null);
    if (focus) { $("note").innerHTML = `<b>${focus.sel.type === "link" ? "Interfaces" : "Focus"}</b> ${focus.label}`; $("note").classList.add("show"); }
    else $("note").classList.remove("show");
  }
  function setFocus(sel) {
    dgSel = sel; focus = focusOf(sel);
    reqFilter = focus ? { ids: [...focus.reqs], label: focus.label } : null;
    selReq = null;
    selItem = null;
    renderReqs(); renderTree(); renderInterfaces(); renderDiagram(); updateFilterBar();
    applyFocusView();
    Page.emit("focus", focus);
  }
  function updateFilterBar() {
    const pane = [...document.querySelectorAll(".pane")].find(p => !p.hidden)?.id;
    let n = "";
    if (focus) {
      if (pane === "p-req") n = `${focus.reqs.size} requirement${focus.reqs.size === 1 ? "" : "s"}`;
      else if (pane === "p-if") n = `${focus.ifaces.size} interface${focus.ifaces.size === 1 ? "" : "s"}`;
      else if (pane === "p-tree") n = `${focus.nodes.size} block${focus.nodes.size === 1 ? "" : "s"}`;
      else { const c = Page.comps.find(c => c.pane === pane && c.filterLabel); if (c) n = c.filterLabel(focus); }
    }
    $("filter").classList.toggle("show", !!focus);
    if (focus) $("filter-t").innerHTML = `Showing <b>${focus.label}</b>${n ? " · " + n : ""}`;
  }
  // the diagram follows the 3D view: a block fades when its parts are faint or not built yet
  let nodeMeshes = null, dgLast = "", dgTick = 0;
  function dgReflect() {
    if (++dgTick % 5) return;
    const building = !!Page.driver;
    nodeMeshes ||= Object.fromEntries(Object.keys(DG.nodes).map(id => [id, [...expand(nodeParts(id))].map(n => items[n]).filter(Boolean)]));
    const st = {};
    for (const [id, ms] of Object.entries(nodeMeshes)) {
      let vis = 0, lit = 0, hot = 0;
      for (const m of ms) {
        if (!m.vis) continue; vis++;
        if (m.op > 0.5) lit++;
        if (m.hot) hot++;
      }
      st[id] = !ms.length ? "" : vis === 0 ? "unbuilt" : lit === 0 ? "faint" : (building && vis < ms.length ? "part" : "") + (hot && building ? " hot" : "");
    }
    const sig = JSON.stringify(st) + building;
    if (sig === dgLast) return; dgLast = sig;
    const svgEl = $("dg-svg");
    const gone = (id) => /unbuilt|faint/.test(st[id] || "");
    for (const [id, c] of Object.entries(st)) {
      const g = svgEl.querySelector(`.dg-node[data-node="${id}"]`); if (!g) continue;
      g.classList.remove("unbuilt", "faint", "part", "hot");
      c.split(" ").filter(Boolean).forEach(k => g.classList.add(k));
    }
    for (const [e, v] of Object.entries(DG.ext)) svgEl.querySelector(`.dg-ext[data-node="ext:${e}"]`)?.classList.toggle("faint", v[2].length > 0 && v[2].every(gone));
    svgEl.querySelectorAll(".dg-link").forEach(g => {
      const ends = [g.dataset.a, g.dataset.b].filter(x => !x.startsWith("ext:"));
      g.classList.toggle("faint", ends.some(gone));
    });
  }

  // ------------------------------------------------------------- the loop: motion, components, the diagram, the overlays
  function resize() { viewer.redraw && viewer.redraw(); }
  function frame(now) {
    if (anim) anim(now);
    Page.emit("frame", now);
    drawShapes();
    dgReflect();
    requestAnimationFrame(frame);
  }

  // what the components can use
  Object.assign(Page, {
    V, S, reqs, res, nodes, status, standing, STANDING, partToNode, nodeParts, reqsOfNode, expand, nodeOfPart, dgName,
    viewer, models, items, addMesh, addBody, placeBody, addShapes, setItem, ownerOf, overlay: (name, shapes) => viewer.setOverlay(name, shapes),
    toWorld, rot, groupOffset, pose, poseOf, axes, applyPose, animateTo, stopAnim, sequence,
    highlight, accent, clearAnnot, addDim, addLabel, addCG, setView, resize, view,
    showTab, selectReq, viewReq, showItem, markItems, asShown, selectNode, openGroupOf, setFocus, focusParts, applyFocusView, updateFilterBar, renderReqs,
    linkOf: (key) => DG_LINKS.find(l => linkKey(l) === key),
    // a requirement's chip, coloured by status; bindReqChips(el) makes every chip in el open its requirement
    reqChip: (id, text) => `<span class="chip ${status(id)}" data-req="${id}" title="${(reqs.find(r => r.id === id) || {}).text || id}">${text || id}</span>`,
    bindReqChips(el) { el.querySelectorAll("[data-req]").forEach(c => c.addEventListener("click", (e) => { e.stopPropagation(); showTab("p-req"); selectReq(c.dataset.req, true); })); },
    // the diagram-level blocks a product-tree node is in or under (for filtering by the diagram's focus)
    inFocus(nodeId) { if (!focus) return true; let n = nodeId; while (n) { if (focus.nodes.has(n)) return true; n = (nodes[n] || {}).parent; } return false; },
    note(html) { if (html) { $("note").innerHTML = html; $("note").classList.add("show"); } else $("note").classList.remove("show"); },
  });
  Object.defineProperty(Page, "focus", { get: () => focus });
  Object.defineProperty(Page, "selReq", { get: () => selReq, set: (v) => { selReq = v; } });
  Object.defineProperty(Page, "tab", { get: () => activeTab });
  // the components: each adds its meshes, tab, stage panel and handlers once the core is built
  for (const c of Page.comps) if (c.init) { try { c.init(Page); } catch (e) { console.error(c.id, e); } }
  await loadPageObjects();
  renderTabs();
  renderReqs(); renderTree(); renderInterfaces(); renderDiagram(); updateFilterBar();
  for (const c of Page.comps) if (c.render) { try { c.render(); } catch (e) { console.error(c.id, e); } }
  applyPose(); fitViews();
  if (V.floor) makeFloor(V.floor);
  Object.keys(VIEWS).forEach(k => { const b = document.createElement("button"); b.type = "button"; b.id = "v-" + k; b.textContent = VIEWS[k].label || k[0].toUpperCase() + k.slice(1); b.onclick = () => setView(k); $("viewbar").insertBefore(b, $("v-clear")); });
  setView(Object.keys(VIEWS)[0]); applyPose();
  requestAnimationFrame(frame);
  }
})();
