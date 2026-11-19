"""Electrical and pneumatic: the cabinet on its stand at the machine's right end, its backplate layout, the sensors, the
front E-stop, the pop-up pins, the cable ducts, and every cable, hose and internal wire with its route and both ends.

The cabinet sits on a stand welded to stubs that continue the floor frame's front and rear rails past the bed's right end,
so the floor depth is unchanged. World frame for the cabinet and stand (X along the machine, Y back, Z up).
"""
import math

import detail as D
from detail import box, cyl, drill, item, screw, weld, fuse

# ------------------------------------------------------------------ the cabinet: size and where it sits (world)
CAB = dict(x0=2660.0, x1=3260.0, y0=38.5, y1=338.5, z0=520.0, z1=1320.0, t=1.5)     # 600 W x 800 H x 300 D sheet steel
BP_Y = CAB["y1"] - CAB["t"] - 20.0                   # backplate's back face (on 20 mm studs)
BP_T = 3.0
BP = dict(u0=CAB["x0"] + 20.0, v0=CAB["z0"] + 20.0, W=560.0, H=760.0)
UPR = (2700.0, 3220.0)
FAN_M3H = 70.0
PINS_X = (400.0, 1200.0, 2100.0)                     # pop-up pins: between cross members                                       # 150 mm filter fan, delivered through its inlet and exhaust filters                               # stand uprights, SHS 40x40x3
STUB_X1 = 3300.0                                     # floor-rail stubs run to here

# Components on the backplate: name, (u, v) lower-left on the plate, (w, h) on the plate, depth, kg, how mounted, part number
COMPONENTS = [
    ("terminals", (20, 20), (300, 60), 45, 0.8, "din", "terminal blocks: 4 mm2 feed-through, PE, fused, 2-level sensor blocks"),
    ("controller", (350, 10), (160, 100), 40, 0.4, "ears", "motion controller, Ethernet, 4 axes step/dir, 16 in / 8 out"),
    ("psu_x1", (25, 165), (115, 215), 50, 1.2, "ears", "60 V 14.6 A 350 W supply (salvaged), X1"),
    ("psu_x2", (155, 165), (115, 215), 50, 1.2, "ears", "60 V 14.6 A 350 W supply (salvaged), X2"),
    ("psu_y", (285, 165), (115, 215), 50, 1.2, "ears", "60 V 14.6 A 350 W supply (salvaged), Y"),
    ("psu_z", (415, 165), (115, 215), 50, 1.2, "ears", "60 V 14.6 A 350 W supply (salvaged), Z"),
    ("vfd", (15, 430), (87, 157), 152, 1.8, "ears", "Delta VFD11AMS21ANSHA, 1-ph 230 V in, 11 A, 1500 Hz, STO"),
    ("drv_x1", (122, 430), (97, 151), 52, 0.6, "ears", "closed-loop stepper driver for 34E1K-120 (salvaged), X1"),
    ("drv_x2", (229, 430), (97, 151), 52, 0.6, "ears", "closed-loop stepper driver, X2"),
    ("drv_y", (336, 430), (97, 151), 52, 0.6, "ears", "closed-loop stepper driver, Y"),
    ("drv_z", (443, 430), (97, 151), 52, 0.6, "ears", "closed-loop stepper driver, Z"),
    ("rcd", (20, 650), (36, 90), 75, 0.25, "din", "RCBO 16 A 30 mA type A, 2-pole (supply protection)"),
    ("mcb_vfd", (60, 650), (36, 90), 75, 0.2, "din", "MCB 10 A C-curve 2-pole, VFD"),
    ("mcb_psu", (100, 650), (36, 90), 75, 0.2, "din", "MCB 6 A C-curve 2-pole, stepper supplies"),
    ("mcb_ctl", (140, 650), (18, 90), 75, 0.1, "din", "MCB 2 A 1-pole, 24 V supply and control"),
    ("contactor", (165, 650), (45, 85), 80, 0.35, "din", "contactor 25 A AC-1, 24 V DC coil, 2 NO + aux"),
    ("safety_relay", (220, 650), (22.5, 100), 115, 0.2, "din", "E-stop safety relay, 2-channel, 3 NO"),
    ("psu_24", (250, 650), (40, 90), 100, 0.3, "din", "24 V 2.5 A DIN supply"),
    ("brake_relay", (300, 650), (16, 90), 70, 0.05, "din", "interface relay, Y brake"),
    ("valve_relays", (322, 650), (44, 90), 70, 0.15, "din", "3 interface relays, solenoid valves"),
    ("emc_filter", (380, 645), (60, 100), 50, 0.6, "ears", "single-phase EMC filter 16 A, VFD input"),
]
DUCT_V = [(115, 155), (385, 425), (595, 640)]                  # horizontal slotted ducts 40 tall between the rows (v ranges)


def _w(u, v, y):
    """Backplate coordinates (u along X from the plate's left, v up from its bottom) to the world, at depth y."""
    return (BP["u0"] + u, y, BP["v0"] + v)


def cabinet(g):
    """Stand, enclosure, backplate and its parts, door, fan, gland plate: items (world group) with their joints."""
    out = []
    S = "world"
    ZB0, ZB1 = g["ZB0"], g["ZB1"]
    fr, yr = g["front_lo"][1], g["Y_REAR"]
    x1b = g["X_BED"][1]
    # ---- stand: stubs continuing the floor rails, a cross member, two uprights, two more levelling feet
    for nm, (ya, yb) in (("front", (fr + 10, fr + 110)), ("rear", (yr - 80, yr))):
        st = D.rhs("x", x1b, STUB_X1, ya, yb, ZB0, ZB1, 4.0)
        st = drill(st, "-z", [(STUB_X1 - 40, (ya + yb) / 2, ZB0)], 9.0)
        out.append(item(f"cabinet_stand.stub_{nm}", st, "steel", "made", "RHS 100x50x4 on edge, welded to the floor rail's end", S))
        weld(f"cabinet_stand.stub_{nm}", "F05", f"cabinet_stand.stub_{nm}", f"floor_frame.{nm}_rail", "butt, full round, ground")
        out.append(item(f"cabinet_stand.foot_nut_{nm}", D.foot_nut(STUB_X1 - 40, (ya + yb) / 2, ZB0), "steel", "bought", "M16 nut, welded under the stub", S))
        weld(f"cabinet_stand.foot_nut_{nm}", "F05", f"cabinet_stand.foot_nut_{nm}", f"cabinet_stand.stub_{nm}", "tack 3 sides")
        out.append(item(f"cabinet_stand.foot_{nm}", D.levelling_foot(STUB_X1 - 40, (ya + yb) / 2, ZB0, ZB0), "steel", "bought", "M16 levelling foot, 80 pad, lock nut", S))
        screw(f"cabinet_stand.foot_{nm}", "F05", [f"cabinet_stand.foot_nut_{nm}"], "STUD", 16, [(STUB_X1 - 40, (ya + yb) / 2, 16.0)], (0, 0, 1),
              grip=ZB0 - 13 - 16, L=ZB0 + 4.0 - 16.0, into="nut")
    out.append(item("cabinet_stand.cross", D.rhs("y", STUB_X1 - 80, STUB_X1, fr + 110.5, yr - 80.5, ZB0, ZB1, 4.0), "steel", "made",
                    "RHS 100x50x4 between the stubs' ends", S))
    for nm in ("front", "rear"):
        weld(f"cabinet_stand.cross_{nm}", "F05", "cabinet_stand.cross", f"cabinet_stand.stub_{nm}", "fillet all round")
    cab_bolts = [(x, z) for x in UPR for z in (CAB["z0"] + 100, CAB["z1"] - 100)]
    for k, x in enumerate(UPR):
        up = D.rhs("z", x - 20, x + 20, yr - 40, yr, ZB1, 1700.0, 3.0)
        up = drill(up, "-y", [(x, yr - 40, z) for xx, z in cab_bolts if xx == x], 4.5)
        out.append(item(f"cabinet_stand.upright_{k}", up, "steel", "made", "SHS 40x40x3, welded on the rear stub; 9 mm holes for the cabinet", S))
        weld(f"cabinet_stand.upright_{k}", "F05", f"cabinet_stand.upright_{k}", "cabinet_stand.stub_rear", "fillet all round")
    # ---- enclosure: shell with a door opening at the front (-Y), 4 welded studs for the backplate, gland plate at the bottom
    t = CAB["t"]
    x0, x1, y0, y1, z0, z1 = (CAB[k] for k in ("x0", "x1", "y0", "y1", "z0", "z1"))
    FZ = 420.0
    shell = box(x0, x1, y0, y1, z0, z1) - box(x0 + t, x1 - t, y0 - 1, y1 - t, z0 + t, z1 - t)
    shell = shell - box(x0 + 60, x1 - 60, y0 + 40, y1 - 40, z0 - 1, z0 + t + 1)                # gland opening in the floor
    studs_uv = [(30, 8), (530, 8), (30, 752), (530, 752)]
    studs = fuse([cyl("y", (BP["u0"] + u, 0, BP["v0"] + v), 6.0, BP_Y + BP_T, y1 - t + 0.01) for u, v in studs_uv])
    studs = drill(studs, "-y", [(BP["u0"] + u, BP_Y + BP_T, BP["v0"] + v) for u, v in studs_uv], 2.5, depth=15)
    shell = shell + studs
    shell = drill(shell, "+y", [(x, y1 - t, z) for x, z in cab_bolts], 4.5)
    shell = drill(shell, "+x", [(x1, (y0 + y1) / 2 + s * 63, (z0 + FZ) + s2 * 63) for s in (-1, 1) for s2 in (-1, 1)], 2.25)
    shell = shell - box(x1 - t - 1, x1 + 1, (y0 + y1) / 2 - 56, (y0 + y1) / 2 + 56, z0 + FZ - 56, z0 + FZ + 56)   # fan cut-out
    shell = shell - box(x0 - 1, x0 + t + 1, (y0 + y1) / 2 - 45, (y0 + y1) / 2 + 45, z1 - 200 - 45, z1 - 200 + 45)   # exhaust grille
    gpts = [(x, y, z0) for x in (x0 + 45, x1 - 45) for y in (y0 + 28, y1 - 28)]
    shell = drill(shell, "-z", gpts, 2.75)
    out.append(item("cabinet.enclosure", shell, "steel", "bought", "steel wall enclosure 600 x 800 x 300, IP54, 4 studs for the backplate", S))
    screw("cabinet.enclosure", "E01", ["cabinet.enclosure", "cabinet_stand.upright_0"], "HEX", 8, [(x, y1 - t, z) for x, z in cab_bolts if x == UPR[0]],
          (0, 1, 0), grip=t + 40.0, nut=True, washer=True)
    screw("cabinet.enclosure_r", "E01", ["cabinet.enclosure", "cabinet_stand.upright_1"], "HEX", 8, [(x, y1 - t, z) for x, z in cab_bolts if x == UPR[1]],
          (0, 1, 0), grip=t + 40.0, nut=True, washer=True)
    door = box(x0, x1, y0 - 22, y0 - 0.5, z0, z1)
    door = door - box(x0 + 2, x1 - 2, y0 - 20, y0, z0 + 2, z1 - 2)
    out.append(item("cabinet.door", door, "steel", "bought", "enclosure door, 2 locks, isolator and E-stop on it", S))
    gl = box(x0 + 30, x1 - 30, y0 + 15, y1 - 15, z0 - 2.5, z0 - 0.5)
    gl = gl - fuse([cyl("z", (x0 + 120 + 70 * k, (y0 + y1) / 2, 0), 10.0, z0 - 3, z0) for k in range(6)])
    gl = drill(gl, "-z", [(p[0], p[1], z0 - 2.5) for p in gpts], 2.75)
    out.append(item("cabinet.gland_plate", gl, "steel", "bought", "gland plate, 6 x M25 glands (spindle, motors, sensors, air, mains)", S))
    screw("cabinet.gland_plate", "E04", ["cabinet.enclosure", "cabinet.gland_plate"], "SHCS", 5,
          [(p[0], p[1], z0 + t) for p in gpts], (0, 0, -1), grip=t + 0.5 + 2.0, nut=True)
    fan = box(x1 + 0.5, x1 + 30, (y0 + y1) / 2 - 75, (y0 + y1) / 2 + 75, z0 + FZ - 75, z0 + FZ + 75)
    fan = drill(fan, "+x", [(x1 + 30, (y0 + y1) / 2 + s * 63, (z0 + FZ) + s2 * 63) for s in (-1, 1) for s2 in (-1, 1)], 2.25)
    out.append(item("cabinet.fan", fan, "plastic", "bought", f"filter fan 150 sq, {FAN_M3H:g} m3/h with its filters, 24 V, inlet", S))
    screw("cabinet.fan", "E04", ["cabinet.fan", "cabinet.enclosure"], "SHCS", 4,
          [(x1 + 30, (y0 + y1) / 2 + s * 63, (z0 + FZ) + s2 * 63) for s in (-1, 1) for s2 in (-1, 1)], (-1, 0, 0), grip=29.5 + t, nut=True)
    ex = box(x0 - 25, x0 - 0.5, (y0 + y1) / 2 - 50, (y0 + y1) / 2 + 50, z1 - 250, z1 - 150)
    out.append(item("cabinet.exhaust", ex, "plastic", "bought", "exhaust filter grille 100 sq, clipped in", S))
    # ---- backplate and what is on it (a bench unit)
    bp = box(BP["u0"], BP["u0"] + BP["W"], BP_Y, BP_Y + BP_T, BP["v0"], BP["v0"] + BP["H"])
    bp = drill(bp, "-y", [(BP["u0"] + u, BP_Y, BP["v0"] + v) for u, v in studs_uv], 3.3)
    holes = []
    yf = BP_Y                                   # the backplate's front face
    for name, (u, v), (w, h), d, kg, how, note in COMPONENTS:
        if how == "ears":
            body = box(*_w(u, v + 6, yf - 0.5)[:1], *_w(u + w, v, 0)[:1], yf - d, yf - 0.5, *_w(0, v + 6, 0)[2:], *_w(0, v + h - 6, 0)[2:])
            ear_pts = [(u + w / 2, v + 3), (u + w / 2, v + h - 3)]
            ears = fuse([box(BP["u0"] + u + w / 2 - 10, BP["u0"] + u + w / 2 + 10, yf - 2.5, yf - 0.5, BP["v0"] + v, BP["v0"] + v + 6),
                         box(BP["u0"] + u + w / 2 - 10, BP["u0"] + u + w / 2 + 10, yf - 2.5, yf - 0.5, BP["v0"] + v + h - 6, BP["v0"] + v + h)])
            part = drill(body + ears, "-y", [(BP["u0"] + eu, yf - 2.5, BP["v0"] + ev) for eu, ev in ear_pts], 2.25)
            out.append(item(f"cabinet.{name}", part, "electrical", "bought", note, S))
            pts = [(BP["u0"] + eu, yf - 2.5, BP["v0"] + ev) for eu, ev in ear_pts]
            holes += pts
            screw(f"cabinet.{name}", "E02", [f"cabinet.{name}", "cabinet.backplate"], "SHCS", 4, pts, (0, 1, 0), grip=2.0 + 0.5 + BP_T, nut=True)
        else:
            out.append(item(f"cabinet.{name}", box(BP["u0"] + u, BP["u0"] + u + w, yf - 7.5 - d, yf - 7.6, BP["v0"] + v, BP["v0"] + v + h),
                            "electrical", "bought", note + ", on the DIN rail", S))
    # DIN rails (top row and terminal row) and ducts, bolted
    for nm, (u0, u1, v, us) in (("din_top", (8, 375, 695, (13, 215, 372))), ("din_terminals", (8, 335, 50, (13, 329)))):
        rail = box(BP["u0"] + u0, BP["u0"] + u1, yf - 7.5, yf - 0.5, BP["v0"] + v - 17.5, BP["v0"] + v + 17.5)
        rp = [(BP["u0"] + uu, yf - 7.5, BP["v0"] + v) for uu in us]
        rail = drill(rail, "-y", rp, 2.25)
        out.append(item(f"cabinet.{nm}", rail, "steel", "bought", "DIN rail 35 x 7.5", S))
        holes += rp
        screw(f"cabinet.{nm}", "E02", [f"cabinet.{nm}", "cabinet.backplate"], "SHCS", 4, rp, (0, 1, 0), grip=7.5 + BP_T, nut=True)
    for k, (va, vb) in enumerate(DUCT_V):
        du = box(BP["u0"] + 5, BP["u0"] + BP["W"] - 5, yf - 60, yf - 0.5, BP["v0"] + va, BP["v0"] + vb)
        du = du - box(BP["u0"] + 7, BP["u0"] + BP["W"] - 7, yf - 61, yf - 2.5, BP["v0"] + va + 2, BP["v0"] + vb - 2)
        dp = [(BP["u0"] + uu, yf - 2.5, BP["v0"] + (va + vb) / 2) for uu in (40, 280, 520)]
        du = drill(du, "-y", dp, 2.25)
        out.append(item(f"cabinet.duct_{k}", du, "plastic", "bought", "slotted wiring duct 40 x 60, lid", S))
        holes += dp
        screw(f"cabinet.duct_{k}", "E02", [f"cabinet.duct_{k}", "cabinet.backplate"], "SHCS", 4, dp, (0, 1, 0), grip=2.5 + BP_T, nut=True)
    bp = drill(bp, "-y", [(p[0], yf, p[2]) for p in holes], 2.25)
    out.append(item("cabinet.backplate", bp, "steel", "bought", "galvanised backplate 560 x 760 x 3", S))
    screw("cabinet.backplate", "E03", ["cabinet.backplate", "cabinet.enclosure"], "SHCS", 6,
          [(BP["u0"] + u, BP_Y, BP["v0"] + v) for u, v in studs_uv], (0, 1, 0), grip=BP_T, hole=15)
    # ---- pneumatics on the right upright's +x face, behind the cabinet: filter-regulator and a 3-valve manifold
    xr = UPR[1] + 20
    frl = box(xr + 0.5, xr + 60.5, yr - 40, yr + 20, 200, 360)
    frl = drill(frl, "+x", [(xr + 60.5, yr - 20, z) for z in (230, 330)], 2.75)
    out.append(item("air.frl", frl, "plastic", "bought", "filter-regulator 6 bar with gauge and dump valve, G1/4", S))
    vm = box(xr + 0.5, xr + 50.5, yr - 40, yr + 20, 380, 500)
    vm = drill(vm, "+x", [(xr + 50.5, yr - 20, z) for z in (400, 480)], 2.75)
    out.append(item("air.valves", vm, "plastic", "bought", "manifold, 3 x 5/2 24 V solenoid valves: tool release, taper blow, pop-up pins", S))
    up1 = [i for i, it in enumerate(out) if it["name"] == "cabinet_stand.upright_1"][0]
    out[up1]["part"] = drill(out[up1]["part"], "+x", [(xr, yr - 20, z) for z in (230, 330, 400, 480)], 2.75)
    for nm, zz, wd in (("air.frl", (230, 330), 60), ("air.valves", (400, 480), 50)):
        screw(nm, "E07", [nm, "cabinet_stand.upright_1"], "SHCS", 5, [(xr + 0.5 + wd, yr - 20, z) for z in zz], (-1, 0, 0),
              grip=wd + 40.5, nut=True, washer=True)
    return out


# ------------------------------------------------------------------ sensors, flags, front E-stop, pop-up pins, ducts
def machine_side(g, items):
    """Home switches and their targets, the front E-stop, the pop-up pins and the cable ducts (local frame unless noted)."""
    out = []
    S_ = g["SPOIL_T"]
    SP_OFF, COL_W = g["SP_OFF"], g["COL_W"]
    c1 = g["REF"][0] - SP_OFF
    BLK_Z = g["BLK_Z"]
    # X home: M12 inductive sensors on brackets off the feet's +x end, looking down at steel flags on the substrate
    xpark = g["X_TRAVEL"][0] - SP_OFF + 20.0
    for nm, y, s in (("bottom", g["Y_RB"], 1), ("top", g["Y_RT"], -1)):
        ys_ = y + s * 22.0
        br = box(c1 + 0.5, c1 + 3.5, ys_ - 20, ys_ + 20, BLK_Z, BLK_Z + 20) + box(c1 + 0.5, c1 + 32, ys_ - 20, ys_ + 20, BLK_Z + 20, BLK_Z + 23)
        br = br - cyl("z", (c1 + 20, ys_, 0), 6.2, BLK_Z + 19, BLK_Z + 24)
        br = drill(br, "+x", [(c1 + 3.5, ys_ + k * 14, BLK_Z + 10) for k in (-1, 1)], 2.75)
        out.append(item(f"sensors.x_home_{nm}_bracket", br, "steel", "made", "3 mm angle, 2 x M5 into the foot's end", "x"))
        sen = cyl("z", (c1 + 20, ys_, 0), 6.0, -S_ + 6.5, BLK_Z + 19.5) + cyl("z", (c1 + 20, ys_, 0), 9.0, BLK_Z + 23.5, BLK_Z + 28.5)
        out.append(item(f"sensors.x_home_{nm}", sen, "electrical", "bought", "inductive sensor M12, 4 mm, PNP NO, 2 m PUR cable", "x"))
        foot = f"gantry_frame.foot_{nm}_base"
        fi = [i for i, it in enumerate(items) if it["name"] == foot][0]
        items[fi]["part"] = drill(items[fi]["part"], "+x", [(c1, ys_ + k * 14, BLK_Z + 10) for k in (-1, 1)], 2.1, depth=12)
        screw(f"sensors.x_home_{nm}_bracket", "E05", [f"sensors.x_home_{nm}_bracket", foot], "SHCS", 5,
              [(c1 + 3.5, ys_ + k * 14, BLK_Z + 10) for k in (-1, 1)], (-1, 0, 0), grip=3.5, hole=12)
        yf0, yf1 = sorted((y + s * 14.0, y + s * 34.0))
        yfs = y + s * 28.0
        fl = box(xpark - 20, xpark + 20, yf0, yf1, -S_ - 0.5 + 0.5, -S_ + 2.5)
        fl = drill(fl, "+z", [(xpark + k * 12, yfs, -S_ + 2.5) for k in (-1, 1)], 2.5)
        out.append(item(f"sensors.x_flag_{nm}", fl, "steel", "made", "3 mm steel flag, 2 screws into the substrate", "fixed"))
        sub = "bed.substrate.0"
        screw(f"sensors.x_flag_{nm}", "E05", [f"sensors.x_flag_{nm}", sub], "WOOD", 4.5, [(xpark + k * 12, yfs, -S_ + 2.5) for k in (-1, 1)], (0, 0, -1),
              grip=3.0, into="MDF", L=20, tapped=False)
    # Y home: on the column's +x web near the bottom, looking up at the rope anchor (steel) at the bottom of travel
    zs = g["SHEAVE_Z"]
    ysen = g["Y_WORK"][0] - g["REF"][1] - 4.0              # sensor face 4 mm under the anchor, carriage at home (anchor drawn at REF)
    yb_ = ysen - 50.0
    br = box(c1 + 0.5, c1 + 3.5, yb_ - 25, yb_ + 5, zs - 15, zs + 15) + box(c1 + 0.5, c1 + 36, yb_ + 2, yb_ + 5, zs - 15, zs + 15)
    br = br - cyl("y", (c1 + 26, 0, zs), 6.2, yb_ + 1, yb_ + 6)
    br = drill(br, "+x", [(c1 + 3.5, yb_ - 15, zs + k * 8) for k in (-1, 1)], 2.75)
    out.append(item("sensors.y_home_bracket", br, "steel", "made", "3 mm angle, 2 x M5 into the column web", "x"))
    sen = cyl("y", (c1 + 26, 0, zs), 6.0, yb_ + 5.5, ysen) + cyl("y", (c1 + 26, 0, zs), 9.0, yb_ - 4.5, yb_ + 1.5)
    out.append(item("sensors.y_home", sen, "electrical", "bought", "inductive sensor M12, 4 mm, PNP NO, 2 m PUR cable", "x"))
    wi = [i for i, it in enumerate(items) if it["name"] == "gantry_frame.web_px"][0]
    items[wi]["part"] = drill(items[wi]["part"], "+x", [(c1, yb_ - 15, zs + k * 8) for k in (-1, 1)], 2.1)
    screw("sensors.y_home_bracket", "E05", ["sensors.y_home_bracket", "gantry_frame.web_px"], "SHCS", 5,
          [(c1 + 3.5, yb_ - 15, zs + k * 8) for k in (-1, 1)], (-1, 0, 0), grip=3.5)
    # Z home: on the Y plate's outer face, looking down at a steel tab on the Z plate's inner face (Z at the top of its stroke)
    YR, BLK_H, PL, ZR = g["Y_RISER"], g["BLK_H"], g["PL"], g["Z_RISER"]
    Ypi = c1 + YR + BLK_H
    Ypf, Zpi = Ypi + PL, Ypi + PL + ZR + BLK_H
    ysz = g["REF"][1] + 95.0
    zn_ref = g["REF"][2] + g["TIP_TO_NOSE"]
    z_tab_top = zn_ref + g["ZP1"] - 10.0
    z_face = z_tab_top + (g["ZN_MAX"] - (g["REF"][2] + g["TIP_TO_NOSE"])) + 4.0     # tab top at the top of the stroke, + 4
    tab = box(Zpi - 22, Zpi - 0.5, ysz - 12, ysz + 12, z_tab_top - 25, z_tab_top) + box(Zpi - 3.5, Zpi - 0.5, ysz - 12, ysz + 12, z_tab_top - 45, z_tab_top)
    tab = drill(tab, "-x", [(Zpi - 0.5, ysz, z_tab_top - 37)], 2.75)
    out.append(item("sensors.z_target", tab, "steel", "made", "3 mm steel target tab, M5 into the Z plate", "xyz"))
    zi = [i for i, it in enumerate(items) if it["name"] == "z_axis.z_plate"][0]
    items[zi]["part"] = drill(items[zi]["part"], "-x", [(Zpi, ysz, z_tab_top - 37)], 2.1, depth=12)
    screw("sensors.z_target", "Z01", ["sensors.z_target", "z_axis.z_plate"], "SHCS", 5, [(Zpi - 3.5, ysz, z_tab_top - 37)], (1, 0, 0), grip=3.0, hole=12, into="6061")
    zsb = box(Ypf + 0.5, Ypf + 3.5, ysz - 15, ysz + 15, z_face + 8, z_face + 41) + box(Ypf + 0.5, Ypf + 22, ysz - 15, ysz + 15, z_face + 38, z_face + 41)
    zsb = zsb - cyl("z", (Zpi - 11, ysz, 0), 6.2, z_face + 37, z_face + 42)
    zsb = drill(zsb, "+x", [(Ypf + 3.5, ysz, z_face + 23 + k * 8) for k in (-1, 1)], 2.75)
    out.append(item("sensors.z_home_bracket", zsb, "steel", "made", "3 mm angle, 2 x M5 into the Y plate", "xy"))
    sen = cyl("z", (Zpi - 11, ysz, 0), 6.0, z_face, z_face + 37.5) + cyl("z", (Zpi - 11, ysz, 0), 9.0, z_face + 41.5, z_face + 46.5)
    out.append(item("sensors.z_home", sen, "electrical", "bought", "inductive sensor M12, 4 mm, PNP NO, 2 m PUR cable", "xy"))
    yi = [i for i, it in enumerate(items) if it["name"] == "y_carriage.y_plate"][0]
    items[yi]["part"] = drill(items[yi]["part"], "+x", [(Ypf, ysz, z_face + 23 + k * 8) for k in (-1, 1)], 2.1, depth=12)
    screw("sensors.z_home_bracket", "C01", ["sensors.z_home_bracket", "y_carriage.y_plate"], "SHCS", 5,
          [(Ypf + 3.5, ysz, z_face + 23 + k * 8) for k in (-1, 1)], (-1, 0, 0), grip=3.5, hole=12, into="6061")
    return out


def front_estop(g):
    """A 1-hole E-stop box on the left outrigger's outer side near its tip, at the operator's knee (world); ears with 2 screws."""
    xo = g["xs_legs"][0] - 39.0
    yf = g["Y_FRONT"]
    z0 = g["ZB0"] + 5
    bx = box(xo - 80.5, xo - 3.5, yf + 30, yf + 110, z0, z0 + 80)
    ears = box(xo - 3.5, xo - 0.5, yf + 15, yf + 125, z0 + 25, z0 + 55)
    pts = [(xo - 3.5, yf + 22, z0 + 40), (xo - 3.5, yf + 118, z0 + 40)]
    part = drill(bx + ears, "-x", pts, 2.75)
    head = cyl("x", (0, yf + 70, z0 + 40), 20.0, xo - 115, xo - 80.5)
    items_ = [item("estop.front_box", part + head, "electrical", "bought", "E-stop, 40 mm red mushroom, 2 NC, in a yellow 1-hole box with ears", "world")]
    screw("estop.front_box", "E05", ["estop.front_box", "floor_frame.outrigger_0"], "TEK", 4.8, pts, (1, 0, 0), grip=3.5, L=19, tapped=False)
    return items_


def popup_pins(g):
    """3 compact air cylinders under the substrate; their pins rise through it and the spoilboard to locate the sheet."""
    out = []
    S_, T = g["SPOIL_T"], g["SUBSTRATE_T"]
    zb = -S_ - T                                             # substrate's back face
    for k, x in enumerate(PINS_X):
        y = -12.0
        body = cyl("z", (x, y, 0), 12.0, zb - 75, zb - 15) + box(x - 22, x + 22, y - 22, y + 22, zb - 15, zb - 0.5)
        body = drill(body, "+z", [(x + sx * 15, y + sy * 15, zb - 0.5) for sx in (-1, 1) for sy in (-1, 1) if sx * sy > 0], 2.25)
        pin = cyl("z", (x, y, 0), 5.9, zb - 15, -2.0)               # retracted: 2 mm under the spoilboard's face
        out.append(item(f"popup.cyl_{k}", body + pin, "steel", "bought", "compact air cylinder 16 bore, 30 stroke, 12 mm pin, flange on top", "fixed"))
        screw(f"popup.cyl_{k}", "E07", [f"popup.cyl_{k}", f"bed.substrate.{0 if x < 1000 else 1 if x < 2000 else 2}"], "WOOD", 4.5,
              [(x + sx * 15, y + sy * 15, zb - 15) for sx in (-1, 1) for sy in (-1, 1) if sx * sy > 0], (0, 0, 1), grip=14.5, L=30, into="MDF", tapped=False)
    return out


def ducts(g):
    """PVC trunking 40 x 35 on the X chain tray's rear shelf (behind the chain, above the rear posts' ends), from the X chain's
    fixed end to the bed's right end (local); its lid goes on once the cables are in."""
    out = []
    F = g["CHAIN_SPECS"]["bed.x_chain"]["F"]
    x1b = g["X_BED"][1]
    y0, z0 = g["XCH_Y"][0] + g["XCH_TRAY"], g["XCH_Z"][0]
    du = box(F[0] - 30, x1b - 0.5, y0 + 0.5, y0 + 35, z0 - 40, z0 - 2) - box(F[0] - 31, x1b, y0 + 2.5, y0 + 36, z0 - 38, z0 - 4)
    dp = [(x, y0 + 2.5, z0 - 21) for x in (F[0] + 100, (F[0] + x1b) / 2, x1b - 100)]
    out.append(item("ducts.beam", du, "plastic", "bought", "PVC trunking 40 x 35 on the chain tray's rear shelf", "fixed"))
    screw("ducts.beam", "E06", ["ducts.beam", "bed.x_chain_tray"], "TEK", 4.8, dp, (0, -1, 0), grip=2.5, L=16, tapped=False)
    out.append(item("ducts.beam_lid", box(F[0] - 30, x1b - 0.5, y0 + 35.3, y0 + 37, z0 - 40, z0 - 2), "plastic", "bought", "trunking lid, clipped on", "fixed"))
    return out


def world_ducts(g):
    """Trunking down the back of the stand's left upright, and a tray under the cabinet (world)."""
    yr = g["Y_REAR"]
    out = []
    xu = UPR[0] - 20
    riser = box(xu - 40.5, xu - 0.5, yr - 30, yr + 30, CAB["z0"] - 120, 1690.0) - box(xu - 41, xu - 2.5, yr - 28, yr + 28, CAB["z0"] - 121, 1691)
    out.append(item("ducts.riser", riser, "plastic", "bought", "PVC trunking 40 x 60 down the stand's left upright", "world"))
    screw("ducts.riser", "E06", ["ducts.riser", "cabinet_stand.upright_0"], "TEK", 4.8, [(xu - 2.5, yr - 15, z) for z in (700, 1100, 1500)], (1, 0, 0),
          grip=2.5, L=19, tapped=False)
    out.append(item("ducts.riser_lid", box(xu - 42.5, xu - 40.8, yr - 30, yr + 30, CAB["z0"] - 120, 1690.0), "plastic", "bought", "trunking lid, clipped on", "world"))
    tray = box(UPR[0] + 20.5, CAB["x0"] + 320, 120.0, yr - 1.0, CAB["z0"] - 122, CAB["z0"] - 120) + box(UPR[0] + 20.5, UPR[0] + 23.5, yr - 35, yr - 5, CAB["z0"] - 140, CAB["z0"] - 100)
    tray = drill(tray, "+x", [(UPR[0] + 23.5, yr - 20, CAB["z0"] - 120 + k * 12) for k in (-1, 1)], 2.75)
    out.append(item("ducts.tray", tray, "steel", "made", "2 mm cable tray under the cabinet, flange on the left upright", "world"))
    screw("ducts.tray", "E06", ["ducts.tray", "cabinet_stand.upright_0"], "TEK", 4.8, [(UPR[0] + 23.5, yr - 20, CAB["z0"] - 120 + k * 12) for k in (-1, 1)],
          (-1, 0, 0), grip=3.5, L=19, tapped=False)
    return out




# ------------------------------------------------------------------ cables, hoses and internal wires
# name: (what, outside dia mm, kg/m, device it starts at, chains it runs through in order, cabinet terminal)
CABLE_LIST = [
    ("cable.spindle_power", "4G2.5 shielded continuous-flex", 13.0, 0.30, "spindle.body", ["Z", "Y", "X"], "cabinet.vfd"),
    ("cable.spindle_fan", "3G0.75 continuous-flex", 6.5, 0.08, "spindle.body", ["Z", "Y", "X"], "cabinet.terminals"),
    ("cable.spindle_sensors", "5 x 0.25 continuous-flex (clamp, unclamp sensors)", 6.0, 0.06, "spindle.body", ["Z", "Y", "X"], "cabinet.terminals"),
    ("hose.tool_release", "PU 8/6 air", 8.0, 0.03, "spindle.body", ["Z", "Y", "X"], "air.valves"),
    ("hose.taper_blow", "PU 6/4 air", 6.0, 0.02, "spindle.body", ["Z", "Y", "X"], "air.valves"),
    ("cable.z_motor_power", "4 x 1.0 shielded continuous-flex", 8.0, 0.10, "y_carriage.z_motor", ["Y", "X"], "cabinet.drv_z"),
    ("cable.z_motor_encoder", "encoder 6 x 0.14 shielded", 7.0, 0.06, "y_carriage.z_motor", ["Y", "X"], "cabinet.drv_z"),
    ("cable.z_home", "3 x 0.34 PUR", 5.0, 0.04, "sensors.z_home", ["Y", "X"], "cabinet.terminals"),
    ("cable.y_motor_power", "4 x 1.0 shielded continuous-flex", 8.0, 0.10, "gantry_drives.y_motor", ["X"], "cabinet.drv_y"),
    ("cable.y_motor_encoder", "encoder 6 x 0.14 shielded", 7.0, 0.06, "gantry_drives.y_motor", ["X"], "cabinet.drv_y"),
    ("cable.y_brake", "2 x 0.75 continuous-flex", 6.0, 0.05, "gantry_drives.y_brake", ["X"], "cabinet.terminals"),
    ("cable.y_home", "3 x 0.34 PUR", 5.0, 0.04, "sensors.y_home", ["X"], "cabinet.terminals"),
    ("cable.x1_motor_power", "4 x 1.0 shielded continuous-flex", 8.0, 0.10, "gantry_drives.x_motor_bottom", ["X"], "cabinet.drv_x1"),
    ("cable.x1_motor_encoder", "encoder 6 x 0.14 shielded", 7.0, 0.06, "gantry_drives.x_motor_bottom", ["X"], "cabinet.drv_x1"),
    ("cable.x2_motor_power", "4 x 1.0 shielded continuous-flex", 8.0, 0.10, "gantry_drives.x_motor_top", ["X"], "cabinet.drv_x2"),
    ("cable.x2_motor_encoder", "encoder 6 x 0.14 shielded", 7.0, 0.06, "gantry_drives.x_motor_top", ["X"], "cabinet.drv_x2"),
    ("cable.x1_home", "3 x 0.34 PUR", 5.0, 0.04, "sensors.x_home_bottom", ["X"], "cabinet.terminals"),
    ("cable.x2_home", "3 x 0.34 PUR", 5.0, 0.04, "sensors.x_home_top", ["X"], "cabinet.terminals"),
    ("cable.estop_front", "4 x 0.75 PUR", 6.5, 0.06, "estop.front_box", [], "cabinet.safety_relay"),
    ("hose.popup_pins", "PU 6/4 air, tee to 3 cylinders", 6.0, 0.02, "popup.cyl_1", [], "air.valves"),
    ("hose.supply", "PU 10/7 air from the compressor's line", 10.0, 0.05, "air.frl", [], "air.valves"),
    ("cable.mains", "3G2.5 H07RN-F, 3 m, 15 A plug", 11.0, 0.20, "cabinet.rcd", [], "cabinet.terminals"),
]
# internal wiring: (from, to, what) - every component's terminals in use
WIRES = [
    ("cable.mains", "cabinet.rcd", "L N PE: 15 A plug to RCBO 16 A 30 mA, PE to the PE bar"),
    ("cabinet.rcd", "cabinet.mcb_vfd", "L N 2.5 mm2"), ("cabinet.rcd", "cabinet.mcb_psu", "L N 1.5 mm2"), ("cabinet.rcd", "cabinet.mcb_ctl", "L 1.0 mm2"),
    ("cabinet.mcb_vfd", "cabinet.emc_filter", "L N 2.5 mm2"), ("cabinet.emc_filter", "cabinet.vfd", "L N 2.5 mm2 to R/L1 S/L2"),
    ("cabinet.mcb_psu", "cabinet.contactor", "L N 1.5 mm2 through the main contacts"),
    ("cabinet.contactor", "cabinet.psu_x1", "L N 1.0 mm2"), ("cabinet.contactor", "cabinet.psu_x2", "L N 1.0 mm2"),
    ("cabinet.contactor", "cabinet.psu_y", "L N 1.0 mm2"), ("cabinet.contactor", "cabinet.psu_z", "L N 1.0 mm2"),
    ("cabinet.psu_x1", "cabinet.drv_x1", "+60 V / 0 V 1.5 mm2"), ("cabinet.psu_x2", "cabinet.drv_x2", "+60 V / 0 V 1.5 mm2"),
    ("cabinet.psu_y", "cabinet.drv_y", "+60 V / 0 V 1.5 mm2"), ("cabinet.psu_z", "cabinet.drv_z", "+60 V / 0 V 1.5 mm2"),
    ("cabinet.mcb_ctl", "cabinet.psu_24", "L N 1.0 mm2"),
    ("cabinet.psu_24", "cabinet.terminals", "24 V / 0 V bus 1.0 mm2"),
    ("cabinet.terminals", "cabinet.controller", "24 V supply, 16 inputs (home switches, spindle sensors, VFD fault, driver alarms)"),
    ("cabinet.controller", "cabinet.drv_x1", "step, dir, enable, alarm (shielded 4-pair)"), ("cabinet.controller", "cabinet.drv_x2", "step, dir, enable, alarm"),
    ("cabinet.controller", "cabinet.drv_y", "step, dir, enable, alarm"), ("cabinet.controller", "cabinet.drv_z", "step, dir, enable, alarm"),
    ("cabinet.controller", "cabinet.vfd", "0-10 V speed, run/stop, fault (shielded)"),
    ("cabinet.controller", "cabinet.brake_relay", "output: Y brake release"), ("cabinet.brake_relay", "cabinet.terminals", "24 V to the brake's terminals"),
    ("cabinet.controller", "cabinet.valve_relays", "outputs: tool release, taper blow, pop-up pins"),
    ("cabinet.valve_relays", "air.valves", "24 V to 3 solenoids (3 x 2 x 0.5 cable via the gland)"),
    ("cabinet.terminals", "cabinet.safety_relay", "door E-stop and front E-stop, 2 channels each, in series"),
    ("cabinet.safety_relay", "cabinet.contactor", "safety output to the contactor coil (drops the stepper supplies)"),
    ("cabinet.safety_relay", "cabinet.vfd", "STO1 / STO2: safe torque off"),
    ("cabinet.safety_relay", "cabinet.controller", "E-stop status input"),
    ("cabinet.psu_24", "cabinet.fan", "24 V to the filter fan"),
]


def cable_names():
    return [c[0] for c in CABLE_LIST] + [f"wire.{i:02d}" for i in range(len(WIRES))]


def chain_fill(g):
    """Cables each chain carries (outside diameters), from the schedule."""
    out = {"X": [], "Y": [], "Z": []}
    for c in CABLE_LIST:
        for ch in c[5]:
            out[ch].append(c[2])
    return out


# ------------------------------------------------------------------ routes
def _chain_end(spec, ref):
    """The chain's moving end at the reference pose, and its fixed end (local)."""
    m = {"x": ref[0], "y": ref[1], "tip": ref[2]}[spec["var"]] + spec["m_off"]
    p, _ = D.chain_point(spec, m, spec["L"])
    return tuple(p), tuple(spec["F"])


CH = {"X": "bed.x_chain", "Y": "gantry_drives.y_chain", "Z": "y_carriage.z_chain"}
CH_MOVING = {"X": "x", "Y": "xy", "Z": "xyz"}           # the group each chain's moving end rides with
CH_FIXED = {"X": "fixed", "Y": "x", "Z": "xy"}
GROUP_CHAINS = {"xyz": ["Z", "Y", "X"], "xy": ["Y", "X"], "x": ["X"], "fixed": [], "world": []}


def routes(g, items):
    """Each cable as waypoints [(point, group)] with ("chain", X) markers, device end first (local frame unless group is world)."""
    ref = g["REF"]
    grp = {it["name"]: it["group"] for it in items}
    cen = {it["name"]: it["part"].centre() for it in items}
    c1 = ref[0] - g["SP_OFF"]
    c0 = c1 - g["COL_W"]
    mot = {"gantry_drives.x_motor_bottom": (g["x_motor_loc"](c0, g["Y_RB"]), "x"), "gantry_drives.x_motor_top": (g["x_motor_loc"](c0, g["Y_RT"]), "x"),
           "gantry_drives.y_motor": (g["y_motor_loc"](c0), "x"), "y_carriage.z_motor": (g["z_motor_loc"](c1, ref[1]), "xy")}
    ends = {k: _chain_end(g["CHAIN_SPECS"][v], ref) for k, v in CH.items()}
    W = g["W"]

    def wp(p):
        return tuple((W * D.Location.translation(*p)).position())
    F = ends["X"][1]
    x1b, YT, BB = g["X_BED"][1], g["Y_RT"], g["BED_BACK"]
    yr = g["Y_REAR"]
    yd, zd = g["XCH_Y"][0] + g["XCH_TRAY"] + 15, g["XCH_Z"][0] - 21
    duct_in = (F[0], yd, zd)
    duct_out = (x1b - 5, yd, zd)
    o = wp(duct_out)
    xr_ = UPR[0] - 40
    tail = [(duct_in, "fixed"), (duct_out, "fixed"), ((xr_, o[1], o[2]), "world"), ((xr_, yr, 1650.0), "world"),
            ((xr_, yr, CAB["z0"] - 110), "world"), ((xr_, yr + 40, CAB["z0"] - 110), "world"), ((UPR[0] + 30, yr + 40, CAB["z0"] - 110), "world"),
            ((UPR[0] + 60, 230.0, CAB["z0"] - 115), "world")]
    out = {}
    for name, what, od, kgm, dev, chains, term in CABLE_LIST:
        if dev in mot:
            loc, dg = mot[dev]
            p0 = tuple((loc * D.Location.translation(0, -55, -150)).position())
        elif dev == "spindle.body":
            dg = "xyz"
            zn = ref[2] + g["TIP_TO_NOSE"]
            p0 = (ref[0] + g["SP_W"] / 2 + 2, ref[1] + (28 if "power" in name else -28), zn + g["SP_L"] - 15)
        else:
            dg = grp.get(dev, "world")
            p0 = tuple(cen[dev])
        pts = [(p0, dg)]
        for ch in chains:
            mv, fx = ends[ch]
            pts.append((mv, CH_MOVING[ch]))
            pts.append(("chain", ch))
            pts.append((fx, CH_FIXED[ch]))
        gl = (CAB["x0"] + 120 + 70 * (len(out) % 6), 230.0, CAB["z0"] - 2.5)
        tc = (BP["u0"] + 280, BP_Y - 40, BP["v0"] + 100)
        for nm_, (u, v), (w, h), d, kg, how, note in COMPONENTS:
            if f"cabinet.{nm_}" == term:
                tc = (BP["u0"] + u + w / 2, BP_Y - d / 2, BP["v0"] + v + h / 2)
        if term.startswith("air."):
            tc = tuple(cen[term])
        if chains:
            pts += tail
        elif dev.startswith("estop"):
            ex = tuple(cen[dev])
            pts += [((ex[0], g["front_lo"][1] + 60, g["ZB1"] + 10), "world"), ((x1b, g["front_lo"][1] + 60, g["ZB1"] + 10), "world"),
                    ((UPR[0] + 60, 120.0, CAB["z0"] - 115), "world")]
        elif dev.startswith("popup"):
            pts += [((1200.0, -12.0, -g["SPOIL_T"] - g["SUBSTRATE_T"] - 40), "fixed"), ((x1b - 30, -12.0, -g["SPOIL_T"] - g["SUBSTRATE_T"] - 40), "fixed"),
                    ((UPR[1] + 60, yr - 20, 450.0), "world")]
        if term.startswith("air."):
            pts += [(tc, "world")]
        elif dev == "cabinet.rcd":
            pts = [((CAB["x0"] + 120, 230.0, CAB["z0"] - 400), "world"), (gl, "world"), (tc, "world")]
        else:
            pts += [(gl, "world"), (tc, "world")]
        out[name] = dict(name=name, what=what, od=od, kgm=kgm, dev=dev, dev_group=dg, chains=chains, term=term, pts=pts)
    return out


def check(g, items, require, routes_):
    """R63: every cable and hose from a real device, through the chains its device's axis needs, to a real terminal; every
    device has its cables; every cabinet part is wired. R67: cabinet heat. Returns cable lengths (m)."""
    import math as m_
    names = {it["name"] for it in items} | set(g["MOTORS"])
    W = g["W"]

    def wp(p, gr):
        return p if gr == "world" else tuple((W * D.Location.translation(*p)).position())
    text = ("Every cable and hose shall run from a real device, through the cable chains its axis needs (in order), to a real "
            "terminal in the cabinet, and be laid and terminated in a step (faults)")
    lengths = {}
    for nm, c in routes_.items():
        faults = []
        if c["dev"] not in names:
            faults.append(f"no device {c['dev']}")
        if c["term"] not in names:
            faults.append(f"no terminal {c['term']}")
        if c["chains"] != GROUP_CHAINS.get(c["dev_group"], []):
            faults.append(f"runs through {c['chains']} but its device rides on {c['dev_group']}")
        L = 0.0
        prev = None
        for wpnt in c["pts"]:
            if wpnt[0] == "chain":
                L += g["CHAIN_SPECS"][CH[wpnt[1]]]["L"]
                prev = None
                continue
            p, gr = wpnt
            if prev is not None:
                pg = prev[1]
                if pg != gr and not ({pg, gr} <= {"fixed", "world"}):
                    faults.append(f"free run from {pg} to {gr}: it would be torn as the axes move")
                L += m_.dist(wp(prev[0], pg), wp(p, gr))
            prev = (p, gr)
        L += 600.0                                         # 300 mm service loop at each end
        lengths[nm] = L / 1000.0
        require("R63", text, len(faults), "<=", 0, "", case=f"E08 {nm}: {c['what']}, {L / 1000:.1f} m" + (f"; {faults[0]}" if faults else ""))
    need = {"spindle.body": 5, "gantry_drives.x_motor_bottom": 2, "gantry_drives.x_motor_top": 2, "gantry_drives.y_motor": 2, "y_carriage.z_motor": 2,
            "gantry_drives.y_brake": 1, "sensors.x_home_bottom": 1, "sensors.x_home_top": 1, "sensors.y_home": 1, "sensors.z_home": 1,
            "estop.front_box": 1, "popup.cyl_1": 1, "air.frl": 1}
    for dev, n in need.items():
        got = sum(1 for c in routes_.values() if c["dev"] == dev)
        require("R63", text, abs(got - n), "<=", 0, "", case=f"E09 {dev}: {got} of {n} cables and hoses")
    comps = [f"cabinet.{c[0]}" for c in COMPONENTS] + ["cabinet.fan", "air.valves"]
    for cp in comps:
        used = any(cp in (a, b) for a, b, _ in WIRES) or any(c["term"] == cp for c in routes_.values())
        require("R63", text, 0 if used else 1, "<=", 0, "", case=f"E02 {cp}: " + ("wired" if used else "nothing connected"))
    loss = 4 * 150.0 * (1 / 0.86 - 1) + 4 * 12.0 + 0.03 * g["p_shaft"] / 0.9 + 5 + 5 + 3
    area = 2 * (0.6 * 0.8 + 0.6 * 0.3 + 0.8 * 0.3)
    need_m3h = 3.1 * max(0.0, loss - 5.5 * area * 10.0) / 10.0
    require("R67", "The cabinet shall stay within 10 K of the room: its filter fan moves enough air for the heat its walls can't shed (m3/h)",
            need_m3h, "<=", FAN_M3H, "m3/h", evidence={"tool": f"losses {loss:.0f} W (supplies at 86 %, drivers, VFD at 97 %); walls 5.5 W/m2K over {area:.2f} m2; "
                                                                "airflow 3.1 x P / dT", "leaves_out": "sun, other heat in the room"})
    return lengths
