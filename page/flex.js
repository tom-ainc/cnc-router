// flex.js: cable chains, cables and hoses, and ropes that re-lay themselves as the axes move.
// A component of the page framework (core.js); its data is in viewer_data.json:
//   V.chains  [{name, group, var (the axis that drives it), m_off, m_min, f, F, d, n, w, R, sg, h, W, pitch, L, N, info}]
//   V.cables  [{name, od, info, pts: [[x, y, z, group] or ["chain", chain name]]}]
//   V.ropes   [{name, r, info, pts: [[x, y, z, group]]}]
(function () {
  const comp = { id: "flex" };
  Page.component(comp);
  comp.init = function (P) {
  const { V, THREE, meshes, scene, local, groupObj, groupOffset, pose } = P;
  // ---- cable chains: link by link, re-laid every time an axis moves
  function boxGeo(x0, x1, y0, y1, z0, z1) {
    const g = new THREE.BoxGeometry(x1 - x0, y1 - y0, z1 - z0);
    g.translate((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2);
    return g.toNonIndexed();
  }
  function mergeGeos(gs) {
    let n = 0; gs.forEach(g => { n += g.attributes.position.count; });
    const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3);
    let o = 0;
    for (const g of gs) { pos.set(g.attributes.position.array, o * 3); nor.set(g.attributes.normal.array, o * 3); o += g.attributes.position.count; }
    const m = new THREE.BufferGeometry();
    m.setAttribute("position", new THREE.BufferAttribute(pos, 3)); m.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
    return m;
  }
  const chainObjs = [];
  for (const c of V.chains || []) {
    const p = c.pitch, L = 0.8 * p, t = 3, h = c.h, Wd = c.W;
    const geo = mergeGeos([boxGeo(-L / 2, L / 2, 0, t, -h / 2, h / 2), boxGeo(-L / 2, L / 2, Wd - t, Wd, -h / 2, h / 2),
                           boxGeo(-0.2 * p, 0.2 * p, t - 0.5, Wd - t + 0.5, h / 2 - t, h / 2 - 0.3), boxGeo(-0.2 * p, 0.2 * p, t - 0.5, Wd - t + 0.5, -h / 2 + 0.3, -h / 2 + t)]);
    const mat = new THREE.MeshStandardMaterial({ color: "#2b2f34", roughness: 0.5, metalness: 0.05, transparent: true, opacity: 1 });
    const im = new THREE.InstancedMesh(geo, mat, c.N);
    im.userData.name = c.name; im.userData.edges = null;
    im.frustumCulled = false;
    groupObj(c.group).add(im);
    meshes[c.name] = im;
    chainObjs.push({ c, im });
    V.parts[c.name] = { info: c.info + " | " + c.N + " links, " + Math.round(c.L) + " mm", kind: "bought" };
  }
  const _M = new THREE.Matrix4(), _t = new THREE.Vector3(), _w = new THREE.Vector3(), _z = new THREE.Vector3();
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
  function updateChains() {
    for (const { c, im } of chainObjs) {
      const m = pose[c.var] + c.m_off;
      for (let i = 0; i < c.N; i++) {
        const [p, t] = chainPoint(c, m, i * c.L / (c.N - 1));
        _t.set(t[0], t[1], t[2]); _w.set(c.w[0], c.w[1], c.w[2]); _z.crossVectors(_t, _w);
        _M.makeBasis(_t, _w, _z); _M.setPosition(p[0], p[1], p[2]);
        im.setMatrixAt(i, _M);
      }
      im.instanceMatrix.needsUpdate = true;
    }
  }
  // ---- cables and hoses: re-laid through the chains as the axes move
  const chainByName = Object.fromEntries((V.chains || []).map(c => [c.name, c]));
  const cableObjs = [];
  const _gv = new THREE.Vector3();
  const grpOff = groupOffset;
  function toWorld(p, g) {
    if (g === "world") return new THREE.Vector3(p[0], p[1], p[2]);
    const o = grpOff(g);
    return local.localToWorld(_gv.set(p[0] + o[0], p[1] + o[1], p[2] + o[2]).clone());
  }
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
    return out.filter((p, i, a) => i === 0 || p.distanceTo(a[i - 1]) > 0.5);
  }
  (V.cables || []).forEach((C, idx) => {
    const isHose = C.name.startsWith("hose.");
    const mat = new THREE.MeshStandardMaterial({ color: isHose ? "#2f7fbf" : (C.od >= 10 ? "#e07b1f" : "#3b3f45"), roughness: 0.6, metalness: 0.05, transparent: true, opacity: 1 });
    const m = new THREE.Mesh(new THREE.BufferGeometry(), mat);
    m.userData.name = C.name; m.userData.edges = null; m.frustumCulled = false;
    scene.add(m); meshes[C.name] = m;
    V.parts[C.name] = { info: C.info, kind: "bought" };
    cableObjs.push({ C, m, idx });
  });
  function updateCables() {
    local.updateMatrixWorld(true);          // before the first render the local frame's world matrix is not set yet
    for (const { C, m, idx } of cableObjs) {
      const pts = cablePoints(C, idx);
      if (pts.length < 2) continue;
      const curve = new THREE.CatmullRomCurve3(pts, false, "centripetal");
      const geo = new THREE.TubeGeometry(curve, Math.min(400, pts.length * 4), C.od / 2, 6, false);
      m.geometry.dispose(); m.geometry = geo;
    }
  }

  // ---- ropes and belts: a smooth line through points that each ride with a group, re-laid as the axes move
  // V.ropes [{name, r, pts: [[x, y, z, group]], info, colour}]
  const ropeObjs = [];
  for (const R of V.ropes || []) {
    const mat = new THREE.MeshStandardMaterial({ color: R.colour || "#9aa0a6", roughness: 0.4, metalness: 0.6, transparent: true, opacity: 1 });
    const m = new THREE.Mesh(new THREE.BufferGeometry(), mat);
    m.userData.name = R.name; m.userData.edges = null; m.frustumCulled = false;
    local.add(m); meshes[R.name] = m;
    V.parts[R.name] = { info: R.info, kind: "bought" };
    ropeObjs.push({ R, m });
  }
  function updateRope() {
    for (const { R, m } of ropeObjs) {
      const pts = R.pts.map(([x, y, z, g]) => { const o = groupOffset(g); return new THREE.Vector3(x + o[0], y + o[1], z + o[2]); });
      const curve = new THREE.CatmullRomCurve3(pts, false, "catmullrom", 0.05);
      m.geometry.dispose(); m.geometry = new THREE.TubeGeometry(curve, 160, R.r, 8, false);
    }
  }

  P.on("pose", () => { updateChains(); updateRope(); updateCables(); });
  };
})();
