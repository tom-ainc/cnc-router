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
      for (const src of V.components || []) await loadScript(src);
    } catch (e) {
      $("err").style.display = "block"; $("err").textContent = "The page did not load: " + e.message; return;
    }
    main(V, S);
  })();

  function main(V, S) {
  V.parts ||= {}; V.viz ||= {};
  if (V.title) { document.title = V.title; $("title").textContent = V.title; }
  $("subtitle").textContent = V.subtitle || "";
  Page.style("#panes { display: contents; }");
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
  function renderInterfaces() {
    const name = (x) => x.startsWith("external:") ? x.slice(9) + " (outside)" : (x === "P" ? "machine" : x);
    const its = focus ? S.interfaces.filter(i => focus.ifaces.has(i.id)) : S.interfaces;
    const bl = focus ? S.blocks.filter(b => b.node === "P" || focus.nodes.has(b.node)) : S.blocks;
    $("p-if").innerHTML = (its.length ? "" : `<div class="empty">No interfaces.</div>`) + its.map(i => `<div class="item"><div class="id">${i.id}</div>
      <div><b>${name(i.a)}</b> ↔ <b>${name(i.b)}</b> · ${i.kind}<br>${i.text}</div>
      ${i.keeps ? `<div class="why">keeps: ${i.keeps}</div>` : ""}</div>`).join("") +
      `<div class="section-h">Flows</div>` + bl.map(b => `<div class="item"><div class="id">${b.node}</div>
      <div>in: ${b.inputs.map(p => p.name + (p.unit ? " (" + p.unit + ")" : "")).join(", ")}<br>out: ${b.outputs.map(p => p.name).join(", ")}</div></div>`).join("");
  }
  function renderAssumptions() {
    $("p-as").innerHTML = S.assumptions.map(a => `<div class="item"><div class="id">${a.id}</div><div>${a.text}</div><div class="why">${a.reason}</div></div>`).join("");
  }
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
    const tabs = [["p-req", "t-req", "Requirements"], ["p-tree", "t-tree", "Product tree"], ["p-if", "t-if", "Interfaces"], ["p-as", "t-as", "Assumptions"]];
    for (const c of Page.comps) {
      if (!c.pane) continue;
      const t = [c.pane, c.tabId || "t-" + c.pane.replace(/^p-/, ""), c.tab || c.id], k = c.after ? tabs.findIndex(x => x[0] === c.after) : -1;
      if (k >= 0) tabs.splice(k + 1, 0, t); else tabs.push(t);
      if (c.stage) $("ctl").insertAdjacentHTML("beforebegin", c.stage);
    }
    $("tabs").innerHTML = tabs.map(([p, id, l]) => `<button role="tab" aria-selected="${p === activeTab}" data-pane="${p}" id="${id}">${l}</button>`).join("");
    $("panes").innerHTML = tabs.map(([p]) => `<div class="pane" id="${p}" role="tabpanel"${p === activeTab ? "" : " hidden"}></div>`).join("");
    document.querySelectorAll(".tabs button").forEach(b => b.addEventListener("click", () => showTab(b.dataset.pane)));
  }
  // ------------------------------------------------------------- 3D
  const view = $("view");
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
  view.prepend(renderer.domElement);
  const scene = new THREE.Scene();
  // orthographic: true proportions in every view; viewH is the height of world the view shows (mm), zoom scales it
  let viewH = 3200, aspect = 1;
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 10, 60000);
  function frustum() {
    camera.top = viewH / 2; camera.bottom = -viewH / 2;
    camera.left = -viewH * aspect / 2; camera.right = viewH * aspect / 2;
    camera.updateProjectionMatrix();
  }
  camera.up.set(0, 0, 1);
  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 0.75));
  const sun = new THREE.DirectionalLight(0xffffff, 0.65); sun.position.set(-2000, -3000, 4000); scene.add(sun);
  const fill = new THREE.DirectionalLight(0xffffff, 0.25); fill.position.set(3000, 2000, 1500); scene.add(fill);

  // the floor grid: V.floor {x: [lo, hi], y: [lo, hi], step, major} in mm, else fitted round the model once it is built
  const floor = new THREE.Group();
  const gmat = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.18 });
  const gmat2 = new THREE.LineBasicMaterial({ transparent: true, opacity: 0.4 });
  function makeFloor(fl) {
    floor.clear();
    const st = fl.step || 100, mj = fl.major || 1000, g1 = [], g2 = [];
    for (let x = fl.x[0]; x <= fl.x[1] + 1e-6; x += st) (Math.abs(x % mj) > 1e-6 ? g1 : g2).push(x, fl.y[0], 0, x, fl.y[1], 0);
    for (let y = fl.y[0]; y <= fl.y[1] + 1e-6; y += st) (Math.abs(y % mj) > 1e-6 ? g1 : g2).push(fl.x[0], y, 0, fl.x[1], y, 0);
    [[g1, gmat], [g2, gmat2]].forEach(([a, m]) => { const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(a, 3)); floor.add(new THREE.LineSegments(g, m)); });
  }
  scene.add(floor);

  // the model's own frame in the world: V.frame {translate: [x, y, z], rotate: [rx, ry, rz] degrees}
  const local = new THREE.Group();
  const FR = V.frame || {};
  local.position.set(...(FR.translate || [0, 0, 0]));
  local.rotation.set(...(FR.rotate || [0, 0, 0]).map(THREE.MathUtils.degToRad));
  scene.add(local);
  // moving groups: V.groups {name: [[axis, [dx, dy, dz], scale, ref], ...]}: the group moves by dir * scale * (pose[axis] - ref)
  // summed over its terms. "fixed" is the model's frame, "world" the scene.
  const groupObjs = {};
  for (const g of Object.keys(V.groups || {})) { groupObjs[g] = new THREE.Group(); local.add(groupObjs[g]); }
  const groupObj = (g) => g === "world" ? scene : groupObjs[g] || local;
  const meshes = {};
  const sharedGeo = {};
  function makeGeo(src, smooth) {
    let g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(src.p, 3));
    g.setIndex(src.t);
    if (smooth) { g.computeVertexNormals(); return g; }       // bought-part meshes: smooth shading
    g = g.toNonIndexed(); g.computeVertexNormals(); return g;
  }
  for (const [name, P] of Object.entries(V.parts)) {
    const geo = P.shared ? (sharedGeo[P.shared] ||= makeGeo(V.shared[P.shared], true)) : makeGeo(P, false);
    const mat = new THREE.MeshStandardMaterial({ color: P.colour, roughness: 0.65, metalness: 0.15, transparent: true, opacity: 1, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
    const m = new THREE.Mesh(geo, mat);
    m.userData.name = name; m.userData.base = new THREE.Color(P.colour);
    if (P.loc) { m.matrixAutoUpdate = false; m.matrix.set(...P.loc); }
    const edgeGeo = P.shared ? (sharedGeo[P.shared + ":edges"] ||= new THREE.EdgesGeometry(geo, 40)) : new THREE.EdgesGeometry(geo, 25);
    const edges = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.25 }));
    m.add(edges); m.userData.edges = edges;
    groupObj(P.group).add(m);
    meshes[name] = m;
  }
  // ---- the pose: one value per axis (V.axes [{id, label, range, unit, start}]); a pose given as a list is in axis order
  const axes = V.axes || [];
  const pose = Object.fromEntries(axes.map(a => [a.id, a.start ?? a.range[0]]));
  const poseOf = (p) => Array.isArray(p) ? Object.fromEntries(axes.map((a, i) => [a.id, p[i]])) : { ...pose, ...p };
  function groupOffset(g) {
    const o = [0, 0, 0];
    for (const [ax, d, k, ref] of (V.groups || {})[g] || []) { const s = (k ?? 1) * ((pose[ax] ?? 0) - (ref ?? 0)); o[0] += d[0] * s; o[1] += d[1] * s; o[2] += d[2] * s; }
    return o;
  }
  function applyPose() {
    for (const [g, obj] of Object.entries(groupObjs)) obj.position.set(...groupOffset(g));
    Page.emit("pose", pose);
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

  // highlight: the chosen parts keep their colour, everything else goes faint
  const accent = () => new THREE.Color(css("--accent"));
  // a name picks that part, or every part whose name starts with it and a dot ("y_carriage" picks "y_carriage.y_plate")
  function expand(names) {
    const out = new Set();
    for (const n of names || []) for (const m of Object.keys(meshes)) if (m === n || m.startsWith(n.endsWith(".") ? n : n + ".")) out.add(m);
    return out;
  }
  function highlight(names) {
    const on = expand(names);
    for (const [n, m] of Object.entries(meshes)) {
      const lit = !on.size || on.has(n);
      m.material.opacity = lit ? 1 : 0.12;
      m.material.depthWrite = lit;
      m.material.emissive = on.has(n) ? accent().multiplyScalar(0.28) : new THREE.Color(0);
      if (m.userData.edges) m.userData.edges.material.opacity = lit ? 0.25 : 0.05;
    }
  }

  // dimension lines and markers
  const annot = new THREE.Group(); scene.add(annot);
  let labels = [];
  function clearAnnot() { annot.clear(); labels.forEach(l => l.el.remove()); labels = []; }
  function addLabel(pos, text, cls) {
    const el = document.createElement("div"); el.className = "dim-label" + (cls ? " " + cls : ""); el.textContent = text;
    $("labels").appendChild(el); labels.push({ el, pos });
  }
  function onTop(o) { o.renderOrder = 999; o.material.transparent = true; o.material.depthTest = false; return o; }
  function addDim(a, b, text) {
    const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b);
    const col = accent();
    const g = new THREE.BufferGeometry().setFromPoints([A, B]);
    annot.add(onTop(new THREE.Line(g, new THREE.LineBasicMaterial({ color: col }))));
    [A, B].forEach(p => { const s = onTop(new THREE.Mesh(new THREE.SphereGeometry(12, 12, 8), new THREE.MeshBasicMaterial({ color: col }))); s.position.copy(p); annot.add(s); });
    addLabel(A.clone().add(B).multiplyScalar(0.5), text);
  }
  function addCG(p, text) {
    const col = new THREE.Color(css("--fail"));
    const s = onTop(new THREE.Mesh(new THREE.SphereGeometry(28, 20, 14), new THREE.MeshBasicMaterial({ color: col })));
    s.position.set(...p); annot.add(s);
    const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...p), new THREE.Vector3(p[0], p[1], 0)]);
    annot.add(onTop(new THREE.Line(g, new THREE.LineDashedMaterial({ color: col, dashSize: 30, gapSize: 20 }))).computeLineDistances());
    addLabel(new THREE.Vector3(p[0], p[1], p[2] + 90), text, "cg");
  }

  // camera views: V.views {name: {dir, height, target, label}}; without them, iso, side and front are fitted to the model
  let VIEWS = V.views;
  function fitViews() {
    const b = new THREE.Box3();
    for (const m of Object.values(meshes)) if (m.geometry && !m.isInstancedMesh) { m.geometry.computeBoundingBox(); const bb = m.geometry.boundingBox.clone().applyMatrix4(m.matrixWorld); if (isFinite(bb.min.x)) b.union(bb); }
    const c = b.getCenter(new THREE.Vector3()), s = b.getSize(new THREE.Vector3()), r = s.length() * 1.2 || 1000;
    if (!VIEWS) VIEWS = { iso: { dir: [-0.5, -0.72, 0.45], height: r, target: c.toArray() }, side: { dir: [-1, 0, 0], height: r * 0.8, target: c.toArray() },
                          front: { dir: [0, -1, 0], height: r, target: c.toArray() } };
    if (!V.floor) { const st = 1000; makeFloor({ x: [Math.floor((b.min.x - 500) / st) * st, Math.ceil((b.max.x + 500) / st) * st], y: [Math.floor((b.min.y - 500) / st) * st, Math.ceil((b.max.y + 500) / st) * st] }); }
  }
  function setView(kind) {
    const v = VIEWS[kind] || VIEWS[Object.keys(VIEWS)[0]];
    const tg = new THREE.Vector3(...v.target), d = new THREE.Vector3(...v.dir).normalize().multiplyScalar(15000);
    controls.target.copy(tg);
    camera.position.copy(tg).add(d);
    viewH = v.height; camera.zoom = 1; frustum();
    controls.update();
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
    if (scroll) $("row-" + id)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
  function selectNode(nid) { setFocus(nid ? { type: "node", id: nid } : null); }
  $("v-clear").onclick = () => { setFocus(null); selectReq(null); };

  // picking in the viewer
  const ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
  function pick(e) {
    const r = renderer.domElement.getBoundingClientRect();
    mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(mouse, camera);
    const hits = ray.intersectObjects(Object.values(meshes).filter(m => m.visible && m.material.opacity > 0.5), false);
    return hits.length ? hits[0].object.userData.name : null;
  }
  let down = null;
  renderer.domElement.addEventListener("pointerdown", e => { down = [e.clientX, e.clientY]; });
  renderer.domElement.addEventListener("pointerup", e => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
    const n = pick(e); if (n && partToNode[n]) selectNode(partToNode[n]);
  });
  renderer.domElement.addEventListener("pointermove", e => {
    const n = pick(e), h = $("hover");
    if (!n) { h.style.display = "none"; return; }
    const r = view.getBoundingClientRect();
    h.textContent = n + (partToNode[n] ? " · " + partToNode[n] : "") + (V.parts[n] && V.parts[n].info ? " — " + V.parts[n].info : "");
    h.style.left = (e.clientX - r.left + 12) + "px"; h.style.top = (e.clientY - r.top + 12) + "px"; h.style.display = "block";
  });
  renderer.domElement.addEventListener("pointerleave", () => { $("hover").style.display = "none"; });

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
      else if (pane === "p-as") n = "assumptions are not tied to blocks, so all are shown";
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
    nodeMeshes ||= Object.fromEntries(Object.keys(DG.nodes).map(id => [id, [...expand(nodeParts(id))].map(n => meshes[n]).filter(Boolean)]));
    const st = {};
    for (const [id, ms] of Object.entries(nodeMeshes)) {
      let vis = 0, lit = 0, hot = 0;
      for (const m of ms) {
        if (!m.visible) continue; vis++;
        if (m.material.opacity > 0.5) lit++;
        const em = m.material.emissive; if (em && em.r + em.g + em.b > 0.01) hot++;
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

  // ------------------------------------------------------------- render loop
  function resize() {
    const w = view.clientWidth, h = view.clientHeight;
    renderer.setSize(w, h, false); aspect = w / h; frustum();
  }
  new ResizeObserver(resize).observe(view);
  function themeColours() {
    renderer.setClearColor(new THREE.Color(css("--viewer")));
    const ink = new THREE.Color(css("--ink")); gmat.color = ink; gmat2.color = ink;
  }
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", themeColours);
  new MutationObserver(themeColours).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const v3 = new THREE.Vector3();
  function frame(now) {
    if (anim) anim(now);
    Page.emit("frame", now);
    dgReflect();
    controls.update();
    if (!Page.hold) renderer.render(scene, camera);
    const w = view.clientWidth, h = view.clientHeight;
    for (const l of labels) {
      v3.copy(l.pos).project(camera);
      l.el.style.left = ((v3.x + 1) / 2 * w) + "px"; l.el.style.top = ((1 - v3.y) / 2 * h) + "px";
      l.el.style.display = v3.z < 1 ? "block" : "none";
    }
    requestAnimationFrame(frame);
  }

  // what the components can use
  Object.assign(Page, {
    V, S, THREE, reqs, res, nodes, status, standing, STANDING, partToNode, nodeParts, reqsOfNode, expand, nodeOfPart, dgName,
    scene, local, camera, renderer, controls, meshes, groupObj, groupOffset, pose, poseOf, axes, applyPose, animateTo, stopAnim, sequence,
    highlight, accent, clearAnnot, addDim, addLabel, addCG, setView, resize, view,
    showTab, selectReq, selectNode, openGroupOf, setFocus, focusParts, applyFocusView, updateFilterBar, renderReqs,
    linkOf: (key) => DG_LINKS.find(l => linkKey(l) === key),
    note(html) { if (html) { $("note").innerHTML = html; $("note").classList.add("show"); } else $("note").classList.remove("show"); },
  });
  Object.defineProperty(Page, "focus", { get: () => focus });
  Object.defineProperty(Page, "selReq", { get: () => selReq, set: (v) => { selReq = v; } });
  Object.defineProperty(Page, "tab", { get: () => activeTab });
  // the components: each adds its meshes, tab, stage panel and handlers once the core is built
  for (const c of Page.comps) if (c.init) { try { c.init(Page); } catch (e) { console.error(c.id, e); } }
  renderTabs();
  renderReqs(); renderTree(); renderInterfaces(); renderAssumptions(); renderDiagram(); updateFilterBar();
  for (const c of Page.comps) if (c.render) { try { c.render(); } catch (e) { console.error(c.id, e); } }
  applyPose(); local.updateMatrixWorld(true); fitViews();
  if (V.floor) makeFloor(V.floor);
  Object.keys(VIEWS).forEach(k => { const b = document.createElement("button"); b.type = "button"; b.id = "v-" + k; b.textContent = VIEWS[k].label || k[0].toUpperCase() + k.slice(1); b.onclick = () => setView(k); $("viewbar").insertBefore(b, $("v-clear")); });
  themeColours(); resize(); setView(Object.keys(VIEWS)[0]); applyPose();
  requestAnimationFrame(frame);
  }
})();
