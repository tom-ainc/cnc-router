// sim-ui.js: the Simulation tab of the systems-simulation skill, a component of the page framework (core.js).
// Simulink-style diagrams under the 3D view, scopes and measures in the tab, and the 3D view driven by the run.
// It is the same for every project. The project's model (sim.js) and its page config (sim-page.js), loaded before it, supply:
//   SIMMODEL.build(P), jobs(P), Run(P, job, {feed, acc, custom, start}), Meter(P), measure(M, meter, P)
//   SIMMODEL.ui(P): {summary, pose: {keys, ref, act, scale}, cutting(M), jog, scopes, scopesOn, firstJob,
//                    measures(job, r, full, V.sim), trust(V.sim.verify), focusReq(id, V.sim.results)}
// and viewer_data.json carries V.sim {params, results, verify, digest}. A requirement whose V.viz entry has sim: true
// opens here, at the job and moment its worst case happens.
(function () {
  const comp = { id: "sim", tab: "Simulation", pane: "p-sim", tabId: "t-sim",
    stage: `<div class="sim-diag" id="sim-diag" aria-label="Simulation block diagram">
      <div class="sd-crumb" id="sd-crumb"></div><div class="sd-wrap" id="sd-wrap"></div>
      <div class="sd-hint">Click a block to show its scopes; double-click a heavy-bordered block to open it. Click a wire to plot it in the probe scope. Scroll to zoom, drag to pan, double-click the background to fit.</div>
    </div>` };
  Page.component(comp);
  Page.style(`
.sim-diag { display: none; }
body.sim-mode .sim-diag { display: flex; flex-direction: column; height: 42vh; min-height: 260px; border-top: 1px solid var(--line); background: var(--panel); }
.sim-diag .sd-wrap { flex: 1; min-height: 0; }
.scope-sel { padding: 6px 12px; font-size: 12px; color: var(--muted); background: var(--accent-soft); border-bottom: 1px solid var(--line); }
.scope-sel button { background: none; border: 0; padding: 0; font: inherit; margin-left: 6px; }
.scope-sel[hidden], .scope-pick[hidden] { display: none; }
#sd-svg .sblk.sel .sb { stroke: var(--accent); stroke-width: 2.6; }
#sd-svg .sblk:not(.open) { cursor: pointer; }
.scopes { display: grid; grid-template-columns: minmax(0, 1fr); grid-auto-rows: 200px; gap: 1px; background: var(--line); border-bottom: 1px solid var(--line); }
body.sim-mode .ctl, body.sim-mode .stats { display: none; }
.scope-pick { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 12px; border-bottom: 1px solid var(--line); font-size: 11px; }
.scope-pick label { display: inline-flex; align-items: center; gap: 3px; padding: 1px 7px 1px 4px; border: 1px solid var(--line); border-radius: 999px; cursor: pointer; color: var(--muted); }
.scope-pick label.on { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
.scope-pick input { margin: 0; accent-color: var(--accent); }
.scope { background: var(--panel); display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.sc-h { display: flex; gap: 8px; align-items: baseline; padding: 3px 8px 0; font-size: 11px; color: var(--muted); white-space: nowrap; overflow: hidden; }
.sc-h b { font: 600 12px var(--font-display); color: var(--ink); }
.sc-k { margin-left: auto; display: flex; gap: 8px; font-weight: 500; overflow: hidden; }
.scope canvas { flex: 1; min-height: 0; width: 100%; display: block; }
.sim-bar { position: sticky; top: 0; z-index: 2; background: var(--panel); border-bottom: 1px solid var(--line); padding: 8px 12px; display: grid; gap: 6px; font-size: 12px; color: var(--muted); }
.sim-bar .row2 { display: flex; gap: 6px 10px; align-items: center; flex-wrap: wrap; }
.sim-bar button, .sim-bar select { font: inherit; font-size: 12px; color: var(--ink); background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 2px 8px; cursor: pointer; }
.sim-bar button:hover { border-color: var(--accent); color: var(--accent); }
.sim-bar #sim-play { background: var(--accent); color: #fff; border-color: var(--accent); min-width: 72px; }
.sim-bar label { display: inline-flex; gap: 4px; align-items: center; }
.sim-bar input[type=range] { width: 80px; accent-color: var(--accent); }
.sim-bar .jog button { padding: 1px 7px; font-family: var(--font-mono); }
.sim-bar .jog button:disabled { opacity: .45; cursor: default; color: var(--muted); border-color: var(--line); }
.sim-bar .vals { margin-left: auto; }
#sim-t.buf { color: var(--open); }
.sim-note { font-size: 12px; color: var(--muted); }
.sd-crumb { padding: 6px 12px 0; font-size: 12px; color: var(--muted); display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.sd-crumb button { background: none; border: 0; padding: 0; font: inherit; }
.sd-crumb b { color: var(--ink); font-family: var(--font-display); }
.sd-wrap { padding: 4px 6px; }
#sd-svg { width: 100%; height: 100%; display: block; background: color-mix(in srgb, var(--bg) 55%, var(--panel)); border: 1px solid var(--line); border-radius: 6px; cursor: grab; font-family: var(--font-body); user-select: none; touch-action: none; }
#sd-svg .sb { fill: var(--panel); stroke: var(--ink); stroke-width: 1.1; }
#sd-svg .sb.sub { stroke-width: 2.2; }
#sd-svg .sblk.open { cursor: pointer; }
#sd-svg .sblk.open:hover .sb, #sd-svg .sblk.open:focus .sb { stroke: var(--accent); fill: var(--accent-soft); }
#sd-svg .sblk.on .sb { fill: var(--fail-bg); stroke: var(--fail); }
#sd-svg .sl { fill: none; stroke: var(--ink); stroke-width: 1.1; }
#sd-svg .scr { fill: var(--bg); stroke: var(--muted); }
#sd-svg .st { font-size: 10px; fill: var(--ink); }
#sd-svg .st.c { text-anchor: middle; }
#sd-svg .st.bold { font-weight: 600; font-size: 10.5px; }
#sd-svg .st.sm { font-size: 8.5px; fill: var(--muted); }
#sd-svg .st.live { fill: var(--accent); font-family: var(--font-mono); }
#sd-svg .st.sg { font-size: 9px; font-family: var(--font-mono); }
#sd-svg .st.pl { font-size: 8px; fill: var(--muted); }
#sd-svg .st.pr { font-size: 8px; fill: var(--muted); text-anchor: end; }
#sd-svg .st.val { font-size: 8.5px; font-family: var(--font-mono); fill: var(--accent); }
#sd-svg .sp rect { fill: var(--panel); stroke: var(--ink); }
#sd-svg .sp.out rect { fill: var(--bg); }
#sd-svg .sw { cursor: pointer; }
#sd-svg .sw .hit { fill: none; stroke: transparent; stroke-width: 9; }
#sd-svg .sw .ln { fill: none; stroke: var(--muted); stroke-width: 1.1; }
#sd-svg .sw:hover .ln { stroke: var(--accent); stroke-width: 1.8; }
#sd-svg .sw.pr .ln { stroke: var(--accent); stroke-width: 2.2; }
#sd-svg .arr { fill: var(--muted); }
.sd-hint { padding: 0 12px 4px; font-size: 11px; color: var(--muted); }
.sim-meas table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sim-meas th { text-align: left; font-weight: 500; color: var(--muted); padding: 4px 8px; border-bottom: 1px solid var(--line); }
.sim-meas td { padding: 4px 8px; border-bottom: 1px solid var(--line); }
.sim-meas td.num { text-align: right; font-family: var(--font-mono); white-space: nowrap; }
.sim-meas .muted { color: var(--muted); font-size: 11.5px; }
.sim-meas table.sens td:first-child { width: 38%; }
.sim-foot { padding: 6px 12px 12px; font-size: 11px; color: var(--muted); }
`);
  comp.init = function (P) {
  const { V, THREE, $, css, store, status, local, pose, applyPose, highlight, clearAnnot, showTab, openGroupOf } = P;
  // ------------------------------------------------------------- simulation: Simulink-style diagrams, scopes, and the 3D view, all driven by one run
  const MODEL = window.SIMMODEL || window.CNCSIM;
  const SIMP = MODEL && V.sim && V.sim.params, SIMRES = V.sim && V.sim.results;
  const SIM_JOBS = SIMP ? MODEL.jobs(SIMP) : {};
  const U = SIMP && MODEL.ui ? MODEL.ui(SIMP) : {};
  const UP = U.pose || { keys: [], ref: [], act: [], scale: 1 };
  let SR = null, simOn = false, simRun = false, simSpeed = 1, simDiag = "top", simJob = U.firstJob || Object.keys(SIM_JOBS)[0], simErr = 1, simWin = 20;
  let simTOff = 0, simLastReal = 0, simMeter = null, simSeeking = false, simShowVals = false;
  const simProbe = [];
  let simFeed = 1, simAcc = 1;
  const fmtSig = (v, u) => {
    if (!isFinite(v)) return "–";
    if (u === "m") return (v * 1000).toFixed(2) + " mm";
    if (u === "m/s") return (v * 1000).toFixed(1) + " mm/s";
    const a = Math.abs(v), s = a >= 1000 ? v.toFixed(0) : a >= 100 ? v.toFixed(1) : a >= 1 ? v.toFixed(2) : a >= 0.01 ? v.toFixed(3) : v.toExponential(1);
    return s + (u ? " " + u : "");
  };
  const sigScale = (u) => u === "m" ? 1000 : u === "m/s" ? 1000 : 1;
  const sigUnit = (u) => u === "m" ? "mm" : u === "m/s" ? "mm/s" : u;

  // ---- recording: every signal, min and max per 10 ms, so a wire probed after the fact still has its history
  const REC = { dt: 0.01, n: 0, cap: 0, ns: 0 };
  function recReset(ns) {
    REC.ns = ns; REC.n = 0; REC.cap = 8192;
    REC.min = new Float32Array(REC.cap * ns); REC.max = new Float32Array(REC.cap * ns); REC.t = new Float64Array(REC.cap);
    REC.bmin = new Float64Array(ns).fill(Infinity); REC.bmax = new Float64Array(ns).fill(-Infinity); REC.next = REC.dt;
  }
  function recStep(v, t) {
    const bmin = REC.bmin, bmax = REC.bmax, ns = REC.ns;
    for (let i = 0; i < ns; i++) { const x = v[i]; if (x < bmin[i]) bmin[i] = x; if (x > bmax[i]) bmax[i] = x; }
    if (t < REC.next) return;
    if (REC.n >= REC.cap) {
      const c2 = REC.cap * 2, mn = new Float32Array(c2 * ns), mx = new Float32Array(c2 * ns), tt = new Float64Array(c2);
      mn.set(REC.min); mx.set(REC.max); tt.set(REC.t); REC.min = mn; REC.max = mx; REC.t = tt; REC.cap = c2;
    }
    const o = REC.n * ns;
    for (let i = 0; i < ns; i++) { REC.min[o + i] = bmin[i]; REC.max[o + i] = bmax[i]; bmin[i] = Infinity; bmax[i] = -Infinity; }
    REC.t[REC.n++] = t; REC.next = t + REC.dt;
  }

  // ---- the path in 3D: what the program asks for (faint) and where the tool tip went (cutting moves bright)
  const trace = { max: 60000 };
  function traceLines() {
    const mk = (col, op, dashed) => {
      const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(trace.max * 6), 3)); g.setDrawRange(0, 0);
      const m = dashed ? new THREE.LineDashedMaterial({ color: col, transparent: true, opacity: op, dashSize: 12, gapSize: 8, depthTest: false })
                       : new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: op, depthTest: false });
      const L = new THREE.LineSegments(g, m); L.renderOrder = 998; L.frustumCulled = false; L.visible = false; local.add(L); return L;
    };
    trace.cut = mk("#d0402b", 1); trace.move = mk("#4b5560", 0.7); trace.plan = mk("#1f6fb2", 0.35);
    trace.n = { cut: 0, move: 0 }; trace.tt = { cut: new Float64Array(trace.max), move: new Float64Array(trace.max) };
  }
  function tracePush(kind, a, b, t) {
    const L = trace[kind], n = trace.n[kind]; if (n >= trace.max) return;
    const arr = L.geometry.attributes.position.array, o = n * 6;
    arr[o] = a[0]; arr[o + 1] = a[1]; arr[o + 2] = a[2]; arr[o + 3] = b[0]; arr[o + 4] = b[1]; arr[o + 5] = b[2];
    trace.tt[kind][n] = t; trace.n[kind] = n + 1; L.geometry.attributes.position.needsUpdate = true;
  }
  function traceShowTo(t) {                     // draw the track up to the playback time
    for (const k of ["cut", "move"]) {
      const tt = trace.tt[k]; let lo = 0, hi = trace.n[k];
      while (lo < hi) { const m = (lo + hi) >> 1; if (tt[m] <= t) lo = m + 1; else hi = m; }
      trace[k].geometry.setDrawRange(0, lo * 2);
    }
  }
  function traceReset(plan) {
    for (const k of ["cut", "move"]) { trace.n[k] = 0; trace[k].geometry.setDrawRange(0, 0); }
    const segs = plan.segs.filter(s => s.L), arr = trace.plan.geometry.attributes.position.array;
    let n = 0;
    for (const s of segs) { if (n >= trace.max) break; arr.set([...s.p0, ...s.p1], n * 6); n++; }
    trace.plan.geometry.setDrawRange(0, n * 2); trace.plan.geometry.attributes.position.needsUpdate = true;
    trace.last = null;
  }
  const traceShow = (on) => ["cut", "move", "plan"].forEach(k => { if (trace[k]) trace[k].visible = on; });

  // ---- a run
  function simLoad(job, opt) {
    opt = opt || {};
    if (!SIMP) return;
    simJob = job || simJob; simRun = false; simSeeking = false; simBuffering = false; simJog = null;
    const P = JSON.parse(JSON.stringify(SIMP));
    SR = MODEL.Run(P, opt.custom ? null : simJob, { feed: simFeed, acc: simAcc, custom: opt.custom, start: opt.start });
    SR.P = P; SR.start = (opt.start || (U.jog || {}).start || []).slice();
    if (!opt.keep) { recReset(SR.M.names.length); simTOff = 0; simTp = 0; simMeter = MODEL.Meter(P); traceReset(SR.M.planner.plan); }
    else { simTOff = REC.n ? REC.t[REC.n - 1] : 0; REC.next = simTOff + REC.dt; traceAppendPlan(SR.M.planner.plan); }
    SR.M.step();
    simUI(); simPose(true);
  }
  function traceAppendPlan(plan) {
    const arr = trace.plan.geometry.attributes.position.array;
    let n = trace.plan.geometry.drawRange.count / 2;
    for (const s of plan.segs.filter(s => s.L)) { if (n >= trace.max) break; arr.set([...s.p0, ...s.p1], n * 6); n++; }
    trace.plan.geometry.setDrawRange(0, n * 2); trace.plan.geometry.attributes.position.needsUpdate = true;
  }
  // the computation runs ahead of the playback into the recording; playback starts (and resumes) only once the
  // computation can stay ahead of it to the end of the job at the chosen speed
  let simJog = null;
  let simTp = 0, simBuffering = false, simCs = 0, simFrameMs = 16, simFrames = 0;
  const PLAY_MS = 12, BUF_MS = 30;                    // computing per frame while playing, and while waiting
  const tcNow = () => SR ? SR.M.t + simTOff : 0, tEnd = () => SR ? SR.T + simTOff : 0, simDone = () => SR && SR.M.t >= SR.T - 1e-9;
  function simCompute(ms) {
    if (!SR || simDone()) return;
    const M = SR.M, P = SR.P, t0 = performance.now(), m0 = M.t;
    while (M.t < SR.T) {
      for (let i = 0; i < 50 && M.t < SR.T; i++) { M.step(); MODEL.measure(M, simMeter, P); recStep(M.v, M.t + simTOff); traceStep(M); }
      if (performance.now() - t0 > ms) break;
    }
    const el = performance.now() - t0;
    if (el > 1) simCs = simCs ? 0.85 * simCs + 0.15 * (M.t - m0) / el : (M.t - m0) / el;     // simulated s per ms of computing
  }
  const playRate = () => simCs * PLAY_MS / Math.max(simFrameMs, 16) * 1000;              // simulated s per real s, while playing
  function simReady() {
    if (simDone()) return true;
    if (simFrames < 10 || !simCs) return false;                                             // not measured yet
    const r = playRate(), tc = tcNow(), T = tEnd();
    if (tc - simTp < Math.min(0.3 * simSpeed, T - simTp)) return false;                    // a little lead, for jitter
    return (T - tc) / Math.max(r, 1e-9) <= 0.85 * (T - simTp) / simSpeed;                   // it finishes before the playback catches up
  }
  function simWait() {                                                                        // seconds of real time until playback can start
    const r = playRate(), rb = simCs * BUF_MS / Math.max(simFrameMs, BUF_MS + 4) * 1000, T = tEnd();
    const need = T - 0.85 * r * (T - simTp) / simSpeed;
    return Math.max(0, (Math.max(need, simTp + 0.3 * simSpeed) - tcNow()) / Math.max(rb, 1e-9));
  }
  function simAdvance(dtReal) {
    if (!SR) return;
    if (dtReal > 0) { simFrameMs = simFrames ? 0.6 * simFrameMs + 0.4 * Math.min(1000, dtReal * 1000) : dtReal * 1000; simFrames++; }
    simCompute(simRun && !simBuffering ? PLAY_MS : BUF_MS);
    if (!simRun) return;
    if (simBuffering) { if (simReady()) simBuffering = false; else return; }
    simTp = Math.min(simTp + Math.min(dtReal, 0.5) * simSpeed, tcNow());
    if (simTp >= tEnd() - 1e-9) { simTp = tEnd(); simRun = false; simPose(true); simUI(); }     // the last frame: show where it ended
    else if (simTp >= tcNow() - 1e-9) { simBuffering = true; simUI(); }                    // it caught up: wait again
  }
  // a recorded value at the playback time (the middle of its 10 ms bucket's range)
  function recK(t) { let lo = 0, hi = REC.n - 1; if (hi < 0 || t < REC.t[0]) return -1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (REC.t[m] <= t) lo = m; else hi = m - 1; } return lo; }
  function recVal(k, i) { if (k < 0) return SR.M.v[i]; const o = k * REC.ns + i; return 0.5 * (REC.min[o] + REC.max[o]); }
  function traceStep(M) {
    if (!UP.act.length) return;
    const p = UP.act.map(n => M.v[M.index.get(n)] * UP.scale);
    const kind = U.cutting && U.cutting(M) ? "cut" : "move";
    if (!trace.last) { trace.last = p; trace.lastKind = kind; return; }
    const d = Math.hypot(p[0] - trace.last[0], p[1] - trace.last[1], p[2] - trace.last[2]);
    if (d > 0.6 || kind !== trace.lastKind) { tracePush(kind, trace.last, p, M.t + simTOff); trace.last = p; trace.lastKind = kind; }
  }
  // the machine in 3D where the model has it; errors can be magnified so a 50 µm wobble shows
  let simPoseTick = 0;
  function simPose(force) {
    if (!SR) return;
    if (!force && (++simPoseTick % 2)) return;
    const M = SR.M, kb = recK(simTp), ix = (n) => recVal(kb, M.index.get(n)), k = simErr;
    const r = UP.ref.map(ix), a = UP.act.map(ix);
    UP.keys.forEach((key, i) => { pose[key] = UP.scale * (r[i] + (a[i] - r[i]) * k); });
    applyPose(); traceShowTo(simTp);
  }
  function simSeek(t, then) {                           // compute ahead without drawing, then play from a moment worth looking at
    if (!SR) return;
    simSeeking = true; simRun = false;
    const target = Math.min(t, SR.T) + simTOff;
    const chunk = () => {
      if (!simSeeking) return;
      simCompute(40);
      $("sim-t").textContent = `computing ahead… ${tcNow().toFixed(1)} of ${target.toFixed(1)} s`;
      if (tcNow() < target && !simDone()) setTimeout(chunk, 0);
      else { simSeeking = false; simTp = target; simPose(true); simUI(); if (then) then(); }
    };
    chunk();
  }

  // ---- the diagrams: ports worked out from the wiring, as Simulink draws a subsystem
  let SD = null;            // the structure, from a model built once
  function sdBuild() {
    const M = MODEL.build(JSON.parse(JSON.stringify(SIMP)));
    const desc = {};
    const walk = (id) => { const sys = M.systems[id]; let bl = sys.blocks.filter(b => b.type !== "sub"); for (const c of sys.children) bl = bl.concat(walk(c)); desc[id] = bl; return bl; };
    walk("top");
    const consumers = {};
    for (const b of M.blocks) if (b.type !== "sub") b.in.forEach(s => (consumers[s] ||= []).push(b));
    const ports = {};
    for (const id of Object.keys(M.systems)) {
      const bl = desc[id], inside = new Set(bl), prod = new Set(), seen = new Set(), ins = [], outs = [];
      bl.forEach(b => { if (b.type !== "scope") b.out.forEach(s => prod.add(s)); });
      bl.forEach(b => b.in.forEach(s => { if (!prod.has(s) && !seen.has(s)) { seen.add(s); ins.push(s); } }));
      bl.forEach(b => { if (b.type === "scope") return; b.out.forEach(s => { if ((consumers[s] || []).some(c => !inside.has(c)) && !outs.includes(s)) outs.push(s); }); });
      ports[id] = { ins, outs };
    }
    SD = { M, ports };
  }
  const BSIZE = { gain: [40, 34], sum: [26, 26], prod: [28, 28], int: [36, 36], sat: [44, 36], lookup: [64, 40], const: [80, 30], fcn: [96, 44], src: [120, 60], scope: [70, 50], sub: [120, 64] };
  const short = (s) => s.split(".").slice(1).join(".") || s;
  function sdElements(sysId) {
    const sys = SD.M.systems[sysId], els = [];
    for (const b of sys.blocks) {
      const [w, h] = b.size || BSIZE[b.type] || [80, 40];
      let ins = b.in, outs = b.out;
      if (b.type === "sub") { ins = SD.ports[b.child].ins; outs = SD.ports[b.child].outs; }
      if (b.type === "scope") outs = [];
      els.push({ b, x: b.pos[0], y: b.pos[1], w, h: b.type === "sub" ? Math.max(h, 16 * Math.max(ins.length, outs.length) + 10) : h, ins, outs });
    }
    // inports at the left, beside their first user; outports at the right, beside their source
    const P = SD.ports[sysId];
    const portY = (el, s, side) => { const list = side === "in" ? el.ins : el.outs, i = list.indexOf(s); return el.y + el.h * (i + 1) / (list.length + 1); };
    if (sysId !== "top") {
      const inEls = P.ins.map(s => { const user = els.find(e => e.ins.includes(s)); return { port: "in", sig: s, x: 0, y: user ? portY(user, s, "in") - 9 : 20, w: 46, h: 18, ins: [], outs: [s] }; });
      inEls.sort((a, b) => a.y - b.y); for (let i = 1; i < inEls.length; i++) inEls[i].y = Math.max(inEls[i].y, inEls[i - 1].y + 22);
      const maxX = Math.max(...els.map(e => e.x + e.w)) + 50;
      const outEls = P.outs.map(s => { const src = els.find(e => e.outs.includes(s)); return { port: "out", sig: s, x: maxX, y: src ? portY(src, s, "out") - 9 : 20, w: 46, h: 18, ins: [s], outs: [] }; });
      outEls.sort((a, b) => a.y - b.y); for (let i = 1; i < outEls.length; i++) outEls[i].y = Math.max(outEls[i].y, outEls[i - 1].y + 22);
      els.push(...inEls, ...outEls);
      // inports sit left of everything
      const minX = Math.min(...els.filter(e => !e.port).map(e => e.x));
      inEls.forEach(e => { e.x = minX - 80; });
    }
    els.forEach(e => {
      e.pin = e.ins.map((s, i) => [e.x, e.y + e.h * (i + 1) / (e.ins.length + 1)]);
      e.pout = e.outs.map((s, i) => [e.x + e.w, e.y + e.h * (i + 1) / (e.outs.length + 1)]);
    });
    return els;
  }
  function sdWires(els) {
    const wires = [], lanes = {};
    const maxY = Math.max(...els.map(e => e.y + e.h));
    let lane = 0;
    for (const e of els) e.ins.forEach((s, i) => {
      const src = els.find(o => o.outs.includes(s)); if (!src) return;
      const [x1, y1] = src.pout[src.outs.indexOf(s)], [x2, y2] = e.pin[i];
      let d;
      if (x2 > x1 + 14) {
        const mx = Math.round(x1 + Math.max(8, Math.min(x2 - x1 - 8, (x2 - x1) / 2 + ((wires.length % 5) - 2) * 3)));
        d = `M${x1},${y1} H${mx} V${y2} H${x2}`;
      } else {                                     // feedback: round below the blocks
        const ly = (lanes[s] ??= maxY + 14 + 8 * (lane++ % 6));
        d = `M${x1},${y1} H${x1 + 10} V${ly} H${x2 - 12} V${y2} H${x2}`;
      }
      wires.push({ s, d, x1, y1 });
    });
    return wires;
  }
  const SUMMARY = U.summary || {};
  function sdIcon(e) {
    const b = e.b, x = e.x, y = e.y, w = e.w, h = e.h, cx = x + w / 2, cy = y + h / 2;
    switch (b.type) {
      case "gain": return `<polygon points="${x},${y} ${x},${y + h} ${x + w},${cy}" class="sb"/><text x="${x + w * 0.36}" y="${cy + 3.5}" class="st c">${b.label || fmtK(b.k)}</text>`;
      case "sum": return `<circle cx="${cx}" cy="${cy}" r="${w / 2}" class="sb"/>` + b.signs.split("").map((g, i) => { const py = y + h * (i + 1) / (b.signs.length + 1); return `<text x="${x + 6}" y="${py + 3}" class="st sg">${g}</text>`; }).join("") + `<text x="${cx + 3}" y="${cy + 4}" class="st c">Σ</text>`;
      case "prod": return `<circle cx="${cx}" cy="${cy}" r="${w / 2}" class="sb"/><text x="${cx}" y="${cy + 4}" class="st c">×</text>`;
      case "int": return `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="sb"/><text x="${cx}" y="${cy - 1}" class="st c">1</text><line x1="${x + 9}" x2="${x + w - 9}" y1="${cy + 2}" y2="${cy + 2}" class="sl"/><text x="${cx}" y="${cy + 12}" class="st c">s</text>`;
      case "sat": return `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="sb"/><path d="M${x + 7},${y + h - 9} H${x + 16} L${x + w - 16},${y + 9} H${x + w - 7}" class="sl"/>`;
      case "lookup": return `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="sb"/><path d="M${x + 6},${y + 10} C${x + 18},${y + 10} ${x + 22},${y + h - 8} ${x + w - 6},${y + h - 7}" class="sl"/><text x="${cx}" y="${y + h - 4}" class="st c sm">${b.sub || ""}</text>`;
      case "const": return `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="sb"/><text x="${cx}" y="${cy + 4}" class="st c">${b.sub || fmtK(b.k)}</text>`;
      case "scope": return `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="sb"/><rect x="${x + 8}" y="${y + 8}" width="${w - 16}" height="${h - 16}" class="scr"/><path d="M${x + 10},${cy + 4} l8,-8 l8,10 l8,-6 l8,4 l8,-6" class="sl"/>`;
      case "sub": {
        const P = SD.ports[b.child];
        return `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="sb sub"/><text x="${cx}" y="${y + 15}" class="st c bold">${b.label}</text>` +
          `<text x="${cx}" y="${y + h - 6}" class="st c sm live" data-sum="${SUMMARY[b.child] || ""}"></text>` +
          P.ins.map((s, i) => `<text x="${x + 4}" y="${e.pin[i][1] + 3}" class="st pl">${short(s)}</text>`).join("") +
          P.outs.map((s, i) => `<text x="${x + w - 4}" y="${e.pout[i][1] + 3}" class="st pr">${short(s)}</text>`).join("");
      }
      default: return `<rect x="${x}" y="${y}" width="${w}" height="${h}" class="sb"/><text x="${cx}" y="${cy - (b.sub ? 2 : -4)}" class="st c bold">${b.label || b.id}</text>` + (b.sub ? `<text x="${cx}" y="${cy + 11}" class="st c sm">${b.sub}</text>` : "");
    }
  }
  const fmtK = (k) => Math.abs(k) >= 1000 || (Math.abs(k) < 0.01 && k) ? k.toExponential(1) : (+k.toPrecision(3)).toString();
  let sdView = null, sdBox = null, sdSel = null, sdDragged = false;
  function sdRender() {
    if (!SD) sdBuild();
    const els = sdElements(simDiag), wires = sdWires(els);
    const xs = els.flatMap(e => [e.x, e.x + e.w]), ys = els.flatMap(e => [e.y, e.y + e.h]);
    const lanesY = Math.max(...ys) + 14 + 8 * 6;
    const box = [Math.min(...xs) - 16, Math.min(...ys) - 24, Math.max(...xs) - Math.min(...xs) + 32, Math.max(lanesY, Math.max(...ys)) - Math.min(...ys) + 34];
    sdBox = box; sdView = sdView && sdView.sys === simDiag ? sdView : { sys: simDiag, v: box.slice() };
    const units = (s) => SD.M.units[SD.M.index.get(s)] || "";
    let h = `<svg id="sd-svg" viewBox="${sdView.v.join(" ")}" role="img" aria-label="Block diagram: ${SD.M.systems[simDiag].label}">
      <defs><marker id="sd-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L8,4 L0,8 z" class="arr"/></marker></defs>`;
    for (const w of wires) {
      const pr = simProbe.includes(w.s);
      h += `<g class="sw${pr ? " pr" : ""}" data-sig="${w.s}"><title>${w.s} (${units(w.s) || "–"}): click to plot it in the probe scope</title><path d="${w.d}" class="hit"/><path d="${w.d}" class="ln" marker-end="url(#sd-arr)"/></g>`;
    }
    for (const e of els) {
      if (e.port) {
        const n = (e.port === "in" ? SD.ports[simDiag].ins : SD.ports[simDiag].outs).indexOf(e.sig) + 1;
        h += `<g class="sp ${e.port}"><rect x="${e.x}" y="${e.y}" width="${e.w}" height="${e.h}" rx="9"/><text x="${e.x + e.w / 2}" y="${e.y + 12.5}" class="st c">${n}</text>
          <text x="${e.port === "in" ? e.x + e.w + 4 : e.x - 4}" y="${e.y - 3}" class="st ${e.port === "in" ? "" : "pr"} sm">${short(e.sig)}</text></g>`;
        continue;
      }
      const b = e.b, open = b.type === "sub";
      const isSel = sdSel && sdSel.sys === simDiag && sdSel.id === b.id;
      h += `<g class="sblk ${b.type}${open ? " open" : ""}${isSel ? " sel" : ""}" data-id="${b.id}" ${open ? `data-sys="${b.child}"` : ""} tabindex="0" role="button" aria-label="${b.label || b.id}${open ? ", subsystem" : ""}">
        <title>${b.label || b.id}${b.sub ? " — " + b.sub : ""}: click to show its scopes${open ? ", double-click to open" : ""}</title>${sdIcon(e)}</g>`;
      if (!["fcn", "src", "sub", "const", "scope"].includes(b.type) && b.label && b.type !== "gain") h += `<text x="${e.x + e.w / 2}" y="${e.y + e.h + 11}" class="st c sm lbl">${b.label}</text>`;
      if (b.type === "gain" && b.sub) h += `<text x="${e.x + e.w / 2}" y="${e.y + e.h + 11}" class="st c sm lbl">${b.sub}</text>`;
    }
    // value tags: probed wires always, every wire when "values" is on
    for (const e of els) e.outs.forEach((s, i) => {
      if (!(simShowVals || simProbe.includes(s) || e.port === "out")) return;
      if (e.port === "in") return;
      const [x, y] = e.pout[i];
      h += `<text x="${x + 3}" y="${y - 3}" class="st val" data-val="${s}"></text>`;
    });
    h += `</svg>`;
    const path = []; let id = simDiag; while (id) { path.unshift(id); id = SD.M.systems[id].parent; }
    $("sd-crumb").innerHTML = path.map((p, i) => i < path.length - 1 ? `<button type="button" class="lk" data-sys="${p}">${SD.M.systems[p].label}</button> ›` : `<b>${SD.M.systems[p].label}</b>`).join(" ");
    $("sd-wrap").innerHTML = h;
    $("sd-crumb").querySelectorAll("[data-sys]").forEach(el => el.onclick = () => { simDiag = el.dataset.sys; sdSel = null; sdRender(); });
    $("sd-wrap").querySelectorAll(".sblk").forEach(el => {
      const open = () => { if (el.dataset.sys) { simDiag = el.dataset.sys; sdSel = null; sdRender(); } };
      const pick = () => { const id = el.dataset.id; sdSel = sdSel && sdSel.sys === simDiag && sdSel.id === id ? null : { sys: simDiag, id }; sdRender(); };
      el.addEventListener("click", pick); el.addEventListener("dblclick", (e) => { e.stopPropagation(); open(); });
      el.addEventListener("keydown", e => { if (e.key === "Enter") open(); if (e.key === " ") { e.preventDefault(); pick(); } });
    });
    $("sd-svg").addEventListener("click", (e) => { if (!e.target.closest(".sblk, .sw") && sdSel && !sdDragged) { sdSel = null; sdRender(); } });
    scopeInit();
    $("sd-wrap").querySelectorAll(".sw").forEach(el => el.addEventListener("click", () => {
      const s = el.dataset.sig, i = simProbe.indexOf(s);
      if (i >= 0) simProbe.splice(i, 1); else { simProbe.push(s); if (simProbe.length > 4) simProbe.shift(); }
      if (!scopeOn.has("probe")) { scopeOn.add("probe"); store.set("simScopes", [...scopeOn].join(",")); }
      sdRender();
    }));
    sdLive(true);
  }
  // pan and zoom the diagram
  (function () {
    let drag = null;
    const wrap = () => $("sd-wrap");
    document.addEventListener("wheel", (e) => {
      const svg = e.target.closest && e.target.closest("#sd-svg"); if (!svg || !sdView) return;
      e.preventDefault();
      const r = svg.getBoundingClientRect(), v = sdView.v, k = e.deltaY > 0 ? 1.15 : 1 / 1.15;
      const s = Math.max(v[2] / r.width, v[3] / r.height);
      const px = v[0] + (e.clientX - r.left - (r.width - v[2] / s) / 2) * s, py = v[1] + (e.clientY - r.top - (r.height - v[3] / s) / 2) * s;
      sdView.v = [px - (px - v[0]) * k, py - (py - v[1]) * k, v[2] * k, v[3] * k];
      svg.setAttribute("viewBox", sdView.v.join(" "));
    }, { passive: false });
    document.addEventListener("pointerdown", (e) => {
      const svg = e.target.closest && e.target.closest("#sd-svg"); if (!svg || e.target.closest(".sblk, .sw")) return;
      sdDragged = false;
      drag = { x: e.clientX, y: e.clientY, v: sdView.v.slice(), svg };
    });
    document.addEventListener("pointermove", (e) => {
      if (!drag) return;
      if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 3) sdDragged = true;
      const r = drag.svg.getBoundingClientRect(), s = Math.max(drag.v[2] / r.width, drag.v[3] / r.height);
      sdView.v = [drag.v[0] - (e.clientX - drag.x) * s, drag.v[1] - (e.clientY - drag.y) * s, drag.v[2], drag.v[3]];
      drag.svg.setAttribute("viewBox", sdView.v.join(" "));
    });
    document.addEventListener("pointerup", () => { drag = null; });
    document.addEventListener("dblclick", (e) => { if (e.target.closest && e.target.closest("#sd-svg") && !e.target.closest(".sblk")) { sdView.v = sdBox.slice(); $("sd-svg").setAttribute("viewBox", sdView.v.join(" ")); } });
  })();
  let sdLiveT = 0;
  function sdLive(force) {
    const now = performance.now(); if (!force && now - sdLiveT < 120) return; sdLiveT = now;
    if (!SR) return;
    const M = SR.M, wrap = $("sd-wrap"); if (!wrap) return;
    const kb = recK(simTp), val = (s) => recVal(kb, M.index.get(s));
    wrap.querySelectorAll("[data-val]").forEach(el => { const s = el.dataset.val; el.textContent = fmtSig(val(s), M.units[M.index.get(s)]); });
    wrap.querySelectorAll("[data-sum]").forEach(el => { const s = el.dataset.sum; if (s) el.textContent = short(s) + " " + fmtSig(val(s), M.units[M.index.get(s)]); });
    // a saturating block lights up, as the torque limit or the VFD's power cap bites
    const active = (b) => { const u = recVal(kb, b.ii[0]), lim = b.ii.length > 1 ? recVal(kb, b.ii[1]) : null;
      return lim !== null ? Math.abs(u) > lim * 1.0005 : u < b.lo || u > b.hi; };
    wrap.querySelectorAll(".sblk.sat").forEach(el => { const b = M.blocks.find(q => q.sys === simDiag && q.id === el.dataset.id); el.classList.toggle("on", !!(b && active(b))); });
    if (simDiag === "top") {
      const sat = (sys) => M.blocks.some(q => q.type === "sat" && (q.sys === sys || (SD.M.systems[q.sys] || {}).parent === sys) && active(q));
      wrap.querySelectorAll(".sblk.open").forEach(el => el.classList.toggle("on", sat(el.dataset.sys)));
    }
  }

  // ---- scopes: strip charts beside the 3D view, Simulink's Scope blocks
  const COLS = ["#1f6fb2", "#d0402b", "#2f8f4e", "#9a6a12", "#7a4fb5"];
  // each trace: [signal, label, scale (default from its unit), colour index, dashed]; dashed traces are what the program asked for
  const SCOPES = [...(U.scopes || []), { id: "probe", title: "Probe", unit: "", probe: true, sigs: [], lines: [] }];
  const scopeOn = new Set((store.get("simScopes", "") || [...(U.scopesOn || SCOPES.slice(0, 4).map(s => s.id)), "probe"].join(",")).split(",").filter(Boolean));
  // what the diagram selection stands for: a subsystem's own signals, or one block's inputs and outputs
  function scopeFilter() {
    if (!SD) return null;
    let sys = null, blk = null;
    if (sdSel) { const b = SD.M.blocks.find(q => q.sys === sdSel.sys && q.id === sdSel.id); if (!b) return null; if (b.type === "sub") sys = b.child; else blk = b; }
    else if (simDiag !== "top") sys = simDiag;
    if (!sys && !blk) return null;
    const desc = [], walk = (id) => { const S = SD.M.systems[id]; S.blocks.forEach(b => { if (b.type !== "sub") desc.push(b); }); S.children.forEach(walk); };
    let sigs, label, probe = [];
    if (sys) { walk(sys); sigs = new Set(desc.filter(b => b.type !== "scope").flatMap(b => b.out)); label = SD.M.systems[sys].label; }
    else { sigs = new Set([...blk.out, ...blk.in]); label = blk.label || blk.id; probe = blk.type === "scope" ? blk.in : blk.out; }
    return { sigs, label, probe };
  }
  function scopesShown() {
    const F = scopeFilter();
    if (!F) return SCOPES.filter(S => scopeOn.has(S.id));
    const list = SCOPES.filter(S => !S.probe && S.sigs.some(([n]) => F.sigs.has(n)));
    if (F.probe.length || simProbe.length || !list.length) list.push(SCOPES.find(S => S.probe));
    return list;
  }
  function scopeInit() {
    if (!$("scopes")) return;
    const F = scopeFilter();
    $("scope-sel").innerHTML = F ? `Scopes for <b>${F.label}</b>, from the diagram selection <button type="button" class="lk" id="scope-all">show the ticked set</button>` : "";
    $("scope-sel").hidden = !F;
    if (F) $("scope-all").onclick = () => { sdSel = null; if (simDiag !== "top") simDiag = "top"; sdRender(); };
    $("scope-pick").hidden = !!F;
    $("scope-pick").innerHTML = SCOPES.map(S => `<label class="${scopeOn.has(S.id) ? "on" : ""}"><input type="checkbox" data-sc="${S.id}"${scopeOn.has(S.id) ? " checked" : ""}>${S.title}</label>`).join("");
    $("scope-pick").querySelectorAll("[data-sc]").forEach(el => el.onchange = () => {
      el.checked ? scopeOn.add(el.dataset.sc) : scopeOn.delete(el.dataset.sc);
      el.parentElement.classList.toggle("on", el.checked);
      store.set("simScopes", [...scopeOn].join(",")); scopeInit();
    });
    $("scopes").innerHTML = scopesShown().map(S => `<div class="scope" id="sc-${S.id}"><div class="sc-h"><b>${S.title}</b><span class="sc-u"></span><span class="sc-k"></span></div><canvas></canvas></div>`).join("");
    scopeDraw(true);
  }
  let scT = 0;
  function scopeDraw(force) {
    const now = performance.now(); if (!force && now - scT < 66) return; scT = now;
    if (!SR || !REC.n) return;
    const kEnd = recK(simTp) + 1;
    const tNow = simTp, t0 = simWin ? Math.max(0, tNow - simWin) : 0, t1 = simWin ? Math.max(simWin, tNow) : Math.max(tNow, 1);
    const ink = css("--muted"), line = css("--line"), fail = css("--fail");
    // first bucket in the window
    let i0 = 0, lo = 0, hi = REC.n - 1; while (lo < hi) { const m = (lo + hi) >> 1; if (REC.t[m] < t0) lo = m + 1; else hi = m; } i0 = lo;
    const selProbe = (scopeFilter() || {}).probe || [];
    scopesShown().forEach((S) => {
      const div = $("sc-" + S.id); if (!div) return;
      const cv = div.querySelector("canvas");
      const W = cv.clientWidth, H = cv.clientHeight, dpr = Math.min(2, devicePixelRatio || 1);
      if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
      const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
      const sigs = (S.probe ? (simProbe.length ? simProbe : selProbe).map((s, j) => [s, short(s), undefined, j]) : S.sigs)
        .map(([s, l, k, c, dash], j) => { const i = SR.M.index.get(s); return i === undefined ? null : { i, l, k: k ?? sigScale(SR.M.units[i]), c: c ?? j, dash }; }).filter(Boolean);
      const u0 = sigs.length ? SR.M.units[sigs[0].i] || "" : "";
      div.querySelector(".sc-u").textContent = S.probe ? (sigs.length ? sigUnit(u0) : "click any wire in the diagram") : S.unit + (S.note ? " · " + S.note : "");
      div.querySelector(".sc-k").innerHTML = sigs.filter(q => q.l).map(q => `<span style="color:${COLS[q.c % 5]}">${q.l}</span>`).join(" ");
      let ymin = Infinity, ymax = -Infinity;
      for (let b = i0; b < kEnd; b++) for (const q of sigs) { const a = REC.min[b * REC.ns + q.i] * q.k, c = REC.max[b * REC.ns + q.i] * q.k; if (a < ymin) ymin = a; if (c > ymax) ymax = c; }
      for (const [y] of S.lines) { ymin = Math.min(ymin, y); ymax = Math.max(ymax, y); }
      if (!isFinite(ymin)) { ymin = 0; ymax = 1; }
      if (ymax - ymin < 1e-9) { ymax += 1; ymin -= 1; }
      const pad = (ymax - ymin) * 0.08; ymin -= pad; ymax += pad;
      const L = 40, R = 6, T = 4, B = 14, pw_ = W - L - R, ph = H - T - B;
      const X = (t) => L + (t - t0) / (t1 - t0) * pw_, Y = (v) => T + (1 - (v - ymin) / (ymax - ymin)) * ph;
      g.font = "10px " + css("--font-mono"); g.fillStyle = ink; g.strokeStyle = line; g.lineWidth = 1;
      g.strokeRect(L + 0.5, T + 0.5, pw_, ph);
      const step = niceStep((ymax - ymin) / 4);
      for (let v = Math.ceil(ymin / step) * step; v <= ymax; v += step) { const y = Y(v); g.globalAlpha = 0.5; g.beginPath(); g.moveTo(L, y); g.lineTo(L + pw_, y); g.stroke(); g.globalAlpha = 1; g.fillText(fmtTick(v), 2, y + 3); }
      const ts = niceStep((t1 - t0) / 5);
      for (let t = Math.ceil(t0 / ts) * ts; t <= t1; t += ts) g.fillText(t.toFixed(ts < 1 ? 1 : 0) + " s", X(t) - 8, H - 2);
      for (const [y, lab] of S.lines) { g.strokeStyle = fail; g.setLineDash([4, 3]); g.beginPath(); g.moveTo(L, Y(y)); g.lineTo(L + pw_, Y(y)); g.stroke(); g.setLineDash([]); if (lab) { g.fillStyle = fail; g.fillText(lab, L + 4, Y(y) - 3); g.fillStyle = ink; } }
      if (!sigs.length) return;
      g.save(); g.beginPath(); g.rect(L, T, pw_, ph); g.clip();
      // per pixel column: the envelope of the buckets in it
      for (const q of sigs) {
        g.strokeStyle = COLS[q.c % 5]; g.lineWidth = q.dash ? 1 : 1.3; g.setLineDash(q.dash ? [5, 3] : []); g.globalAlpha = q.dash ? 0.8 : 1; g.beginPath();
        let col = -1, cmn = 0, cmx = 0, first = true;
        const flush = () => { if (col < 0) return; const x = col + 0.5; if (first) { g.moveTo(x, Y(cmx)); first = false; } else g.lineTo(x, Y(cmx)); if (cmn !== cmx) g.lineTo(x, Y(cmn)); };
        for (let b = i0; b < kEnd; b++) {
          const x = Math.floor(X(REC.t[b])), a = REC.min[b * REC.ns + q.i] * q.k, c = REC.max[b * REC.ns + q.i] * q.k;
          if (x !== col) { flush(); col = x; cmn = a; cmx = c; } else { if (a < cmn) cmn = a; if (c > cmx) cmx = c; }
        }
        flush(); g.stroke();
      }
      g.setLineDash([]); g.globalAlpha = 1;
      g.restore();
    });
  }
  const niceStep = (r) => { const p = Math.pow(10, Math.floor(Math.log10(r || 1))), f = r / p; return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p; };
  const fmtTick = (v) => Math.abs(v) >= 1000 ? (v / 1000).toFixed(1) + "k" : Math.abs(v) < 1e-9 ? "0" : (+v.toPrecision(3)).toString();

  // ---- the controls and measures
  function simUI() {
    if (!SR) return;
    $("sim-play").textContent = simRun ? "Pause" : simDone() && simTp >= tEnd() - 1e-9 ? "Run again" : "Run";
    simJogState();
    $("sim-note").textContent = simJog || (SR.job ? SR.job.note || "" : "");
    simMeasures();
  }
  function simMeasures() {
    if (!SR || !simMeter || !U.measures) return;
    const full = SIMRES && SIMRES[simJob], m = U.measures(simJob, simMeter.r, full, V.sim);
    const f = (v) => v == null ? "–" : (+v.toPrecision(3)).toString();
    $("sim-meas").innerHTML = `<table><thead><tr><th></th><th>measure</th><th>this run, computed</th><th>full run</th><th>limit</th></tr></thead><tbody>` +
      m.rows.map(([id, t, a, b, l, u]) => `<tr><td><span class="chip ${status(id)}" data-req="${id}">${id}</span></td><td>${t}</td><td class="num">${f(a)}</td><td class="num">${f(b)}</td><td class="num">${l} ${u}</td></tr>`).join("") +
      `</tbody></table><div class="sim-foot">${m.foot || ""}</div>`;
    $("sim-meas").querySelectorAll("[data-req]").forEach(el => el.onclick = () => {
      const id = el.dataset.req; showTab("p-req"); openGroupOf(id); P.selReq = id;
      document.querySelectorAll(".req").forEach(r => r.classList.toggle("sel", r.dataset.req === id));
      $("row-" + id)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  }
  // how far to trust the model: its own checks, and how the requirements move when each guessed parameter is halved or doubled
  let SENS = null;
  if (SIMP) fetch("sensitivity.json").then(r => r.ok ? r.json() : null).then(j => { SENS = j; simTrust(); }).catch(() => {});
  function simTrust() {
    const el = $("sim-trust"); if (!el || !V.sim) return;
    const v = V.sim.verify, f3 = (x) => (+x.toPrecision(3)).toString();
    let h = "";
    if (v && U.trust) {
      const rows = U.trust ? U.trust(v) : [];
      h += `<table><thead><tr><th></th><th>check: is the model solved right?</th><th>result</th><th>limit</th></tr></thead><tbody>` +
        rows.map(([id, t, r, l]) => `<tr><td><span class="chip ${status(id)}">${id}</span></td><td>${t}</td><td class="num">${r}</td><td class="num">${l}</td></tr>`).join("") + `</tbody></table>`;
    }
    if (!SENS) { el.innerHTML = h + `<div class="sim-foot">No sensitivity sweep yet: run <code>python3 sensitivity.py</code> after router.py.</div>`; return; }
    const B = SENS.base, margin = (c) => c.op === "<=" ? c.lim - c.v : c.v - c.lim;
    const scale = (k) => Math.max(Math.abs(B[k].lim), Math.abs(margin(B[k])), 1e-9);
    const cell = (r) => {
      const fails = Object.entries(r.checks).filter(([, c]) => !c.ok);
      if (fails.length) return fails.map(([k, c]) => `<span class="chip fail" title="${k}: ${f3(c.v)} against ${c.op} ${f3(c.lim)}">${k} ${f3(c.v)}</span>`).join(" ");
      let worst = null, loss = 0;
      for (const [k, c] of Object.entries(r.checks)) { const d = (margin(B[k]) - margin(c)) / scale(k); if (d > loss) { loss = d; worst = k; } }
      return worst && loss > 0.02 ? `<span class="muted">pass · ${worst} ${f3(B[worst].v)} → ${f3(r.checks[worst].v)}</span>` : `<span class="muted">pass, little change</span>`;
    };
    const by = {}; SENS.rows.forEach(r => { (by[r.name] ||= {})[r.f] = r; });
    const fragile = {};
    SENS.rows.forEach(r => Object.entries(r.checks).forEach(([k, c]) => { if (!c.ok) (fragile[k] ||= []).push(`${r.name} ×${r.f}`); }));
    const stale = SENS.digest !== V.sim.digest;
    h += `<table class="sens"><thead><tr><th>guessed parameter</th><th>at ½×</th><th>at 2×</th></tr></thead><tbody>` +
      Object.entries(by).map(([n, q]) => `<tr><td>${n}</td><td>${q[0.5] ? cell(q[0.5]) : "–"}</td><td>${q[2] ? cell(q[2]) : "–"}</td></tr>`).join("") + `</tbody></table>
      <div class="sim-foot">${stale ? "<b>This sweep is stale:</b> the parameters have changed since it ran. " : ""}Each row reruns every job with one guess halved or doubled
      (${SENS.rows.length} runs, ${Math.round(SENS.seconds / 60)} min). ${Object.keys(fragile).length ? "Fragile: " + Object.entries(fragile).map(([k, w]) => `<b>${k}</b> fails with ${w.join(", ")}`).join("; ") + "." : "No requirement fails under any of these."}</div>`;
    el.innerHTML = h;
  }
  function renderSim() {
    if (!SIMP) { $("p-sim").innerHTML = `<div class="empty">No simulation in this build.</div>`; return; }
    const J = U.jog || { axes: [] };
    $("p-sim").innerHTML = `<div class="sim-bar">
        <div class="row2"><select id="sim-job" aria-label="Job">${Object.entries(SIM_JOBS).map(([k, j]) => `<option value="${k}"${k === simJob ? " selected" : ""}>${j.label}</option>`).join("")}</select>
          <button type="button" id="sim-play">Run</button><button type="button" id="sim-reset">Reset</button>
          <label>speed <select id="sim-speed">${[0.1, 0.25, 1, 4, 16].map(s => `<option value="${s}"${s === simSpeed ? " selected" : ""}>${s}×</option>`).join("")}</select></label>
          <span id="sim-t" class="num"></span></div>
        <div class="row2"><label>feed <input id="sim-feed" type="range" min="50" max="150" step="10" value="${simFeed * 100}"><span class="num" id="sim-feed-v">${simFeed * 100}%</span></label>
          <label>accel <input id="sim-acc" type="range" min="50" max="300" step="25" value="${simAcc * 100}"><span class="num" id="sim-acc-v">${simAcc * 100}%</span></label>
          <label>3D error <select id="sim-err">${[1, 100, 1000].map(k => `<option value="${k}"${k === simErr ? " selected" : ""}>×${k}</option>`).join("")}</select></label>
          <label>window <select id="sim-win">${[[5, "5 s"], [20, "20 s"], [0, "all"]].map(([v, l]) => `<option value="${v}"${v === simWin ? " selected" : ""}>${l}</option>`).join("")}</select></label></div>
        <div class="row2 jog"${J.axes.length ? "" : " hidden"}><span>jog</span>${J.axes.map(a => `<button type="button" data-jog="${a}-">${a}−</button><button type="button" data-jog="${a}+">${a}+</button>`).join("")}
          <select id="sim-jstep" aria-label="Jog step">${(J.steps || [1, 10, 100]).map(s => `<option value="${s}"${s === J.step ? " selected" : ""}>${s} ${J.unit || ""}</option>`).join("")}</select>
          <label class="vals"><input type="checkbox" id="sim-vals"${simShowVals ? " checked" : ""}> values on wires</label></div>
        <div class="sim-note" id="sim-note"></div></div>
      <div class="scope-sel" id="scope-sel" hidden></div>
      <div class="scope-pick" id="scope-pick" aria-label="Scopes to show"></div>
      <div class="scopes" id="scopes" aria-label="Scopes"></div>
      <div class="section-h">Measures</div><div id="sim-meas" class="sim-meas"></div>
      <div class="section-h">Model checks and sensitivity</div><div id="sim-trust" class="sim-meas"></div>`;
    simTrust();
    $("sim-job").onchange = (e) => { simLoad(e.target.value); };
    $("sim-play").onclick = () => {
      if (!SR || simSeeking) return;
      if (simTp >= tEnd() - 1e-9 && simDone()) simLoad(simJob);
      simRun = !simRun; if (simRun) simBuffering = !simReady();
      simLastReal = performance.now(); simUI();
    };
    $("sim-reset").onclick = () => simLoad(simJob);
    $("sim-speed").onchange = (e) => { simSpeed = +e.target.value; if (simRun) { simBuffering = !simReady(); simUI(); } };
    $("sim-feed").oninput = (e) => { simFeed = e.target.value / 100; $("sim-feed-v").textContent = e.target.value + "%"; };
    $("sim-feed").onchange = () => simLoad(simJob);
    $("sim-acc").oninput = (e) => { simAcc = e.target.value / 100; $("sim-acc-v").textContent = e.target.value + "%"; };
    $("sim-acc").onchange = () => simLoad(simJob);
    $("sim-err").onchange = (e) => { simErr = +e.target.value; simPose(true); };
    $("sim-win").onchange = (e) => { simWin = +e.target.value; scopeDraw(true); };
    $("sim-vals").onchange = (e) => { simShowVals = e.target.checked; sdRender(); };
    $("p-sim").querySelectorAll("[data-jog]").forEach(el => el.onclick = () => {
      if (!SR || simRun || simSeeking) return;
      // jog from where the playback is: drop whatever was computed after it, and start there at rest
      const kb = recK(simTp), M = SR.M;
      const cur = REC.n && kb >= 0 ? UP.ref.map(n => recVal(kb, M.index.get(n)) * UP.scale) : SR.start.slice();
      const a = el.dataset.jog.slice(0, -1), sgn = el.dataset.jog.slice(-1) === "+" ? 1 : -1, i = J.axes.indexOf(a), to = cur.slice();
      to[i] += sgn * +$("sim-jstep").value;
      const lim = J.lim[i]; to[i] = Math.max(lim[0], Math.min(lim[1], to[i]));
      if (Math.abs(to[i] - cur[i]) < 0.01) { $("sim-note").textContent = `${a} is at the ${sgn > 0 ? "upper" : "lower"} end of its travel (${lim[sgn > 0 ? 1 : 0]} ${J.unit || ""}): no jog that way.`; return; }
      const custom = { label: "Jog", note: J.note(a, sgn, $("sim-jstep").value), prog: J.prog(to) };
      simTruncate();
      simLoad(simJob, { custom, start: cur, keep: true }); simJog = custom.note; simRun = true; simBuffering = !simReady(); simLastReal = performance.now(); simUI();
    });
    sdRender(); simUI();
  }
  function simJogState() {
    const ok = SR && !simRun && !simSeeking;
    document.querySelectorAll("[data-jog]").forEach(b => { b.disabled = !ok; b.title = ok ? "jog from where the playback is" : "pause to jog"; });
  }
  // cut the recording and the 3D track back to the playback time, so a jog carries on from there
  function simTruncate() {
    const k = recK(simTp);
    REC.n = Math.max(0, k + 1); REC.bmin.fill(Infinity); REC.bmax.fill(-Infinity);
    for (const kd of ["cut", "move"]) { let n = trace.n[kd]; while (n > 0 && trace.tt[kd][n - 1] > simTp) n--; trace.n[kd] = n; }
    trace.last = null;
  }
  function enterSim() {
    if (!SIMP) return;
    simOn = true; document.body.classList.add("sim-mode");
    if (!trace.cut) traceLines();
    traceShow(true);
    if (!SR) simLoad(simJob);
    clearAnnot(); highlight(P.focus ? P.focusParts() : null);
    setTimeout(() => { P.resize(); scopeDraw(true); }, 0);
  }
  function exitSim() {
    if (!simOn) return;
    simOn = false; simRun = false; simSeeking = false; document.body.classList.remove("sim-mode");
    traceShow(false);
    setTimeout(P.resize, 0);
  }
  function simFrame(now) {
    if (!simOn || !SR) return;
    const dt = simLastReal ? (now - simLastReal) / 1000 : 0; simLastReal = now;
    if (!simSeeking) {
      simAdvance(dt);
      if (simRun && !simBuffering) simPose(false);
      const T = tEnd() - simTOff, tp = simTp - simTOff, ahead = simDone() ? "all computed" : `computed to ${(tcNow() - simTOff).toFixed(1)} s`;
      $("sim-t").textContent = simRun && simBuffering
        ? `buffering… playback at ${simSpeed}× starts in about ${Math.ceil(simWait())} s (${ahead})`
        : `t ${tp.toFixed(2)} of ${T.toFixed(1)} s · ${ahead}`;
      $("sim-t").classList.toggle("buf", simRun && simBuffering);
    }
    scopeDraw(false); sdLive(false);
    if ((now | 0) % 6 === 0) { simMeasures(); simJogState(); }
  }
  // a requirement from the simulation: open the job and run ahead to just before its worst moment
  function simFocusReq(id) {
    if (!SIMRES || !U.focusReq) return;
    const o = U.focusReq(id, SIMRES) || {}, job = o.job || simJob;
    if (o.probe) simProbe.splice(0, simProbe.length, ...o.probe);
    for (const s of o.scopes || []) if (!scopeOn.has(s)) { scopeOn.add(s); store.set("simScopes", [...scopeOn].join(",")); }
    simDiag = o.diag || "top"; sdView = null; sdSel = null;
    $("sim-job").value = job; simLoad(job); sdRender();
    if (o.t != null) simSeek(Math.max(0, o.t - 0.6), () => { simSpeed = 0.1; $("sim-speed").value = "0.1"; simRun = true; simBuffering = !simReady(); simLastReal = performance.now(); simUI(); });
  }

  Object.assign(comp, {
    render() { renderSim(); scopeInit(); },
    enter: enterSim, exit: exitSim,
    claimsReq: (id) => !!(V.viz[id] && V.viz[id].sim && SIMP),
    focusReq: simFocusReq,
  });
  P.on("frame", (now) => {
    try { simFrame(now); }
    catch (e) { console.error(e); simRun = false; simSeeking = false; if ($("sim-t")) $("sim-t").textContent = "simulation stopped: " + e.message; }
    P.hold = simOn && simSeeking;
  });
  };
})();
