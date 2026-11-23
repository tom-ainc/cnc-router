"""Data for the page's 3D viewer and tabs (page/viewer_data.json, golf models in page/golf)."""
import json
import time as _time
from se import PageView
from cnc import assembly as A
from cnc import simulation as SIM
from cnc.parts import electrical as EL
from cnc.parts import fasteners as FA
from cnc.params import (
    ATC_XC, ATC_YC, COL_W, M_CW, REEVE, SHEET_L, SPOIL_T, SP_OFF, TILT, TIP_MIN, TIP_TO_NOSE, X_BED, X_TRAVEL, X_WORK,
    Y_RB, Y_RT, Y_WORK, ZN_MAX, Z_TRAVEL)
from cnc.geometry.shapes import fuse
from cnc.geometry.motor import x_motor_loc, y_motor_loc, z_motor_loc
from cnc.geometry.bed import CHAIN_SPECS
from cnc.geometry.moving import counterweight, gantry, head
from cnc.geometry.world import H0, W, Y_FRONT, Y_REAR, world, wpt
from cnc.geometry.pose import POSE, REF
from cnc.system.tree import N_ATC, N_BASE, N_BED, N_ELEC, N_GAN, N_SP, N_YC, N_ZA
from cnc.system.requirements import require
from cnc.checks.travel import tilt_meas
from cnc.checks.envelope import fb, fixed_depth, floor_b, poses, ymax_all, ymin_all, zmax
from cnc.parts.items import ROPE_PTS, items
from cnc.checks.stability import m_total, masses
from cnc.checks.structure import span
from cnc.checks.power import i_total, p_shaft
from cnc.checks.toolchange import ATC_SLIDE0, z_nose_atc
from cnc.checks.dynamics import OVERRUN_OK, SIM_JOBS, SIM_P, SIM_R, SIM_V
from cnc.checks.build import ASM_UNITS, CABLE_M, CABLE_ROUTES, JOINT_RESULTS, X_ASM
from cnc.outputs.build_steps import STEPS


def loc_matrix(loc):
    """A Location as a row-major 4x4 matrix, for the viewer."""
    r, t = loc.matrix(), loc.position()
    return [round(v, 6) for row in ([*r[i], t[i]] for i in range(3)) for v in row] + [0, 0, 0, 1]


def mesh_of(p, chord=0.05, angle=10.0):
    """Triangles for the viewer: 0.05 mm chord, 10 deg angle (golf's angle is in degrees)."""
    m = p.mesh(chord, angle)
    pts, tris = m.points(), m.triangles()
    return {"p": [round(c, 2) for pt in pts for c in pt], "t": [i for tr in tris for i in tr]}


_c1 = REF[0] - SP_OFF
V = PageView("Tilted-bed CNC router · 2400 × 1200",
             "Concept design, bed 10° from vertical, salvaged 9 kW ISO30 spindle on a 240 V 15 A circuit",
             components=["sim.js", "sim-page.js", "sim-ui.js", "build.js", "flex.js", "confirm.js"], whole="whole machine", bought_word="salvaged")
V.update({"tilt": TILT, "h0": H0, "parts": {}, "ranges": {
        "x": [X_TRAVEL[0], X_TRAVEL[1]], "x_work": list(X_WORK), "y": list(Y_WORK), "tip": [TIP_MIN, ZN_MAX - TIP_TO_NOSE]},
     "reeve": REEVE, "cw_ref": REF[1], "pose": list(POSE), "park": [X_TRAVEL[0], Y_WORK[0], ZN_MAX - TIP_TO_NOSE], "viz": {}})
# golf cannot mesh this STEP in reasonable time, so it is meshed once by gmsh (tools/step_mesh.py) and placed here
V["shared"] = {"motor": json.load(open("parts/34E1K-120_mesh.json"))}


def _hex(c):
    return "#%02x%02x%02x" % tuple(int(255 * v) for v in c)


# cable chains: the page rebuilds them link by link from these as the axes move
V["chains"] = [dict(name=nm, **{k: v for k, v in sp.items() if k != "part"}, info=sp["part"]) for nm, sp in CHAIN_SPECS.items()]
V["cables"] = [dict(name=c["name"], od=c["od"], info=f"{c['what']}: {c['dev']} to {c['term']}, {CABLE_M[c['name']]:.1f} m",
                    pts=[["chain", EL.CH[w[1]]] if w[0] == "chain" else [*[round(v, 1) for v in w[0]], w[1]] for w in c["pts"]])
                for c in CABLE_ROUTES.values()]
V["ropes"] = [{"name": "gantry_frame.rope", "r": 2.5, "pts": [[*p, grp] for p, grp in ROPE_PTS],
                "info": [it for it in items if it["name"] == "gantry_frame.rope"][0]["note"]}]
# The page draws the parts with golf's viewer: golf_models writes them, placed in the world, as golf models in
# page/golf (packed under the viewer's 16 MiB a model). The chains, cables and rope are drawn by the page as they move.
_page_parts = []
for _it in items:
    if _it["name"] in CHAIN_SPECS or _it["name"] == "gantry_frame.rope":
        continue
    V["parts"][_it["name"]] = dict(group=_it["group"], colour=_hex(_it["colour"]),
                                   info=f"{_it['note']} | {_it['mat']} | {_it['kg']:.2f} kg", kind=_it["kind"])
    _page_parts.append((_it["name"], _it["part"] if _it["group"] == "world" else world(_it["part"]), _it["colour"], _it["group"]))
# the motors: golf cannot mesh their STEP in reasonable time, so the page draws their gmsh mesh itself
for name, loc, grp, nd in (("gantry_drives.x_motor_bottom", x_motor_loc(_c1 - COL_W, Y_RB), "x", "GAN"),
                           ("gantry_drives.x_motor_top", x_motor_loc(_c1 - COL_W, Y_RT), "x", "GAN"),
                           ("gantry_drives.y_motor", y_motor_loc(_c1 - COL_W), "x", "GAN"), ("y_carriage.z_motor", z_motor_loc(_c1, REF[1]), "xy", "YC")):
    V["parts"][name] = dict(shared="motor", group=grp, colour="#34383f", loc=loc_matrix(loc),
                            info="StepperOnline 34E1K-120, 12 N*m closed-loop (salvaged) | 5.0 kg", kind="bought")
_t_pm = _time.time()
print("page models:", V.golf_models(_page_parts), f"in {_time.time() - _t_pm:.0f} s")
# which product-tree node shows which parts
for node, prefixes in ((N_BED, ("bed.",)), (N_GAN, ("gantry_frame.", "gantry_drives.", "counterweight.")), (N_YC, ("y_carriage.",)),
                       (N_ZA, ("z_axis.",)), (N_SP, ("spindle.", "tool")), (N_ATC, ("atc_rack.",)), (N_BASE, ("floor_frame.", "feet.")),
                       (N_ELEC, ("cabinet", "air.", "ducts.", "popup.", "estop.", "sensors.", "cable.", "hose."))):
    node.shows = [n for n in list(V["parts"]) + [c["name"] for c in V["chains"]] if n.startswith(prefixes)]
xs_hi, xs_lo = X_WORK[1], X_TRAVEL[0]
tip_up, tip_dn = ZN_MAX - TIP_TO_NOSE, TIP_MIN
top_pt = None
for xs, ys, tip in poses:   # where the height is reached
    a = fuse(list(gantry(xs, with_arm=False)) + list(head(xs, ys, tip, zchain=False))).moved(W).bounding_box()
    if a.max()[2] >= zmax - 0.01:
        top_pt = ((a.min()[0] + a.max()[0]) / 2, a.min()[1], a.max()[2]); worst_h = [xs, ys, tip]
if top_pt is None:
    top_pt, worst_h = ((fb.min()[0] + fb.max()[0]) / 2, fb.min()[1], fb.max()[2]), [X_WORK[1], Y_WORK[1], tip_up]
L = lambda x, y, z: list(wpt(x, y, z))
xm = (X_BED[0] + X_BED[1]) / 2
viz = {
    "R1": {"pose": [X_WORK[0], 600, 50], "sweep": "x", "parts": ["sheet", "gantry_frame"],
           "dims": [[L(X_WORK[0], -60, 0), L(X_WORK[1], -60, 0), f"tool centre {X_WORK[0]:g} to {X_WORK[1]:g} mm"],
                    [L(0, 1260, 0), L(SHEET_L, 1260, 0), "sheet 2400"]]},
    "R2": {"pose": [1200, Y_WORK[0], 50], "sweep": "y", "parts": ["sheet", "y_carriage"],
           "dims": [[L(-60, Y_WORK[0], 0), L(-60, Y_WORK[1], 0), f"tool centre {Y_WORK[0]:g} to {Y_WORK[1]:g} mm"]]},
    "R3": {"pose": [1200, 600, tip_up], "sweep": "z", "parts": ["z_axis", "spindle", "tool"],
           "dims": [[L(1200 + 120, 600, tip_dn), L(1200 + 120, 600, tip_up), f"Z stroke {Z_TRAVEL:.0f} mm"]]},
    "R4": {"pose": list(POSE), "parts": ["bed", "spoilboard"], "view": "side",
           "dims": [[L(X_BED[1] + 50, Y_RT, -SPOIL_T), [X_BED[1] + 50 * 1.0, wpt(0, Y_RT, -SPOIL_T)[1], 0.0 + wpt(0, Y_RB, -SPOIL_T)[2]], f"{tilt_meas:.1f} deg from vertical"]]},
    "R5": {"pose": [1200, 600, tip_dn], "parts": ["tool", "spoilboard"]},
    "R6": {"pose": worst_h, "parts": [], "dims": [[[top_pt[0], top_pt[1], 0.0], list(top_pt), f"{zmax:.0f} mm (limit 1800)"]], "view": "side"},
    "R7": {"pose": V["park"], "parts": ["floor_frame", "feet"], "view": "side",
           "dims": [[[X_BED[1] + 80, floor_b.min()[1], 0.0], [X_BED[1] + 80, floor_b.max()[1], 0.0], f"floor frame {floor_b.max()[1] - floor_b.min()[1]:.0f} mm"]]},
    "R8": {"pose": V["park"], "parts": ["bed", "floor_frame", "feet", "rail_bottom", "rail_top"], "view": "side",
           "dims": [[[X_BED[1] + 80, fb.min()[1], 5.0], [X_BED[1] + 80, fb.max()[1], 5.0], f"parked depth {fixed_depth:.0f} mm"],
                    [[X_WORK[1], ymin_all, 40.0], [X_WORK[1], ymax_all, 40.0], f"cutting envelope {ymax_all - ymin_all:.0f} mm"]]},
    "R9": {"pose": list(POSE), "parts": []}, "R10": {"pose": list(POSE), "parts": ["bed", "floor_frame", "feet"]},
    "R11": {"pose": [X_TRAVEL[0], Y_WORK[0], tip_up], "sweep": "x", "parts": ["gantry_frame", "gantry_drives", "y_carriage", "z_axis", "spindle"]},
    "R12": {"pose": [X_WORK[0], Y_WORK[0], tip_dn], "sweep": "xwork", "parts": ["y_carriage", "z_axis", "spindle", "sheet"]},
    "R13": {"pose": [X_TRAVEL[0], Y_WORK[0], tip_dn], "sweep": "y", "parts": ["y_carriage", "z_axis", "spindle", "gantry_frame"]},
    "R14": {"pose": V["park"], "parts": ["atc_rack", "gantry_frame", "spindle"]},
    "R15": {"pose": [1200, Y_WORK[0], tip_up], "parts": ["floor_frame", "feet"], "view": "side", "cg": True,
            "dims": [[[X_BED[1] + 80, Y_FRONT, 2.0], [X_BED[1] + 80, Y_REAR, 2.0], "foot span"]]},
    "R16": {"pose": list(POSE), "parts": ["floor_frame", "feet"], "view": "side", "cg": True},
    "R17": {"pose": list(POSE), "sweep": "x", "parts": ["gantry_drives", "x_motors", "x_motor_top"]},
    "R18": {"pose": list(POSE), "sweep": "y", "parts": ["y_carriage", "y_motor", "counterweight"]},
    "R19": {"pose": list(POSE), "sweep": "z", "parts": ["z_axis", "z_motor"]},
    "R32": {"pose": list(POSE), "parts": ["x_motors", "x_motor_top", "y_motor", "z_motor"]},
    "R33": {"pose": list(POSE), "parts": ["x_motors", "x_motor_top", "y_motor", "z_motor"]},
    "R34": {"pose": [1200, Y_WORK[1], tip_up], "parts": ["y_carriage", "z_axis", "spindle", "y_motor"]},
    "R35": {"pose": list(POSE), "sweep": "y", "parts": ["counterweight", "y_carriage"]},
    "R36": {"pose": list(POSE), "parts": ["counterweight", "gantry_frame"]},
    "R37": {"pose": list(POSE), "sweep": "y", "parts": ["counterweight"]},
    "R38": {"pose": [1200, Y_WORK[1], tip_up], "sweep": "y", "parts": ["y_carriage", "counterweight", "gantry_drives"]},
    "R39": {"pose": list(POSE), "sweep": "z", "parts": ["z_axis", "y_carriage", "z_motor"]},
    "R40": {"pose": list(POSE), "parts": ["y_carriage", "z_axis", "gantry_drives"]},
    "R44": {"pose": [X_BED[0] + 40 + span / 2 + SP_OFF, Y_WORK[1], tip_dn], "parts": ["bed", "rail_top", "floor_frame"], "view": "front"},
    "R45": {"pose": [1200, 600, tip_dn], "parts": ["spoilboard", "substrate", "bed"]},
    "R46": {"pose": [1200, 600, tip_dn], "parts": ["gantry_frame", "spindle"]},
    "R47": {"pose": [1200, 600, tip_dn], "parts": ["gantry_frame", "bed", "spindle", "y_carriage", "z_axis"]},
    "R41": {"pose": list(POSE), "parts": ["x_chain", "gantry_frame", "gantry_drives", "y_carriage"]},
    "R42": {"pose": list(POSE), "parts": ["x_chain", "gantry_drives", "y_carriage"]},
    "R43": {"pose": list(POSE), "parts": ["x_chain", "gantry_drives", "y_carriage"]},
    "R20": {"pose": list(POSE), "sweep": "y", "parts": ["y_carriage", "y_motor"]}, "R21": {"pose": [1200, Y_WORK[1], tip_up], "parts": ["y_carriage", "z_axis", "spindle"]},
    "R22": {"pose": [1200, 600, tip_dn], "parts": ["gantry_frame"]},
    "R26": {"pose": [1200, 600, tip_dn], "parts": ["spindle", "tool", "sheet"]},
    "R28": {"pose": V["park"], "parts": ["sheet", "spoilboard"]},
    "R29": {"pose": list(POSE), "sweep": "x", "parts": ["spindle", "z_axis", "y_carriage"]},
}
for rid in ("R23", "R24", "R25", "R30", "R31"):
    viz[rid] = {"pose": list(POSE), "parts": ["spindle"]}
viz["R27"] = {"pose": list(POSE), "parts": ["gantry_drives"]}
RENAME = {"rail_bottom": "bed.x_rail_bottom", "rail_top": "bed.x_rail_top", "rack_bottom": "bed.rack_bottom", "rack_top": "bed.rack_top",
          "spoilboard": "bed.spoilboard", "substrate": "bed.substrate", "x_chain": "bed.x_chain", "x_motors": "gantry_drives.x_motor_bottom",
          "x_motor_top": "gantry_drives.x_motor_top", "y_motor": "gantry_drives.y_motor", "z_motor": "y_carriage.z_motor",
          "bed": "bed.", "floor_frame": "floor_frame.", "feet": "feet."}
for _v in viz.values():
    _v["parts"] = [RENAME.get(p, p) for p in _v.get("parts", [])]
viz["R50"] = {"pose": list(POSE), "parts": []}
viz["R51"] = {"pose": list(POSE), "parts": ["y_carriage", "z_axis", "spindle"]}
viz["R52"] = {"pose": [ATC_XC, ATC_YC[2], z_nose_atc - TIP_TO_NOSE], "parts": ["atc_rack", "spindle", "z_axis"], "view": "front"}
viz["R53"] = {"pose": list(POSE), "sweep": "y", "parts": ["counterweight"]}
viz["R54"] = {"pose": [ATC_SLIDE0, ATC_YC[2], z_nose_atc - TIP_TO_NOSE], "parts": ["atc_rack", "spindle"]}
for _rid in ("R69", "R70", "R71", "R72", "R73", "R74", "R75", "R76", "R77", "R78", "R79", "R80", "R81", "R82", "R83", "R84"):
    viz[_rid] = {"pose": list(POSE), "parts": [], "sim": True}
V["viz"] = viz
V["sim"] = {"params": SIM_P, "results": {j: {k: v for k, v in SIM_R[j].items() if k != "steady"} for j in SIM_JOBS}, "overrun_ok": OVERRUN_OK,
            "verify": SIM_V, "digest": SIM.digest(SIM_P)}
# what each requirement is about, for grouping the list on the page
V["req_topics"] = {
    "Sheet and travel": ["R1", "R2", "R3", "R4", "R5", "R14"],
    "Size and footprint": ["R6", "R7", "R8", "R56"],
    "Clearances": ["R9", "R10", "R11", "R12", "R13", "R37", "R38", "R39", "R40", "R50", "R52", "R54", "R66", "R68"],
    "Stiffness and stability": ["R15", "R16", "R22", "R44", "R45", "R46", "R47"],
    "Drives, counterweight and masses": ["R17", "R18", "R19", "R20", "R21", "R32", "R33", "R34", "R35", "R36", "R51", "R53"],
    "Cables and chains": ["R41", "R42", "R43", "R55", "R63"],
    "Power and electrical": ["R23", "R24", "R25", "R26", "R27", "R30", "R31", "R67"],
    "Fabrication and build": ["R48", "R49", "R57", "R58", "R59", "R60", "R61", "R62", "R64", "R65"],
    "Use and safety": ["R28", "R29"],
    "Dynamics (simulation)": ["R69", "R70", "R71", "R72", "R73", "R74", "R75", "R76", "R77", "R78", "R79"],
    "Simulation model checks": ["R80", "R81", "R82", "R83", "R84"],
}
_shown = set(V["parts"]) | {c["name"] for c in V["chains"]}
_missing = [n for _st in STEPS for n in _st["adds"] if n not in _shown and n != "gantry_frame.rope" and not n.startswith(("wire.", "cable.", "hose."))]
_grp = {it["name"]: it["group"] for it in items}
_grp.update({"gantry_drives.x_motor_bottom": "x", "gantry_drives.x_motor_top": "x", "gantry_drives.y_motor": "x", "y_carriage.z_motor": "xy"})
V["fasteners"] = []
for _J in JOINT_RESULTS:
    _f = _J["f"]
    _D, _k = FA.head_size(_f)
    V["fasteners"].append(dict(name=_J["name"], step=_J["step"], type=_f["type"], d=_f["d"], L=_f["L"], head=[_D, _k],
                               nut=[FA.ISO[_f["d"]][6] * 1.1, FA.ISO[_f["d"]][7], _J["grip"] + 0.5 + (1.6 if _f["washer"] else 0)] if _f["nut"] else None,
                               pts=[[round(c, 2) for c in p] for p in _J["pts"]], dir=list(_J["dir"]), group=_grp.get(_J["parts"][0], "fixed"),
                               label=FA.label(_f), ok=not _J["fails"], draw=_f["type"] != "STUD"))
V["assembly"] = {"steps": STEPS, "stage": A.STAGE, "units": {u: d["parts"] for u, d in ASM_UNITS.items()},
                 "pose": [X_ASM, (Y_WORK[0] + Y_WORK[1]) / 2, ZN_MAX - TIP_TO_NOSE]}
require("R64", "Every step of the build shall play back in the 3D viewer with all of its parts (parts a step names that the viewer lacks)",
        len(_missing), "<=", 0, "", case=f"{len(STEPS)} steps" + (f"; missing {', '.join(_missing[:4])}" if _missing else ""))
viz["R57"] = viz["R58"] = viz["R59"] = viz["R64"] = {"pose": V["assembly"]["pose"], "parts": []}
for _r in ("R57", "R58", "R59", "R61", "R62", "R64"):        # these open at their build step
    viz.setdefault(_r, {})["build"] = True
cgs = []
for ys, tip in ((Y_WORK[0], tip_up), (Y_WORK[1], tip_dn), (POSE[1], POSE[2])):
    car, za, sp_, _ = head(POSE[0], ys, tip)
    mm = dict(masses, y_carriage=(world(car), masses["y_carriage"][1]), z_axis=(world(za), masses["z_axis"][1]),
              spindle=(world(sp_), masses["spindle"][1]), counterweight=(world(counterweight(POSE[0], ys)), M_CW))
    cgs.append([sum(p.centre()[i] * m for p, m in mm.values()) / m_total for i in range(3)])
V["cg"] = cgs
V["stats"] = {"height": zmax, "floor_depth": floor_b.max()[1] - floor_b.min()[1], "parked_depth": fixed_depth,
              "envelope_depth": ymax_all - ymin_all, "length": fb.max()[0] - fb.min()[0], "mass": m_total,
              "sheet_edge_height": wpt(0, 0, 0)[2], "spindle_power": p_shaft, "circuit_a": i_total}
# ---- how the page shows this machine (page/core.js reads these; see the systems-engineering skill's page.md)
V.frame(translate=(0, 0, H0), rotate=(90 - TILT, 0, 0))
V.axis("x", "X, along the sheet", (X_TRAVEL[0], X_TRAVEL[1]), start=POSE[0])
V.axis("y", "Y, up the bed", Y_WORK, start=POSE[1])
V.axis("tip", "Z, tool tip off the spoilboard", (TIP_MIN, tip_up), start=POSE[2])
V.group("x", ("x", (1, 0, 0)))
V.group("xy", ("x", (1, 0, 0)), ("y", (0, 1, 0)))
V.group("xyz", ("x", (1, 0, 0)), ("y", (0, 1, 0)), ("tip", (0, 0, 1), 1, TIP_MIN))
V.group("cw", ("x", (1, 0, 0)), ("y", (0, 1, 0), -1 / REEVE, REF[1]))       # the counterweight: half the head's travel, the other way
V.button("Park for loading", V["park"], ms=1600)
V.button("Run all axes", seq=[([X_WORK[0], Y_WORK[0], tip_up], 1200), ([X_WORK[0], Y_WORK[0], TIP_MIN], 700), ([X_WORK[1], Y_WORK[0], TIP_MIN], 2400),
                              ([X_WORK[1], Y_WORK[1], TIP_MIN], 1500), ([X_WORK[0], Y_WORK[1], TIP_MIN], 2400), ([X_WORK[0], Y_WORK[1], tip_up], 700),
                              (list(POSE), 1400)])
V.sweep("x", ("x", X_TRAVEL[0], 900), ("x", X_TRAVEL[1], 2600), ("x", None, 1400))
V.sweep("xwork", ("x", X_WORK[0], 600), ("x", X_WORK[1], 2400), ("x", X_WORK[0], 2400))
V.sweep("y", ("y", Y_WORK[0], 700), ("y", Y_WORK[1], 1800), ("y", None, 1000))
V.sweep("z", ("tip", TIP_MIN, 500), ("tip", tip_up, 1200), ("tip", None, 800))
V.view("iso", (-0.5, -0.72, 0.45), 3200, (1100, -150, 850))
V.view("side", (-1, 0, 0), 2500, (1300, -50, 950))
V.view("front", (0, -1, 0), 3400, (1300, 0, 950))
V.floor((-1000, 3500), (-1500, 1000))
_st = V["stats"]
V.tile("Height", _st["height"], "mm", "R6", "/ 1800")
V.tile("Depth parked", _st["parked_depth"], "mm", "R8", "/ 1000")
V.tile("Depth cutting", _st["envelope_depth"], "mm", "R8")
V.tile("Spindle power", _st["spindle_power"] / 1000, "kW", "R26", "on 15 A", digits=2)
V.tile("Circuit draw", _st["circuit_a"], "A", "R25", "/ 12 cont.", digits=1)
V.tile("Mass", _st["mass"], "kg", "R15", "with sheet")
V.diagram({"ZA": (290, 14), "SP": (470, 14), "YC": (290, 90), "ELEC": (104, 112), "GAN": (290, 166), "ATC": (470, 152), "BASE": (104, 248), "BED": (290, 248)},
          {"dust": (8, 24, ["ZA"]), "supply": (8, 84, ["ELEC"]), "air": (8, 140, ["ELEC"]), "operator": (8, 190, ["BED", "ELEC"]),
           "floor": (8, 274, ["BASE"]), "sheet": (480, 262, ["BED"])}, frame=(96, 4, 508, 306), size=(700, 314))
for _z in viz.values():                                     # centres of gravity: head low and head high
    if _z.pop("cg", None):
        _z["marks"] = [[cgs[0], "CG, head low"], [cgs[1], "CG, head high"]]
V.write()                                                   # page/viewer_data.json; report() adds page/data.js
