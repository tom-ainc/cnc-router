// flex.js: cable chains, cables and hoses, and ropes that re-lay themselves as the axes move.
// A component of the page framework (core.js), drawn with golf's viewer: each chain is one mesh of its links, each
// cable and rope a tube. Its data is in viewer_data.json:
//   V.chains  [{name, group, var (the axis that drives it), m_off, m_min, f, F, d, n, w, R, sg, h, W, pitch, L, N, info}]
//   V.cables  [{name, od, info, pts: [[x, y, z, group] or ["chain", chain name]]}]
//   V.ropes   [{name, r, info, colour, pts: [[x, y, z, group]]}]
// Points are in their group's frame; the core moves them with the pose.
(function () {
  const comp = { id: "flex" };
  Page.component(comp);
  comp.init = function (P) {
  const { V, pose, toWorld, addShapes } = P;
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

  // ---- cable chains: link by link, re-laid every time an axis moves
  // one link: two side plates and two cross bars, as boxes in the link's frame (x along the chain, y across it)
  function box(x0, x1, y0, y1, z0, z1, P, T) {
    const o = P.length / 3;
    for (const x of [x0, x1]) for (const y of [y0, y1]) for (const z of [z0, z1]) P.push(x, y, z);
    // corners: index = 4*ix + 2*iy + iz
    [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]
      .forEach(([a, b, c, d]) => T.push(o + a, o + b, o + c, o + a, o + c, o + d));
  }
  function linkShape(c) {
    const p = c.pitch, L = 0.8 * p, t = 3, h = c.h, Wd = c.W, P = [], T = [];
    box(-L / 2, L / 2, 0, t, -h / 2, h / 2, P, T); box(-L / 2, L / 2, Wd - t, Wd, -h / 2, h / 2, P, T);
    box(-0.2 * p, 0.2 * p, t - 0.5, Wd - t + 0.5, h / 2 - t, h / 2 - 0.3, P, T); box(-0.2 * p, 0.2 * p, t - 0.5, Wd - t + 0.5, -h / 2 + 0.3, -h / 2 + t, P, T);
    return { P, T };
  }
  function chainPoint(c, m, s) {
    const b = c.f + 30 + ((c.sg || 1) * m - c.m_min) / 2, a = b - c.f, R = c.R, F = c.F, d = c.d, n = c.n;
    if (s <= a) return [[0, 1, 2].map(i => F[i] + d[i] * s), d];
    if (s <= a + Math.PI * R) {
      const ph = (s - a) / R;
      const cen = [0, 1, 2].map(i => F[i] + d[i] * a + n[i] * R);
      return [[0, 1, 2].map(i => cen[i] - n[i] * R * Math.cos(ph) + d[i] * R * Math.sin(ph)),
              [0, 1, 2].map(i => d[i] * Math.cos(ph) + n[i] * Math.sin(ph))];
    }
    const u = s - a - Math.PI * R;
    return [[0, 1, 2].map(i => F[i] + d[i] * a + n[i] * 2 * R - d[i] * u), d.map(v => -v)];
  }
  // each link is a body of its own, placed every time the chain re-lays: "<chain>.<i>", so the chain's name picks them all
  const R = P.rot;
  const chains = (V.chains || []).map(c => {
    const link = linkShape(c);
    V.parts[c.name] = { info: c.info + " | " + c.N + " links, " + Math.round(c.L) + " mm", kind: "bought", group: c.group };
    for (let i = 0; i < c.N; i++) P.addBody(`${c.name}.${i}`, { positions: link.P, triangles: link.T, color: "#2b2f34" });
    return { c, link };
  });
  function placeChain({ c }) {
    const m = pose[c.var] + c.m_off, w = c.w;
    for (let i = 0; i < c.N; i++) {
      const [p, t] = chainPoint(c, m, i * c.L / (c.N - 1));
      const z = [t[1] * w[2] - t[2] * w[1], t[2] * w[0] - t[0] * w[2], t[0] * w[1] - t[1] * w[0]];
      // the link's axes in the world: the frame's rotation of (t, w, z) as columns
      const a = R(t), b = R(w), d = R(z);
      P.placeBody(`${c.name}.${i}`, toWorld(p, c.group), [a[0], b[0], d[0], a[1], b[1], d[1], a[2], b[2], d[2]]);
    }
  }

  // a smooth line through points (Catmull-Rom), for cables and ropes drawn as tubes
  function smooth(pts, per) {
    if (pts.length < 3) return pts;
    const out = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
      const n = Math.max(1, Math.min(per, Math.ceil(dist(p1, p2) / 15)));
      for (let k = 0; k < n; k++) {
        const t = k / n, t2 = t * t, t3 = t2 * t;
        out.push([0, 1, 2].map(j => 0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)));
      }
    }
    out.push(pts[pts.length - 1]);
    return out;
  }

  // ---- cables and hoses: re-laid through the chains as the axes move
  const chainByName = Object.fromEntries((V.chains || []).map(c => [c.name, c]));
  function cablePoints(C, idx) {
    const out = [];
    for (const w of C.pts) {
      if (w[0] === "chain") {
        const c = chainByName[w[1]];
        const m = pose[c.var] + c.m_off;
        const sh = ((idx % 5) - 2) * (c.W / 7);
        for (let k = 24; k >= 0; k--) {
          const [p] = chainPoint(c, m, c.L * k / 24);
          out.push(toWorld([p[0] + c.w[0] * (c.W / 2 + sh), p[1] + c.w[1] * (c.W / 2 + sh), p[2] + c.w[2] * (c.W / 2 + sh)], c.group));
        }
      } else out.push(toWorld(w.slice(0, 3), w[3]));
    }
    return out.filter((p, i, a) => i === 0 || dist(p, a[i - 1]) > 0.5);
  }
  (V.cables || []).forEach((C, idx) => {
    const color = C.name.startsWith("hose.") ? "#2f7fbf" : (C.od >= 10 ? "#e07b1f" : "#3b3f45");
    addShapes(C.name, () => [{ type: "tube", points: smooth(cablePoints(C, idx), 4), radius: C.od / 2, style: { color, lit: true } }], { info: C.info });
  });

  // ---- ropes and belts: a smooth line through points that each ride with a group
  for (const R of V.ropes || []) {
    addShapes(R.name, () => [{ type: "tube", points: smooth(R.pts.map(([x, y, z, g]) => toWorld([x, y, z], g)), 8), radius: R.r,
      style: { color: R.colour || "#9aa0a6", lit: true } }], { info: R.info });
  }
  P.on("pose", () => { for (const ch of chains) placeChain(ch); });
  };
})();
