"""The fixed parts in the local machine frame: bed weldment, spoilboard, rails, racks, the cable chains' specs,
the tool rack, the sheet and the space workholding may use."""
import math
from cnc.params import (
    ATC_X, ATC_Y, BED_D, BLK_H, CHAIN, CHAIN_R, CLAMP_H, COL_D, COL_W, FORK_Z, LAND, PL, RACK_H, RACK_OFF, RACK_SHIM,
    RACK_W, RAIL_H, RAIL_W, SHEET_L, SHEET_W, SPOIL_T, SP_OFF, STOCK_T, TIP_MIN, TIP_TO_NOSE, X_BED, X_TRAVEL, YCH,
    Y_RB, Y_RISER, Y_RT, Y_WORK, ZC0, ZCH_LEN, ZN_MIN, ZYP1, Z_TRAVEL)
from cnc.geometry.shapes import box, fuse

# ---- bed weldment: two rail beams (RHS 100 x 80 x 5, rails and racks on their front faces), RHS 50 x 50 x 3 cross
# members under a 25 mm MDF substrate that carries the spoilboard
RAIL_BEAM = dict(b=100.0, d=BED_D, t=5.0)          # b along y (in the bed's plane), d along z (its depth)
CROSS = dict(b=50.0, d=50.0, t=3.0)
SUBSTRATE_T = 25.0
SPOIL_SPLIT = 1250.0     # the spoilboard is two boards (each under 30 kg), joined here, off the substrate joints and the pin holes
CROSS_PITCH = 300.0
BED_BACK = -SPOIL_T - LAND - BED_D
beam_b = box(X_BED[0], X_BED[1], Y_RB - 80, Y_RB + 20, BED_BACK, -SPOIL_T - LAND)
beam_t = box(X_BED[0], X_BED[1], Y_RT - 20, Y_RT + 80, BED_BACK, -SPOIL_T - LAND)
lands = [box(X_BED[0], X_BED[1], y - 15, y + 15, -SPOIL_T - LAND - 0.0, -SPOIL_T) for y in (Y_RB, Y_RT)] + \
        [box(X_BED[0], X_BED[1], y - RACK_W / 2, y + RACK_W / 2, -SPOIL_T - LAND, -SPOIL_T + RACK_SHIM)
         for y in (Y_RB - RACK_OFF, Y_RT + RACK_OFF)]
n_cross = int(math.ceil((X_BED[1] - X_BED[0] - CROSS["b"]) / CROSS_PITCH)) + 1
cross_x = [X_BED[0] + CROSS["b"] / 2 + i * (X_BED[1] - X_BED[0] - CROSS["b"]) / (n_cross - 1) for i in range(n_cross)]
z_sub = -SPOIL_T - SUBSTRATE_T
crosses = [box(x - CROSS["b"] / 2, x + CROSS["b"] / 2, Y_RB + 20 - 1, Y_RT - 20 + 1, z_sub - CROSS["d"], z_sub - 0.5) for x in cross_x]
bed = fuse([beam_b, beam_t] + lands + crosses)
# (modelled with 0.5 mm glue lines to the steel and the spoilboard, so the solids do not share faces)
substrate = box(X_BED[0], X_BED[1], Y_RB + 20.5, Y_RT - 20.5, z_sub, -SPOIL_T - 0.5)
spoil = box(-20, SHEET_L + 20, -30, SHEET_W + 30, -SPOIL_T, 0)
rail_b = box(X_BED[0], X_BED[1], Y_RB - RAIL_W / 2, Y_RB + RAIL_W / 2, -SPOIL_T, -SPOIL_T + RAIL_H)
rail_t = box(X_BED[0], X_BED[1], Y_RT - RAIL_W / 2, Y_RT + RAIL_W / 2, -SPOIL_T, -SPOIL_T + RAIL_H)
RACK_Z = (-SPOIL_T + RACK_SHIM, -SPOIL_T + RACK_SHIM + RACK_H)
# racks modelled to their tooth roots (2.25 m below the tips); the pinion to its root circle, so a correct mesh shows no overlap
M_GEAR = 1.5
rack_b = box(X_BED[0], X_BED[1], Y_RB - RACK_OFF - RACK_W / 2 + 2.25 * M_GEAR, Y_RB - RACK_OFF + RACK_W / 2, *RACK_Z)
rack_t = box(X_BED[0], X_BED[1], Y_RT + RACK_OFF - RACK_W / 2, Y_RT + RACK_OFF + RACK_W / 2 - 2.25 * M_GEAR, *RACK_Z)
# X cable chain: lies against the bed's back face below its top edge, looping in the bed's plane
XCH = CHAIN["X"]
# X cable chain: stands upright in the bed's plane on a tray along the top rail beam's top edge, looping upwards
# (above the 1800 mm limit, which the user accepted for the chain), clear of the rear posts behind the bed.
XCH_Z = (-SPOIL_T - LAND - XCH["w"], -SPOIL_T - LAND)
CH_PAD = 1.5            # chain zones: room for the link corners at the bend's outside
XCH_TRAY = 3.0
XCH_Y = (Y_RT + 80, Y_RT + 80 + XCH_TRAY + 2 * CHAIN_R + XCH["h"] + 2 * CH_PAD)
xchain = box(X_BED[0], X_BED[1], *XCH_Y, *XCH_Z) + box(X_BED[0], X_BED[1], XCH_Y[0], XCH_Y[0] + XCH_TRAY + 0.2, XCH_Z[0] - 42.2, XCH_Z[0] + 0.5)


def _chain_spec(part, group, var, m_off, m_lo, m_hi, F_rest, d, n, w, ch, pitch, zone, f_back=0.0):
    """A cable chain: fixed end F, runs along d (which may point either way along its axis), bends towards n, width along
    w. Its moving end is at m = pose[var] + m_off. f, m_min, m_max and zone are measured along d; the fixed end sits at the
    middle of the moving end's range, moved f_back against d (so the chain's loop reaches less far along d)."""
    sg = sum(d)
    lo, hi = sorted((sg * m_lo, sg * m_hi))
    f = (lo + hi) / 2 - f_back
    F = tuple(sg * f if d[i] else F_rest[i] for i in range(3))
    L = 60.0 + f - lo + math.pi * CHAIN_R
    return dict(part=part, group=group, var=var, m_off=m_off, m_min=lo, m_max=hi, f=f, F=F, d=d, n=n, w=w, R=CHAIN_R, sg=sg,
                h=ch["h"], W=ch["w"], pitch=pitch, L=L, N=int(math.ceil(L / pitch)) + 1, zone=tuple(sorted((sg * zone[0], sg * zone[1]))))


_offx = -SP_OFF - COL_W + 100                      # X chain's moving end (the arm), from the spindle axis
_cc0 = -SP_OFF - COL_W / 2                         # column centre at xs = 0
_zoff = ZYP1 - 450 - ZN_MIN                        # Z chain's moving end on the Z plate, from the nose
CHAIN_SPECS = {
    "bed.x_chain": _chain_spec("cable chain 25 x 57 inside, R100, pitch 38, upright on a tray on the bed's top edge", "fixed", "x", _offx,
                               X_TRAVEL[0] + _offx, X_TRAVEL[1] + _offx, (0, XCH_Y[0] + XCH_TRAY + CH_PAD + CHAIN["X"]["h"] / 2, XCH_Z[1]),
                               (-1, 0, 0), (0, 1, 0), (0, 0, -1), CHAIN["X"], 38.0, (X_BED[0], X_BED[1]), f_back=10.0),
    "gantry_drives.y_chain": _chain_spec("cable chain 25 x 38 inside, R100, pitch 33", "x", "y", 100.0, Y_WORK[0] + 100, Y_WORK[1] + 100,
                                         (_cc0 - CHAIN["Y"]["w"] / 2, 0, ZC0 + COL_D + 5 + CH_PAD + CHAIN["Y"]["h"] / 2),
                                         (0, -1, 0), (0, 0, 1), (1, 0, 0), CHAIN["Y"], 33.0, (Y_RB - 40, Y_RT + 40), f_back=10.0),
    "y_carriage.z_chain": _chain_spec("cable chain 25 x 38 inside, R100, pitch 33", "xy", "tip", TIP_TO_NOSE + _zoff,
                                      TIP_MIN + TIP_TO_NOSE + _zoff, TIP_MIN + Z_TRAVEL + TIP_TO_NOSE + _zoff,
                                      (-SP_OFF + Y_RISER + BLK_H + PL + CH_PAD + CHAIN["Z"]["h"] / 2, YCH + 5, 0),
                                      (0, 0, 1), (1, 0, 0), (0, 1, 0), CHAIN["Z"], 33.0, (ZYP1 - ZCH_LEN, ZYP1)),
}
Y_FIX = CHAIN_SPECS["gantry_drives.y_chain"]["F"][1]   # Y chain's fixed end: the middle of its moving end's range, 10 up
atc = box(ATC_X[0] - 9, ATC_X[1] + 9, ATC_Y[0] - 20, ATC_Y[1] + 20, -SPOIL_T - 0.2, FORK_Z + 100)   # forks, holders and cutters, stands
stock = box(0, SHEET_L, 0, SHEET_W, 0, STOCK_T)          # the sheet: an outside thing
clamps = box(0, SHEET_L, 0, SHEET_W, 0, CLAMP_H)         # space workholding may use
