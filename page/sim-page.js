// sim-page.js: how the page's simulation component (sim-ui.js) shows this machine's model (sim.js).
// Kept apart from sim.js so that changing the page does not change the model (the sweep's digest hashes sim.js).
(function () {
  const MODEL = window.SIMMODEL || window.CNCSIM;
  if (!MODEL) return;
  window.SIMMODEL = MODEL;
  MODEL.ui = ui;

  // ---- how the page's simulation component (sim-ui.js) shows this model: everything about it that is this machine's
  function ui(P) {
    const RPM = 30 / Math.PI, T0 = P.axes.Y.cw.T0, f3 = (x) => (+x.toPrecision(3)).toString();
    return {
      // the line under each subsystem block in the top diagram
      summary: { plan: "ref.feed", X: "X.x", Y: "Y.x", Z: "Z.x", struct: "st.dz", cutf: "cut.F", spindle: "sp.rpm", tip: "tip.contour", power: "pw.I_mains" },
      // the model's coordinates (m) to the page's axes (mm): what the program asks for, and where the tool went
      pose: { keys: ["x", "y", "tip"], ref: ["ref.x", "ref.y", "ref.z"], act: ["tip.x", "tip.y", "tip.z"], scale: 1000 },
      cutting: (M) => !!(M.planner.ref && M.planner.ref.cut),
      jog: { axes: ["X", "Y", "Z"], lim: P.job.lim, start: P.job.park, steps: [1, 10, 100, 500], step: 100, unit: "mm",
             note: (a, sgn, d) => `jog ${a} ${sgn > 0 ? "+" : "−"}${d} mm at the rapid speed`, prog: (to) => [{ op: "rapid", to }] },
      // scopes: [signal, label, scale (default from its unit), colour index, dashed]; dashed is what the program asked for
      scopes: [
        { id: "pos", title: "Position, tool tip", unit: "mm", sigs: [["tip.x", "X", 1000, 0], ["tip.y", "Y", 1000, 1], ["tip.z", "Z", 1000, 2], ["ref.x", "", 1000, 0, 1], ["ref.y", "", 1000, 1, 1], ["ref.z", "", 1000, 2, 1]], lines: [], note: "dashed: programmed" },
        { id: "vel", title: "Velocity, tool tip", unit: "m/min", sigs: [["tip.vx", "X", 60, 0], ["tip.vy", "Y", 60, 1], ["tip.vz", "Z", 60, 2], ["ref.vx", "", 60, 0, 1], ["ref.vy", "", 60, 1, 1], ["ref.vz", "", 60, 2, 1]], lines: [], note: "dashed: programmed" },
        { id: "acc", title: "Acceleration, tool tip", unit: "m/s²", sigs: [["tip.ax", "X", 1, 0], ["tip.ay", "Y", 1, 1], ["tip.az", "Z", 1, 2], ["ref.ax", "", 1, 0, 1], ["ref.ay", "", 1, 1, 1], ["ref.az", "", 1, 2, 1]], lines: [], note: "dashed: programmed" },
        { id: "err", title: "Position error, tool tip", unit: "µm", sigs: [["tip.ex", "X"], ["tip.ey", "Y"], ["tip.ez", "Z"], ["tip.contour", "off the path", 1, 3]], lines: [[100, "R69 limit"], [-100, ""]] },
        { id: "verr", title: "Velocity error, tool tip", unit: "mm/s", sigs: [["tip.evx", "X", 1000], ["tip.evy", "Y", 1000], ["tip.evz", "Z", 1000]], lines: [] },
        { id: "aerr", title: "Acceleration error, tool tip", unit: "m/s²", sigs: [["tip.eax", "X", 1], ["tip.eay", "Y", 1], ["tip.eaz", "Z", 1]], lines: [] },
        { id: "util", title: "Torque used", unit: "% of pull-out", sigs: [["X.util", "X"], ["Y.util", "Y"], ["Z.util", "Z"]], lines: [[80, "R70 limit"]] },
        { id: "tq", title: "Motor torque", unit: "N·m (X: both motors)", sigs: [["X.T_m", "X", 1, 0], ["Y.T_m", "Y", 1, 1], ["Z.T_m", "Z", 1, 2], ["X.T_max", "", 1, 0, 1], ["Y.T_max", "", 1, 1, 1], ["Z.T_max", "", 1, 2, 1]], lines: [], note: "dashed: pull-out at speed" },
        { id: "rpm", title: "Motor speed", unit: "rpm", sigs: [["X.w_m", "X", RPM], ["Y.w_m", "Y", RPM], ["Z.w_m", "Z", RPM]], lines: [] },
        { id: "fd", title: "Drive force", unit: "N, belt / screw / rack", sigs: [["X.F_d", "X"], ["Y.F_d", "Y"], ["Z.F_d", "Z"]], lines: [] },
        { id: "cut", title: "Cutting force", unit: "N", sigs: [["cut.F", "feed force"], ["cut.Fx", "x"], ["cut.Fy", "y"], ["cut.Fz", "z"]], lines: [] },
        { id: "spw", title: "Spindle power", unit: "W", sigs: [["sp.P_cut", "cut"], ["sp.P_in", "VFD input"]], lines: [] },
        { id: "srpm", title: "Spindle speed", unit: "rpm", sigs: [["sp.rpm", "actual", 1, 0], ["ref.rpm", "set", 1, 1, 1]], lines: [] },
        { id: "col", title: "Column deflection at the head", unit: "µm", sigs: [["st.dx", "x, along the sheet", 1e6], ["st.dz", "z, normal to the bed", 1e6]], lines: [] },
        { id: "rope", title: "Counterweight rope", unit: "N", sigs: [["cw.T", "tension"]], lines: [[T0 / 2, "R76 limit"]] },
        { id: "bus", title: "60 V buses", unit: "V", sigs: [["pw.X1.V", "X1"], ["pw.X2.V", "X2"], ["pw.Y.V", "Y"], ["pw.Z.V", "Z"]], lines: [[90, "R72 limit"]] },
        { id: "psu", title: "Supply load", unit: "W", sigs: [["pw.X1.P_psu", "X1"], ["pw.X2.P_psu", "X2"], ["pw.Y.P_psu", "Y"], ["pw.Z.P_psu", "Z"]], lines: [[350, "rating"]] },
        { id: "mains", title: "Mains current", unit: "A", sigs: [["pw.I_mains", "mains"]], lines: [[15, "circuit"], [12, "80 %"]] },
        { id: "fail", title: "Power and drivers", unit: "on = 1", sigs: [["pw.ok", "mains", 1, 0], ["X.ok", "X driver", 1, 1], ["Y.ok", "Y driver", 1, 2], ["Z.ok", "Z driver", 1, 3], ["pw.brake", "Y brake on", 1, 4, 1]], lines: [] },
      ],
      scopesOn: ["pos", "vel", "acc", "err", "verr", "aerr", "util", "mains"],
      firstJob: "profile",
      // the measures under the scopes: [requirement, measure, this run, the full run, limit, unit] and a footnote
      measures(job, r, full, sim) {
        const cut = ["profile", "pocket"].includes(job);
        if (job.startsWith("pfail")) return failMeasures(r, full, sim);
        return { rows: [
          ["R69", "Contour error while cutting", cut ? r.contour : null, full && cut ? full.contour : null, "≤ 100", "µm"],
          ["R70", "Torque used, worst axis", Math.max(r.util.X, r.util.Y, r.util.Z) * 100, full ? Math.max(full.util.X, full.util.Y, full.util.Z) * 100 : null, "≤ 80", "%"],
          ["R71", "Supply load, 100 ms average", Math.max(...Object.values(r.psu)), full ? Math.max(...Object.values(full.psu)) : null, "≤ 350", "W"],
          ["R72", "Highest bus voltage", r.vbus, full ? full.vbus : null, "≤ 90", "V"],
          ["R73", "Mains current, 1 s average", r.mains_1s, full ? full.mains_1s : null, "≤ 15", "A"],
          ["R74", "Spindle droop while cutting", cut ? r.droop * 100 : null, full && cut ? full.droop * 100 : null, "≤ 10", "%"],
          ["R76", "Least rope tension", r.rope_min < 1e8 ? r.rope_min / T0 * 100 : null, full ? full.rope_min / T0 * 100 : null, "≥ 50", "% of static"],
        ], foot: "“Full run” is router.py running this same model (sim.js) to the end of the job; the requirements read it." };
      },
      // is the model solved right: the verify results as rows [requirement, check, result, limit]
      trust(v) {
        const conv = Object.values(v.conv).reduce((a, q) => Math.max(a, q.change), 0);
        return [
          ["R80", "Drive frequencies against the two-mass formula", Object.entries(v.drive).map(([a, q]) => `${a} ${f3(q.freq_err)} %`).join(", "), "≤ 1 %"],
          ["R81", "Energy drift, losses off, 1 s", Object.entries(v.drive).map(([a, q]) => `${a} ${f3(q.energy_drift)} %`).join(", "), "≤ 0.1 %"],
          ["R82", "Steady torque against the force balance", Object.entries(v.steady).map(([a, q]) => `${a} ${f3(q.err)} %`).join(", "), "≤ 1 %"],
          ["R83", "Movement when left alone", `${f3(v.rest.worst_um)} µm`, "≤ 0.1 µm"],
          ["R84", "Largest change at half the time step", `${f3(conv)} %`, "≤ 2 %"],
        ];
      },
      // a requirement from the simulation: which job, which moment, which diagram, which scopes and wires
      focusReq(id, RES) {
        const jobsAll = Object.keys(RES).filter(j => !j.startsWith("pfail") || ["R72", "R73"].includes(id)), cut = ["profile", "pocket"];
        const arg = (js, f, min) => js.reduce((a, b) => (min ? f(b) < f(a) : f(b) > f(a)) ? b : a);
        const U = (j) => Math.max(...Object.values(RES[j].util));
        const o = { job: null, t: null, diag: "top" };
        if (id === "R69") { o.job = arg(cut, j => RES[j].contour); o.t = RES[o.job].contour_at; o.diag = "tip"; o.probe = ["tip.contour"]; }
        if (id === "R70") { o.job = arg(jobsAll, U); const ax = Object.entries(RES[o.job].util).sort((a, b) => b[1] - a[1])[0][0]; o.t = RES[o.job].util_at[ax]; o.diag = ax; }
        if (id === "R71") { o.job = arg(jobsAll, j => Math.max(...Object.values(RES[j].psu))); o.diag = "power"; }
        if (id === "R72") { o.job = arg(jobsAll, j => RES[j].vbus); o.diag = "pwX1"; }
        if (id === "R73") { o.job = arg(jobsAll, j => RES[j].mains_1s); o.diag = "power"; }
        if (id === "R74") { o.job = arg(cut, j => RES[j].droop); o.diag = "spindle"; }
        if (id === "R75") { o.diag = "struct"; }
        if (id === "R76") { o.job = arg(jobsAll.filter(j => !j.startsWith("pfail")), j => RES[j].rope_min, true); o.diag = "Y"; }
        if (["R77", "R78", "R79"].includes(id) && RES.pfail_drop) { o.job = "pfail_drop"; o.t = RES[o.job].fail.t - 0.4; o.diag = id === "R78" ? "Y" : "top"; o.scopes = ["fail"]; }
        return o;
      },
    };
    // a power-failure job: how far each axis runs past its normal stop, whether it then holds, and the rope
    function failMeasures(r, full, sim) {
      const ok = (sim && sim.overrun_ok) || {}, f = (v) => v == null ? "–" : f3(v);
      const over = (F, i) => { if (!F) return null; const a = "XYZ"[i], v = Math.abs(F.v0[i]); return Math.max(0, F.run[i] - v * v / (2 * P.axes[a].acc)) * 1000; };
      const creep = (F, i) => F && F.x2 ? Math.abs(F.xs[i] - F.x2[i]) * 1000 : null;
      const A = r.fail, B = full && full.fail, rows = [];
      ["X", "Y", "Z"].forEach((a, i) => {
        rows.push(["R77", `${a}: ran on after the failure`, A ? A.run[i] * 1000 : null, B ? B.run[i] * 1000 : null, "", "mm"]);
        rows.push(["R77", `${a}: past its normal stop`, over(A, i), over(B, i), "≤ " + f(ok[a]), "mm"]);
        rows.push(["R79", `${a}: movement 2 s on`, creep(A, i), creep(B, i), "≤ 0.01", "mm"]);
      });
      rows.push(["R78", "Rope, peak tension", A ? A.rope_max : null, B ? B.rope_max : null, "≤ 3000", "N"]);
      rows.push(["R78", "Rope, least tension", A ? A.rope_min : null, B ? B.rope_min : null, "", "N"]);
      rows.push(["R72", "Highest bus voltage", A ? A.vbus : null, B ? B.vbus : null, "≤ 90", "V"]);
      const trips = (F) => F ? Object.entries(F.trips).map(([k, q]) => `${k} ${q.why} at ${(q.t * 1000).toFixed(0)} ms`).join("; ") : "";
      return { rows, foot: `${A ? "Drivers: " + trips(A) + ". " : "The power fails halfway along the rapid. "}“Past its normal stop” is the run-on less the distance the controller would have stopped in from that speed; the allowances are the X rail beyond the travel, the Y rails' ends, and the 10 mm clearance over the sheet.` };
    }
  }

})();
