"""R6, R56, R7, R8: size and footprint at the extreme poses."""
from cnc.params import DEPTH_MAX, H_MAX, TIP_MIN, TIP_TO_NOSE, X_TRAVEL, X_WORK, Y_WORK, ZN_MAX
from cnc.geometry.shapes import Bounds, fuse
from cnc.geometry.bed import atc, rack_b, rack_t, rail_b, rail_t, spoil, substrate, xchain
from cnc.geometry.moving import gantry, head
from cnc.geometry.world import H0, W, base, bed_w, feet, world, wpt
from cnc.system.requirements import require

poses = [(xs, ys, tip) for xs in (X_TRAVEL[0], X_WORK[1]) for ys in Y_WORK for tip in (TIP_MIN, ZN_MAX - TIP_TO_NOSE)]
fixed_parts_w = [bed_w, world(substrate), world(spoil), world(rail_b), world(rail_t), world(rack_b), world(rack_t), world(atc), world(xchain), base, feet]
zmax, ymin, ymax = -1e9, 1e9, -1e9
for xs, ys, tip in poses:
    a = fuse(list(gantry(xs, with_arm=False)) + list(head(xs, ys, tip, zchain=False))).moved(W)   # (the chains are measured below)
    b = a.bounding_box()
    zmax = max(zmax, b.max()[2]); ymin = min(ymin, b.min()[1]); ymax = max(ymax, b.max()[1])
fb = Bounds(fixed_parts_w)
fb_h = Bounds([p for p in fixed_parts_w if p is not fixed_parts_w[8]])          # without the X chain
zmax = max(zmax, fb_h.max()[2]); ymin_all = min(ymin, fb.min()[1]); ymax_all = max(ymax, fb.max()[1])
require("R6", "The machine shall be no taller than 1800 mm in any pose (the X and Z cable chains and their brackets excepted)", zmax, "<=", H_MAX, "mm")
CEILING = 2400.0
z_chain_top = max(fb.max()[2], max(gantry(xs)[0].moved(W).bounding_box().max()[2] for xs in X_TRAVEL))
z_zchain_top = max(head(xs, Y_WORK[1], tip)[0].moved(W).bounding_box().max()[2] for xs in X_TRAVEL for tip in (TIP_MIN, ZN_MAX - TIP_TO_NOSE))
require("R56", "The X and Z cable chains and their brackets shall clear a 2400 mm ceiling by 100 mm", max(z_chain_top, z_zchain_top), "<=", CEILING - 100, "mm")
floor_b = fuse([base, feet]).bounding_box()
require("R7", "The floor frame shall be no deeper than 1000 mm front to back",
        floor_b.max()[1] - floor_b.min()[1], "<=", DEPTH_MAX, "mm")
fixed_depth = fb.max()[1] - fb.min()[1]          # bed, rails, racks, ATC, floor frame and feet
require("R8", "With the gantry parked in the corner, the bed and floor frame shall be no deeper than 1000 mm "
        "(the head's overhang while cutting is accepted)", fixed_depth, "<=", DEPTH_MAX, "mm")
print("height", zmax, "floor depth", floor_b.max()[1] - floor_b.min()[1], "envelope", ymin_all, ymax_all, ymax_all - ymin_all,
      "sheet bottom edge height", wpt(0, 0, 0)[2], "H0", H0, "length", fb.max()[0] - fb.min()[0])
