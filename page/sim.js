/* Tilted-bed CNC router: a block-diagram simulation of the machine.
   One model, run in the page (live, with its diagrams and scopes) and under Node by router.py (to verify requirements).
   Units inside: SI (m, s, kg, N, rad). Positions shown and jobs written in mm.

   The model is a graph of Simulink-style blocks (gain, sum, integrator, saturation, lookup, function, subsystem) wired by
   named signals. Each step evaluates the feed-through blocks in dependency order, then advances the integrators with
   semi-implicit (symplectic) Euler: velocities first, then the positions that integrate them. */
(function (root) {
  "use strict";

  // ------------------------------------------------------------------ the block graph
  class Model {
    constructor(P) {
      this.P = P; this.dt = P.dt;
      this.index = new Map(); this.names = []; this.units = []; this.blocks = []; this.systems = {};
      this.order = [];
    }
    s(name, unit) {
      if (!this.index.has(name)) { this.index.set(name, this.names.length); this.names.push(name); this.units.push(unit || ""); }
      else if (unit && !this.units[this.index.get(name)]) this.units[this.index.get(name)] = unit;
      return this.index.get(name);
    }
    sys(id, label, parent, size) { this.systems[id] = { id, label, parent, blocks: [], children: [], size: size || [760, 420] }; if (parent) this.systems[parent].children.push(id); return id; }
    add(sys, b) {
      b.sys = sys; b.in = b.in || []; b.out = b.out || [];
      b.ii = b.in.map(n => this.s(n)); b.oi = b.out.map((n, i) => this.s(n, (b.units || [])[i]));
      b.n = this.blocks.length; this.blocks.push(b); this.systems[sys].blocks.push(b);
      return b;
    }
    finish() {
      this.v = new Float64Array(this.names.length);
      const stateful = new Set(["int", "lag"]);
      const prod = new Map();                       // signal -> block that writes it
      for (const b of this.blocks) if (b.type !== "sub") for (const o of b.oi) prod.set(o, b);
      // evaluation order of the feed-through blocks: a block runs after the blocks that write its inputs (integrators excepted)
      const ft = this.blocks.filter(b => !stateful.has(b.type) && b.type !== "sub" && b.type !== "scope");
      const seen = new Set(), tmp = new Set(), order = [];
      const visit = (b) => {
        if (seen.has(b.n)) return;
        if (tmp.has(b.n)) throw new Error("algebraic loop at " + b.id);
        tmp.add(b.n);
        for (const i of b.ii) { const p = prod.get(i); if (p && !stateful.has(p.type) && p.type !== "sub") visit(p); }
        tmp.delete(b.n); seen.add(b.n); order.push(b);
      };
      ft.forEach(visit);
      this.order = order;
      // integrators: those fed by another integrator's output (positions) step after the ones they integrate (velocities)
      const ints = this.blocks.filter(b => stateful.has(b.type));
      const intOut = new Set(ints.flatMap(b => b.oi));
      this.ints1 = ints.filter(b => !intOut.has(b.ii[0]));
      this.ints2 = ints.filter(b => intOut.has(b.ii[0]));
      this.reset();
      return this;
    }
    reset() {
      this.v.fill(0); this.t = 0;
      for (const b of this.blocks) {
        if (b.type === "int" || b.type === "lag") { b.x = typeof b.x0 === "function" ? b.x0(this.P) : (b.x0 || 0); this.v[b.oi[0]] = b.x; }
        if (b.init) b.init(b, this);
        if (b.type === "const") this.v[b.oi[0]] = b.k;
      }
    }
    step() {
      const v = this.v, dt = this.dt;
      for (const b of this.order) {
        switch (b.type) {
          case "gain": v[b.oi[0]] = b.k * v[b.ii[0]]; break;
          case "sum": { let s = 0; for (let i = 0; i < b.ii.length; i++) s += b.signs[i] === "-" ? -v[b.ii[i]] : v[b.ii[i]]; v[b.oi[0]] = s; break; }
          case "prod": v[b.oi[0]] = v[b.ii[0]] * v[b.ii[1]]; break;
          case "sat": {
            const u = v[b.ii[0]], lo = b.ii.length > 1 ? -v[b.ii[1]] : b.lo, hi = b.ii.length > 1 ? v[b.ii[1]] : b.hi;
            const y = u < lo ? lo : u > hi ? hi : u; v[b.oi[0]] = y; b.active = y !== u; break;
          }
          case "lookup": v[b.oi[0]] = interp(b.xs, b.ys, Math.abs(v[b.ii[0]]) * (b.xscale || 1)); break;
          case "const": v[b.oi[0]] = b.k; break;
          case "fcn": case "src": {
            const r = b.f(b.ii.map(i => v[i]), this, b);
            if (b.oi.length === 1) v[b.oi[0]] = typeof r === "number" ? r : r[0];
            else for (let i = 0; i < b.oi.length; i++) v[b.oi[i]] = r[i];
            break;
          }
        }
      }
      for (const set of [this.ints1, this.ints2]) for (const b of set) {
        if (b.type === "int") {
          let x = b.x + v[b.ii[0]] * dt;
          if (b.lo !== undefined && x < b.lo) x = b.lo; if (b.hi !== undefined && x > b.hi) x = b.hi;
          b.x = x;
        } else b.x += (v[b.ii[0]] - b.x) * dt / b.tau;
        v[b.oi[0]] = b.x;
      }
      this.t += dt;
    }
    get(name) { return this.v[this.index.get(name)]; }
  }
  // stick-slip friction (elasto-plastic): a stiff spring that slips at the friction force, so it holds at rest as well as
  // dragging in motion; z is the spring's deflection, kept in the block
  function stick(b, key, v, dt, Fmax, zmax, mass) {
    if (!(Fmax > 0)) { b[key] = 0; return 0; }
    const k = Fmax / zmax, c = 2 * 0.3 * Math.sqrt(k * mass);
    let z = (b[key] || 0) + v * dt;
    if (z > zmax) z = zmax; else if (z < -zmax) z = -zmax;
    b[key] = z;
    const F = k * z + (Math.abs(z) < zmax ? c * v : 0);
    return Math.max(-Fmax, Math.min(Fmax, F));
  }
  function interp(xs, ys, x) {
    if (x <= xs[0]) return ys[0];
    for (let i = 1; i < xs.length; i++) if (x <= xs[i]) return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    return ys[ys.length - 1] * xs[xs.length - 1] / x;          // beyond the table: constant power
  }

  // ------------------------------------------------------------------ jobs: the programs the machine runs (mm, m/min, rpm)
  function jobs(P) {
    const J = P.job, safe = J.stock_t + 10, park = J.park, f = J.feed;
    const tl = J.stock_t / 3;                                       // three passes through the sheet
    const rect = (x0, y0, w, h, r, z, doc) => {                     // profile with rounded corners, climb direction
      const pts = [], n = 30, seg = (cx, cy, a0) => { for (let i = 0; i <= n; i++) { const a = a0 + i * Math.PI / 2 / n; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); } };   // 3° chords, as a controller splits G2/G3
      seg(x0 + w - r, y0 + r, -Math.PI / 2); seg(x0 + w - r, y0 + h - r, 0); seg(x0 + r, y0 + h - r, Math.PI / 2); seg(x0 + r, y0 + r, Math.PI);
      pts.push(pts[0]);
      return pts.map(([x, y]) => ({ op: "feed", to: [x, y, z], f, cut: { doc, woc: J.tool_d } }));
    };
    const out = {};
    out.rapids = { label: "Rapids across the travel", note: "G0 moves corner to corner at the rapid speeds: the hardest case for torque, supplies and vibration",
      prog: [{ op: "rapid", to: [park[0], park[1], park[2]] },
             { op: "rapid", to: [J.x[1] - 150, park[1], park[2]] }, { op: "rapid", to: [J.x[1] - 150, J.y[1], park[2]] },
             { op: "rapid", to: [J.x[1] - 150, J.y[1], safe] }, { op: "rapid", to: [J.x[1] - 150, J.y[1], park[2]] },
             { op: "rapid", to: [J.x[0] + 100, J.y[0], park[2]] }, { op: "rapid", to: [J.x[1] - 150, J.y[1], park[2]] },
             { op: "rapid", to: [park[0], park[1], park[2]] }] };
    const prof = [{ op: "spindle", rpm: J.rpm }, { op: "rapid", to: [200 + 600, 150, safe] }, { op: "dwell", t: J.spinup }];
    for (let k = 1; k <= 3; k++) {
      const z = J.stock_t - k * tl;
      prof.push({ op: "feed", to: [200 + 600, 150, z], f: J.plunge, cut: { plunge: true } });
      prof.push(...rect(200, 150, 1200, 600, 50, z, tl));
      prof.push({ op: "rapid", to: [200 + 600, 150, safe] });
    }
    prof.push({ op: "rapid", to: [park[0], park[1], park[2]] }, { op: "spindle", rpm: 0 });
    out.profile = { label: "Profile a 1200 × 600 panel", note: `three ${tl.toFixed(1)} mm passes through ${J.stock_t} mm sheet at ${f} m/min, 50 mm corner radii`, prog: prof };
    const pocket = [{ op: "spindle", rpm: J.rpm }, { op: "rapid", to: [1500, 700, safe] }, { op: "dwell", t: J.spinup },
                    { op: "feed", to: [1500, 700, J.stock_t - 6], f: J.plunge, cut: { plunge: true } }];
    const so = J.tool_d * 0.6;
    for (let i = 0, y = 700; i < 16; i++, y += so) {
      pocket.push({ op: "feed", to: [i % 2 ? 1500 : 1900, y, J.stock_t - 6], f, cut: { doc: 6, woc: i ? so : J.tool_d } });
      if (i < 15) pocket.push({ op: "feed", to: [i % 2 ? 1500 : 1900, y + so, J.stock_t - 6], f, cut: { doc: 6, woc: so } });
    }
    pocket.push({ op: "rapid", to: [1900, 700 + 15 * so, safe] }, { op: "rapid", to: [park[0], park[1], park[2]] }, { op: "spindle", rpm: 0 });
    out.pocket = { label: "Raster pocket, 400 × 110", note: `6 mm deep, ${so.toFixed(1)} mm stepover: many short reversals at ${f} m/min`, prog: pocket };
    const A = J.atc, za = A.z_nose, zu = park[2];
    out.toolchange = { label: "Tool change at the rack", note: "motion only: rapid to the rack, slide the holder into its fork, lift clear, return",
      prog: [{ op: "rapid", to: [A.x0 - 60, A.y, zu] }, { op: "rapid", to: [A.x0 - 60, A.y, za] }, { op: "feed", to: [A.x1, A.y, za], f: 2 },
             { op: "dwell", t: 0.5 }, { op: "feed", to: [A.x1, A.y, za + 60], f: 1 }, { op: "rapid", to: [A.x1, A.y, zu] },
             { op: "rapid", to: [park[0], park[1], park[2]] }] };
    // total power failure halfway along a rapid down the slope (-y) and towards the bed (-z), with x at its rapid too:
    // each axis at its own rapid speed at the moment the power goes
    const A0 = [300, J.y[1] - 50, park[2]], dir = [15, -10, -5], sc = 50, B0 = A0.map((v, i) => v + dir[i] * sc);
    const vpath = Math.hypot(...dir.map((d, i) => d / Math.abs(d) * P.axes["XYZ"[i]].v_rapid * 60));
    const pf = (drop) => ({ label: drop ? "Power failure, drivers drop out at once" : "Power failure at rapid", fail: { drop },
      note: drop ? "worst case: every driver drops out the instant the mains goes; only friction, the motors' detent torque and the Y brake stop the axes"
                 : "the mains goes halfway along a rapid in −y, −z (and +x); the controller stops, the drivers hold the frozen command on their buses' energy until they trip, the Y brake drops in",
      prog: [{ op: "rapid", to: A0 }, { op: "dwell", t: 0.3 }, { op: "feed", to: B0, f: vpath, fail: true }, { op: "dwell", t: 3 }] });
    out.pfail = pf(false);
    out.pfail_drop = pf(true);
    return out;
  }

  // ------------------------------------------------------------------ the planner: lines with trapezoid speeds, cornering by junction deviation
  function plan(P, prog, start, opt) {
    opt = opt || {};
    const ov = opt.feed || 1, acc = opt.acc || 1, ax = P.axes, names = ["X", "Y", "Z"];
    const segs = [];
    let pos = start.slice(), rpm = 0;
    for (const op of prog) {
      if (op.op === "spindle") { rpm = op.rpm; segs.push({ kind: "spindle", rpm }); continue; }
      if (op.op === "dwell") { segs.push({ kind: "dwell", T: op.t, p0: pos.slice(), rpm }); continue; }
      const to = op.to.map((v, i) => Math.max(P.job.lim[i][0], Math.min(P.job.lim[i][1], v)));
      const d = to.map((v, i) => (v - pos[i]) / 1000), L = Math.hypot(...d);
      if (L < 1e-7) continue;
      const u = d.map(v => v / L);
      let vmax = Infinity, a = Infinity;
      names.forEach((n, i) => { if (Math.abs(u[i]) > 1e-9) { vmax = Math.min(vmax, ax[n].v_rapid / Math.abs(u[i])); a = Math.min(a, ax[n].acc * acc / Math.abs(u[i])); } });
      if (op.op === "feed") vmax = Math.min(vmax, op.f * ov / 60);
      segs.push({ kind: op.op, p0: pos.slice(), p1: to, L, u, vmax, a, cut: op.cut || null, rpm, fail: !!op.fail });
      pos = to;
    }
    if (!segs.length) segs.push({ kind: "dwell", T: 0, p0: pos.slice(), rpm });      // nothing to do: a program that stays put
    // junction speeds: zero at stops, type changes and ends; else the junction-deviation limit (grbl's)
    const mv = segs.filter(s => s.kind === "rapid" || s.kind === "feed");
    for (let i = 0; i < segs.length; i++) {
      const s = segs[i]; if (!(s.kind === "rapid" || s.kind === "feed")) continue;
      const n = segs[i + 1];
      s.vj = 0;
      if (n && n.kind === s.kind) {
        const cos = -(s.u[0] * n.u[0] + s.u[1] * n.u[1] + s.u[2] * n.u[2]);
        if (cos < 0.999) {
          const sin2 = Math.sqrt(Math.max(0, (1 - cos) / 2));
          s.vj = Math.min(s.vmax, n.vmax, Math.sqrt(Math.min(s.a, n.a) * P.plan.jd * sin2 / Math.max(1e-6, 1 - sin2)));
        }
      }
    }
    // backward then forward passes, so every segment can reach its exit speed
    let vnext = 0;
    for (let i = segs.length - 1; i >= 0; i--) {
      const s = segs[i]; if (!s.L) { vnext = 0; continue; }
      s.vout = Math.min(s.vj, vnext);
      vnext = Math.min(s.vmax, Math.sqrt(s.vout * s.vout + 2 * s.a * s.L));
      s.vin_max = vnext;
    }
    let vprev = 0, prevKind = null;
    for (const s of segs) {
      if (!s.L) { vprev = 0; prevKind = null; continue; }
      s.vin = prevKind === s.kind ? Math.min(vprev, s.vin_max) : 0;
      s.vout = Math.min(s.vout, Math.sqrt(s.vin * s.vin + 2 * s.a * s.L));
      const vp = Math.min(s.vmax, Math.sqrt((2 * s.a * s.L + s.vin * s.vin + s.vout * s.vout) / 2));
      s.vp = vp;
      s.t1 = (vp - s.vin) / s.a; s.d1 = (vp * vp - s.vin * s.vin) / (2 * s.a);
      s.t3 = (vp - s.vout) / s.a; s.d3 = (vp * vp - s.vout * s.vout) / (2 * s.a);
      s.d2 = Math.max(0, s.L - s.d1 - s.d3); s.t2 = s.d2 / vp;
      s.T = s.t1 + s.t2 + s.t3;
      vprev = s.vout; prevKind = s.kind;
    }
    let t = 0;
    for (const s of segs) { s.t0 = t; t += s.T || 0; if (s.kind === "spindle") s.T = 0; }
    return { segs, T: t, end: pos };
  }
  // reference at time t: position (m), velocity, acceleration, direction, cut, spindle rpm
  function sample(pl, t, cur) {
    const segs = pl.segs;
    let i = cur.i;
    while (i < segs.length - 1 && t >= segs[i].t0 + (segs[i].T || 0)) i++;
    cur.i = i;
    const s = segs[i];
    if (s.kind === "spindle") cur.rpm = s.rpm;
    if (s.rpm !== undefined) cur.rpm = s.rpm;
    if (!s.L) {
      const p = s.p0 || pl.end;
      return { p: p.map(v => v / 1000), v: [0, 0, 0], a: [0, 0, 0], u: [0, 0, 0], cut: null, rpm: cur.rpm, seg: i, speed: 0, done: t >= pl.T, kind: s.kind };
    }
    const tt = Math.min(Math.max(0, t - s.t0), s.T);
    let d, sp, ac;
    if (tt < s.t1) { sp = s.vin + s.a * tt; d = s.vin * tt + 0.5 * s.a * tt * tt; ac = s.a; }
    else if (tt < s.t1 + s.t2) { const q = tt - s.t1; sp = s.vp; d = s.d1 + s.vp * q; ac = 0; }
    else { const q = tt - s.t1 - s.t2; sp = s.vp - s.a * q; d = s.d1 + s.d2 + s.vp * q - 0.5 * s.a * q * q; ac = -s.a; }
    if (t >= s.t0 + s.T) { sp = s.vout; ac = 0; d = s.L; }
    return { p: s.p0.map((v, k) => v / 1000 + s.u[k] * d), v: s.u.map(c => c * sp), a: s.u.map(c => c * ac), u: s.u, cut: s.cut, rpm: cur.rpm,
             seg: i, speed: sp, done: t >= pl.T, kind: s.kind };
  }

  // ------------------------------------------------------------------ diagram layouts (x, y of the block's top-left; optional w, h)
  const LAYOUT = {
    top: { plan: [70, 150, 110, 150], X: [260, 20, 120, 64], Y: [260, 130, 120, 64], Z: [260, 240, 120, 64], struct: [440, 40, 120, 60],
           cutf: [440, 150, 120, 50], spindle: [440, 250, 120, 60], tip: [610, 40, 110, 60], power: [610, 220, 110, 80], scope: [630, 130, 70, 50] },
    plan: { job: [110, 60, 140, 260] },
    axis: { G1: [70, 30], G2: [70, 150], e: [140, 34], ev: [140, 154], ie: [190, 80], kp: [250, 30], ki: [250, 80], kd: [250, 150],
            pid: [320, 85], sat: [370, 80], en: [430, 74, 70, 46], po: [300, 200, 70, 40], util: [400, 200, 90, 40], msum: [520, 84], invJ: [560, 80], wm: [620, 80], thm: [680, 80], bm: [550, 14, 80, 40],
            comp: [530, 200, 100, 50], pw: [650, 170], fric: [380, 270, 90, 40], grav: [380, 330, 90, 34], lsum: [500, 290], invm: [550, 286],
            v: [610, 286], x: [670, 286], rope: [250, 330, 90, 44], cwsum: [130, 330, 96, 44], cwv: [40, 290], cwu: [40, 360], brk: [380, 380, 90, 40] },
    spindle: { w_ref: [70, 40], e: [150, 44], kp: [210, 40], tmax: [210, 120, 100, 44], lim: [330, 40], load: [330, 200, 100, 44], acc: [450, 84],
               invJ: [500, 80], w: [560, 80], rpm: [620, 150], pin: [450, 260, 100, 44], ft: [600, 230, 100, 44] },
    struct: { kx: [60, 30, 80, 40], kz: [60, 200, 80, 40], fx: [180, 30, 100, 44], ax: [320, 30, 90, 44], vx: [450, 34], dx: [510, 34],
              fz: [180, 200, 100, 44], az: [320, 200, 90, 44], vz: [450, 204], dz: [510, 204], fzb: [450, 280, 90, 40] },
    cutf: { split: [200, 60, 90, 70] },
    tip: { pos: [150, 40, 110, 80], err: [350, 40, 110, 150], kin: [150, 230, 110, 120], verr: [350, 240, 110, 150] },
    supply: { drv: [140, 40, 100, 50], psu: [140, 170, 100, 50], net: [300, 110], dv: [360, 106, 90, 44], V: [490, 110], in: [490, 200, 90, 44] },
    power: { grid: [-60, 140, 80, 50], psu_X1: [120, 20, 120, 50], psu_X2: [120, 100, 120, 50], psu_Y: [120, 180, 120, 50], psu_Z: [120, 260, 120, 50], mains: [360, 110, 110, 120] },
  };

  // ------------------------------------------------------------------ the machine model
  function build(P) {
    const M = new Model(P);
    const g = P.g, th = P.tilt * Math.PI / 180;
    M.sys("top", "Tilted-bed CNC router", null, [940, 470]);

    // ---- job and planner: the reference trajectory
    const pl = { plan: null, cur: { i: 0, rpm: 0 }, ref: null };
    M.planner = pl;
    M.sys("plan", "Planner", "top", [700, 360]);
    M.add("plan", { id: "job", type: "src", label: "Job program", sub: "G-code segments", pos: [40, 150], size: [120, 60], in: [],
      out: ["ref.x", "ref.y", "ref.z", "ref.vx", "ref.vy", "ref.vz", "ref.ax", "ref.ay", "ref.az", "ref.ux", "ref.uy", "ref.uz", "ref.cut", "ref.mrr", "ref.rpm", "ref.feed"],
      units: ["m", "m", "m", "m/s", "m/s", "m/s", "m/s²", "m/s²", "m/s²", "", "", "", "", "mm³/s", "rpm", "m/min"],
      f: (u, m) => {
        if (m.fail && m.t >= m.fail.t) {                    // the controller has lost power: no more pulses, the command freezes
          if (!pl.frozen) pl.frozen = Object.assign({}, pl.ref, { v: [0, 0, 0], a: [0, 0, 0], cut: null, rpm: 0, speed: 0 });
          const r = pl.frozen; pl.ref = r;
          return [...r.p, 0, 0, 0, 0, 0, 0, ...r.u, 0, 0, 0, 0];
        }
        const r = sample(pl.plan, m.t, pl.cur); pl.ref = r;
        let mrr = 0;
        if (r.cut) {
          if (r.cut.plunge) mrr = Math.PI / 4 * P.job.tool_d ** 2 * Math.abs(r.v[2]) * 1000;
          else mrr = r.cut.doc * r.cut.woc * Math.hypot(r.v[0], r.v[1]) * 1000;
        }
        return [...r.p, ...r.v, ...r.a, ...r.u, r.cut ? 1 : 0, mrr, r.rpm, r.speed * 60];
      } });

    // ---- spindle: VFD speed loop, power-capped, rotor inertia, losses and the cut
    const SPx = P.spindle;
    M.sys("spindle", "Spindle and VFD", "top", [760, 380]);
    M.add("spindle", { id: "w_ref", type: "gain", k: Math.PI / 30, label: "rpm → rad/s", pos: [60, 60], in: ["ref.rpm"], out: ["sp.w_ref"], units: ["rad/s"] });
    M.add("spindle", { id: "e", type: "sum", signs: "+-", pos: [180, 60], in: ["sp.w_ref", "sp.w"], out: ["sp.e"], units: ["rad/s"] });
    M.add("spindle", { id: "kp", type: "gain", k: SPx.kp, label: "Kp", pos: [260, 60], in: ["sp.e"], out: ["sp.T_cmd"], units: ["N·m"] });
    M.add("spindle", { id: "tmax", type: "fcn", label: "torque limit", sub: "min(T, P_cap / ω)", pos: [260, 170], in: ["sp.w", "pw.ok"], out: ["sp.T_max"], units: ["N·m"],
      f: ([w, ok]) => ok ? Math.min(SPx.T_max, SPx.P_cap / Math.max(Math.abs(w), 50)) : 0 });
    M.add("spindle", { id: "lim", type: "sat", dyn: true, label: "VFD limit", pos: [380, 60], in: ["sp.T_cmd", "sp.T_max"], out: ["sp.T"], units: ["N·m"] });
    M.add("spindle", { id: "load", type: "fcn", label: "loads", sub: "bearings, windage, cut", pos: [380, 260], in: ["sp.w", "ref.mrr"], out: ["sp.T_load", "sp.P_cut"], units: ["N·m", "W"],
      f: ([w, mrr]) => {
        const loss = SPx.P_loss * (Math.abs(w) / SPx.w_rated) ** 2;
        const pc = P.cut.u * mrr;
        return [(loss + pc) / Math.max(Math.abs(w), 50) * Math.sign(w || 1), pc];
      } });
    M.add("spindle", { id: "acc", type: "sum", signs: "+-", pos: [500, 120], in: ["sp.T", "sp.T_load"], out: ["sp.T_net"], units: ["N·m"] });
    M.add("spindle", { id: "invJ", type: "gain", k: 1 / SPx.J, label: "1/J", pos: [580, 120], in: ["sp.T_net"], out: ["sp.alpha"], units: ["rad/s²"] });
    M.add("spindle", { id: "w", type: "int", label: "∫", pos: [660, 120], in: ["sp.alpha"], out: ["sp.w"], units: ["rad/s"] });
    M.add("spindle", { id: "rpm", type: "gain", k: 30 / Math.PI, label: "→ rpm", pos: [660, 220], in: ["sp.w"], out: ["sp.rpm"], units: ["rpm"] });
    M.add("spindle", { id: "pin", type: "fcn", label: "VFD input", sub: "Tω / (η_m η_vfd)", pos: [500, 300], in: ["sp.T", "sp.w"], out: ["sp.P_in"], units: ["W"],
      f: ([T, w]) => Math.max(0, T * w) / (SPx.eta_m * SPx.eta_vfd) + SPx.P_standby });
    M.add("spindle", { id: "ft", type: "fcn", label: "cutting force", sub: "P / (ω r)", pos: [660, 300], in: ["sp.P_cut", "sp.w", "sp.w_ref"], out: ["cut.F"], units: ["N"],
      f: ([pc, w, wr]) => pc > 0 ? P.cut.k_feed * pc / (Math.max(Math.abs(w), 0.2 * Math.abs(wr), 50) * P.cut.r) : 0 });

    // ---- one axis: closed-loop stepper driver, motor, belt / screw / rack compliance, carriage
    const axis = (A, sysLabel, extra) => {
      const a = P.axes[A], s = (n) => A + "." + n;
      M.sys(A, sysLabel, "top", [1000, 470]);
      const G = a.G;                                        // motor rad per metre of travel
      const Jm = a.J_m;                                     // motor side, all motors
      const wc = 2 * Math.PI * P.servo.f_bw, Jt = a.J_servo;
      const Kp = Jt * wc * wc, Kd = 2 * P.servo.zeta * Jt * wc, Ki = Kp * wc * P.servo.ki;
      a.gains = { Kp, Kd, Ki };
      M.add(A, { id: "G1", type: "gain", k: G, label: "G", sub: "rad/m", pos: [60, 50], in: ["ref." + A.toLowerCase()], out: [s("th_ref")], units: ["rad"] });
      M.add(A, { id: "G2", type: "gain", k: G, label: "G", sub: "rad/m", pos: [60, 150], in: ["ref.v" + A.toLowerCase()], out: [s("w_ref")], units: ["rad/s"] });
      M.add(A, { id: "e", type: "sum", signs: "+-", pos: [160, 50], in: [s("th_ref"), s("th_m")], out: [s("e")], units: ["rad"] });
      M.add(A, { id: "ie", type: "int", label: "∫", pos: [230, 100], in: [s("e")], out: [s("ie")], lo: -0.5, hi: 0.5, units: ["rad·s"], x0: () => (a.Td0 || 0) / Ki });   // at rest the loop's integral alone holds the load
      M.add(A, { id: "ev", type: "sum", signs: "+-", pos: [160, 150], in: [s("w_ref"), s("w_m")], out: [s("ev")], units: ["rad/s"] });
      M.add(A, { id: "kp", type: "gain", k: Kp, label: "Kp", pos: [300, 50], in: [s("e")], out: [s("Tp")], units: ["N·m"] });
      M.add(A, { id: "ki", type: "gain", k: Ki, label: "Ki", pos: [300, 100], in: [s("ie")], out: [s("Ti")], units: ["N·m"] });
      M.add(A, { id: "kd", type: "gain", k: Kd, label: "Kd", pos: [300, 150], in: [s("ev")], out: [s("Td")], units: ["N·m"] });
      M.add(A, { id: "pid", type: "sum", signs: "+++", pos: [380, 100], in: [s("Tp"), s("Ti"), s("Td")], out: [s("T_cmd")], units: ["N·m"] });
      M.add(A, { id: "po", type: "lookup", label: "pull-out", sub: "34E1K-120", pos: [380, 230], xs: P.motor.curve.map(c => c[0]), ys: P.motor.curve.map(c => c[1] * a.n_mot),
        xscale: 30 / Math.PI, in: [s("w_m")], out: [s("T_max")], units: ["N·m"] });
      M.add(A, { id: "sat", type: "sat", dyn: true, label: "driver", pos: [470, 100], in: [s("T_cmd"), s("T_max")], out: [s("T_s")], units: ["N·m"] });
      const bus = A === "X" ? "pw.X1.V" : "pw." + A + ".V";
      M.add(A, { id: "en", type: "fcn", label: "output stage", sub: "trips: bus, error", pos: [420, 120], in: [s("T_s"), s("e"), bus, "pw.ok"], out: [s("T_m"), s("ok")], units: ["N·m", ""],
        init: (b) => { b.on = 1; b.why = ""; },
        f: ([T, e, V, ok], m, b) => {
          if (b.on) {
            const why = V < P.power.V_uv ? "bus undervoltage" : V > P.power.V_max ? "bus overvoltage" : Math.abs(e) > P.motor.e_trip ? "position error" :
                        m.fail && m.fail.drop && !ok ? "dropped out with the mains" : "";
            if (why) { b.on = 0; b.why = why; b.t = m.t; }
          }
          return [b.on ? T : 0, b.on];
        } });
      M.add(A, { id: "util", type: "fcn", label: "torque used", sub: "% of pull-out", pos: [470, 170], in: [s("T_cmd"), s("T_max")], out: [s("util")], units: ["%"],
        f: ([T, Tm]) => 100 * Math.abs(T) / Tm });
      // motor rotor
      M.add(A, { id: "msum", type: "sum", signs: "+--", pos: [560, 100], in: [s("T_m"), s("T_r"), s("T_b")], out: [s("T_net")], units: ["N·m"] });
      M.add(A, { id: "invJ", type: "gain", k: 1 / Jm, label: "1/J", sub: "motor", pos: [630, 100], in: [s("T_net")], out: [s("al_m")], units: ["rad/s²"] });
      M.add(A, { id: "wm", type: "int", label: "∫", pos: [700, 100], in: [s("al_m")], out: [s("w_m")], units: ["rad/s"], x0: 0 });
      M.add(A, { id: "thm", type: "int", label: "∫", pos: [770, 100], in: [s("w_m")], out: [s("th_m")], units: ["rad"], x0: () => G * a.x0 });             // at rest the motor sits on its command
      M.add(A, { id: "bm", type: "fcn", label: "drag", sub: "viscous + detent", pos: [630, 30], in: [s("w_m")], out: [s("T_b")], units: ["N·m"],
        f: ([w], m, b) => a.b_m * w + stick(b, "z", w, m.dt, P.motor.T_det * a.n_mot, 0.01, Jm) });
      // transmission: belt, screw or rack, as one spring and damper between motor and carriage
      M.add(A, { id: "comp", type: "fcn", label: a.trans, sub: `k ${(a.k / 1e6).toFixed(0)} N/µm`, pos: [700, 230], size: [120, 56],
        in: [s("th_m"), s("w_m"), s("x"), s("v")], out: [s("F_d"), s("T_r")], units: ["N", "N·m"],
        f: ([thm, wm, x, v], m, b) => {
          const F = a.k * (thm / G - x) + a.c * (wm / G - v);
          // the drive's losses (belt, screw or rack, efficiency eta) as friction on the motor side: F/G (1/eta - 1) while it turns, holding
          // any torque up to that at rest
          return [F, F / G + stick(b, "z", wm, m.dt, Math.abs(F / G) * (1 / a.eta - 1), 0.002, Jm)];
        } });
      // carriage
      M.add(A, { id: "fric", type: "fcn", label: "friction", sub: "blocks, seals, nut", pos: [560, 330], in: [s("v")], out: [s("F_f")], units: ["N"],
        f: ([v], m, b) => stick(b, "z", v, m.dt, a.Fc, 5e-6, a.m) + a.bv * v });
      M.add(A, { id: "grav", type: "const", k: a.grav, label: "gravity", sub: `${a.grav.toFixed(0)} N`, pos: [560, 400], out: [s("F_g")], units: ["N"] });
      const ins = [s("F_d"), s("F_f"), s("F_g"), ...extra.forces];
      M.add(A, { id: "lsum", type: "sum", signs: "+-+" + extra.signs, pos: [700, 360], in: ins, out: [s("F_net")], units: ["N"] });
      M.add(A, { id: "invm", type: "gain", k: 1 / a.m, label: "1/m", sub: `${a.m.toFixed(0)} kg`, pos: [780, 360], in: [s("F_net")], out: [s("a")], units: ["m/s²"] });
      M.add(A, { id: "v", type: "int", label: "∫", pos: [850, 360], in: [s("a")], out: [s("v")], units: ["m/s"] });
      M.add(A, { id: "x", type: "int", label: "∫", pos: [920, 360], in: [s("v")], out: [s("x")], units: ["m"], x0: () => a.x0 - (a.Fd0 || 0) / a.k });   // and the carriage sags by the drive spring's stretch
      M.add(A, { id: "pw", type: "prod", label: "×", sub: "Tω", pos: [920, 230], in: [s("T_m"), s("w_m")], out: [s("P_shaft")], units: ["W"] });
    };
    // structure: the column bending at the head, x (along the sheet) and z (normal to the bed)
    const S = P.struct;
    const kcol = (I, y) => {                                 // column between the X rails, the head at y: k = 3 E I L / (a^2 b^2)
      const a = Math.min(Math.max(y - S.y0, 0.05 * S.L), 0.95 * S.L), b = S.L - a;
      return 3 * S.E * I * S.L / (a * a * b * b);
    };
    axis("X", "X axis: 2 × rack and pinion, 3:1 belt", { forces: ["st.Fx", "cut.Fx"], signs: "+-" });
    // Y with the counterweight on its 2:1 rope
    const CW = P.axes.Y.cw;
    axis("Y", "Y axis: ballscrew, 2:3 belt, counterweight", { forces: ["cw.T", "cut.Fy", "Y.F_brk"], signs: "+--" });
    M.add("Y", { id: "brk", type: "fcn", label: "24 V brake", sub: `${P.axes.Y.brake_F.toFixed(0)} N at the nut`, pos: [380, 390], in: ["Y.v", "pw.brake"], out: ["Y.F_brk"], units: ["N"],
      f: ([v, on], m, b) => stick(b, "z", v, m.dt, on ? P.axes.Y.brake_F : 0, 2e-5, P.axes.Y.m) });
    M.add("Y", { id: "rope", type: "fcn", label: "rope", sub: "2:1, one-sided", pos: [380, 400], in: ["Y.x", "Y.v", "cw.u", "cw.v"], out: ["cw.T"], units: ["N"],
      f: ([x, v, u, vu]) => Math.max(0, CW.T0 + CW.k * (2 * u - x) + CW.c * (2 * vu - v)) });
    M.add("Y", { id: "cwsum", type: "fcn", label: "counterweight", sub: `${CW.m.toFixed(0)} kg`, pos: [230, 400], in: ["cw.T", "cw.v"], out: ["cw.a"], units: ["m/s²"],
      f: ([T, vu]) => (CW.m * g * Math.cos(th) - 2 * T - CW.Fc * Math.tanh(vu / 0.002)) / CW.m });
    M.add("Y", { id: "cwv", type: "int", label: "∫", pos: [100, 330], in: ["cw.a"], out: ["cw.v"], units: ["m/s"] });
    M.add("Y", { id: "cwu", type: "int", label: "∫", pos: [100, 400], in: ["cw.v"], out: ["cw.u"], units: ["m"], x0: () => (P.axes.Y.x0 - (P.axes.Y.Fd0 || 0) / P.axes.Y.k) / 2 });
    axis("Z", "Z axis: ballscrew, 1:2 belt", { forces: ["st.Fz", "cut.Fz"], signs: "--" });

    // cutting force along the feed, split onto the axes
    M.sys("cutf", "Cutting force", "top", [520, 260]);
    M.add("cutf", { id: "split", type: "fcn", label: "resolve", sub: "−F · u", pos: [200, 110], in: ["cut.F", "ref.ux", "ref.uy", "ref.uz"], out: ["cut.Fx", "cut.Fy", "cut.Fz"], units: ["N", "N", "N"],
      f: ([F, ux, uy, uz]) => [F * ux, F * uy, F * uz] });

    M.sys("struct", "Structure: column bending at the head", "top", [900, 440]);
    M.add("struct", { id: "kx", type: "fcn", label: "k_x(y)", sub: "3EIL/a²b²", pos: [60, 60], in: ["Y.x"], out: ["st.kx"], units: ["N/m"], f: ([y]) => kcol(S.Ix, y) });
    M.add("struct", { id: "kz", type: "fcn", label: "k_z(y)", sub: "column + blocks", pos: [60, 260], in: ["Y.x"], out: ["st.kz"], units: ["N/m"],
      f: ([y]) => 1 / (1 / kcol(S.Iz, y) + 1 / S.k_blocks_z) });
    M.add("struct", { id: "fx", type: "fcn", label: "spring + damper", sub: "head on the column", pos: [230, 60], in: ["st.dx", "st.vx", "st.kx"], out: ["st.Fx"], units: ["N"],
      f: ([d, v, k]) => S.off ? 0 : k * d + 2 * S.zeta * Math.sqrt(k * S.mx) * v });
    M.add("struct", { id: "ax", type: "fcn", label: "head, x", sub: `${S.mx.toFixed(0)} kg`, pos: [420, 60], in: ["st.Fx", "X.a"], out: ["st.ax"], units: ["m/s²"],
      f: ([F, aX]) => -F / S.mx - aX });
    M.add("struct", { id: "vx", type: "int", label: "∫", pos: [560, 60], in: ["st.ax"], out: ["st.vx"], units: ["m/s"] });
    M.add("struct", { id: "dx", type: "int", label: "∫", pos: [640, 60], in: ["st.vx"], out: ["st.dx"], units: ["m"] });
    M.add("struct", { id: "fz", type: "fcn", label: "spring + damper", sub: "normal to the bed", pos: [230, 260], in: ["st.dz", "st.vz", "st.kz"], out: ["st.Fzs"], units: ["N"],
      f: ([d, v, k]) => k * d + 2 * S.zeta * Math.sqrt(k * S.mz) * v });
    M.add("struct", { id: "az", type: "fcn", label: "head, z", sub: `${S.mz.toFixed(0)} kg`, pos: [420, 260], in: ["st.Fzs", "Z.F_d"], out: ["st.az"], units: ["m/s²"],
      f: ([F, Fd]) => (-F - Fd) / S.mz });
    M.add("struct", { id: "vz", type: "int", label: "∫", pos: [560, 260], in: ["st.az"], out: ["st.vz"], units: ["m/s"] });
    M.add("struct", { id: "dz", type: "int", label: "∫", pos: [640, 260], in: ["st.vz"], out: ["st.dz"], units: ["m"],
      x0: () => -(P.axes.Z.Fd0 || 0) / (1 / (1 / kcol(S.Iz, P.axes.Y.x0) + 1 / S.k_blocks_z)) });
    // the Z carriage rides on the head: its base accelerates with the head's z-deflection
    M.add("struct", { id: "fzb", type: "fcn", label: "base force", sub: "−m_z a_head", pos: [760, 260], in: ["st.az"], out: ["st.Fz"], units: ["N"],
      f: ([az]) => S.off ? 0 : P.axes.Z.m * az });

    // tool tip: where the cutter is, against where the program wants it
    M.sys("tip", "Tool tip error", "top", [760, 300]);
    M.add("tip", { id: "pos", type: "fcn", label: "tool tip", sub: "carriages + column", pos: [120, 90], in: ["X.x", "st.dx", "Y.x", "Z.x", "st.dz"], out: ["tip.x", "tip.y", "tip.z"], units: ["m", "m", "m"],
      f: ([x, dx, y, z, dz]) => [x + dx, y, z + dz] });
    M.add("tip", { id: "err", type: "fcn", label: "error", sub: "lag and contour", pos: [380, 140], size: [120, 70],
      in: ["tip.x", "tip.y", "tip.z", "ref.x", "ref.y", "ref.z", "ref.ux", "ref.uy", "ref.uz"],
      out: ["tip.ex", "tip.ey", "tip.ez", "tip.contour"], units: ["µm", "µm", "µm", "µm"],
      f: ([x, y, z, rx, ry, rz, ux, uy, uz]) => {
        const e = [x - rx, y - ry, z - rz], d = e[0] * ux + e[1] * uy + e[2] * uz;
        const c = Math.hypot(e[0] - d * ux, e[1] - d * uy, e[2] - d * uz);
        return [e[0] * 1e6, e[1] * 1e6, e[2] * 1e6, c * 1e6];
      } });

    // the tool tip's velocity and acceleration: the carriages' plus the column's bending at the head; and their errors
    M.add("tip", { id: "kin", type: "fcn", label: "tip motion", sub: "carriages + column", pos: [150, 220], size: [110, 110],
      in: ["X.v", "st.vx", "Y.v", "Z.v", "st.vz", "X.a", "st.ax", "Y.a", "Z.a", "st.az"],
      out: ["tip.vx", "tip.vy", "tip.vz", "tip.ax", "tip.ay", "tip.az"], units: ["m/s", "m/s", "m/s", "m/s²", "m/s²", "m/s²"],
      f: ([vX, vx, vY, vZ, vz, aX, ax, aY, aZ, az]) => [vX + vx, vY, vZ + vz, aX + ax, aY, aZ + az] });
    M.add("tip", { id: "verr", type: "fcn", label: "motion error", sub: "actual − programmed", pos: [350, 240], size: [110, 130],
      in: ["tip.vx", "tip.vy", "tip.vz", "tip.ax", "tip.ay", "tip.az", "ref.vx", "ref.vy", "ref.vz", "ref.ax", "ref.ay", "ref.az"],
      out: ["tip.evx", "tip.evy", "tip.evz", "tip.eax", "tip.eay", "tip.eaz"], units: ["m/s", "m/s", "m/s", "m/s²", "m/s²", "m/s²"],
      f: (u) => [u[0] - u[6], u[1] - u[7], u[2] - u[8], u[3] - u[9], u[4] - u[10], u[5] - u[11]] });

    // ---- power: each motor's driver and 60 V supply, the spindle's VFD, the mains
    const PW = P.power;
    M.sys("power", "Power", "top", [900, 440]);
    M.add("power", { id: "grid", type: "src", label: "mains", sub: "fails at t_f", pos: [20, 360], out: ["pw.ok", "pw.brake"], units: ["", ""],
      f: (u, m) => { const f = m.fail; if (!f || m.t < f.t) return [1, 0]; return [0, m.t >= f.t + P.fail.brake_delay ? 1 : 0]; } });
    const supply = (id, label, Tsig, Psig, share, y) => {
      const s = (n) => "pw." + id + "." + n;
      M.sys("pw" + id, label, "power", [900, 360]);
      M.add("pw" + id, { id: "drv", type: "fcn", label: "driver", sub: "Tω + 2I²R", pos: [140, 80], size: [120, 60], in: [Tsig, Psig, Tsig[0] + ".ok"], out: [s("P_drv"), s("I")], units: ["W", "A"],
        f: ([T, Pm, on]) => {
          if (!on) return [0, 0];
          const I = Math.max(P.motor.I_idle, Math.min(P.motor.I_peak, Math.abs(T * share) / P.motor.Kt));
          const pm = Pm * share;
          return [(pm > 0 ? pm / PW.eta_drv : pm * PW.regen) + 2 * I * I * P.motor.R + PW.drv_idle, I];
        } });
      M.add("pw" + id, { id: "psu", type: "fcn", label: "60 V supply", sub: `${PW.psu_w} W, no sink`, pos: [140, 230], size: [120, 60], in: [s("V"), "pw.ok"], out: [s("P_psu")], units: ["W"],
        f: ([V, ok]) => ok ? Math.max(0, Math.min(PW.psu_peak, PW.G * (PW.V_set - V))) : 0 });
      M.add("pw" + id, { id: "net", type: "sum", signs: "+-", pos: [380, 160], in: [s("P_psu"), s("P_drv")], out: [s("P_net")], units: ["W"] });
      M.add("pw" + id, { id: "dv", type: "fcn", label: "bus capacitor", sub: `${(PW.C * 1e6).toFixed(0)} µF`, pos: [500, 160], in: [s("P_net"), s("V")], out: [s("dV")], units: ["V/s"],
        f: ([p, V]) => p / (PW.C * Math.max(V, 5)) });
      M.add("pw" + id, { id: "V", type: "int", label: "∫", pos: [640, 160], in: [s("dV")], out: [s("V")], units: ["V"], x0: PW.V_set });
      M.add("pw" + id, { id: "in", type: "fcn", label: "mains side", sub: "P / η + idle", pos: [640, 290], in: [s("P_psu")], out: [s("P_in")], units: ["W"],
        f: ([p]) => p / PW.eta_psu + PW.psu_idle });
      M.add("power", { id: "psu_" + id, type: "sub", child: "pw" + id, label, pos: [120, y], size: [150, 54] });
    };
    supply("X1", "Supply X1", "X.T_m", "X.P_shaft", 0.5, 30);
    supply("X2", "Supply X2", "X.T_m", "X.P_shaft", 0.5, 120);
    supply("Y", "Supply Y", "Y.T_m", "Y.P_shaft", 1, 210);
    supply("Z", "Supply Z", "Z.T_m", "Z.P_shaft", 1, 300);
    M.add("power", { id: "mains", type: "fcn", label: "mains current", sub: "Σ P / (V · PF)", pos: [500, 180], size: [130, 70],
      in: ["pw.X1.P_in", "pw.X2.P_in", "pw.Y.P_in", "pw.Z.P_in", "sp.P_in", "pw.ok"], out: ["pw.I_mains", "pw.P_mains"], units: ["A", "W"],
      f: ([a, b, c, d, vfd, ok]) => {
        if (!ok) return [0, 0];
        const aux = a + b + c + d + PW.aux_w;
        return [(aux / PW.pf_aux + vfd / PW.pf_vfd) / PW.mains_v, aux + vfd];
      } });

    // ---- top level: the subsystems, as Simulink draws them
    const top = (id, child, label, pos, size) => M.add("top", { id, type: "sub", child, label, pos, size: size || [150, 70] });
    top("plan", "plan", "Planner", [40, 190], [130, 130]);
    top("X", "X", "X axis", [300, 40]);
    top("Y", "Y", "Y axis", [300, 180]);
    top("Z", "Z", "Z axis", [300, 320]);
    top("spindle", "spindle", "Spindle + VFD", [520, 360], [150, 70]);
    top("cutf", "cutf", "Cutting force", [520, 250], [140, 60]);
    top("struct", "struct", "Structure", [520, 110], [150, 70]);
    top("tip", "tip", "Tool tip", [760, 60], [130, 70]);
    top("power", "power", "Power", [760, 300], [130, 90]);
    M.add("top", { id: "scope", type: "scope", label: "Scopes", pos: [790, 190], size: [80, 56], in: ["tip.contour", "pw.I_mains"] });
    // where each block sits in its diagram: [x, y, w, h] (the axes share one layout, as do the four supplies)
    for (const b of M.blocks) {
      const key = ["X", "Y", "Z"].includes(b.sys) ? "axis" : b.sys.startsWith("pw") && b.sys !== "power" ? "supply" : b.sys;
      const L = (LAYOUT[key] || {})[b.id];
      if (L) { b.pos = [L[0], L[1]]; if (L[2]) b.size = [L[2], L[3]]; }
    }
    M.finish();
    return M;
  }

  // ------------------------------------------------------------------ running: a job, with the measures the requirements read
  function Run(P, jobKey, opt) {
    opt = opt || {};
    const J = jobs(P);
    const job = J[jobKey] || opt.custom;
    const start = opt.start || P.job.park;
    // start at rest, each axis already holding its own weight (and the Y counterweight's pull)
    for (const A of ["X", "Y", "Z"]) {
      const a = P.axes[A];
      a.x0 = start["XYZ".indexOf(A)] / 1000;
      a.Fd0 = a.Fd0_test ?? -(a.grav + (A === "Y" ? a.cw.T0 : 0));
      a.Td0 = a.Td0_test ?? a.Fd0 / a.G;
    }
    const M = build(P);
    M.planner.plan = plan(P, job.prog, start, opt);
    M.planner.cur = { i: 0, rpm: 0 };
    if (job.fail) {
      const sg = M.planner.plan.segs.find(q => q.fail);
      M.fail = { t: sg.t0 + sg.T / 2, drop: job.fail.drop, seg: sg };
    }
    M.reset();
    // settle the Y counterweight rope and integrators at rest: start each axis holding its own weight
    M.v[M.index.get("cw.T")] = P.axes.Y.cw.T0;
    return { M, job, T: M.planner.plan.T + 0.6 };
  }
  // the measures, kept as the run goes: worst cases and windows
  function Meter(P) {
    const n100 = Math.round(0.1 / P.dt), n1 = Math.round(1 / P.dt);
    const box = (n) => ({ n, buf: new Float64Array(n), i: 0, sum: 0, full: false,
      push(x) { this.sum += x - this.buf[this.i]; this.buf[this.i] = x; this.i = (this.i + 1) % this.n; if (!this.i) this.full = true; return this.sum / (this.full ? this.n : Math.max(1, this.i)); } });
    return { psu: { X1: box(n100), X2: box(n100), Y: box(n100), Z: box(n100) }, mains: box(n1),
      r: { contour: 0, contour_at: 0, rope_min: 1e9, rope_max: 0, fail: null, util: { X: 0, Y: 0, Z: 0 }, util_at: { X: 0, Y: 0, Z: 0 }, sat_s: 0,
           psu: { X1: 0, X2: 0, Y: 0, Z: 0 }, vbus: 0, vbus_min: 1e9, mains_1s: 0, mains_peak: 0, mains_sum: 0, n: 0, droop: 0, cut_s: 0,
           steady: { X: [], Y: [], Z: [] }, t: 0 } };
  }
  function measure(M, me, P) {
    const v = M.v, ix = (n) => v[M.index.get(n)], r = me.r, t = M.t;
    const ref = M.planner.ref;
    if (ref && ref.cut && !ref.cut.plunge && ref.speed > 0.5 * P.job.feed / 60) {
      const c = ix("tip.contour"); if (c > r.contour) { r.contour = c; r.contour_at = t; }
      r.cut_s += M.dt;
      const wr = ix("sp.w_ref"); if (wr > 0) r.droop = Math.max(r.droop, (wr - ix("sp.w")) / wr);
    }
    for (const A of ["X", "Y", "Z"]) {
      const u = Math.abs(ix(A + ".T_cmd")) / ix(A + ".T_max");
      if (u > r.util[A]) { r.util[A] = u; r.util_at[A] = t; }
      // steady speed, no acceleration: the torque to compare with the hand calculation
      if (ref && ref.kind === "rapid" && Math.abs(ref.a["XYZ".indexOf(A)]) < 1e-9 && Math.abs(ref.v["XYZ".indexOf(A)]) > 0.9 * P.axes[A].v_rapid && t > 0.3)
        r.steady[A].push([ix(A + ".T_m"), ref.v["XYZ".indexOf(A)]]);
    }
    for (const k of ["X1", "X2", "Y", "Z"]) {
      const a = me.psu[k].push(ix("pw." + k + ".P_psu")); if (a > r.psu[k]) r.psu[k] = a;
      const V = ix("pw." + k + ".V"); if (V > r.vbus) r.vbus = V; if (V < r.vbus_min) r.vbus_min = V;
    }
    const T = ix("cw.T"); if (T < r.rope_min) r.rope_min = T; if (T > r.rope_max) r.rope_max = T;
    if (M.fail) {
      const F = r.fail || (r.fail = null);
      if (t >= M.fail.t) {
        if (!r.fail) {
          r.fail = { t: M.fail.t, drop: M.fail.drop, x0: [ix("X.x"), ix("Y.x"), ix("Z.x")], v0: [ix("X.v"), ix("Y.v"), ix("Z.v")], tip0: ix("tip.z"),
                     run: [0, 0, 0], tip_min: ix("tip.z"), rope_min: T, rope_max: T, vbus: 0, trips: {}, stop: [null, null, null], xs: [0, 0, 0] };
        }
        const f = r.fail, x = [ix("X.x"), ix("Y.x"), ix("Z.x")], v = [ix("X.v"), ix("Y.v"), ix("Z.v")];
        for (let i = 0; i < 3; i++) {
          const d = (x[i] - f.x0[i]) * Math.sign(f.v0[i] || 1);
          if (d > f.run[i]) f.run[i] = d;
          if (f.stop[i] === null && Math.abs(v[i]) < 1e-4 && t > f.t + 0.02) f.stop[i] = t - f.t;
          f.xs[i] = x[i];                                     // where it is at the end, for the creep
        }
        if (t >= f.t + 2 && !f.x2) f.x2 = x.slice();
        f.tip_min = Math.min(f.tip_min, ix("tip.z"));
        f.rope_min = Math.min(f.rope_min, T); f.rope_max = Math.max(f.rope_max, T);
        for (const k of ["X1", "X2", "Y", "Z"]) f.vbus = Math.max(f.vbus, ix("pw." + k + ".V"));
        for (const b of M.blocks) if (b.id === "en" && !b.on && !(b.sys in f.trips)) f.trips[b.sys] = { t: +(b.t - f.t).toFixed(4), why: b.why };
      }
    }
    const I = ix("pw.I_mains"), Ia = me.mains.push(I);
    if (Ia > r.mains_1s) r.mains_1s = Ia; if (I > r.mains_peak) r.mains_peak = I;
    r.mains_sum += I; r.n++; r.t = t;
  }
  function runAll(P, keys) {                                 // under Node: every job to its end, the measures
    const out = {};
    for (const k of keys || Object.keys(jobs(P))) {
      const R = Run(P, k, {}), me = Meter(P);
      const steps = Math.ceil(R.T / P.dt);
      for (let i = 0; i < steps; i++) { R.M.step(); measure(R.M, me, P); }
      const r = me.r; r.mains_avg = r.mains_sum / r.n; r.T = R.T;
      for (const A of ["X", "Y", "Z"]) {
        const s = r.steady[A]; r.steady[A] = s.length ? { T: s.reduce((a, q) => a + Math.abs(q[0]), 0) / s.length, n: s.length, up: s.filter(q => q[1] > 0).length } : null;
        const a = P.axes[A]; r.tip_end = r.tip_end || {};
        r.tip_end[A] = (R.M.get(A + ".x") - R.M.planner.plan.end["XYZ".indexOf(A)] / 1000) * 1e6;
      }
      r.modes = modes(P);
      out[k] = r;
    }
    return out;
  }
  // natural frequencies, for the diagram and the requirement: each drive on its spring, the column at mid-height, the rope
  function modes(P) {
    const f = (k, m) => Math.sqrt(k / m) / (2 * Math.PI), S = P.struct;
    const mid = (I) => 48 * S.E * I / S.L ** 3;
    const out = {};
    for (const A of ["X", "Y", "Z"]) { const a = P.axes[A]; const mr = 1 / (1 / a.m + 1 / (a.J_m * a.G * a.G)); out["drive " + A] = f(a.k, mr); }
    out["column x"] = f(mid(S.Ix), S.mx);
    out["column z"] = f(1 / (1 / mid(S.Iz) + 1 / S.k_blocks_z), S.mz);
    out["counterweight rope"] = f(P.axes.Y.cw.k * 4, P.axes.Y.cw.m);
    return out;
  }

  // ------------------------------------------------------------------ verification: the model against answers known without it
  const clone = (o) => JSON.parse(JSON.stringify(o));
  function idle(P, T) { return { label: "idle", prog: [{ op: "dwell", t: T }] }; }
  // a drive alone, lossless and loop open, released with its spring loaded: it should ring at the two-mass frequency and keep its energy
  function freeDrive(P, A) {
    const Q = clone(P);
    for (const B of ["X", "Y", "Z"]) { const b = Q.axes[B]; b.Fc = 0; b.bv = 0; b.b_m = 0; b.grav = 0; b.eta = 1; b.c = 0; b.Fd0_test = 0; b.Td0_test = 0; }
    Q.axes.Y.cw.k = 0; Q.axes.Y.cw.T0 = 0; Q.axes.Y.cw.c = 0; Q.motor.T_det = 0; Q.servo.f_bw = 1e-9; Q.struct.off = true;
    const a = Q.axes[A]; a.Fd0_test = 1000; a.Td0_test = 0;
    const R = Run(Q, null, { custom: idle(Q, 1.2) }), M = R.M, ix = (n) => M.index.get(n);
    const iF = ix(A + ".F_d"), iv = ix(A + ".v"), iw = ix(A + ".w_m"), ith = ix(A + ".th_m"), ixx = ix(A + ".x");
    const E = () => { const v = M.v, d = v[ith] / a.G - v[ixx]; return 0.5 * a.m * v[iv] ** 2 + 0.5 * a.J_m * v[iw] ** 2 + 0.5 * a.k * d * d; };
    const cross = [], e = [];
    let prev = M.v[iF];
    const n = Math.round(1.0 / Q.dt);
    for (let i = 0; i < n; i++) { M.step(); const F = M.v[iF]; if (prev > 0 && F <= 0) cross.push(M.t - Q.dt * F / (F - prev)); prev = F; e.push(E()); }
    const f = (cross.length - 1) / (cross[cross.length - 1] - cross[0]);
    const want = Math.sqrt(a.k * (1 / a.m + 1 / (a.J_m * a.G * a.G))) / (2 * Math.PI);
    const tenth = Math.floor(e.length / 10), avg = (q) => q.reduce((s, x) => s + x, 0) / q.length;
    const e0 = avg(e.slice(0, tenth)), e1 = avg(e.slice(-tenth));
    return { f, want, freq_err: Math.abs(f / want - 1) * 100, energy_drift: Math.abs(e1 / e0 - 1) * 100, E0: e0 };
  }
  // one axis at a steady speed: the motor torque should be the load force through the drive plus the motor's own drag
  function steadyTorque(P, A) {
    const Q = clone(P), a = Q.axes[A], i = "XYZ".indexOf(A), lim = Q.job.lim[i];
    const start = Q.job.park.slice(); start[i] = lim[0] + 20;
    const to = start.slice(); to[i] = lim[1] - 20;
    const R = Run(Q, null, { custom: { label: "steady", prog: [{ op: "rapid", to }] }, start }), M = R.M, ix = (n) => M.v[M.index.get(n)];
    const v = a.v_rapid, tAcc = v / a.acc + 0.4, tEnd = R.M.planner.plan.T - v / a.acc - 0.05;
    let sum = 0, n = 0;
    while (M.t < tEnd) { M.step(); if (M.t > tAcc) { sum += ix(A + ".T_m"); n++; } }
    const F = a.Fc + a.bv * v - a.grav - (A === "Y" ? a.cw.T0 - a.cw.Fc / 2 : 0);
    const want = F / a.G / a.eta + a.b_m * a.G * v + Q.motor.T_det * a.n_mot;
    const got = sum / n;
    return { got, want, err: Math.abs(got / want - 1) * 100 };
  }
  // left alone where it starts, nothing should move: the model starts in equilibrium
  function atRest(P) {
    const Q = clone(P), R = Run(Q, null, { custom: idle(Q, 0.5) }), M = R.M, ix = (n) => M.v[M.index.get(n)];
    M.step();
    const p0 = [ix("tip.x"), ix("tip.y"), ix("tip.z")];      // where it sits, sag under its own weight included
    let worst = 0;
    while (M.t < 0.5) { M.step(); worst = Math.max(worst, ...[ix("tip.x"), ix("tip.y"), ix("tip.z")].map((x, i) => Math.abs(x - p0[i]) * 1e6)); }
    return { worst_um: worst, sag_um: Math.abs(ix("tip.ez")) };
  }
  // halving the step should not change the answers
  function convergence(P, base) {
    const Q = clone(P); Q.dt = P.dt / 2;
    const keys = ["rapids", "pocket", "pfail_drop"], half = runAll(Q, keys), out = {};
    const pick = { contour: (r) => r.contour, util: (r) => r.fail ? null : Math.max(...Object.values(r.util)) * 100, vbus: (r) => r.vbus,
                   rope_min: (r) => r.rope_min, x_run: (r) => r.fail ? r.fail.run[0] * 1000 : null };
    for (const k of keys) for (const [m, f] of Object.entries(pick)) {
      const a = f(base[k]), b = f(half[k]);
      if (a == null || b == null || Math.abs(a) < 1e-6) continue;
      out[`${k}: ${m}`] = { dt: a, half: b, change: Math.abs(b / a - 1) * 100 };
    }
    return out;
  }
  function verify(P, base) {
    const out = { drive: {}, steady: {}, rest: atRest(P), conv: convergence(P, base) };
    for (const A of ["X", "Y", "Z"]) { out.drive[A] = freeDrive(P, A); out.steady[A] = steadyTorque(P, A); }
    return out;
  }

  // ------------------------------------------------------------------ the requirements' worst cases, for the sensitivity sweep
  function checks(P, R) {
    const L = P.limits, run = Object.keys(R).filter(k => !k.startsWith("pfail") && !k.startsWith("_")), all = Object.keys(R).filter(k => !k.startsWith("_"));
    const fails = all.filter(k => k.startsWith("pfail")), cut = ["profile", "pocket"].filter(k => R[k]);
    const mx = (ks, f) => Math.max(...ks.map(f)), mn = (ks, f) => Math.min(...ks.map(f));
    const c = {};
    c.R69 = { v: mx(cut, k => R[k].contour), lim: L.contour, op: "<=" };
    c.R70 = { v: mx(run, k => Math.max(...Object.values(R[k].util)) * 100), lim: 80, op: "<=" };
    c.R71 = { v: mx(all, k => Math.max(...Object.values(R[k].psu))), lim: P.power.psu_w, op: "<=" };
    c.R72 = { v: mx(all, k => R[k].vbus), lim: 0.9 * P.power.V_max, op: "<=" };
    c.R73 = { v: mx(all, k => R[k].mains_1s), lim: L.mains, op: "<=" };
    c.R74 = { v: mx(cut, k => R[k].droop * 100), lim: 10, op: "<=" };
    const md = R[all[0]].modes;
    c.R75 = { v: Math.min(...Object.entries(md).filter(([k]) => k !== "counterweight rope").map(([, f]) => f / P.servo.f_bw)), lim: 2.5, op: ">=" };
    c.R76 = { v: mn(run, k => R[k].rope_min / P.axes.Y.cw.T0 * 100), lim: 50, op: ">=" };
    const over = (F, i) => { const A = "XYZ"[i], v = Math.abs(F.v0[i]); return L.overrun[A] - Math.max(0, F.run[i] - v * v / (2 * P.axes[A].acc)) * 1000; };
    ["X", "Y", "Z"].forEach((A, i) => { c["R77 " + A] = { v: mn(fails, k => over(R[k].fail, i)), lim: 0, op: ">=", unit: "mm to spare" }; });
    c.R78 = { v: mn(fails, k => L.rope_mbl / Math.max(1, R[k].fail.rope_max)), lim: 5, op: ">=" };
    c.R79 = { v: mx(fails, k => Math.max(...[0, 1, 2].map(i => R[k].fail.x2 ? Math.abs(R[k].fail.xs[i] - R[k].fail.x2[i]) * 1000 : 0))), lim: 0.01, op: "<=" };
    for (const q of Object.values(c)) q.ok = q.op === "<=" ? q.v <= q.lim : q.v >= q.lim;
    return c;
  }
  // the guesses, each run at half and double
  const VARIATIONS = [
    ["drive stiffness (belts, rack, screws)", (Q, f) => { for (const a of Object.values(Q.axes)) { a.k *= f; a.c *= Math.sqrt(f); } }],
    ["drive damping", (Q, f) => { for (const a of Object.values(Q.axes)) a.c *= f; }],
    ["carriage friction (blocks, seals, nuts)", (Q, f) => { for (const a of Object.values(Q.axes)) a.Fc *= f; }],
    ["viscous drag", (Q, f) => { for (const a of Object.values(Q.axes)) a.bv *= f; }],
    ["drivers' position-loop bandwidth", (Q, f) => { Q.servo.f_bw *= f; }],
    ["motor detent torque", (Q, f) => { Q.motor.T_det *= f; }],
    ["bus capacitance", (Q, f) => { Q.power.C *= f; }],
    ["drivers' undervoltage trip", (Q, f) => { Q.power.V_uv *= f; }],
    ["Y brake delay", (Q, f) => { Q.fail.brake_delay *= f; }],
    ["counterweight rope stiffness", (Q, f) => { Q.axes.Y.cw.k *= f; Q.axes.Y.cw.c *= Math.sqrt(f); }],
    ["column damping", (Q, f) => { Q.struct.zeta *= f; }],
    ["bearing blocks' stiffness, normal to the bed", (Q, f) => { Q.struct.k_blocks_z *= f; }],
    ["spindle inertia", (Q, f) => { Q.spindle.J *= f; }],
    ["spindle bearing and windage losses", (Q, f) => { Q.spindle.P_loss *= f; }],
    ["cutting feed force", (Q, f) => { Q.cut.k_feed *= f; }],
  ];
  function sweep(P, which) {
    const out = [];
    for (const i of which) {
      const [name, fn] = VARIATIONS[Math.floor(i / 2)], f = i % 2 ? 2 : 0.5, Q = clone(P);
      fn(Q, f);
      out.push({ i, name, f, checks: checks(Q, runAll(Q)) });
    }
    return out;
  }

  const api = { build, jobs, plan, sample, Run, Meter, measure, runAll, modes, interp, verify, checks, sweep, VARIATIONS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.CNCSIM = api;
})(typeof self !== "undefined" ? self : this);

// under Node: node sim.js params.json -> the measures of every job, as JSON
if (typeof require !== "undefined" && typeof module !== "undefined" && require.main === module) {
  const P = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
  const t0 = Date.now(), S = module.exports;
  if (process.argv[3] === "sweep") {                          // node sim.js P.json sweep 0,1,2 -> those variations' worst cases
    process.stdout.write(JSON.stringify(S.sweep(P, process.argv[4].split(",").map(Number))));
  } else if (process.argv[3] === "base") {                    // node sim.js P.json base -> the unvaried worst cases
    process.stdout.write(JSON.stringify(S.checks(P, S.runAll(P))));
  } else {
    const out = S.runAll(P);
    out._ms = Date.now() - t0;
    out._verify = S.verify(P, out);
    out._checks = S.checks(P, out);
    out._ms_verify = Date.now() - t0 - out._ms;
    process.stdout.write(JSON.stringify(out));
  }
}
