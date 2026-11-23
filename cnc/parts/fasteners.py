"""Fasteners: catalogue sizes (ISO 4762 socket head cap screws, ISO 10642 countersunk, ISO 4017 hex bolts, ISO 4032 nuts,
ISO 7089 washers, ISO 4026 set screws, self-drilling and chipboard screws), length choice, solids for the checks.

A fastener sits at `p` (the point where its head bears, or for a set screw its outer end) and points along `d`
(from the head towards the thread's end).
"""
import math

from golf_py import Axis, Location, Part

# d: (head dia, head height, hex key, tap drill radius, clearance radius, torque N*m for 8.8 into steel, spanner, nut height)
ISO = {3: (5.5, 3.0, 2.5, 1.25, 1.7, 1.2, 5.5, 2.4), 4: (7.0, 4.0, 3.0, 1.65, 2.25, 2.9, 7.0, 3.2),
       5: (8.5, 5.0, 4.0, 2.1, 2.75, 6.0, 8.0, 4.7), 6: (10.0, 6.0, 5.0, 2.5, 3.3, 10.0, 10.0, 5.2),
       8: (13.0, 8.0, 6.0, 3.4, 4.5, 25.0, 13.0, 6.8), 10: (16.0, 10.0, 8.0, 4.2, 5.5, 49.0, 16.0, 8.4),
       12: (18.0, 12.0, 10.0, 5.1, 6.6, 85.0, 18.0, 10.8), 16: (24.0, 16.0, 14.0, 7.0, 8.75, 210.0, 24.0, 14.8)}
LENGTHS = [4, 5, 6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200]
# thread engagement needed, in diameters, by the tapped part's material
ENGAGE = {"steel": 1.0, "6061": 1.5, "cast iron": 1.25, "MDF": 2.5, "nut": 0.8}

# DIN 7984 low-head cap screws: d: (head dia, head height, hex key)
LOW = {5: (8.5, 3.5, 3.0), 6: (10.0, 4.0, 4.0), 8: (13.0, 5.0, 5.0), 10: (16.0, 6.0, 7.0)}
# DIN 911 hex keys: short arm length, the reach straight down a screw's axis
KEY_SHORT = {2.5: 18.0, 3.0: 20.0, 4.0: 25.0, 5.0: 28.0, 6.0: 32.0, 7.0: 34.0, 8.0: 36.0, 10.0: 40.0, 14.0: 56.0}

TYPES = {"SHCS": "ISO 4762 socket head cap screw", "LHCS": "DIN 7984 low-head cap screw", "CSK": "ISO 10642 countersunk screw", "HEX": "ISO 4017 hex bolt",
         "SET": "ISO 4026 set screw, cup point", "TEK": "self-drilling wafer-head screw 10-16", "WOOD": "chipboard screw, countersunk",
         "ROD": "threaded rod, 2 nuts and washers", "STUD": "levelling foot stud"}


def spec(kind, d, L, nut=False, washer=False, std=None):
    return dict(type=kind, d=d, L=L, nut=nut, washer=washer, std=std or TYPES[kind])


def label(f):
    t = f["type"]
    if t in ("TEK", "WOOD"):
        return f"{f['d']:g} x {f['L']:g} {TYPES[t]}"
    return f"M{f['d']:g} x {f['L']:g} {TYPES[t]}" + (", nut" if f["nut"] else "") + (" and washer" if f["washer"] else "")


def tool(f):
    d = f["d"]
    if f["type"] in ("TEK", "WOOD"):
        return "cordless driver, PH2 / 8 mm hex bit"
    if f["type"] == "HEX" or f["type"] == "ROD":
        return f"{ISO[d][6]:g} mm spanner" + (" x 2" if f["nut"] else "")
    key = LOW[d][2] if f["type"] == "LHCS" else ISO[d][2]
    return f"{key:g} mm hex key" + (f" and {ISO[d][6]:g} mm spanner" if f["nut"] else "")


def torque(f, into="steel"):
    if f["type"] in ("TEK", "WOOD"):
        return None
    t = ISO[f["d"]][5]
    if f["type"] == "SET":
        return round(t * 0.4, 1)
    return round(t * (0.6 if into == "6061" and not f["nut"] else 1.0), 1)


def head_size(f):
    """(diameter, height) of what stands proud of the bearing face: for countersunk heads the cone sits inside the part."""
    d = f["d"]
    if f["type"] == "SHCS":
        return ISO[d][0], ISO[d][1]
    if f["type"] == "LHCS":
        return LOW[d][0], LOW[d][1]
    if f["type"] == "HEX":
        return ISO[d][6] * 1.15, 0.7 * d
    if f["type"] == "ROD":
        return ISO[d][6] * 1.1, ISO[d][7] + 2.0          # the top nut and its washer
    return 0.0, 0.0


def choose_length(grip, need, depth=None, kind="SHCS", nut_h=0.0, csk=0.0):
    """Shortest standard length with `need` mm of thread past the grip, and (blind hole) its tip at least 1 mm short of the
    hole's bottom; with a nut, long enough to stand 1.5 mm proud of it. None when no length fits."""
    for L in LENGTHS:
        eng = L - grip - (csk if kind == "CSK" else 0.0)
        if nut_h:
            if eng >= nut_h + 1.5:
                return L
            continue
        if eng >= need and (depth is None or eng <= depth - 1.0):
            return L
    return None


# ------------------------------------------------------------------ solids, for the checks and the viewer
def _along(p, d, r, a0, a1):
    """Cylinder of radius r on the line p + t d, t from a0 to a1."""
    c = Part.cylinder(r, a1 - a0).moved(Location.translation(0, 0, (a0 + a1) / 2))
    return c.moved(_frame(p, d))


def _frame(p, d):
    """Location taking +z to d at p."""
    x, y, z = d
    ang = math.degrees(math.acos(max(-1.0, min(1.0, z))))
    T = Location.translation(*p)
    if ang < 1e-6:
        return T
    if abs(ang - 180) < 1e-6:
        return T * Location.about(Axis.X, 180)
    ax = (-y, x, 0.0)
    n = math.hypot(*ax)
    return T * Location.about(Axis((0, 0, 0), (ax[0] / n, ax[1] / n, 0.0)), ang)


def shank(p, d, f, r=None, a0=0.0, a1=None):
    return _along(p, d, r if r is not None else f["d"] / 2 - 0.05, a0, f["L"] if a1 is None else a1)


def head(p, d, f, lift=0.05):
    """What stands proud of the bearing face (nothing for countersunk and set screws)."""
    D, k = head_size(f)
    if not k:
        return None
    return _along(p, d, D / 2, -k - lift, -lift)


def seat(p, d, f):
    """A thin ring just under the head: it must cut into the first clamped part (the head bears on material)."""
    D, k = head_size(f)
    if f["type"] in ("CSK", "WOOD"):
        D = 2.0 * f["d"]
    if f["type"] == "SET" or D <= f["d"] + 1.6:
        return None
    return _along(p, d, D / 2 - 0.3, 0.05, 0.4) - _along(p, d, f["d"] / 2 + 0.5, -1, 1)


def nut(p, d, f, grip):
    if not f["nut"]:
        return None
    h = ISO[f["d"]][7]
    w = 0.5 + (1.6 if f["washer"] else 0.0)
    return _along(p, d, ISO[f["d"]][6] * 0.55, grip + w, grip + w + h)
