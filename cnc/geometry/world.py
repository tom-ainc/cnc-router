"""The bed tilted into the world, and the floor frame under it (world frame)."""
import math
from golf_py import Axis, Location, Part
from cnc.params import BASE_H, FOOT_H, SPOIL_T, TILT, X_BED, Y_RB, Y_RT
from cnc.geometry.shapes import box, fuse
from cnc.geometry.bed import BED_BACK, bed

LIFT_PROBE = Location.about(Axis.X, 90 - TILT)
_low = bed.fork().moved(LIFT_PROBE).bounding_box().min()[2]
H0 = FOOT_H + BASE_H - _low            # lift so the bed's lowest edge sits on the floor frame (R11 checks the gantry clears it)
W = Location.translation(0, 0, H0) * LIFT_PROBE


def world(p):
    """A copy of p placed in the world (golf's named edits change their part, so move a fork)."""
    return p.fork().moved(W)


def wpt(x, y, z):
    """A local point in the world, as a tuple (through a tiny cube)."""
    return world(box(x - .5, x + .5, y - .5, y + .5, z - .5, z + .5)).centre()


# ------------------------------------------------------------------ floor frame (world)
bed_w = world(bed)
bb = bed_w.bounding_box()
back_hi = wpt(0, Y_RT, BED_BACK)                    # bed back at the top rail
back_lo = wpt(0, Y_RB - 80, BED_BACK)               # bed back, bottom edge
front_lo = wpt(0, Y_RB - 80, -SPOIL_T)              # bed face, bottom edge
Y_FRONT = -420.0                                    # front outrigger tip (world y)
Y_REAR = back_hi[1] + 40.0                          # rear floor rail under the bed top
ZB0, ZB1 = FOOT_H, FOOT_H + BASE_H
N_LEGS = 5                                           # rear posts: spans short enough for the top rail beam (R44)
xs_legs = [X_BED[0] + 40 + i * (X_BED[1] - X_BED[0] - 80) / (N_LEGS - 1) for i in range(N_LEGS)]
base_parts = [
    box(X_BED[0], X_BED[1], front_lo[1] + 10, front_lo[1] + 110, ZB0, ZB1),     # front rail, under the bed only
    box(X_BED[0], X_BED[1], Y_REAR - 80, Y_REAR, ZB0, ZB1),                    # rear rail
]
OUTRIG_H = 50.0                                     # outriggers in front of the bed are low, so the X drives pass over them
base_parts += [box(x - 40, x + 40, front_lo[1] + 10, Y_REAR, ZB0, ZB1) for x in xs_legs]                  # cross members
base_parts += [box(x - 39, x + 39, Y_FRONT, front_lo[1] + 30, ZB0 + 0.5, ZB0 + OUTRIG_H) for x in xs_legs]  # outriggers
feet = [box(x - 40, x + 40, y - 40, y + 40, 0, FOOT_H + (0.5 if y < 0 else 0.0)) for x in xs_legs for y in (Y_FRONT + 40, Y_REAR - 40)]
# bed saddles from the front rail up to the bed's lowest edge
saddles = [box(x - 40, x + 40, front_lo[1] - 60, back_lo[1], ZB1, bb.min()[2]) for x in xs_legs] if bb.min()[2] - ZB1 > 5 else []
# rear posts from the rear rail up to the bed back at the top rail
struts = []
for x in xs_legs:
    a = (x, Y_REAR - 40, ZB1 - 20)
    b = (x, back_hi[1], back_hi[2])
    L = math.dist(a, b)
    ang = math.degrees(math.atan2(b[2] - a[2], b[1] - a[1]))
    s = Part.cuboid(58, L + 120, 58).moved(Location.about(Axis.X, ang))
    s = s.moved(Location.translation(x, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2))
    s = s - box(x - 100, x + 100, Y_REAR - 400, Y_REAR + 400, ZB1 - 400, ZB1 - 0.3)              # ends cut to fit (as the detail)
    struts.append(s - world(box(X_BED[0] - 10, X_BED[1] + 10, Y_RT - 400, Y_RT + 400, BED_BACK + 0.3, BED_BACK + 500)))
base = fuse(base_parts + saddles + struts)
feet = fuse(feet)
