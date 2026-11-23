"""R9-R14: fits and clearances of the envelopes over the travels."""
from golf_py import Location
from se import require_no_overlap
from cnc.params import TIP_MIN, TIP_TO_NOSE, X_TRAVEL, X_WORK, Y_WORK, ZN_MAX
from cnc.geometry.shapes import box, fuse
from cnc.geometry.bed import atc, bed, clamps, rack_b, rack_t, rail_b, rail_t, spoil, stock, substrate, xchain
from cnc.geometry.moving import counterweight, gantry, head
from cnc.geometry.world import W, base, bed_w, feet, world, wpt
from cnc.geometry.pose import POSE, g_frame, g_other, h_car, h_sp, h_z
from cnc.system.requirements import clear_travel, require

require_no_overlap("R9", {"bed": bed, "substrate": substrate, "spoilboard": spoil, "rail_b": rail_b, "rail_t": rail_t,
                          "rack_b": rack_b, "rack_t": rack_t, "atc": atc, "stock": stock,
                          "gantry_frame": g_frame, "gantry_drives": g_other,
                          "y_carriage": h_car, "z_axis": h_z, "spindle": h_sp, "counterweight": counterweight(*POSE[:2]),
                          "x_chain": xchain},
                   text="No two parts shall overlap (posed mid-sheet)",
                   allow=[("gantry_frame", "gantry_drives")])
require_no_overlap("R10", {"bed": bed_w, "base": base, "feet": feet}, text="Floor frame shall not overlap the bed",
                   allow=[("bed", "base")])
gf, go = gantry(X_TRAVEL[0])
fixed_g = {"bed": bed, "substrate": substrate, "spoilboard": spoil, "rails": rail_b + rail_t, "racks": rack_b + rack_t, "atc": atc,
           "sheet+clamps": clamps}
fixed_gw = {k: world(v) for k, v in fixed_g.items()}
fixed_gw["floor frame"] = base
fixed_gw["floor (25 mm clearance)"] = box(-2000, 5000, -2000, 2000, -50, 25)
fixed_gw["x cable chain"] = world(xchain)
span = X_TRAVEL[1] - X_TRAVEL[0]
for ys in Y_WORK:
    mov = fuse([gf, go] + list(head(X_TRAVEL[0], ys, ZN_MAX - TIP_TO_NOSE)[:3])).moved(W)
    clear_travel("R11", mov, fixed_gw, place=lambda t: Location.translation(t * span, 0, 0), tag=f"retracted, y {ys:g}",
                 text="Retracted, gantry and head shall clear the bed, racks, ATC, floor frame and clamps over all X travel")
# plunged: only over the sheet (tool excluded, it cuts by design; ATC rack excluded, it is visited retracted)
fixed_cut = {k: v for k, v in fixed_gw.items() if k not in ("atc", "sheet+clamps")}
fixed_cut["sheet"] = world(stock)
for ys in Y_WORK:
    mov = fuse(list(gantry(X_WORK[0])) + list(head(X_WORK[0], ys, TIP_MIN)[:3])).moved(W)
    clear_travel("R12", mov, fixed_cut, tag=f"y {ys:g}",
                         place=lambda t: Location.translation(t * (X_WORK[1] - X_WORK[0]), 0, 0),
                         text="Plunged, the head shall clear everything but the cut over the sheet")
# Y travel of the head against the gantry and bed, plunged and retracted
gfw = {"gantry frame": world(gf), "gantry drives": world(go), "bed": bed_w, "rails": world(rail_b + rail_t), "floor frame": base}
for tip in (TIP_MIN, ZN_MAX - TIP_TO_NOSE):
    mov = fuse(list(head(X_TRAVEL[0], Y_WORK[0], tip)[:3])).moved(W)
    d = wpt(0, Y_WORK[1] - Y_WORK[0], 0)
    o = wpt(0, 0, 0)
    clear_travel("R13", mov, gfw, tag=f"tip {tip:g}",
                         place=lambda t: Location.translation(0, t * (d[1] - o[1]), t * (d[2] - o[2])),
                         text="The head shall clear the gantry and bed over all Y travel")
# parked for loading: the whole gantry left of the sheet
park = fuse(list(gantry(X_TRAVEL[0])) + list(head(X_TRAVEL[0], Y_WORK[0], ZN_MAX - TIP_TO_NOSE)))
require("R14", "Parked, the gantry shall leave the whole sheet open for loading from the front",
        0.0 - park.bounding_box().max()[0], ">=", 20, "mm")
