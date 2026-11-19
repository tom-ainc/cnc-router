"""Detailed parts of the router: bought parts at catalogue sizes, fabricated parts with their holes.

Builders make each part in its own canonical frame; `frame(origin, xdir, zdir)` places it. Assembly functions
work in the router's local machine frame (x along the sheet, y up the bed, z out of the bed) and take `g`, the
router script's globals, for every layout dimension, so the detail follows the layout.

Each assembly returns items: dict(name, part, mat, kind, note, group, qty)
  kind "bought" (note: part number) or "made" (note: how it is made); group: which axes move it.
"""
import math

from golf_py import Axis, Location, Part, Sketch

DENS = {"steel": 7.85, "6061": 2.70, "MDF": 0.75, "UHMW": 0.94, "cast iron": 7.2}   # g/cm^3


# ------------------------------------------------------------------ geometry helpers
def box(x0, x1, y0, y1, z0, z1):
    return Part.cuboid(x1 - x0, y1 - y0, z1 - z0).moved(
        Location.translation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def cyl(axis, c, r, a0, a1):
    """Cylinder along `axis` through point c (its other two coordinates), from a0 to a1 along the axis."""
    p = Part.cylinder(r, a1 - a0)
    m = (a0 + a1) / 2
    if axis == "z":
        return p.moved(Location.translation(c[0], c[1], m))
    if axis == "x":
        return p.moved(Location.translation(m, c[1], c[2]) * Location.about(Axis.Y, 90))
    return p.moved(Location.translation(c[0], m, c[2]) * Location.about(Axis.X, 90))


def fuse(parts):
    parts = [p for p in parts if p is not None]
    return parts[0].fuse_all(parts[1:]) if len(parts) > 1 else parts[0]


_FACE = {"+z": None, "-z": (Axis.X, 180), "+x": (Axis.Y, 90), "-x": (Axis.Y, -90), "+y": (Axis.X, -90), "-y": (Axis.X, 90)}


def drill(part, face, pts, r, depth=None, cbore=None):
    """Holes from the face whose outward normal is `face`, at points on that face. cbore = (radius, depth)."""
    if not pts:
        return part
    rot = _FACE[face]
    locs = [Location.translation(*p) * (Location.about(*rot) if rot else Location.translation(0, 0, 0)) for p in pts]
    if cbore:
        return part.counter_bore_hole(locs, radius=r, bore_radius=cbore[0], bore_depth=cbore[1], depth=depth)
    return part.hole(locs, radius=r, depth=depth)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def frame(origin, xdir, zdir):
    """Location taking the canonical frame (x, z) to (xdir, zdir) at origin: built from axis and angle."""
    ydir = _cross(zdir, xdir)
    R = [[xdir[i], ydir[i], zdir[i]] for i in range(3)]          # columns are the images of ex, ey, ez
    tr = R[0][0] + R[1][1] + R[2][2]
    c = max(-1.0, min(1.0, (tr - 1) / 2))
    ang = math.degrees(math.acos(c))
    T = Location.translation(*origin)
    if ang < 1e-6:
        return T
    if abs(ang - 180) < 1e-6:
        ax = [math.sqrt(max(0.0, (R[i][i] + 1) / 2)) for i in range(3)]
        k = max(range(3), key=lambda i: ax[i])
        for i in range(3):
            if i != k:
                ax[i] = math.copysign(ax[i], R[k][i] + R[i][k]) if ax[i] else 0.0
        return T * Location.about(Axis((0, 0, 0), tuple(ax)), 180)
    s = 2 * math.sin(math.radians(ang))
    ax = ((R[2][1] - R[1][2]) / s, (R[0][2] - R[2][0]) / s, (R[1][0] - R[0][1]) / s)
    return T * Location.about(Axis((0, 0, 0), ax), ang)


def hull2d(circles, n=48):
    pts = sorted(set((round(cx + r * math.cos(2 * math.pi * i / n), 4), round(cy + r * math.sin(2 * math.pi * i / n), 4))
                     for cx, cy, r in circles for i in range(n)))

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def rhs(axis, x0, x1, y0, y1, z0, z1, t):
    """Hollow rectangular section filling the box, open along `axis`, wall t."""
    e = {"x": (x0 - 1, x1 + 1, y0 + t, y1 - t, z0 + t, z1 - t), "y": (x0 + t, x1 - t, y0 - 1, y1 + 1, z0 + t, z1 - t),
         "z": (x0 + t, x1 - t, y0 + t, y1 - t, z0 - 1, z1 + 1)}[axis]
    return box(x0, x1, y0, y1, z0, z1) - box(*e)


# ------------------------------------------------------------------ bought parts, canonical frames
def c_rail(L, pitch=60.0, end=20.0):
    """HGR25R rail along +x from 0 to L: 23 wide, 22 high on z = 0, ball-track grooves, M6 counterbores 11 x 9 deep."""
    r = box(0, L, -11.5, 11.5, 0, 22)
    r = r - box(-1, L + 1, 9.3, 12.5, 13.5, 17.5) - box(-1, L + 1, -12.5, -9.3, 13.5, 17.5)
    pts = [(end + pitch * i, 0, 22) for i in range(int((L - 2 * end) // pitch) + 1)]
    return drill(r, "+z", pts, 3.5, cbore=(5.5, 9))


def rail_holes(L, pitch=60.0, end=20.0):
    return [end + pitch * i for i in range(int((L - 2 * end) // pitch) + 1)]


def c_block():
    """HGH25CA block centred on x = 0 over a rail on z = 0: 48 wide, 58 body + 2 x 13 seals = 84, 5.5 to 40 high,
    rail channel, M6 x 8 tapped holes at 35 x 35, grease nipple."""
    body = box(-29, 29, -24, 24, 5.5, 40)
    seals = box(-42, -29, -22, 22, 7, 37) + box(29, 42, -22, 22, 7, 37)
    b = (body + seals) - box(-43, 43, -12, 12, -1, 23)
    b = drill(b, "+z", [(sx * 17.5, sy * 17.5, 40) for sx in (-1, 1) for sy in (-1, 1)], 2.5, depth=8)
    return b + cyl("x", (0, 0, 28), 3.5, -42 - 9, -42)


def c_support(L, B, H, h, bore, P, cap=0.0, hole_r=3.3):
    """BK/BF support unit: screw along +x through the origin, block x 0..L, base face z = -h, width B along y,
    H high; 2 bolt holes down through it at y = +-P/2; BK's bearing cap on the -x side."""
    blk = box(0, L, -B / 2, B / 2, -h, H - h)
    blk = blk - box(-1, L + 1, -B / 2 - 1, -B / 2 + (B - 0.6 * B) / 2, H - h - 0.45 * H, H - h + 1) \
              - box(-1, L + 1, B / 2 - (B - 0.6 * B) / 2, B / 2 + 1, H - h - 0.45 * H, H - h + 1)
    blk = blk - cyl("x", (0, 0, 0), bore / 2, -1, L + 1)
    blk = drill(blk, "+z", [(L / 2, sy * P / 2, H - h - 0.45 * H) for sy in (-1, 1)], hole_r)
    if cap:
        blk = blk + (cyl("x", (0, 0, 0), bore / 2 + 9, -cap, 0) - cyl("x", (0, 0, 0), bore / 2 + 1, -cap - 1, 1))
    return blk


def c_nut(D, FL, FT, L, d, pcd, nholes=6):
    """Flanged ball nut along +x centred on 0, flange at the +x end, `nholes` x 6.6 on `pcd`, one flat on the flange."""
    n = cyl("x", (0, 0, 0), D / 2, -L / 2, L / 2) + cyl("x", (0, 0, 0), FL / 2, L / 2 - FT, L / 2)
    n = n - box(L / 2 - FT - 1, L / 2 + 1, FL / 2 - 6, FL / 2 + 1, -FL / 2, FL / 2)                   # flat
    n = drill(n, "+x", [(L / 2, pcd / 2 * math.cos(math.radians(a)), pcd / 2 * math.sin(math.radians(a)))
                        for a in [30 + 360 / nholes * i for i in range(nholes)] if math.cos(math.radians(a)) * pcd / 2 < FL / 2 - 8], 3.3)
    return n - cyl("x", (0, 0, 0), d / 2 + 0.5, -L, L)


def pulley_hub_r(teeth, width=15.0):
    return min((teeth * 5 / math.pi - 1.14) / 2 - 2, 18)


def c_pulley(teeth, width=15.0, bore=14.0):
    """HTD 5M pulley on +z from 0: flanges, toothed body, hub with an M5 set screw on +x; pitch diameter teeth x 5 / pi."""
    pd = teeth * 5 / math.pi
    od = pd - 1.14
    hr = pulley_hub_r(teeth, width)
    p = fuse([cyl("z", (0, 0, 0), od / 2 + 4, 0, 1.5), cyl("z", (0, 0, 0), od / 2, 1.5, 2.5 + width),
              cyl("z", (0, 0, 0), od / 2 + 4, 2.5 + width, 4 + width), cyl("z", (0, 0, 0), hr, 4 + width, 12 + width)])
    p = p - cyl("z", (0, 0, 0), bore / 2, -1, 20 + width)
    return drill(p, "+x", [(hr, 0, 8 + width)], 2.1)


def pulley_setscrew(name, step, loc, teeth, bore, width=15.0):
    """The pulley's set screw, on a flat on the shaft: tip at the bore."""
    hr = pulley_hub_r(teeth, width)
    wall = hr - bore / 2
    L = max(l for l in FA.LENGTHS if l <= wall + 0.2) if wall >= 5.8 else 4
    screw(name, step, [name.rsplit("_set", 1)[0]], "SET", 5, [tp(loc, (hr, 0, 8 + width))], tv(loc, (-1, 0, 0)), grip=0.0, L=L, tapped=True,
          into="6061")


def c_belt(centres, pds, width=15.0, t=3.6):
    """HTD 5M belt loop in the xy plane over pulleys at `centres` with pitch diameters `pds`, z 0..width."""
    outer = hull2d([(x, y, pd / 2 + t / 2) for (x, y), pd in zip(centres, pds)])
    inner = hull2d([(x, y, pd / 2 - t / 2) for (x, y), pd in zip(centres, pds)])
    return Sketch.polygon(outer).extrude(width) - Sketch.polygon(inner).extrude(width + 2).moved(Location.translation(0, 0, -1))


def c_pinion(pcd, m, face, bore=14.0, teeth=20):
    """Helical pinion on +z from 0: trapezoid teeth (tip pcd/2 + m, root pcd/2 - 1.25 m), hub above, bore."""
    tip, root = pcd / 2 + m, pcd / 2 - 1.25 * m
    pts = []
    for i in range(teeth):
        a0 = 2 * math.pi * i / teeth
        da = 2 * math.pi / teeth
        for frac, r in ((0.0, root), (0.18, root), (0.32, tip), (0.68, tip), (0.82, root)):
            a = a0 + frac * da
            pts.append((r * math.cos(a), r * math.sin(a)))
    p = Sketch.polygon(pts).extrude(face)
    p = p - cyl("z", (0, 0, 0), bore / 2, -1, face + 1)
    return drill(p, "+x", [(root - 0.3, 0, face / 2)], 2.1)


def c_holder(tool_d=12.0, stick=55.0):
    """ISO30 holder with ER32 nut and cutter, nose (gauge line) at z = 0, taper up (+z), cutter down."""
    taper = Part.cone(31.75 / 2, 17.4 / 2, 47.8).moved(Location.translation(0, 0, 47.8 / 2))
    stud = cyl("z", (0, 0, 0), 6.5, 47.8, 47.8 + 18)
    flange = cyl("z", (0, 0, 0), 23.0, -15.9, 0) - (cyl("z", (0, 0, 0), 24.0, -11, -5) - cyl("z", (0, 0, 0), 20.0, -11, -5))
    body = cyl("z", (0, 0, 0), 20.0, -45, -15.9)
    nut = cyl("z", (0, 0, 0), 25.0, -65, -45)
    tool = cyl("z", (0, 0, 0), tool_d / 2, -65 - stick, -65)
    return fuse([taper, stud, flange, body, nut]), tool


def c_spindle(L=510.0, W=133.0, rear=50.0):
    """9 kW ISO30 ATC spindle (133 square x 510): nose at z = 0, body up +z. Finned rounded-square housing,
    front bearing nose, rear fan cowl, power and sensor plugs. Beyond 510 x 133 x 133 the shapes are estimates."""
    body = box(-W / 2, W / 2, -W / 2, W / 2, 40, L - 30)
    body = body.fillet(body.edges().parallel_to(Axis.Z), 12)
    for k in range(9):
        z = 75 + k * 40
        ring = box(-W / 2 - 1, W / 2 + 1, -W / 2 - 1, W / 2 + 1, z, z + 6) - box(-W / 2 + 3, W / 2 - 3, -W / 2 + 3, W / 2 - 3, z - 1, z + 7)
        body = body - ring
    nose = cyl("z", (0, 0, 0), 55.0, 0, 40)
    back = box(-W / 2 + 6, W / 2 - 6, -W / 2 + 6, W / 2 - 6, L - 30, L)
    cowl = cyl("z", (0, 0, 0), 48.0, L, L + rear) - cyl("z", (0, 0, 0), 40.0, L + 10, L + rear + 1)
    plug1 = cyl("x", (0, 28, L - 15), 13.0, W / 2 - 25, W / 2 - 0.5)
    plug2 = cyl("x", (0, -28, L - 15), 9.0, W / 2 - 25, W / 2 - 0.5)
    sp = fuse([body, nose, back, cowl, plug1, plug2])
    taper = Part.cone(32.2 / 2, 18.0 / 2, 48.5).moved(Location.translation(0, 0, 48.5 / 2 - 0.3))
    return sp - taper - cyl("z", (0, 0, 0), 8.0, 47, 120)


def c_chain_loop(run_len_a, run_len_b, R, h, w):
    """Cable chain side view in the xz plane: run A along +x on z 0..h from x 0 to run_len_a, a 180 deg bend of radius R
    (to the chain's centre line) at x = run_len_a, run B back along -x at z 2R..2R+h for run_len_b. Width w along y."""
    a = box(0, run_len_a, 0, w, 0, h)
    b = box(run_len_a - run_len_b, run_len_a, 0, w, 2 * R, 2 * R + h)
    ring = cyl("y", (run_len_a, 0, R + h / 2), R + h / 2, 0, w) - cyl("y", (run_len_a, 0, R + h / 2), R - h / 2, -1, w + 1)
    ring = ring - box(run_len_a - R - h - 1, run_len_a, -1, w + 1, -1, 2 * R + h + 1)
    return fuse([a, b, ring])


def item(name, part, mat, kind, note, group, qty=1):
    return dict(name=name, part=part, mat=mat, kind=kind, note=note, group=group, qty=qty)


# ------------------------------------------------------------------ joints: every fastener and weld, registered where the holes are drilled
import fasteners as FA

JOINTS = []     # dict(name, step, parts (head side first; the last takes the thread unless there is a nut), f, pts, dir, grip, hole, into)
WELDS = []      # dict(name, step, a, b, how)


def tp(loc, p):
    """A point of a canonical frame, placed by `loc`."""
    return (loc * Location.translation(*p)).position()


def tv(loc, v):
    a, b = tp(loc, (0, 0, 0)), tp(loc, v)
    return tuple(b[i] - a[i] for i in range(3))


def screw(name, step, parts, kind, d, pts, dirn, grip, hole=None, into="steel", L=None, nut=False, washer=False, tapped=True):
    """Fasteners at pts (where each head bears), along dirn, through `grip` mm of the parts before the last one.
    The length is the shortest standard one that engages enough thread (and stays short of a blind hole's bottom)."""
    if L is None:
        csk = 0.0
        need = FA.ENGAGE[into] * d
        nut_h = FA.ISO[d][7] + (1.6 if washer else 0.0) + 0.5 if nut else 0.0
        L = FA.choose_length(grip, need, hole, kind, nut_h, csk)
    f = FA.spec(kind, d, L or 0, nut=nut, washer=washer)
    JOINTS.append(dict(name=name, step=step, parts=list(parts), f=f, pts=[tuple(float(c) for c in p) for p in pts], dir=tuple(dirn),
                       grip=grip, hole=hole, into=into, tapped=tapped and not nut, ok_len=L is not None))


def weld(name, step, a, b, how):
    WELDS.append(dict(name=name, step=step, a=a, b=b, how=how))


# ================================================================== assemblies (router's local frame)
def _rail_x(g, x0, x1, y):
    return c_rail(x1 - x0).moved(frame((x0, y, -g["SPOIL_T"]), (1, 0, 0), (0, 0, 1)))


def rack_profile(x0, x1, y_c, w, m, sgn, beta=19.5, pa=20.0, shift=0.0):
    """Outline (x, y) of a rack w deep with teeth on its sgn y face: transverse pitch pi m / cos(beta), 20 deg flanks,
    addendum m, dedendum 1.25 m, tips on the face. `shift` slides the teeth along x (to draw the helix in slices)."""
    p = math.pi * m / math.cos(math.radians(beta))
    tn = math.tan(math.radians(pa))
    tip_y = y_c + sgn * w / 2
    pl = tip_y - sgn * m
    root_y = pl - sgn * 1.25 * m
    back_y = y_c - sgn * w / 2
    hw_tip, hw_root = p / 4 - m * tn, p / 4 + 1.25 * m * tn
    pts = [(x0, back_y), (x1, back_y), (x1, root_y)]
    k = int(math.floor((x1 - x0 - shift) / p))
    teeth = []
    for i in range(k, -1, -1):
        xc = x0 + shift + p / 2 + i * p
        if xc + hw_root > x1 - 0.2 or xc - hw_root < x0 + 0.2:
            continue
        teeth += [(xc + hw_root, root_y), (xc + hw_tip, tip_y), (xc - hw_tip, tip_y), (xc - hw_root, root_y)]
    pts += teeth + [(x0, root_y)]
    return pts if sgn < 0 else list(reversed(pts))


def _rack(g, y_c, sgn, x0=None, x1=None):
    """m1.5 helical rack on its land: real tooth profile, the 19.5 deg helix drawn as 4 stepped slices; M6 counterbores at 125."""
    if x0 is None:
        x0, x1 = g["X_BED"]
    w, h, m = g["RACK_W"], g["RACK_H"], g["M_GEAR"]
    z0 = g["RACK_Z"][0]
    n = 4
    tb = math.tan(math.radians(19.5))
    slices = []
    for k in range(n):
        zz = z0 + k * h / n
        sk = Sketch.polygon(rack_profile(x0, x1, y_c, w, m, sgn, shift=1.0 + (k + 0.5) * h / n * tb)).extrude(h / n - 0.02)
        slices.append(sk.moved(Location.translation(0, 0, zz + 0.01)))
    r = fuse(slices)          # the slices are 0.02 apart, so the union is cheap
    xb0 = g["X_BED"][0]
    pts = [(xb0 + 62.5 + 125 * i + 0.05, y_c - sgn * 2.5, z0 + h) for i in range(40)]
    return drill(r, "+z", [p for p in pts if x0 < p[0] < x1], 3.3, cbore=(5.5, 6.5))


def bed_assembly(g):
    x0, x1 = g["X_BED"]
    S, LAND, BB = g["SPOIL_T"], g["LAND"], g["BED_BACK"]
    Y_RB, Y_RT = g["Y_RB"], g["Y_RT"]
    out = []
    zf = -S - LAND                                      # beam front face
    for nm, (ya, yb) in (("bottom", (Y_RB - 80, Y_RB + 20)), ("top", (Y_RT - 20, Y_RT + 80))):
        beam = rhs("x", x0 + 5, x1 - 5, ya, yb, BB, zf, 5.0)
        out.append(item(f"bed.rail_beam_{nm}", beam, "steel", "made", "RHS 100x80x5, ends capped", "fixed"))
        for k, xc in enumerate((x0 + 2.5, x1 - 2.5)):
            out.append(item(f"bed.beam_cap_{nm}_{k}", box(xc - 2.5, xc + 2.5, ya, yb, BB, zf), "steel", "made", "5 mm plate, welded", "fixed"))
            weld(f"bed.beam_cap_{nm}_{k}", "B01" if nm == "bottom" else "B02", f"bed.beam_cap_{nm}_{k}", f"bed.rail_beam_{nm}", "fillet all round, ground flush")
    # lands: rail lands 30 x 10 and rack lands 17 x 13, welded, then flattened by hand; tapped M6 for the rails and racks
    holes = rail_holes(x1 - x0)
    for nm, y in (("bottom", Y_RB), ("top", Y_RT)):
        land = box(x0, x1, y - 15, y + 15, zf, -S)
        land = drill(land, "+z", [(x0 + h, y, -S) for h in holes], 2.5, depth=12)
        out.append(item(f"bed.rail_land_{nm}", land, "steel", "made", "flat 30x10, welded, flattened by hand; M6 tapped at 60", "fixed"))
        weld(f"bed.rail_land_{nm}", "B04", f"bed.rail_land_{nm}", f"bed.rail_beam_{nm}", "30 mm stitches at 150, both sides, alternating")
        screw(f"bed.x_rail_{nm}", "X01", [f"bed.x_rail_{nm}", f"bed.rail_land_{nm}"], "SHCS", 6,
              [(x0 + h, y, -S + 13) for h in holes], (0, 0, -1), grip=13, hole=12)
    rack_pitch = [x0 + 62.5 + 125 * i for i in range(int((x1 - x0 - 62.5) // 125) + 1)]
    for nm, y, sgn in (("bottom", Y_RB - g["RACK_OFF"], -1), ("top", Y_RT + g["RACK_OFF"], 1)):
        land = box(x0, x1, y - g["RACK_W"] / 2, y + g["RACK_W"] / 2, zf, g["RACK_Z"][0])
        land = drill(land, "+z", [(xr + 0.05, y - sgn * 2.5, g["RACK_Z"][0]) for xr in rack_pitch], 2.5, depth=12)
        out.append(item(f"bed.rack_land_{nm}", land, "steel", "made", "flat 17x16, welded, flattened by hand to 13; M6 tapped at 125", "fixed"))
        weld(f"bed.rack_land_{nm}", "B04", f"bed.rack_land_{nm}", f"bed.rail_beam_{nm}", "30 mm stitches at 150, both sides, alternating")
    zs = -S - g["SUBSTRATE_T"]
    for i, xc in enumerate(g["cross_x"]):
        cm = rhs("y", xc - 25, xc + 25, Y_RB + 20, Y_RT - 20, zs - 50, zs - 0.5, 3.0)
        out.append(item(f"bed.cross_{i:02d}", cm, "steel", "made", "RHS 50x50x3, welded between the rail beams", "fixed"))
        for nm in ("bottom", "top"):
            weld(f"bed.cross_{i:02d}_{nm}", "B03", f"bed.cross_{i:02d}", f"bed.rail_beam_{nm}", "fillet all round")
    xy0 = g["XCH_Y"][0]
    out.append(item("bed.x_chain_tray", box(x0, x1, xy0 + 0.5, xy0 + g["XCH_TRAY"], g["XCH_Z"][0] - 42, g["XCH_Z"][1]), "steel", "made",
                    "3 mm tray on the top rail beam, the X chain's fixed run sits in it; a 42 mm shelf behind for the cable trunking", "fixed"))
    weld("bed.x_chain_tray", "B04", "bed.x_chain_tray", "bed.rail_beam_top", "30 mm stitches at 300")
    # substrate in 3 boards (each under 30 kg), butted over cross members; countersunk self-drilling screws into the cross members
    cx = g["cross_x"]
    cuts = [x0] + [min(cx, key=lambda c: abs(c - (x0 + (x1 - x0) * k / 3))) for k in (1, 2)] + [x1]
    ys_sub = [Y_RB + 120, (Y_RB + Y_RT) / 2, Y_RT - 120]
    for k in range(3):
        a = cuts[k] + (0.25 if k else 0.0)
        b = cuts[k + 1] - (0.25 if k < 2 else 0.0)
        sub = box(a, b, Y_RB + 20.5, Y_RT - 20.5, zs, -S - 0.5)
        atc_b = [(x, y, zs) for x in (g["ATC_X"][0] + 2, g["ATC_X"][0] + 50) for y in (g["ATC_Y"][0] - 10, g["ATC_Y"][1] + 10) if a < x < b]
        sub = drill(sub, "-z", atc_b, 3.3)
        sub = drill(sub, "-z", [(x, -12.0, zs) for x in (400, 1200, 2100) if a < x < b], 6.5)
        out.append(item(f"bed.substrate.{k}", sub, "MDF", "made",
                        f"25 mm MDF {b - a:.0f} x {Y_RT - Y_RB - 41:.0f}, glued and screwed to the cross members; ends butt on a cross member", "fixed"))
        pts = []
        for i, c in enumerate(cx):
            if a - 1 <= c - 25 and c + 25 <= b + 1:
                pts += [(c, y, -S - 0.5) for y in ys_sub]
            elif abs(c - a) < 1:
                pts += [(c + 12, y, -S - 0.5) for y in ys_sub]
            elif abs(c - b) < 1:
                pts += [(c - 12, y, -S - 0.5) for y in ys_sub]
        for i, c in enumerate(cx):
            sel = [p for p in pts if abs(p[0] - c) <= 12.5]
            if sel:
                screw(f"bed.substrate.{k}_cross_{i:02d}", "B08", [f"bed.substrate.{k}", f"bed.cross_{i:02d}"], "TEK", 4.8, sel, (0, 0, -1),
                      grip=25.5, into="steel", L=45, tapped=False)
    # spoilboard in 2 boards (each under 30 kg), the joint off the substrate joints; screwed down, heads 6 mm under the face
    pins = [(xx, -12.0, 0) for xx in (400, 1200, 2100)]
    for k, (a, b) in enumerate(((-20, g["SPOIL_SPLIT"] - 0.25), (g["SPOIL_SPLIT"] + 0.25, g["SHEET_L"] + 20))):
        sp = box(a, b, -30, g["SHEET_W"] + 30, -S, 0)
        sp = drill(sp, "+z", [p for p in pins if a + 20 < p[0] < b - 20], 6.0)
        spts = [(xx, yy, -6.0) for xx in [a + 60 + i * (b - a - 120) / 4 for i in range(5)] for yy in (100.0, 600.0, 1100.0)
                if min(abs(xx - c) for c in cuts) > 30]
        sp = drill(sp, "+z", [(p[0], p[1], 0.0) for p in spts], 2.3, cbore=(5.5, 6.0))
        out.append(item(f"bed.spoilboard.{k}", sp, "MDF", "made",
                        f"25 mm MDF {b - a:.0f} x {g['SHEET_W'] + 60:.0f}, surfaced in place; 12 mm holes for the pop-up pins", "fixed"))
        for j in range(3):
            xa, xb = cuts[j], cuts[j + 1]
            sel = [p for p in spts if xa < p[0] < xb]
            if sel:
                screw(f"bed.spoilboard.{k}_sub{j}", "M02", [f"bed.spoilboard.{k}", f"bed.substrate.{j}"], "WOOD", 4.5, sel, (0, 0, -1),
                      grip=19.5, into="MDF", L=40, tapped=False)
    out.append(item("sheet", box(0, g["SHEET_L"], 0, g["SHEET_W"], 0, g["STOCK_T"]), "MDF", "outside", "the sheet", "fixed"))
    for nm, y in (("bottom", Y_RB), ("top", Y_RT)):
        out.append(item(f"bed.x_rail_{nm}", _rail_x(g, x0, x1, y), "steel", "bought", "HIWIN HGR25R, cut to length", "fixed"))
    # racks come in 1 m lengths, butted end to end (the last one cut)
    for nm, y, sgn in (("bottom", Y_RB - g["RACK_OFF"], -1), ("top", Y_RT + g["RACK_OFF"], 1)):
        xa, k = x0, 0
        while xa < x1 - 1:
            xb = min(xa + 1000.0, x1)
            out.append(item(f"bed.rack_{nm}.{k}", _rack(g, y, sgn, xa + 0.05, xb - 0.05), "steel", "bought",
                            "helical rack m1.5 17x17, 19.5 deg, 1 m" + (" (cut)" if xb - xa < 999 else ""), "fixed"))
            hp = [(xr + 0.05, y - sgn * 2.5, g["RACK_Z"][1] - 6.5) for xr in rack_pitch if xa + 0.05 < xr < xb - 0.05]
            screw(f"bed.rack_{nm}.{k}", "X02", [f"bed.rack_{nm}.{k}", f"bed.rack_land_{nm}"], "SHCS", 6, hp, (0, 0, -1),
                  grip=g["RACK_H"] - 6.5, hole=12)
            xa, k = xb, k + 1
    return out


def atc_assembly(g):
    """Fork plate on a spine between two stands; the stands bolt up through the substrate from behind."""
    xa, xb = g["ATC_X"]
    xc, fz = g["ATC_XC"], g["FORK_Z"]
    ya, yb = g["ATC_Y"]
    S = g["SPOIL_T"]
    out = []
    fork = box(xa - 9, xb + 9, ya - 20, yb + 20, fz, fz + 5)
    for yc in g["ATC_YC"]:
        fork = fork - (box(xa - 10, xc, yc - 20.5, yc + 20.5, fz - 1, fz + 6) + cyl("z", (xc, yc, 0), 20.5, fz - 1, fz + 6))
    # fork plate: 2 countersunk M5 into each stand's top, 3 into the spine
    fs_pts = [(xa + 5, y, fz + 5) for y in (ya - 10, yb + 10)] + [(xb + 3, y, fz + 5) for y in (ya - 10, yb + 10)]
    sp_pts = [(xb + 3, y, fz + 5) for y in (g["ATC_YC"][1] + 55, g["ATC_YC"][3] - 55 + 110 * 0, g["ATC_YC"][4] + 55)]
    fork = drill(fork, "+z", fs_pts + sp_pts, 2.75)
    spine = box(xb - 3, xb + 9, ya + 0.5, yb - 0.5, fz - 25, fz - 0.5)
    spine = drill(spine, "+z", [(p[0], p[1], fz - 0.5) for p in sp_pts], 2.1, depth=14)
    spine = drill(spine, "-y", [(xb + 3, ya + 0.5, fz - 12.5)], 2.5, depth=15)
    spine = drill(spine, "+y", [(xb + 3, yb - 0.5, fz - 12.5)], 2.5, depth=15)
    out.append(item("atc.fork_plate", fork, "6061", "made", "5 mm plate, 6 slots 41 wide engaging the ISO30 flange groove", "fixed"))
    out.append(item("atc.spine", spine, "6061", "made", "12 x 30 bar under the fork plate's back edge, M6 tapped each end", "fixed"))
    screw("atc_rack.fork_plate_stands", "K03", ["atc_rack.fork_plate", "atc_rack.stand_0"], "CSK", 5, fs_pts[:1] + fs_pts[2:3], (0, 0, -1),
          grip=5.0, hole=14, into="6061")
    screw("atc_rack.fork_plate_stand_1", "K03", ["atc_rack.fork_plate", "atc_rack.stand_1"], "CSK", 5, fs_pts[1:2] + fs_pts[3:4], (0, 0, -1),
          grip=5.0, hole=14, into="6061")
    screw("atc_rack.fork_plate_spine", "K03", ["atc_rack.fork_plate", "atc_rack.spine"], "CSK", 5, sp_pts, (0, 0, -1), grip=5.5, hole=14, into="6061")
    bolt_x = (xa + 2, xa + 50)                     # through the substrate from behind, clear of the cross member under the rack
    for k, (y0, y1) in enumerate(((ya - 20, ya), (yb, yb + 20))):
        st = box(xa - 9, xb + 9, y0, y1, -S - 0.5 + 0.5, fz - 0.01)
        st = drill(st, "-z", [(x, (y0 + y1) / 2, -S) for x in bolt_x], 2.5, depth=22)
        st = drill(st, "+z", [(p[0], (y0 + y1) / 2, fz - 0.01) for p in fs_pts if abs(p[1] - (y0 + y1) / 2) < 11], 2.1, depth=14)
        yy = y1 if k == 0 else y0
        st = drill(st, "-y" if k == 0 else "+y", [(xb + 3, y0, fz - 12.5)] if k == 0 else [(xb + 3, y1, fz - 12.5)], 3.3)
        out.append(item(f"atc.stand_{k}", st, "6061", "made", "20 mm plate stand, M6 tapped underneath, bolted up through the substrate", "fixed"))
        screw(f"atc_rack.stand_{k}_down", "K03", ["bed.substrate.2", f"atc_rack.stand_{k}"], "SHCS", 6,
              [(x, (y0 + y1) / 2, -S - g["SUBSTRATE_T"]) for x in bolt_x], (0, 0, 1), grip=25.0, hole=22, into="6061")
        # spine end screw: through the stand, into the spine's end
        if k == 0:
            screw("atc_rack.spine_0", "K03", ["atc_rack.stand_0", "atc_rack.spine"], "SHCS", 6, [(xb + 3, y0, fz - 12.5)], (0, 1, 0),
                  grip=20.5, hole=15, into="6061")
        else:
            screw("atc_rack.spine_1", "K03", ["atc_rack.stand_1", "atc_rack.spine"], "SHCS", 6, [(xb + 3, y1, fz - 12.5)], (0, -1, 0),
                  grip=20.5, hole=15, into="6061")
    z_nose = fz + 10.5
    for i, yc in enumerate(g["ATC_YC"]):
        h, t = c_holder(g["TOOL_D"], g["TOOL_STICK"])
        out.append(item(f"atc.holder_{i}", (h + t).moved(Location.translation(xc, yc, z_nose)), "steel", "bought",
                        "ISO30 holder, ER32, with cutter", "fixed"))
    return out


T_MOTOR_FLANGE = 10.0     # 34E1K-120 flange thickness under the bolt heads (assumed: the STEP's flange is not measured)
X_PULLEYS = (20, 60)      # X drive belt: 20T on the 14 mm motor shaft (a 15T is too small to bore 14), 60T on the pinion shaft


def x_drive_layout(g, c0, y, sgn):
    """Plan of one X drive: pinion axis, plate extents, standoffs, tab."""
    yp = y + sgn * (g["RACK_OFF"] + g["RACK_W"] / 2 - 1.5 + g["X_PINION_PCD"] / 2)
    xp = c0 - 55
    ylo, yhi = (yp - 56, y + 40) if sgn < 0 else (y - 40, yp + 56)
    xlo, xhi = xp - 52, c0 - 8
    y_p, y_m = (ylo + 8, yhi - 8) if sgn < 0 else (yhi - 8, ylo + 8)       # pinion side, motor side
    stand = [(xlo + 6, y_p), (xhi - 6, y_p), (xlo + 6, y_m), (xhi - 6, y)]   # clear of the pulleys, belt and motor screws
    return dict(yp=yp, xp=xp, ylo=ylo, yhi=yhi, xlo=xlo, xhi=xhi, stand=stand)


def gantry_assembly(g, xs):
    """Column weldment, feet, X blocks and drives, Y rails, screw, supports, brake, Y belt, top sheave, chain arm."""
    SP_OFF, COL_W, COL_D, COL_T, ZC0 = g["SP_OFF"], g["COL_W"], g["COL_D"], g["COL_T"], g["ZC0"]
    Y_RB, Y_RT, BLK_Z, S = g["Y_RB"], g["Y_RT"], g["BLK_Z"], g["SPOIL_T"]
    c1 = xs - SP_OFF
    c0 = c1 - COL_W
    cc = (c0 + c1) / 2
    yb, yt = Y_RB - 40, Y_RT + 40
    z0, z1 = ZC0, ZC0 + COL_D
    out = []
    G = "x"
    W = lambda n, a, b, how: weld(n, "G01" if "riser" not in n and "foot" not in n else "G02", a, b, how)
    # ---- column weldment
    sx, sy_, sz = c1 + g["ROPE_X"] - g["SHEAVE_D"] / 2, g["SHEAVE_Y"], g["SHEAVE_Z"]
    cap_y = yb + 5
    cap_web_z = [z0 + 60, z0 + COL_D / 2, z1 - 60]
    cap_fl_x = [cc - 40, cc + 40]
    dead_y, dead_z = yt - 55, sz + g["SHEAVE_D"]                 # rope dead end: an M8 bolt across the column under the top cap
    web_p = box(c1 - COL_T, c1, yb, yt, z0, z1)
    web_p = web_p - box(c1 - COL_T - 1, c1 + 1, sy_ - 62, sy_ + 62, sz - 20, sz + 20)
    web_p = drill(web_p, "+x", [(c1, dead_y, dead_z)], 4.5)
    out.append(item("gantry_frame.web_px", web_p, "steel", "made", f"plate {COL_D:g}x{COL_T:g}, slot for the rope sheave; M6 tapped for BK20/BF20", G))
    web_m = box(c0, c0 + COL_T, yb, yt, z0, z1)
    web_m = drill(web_m, "-x", [(c0, cap_y, z) for z in cap_web_z] + [(c0, dead_y, dead_z)], 3.3)
    web_m = drill(web_m, "-x", [(c0, dead_y, dead_z)], 4.5)
    out.append(item("gantry_frame.web_mx", web_m, "steel", "made", f"plate {COL_D:g}x{COL_T:g}", G))
    fb = box(c0 + COL_T, c1 - COL_T, yb, yt, z0, z0 + COL_T)
    fb = drill(fb, "-z", [(sx, sy_, z0)], 6.3)
    out.append(item("gantry_frame.flange_back", fb, "steel", "made", "plate 148x6; sheave axle nut welded inside before the box is closed", G))
    ff = box(c0 + COL_T, c1 - COL_T, yb, yt, z1 - COL_T, z1)
    ff = drill(ff, "+z", [(x, cap_y, z1) for x in cap_fl_x] + [(sx, sy_, z1)], 3.3)
    ff = drill(ff, "+z", [(sx, sy_, z1)], 6.3)
    yfx = [(cc + s * 18, g["Y_FIX"], z1) for s in (-1, 1)]
    ff = drill(ff, "+z", yfx, 2.5)
    out.append(item("gantry_frame.flange_front", ff, "steel", "made", "plate 148x6; M6 tapped for the Y chain bracket", G))
    for n_ in ("web_px", "web_mx"):
        for f_ in ("flange_back", "flange_front"):
            W(f"gantry_frame.{n_}_{f_}", f"gantry_frame.{n_}", f"gantry_frame.{f_}", "4 mm fillet, 50 mm stitches alternating sides and ends")
    cap_t = box(c0 + COL_T, c1 - COL_T, yt - 10, yt, z0 + COL_T, z1 - COL_T)
    ymp = [(x, yt, z) for x in (c0 + 25, c1 - 25) for z in (z0 + 140, z1 - 30)]
    cap_t = drill(cap_t, "+y", ymp, 3.4, depth=10)
    out.append(item("gantry_frame.cap_top", cap_t, "steel", "made", "plate 10, welded in; M8 tapped for the Y motor plate", G))
    W("gantry_frame.cap_top", "gantry_frame.cap_top", "gantry_frame.web_px", "fillet all round the top")
    cap_b = box(c0 + COL_T + 0.5, c1 - COL_T - 0.5, yb, yb + 10, z0 + COL_T + 0.5, z1 - COL_T - 0.5)
    cap_b = drill(cap_b, "-x", [(c0 + COL_T + 0.5, cap_y, z) for z in cap_web_z], 2.5, depth=14)
    cap_b = drill(cap_b, "+z", [(x, cap_y, z1 - COL_T - 0.5) for x in cap_fl_x], 2.5, depth=14)
    out.append(item("gantry_frame.cap_bottom", cap_b, "steel", "made", "plate 10, bolted in (5 x M6) so the counterweight goes in from below", G))
    screw("gantry_frame.cap_bottom_web", "W08", ["gantry_frame.web_mx", "gantry_frame.cap_bottom"], "SHCS", 6,
          [(c0, cap_y, z) for z in cap_web_z], (1, 0, 0), grip=COL_T + 0.5, hole=14)
    screw("gantry_frame.cap_bottom_flange", "W08", ["gantry_frame.flange_front", "gantry_frame.cap_bottom"], "SHCS", 6,
          [(x, cap_y, z1) for x in cap_fl_x], (0, 0, -1), grip=COL_T + 0.5, hole=14)
    # sheave axle: an M12 bolt from the front flange into a nut welded inside the back flange
    out.append(item("gantry_frame.sheave_axle_nut", cyl("z", (sx, sy_, 0), 9.9, z0 + COL_T, z0 + COL_T + 10.8) - cyl("z", (sx, sy_, 0), 5.1, z0, z1),
                    "steel", "bought", "M12 weld nut, welded inside the back flange", G))
    W("gantry_frame.sheave_axle_nut", "gantry_frame.sheave_axle_nut", "gantry_frame.flange_back", "tack all round, before the box is closed")
    screw("gantry_frame.sheave_axle", "G03", ["gantry_frame.flange_front", "gantry_frame.rope_sheave", "gantry_frame.sheave_axle_nut"], "HEX", 12,
          [(sx, sy_, z1)], (0, 0, -1), grip=COL_D - COL_T - 10.8, L=COL_D - COL_T + 3, into="nut")
    for i, zr in enumerate((ZC0 + 40, ZC0 + COL_D - 40)):
        riser = box(c1, c1 + g["Y_RISER"], g["Y_RAIL"][0], g["Y_RAIL"][1], zr - 12.5, zr + 12.5)
        rh = rail_holes(g["Y_RAIL"][1] - g["Y_RAIL"][0])
        riser = drill(riser, "+x", [(c1 + g["Y_RISER"], g["Y_RAIL"][0] + h, zr) for h in rh], 2.5, depth=14)
        out.append(item(f"gantry_frame.y_riser_{i}", riser, "steel", "made", "flat 40x25 welded on, flattened by hand; M6 tapped at 60", G))
        W(f"gantry_frame.y_riser_{i}", f"gantry_frame.y_riser_{i}", "gantry_frame.web_px", "30 mm stitches at 150 both sides, alternating")
        screw(f"gantry_drives.y_rail_{i}", "Y01", [f"gantry_drives.y_rail_{i}", f"gantry_frame.y_riser_{i}"], "SHCS", 6,
              [(c1 + g["Y_RISER"] + 13, g["Y_RAIL"][0] + h, zr) for h in rh], (-1, 0, 0), grip=13, hole=14)
    # ---- feet: base plate on two X blocks, two gussets up to the column
    drives = {}
    for nm, y, sgn in (("bottom", Y_RB, -1), ("top", Y_RT, 1)):
        L_ = x_drive_layout(g, c0, y, sgn)
        drives[nm] = (y, sgn, L_)
        base = box(c0, c1, y - 40, y + 40, BLK_Z, BLK_Z + 20)
        bpts = [(cc + dx + sx_ * 17.5, y + sy * 17.5, BLK_Z + 20) for dx in (-45, 45) for sx_ in (-1, 1) for sy in (-1, 1)]
        base = drill(base, "+z", bpts, 3.3, cbore=(5.5, 6.5))
        tabp = [(c0 + 9, y, BLK_Z + 20), (c0 + 25, y, BLK_Z + 20)]
        base = drill(base, "+z", tabp, 3.4, depth=16)
        if nm == "top":
            base = drill(base, "+y", [(x, y + 40, BLK_Z + 10) for x in (c0 + 80, c0 + 120)], 2.5, depth=15)
        out.append(item(f"gantry_frame.foot_{nm}_base", base, "steel", "made", "plate 20, 8 counterbored M6 into the X blocks; M8 tapped for the X drive", G))
        for k, yy in enumerate((y - 40, y + 30)):
            out.append(item(f"gantry_frame.foot_{nm}_gusset_{k}", box(c0, c1, yy, yy + 10, BLK_Z + 20, z0), "steel", "made", "plate 10, welded", G))
            W(f"gantry_frame.foot_{nm}_gusset_{k}_base", f"gantry_frame.foot_{nm}_gusset_{k}", f"gantry_frame.foot_{nm}_base", "fillet both sides")
            W(f"gantry_frame.foot_{nm}_gusset_{k}_col", f"gantry_frame.foot_{nm}_gusset_{k}", "gantry_frame.flange_back", "fillet both sides")
        for dx in (-45, 45):
            bn = f"gantry_drives.x_block_{nm}_{'l' if dx < 0 else 'r'}"
            out.append(item(bn, c_block().moved(frame((cc + dx, y, -S), (1 if dx < 0 else -1, 0, 0), (0, 0, 1))), "steel", "bought",
                            "HIWIN HGH25CA, grease nipple outwards", G))
            screw(f"gantry_frame.foot_{nm}_{'l' if dx < 0 else 'r'}", "G04", [f"gantry_frame.foot_{nm}_base", bn], "SHCS", 6,
                  [(p[0], p[1], BLK_Z + 13.5) for p in bpts if (p[0] - cc) * dx > 0], (0, 0, -1), grip=13.5, hole=8)
    # ---- X drives: 20T:60T belt, pinion shaft in 2 x 61902 bearings in a housing under the lower plate; the drive hangs
    # off the foot by a tab on its motor plate, bolted down through a spacer with slotted holes to set the mesh
    pf = g["PIN_FACE"]
    zp = (g["RACK_Z"][0] + g["RACK_Z"][1]) / 2
    zb = max(zp + pf / 2, g["RACK_Z"][1]) + 1
    for nm, (y, sgn, L_) in drives.items():
        xp, yp = L_["xp"], L_["yp"]
        D = f"gantry_drives.x_"
        pin = c_pinion(g["X_PINION_PCD"], g["M_GEAR"], pf, bore=15.0) + (cyl("z", (0, 0, 0), 12.0, -10.0, 0.01) - cyl("z", (0, 0, 0), 7.5, -11, 1))
        pin = drill(pin, "+y", [(0, 12.0, -5.0)], 2.1)
        pin_loc = Location.translation(xp, yp, zp - pf / 2) * Location.about(Axis.Z, 0 if sgn < 0 else 180) * Location.about(Axis.Z, 180)
        out.append(item(f"{D}pinion_{nm}", pin.moved(pin_loc), "steel", "bought", "helical pinion m1.5 20T, 19.5 deg, bored 15, hub with set screw on a flat", G))
        screw(f"{D}pinion_{nm}_set", "D0" + ("1" if nm == "bottom" else "2"), [f"{D}pinion_{nm}"], "SET", 5,
              [tp(pin_loc, (0, 12.0, -5.0))], tv(pin_loc, (0, -1, 0)), grip=0.0, L=4, into="steel")
        hz1 = BLK_Z - 0.5
        hous = cyl("z", (xp, yp, 0), 25.0, zb, hz1) + cyl("z", (xp, yp, 0), 34.0, hz1 - 5, hz1)
        hous = hous - cyl("z", (xp, yp, 0), 14.0, zb + 2, hz1 + 1) - cyl("z", (xp, yp, 0), 11.0, zb - 1, hz1 + 1)
        fl = [(xp + 29 * math.cos(math.radians(a)), yp + 29 * math.sin(math.radians(a)), hz1 - 5) for a in (90, 210, 330)]
        hous = drill(hous, "-z", fl, 2.25)
        out.append(item(f"{D}bearing_{nm}", hous, "6061", "made", "bearing housing, 2 x 61902, flange under the lower plate", G))
        for k, zz in enumerate((hz1 - 14.5, hz1 - 7.25)):
            br = cyl("z", (xp, yp, 0), 13.95, zz, zz + 7) - cyl("z", (xp, yp, 0), 7.55, zz - 1, zz + 8)
            out.append(item(f"{D}brg_{nm}_{k}", br, "steel", "bought", "61902-2RS bearing 15 x 28 x 7", G))
        out.append(item(f"{D}shaft_{nm}", cyl("z", (xp, yp, 0), 7.5, zp - pf / 2 - 9.5, BLK_Z + 36.5), "steel", "made",
                        "shaft 15 h6, flats for the pinion and pulley set screws", G))
        plate = box(L_["xlo"], L_["xhi"], L_["ylo"], L_["yhi"], BLK_Z, BLK_Z + 8)
        plate = drill(plate, "+z", [(xp, yp, BLK_Z + 8)], 8.5)
        plate = drill(plate, "-z", [(p[0], p[1], BLK_Z) for p in fl], 1.65)
        plate = drill(plate, "-z", [(px, py, BLK_Z) for px, py in L_["stand"]], 3.3)
        out.append(item(f"{D}pivot_plate_{nm}", plate, "6061", "made", "8 mm lower plate: bearing housing under it, 4 standoffs to the motor plate", G))
        screw(f"{D}bearing_{nm}", "D0" + ("1" if nm == "bottom" else "2"), [f"{D}bearing_{nm}", f"{D}pivot_plate_{nm}"], "SHCS", 4,
              fl, (0, 0, 1), grip=5.5, hole=8, into="6061")
        top = box(L_["xlo"], L_["xhi"], L_["ylo"], L_["yhi"], BLK_Z + 38, BLK_Z + 44) + box(L_["xhi"] - 1, c0 + 30, y - 26, y + 26, BLK_Z + 38, BLK_Z + 44)
        top = drill(top, "+z", [(xp, y, BLK_Z + 44)], 37.0)
        mh = [(xp + sx_ * 34.79, y + sy * 34.79, BLK_Z + 44) for sx_ in (-1, 1) for sy in (-1, 1)]
        top = drill(top, "+z", mh, 2.75)
        top = drill(top, "+z", [(px, py, BLK_Z + 44) for px, py in L_["stand"]], 3.3)
        top = drill(top, "+z", [(p[0], p[1], BLK_Z + 44) for p in tabp_of(c0, y, BLK_Z)], 4.5)
        out.append(item(f"{D}motor_plate_{nm}", top, "6061", "made", "6 mm, NEMA34 pattern, pilot 74; tab with 2 slots over the foot", G))
        spc = box(c0 + 2, c0 + 30, y - 24, y + 24, BLK_Z + 20.5, BLK_Z + 37.5)
        spc = drill(spc, "+z", [(p[0], p[1], BLK_Z + 37.5) for p in tabp_of(c0, y, BLK_Z)], 4.5)
        out.append(item(f"{D}tab_spacer_{nm}", spc, "steel", "made", "17 mm spacer block between the foot and the motor plate's tab", G))
        screw(f"{D}tab_{nm}", "D0" + ("3" if nm == "bottom" else "4"), [f"{D}motor_plate_{nm}", f"{D}tab_spacer_{nm}", f"gantry_frame.foot_{nm}_base"],
              "LHCS", 8, [(p[0], p[1], BLK_Z + 44) for p in tabp_of(c0, y, BLK_Z)], (0, 0, -1), grip=24.0, hole=16)
        for k, (px, py) in enumerate(L_["stand"]):
            so = cyl("z", (px, py, 0), 6.0, BLK_Z + 8, BLK_Z + 38)
            so = drill(so, "-z", [(px, py, BLK_Z + 8)], 2.5, depth=11)
            so = drill(so, "+z", [(px, py, BLK_Z + 38)], 2.5, depth=11)
            out.append(item(f"{D}standoff_{nm}_{k}", so, "steel", "bought", "standoff M6 x 30, hex 12, female both ends", G))
            screw(f"{D}standoff_{nm}_{k}_lo", "D0" + ("1" if nm == "bottom" else "2"), [f"{D}pivot_plate_{nm}", f"{D}standoff_{nm}_{k}"], "SHCS", 6,
                  [(px, py, BLK_Z)], (0, 0, 1), grip=8.0, hole=11)
            screw(f"{D}standoff_{nm}_{k}_hi", "D0" + ("1" if nm == "bottom" else "2"), [f"{D}motor_plate_{nm}", f"{D}standoff_{nm}_{k}"], "SHCS", 6,
                  [(px, py, BLK_Z + 44)], (0, 0, -1), grip=6.0, hole=11)
        p60 = Location.translation(xp, yp, BLK_Z + 9)
        out.append(item(f"{D}pulley60_{nm}", c_pulley(X_PULLEYS[1], bore=15.0).moved(p60), "6061", "bought", "HTD 5M 60T 15 wide, bore 15", G))
        pulley_setscrew(f"{D}pulley60_{nm}_set", "D0" + ("1" if nm == "bottom" else "2"), p60, X_PULLEYS[1], 15.0)
        p20 = Location.translation(xp, y, BLK_Z + 9) * Location.about(Axis.Z, 180)
        out.append(item(f"{D}pulley20_{nm}", c_pulley(X_PULLEYS[0], bore=14.0).moved(p20), "6061", "bought", "HTD 5M 20T 15 wide, bore 14", G))
        pulley_setscrew(f"{D}pulley20_{nm}_set", "D0" + ("1" if nm == "bottom" else "2"), p20, X_PULLEYS[0], 14.0)
        out.append(item(f"{D}belt_{nm}", c_belt([(xp, yp), (xp, y)], [X_PULLEYS[1] * 5 / math.pi, X_PULLEYS[0] * 5 / math.pi]).moved(Location.translation(0, 0, BLK_Z + 11)),
                        "rubber", "bought", "HTD 5M 15 wide belt", G))
        # motor: M5 through its flange and the plate, nuts underneath
        screw(f"{D}motor_{nm}", "D0" + ("1" if nm == "bottom" else "2"), [f"{D}motor_{nm}", f"{D}motor_plate_{nm}"], "SHCS", 5,
              [(p[0], p[1], BLK_Z + 44 + T_MOTOR_FLANGE) for p in mh], (0, 0, -1), grip=T_MOTOR_FLANGE + 6.0, nut=True, washer=True)
    # ---- Y rails, screw, supports, brake
    for i, zr in enumerate((ZC0 + 40, ZC0 + COL_D - 40)):
        out.append(item(f"gantry_drives.y_rail_{i}", c_rail(g["Y_RAIL"][1] - g["Y_RAIL"][0]).moved(
            frame((c1 + g["Y_RISER"], g["Y_RAIL"][0], zr), (0, 1, 0), (1, 0, 0))), "steel", "bought", "HIWIN HGR25R, cut to length", G))
    xs_, zs_ = c1 + g["YS_X"], g["YS_Z"]
    top = yt
    out.append(item("gantry_drives.y_screw", ballscrew("y", (xs_, 0, zs_), 25.0, yb - 5 - g["BRAKE_L"], top + 36, journal=(36 + 44, 5 + g["BRAKE_L"] + 21)),
                    "steel", "bought", "ball screw 25 x 20 lead (BSS2520 class), ends machined for BK20/BF20", G))
    for nm, (Ls, ycs, cap, ya_, yb_) in (("bk20", (35, top - 35, 8, top - 43, top)), ("bf20", (20, yb, 0, yb, yb + 20))):
        loc = frame((xs_, ycs, zs_), (0, 1, 0), (1, 0, 0))
        out.append(item(f"gantry_drives.y_{nm}", c_support(Ls, 88, 60, 34, 20, 70, cap=cap).moved(loc), "steel", "bought",
                        ("BK20 fixed support" if cap else "BF20 floating support"), G))
        hp = [tp(loc, (Ls / 2, sy * 35, 60 - 34 - 0.45 * 60)) for sy in (-1, 1)]
        sp = box(c1, c1 + 6, ya_, yb_, zs_ - 44, zs_ + 44)
        sp = drill(sp, "+x", [(c1 + 6, p[1], p[2]) for p in hp], 3.3)
        out.append(item(f"gantry_drives.y_spacer_{nm[:2]}", sp, "steel", "made", "6 mm spacer, ground", G))
        web_p_holes = [(c1, p[1], p[2]) for p in hp]
        out[[i for i, it in enumerate(out) if it["name"] == "gantry_frame.web_px"][0]]["part"] = drill(
            [it for it in out if it["name"] == "gantry_frame.web_px"][0]["part"], "+x", web_p_holes, 2.5)
        screw(f"gantry_drives.y_{nm}", "Y04", [f"gantry_drives.y_{nm}", f"gantry_drives.y_spacer_{nm[:2]}", "gantry_frame.web_px"], "SHCS", 6,
              hp, (-1, 0, 0), grip=0.55 * 60 + 6, L=45)
    bf_face = yb
    brk, bpts = brake_part(xs_, zs_, yb - 5 - g["BRAKE_L"], bf_face)
    out.append(item("gantry_drives.y_brake", brk, "steel", "bought", "24 V spring-applied brake, 4 N*m, 2 standoffs to the BF20", G))
    bf_i = [i for i, it in enumerate(out) if it["name"] == "gantry_drives.y_bf20"][0]
    out[bf_i]["part"] = drill(out[bf_i]["part"], "-y", [(p[0], bf_face, p[2]) for p in bpts], 2.1, depth=12)
    screw("gantry_drives.y_brake", "Y03", ["gantry_drives.y_brake", "gantry_drives.y_bf20"], "SHCS", 5, bpts, (0, 1, 0), grip=8.0, hole=12)
    # ---- Y belt over the top cap
    zm = ZC0 + COL_D - 60
    plate = box(c0 - 95, xs_ + 25, top + 0.5, top + 7, zs_ - 30, zm + 45)
    plate = drill(plate, "+y", [(c0 - 50, top + 7, zm)], 37.0)
    plate = drill(plate, "+y", [(xs_, top + 7, zs_)], 15.0)
    ymh = [(c0 - 50 + sx_ * 34.79, top + 7, zm + sz_ * 34.79) for sx_ in (-1, 1) for sz_ in (-1, 1)]
    plate = drill(plate, "+y", ymh, 2.1)
    plate = drill(plate, "+y", [(p[0], top + 7, p[2]) for p in ymp], 4.5)
    out.append(item("gantry_drives.y_motor_plate", plate, "steel", "made", "6.5 mm steel on the column's top cap; NEMA34 pattern tapped M5, screw bore", G))
    screw("gantry_drives.y_motor_plate", "Y05", ["gantry_drives.y_motor_plate", "gantry_frame.cap_top"], "SHCS", 8,
          [(p[0], top + 7, p[2]) for p in ymp], (0, -1, 0), grip=7.0, hole=10)
    screw("gantry_drives.y_motor", "Y05", ["gantry_drives.y_motor", "gantry_drives.y_motor_plate"], "SHCS", 5,
          [(p[0], top - T_MOTOR_FLANGE, p[2]) for p in ymh], (0, 1, 0), grip=T_MOTOR_FLANGE + 0.5, hole=6.5)
    for nm, (px, pz, teeth, bore) in (("motor", (c0 - 50, zm, 30, 14.0)), ("screw", (xs_, zs_, 20, 15.0))):
        loc = frame((px, top + 8, pz), (1, 0, 0), (0, 1, 0))
        out.append(item(f"gantry_drives.y_pulley_{nm}", c_pulley(teeth, bore=bore).moved(loc), "6061", "bought", f"HTD 5M {teeth}T 15 wide, bore {bore:g}", G))
        pulley_setscrew(f"gantry_drives.y_pulley_{nm}_set", "Y05", loc, teeth, bore)
    yb_loop = c_belt([(c0 - 50, -zm), (xs_, -zs_)], [30 * 5 / math.pi, 20 * 5 / math.pi]).moved(frame((0, top + 10, 0), (1, 0, 0), (0, 1, 0)))
    out.append(item("gantry_drives.y_belt", yb_loop, "rubber", "bought", "HTD 5M 15 wide belt", G))
    # ---- top rope sheave (inside the column top, through the slot), on its axle
    sh = cyl("z", (sx, sy_, 0), g["SHEAVE_D"] / 2 + 5, sz - 15, sz - 12) + cyl("z", (sx, sy_, 0), g["SHEAVE_D"] / 2 - 2, sz - 12, sz + 12) + \
        cyl("z", (sx, sy_, 0), g["SHEAVE_D"] / 2 + 5, sz + 12, sz + 15)
    sh = sh - cyl("z", (sx, sy_, 0), 6.1, sz - 16, sz + 16)
    out.append(item("gantry_frame.rope_sheave", sh, "6061", "bought", "rope sheave 100 PCD for 5 mm rope, sealed bearings, bore 12", G))
    # rope dead end: an M8 bolt across the column under the top cap; the rope's eye goes over it
    screw("gantry_frame.rope_dead_end", "W01", ["gantry_frame.web_px", "gantry_frame.web_mx"], "HEX", 8, [(c1, dead_y, dead_z)], (-1, 0, 0),
          grip=COL_W, L=180, nut=True, washer=True)
    # ---- chain arm from the top foot's end, up over the rack to the X chain's moving end
    xz0, xy1 = g["XCH_Z"][0], g["XCH_Y"][1]
    ya0 = Y_RT + 40.5
    arm1 = box(c0 + 60, c0 + 140, ya0, xy1 + 12, -3, BLK_Z + 15) - box(c0 + 63, c0 + 137, ya0 + 3, xy1 + 9, 0, BLK_Z + 16)
    tab = box(c0 + 60, c0 + 140, ya0, ya0 + 3, BLK_Z, BLK_Z + 20)
    arm2 = box(c0 + 60, c0 + 140, xy1 + 0.5, xy1 + 12, xz0, -2.5)
    arm = fuse([arm1, tab, arm2])
    apts = [(x, ya0 + 3, BLK_Z + 10) for x in (c0 + 80, c0 + 120)]
    arm = drill(arm, "+y", apts, 3.3)
    out.append(item("gantry_frame.chain_arm", arm, "steel", "made",
                    "3 mm folded channel bolted to the top foot's end, over the rack, to the X chain's moving end", G))
    screw("gantry_frame.chain_arm", "K01", ["gantry_frame.chain_arm", "gantry_frame.foot_top_base"], "SHCS", 6, apts, (0, -1, 0), grip=3.5, hole=15)
    yw = g["CHAIN"]["Y"]["w"]
    yfix = box(cc - yw / 2, cc + yw / 2, g["Y_FIX"] - 30, g["Y_FIX"] + 30, z1 + 0.5, z1 + 4.5)
    yfix = drill(yfix, "+z", [(p[0], p[1], z1 + 4.5) for p in yfx], 3.3)
    out.append(item("gantry_drives.y_chain_fix", yfix, "steel", "made", "Y chain fixed-end bracket on the column's front face", G))
    screw("gantry_drives.y_chain_fix", "K01", ["gantry_drives.y_chain_fix", "gantry_frame.flange_front"], "SHCS", 6,
          [(p[0], p[1], z1 + 4.5) for p in yfx], (0, 0, -1), grip=4.5, L=12)
    return out


def tabp_of(c0, y, BLK_Z):
    return [(c0 + 9, y, BLK_Z + 20), (c0 + 25, y, BLK_Z + 20)]


def brake_part(x, z, y0, y1):
    """Brake body on the screw's end, a flange, two standoffs to the BF20's lower face (clear of its notches)."""
    pts = [(x - 22, y1 - 8, z + s * 34) for s in (-1, 1)]
    body = cyl("y", (x, 0, z), 30.0, y0, y1 - 8)
    flange = cyl("y", (x, 0, z), 47.0, y1 - 8, y1 - 5)
    stand = fuse([cyl("y", (p[0], 0, p[2]), 5.0, y1 - 5, y1 - 0.5) for p in pts])
    b = fuse([body, flange, stand])
    b = b - cyl("y", (x, 0, z), 8.0, y0 - 1, y1 + 1)
    return drill(b, "-y", [p for p in pts], 2.75), pts


def head_assembly(g, xs, ys, tip):
    SP_OFF, YR, BLK_H, PL, ZR = g["SP_OFF"], g["Y_RISER"], g["BLK_H"], g["PL"], g["Z_RISER"]
    ZC0, COL_D, YCH = g["ZC0"], g["COL_D"], g["YCH"]
    ZYP0, ZYP1 = g["ZYP0"], g["ZYP1"]
    c1 = xs - SP_OFF
    zn = tip + g["TIP_TO_NOSE"]
    Ypi = c1 + YR + BLK_H
    Ypf = Ypi + PL
    zx = Ypf
    Zpi = Ypf + ZR + BLK_H
    Zpo = Zpi + PL
    xs_, zs_ = c1 + g["YS_X"], g["YS_Z"]
    zsx = zx + g["ZS_X"]
    dy = g["Z_RAIL_DY"]
    zrs = (ZC0 + 40, ZC0 + COL_D - 40)
    out = []
    # ---- Y plate
    yp = box(Ypi, Ypf, ys - YCH, ys + YCH, ZYP0, ZYP1)
    yp = drill(yp, "+x", [(Ypf, ys + d + sy * 17.5, zr + sz * 17.5) for zr in zrs for d in (-88, 88) for sy in (-1, 1) for sz in (-1, 1)], 3.3, cbore=(5.5, 6.5))
    ybc = ys - (g["YN_L"] / 2 + 8 + g["YN_L"] / 2 - g["YN_FT"]) / 2 + (g["YN_L"] / 2 - g["YN_FT"]) / 2 * 0  # bracket's y centre (approx)
    ybc = ys + ((-g["YN_L"] / 2 - 8) + (g["YN_L"] / 2 - g["YN_FT"])) / 2
    yp = drill(yp, "+x", [(Ypf, yy_, zs_ + sz * 30) for yy_ in (ys - 24, ys + 15) for sz in (-1, 1)], 4.5, cbore=(7.0, 8.5))
    zh = [z for z in [ZYP0 + 30 + 120 * k for k in range(8)] if z < ZYP1 - 30 and not (190 < z < 310)]
    yp = drill(yp, "-x", [(Ypi, ys + s * dy, z) for s in (-1, 1) for z in zh], 4.5, cbore=(7.0, 8.5))
    yp = drill(yp, "+x", [(Ypf, ys + s * 27, z) for s in (-1, 1) for z in (ZYP1 - 13.5, ZYP0 + 10)], 2.5, depth=15)
    yp = drill(yp, "-x", [(Ypi, ys + s * 30, ZYP1 - 25) for s in (-1, 1)], 2.5, depth=15)
    ytop = ZC0 + COL_D + 5 + 2 * g["CHAIN_R"] + g["CHAIN"]["Y"]["h"] + 2 * g["CH_PAD"]
    ycb = [(Ypi, ys + dyb, ytop + 11) for dyb in (92, 108)]
    yp = drill(yp, "-x", ycb, 2.5, depth=15)
    anc = (Ypf, ys + 10, g["SHEAVE_Z"])
    yp = drill(yp, "+x", [anc], 4.5, cbore=(7.0, 8.5))
    zcf = [(zx - 10, ys + YCH, g["Z_CH_F"] + s * 15) for s in (-1, 1)]
    yp = drill(yp, "+y", zcf, 2.5, depth=15)
    out.append(item("y_carriage.y_plate", yp, "6061", "made", "6061-T6 25 mm plate; all holes from the drawing", "xy"))
    for zr in zrs:
        for d in (-88, 88):
            bn = f"y_carriage.y_block_{zr:.0f}_{'l' if d < 0 else 'r'}"
            out.append(item(bn, c_block().moved(frame((c1 + YR, ys + d, zr), (0, 1, 0), (1, 0, 0))), "steel", "bought", "HIWIN HGH25CA", "xy"))
            screw(bn, "C05", ["y_carriage.y_plate", bn], "SHCS", 6, [(Ypf - 6.5, ys + d + sy * 17.5, zr + sz * 17.5) for sy in (-1, 1) for sz in (-1, 1)],
                  (-1, 0, 0), grip=PL - 6.5, hole=8)
    # ---- Y nut and its bracket
    nloc = frame((xs_, ys, zs_), (0, 1, 0), (1, 0, 0))
    out.append(item("y_carriage.y_nut", c_nut(g["YN_D"], g["YN_FL"], g["YN_FT"], g["YN_L"], 25.0, 55.0).moved(nloc),
                    "steel", "bought", "flanged ball nut 25 x 20 lead", "xy"))
    ynh = [tp(nloc, (g["YN_L"] / 2, 27.5 * math.cos(math.radians(a_)), 27.5 * math.sin(math.radians(a_)))) for a_ in (30, 90, 150, 210, 270, 330)]
    ynh = [p for p in ynh if p[0] > xs_ - g["YN_D"] / 2 - 6 + 4 and p[0] < Ypi - 4]
    br = box(xs_ - g["YN_D"] / 2 - 6, Ypi, ys - g["YN_L"] / 2 - 8, ys + g["YN_L"] / 2 - g["YN_FT"], zs_ - 40, zs_ + 40)
    br = br - cyl("y", (xs_, 0, zs_), g["YN_D"] / 2 + 0.2, ys - g["YN_L"], ys + g["YN_L"])
    fy = ys + g["YN_L"] / 2 - g["YN_FT"]
    br = drill(br, "+y", [(p[0], fy, p[2]) for p in ynh], 2.5, depth=14)
    br = drill(br, "+x", [(Ypi, yy_, zs_ + sz * 30) for yy_ in (ys - 24, ys + 15) for sz in (-1, 1)], 3.4, depth=18)
    out.append(item("y_carriage.y_nut_bracket", br, "6061", "made", "nut housing, bolted to the Y plate (4 x M8)", "xy"))
    screw("y_carriage.y_nut_bracket", "C05", ["y_carriage.y_plate", "y_carriage.y_nut_bracket"], "SHCS", 8,
          [(Ypf - 8.5, yy_, zs_ + sz * 30) for yy_ in (ys - 24, ys + 15) for sz in (-1, 1)], (-1, 0, 0), grip=PL - 8.5, hole=18, into="6061")
    screw("y_carriage.y_nut", "Y03", ["y_carriage.y_nut", "y_carriage.y_nut_bracket"], "SHCS", 6, ynh, (0, -1, 0), grip=g["YN_FT"], hole=14, into="6061")
    anchor = box(c1 + g["ROPE_X"] - 6, Ypi - 0.5, ys, ys + 20, g["SHEAVE_Z"] - 10, g["SHEAVE_Z"] + 10) - cyl("y", (c1 + g["ROPE_X"], 0, g["SHEAVE_Z"]), 3.0, ys - 1, ys + 21)
    anchor = drill(anchor, "+x", [(Ypi - 0.5, anc[1], anc[2])], 3.4, depth=15)
    out.append(item("y_carriage.rope_anchor", anchor, "steel", "made", "rope anchor block, 5 mm rope with a swaged stop", "xy"))
    screw("y_carriage.rope_anchor", "C01", ["y_carriage.y_plate", "y_carriage.rope_anchor"], "SHCS", 8, [(Ypf - 8.5, anc[1], anc[2])], (-1, 0, 0),
          grip=PL - 8.5 + 0.5, hole=15)
    # ---- Z risers, rails, screw, supports
    for s in (-1, 1):
        r = box(Ypf, Ypf + ZR, ys + s * dy - 11.5, ys + s * dy + 11.5, ZYP0, ZYP1)
        r = drill(r, "+x", [(Ypf + ZR, ys + s * dy, ZYP0 + h) for h in rail_holes(ZYP1 - ZYP0)], 2.5, depth=14)
        r = drill(r, "-x", [(Ypf, ys + s * dy, z) for z in zh], 3.4, depth=16)
        lr = 'l' if s < 0 else 'r'
        out.append(item(f"y_carriage.z_riser_{lr}", r, "6061", "made", "6061 bar 32x23, faces machined; M6 rail and M8 base tapped", "xy"))
        out.append(item(f"y_carriage.z_rail_{lr}", c_rail(ZYP1 - ZYP0).moved(frame((Ypf + ZR, ys + s * dy, ZYP0), (0, 0, 1), (1, 0, 0))),
                        "steel", "bought", "HIWIN HGR25R, cut to length", "xy"))
        screw(f"y_carriage.z_riser_{lr}", "C01", ["y_carriage.y_plate", f"y_carriage.z_riser_{lr}"], "SHCS", 8, [(Ypi + 8.5, ys + s * dy, z) for z in zh],
              (1, 0, 0), grip=PL - 8.5, hole=16, into="6061")
        screw(f"y_carriage.z_rail_{lr}", "C01", [f"y_carriage.z_rail_{lr}", f"y_carriage.z_riser_{lr}"], "SHCS", 6,
              [(Ypf + ZR + 13, ys + s * dy, ZYP0 + h) for h in rail_holes(ZYP1 - ZYP0)], (-1, 0, 0), grip=13, hole=14, into="6061")
    out.append(item("y_carriage.z_screw", ballscrew("z", (zsx, ys, 0), 20.0, ZYP0, ZYP1 + 42, journal=(42 + 34, 21)), "steel", "bought",
                    "SFU2010 ball screw, ends machined for BK15/BF15", "xy"))
    for nm, (Ls, zo, cap, za, zb) in (("bk", (27, ZYP1 - 27, 6, ZYP1 - 33, ZYP1)), ("bf", (20, ZYP0, 0, ZYP0, ZYP0 + 20))):
        loc = frame((zsx, ys, zo), (0, 0, 1), (1, 0, 0))
        out.append(item(f"y_carriage.z_{nm}15", c_support(Ls, 70, 47, 28, 15, 54, cap=cap).moved(loc), "steel", "bought",
                        "BK15 fixed support" if cap else "BF15 floating support", "xy"))
        hp = [tp(loc, (Ls / 2, sy * 27, 47 - 28 - 0.45 * 47)) for sy in (-1, 1)]
        sp = drill(box(Ypf, Ypf + 6, ys - 35, ys + 35, za, zb), "+x", [(Ypf + 6, p[1], p[2]) for p in hp], 3.3)
        out.append(item(f"y_carriage.z_spacer_{nm}", sp, "6061", "made", "6 mm spacer", "xy"))
        screw(f"y_carriage.z_{nm}15", "C03", [f"y_carriage.z_{nm}15", f"y_carriage.z_spacer_{nm}", "y_carriage.y_plate"], "SHCS", 6, hp, (-1, 0, 0),
              grip=0.55 * 47 + 6, hole=15, into="6061")
    # ---- Z motor mount, pulleys, belt (the motor itself comes from its STEP file)
    mx = c1 + YR + BLK_H - 50
    mp = box(c1 - 15, Ypf, ys - 45, ys + 45, ZYP1 + 4, ZYP1 + 10)
    mp = drill(mp, "+z", [(mx, ys, ZYP1 + 10)], 37.0)
    zmh = [(mx + sx * 34.79, ys + sy * 34.79, ZYP1 + 10) for sx in (-1, 1) for sy in (-1, 1)]
    mp = drill(mp, "+z", zmh, 2.75)
    tab = box(Ypi - 8.5, Ypi - 0.5, ys - 45, ys + 45, ZYP1 - 40, ZYP1 + 4.5)
    tab = drill(tab, "-x", [(Ypi - 8.5, ys + s * 30, ZYP1 - 25) for s in (-1, 1)], 3.3, cbore=(5.5, 4))
    out.append(item("y_carriage.z_motor_mount", mp + tab, "6061", "made", "6 mm plate and 8 mm tab, NEMA34 pattern", "xy"))
    screw("y_carriage.z_motor_mount", "C04", ["y_carriage.z_motor_mount", "y_carriage.y_plate"], "SHCS", 6,
          [(Ypi - 4.5, ys + s * 30, ZYP1 - 25) for s in (-1, 1)], (1, 0, 0), grip=4.5, hole=15, into="6061")
    screw("y_carriage.z_motor", "C04", ["y_carriage.z_motor", "y_carriage.z_motor_mount"], "SHCS", 5,
          [(p[0], p[1], ZYP1 + 3.5 - T_MOTOR_FLANGE) for p in zmh], (0, 0, 1), grip=T_MOTOR_FLANGE + 6.5, nut=True, washer=True)
    for nm, (px, teeth, bore) in (("motor", (mx, 40, 14.0)), ("screw", (zsx, 20, 12.0))):
        loc = Location.translation(px, ys, ZYP1 + 12)
        out.append(item(f"y_carriage.z_pulley_{nm}", c_pulley(teeth, bore=bore).moved(loc), "6061", "bought", f"HTD 5M {teeth}T 15 wide, bore {bore:g}", "xy"))
        pulley_setscrew(f"y_carriage.z_pulley_{nm}_set", "C04", loc, teeth, bore)
    out.append(item("y_carriage.z_belt", c_belt([(mx, ys), (zsx, ys)], [40 * 5 / math.pi, 20 * 5 / math.pi]).moved(Location.translation(0, 0, ZYP1 + 14)),
                    "rubber", "bought", "HTD 5M 15 wide belt", "xy"))
    # ---- Y chain bracket
    ybr = box(c1 - g["COL_W"] / 2 - 20, Ypi - 0.5, ys + 80, ys + 120, ytop + 2, ytop + 17) - box(c1 - g["COL_W"] / 2 - 15, Ypi - 5.5, ys + 83, ys + 117, ytop + 5, ytop + 18)
    ybr = drill(ybr, "-x", [(Ypi - 5.5, p[1], p[2]) for p in ycb], 3.3)
    out.append(item("y_carriage.y_chain_bracket", ybr, "steel", "made", "folded 3 mm channel, 5 mm end wall, 2 x M6 into the Y plate", "xy"))
    screw("y_carriage.y_chain_bracket", "C01", ["y_carriage.y_chain_bracket", "y_carriage.y_plate"], "SHCS", 6, [(Ypi - 5.5, p[1], p[2]) for p in ycb],
          (1, 0, 0), grip=5.5, hole=15, into="6061")
    # Z chain: fixed-end tab on the Y plate's lower edge, moving-end bracket on the Z plate's lower edge
    zfix = box(zx - 20, zx + 40, ys + YCH + 0.5, ys + YCH + 5, g["Z_CH_F"] - 25, g["Z_CH_F"] + 25)
    zfix = drill(zfix, "+y", [(zx - 10, ys + YCH + 5, g["Z_CH_F"] + s * 15) for s in (-1, 1)], 3.3)
    out.append(item("y_carriage.z_chain_fix", zfix, "steel", "made", "Z chain fixed-end tab, 2 x M6 into the Y plate's upper edge", "xy"))
    screw("y_carriage.z_chain_fix", "C01", ["y_carriage.z_chain_fix", "y_carriage.y_plate"], "SHCS", 6, [(p[0], ys + YCH + 5, p[2]) for p in zcf], (0, -1, 0),
          grip=4.5, hole=15, into="6061")
    # ---- Z axis: blocks, plate, nut and bracket, clamps
    for s in (-1, 1):
        for z0 in (g["ZP0"], g["ZP1"] - 84):
            bn = f"z_axis.z_block_{'l' if s < 0 else 'r'}_{z0:.0f}"
            out.append(item(bn, c_block().moved(frame((Ypf + ZR, ys + s * dy, zn + z0 + 42), (0, 0, 1), (1, 0, 0))), "steel", "bought", "HIWIN HGH25CA", "xyz"))
            screw(bn, "Z01", ["z_axis.z_plate", bn], "SHCS", 6, [(Zpo - 6.5, ys + s * dy + sy * 17.5, zn + z0 + 42 + sz * 17.5) for sy in (-1, 1) for sz in (-1, 1)],
                  (-1, 0, 0), grip=PL - 6.5, hole=8)
    zc = zn + (g["ZP0"] + g["ZP1"]) / 2
    zp = box(Zpi, Zpo, ys - 110, ys + 110, zn + g["ZP0"], zn + g["ZP1"])
    zp = drill(zp, "+x", [(Zpo, ys + s * dy + sy * 17.5, zn + zb + sz * 17.5) for s in (-1, 1) for zb in (g["ZP0"] + 42, g["ZP1"] - 42)
                          for sy in (-1, 1) for sz in (-1, 1)], 3.3, cbore=(5.5, 6.5))
    zp = drill(zp, "+x", [(Zpo, ys + sy * 22, zc + sz * 25) for sy in (-1, 1) for sz in (-1, 1)], 4.5, cbore=(7.0, 8.5))
    zp = drill(zp, "+x", [(Zpo, ys + sy * 76.5, zn + a + dz) for a in g["CLAMP_Z"] for sy in (-1, 1) for dz in (15, 45)], 4.2, depth=20)
    zm_ = zn + ZYP1 - 450 - g["ZN_MIN"]
    zcb = [(Zpi + 12.5, ys + 110, zm_ + s * 5.5) for s in (-1, 1)]
    zp = drill(zp, "+y", zcb, 2.1, depth=15)
    out.append(item("z_axis.z_plate", zp, "6061", "made", "6061-T6 25 mm plate", "xyz"))
    zx1 = zx + 2 * g["CHAIN_R"] + g["CHAIN"]["Z"]["h"] + 2 * g["CH_PAD"]
    zmov = box(Zpi, zx1, ys + 110.5, ys + YCH + 5, zm_ - 15, zm_ + 15) - box(Zpi + 4, zx1 + 1, ys + 114.5, ys + YCH + 6, zm_ - 11, zm_ + 11)
    zmov = drill(zmov, "+y", [(p[0], ys + 114.5, p[2]) for p in zcb], 2.75)
    out.append(item("z_axis.z_chain_bracket", zmov, "steel", "made", "folded 4 mm angle from the Z plate's upper edge to the Z chain's moving end", "xyz"))
    screw("z_axis.z_chain_bracket", "Z01", ["z_axis.z_chain_bracket", "z_axis.z_plate"], "SHCS", 5, [(p[0], ys + 114.5, p[2]) for p in zcb], (0, -1, 0),
          grip=4.5, hole=15, into="6061")
    zloc = frame((zsx, ys, zc), (0, 0, 1), (1, 0, 0))
    out.append(item("z_axis.z_nut", c_nut(g["ZN_D"], g["ZN_FL"], g["ZN_FT"], g["ZN_L"], 20.0, 47.0).moved(zloc), "steel", "bought", "SFU2010 flanged ball nut", "xyz"))
    znh = [tp(zloc, (g["ZN_L"] / 2, 23.5 * math.cos(math.radians(a_)), 23.5 * math.sin(math.radians(a_)))) for a_ in (30, 90, 150, 210, 270, 330)]
    znh = [p for p in znh if zsx - g["ZN_D"] / 2 - 6 + 4 < p[0] < Zpi - 4 and abs(p[1] - ys) < 32]
    zb_ = box(zsx - g["ZN_D"] / 2 - 6, Zpi, ys - 36, ys + 36, zc - g["ZN_L"] / 2 - 8, zc + g["ZN_L"] / 2 - g["ZN_FT"])
    zb_ = zb_ - cyl("z", (zsx, ys, 0), g["ZN_D"] / 2 + 0.2, zc - g["ZN_L"], zc + g["ZN_L"])
    zb_ = drill(zb_, "+x", [(Zpi, ys + sy * 22, zc + sz * 25) for sy in (-1, 1) for sz in (-1, 1)], 3.4, depth=18)
    zb_ = drill(zb_, "+z", [(p[0], p[1], zc + g["ZN_L"] / 2 - g["ZN_FT"]) for p in znh], 2.5, depth=14)
    out.append(item("z_axis.z_nut_bracket", zb_, "6061", "made", "nut housing, bolted to the Z plate (4 x M8)", "xyz"))
    screw("z_axis.z_nut_bracket", "Z01", ["z_axis.z_plate", "z_axis.z_nut_bracket"], "SHCS", 8,
          [(Zpo - 8.5, ys + sy * 22, zc + sz * 25) for sy in (-1, 1) for sz in (-1, 1)], (-1, 0, 0), grip=PL - 8.5, hole=18, into="6061")
    screw("z_axis.z_nut", "C03", ["z_axis.z_nut", "z_axis.z_nut_bracket"], "SHCS", 6, znh, (0, 0, -1), grip=g["ZN_FT"], hole=14, into="6061")
    W = g["SP_W"]
    for k, a in enumerate(g["CLAMP_Z"]):
        za, zb2 = zn + a, zn + a + 60
        hole = box(xs - W / 2 - 0.2, xs + W / 2 + 0.2, ys - W / 2 - 0.2, ys + W / 2 + 0.2, za - 1, zb2 + 1)
        base = box(Zpo, xs - 0.5, ys - W / 2 - 20, ys + W / 2 + 20, za, zb2) - hole
        base = drill(base, "+x", [(xs - 0.5, ys + sy * 76.5, za + dz) for sy in (-1, 1) for dz in (15, 45)], 5.5, cbore=(8.5, 25))
        base = drill(base, "+x", [(xs - 0.5, ys + sy * 76.5, za + 30) for sy in (-1, 1)], 4.2, depth=20)
        cap = box(xs + 0.5, xs + W / 2 + 12, ys - W / 2 - 20, ys + W / 2 + 20, za, zb2) - hole
        cap = drill(cap, "+x", [(xs + W / 2 + 12, ys + sy * 76.5, za + 30) for sy in (-1, 1)], 5.5, cbore=(8.5, 6))
        out.append(item(f"z_axis.clamp_{k}_base", base, "6061", "made", "60 mm block, square bore 133.4 split on the centre line", "xyz"))
        out.append(item(f"z_axis.clamp_{k}_cap", cap, "6061", "made", "clamp cap, 2 x M10", "xyz"))
        screw(f"z_axis.clamp_{k}_base", "Z02", [f"z_axis.clamp_{k}_base", "z_axis.z_plate"], "SHCS", 10,
              [(xs - 25.5, ys + sy * 76.5, za + dz) for sy in (-1, 1) for dz in (15, 45)], (-1, 0, 0), grip=xs - 25.5 - Zpo, hole=20, into="6061")
        screw(f"z_axis.clamp_{k}_cap", "Z03", [f"z_axis.clamp_{k}_cap", f"z_axis.clamp_{k}_base"], "SHCS", 10,
              [(xs + W / 2 + 6, ys + sy * 76.5, za + 30) for sy in (-1, 1)], (-1, 0, 0), grip=W / 2 + 6 + 0.5, hole=20, into="6061")
    # ---- spindle, holder, cutter
    out.append(item("spindle.body", c_spindle(g["SP_L"], W, g["SP_REAR"]).moved(Location.translation(xs, ys, zn)), "steel", "bought",
                    "salvaged 9 kW ISO30 ATC spindle, 380 V (shape estimated beyond 510 x 133 x 133)", "xyz"))
    h, t = c_holder(g["TOOL_D"], g["TOOL_STICK"])
    out.append(item("spindle.holder", h.moved(Location.translation(xs, ys, zn)), "steel", "bought", "ISO30 ER32 holder", "xyz"))
    out.append(item("tool", t.moved(Location.translation(xs, ys, zn)), "carbide", "bought", "12 mm cutter", "xyz"))
    return out


def chain_state(spec, m):
    """Where a chain's bend sits for a moving-end position m: (run A, bend position b), all along the run axis."""
    b = spec["f"] + 30.0 + (spec.get("sg", 1) * m - spec["m_min"]) / 2
    return b - spec["f"], b


def chain_point(spec, m, s):
    """Centre-line point and tangent at arc length s from the fixed end, for moving end m."""
    F, d, n, R = spec["F"], spec["d"], spec["n"], spec["R"]
    a, b = chain_state(spec, m)
    if s <= a:
        p, t = [F[i] + d[i] * s for i in range(3)], d
    elif s <= a + math.pi * R:
        ph = (s - a) / R
        c = [F[i] + d[i] * a + n[i] * R for i in range(3)]
        p = [c[i] - n[i] * R * math.cos(ph) + d[i] * R * math.sin(ph) for i in range(3)]
        t = [d[i] * math.cos(ph) + n[i] * math.sin(ph) for i in range(3)]
    else:
        u = s - a - math.pi * R
        p, t = [F[i] + d[i] * a + n[i] * 2 * R - d[i] * u for i in range(3)], [-v for v in d]
    return p, t


def c_link(pitch, h, W, t=3.0):
    """One chain link: two side plates and two cross bars; x along the chain, y across from 0 to W, z across its height."""
    L = 0.8 * pitch          # longest that stays clear of its neighbours round the R100 bend
    return fuse([box(-L / 2, L / 2, 0, t, -h / 2, h / 2), box(-L / 2, L / 2, W - t, W, -h / 2, h / 2),
                 box(-0.2 * pitch, 0.2 * pitch, t - 0.5, W - t + 0.5, h / 2 - t, h / 2 - 0.3), box(-0.2 * pitch, 0.2 * pitch, t - 0.5, W - t + 0.5, -h / 2 + 0.3, -h / 2 + t)])


def chain_links(spec, m, shift=(0.0, 0.0, 0.0)):
    """The chain's links for moving end m, as one part (links do not touch)."""
    link = c_link(spec["pitch"], spec["h"], spec["W"])
    w = spec["w"]
    parts = []
    for i in range(spec["N"]):
        s = i * spec["L"] / (spec["N"] - 1)
        p, t = chain_point(spec, m, s)
        z = _cross(t, w)
        parts.append(link.moved(frame(tuple(p[k] + shift[k] for k in range(3)), tuple(t), tuple(z))))
    return fuse(parts)


def chains(g, ref):
    """The three cable chains, link by link, at the reference pose `ref` = (xs, ys, tip)."""
    out = []
    for name, spec in g["CHAIN_SPECS"].items():
        m = {"x": ref[0], "y": ref[1], "tip": ref[2]}[spec["var"]] + spec["m_off"]
        out.append(item(name, chain_links(spec, m), "nylon", "bought", spec["part"], spec["group"]))
    return out


def counterweight_assembly(g, xs, ys):
    """Stacked steel slabs on two M12 tie rods, UHMW shoes on the end slabs, the travelling sheave on top."""
    c1 = xs - g["SP_OFF"]
    c0 = c1 - g["COL_W"]
    t, gap = g["COL_T"], g["CW_GAP"]
    xa, xb = c0 + t + gap, c1 - t - gap
    za, zb = g["ZC0"] + t + gap, g["ZC0"] + g["COL_D"] - t - gap
    top = g["CW_TOP_HI"] - (ys - g["Y_WORK"][0]) / g["REEVE"]
    bot = top - g["CW_LEN"]
    steel_top = top - g["CW_SHEAVE"]
    out = []
    n = 8
    h = (steel_top - bot) / n
    rods = [(xa + 22, zm) for zm in (za + 40, zb - 40)]
    for i in range(n):
        slab = box(xa + 4, xb - 4, bot + i * h + 0.5, bot + (i + 1) * h - 0.5, za + 4, zb - 4)
        slab = drill(slab, "+y", [(x, bot + (i + 1) * h - 0.5, z) for x, z in rods], 6.6)
        if i in (0, n - 1):
            ya, yb = bot + i * h + 5, bot + (i + 1) * h - 5
            ym = (ya + yb) / 2
            slab = drill(slab, "-x", [(xa + 4, ym, z) for z in (za + 60, zb - 60)], 2.1, depth=14)
            slab = drill(slab, "+x", [(xb - 4, ym, z) for z in (za + 60, zb - 60)], 2.1, depth=14)
            slab = drill(slab, "-z", [(x, ym, za + 4) for x in (xa + 40, xb - 40)], 2.1, depth=14)
            slab = drill(slab, "+z", [(x, ym, zb - 4) for x in (xa + 40, xb - 40)], 2.1, depth=14)
        out.append(item(f"counterweight.slab_{i}", slab, "steel", "made", f"steel plate {h - 1:.0f} thick, flame cut, 2 holes for the M12 tie rods", "cw"))
    step_of = {0: "W0B", n - 1: "W0A"}
    for s, i in (("bottom", 0), ("top", n - 1)):
        ya, yb = bot + i * h + 5, bot + (i + 1) * h - 5
        ym = (ya + yb) / 2
        for k, (x0, x1, z0, z1, face, pts, d) in enumerate((
                (xa, xa + 3.5, za + 20, zb - 20, "-x", [(xa, ym, z) for z in (za + 60, zb - 60)], (1, 0, 0)),
                (xb - 3.5, xb, za + 20, zb - 20, "+x", [(xb, ym, z) for z in (za + 60, zb - 60)], (-1, 0, 0)),
                (xa + 20, xb - 20, za, za + 3.5, "-z", [(x, ym, za) for x in (xa + 40, xb - 40)], (0, 0, 1)),
                (xa + 20, xb - 20, zb - 3.5, zb, "+z", [(x, ym, zb) for x in (xa + 40, xb - 40)], (0, 0, -1)))):
            shoe = drill(box(x0, x1, ya, yb, z0, z1), face, pts, 2.75)
            out.append(item(f"counterweight.shoe_{s}_{k}", shoe, "UHMW", "made", "UHMW guide shoe 3.5 mm, 2 x M5 countersunk into the slab", "cw"))
            screw(f"counterweight.shoe_{s}_{k}", step_of[i], [f"counterweight.shoe_{s}_{k}", f"counterweight.slab_{i}"], "CSK", 5, pts, d,
                  grip=4.0, hole=14)
    # tie rods through the stack, nuts at both ends
    screw("counterweight.tie_rods", "W08", [f"counterweight.slab_{n - 1 - i}" for i in range(n)], "ROD", 12,
          [(x, steel_top - 0.5, z) for x, z in rods], (0, -1, 0), grip=steel_top - bot - 1.0, nut=True, washer=True,
          L=math.ceil(steel_top - bot - 1.0 + 2 * (10.8 + 2.1) + 6))
    xsh = c1 + g["ROPE_X"] - g["SHEAVE_D"]
    yc, zc = steel_top + 62, g["SHEAVE_Z"] + g["SHEAVE_D"] / 2
    fork = box(xsh - 20, xsh + 20, steel_top, top, za + 30, zb - 30) - box(xsh - 13, xsh + 13, steel_top + 5, top + 1, za + 29, zb - 29)
    fork = drill(fork, "-x", [(xsh - 20, yc, zc)], 6.6)
    out.append(item("counterweight.sheave_fork", fork, "steel", "made", "welded fork on the top slab, M12 axle hole", "cw"))
    weld("counterweight.sheave_fork", "W0A", "counterweight.sheave_fork", f"counterweight.slab_{n - 1}", "fillet both sides")
    sh = cyl("x", (0, yc, zc), g["SHEAVE_D"] / 2 + 5, xsh - 12, xsh + 12) - cyl("x", (0, yc, zc), 6.1, xsh - 13, xsh + 13)
    out.append(item("counterweight.sheave", sh, "6061", "bought", "rope sheave 100 PCD, sealed bearings, bore 12", "cw"))
    screw("counterweight.sheave_axle", "W0A", ["counterweight.sheave_fork", "counterweight.sheave"], "HEX", 12, [(xsh - 20, yc, zc)], (1, 0, 0),
          grip=40.0, nut=True, washer=True)
    return out


def rope_path(g, xs, ys):
    """The counterweight rope, carriage anchor to dead end, as points tagged with the group each one moves with."""
    c1 = xs - g["SP_OFF"]
    R = g["SHEAVE_D"] / 2
    sx, sy, sz = c1 + g["ROPE_X"] - R, g["SHEAVE_Y"], g["SHEAVE_Z"]
    top = g["CW_TOP_HI"] - (ys - g["Y_WORK"][0]) / g["REEVE"]
    yc, zc = top - g["CW_SHEAVE"] + 62, sz + R
    pts = [((c1 + g["ROPE_X"], ys + 20, sz), "xy")]
    pts += [((sx + R * math.cos(math.radians(a)), sy + R * math.sin(math.radians(a)), sz), "x") for a in range(0, 181, 15)]
    pts += [((sx - R, yc - R * math.sin(math.radians(a)), zc - R * math.cos(math.radians(a))), "cw") for a in range(0, 181, 15)]
    pts += [((sx - R, g["Y_RT"] + 40 - 25, zc + R), "x")]
    return pts


def rope_part(pts, r=2.5):
    segs = []
    for (a, _), (b, _) in zip(pts, pts[1:]):
        L = math.dist(a, b)
        if L < 0.5:
            continue
        d = tuple((b[i] - a[i]) / L for i in range(3))
        segs.append(FA._along(a, d, r, 0.05, L - 0.05))
    return fuse(segs)


def levelling_foot(cx, cy, top, h, pad_d=78.0):
    """M16 levelling foot: pad, lock nut, stud up through the weld nut into the rail ("top" is the rail's underside)."""
    return fuse([cyl("z", (cx, cy, 0), pad_d / 2, 0.01, 8), cyl("z", (cx, cy, 0), 13.5, 8, 16), cyl("z", (cx, cy, 0), 8.0, 16, top + 20)])


def foot_nut(cx, cy, top):
    return cyl("z", (cx, cy, 0), 13.5, top - 13, top) - cyl("z", (cx, cy, 0), 7.0, top - 14, top + 1)


def ballscrew(axis, c, d, a0, a1, journal=(0.0, 0.0)):
    """Screw shaft from a0 to a1 along `axis`; journal = (length at a1, length at a0) turned down to the bearings."""
    jd = 20.0 if d >= 25 else 15.0
    parts = [cyl(axis, c, d / 2, a0 + journal[1], a1 - journal[0])]
    if journal[1]:
        parts.append(cyl(axis, c, jd / 2 * 0.75, a0, a0 + journal[1] + 0.5))
    if journal[0]:
        parts.append(cyl(axis, c, jd / 2 * 0.75, a1 - journal[0] - 0.5, a1))
    return fuse(parts)


def c_block_env():
    """Clash envelope of an HGH25CA block (with its grease nipple), canonical frame as c_block."""
    return box(-51, 42, -24, 24, 5.5, 40) - box(-52, 43, -12, 12, -1, 23)
