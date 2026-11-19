// build.js: the Build tab of the assembly-procedure skill, a component of the page framework (core.js).
// It plays the build back in the 3D view: each step's parts arrive along their approach path, bench-built units
// wait at their staging offset and are then fitted, fasteners drive in. A requirement whose V.viz entry has
// build: true opens at the step its worst case names ("S12 ..."). Data in viewer_data.json:
//   V.assembly = {pose: [...], stage: {unit: [dx, dy, dz]}, units: {unit: [parts]},
//                 steps: [{id, title, phase, text, adds: [mesh names], tools: [...], fixture, why, pose,
//                          path: [[dir, mm, "local" | "world"], ...]   the approach of the step's parts, last leg seats them
//                          legs_of: {part: path}                      a part with its own approach
//                          unit: name    built on the bench, staged at stage[unit]; moves: unit   fits that unit
//                          lift: {what, kg, how, force}, fasteners: [{n, label, tool, torque}], welds: [{a, b, how}]}]}
//   V.fasteners = [{name, step, type: SHCS | HEX | CSK | SET | WOOD | TEK | ROD, d, L, head: [D, k], nut: [s, m, z] | null,
//                   pts: [[x, y, z]], dir: [x, y, z], group, label, ok, draw}]   drawn instanced, one mesh per joint
(function () {
  const comp = { id: "build", tab: "Build", pane: "p-asm", tabId: "t-asm", after: "p-req", drives: true };
  Page.component(comp);
  Page.style(`
.asm-bar { position: sticky; top: 0; z-index: 2; background: var(--panel); border-bottom: 1px solid var(--line); padding: 8px 14px; display: grid; gap: 6px; }
.asm-bar .row2 { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; font-size: 12px; color: var(--muted); }
.asm-bar button { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 3px 10px; cursor: pointer; font-size: 12px; }
.asm-bar button:hover { border-color: var(--accent); color: var(--accent); }
.asm-bar input[type=range] { width: 100%; accent-color: var(--accent); }
.step { border-bottom: 1px solid var(--line); padding: 8px 14px 8px 12px; border-left: 3px solid transparent; cursor: pointer; display: grid; grid-template-columns: 38px 1fr; gap: 2px 8px; }
.step:hover { background: color-mix(in srgb, var(--accent-soft) 55%, transparent); }
.step.sel { background: var(--accent-soft); border-left-color: var(--accent); }
.step.done { opacity: .62; }
.step .id { font: 500 12px var(--font-mono); color: var(--muted); padding-top: 2px; }
.step .t { font-size: 13.5px; font-weight: 500; }
.step .meta { grid-column: 2; display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; font-size: 12px; color: var(--muted); }
.step .body { grid-column: 2; font-size: 13px; display: none; }
.step.sel .body { display: block; }
.step .body dl { margin: 6px 0 2px; display: grid; grid-template-columns: 74px 1fr; gap: 3px 8px; font-size: 12px; }
.step .body dt { color: var(--muted); }
.step .body dd { margin: 0; }
.step[hidden], .section-h[hidden] { display: none; }
.step { scroll-margin-top: 84px; }
`);
  comp.init = function (P) {
  const { V, S, THREE, $, fmt, meshes, scene, local, groupObj, accent, clearAnnot, highlight, animateTo, showTab, nodeOfPart } = P;
  function mergeGeos(gs) {
    let n = 0; gs.forEach(g => { n += g.attributes.position.count; });
    const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3);
    let o = 0;
    for (const g of gs) { pos.set(g.attributes.position.array, o * 3); nor.set(g.attributes.normal.array, o * 3); o += g.attributes.position.count; }
    const m = new THREE.BufferGeometry();
    m.setAttribute("position", new THREE.BufferAttribute(pos, 3)); m.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
    return m;
  }
  // ---- fasteners: one instanced mesh per joint, built from catalogue sizes
  function fastenerGeo(F) {
    const d = F.d, L = F.L, parts = [];
    const cylZ = (r, z0, z1, seg) => { const g = new THREE.CylinderGeometry(r, r, z1 - z0, seg || 14); g.rotateX(Math.PI / 2); g.translate(0, 0, (z0 + z1) / 2); return g.toNonIndexed(); };
    const coneZ = (r0, r1, z0, z1) => { const g = new THREE.CylinderGeometry(r1, r0, z1 - z0, 14); g.rotateX(Math.PI / 2); g.translate(0, 0, (z0 + z1) / 2); return g.toNonIndexed(); };
    if (F.type === "SET") parts.push(cylZ(d / 2 - 0.1, 0, L));
    else parts.push(cylZ(d / 2 - 0.1, 0, L));
    if (F.type === "SHCS") parts.push(cylZ(F.head[0] / 2, -F.head[1], 0, 16));
    if (F.type === "HEX") parts.push(cylZ(F.head[0] / 2, -F.head[1], 0, 6));
    if (F.type === "ROD") parts.push(cylZ(F.head[0] / 2, -F.head[1], 0, 6));
    if (["CSK", "WOOD", "TEK"].includes(F.type)) parts.push(coneZ(d, d / 2, 0, 0.55 * d));
    if (F.nut) parts.push(cylZ(F.nut[0] / 2, F.nut[2], F.nut[2] + F.nut[1], 6));
    parts.forEach(g => g.computeVertexNormals());
    return mergeGeos(parts);
  }
  const _M = new THREE.Matrix4();
  const fastObjs = [];
  const _q = new THREE.Quaternion(), _zA = new THREE.Vector3(0, 0, 1), _dv = new THREE.Vector3(), _one = new THREE.Vector3(1, 1, 1);
  for (const F of V.fasteners || []) {
    if (!F.draw || !F.L) continue;
    const geo = fastenerGeo(F);
    const col = F.type === "SHCS" || F.type === "SET" ? "#26282c" : ["TEK", "WOOD"].includes(F.type) ? "#b9a46a" : "#8d939b";
    const mat = new THREE.MeshStandardMaterial({ color: col, roughness: 0.45, metalness: 0.5, transparent: true, opacity: 1 });
    const im = new THREE.InstancedMesh(geo, mat, F.pts.length);
    im.frustumCulled = false;
    _dv.set(...F.dir).normalize(); _q.setFromUnitVectors(_zA, _dv);
    F.pts.forEach((p, i) => { _M.compose(new THREE.Vector3(...p), _q, _one); im.setMatrixAt(i, _M); });
    im.userData.name = "fastener:" + F.name; im.userData.base = F.pts.map(p => p.slice()); im.userData.F = F; im.userData.edges = null;
    groupObj(F.group).add(im);
    meshes["fastener:" + F.name] = im;
    V.parts["fastener:" + F.name] = { info: `${F.pts.length} x ${F.label}` + (F.ok ? "" : " (fails a check)"), kind: "bought" };
    fastObjs.push(im);
  }
  function shiftFastener(im, off) {
    const F = im.userData.F;
    _dv.set(...F.dir).normalize(); _q.setFromUnitVectors(_zA, _dv);
    F.pts.forEach((p, i) => { _M.compose(new THREE.Vector3(p[0] + off[0], p[1] + off[1], p[2] + off[2]), _q, _one); im.setMatrixAt(i, _M); });
    im.instanceMatrix.needsUpdate = true;
  }
  // ------------------------------------------------------------- the build: step-by-step playback
  const ASM = V.assembly || { steps: [], stage: {}, units: {} };
  const asmSteps = ASM.steps;
  const addedAt = {}, unitOf = {}, moveAt = {};
  asmSteps.forEach((st, i) => {
    st.adds.forEach(n => { addedAt[n] = i; if (st.unit) unitOf[n] = st.unit; });
    if (st.moves) moveAt[st.moves] = i;
  });
  const stepIdx = Object.fromEntries(asmSteps.map((s, i) => [s.id, i]));
  for (const F of V.fasteners || []) {
    const n = "fastener:" + F.name;
    if (!meshes[n]) continue;
    addedAt[n] = stepIdx[F.step];
    const st = asmSteps[stepIdx[F.step]];
    if (st && st.unit) unitOf[n] = st.unit;
  }
  for (const m of Object.values(meshes)) if (m.matrixAutoUpdate === false) m.userData.loc0 = m.matrix.clone();
  const _off = new THREE.Vector3(), _T = new THREE.Matrix4();
  const _qInv = local.quaternion.clone().invert();
  function setOffset(name, v, frame) {
    const m = meshes[name]; if (!m) return;
    _off.set(v[0], v[1], v[2]);
    if (frame === "world" && m.parent !== scene) _off.applyQuaternion(_qInv);
    if (frame !== "world" && m.parent === scene) _off.applyQuaternion(local.quaternion);
    if (m.userData.loc0) { _T.makeTranslation(_off.x, _off.y, _off.z); m.matrix.copy(_T).multiply(m.userData.loc0); }
    else m.position.copy(_off);
  }
  const lerp3 = (a, b, t) => [0, 1, 2].map(i => a[i] + (b[i] - a[i]) * t);
  const scale3 = (a, s) => a.map(v => v * s);
  let building = false, stepIx = 0, buildT = 1, buildAnim = null, playing = null;
  function caseStatus(st) {
    const out = [];
    for (const r of S.results) for (const c of r.cases || []) if (c.case && c.case.startsWith(st.id + " ")) out.push({ req: r.requirement, ...c });
    return out;
  }
  // a path: legs [[dir, dist, frame]]; the offset from the seated position at fraction t of the way along
  function legOffset(legs, t) {
    if (!legs) return [[0, 0, 0], "local"];
    const vs = legs.map(l => scale3(l[0], l[1]));
    const total = legs.reduce((a, l) => a + l[1], 0) || 1;
    let s = t * total, cur = [0, 0, 0];
    vs.forEach(v => { cur = cur.map((c, i) => c - v[i]); });
    for (let j = 0; j < legs.length; j++) {
      const f = Math.min(1, s / (legs[j][1] || 1));
      cur = cur.map((c, i) => c + vs[j][i] * Math.max(0, f));
      s -= legs[j][1];
      if (s <= 0) break;
    }
    return [cur, legs[0][2] || "local"];
  }
  function drawBuild() {
    const k = stepIx, st = asmSteps[k], e = buildT < .5 ? 2 * buildT * buildT : 1 - Math.pow(-2 * buildT + 2, 2) / 2;
    const unitLegs = st.path || [[[0, 0, 1], 150, "local"]];
    const approach = legOffset(unitLegs, 0)[0];
    const col = accent().multiplyScalar(0.3);
    for (const [n, m] of Object.entries(meshes)) {
      const a = addedAt[n], u = unitOf[n], mv = u ? moveAt[u] : undefined;
      m.visible = a !== undefined && a <= k;
      if (!m.visible) continue;
      let off = [0, 0, 0], frame = "local";
      const staged = u && (mv === undefined || mv > k);
      if (staged) off = ASM.stage[u] || [0, 0, 1000];
      if (a === k) {
        if (staged) off = lerp3([off[0], off[1], off[2] + 200], off, e);
        else if (st.legs_of && n in st.legs_of) { [off, frame] = legOffset(st.legs_of[n], e); }
        else if (!n.startsWith("fastener:")) { [off, frame] = legOffset(unitLegs, e); }
      }
      if (u && mv === k) off = e < .5 ? lerp3(ASM.stage[u] || [0, 0, 0], approach, e * 2) : legOffset(unitLegs, (e - .5) * 2)[0];
      if (n.startsWith("fastener:") && a === k && !staged) {
        const F = m.userData.F, s = (1 - e) * 40;
        off = [-F.dir[0] * s, -F.dir[1] * s, -F.dir[2] * s];
      }
      if (n.startsWith("fastener:")) shiftFastener(m, off); else setOffset(n, off, frame);
      const now = a === k || (u && mv === k);
      m.material.opacity = 1; m.material.depthWrite = true;
      m.material.emissive = now ? col : new THREE.Color(0);
      if (m.userData.edges) m.userData.edges.material.opacity = 0.25;
    }
  }
  function enterBuild() {
    if (building) return;
    building = true; P.driver = "build"; clearAnnot(); P.selReq = null;
    document.querySelectorAll(".req").forEach(el => el.classList.remove("sel"));
    goStep(stepIx, false);
  }
  function exitBuild() {
    if (!building) return;
    building = false; P.driver = null; stopPlay(); buildAnim = null;
    for (const n of Object.keys(meshes)) { meshes[n].visible = true; if (n.startsWith("fastener:")) shiftFastener(meshes[n], [0, 0, 0]); else setOffset(n, [0, 0, 0]); }
    highlight(null); P.note(null);
  }
  function goStep(i, animate = true) {
    stepIx = Math.max(0, Math.min(asmSteps.length - 1, i));
    const st = asmSteps[stepIx];
    const p = st.pose || ASM.pose;
    animateTo(p, animate ? 700 : 1);
    const t0 = performance.now(), ms = st.moves ? 2200 : 1300;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    buildT = animate && !reduce ? 0 : 1;
    buildAnim = buildT < 1 ? (now) => { buildT = Math.min(1, (now - t0) / ms); drawBuild(); if (buildT >= 1) buildAnim = null; } : null;
    drawBuild();
    $("asm-slider").value = stepIx;
    $("asm-pos").textContent = `Step ${stepIx + 1} of ${asmSteps.length}`;
    document.querySelectorAll(".step").forEach(el => {
      const j = +el.dataset.ix;
      el.classList.toggle("sel", j === stepIx); el.classList.toggle("done", j < stepIx);
    });
    $("step-" + stepIx)?.scrollIntoView({ block: "nearest", behavior: animate ? "smooth" : "auto" });
    const lift = st.lift ? ` · heaviest: ${st.lift.what}, ${st.lift.kg} kg ${st.lift.how} (${st.lift.force} kg each)` : "";
    P.note(`<b>${st.id}</b> ${st.title}<br><span style="color:var(--muted)">${st.phase}${lift}</span>`);
  }
  function stopPlay() { if (playing) { clearTimeout(playing); playing = null; } $("asm-play").textContent = "Play"; }
  function play() {
    if (playing) { stopPlay(); return; }
    $("asm-play").textContent = "Pause";
    const tick = () => {
      if (stepIx >= asmSteps.length - 1) { stopPlay(); return; }
      goStep(stepIx + 1);
      playing = setTimeout(tick, asmSteps[stepIx].moves ? 3200 : 2300);
    };
    if (stepIx >= asmSteps.length - 1) goStep(0);
    playing = setTimeout(tick, 900);
  }
  const unitOfReq = (id) => { const u = (P.reqs.find(r => r.id === id) || {}).unit; return u && u !== "mm^3" ? u : ""; };
  function renderBuild() {
    let html = `<div class="asm-bar"><div class="row2"><button type="button" id="asm-prev">Previous</button><button type="button" id="asm-play">Play</button>
      <button type="button" id="asm-next">Next</button><span id="asm-pos"></span><button type="button" id="asm-exit" style="margin-left:auto">Show finished machine</button></div>
      <input id="asm-slider" type="range" min="0" max="${asmSteps.length - 1}" step="1" value="0" aria-label="Build step"></div>`;
    let ph = null;
    asmSteps.forEach((st, i) => {
      if (st.phase !== ph) { ph = st.phase; html += `<div class="section-h">${ph}</div>`; }
      const cs = caseStatus(st);
      const worst = cs.some(c => c.status === "fail") ? "fail" : cs.length ? "pass" : null;
      const pills = (worst ? `<span class="pill ${worst}">${worst === "fail" ? "Fails a check" : cs.length + (cs.length > 1 ? " checks pass" : " check passes")}</span>` : "") +
        (st.lift ? `<span>${st.lift.force} kg each · ${st.lift.how}</span>` : "") +
        (st.adds.length ? `<span>${st.adds.length} part${st.adds.length > 1 ? "s" : ""}</span>` : "") +
        ((st.fasteners || []).length ? `<span>${st.fasteners.reduce((a, f) => a + f.n, 0)} fasteners</span>` : "") +
        ((st.welds || []).length ? `<span>${st.welds.length} weld${st.welds.length > 1 ? "s" : ""}</span>` : "") +
        (st.moves ? `<span>fits the ${st.moves.replace(/_/g, " ")}</span>` : "") +
        (st.unit ? `<span>on the bench</span>` : "");
      const checks = cs.map(c => `<div><span class="pill ${c.status}">${c.req}</span> ${c.case.slice(st.id.length + 1)}${unitOfReq(c.req) && c.measured != null ? `: <span class="num">${fmt(c.measured)} ${unitOfReq(c.req)}</span>` : ""}</div>`).join("");
      html += `<div class="step" id="step-${i}" data-ix="${i}" tabindex="0"><div class="id">${st.id}</div><div class="t">${st.title}</div>
        <div class="meta">${pills}</div>
        <div class="body"><p style="margin:6px 0">${st.text}</p><dl>
          ${st.tools.length ? `<dt>Tools</dt><dd>${st.tools.join(", ")}</dd>` : ""}
          ${st.fixture ? `<dt>Temporary</dt><dd>${st.fixture}</dd>` : ""}
          ${st.why ? `<dt>Why</dt><dd>${st.why}</dd>` : ""}
          ${(st.fasteners || []).length ? `<dt>Fasteners</dt><dd>${st.fasteners.map(f => `${f.n} × ${f.label} — ${f.tool}${f.torque ? `, ${f.torque} N·m` : ""}`).join("<br>")}</dd>` : ""}
          ${(st.welds || []).length ? `<dt>Welds</dt><dd>${st.welds.map(w => `${w.a.split(".").pop()} to ${w.b.split(".").pop()}: ${w.how}`).join("<br>")}</dd>` : ""}
          ${st.adds.length ? `<dt>Parts</dt><dd>${st.adds.join(", ")}</dd>` : ""}
          ${st.moves ? `<dt>Fits</dt><dd>the ${st.moves.replace(/_/g, " ")} built in ${asmSteps.filter(s => s.unit === st.moves).map(s => s.id).join(", ")}</dd>` : ""}
          ${checks ? `<dt>Checks</dt><dd>${checks}</dd>` : ""}
        </dl></div></div>`;
    });
    $("p-asm").innerHTML = html;
    $("asm-prev").onclick = () => { stopPlay(); goStep(stepIx - 1); };
    $("asm-next").onclick = () => { stopPlay(); goStep(stepIx + 1); };
    $("asm-play").onclick = play;
    $("asm-exit").onclick = () => { exitBuild(); showTab("p-req"); };
    $("asm-slider").addEventListener("input", e => { stopPlay(); goStep(+e.target.value, false); });
    $("p-asm").querySelectorAll(".step").forEach(el => {
      el.addEventListener("click", () => { stopPlay(); goStep(+el.dataset.ix); });
      el.addEventListener("keydown", e => { if (e.key === "Enter") { stopPlay(); goStep(+el.dataset.ix); } });
    });
  }
  const stepNodes = asmSteps.map(st => new Set([...st.adds, ...(st.welds || []).flatMap(w => [w.a, w.b]), ...Object.keys(st.legs_of || {})].map(nodeOfPart).filter(Boolean)));
  // fitting a bench-built unit touches every block the unit was built from
  asmSteps.forEach((st, i) => { if (st.moves) asmSteps.forEach((u, j) => { if (u.unit === st.moves) stepNodes[j].forEach(n => stepNodes[i].add(n)); }); });
  // the build step a P.focus stands for: a block's first step; a line's first step that joins both ends,
  // else the step where the later of the two first appears
  function focusStep(f) {
    if (!f || !f.nodes.size) return -1;
    const ns = [...f.nodes], touches = (i, n) => stepNodes[i].has(n);
    if (f.sel.type === "link" && ns.length === 2) {
      // a mechanical joint is made when the later block arrives; cables and hoses when a step works on both ends
      const L = P.linkOf(f.sel.key);
      const later = Math.max(...ns.map(n => asmSteps.findIndex((_, i) => touches(i, n))));
      if (L && L.kinds.has("mechanical")) return later;
      const both = asmSteps.findIndex((_, i) => ns.every(n => touches(i, n)));
      return both >= 0 ? both : later;
    }
    return asmSteps.findIndex((_, i) => ns.some(n => touches(i, n)));
  }
  function buildToFocus() {
    const j = focusStep(P.focus);
    if (j < 0) return;
    if (j !== stepIx) { stopPlay(); goStep(j); }
  }
  function filterBuild() {
    let lastH = null, any = false;
    const hs = [];
    $("p-asm").querySelectorAll(".section-h, .step").forEach(el => {
      if (el.classList.contains("section-h")) { if (lastH) lastH.hidden = !any; lastH = el; any = false; return; }
      const ok = !P.focus || [...P.focus.nodes].some(x => stepNodes[+el.dataset.ix].has(x));
      el.hidden = !ok; if (ok) any = true;
    });
    if (lastH) lastH.hidden = !any;
  }


  Object.assign(comp, {
    render: renderBuild,
    enter() { enterBuild(); if (P.focus) buildToFocus(); },
    exit() { exitBuild(); P.applyFocusView(); },
    claimsReq: (id) => !!(V.viz[id] && V.viz[id].build) && asmSteps.length > 0,
    focusReq(id) {
      const c = (P.res[id] || {}).case || "";
      const j = asmSteps.findIndex(s => c.startsWith(s.id + " "));
      if (j >= 0) goStep(j);
    },
    filterLabel(f) { const k = stepNodes.filter(s => [...f.nodes].some(x => s.has(x))).length; return `${k} of ${asmSteps.length} build steps`; },
  });
  P.on("focus", () => { filterBuild(); if (building && P.focus) buildToFocus(); });
  P.on("frame", (now) => { if (buildAnim) buildAnim(now); });
  P.shiftFastener = shiftFastener;
  };
})();
