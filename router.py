"""Horizontal (tilted-bed) CNC router for a full 2400 x 1200 sheet - concept design.

Local machine frame (before tilting):  x = along the sheet's 2400 length,
y = up the bed slope (sheet bottom edge at y = 0), z = normal to the bed, towards the operator
(spoilboard face at z = 0).  The bed is then tilted back TILT degrees from vertical.
World frame: X = along the machine, Y = front (-) to back (+), Z = up, floor at Z = 0.
"""
import math
from se import *
from se import _shared
import detail as D


def clear_travel(id, moving, fixed, place, tag, text, steps=9):
    """require_clear_travel with a tag on each case, for one requirement checked in several poses."""
    for i in range(steps):
        there = moving.moved(place(i / (steps - 1)))
        for name, other in fixed.items():
            require(id, text, _shared(there, other), "<=", 0, "mm^3", case=f"{tag}: {name}, step {i} of {steps - 1}")

# ------------------------------------------------------------------ stated by the user
SHEET_L, SHEET_W = 2400.0, 1200.0        # full sheet
TILT = 10.0                              # deg from vertical (answer to question)
Z_TRAVEL_REQ = 300.0                     # sketch: "(Z-travel) 300"
H_MAX = 1800.0                           # sketch: "<= 1800"
DEPTH_MAX = 1000.0                       # answer: floor depth <= 1000 mm
SUPPLY_V, SUPPLY_A = 240.0, 15.0         # single-phase circuit

# ------------------------------------------------------------------ assumed values
STOCK_T = 25.0          # thickest sheet to be cut
TOOL_D = 12.0           # largest cutter used to profile the sheet edge
OVERRUN = 3.0           # tool clears the sheet edge by this much
SPOIL_T = 25.0          # MDF spoilboard
TIP_MIN = -2.0          # deepest tool tip: 2 mm into the spoilboard
CLAMP_H = 40.0          # tallest workholding above the spoilboard

# Bought parts (catalogue sizes)
RAIL_H, RAIL_W = 22.0, 23.0              # HGR25 rail
BLK_H, BLK_W, BLK_L = 40.0, 48.0, 84.0   # HGH25CA block: height from rail base, width, length
SP_W, SP_L, SP_REAR = 133.0, 510.0, 50.0 # spindle body 133 sq x 510 long, fan cowl/plug behind
HOLDER_R, HOLDER_L = 25.0, 65.0          # ISO30 holder + collet nut below the nose
TOOL_STICK = 55.0                        # cutter stick-out below the holder
NEMA = 86.0                              # NEMA34 frame
# Y screw: 25 mm, lead 20 (Misumi BSS2520 class): nut OD 45, flange 68 x 12, nut 75 long; BK20 fixed end (top),
# BF20 floating end (bottom): centre height 34, 88 wide, 60 high, 35 / 20 long.
YS_D, YN_D, YN_FL, YN_FT, YN_L = 25.0, 45.0, 68.0, 12.0, 75.0
BK20 = dict(h=34.0, B=88.0, H=60.0, L=35.0 + 8.0)
BF20 = dict(h=34.0, B=88.0, H=60.0, L=20.0)
# Z screw: SFU2010: nut OD 36, flange 58 x 10, nut 85 long; BK15 / BF15: centre height 28, 70 wide, 47 high, 27+6 / 20 long.
ZS_D, ZN_D, ZN_FL, ZN_FT, ZN_L = 20.0, 36.0, 58.0, 10.0, 85.0
BK15 = dict(h=28.0, B=70.0, H=47.0, L=33.0)
BF15 = dict(h=28.0, B=70.0, H=47.0, L=20.0)
SUP_SPACER = 6.0                         # support blocks sit on 6 mm spacers so the nut flanges clear the face below
NUT_CLEAR = 3.0                          # flange to face clearance
# Rail risers: the screw and its nut sit between the rails, so the blocks are lifted clear of the nut flange
Y_RISER = 40.0                           # steel bar welded to the column face, rails on top
Z_RISER = 32.0                           # aluminium bar on the Y plate: lifts the Z blocks clear of BK15 at the top of the stroke
BRAKE_D, BRAKE_L = 70.0, 45.0            # 24 V spring-applied brake on the Y screw's bottom end
Z_RAIL_DY = 50.0                         # Z rails at +-50: the Y blocks' bolt holes (at +-88 +-17.5) stay clear of the Z risers
CLAMP_Z = (130.0, 260.0)                 # spindle clamps, from the nose: between the Z blocks' bolt rows
ZCH_LEN = 470.0                          # Z chain zone, from the Y plate's far end: high enough to clear the ATC rack
HTD_W = 30.0                             # belt and pulley plane thickness (HTD 5M, 15 mm belt, flanged pulleys)
# The salvaged axis motors: StepperOnline 34E1K-120 (datasheet in parts/): 12 N*m holding, 6 A, 0.72 ohm, 7.3 mH,
# rotor 5400 g*cm^2, 5.0 kg, 1000 PPR encoder. Its STEP: mounting face at z = 0, shaft +z, cable outlet -y.
MOTOR_STEP = import_step_file("parts/34E1K-120.STEP").parts()[0]
# Its envelope, built from the datasheet and the STEP's cable outlet, so it can be fused and clash-checked
# (R32 checks that the STEP lies inside it).
M_HOLD, M_AMPS, M_L, M_J, M_KG = 12.0, 6.0, 7.3e-3, 5.4e-4, 5.0
V_BUS = 58.0                             # V DC: the salvaged 60 V 350 W supplies, ~58 V loaded
PSU_W = 350.0                            # W, one supply per driver (assumed)


def _motor_envelope(pad=0.5):
    """Datasheet sizes plus `pad` all round, so it clears the STEP's own faces."""
    body = Part.cuboid(85.86 + 2 * pad, 85.86 + 2 * pad, 172.4 + 2 * pad).moved(Location.translation(0, 0, -86.2))
    pilot = Part.cylinder(36.5 + pad, 1.6 + pad)
    pilot = pilot.moved(Location.translation(0, 0, -pilot.bounding_box().min()[2] - 0.1))
    shaft = Part.cylinder(7.0 + pad, 35.4 + pad)
    shaft = shaft.moved(Location.translation(0, 0, 1.5 - shaft.bounding_box().min()[2]))
    outlet = Part.cuboid(36.0 + 2 * pad, 101.5 + 2 * pad, 173.5 + 2 * pad).moved(Location.translation(-2.35, -93.2, -74.2))  # cables, from the STEP
    return body.fuse_all([pilot, shaft, outlet])


MOTOR = _motor_envelope()


XD_TOP = 44.0     # X drive: motor plate's top face above the X blocks' top (8 lower plate, 30 standoffs, 6 motor plate)


def x_motor_loc(c0, y):      # shaft towards the bed into a 3:1 belt to the pinion, cable outlet away from the column
    return Location.translation(c0 - 55, y, BLK_Z + XD_TOP) * Location.about(Axis.Z, 90) * Location.about(Axis.X, 180)


def y_motor_loc(c0):         # beside the column top, parallel to the screw, shaft up into a 30T:20T belt step-up over the top cap
    return Location.translation(c0 - 50, Y_RT + 40, ZC0 + COL_D - 60) * Location.about(Axis.Y, -90) * Location.about(Axis.X, -90)


def z_motor_loc(c1, ys):     # behind the Y plate, parallel to the Z screw, shaft out past the plate's end into a 40T:20T belt
    return Location.translation(c1 + Y_RISER + BLK_H - 50, ys, ZYP1 + 3.5) * Location.about(Axis.Z, -90)

# ------------------------------------------------------------------ design variables
BED_D = 80.0           # bed rail beam depth (RHS 100 x 80)
LAND = 10.0            # flat-bar rail lands welded on the beams' front faces, machined: they take the M6 rail screws
COL_W, COL_D = 160.0, 300.0   # gantry column (fabricated box), x and z
COL_T = 6.0
ZC0 = 100.0             # underside of the column above the spoilboard
PL = 25.0               # Y and Z plate thickness
YCH = 130.0             # half-height of the Y carriage (along y)
ZP0, ZP1 = 50.0, 400.0  # Z plate extent measured from the spindle nose
FOOT_H = 30.0           # levelling feet
BASE_H = 100.0          # floor frame RHS height
X_PARK_GAP = 40.0       # parked gantry clears the sheet edge by this

# Drives
X_PINION_PCD = 31.83    # m1.5 20T helical pinion (19.5 deg helix): 1.5 x 20 / cos 19.5
RACK_W, RACK_H, RACK_SHIM = 17.0, 17.0, 3.0   # m1.5 helical rack section; it sits on a 3 mm shim
RACK_OFF = 60.0         # rack centre from its rail centre, outwards (teeth face away from the rail)
PIN_FACE = 15.0         # pinion face width: narrower than the 17 mm rack so it stays clear of the rack's land
# Cable chains: continuous-flex cables (largest: spindle 4G2.5 shielded, 13 mm) need a bend radius >= 7.5 d
CABLE_D_MAX = 13.0
CHAIN_R = 100.0
CHAIN = {"X": dict(h=35.0, w=80.0, inner=(25.0, 57.0)), "Y": dict(h=35.0, w=60.0, inner=(25.0, 38.0)),
         "Z": dict(h=35.0, w=60.0, inner=(25.0, 38.0))}
# cables each chain carries, by outside diameter (mm): spindle, motor power + encoder per motor, brake, fan,
# air 8 and 6, probe and limit switches
import electrical as EL
CABLES = EL.chain_fill(None)          # from the cable schedule in electrical.py
X_RATIO = 3.0           # belt reduction motor:pinion
Y_LEAD, Y_RATIO = 20.0, 2 / 3   # SFU2520 ball screw, belt steps up (motor 30T : screw 20T)
Z_LEAD, Z_RATIO = 10.0, 0.5     # SFU2010, belt steps up (motor 40T : screw 20T)
V_RAPID = {"X": 15.0, "Y": 10.0, "Z": 5.0}   # m/min, assumed targets
ACC = {"X": 1.0, "Y": 1.0, "Z": 1.0}         # m/s^2
F_CUT = 300.0           # N, cutting + feed force while cutting at F_FEED
F_FEED = 6.0            # m/min
# Future 3-phase case: the axes, not the spindle, cap the cut. Largest cut the axes can feed:
# 25 mm cutter, 25 mm deep slot, 10 m/min, spindle at its slowest 12 000 rpm (highest force per watt).
F_FEED_3PH = 10.0                                   # m/min
U_WOOD = 0.04                                       # J/mm^3 (= N/mm^2), plywood / MDF
P_CUT_3PH = U_WOOD * 25 * 25 * (F_FEED_3PH * 1000 / 60)          # W
F_CUT_3PH = P_CUT_3PH / (math.pi * 0.025 * 12000 / 60)           # N, tangential force at the cutter
BRAKE_T = 4.0
# Y counterweight: steel block running inside the gantry column, rope over a sheave at the column top, reeved 2:1
# (a sheave on the block, the rope's end anchored at the column top) so it moves half the head's travel.
M_YC, M_ZA, M_SP = 36.0, 13.0, 31.0      # budgets: R51 checks the detailed parts against them
M_SPINDLE_KG = 29.0                      # the spindle alone (catalogue of the same body)      # kg: Y carriage (plate, Y nut, Z motor, Z screw and supports, aluminium risers), Z axis (with nut), spindle
M_HEAD = M_YC + M_ZA + M_SP - 4.0        # kg moving on Y (half the Y blocks stay on the column)
CW_FRAC = 0.9                            # balances 90 %: the head still weighs down, keeping the screw loaded one way
REEVE = 2.0
M_CW = REEVE * CW_FRAC * M_HEAD          # kg of steel
ROPE_D, SHEAVE_D, ROPE_MBL = 5.0, 100.0, 15000.0   # mm, mm, N (7x19 galvanised, minimum breaking load)
CW_GAP = 6.0                             # clearance to the column walls
CW_SHEAVE = 120.0                        # length of the block's sheave fork on its top (110 sheave, axis along x)           # N*m, 24 V spring-applied brake on the Y screw

# ------------------------------------------------------------------ derived positions
M = TOOL_D / 2 + OVERRUN                       # tool-centre overrun past each sheet edge
X_WORK = (-M, SHEET_L + M)                     # spindle-axis x range while cutting
Y_WORK = (-M, SHEET_W + M)
TIP_TO_NOSE = HOLDER_L + TOOL_STICK
SP_OFF = Y_RISER + BLK_H + PL + Z_RISER + BLK_H + PL + 10 + SP_W / 2   # column +x face -> spindle axis
YS_X = SUP_SPACER + BK20["h"]                  # Y screw axis, from the column face
YS_Z = ZC0 + COL_D / 2                         # Y screw axis, between the Y rails
ZS_X = SUP_SPACER + BK15["h"]                  # Z screw axis, from the Y plate's outer face
Y_RAIL = (Y_WORK[0] - YCH, Y_WORK[1] + YCH)
Y_RB = Y_RAIL[0] + 40.0                        # bottom X rail centre (column end is 40 below)
Y_RT = Y_RAIL[1] - 40.0
ZN_MIN = TIP_MIN + TIP_TO_NOSE                 # spindle nose z, plunged
ZYP0 = ZC0 + 15.0
ZYP1 = ZN_MIN + ZP1 + Z_TRAVEL_REQ + 40.0      # Y plate: the stroke, plus room for BK15 above the Z blocks' wings at the top
Z_CH_F = ZYP1 - 300.0                          # Z chain's fixed end, likewise
Z_TRAVEL = Z_TRAVEL_REQ                        # stroke, set by the limit switches
ZN_MAX = ZN_MIN + Z_TRAVEL
# ATC: six ISO30 forks beyond the sheet's right edge. The column trails the spindle by SP_OFF, so it never passes
# over them (a rack at the left end would be under the column's path: holders stand ~200 mm proud of the bed).
ATC_X = (SHEET_L + 49.0, SHEET_L + 159.0)
ATC_N, ATC_PITCH = 6, 110.0
ATC_YC = [300.0 + i * ATC_PITCH for i in range(ATC_N)]
ATC_Y = (ATC_YC[0] - 50.0, ATC_YC[-1] + 50.0)
FORK_Z = 120.0                                 # fork plate's underside above the spoilboard face
ATC_XC = (ATC_X[0] + ATC_X[1]) / 2
# park: whole gantry left of the ATC rack and the sheet
X_PARK = -X_PARK_GAP - (SP_W / 2 + 12)        # parked at the left end: the clamps' edge 40 mm left of the sheet
X_TRAVEL = (X_PARK, ATC_XC)                    # right end: over the tool rack
X_BED = (X_PARK - SP_OFF - COL_W - 60.0, max(X_TRAVEL[1] - SP_OFF + 60.0, ATC_X[1] + 10.0))   # the bed carries the spoilboard and the rack
BLK_Z = -SPOIL_T + BLK_H                       # top of X blocks


def fuse(parts):
    parts = list(parts)
    return parts[0].fuse_all(parts[1:]) if len(parts) > 1 else parts[0]


def box(x0, x1, y0, y1, z0, z1):
    return Part.cuboid(x1 - x0, y1 - y0, z1 - z0).moved(
        Location.translation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def cyl_z(cx, cy, r, z0, z1):
    c = Part.cylinder(r, z1 - z0)
    b = c.bounding_box()
    return c.moved(Location.translation(cx, cy, z0 - b.min()[2]))


# ------------------------------------------------------------------ fixed parts (local frame)
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


# ------------------------------------------------------------------ moving parts
SHEAVE_Y = Y_RT + 40 - 10 - SHEAVE_D / 2 - 10         # top sheave centre, just under the column's top cap
SHEAVE_Z = ZC0 + 85.0                                 # rope plane, between the lower Y rail and the screw supports
ROPE_X = 10.0                                         # rope runs 10 mm off the column face, in the gap


def top_sheave(c1):
    """Fixed sheave (with its flanges) turning the rope from the carriage, in the gap outside the column's +x wall,
    into the column; it passes through a slot in the wall."""
    return cyl_z(c1 + ROPE_X - SHEAVE_D / 2, SHEAVE_Y, SHEAVE_D / 2 + 5, SHEAVE_Z - 15, SHEAVE_Z + 15)


def cyl_y(cx, cz, r, y0, y1):
    """A cylinder along y."""
    c = Part.cylinder(r, y1 - y0).moved(Location.about(Axis.X, -90))
    b = c.bounding_box()
    return c.moved(Location.translation(cx - (b.min()[0] + b.max()[0]) / 2, y0 - b.min()[1], cz - (b.min()[2] + b.max()[2]) / 2))


CW_X = COL_W - 2 * COL_T - 2 * CW_GAP
CW_Z = COL_D - 2 * COL_T - 2 * CW_GAP
CW_LEN = M_CW / 7.85e-6 / ((CW_X - 8) * (CW_Z - 8)) + CW_SHEAVE      # slabs inset 4 for the UHMW guide strips
CW_TOP_HI = SHEAVE_Y - SHEAVE_D / 2 - 5 - 25         # highest the block's top may go: 25 mm under the fixed sheave


def counterweight(xs, ys):
    """The block, highest when the head is lowest, moving half the head's travel the other way."""
    c1 = xs - SP_OFF
    c0 = c1 - COL_W
    top = CW_TOP_HI - (ys - Y_WORK[0]) / REEVE
    return box(c0 + COL_T + CW_GAP, c1 - COL_T - CW_GAP, top - CW_LEN, top,
               ZC0 + COL_T + CW_GAP, ZC0 + COL_D - COL_T - CW_GAP)


def gantry(xs, motors=True, with_arm=True):
    """Column, feet, X blocks and X motors with the spindle axis at x = xs."""
    c1 = xs - SP_OFF
    c0 = c1 - COL_W
    cc = (c0 + c1) / 2
    col = box(c0, c1, Y_RB - 40, Y_RT + 40, ZC0, ZC0 + COL_D) - box(
        c0 + COL_T, c1 - COL_T, Y_RB - 40 + 10, Y_RT + 40 - 10, ZC0 + COL_T, ZC0 + COL_D - COL_T)   # box, 10 mm end caps
    col = col + top_sheave(c1) + cyl_z(c1 + ROPE_X - SHEAVE_D / 2, SHEAVE_Y, 10.5, ZC0 + COL_T - 0.3, ZC0 + COL_T + 11.2)
    feet = [box(c0, c1, y - 40, y + 40, BLK_Z, ZC0) for y in (Y_RB, Y_RT)]
    blocks = [D.c_block_env().moved(D.frame((cc + dx, y, -SPOIL_T), (1 if dx < 0 else -1, 0, 0), (0, 0, 1))) for y in (Y_RB, Y_RT) for dx in (-45, 45)]
    # X motors: shaft towards the bed into a 3:1 belt to the pinion, cable outlet away from the column
    xmot = [MOTOR.moved(x_motor_loc(c0, y)) for y in (Y_RB, Y_RT)] if motors else []
    # X drive: 15T on the motor, 45T on the pinion shaft (3:1), pinion meshing the outward face of the rack;
    # its bearing housing pivots on the foot and a spring pulls it into mesh
    belt_x = []
    for y, sgn in ((Y_RB, -1), (Y_RT, 1)):
        yp = y + sgn * (RACK_OFF + RACK_W / 2 - 1.5 + X_PINION_PCD / 2)          # pinion centre
        zp = (RACK_Z[0] + RACK_Z[1]) / 2
        xp = c0 - 55
        pinion = cyl_z(xp, yp, X_PINION_PCD / 2 - 1.25 * M_GEAR, zp - PIN_FACE / 2, zp + PIN_FACE / 2)
        housing = box(xp - 35, xp + 35, yp - 35, yp + 35, max(zp + PIN_FACE / 2, RACK_Z[1]) + 1, BLK_Z)
        _L = D.x_drive_layout(globals(), c0, y, sgn)
        belt = box(_L["xlo"], c0 + 30.4, _L["ylo"], _L["yhi"], BLK_Z - 0.3, BLK_Z + XD_TOP + 0.3)
        shaft = cyl_z(xp, yp, 7.5, zp + PIN_FACE / 2 - 0.5, BLK_Z + 1) + cyl_z(xp, yp, 12.5, zp - PIN_FACE / 2 - 10.5, zp - PIN_FACE / 2 + 0.5)
        belt_x += [pinion, housing, belt, shaft]
    # Y motor beside the column top, parallel to the screw, shaft up into a 30T:20T belt step-up
    ymot = [MOTOR.moved(y_motor_loc(c0))] if motors else []
    risers = [box(c1, c1 + Y_RISER, Y_RAIL[0], Y_RAIL[1], z - RAIL_W / 2, z + RAIL_W / 2) for z in (ZC0 + 40, ZC0 + COL_D - 40)]
    yrails = [box(c1 + Y_RISER, c1 + Y_RISER + RAIL_H, Y_RAIL[0], Y_RAIL[1], z - RAIL_W / 2, z + RAIL_W / 2)
              for z in (ZC0 + 40, ZC0 + COL_D - 40)]
    # Y screw: BK20 at the top (drive end), BF20 at the bottom with the brake below the column's end
    xs_, top = c1 + YS_X, Y_RT + 40
    bk = box(c1, c1 + SUP_SPACER + BK20["H"], top - BK20["L"], top, YS_Z - BK20["B"] / 2, YS_Z + BK20["B"] / 2)
    bf = box(c1, c1 + SUP_SPACER + BF20["H"], Y_RB - 40, Y_RB - 40 + BF20["L"], YS_Z - BF20["B"] / 2, YS_Z + BF20["B"] / 2)
    yscrew = cyl_y(xs_, YS_Z, YS_D / 2, Y_RB - 40 - 5 - BRAKE_L, top + 6 + HTD_W)
    brake = cyl_y(xs_, YS_Z, 47.5, Y_RB - 40 - 5 - BRAKE_L, Y_RB - 40 - 0.3)          # with its flange and standoffs to BF20
    # belt over the top cap: 20T on the screw, 30T on the Y motor (axis at c0 - 50, ZC0 + COL_D - 60)
    ybelt = box(c0 - 95, xs_ + 25, top + 0.5, top + 6 + HTD_W, YS_Z - 30, ZC0 + COL_D - 60 + 45)     # motor plate, pulleys, belt
    # arm from the top foot over the bed's top edge, down behind it to the X cable chain's moving end
    # arm from the top foot up past the bed's top edge (over the rack) to the X chain's moving end on its upper run
    arm = fuse([box(c0 + 60, c0 + 140, Y_RT - 40, XCH_Y[1] + 12, -3, BLK_Z + 15),
                box(c0 + 60, c0 + 140, XCH_Y[1] + 0.5, XCH_Y[1] + 12, XCH_Z[0], -3 + 0.5)])
    # Y chain's fixed end: a bracket from the column's front face
    ych_fix = box(cc - CHAIN["Y"]["w"] / 2, cc + CHAIN["Y"]["w"] / 2, Y_FIX - 30, Y_FIX + 30, ZC0 + COL_D + 0.5, ZC0 + COL_D + 4.5)
    # Y cable chain: on the column's front face, looping out towards the operator
    ych = box(cc - CHAIN["Y"]["w"] / 2, cc + CHAIN["Y"]["w"] / 2, Y_RB - 40, Y_RT + 40,
              ZC0 + COL_D + 5, ZC0 + COL_D + 5 + 2 * CHAIN_R + CHAIN["Y"]["h"] + 2 * CH_PAD)
    frame = fuse([col] + feet + ([arm] if with_arm else []))
    others = fuse(blocks + xmot + belt_x + ymot + risers + yrails + [bk, bf, yscrew, brake, ybelt, ych, ych_fix])
    return frame, others


def head(xs, ys, tip, motors=True, zchain=True):
    """Y carriage, Z axis and spindle: spindle axis at (xs, ys), tool tip at z = tip."""
    c1 = xs - SP_OFF
    zn = tip + TIP_TO_NOSE
    yblk = [D.c_block_env().moved(D.frame((c1 + Y_RISER, ys + dy, z), (0, 1, 0), (1, 0, 0)))
            for z in (ZC0 + 40, ZC0 + COL_D - 40) for dy in (-88, 88)]
    x = c1 + Y_RISER + BLK_H                       # Y plate inner face
    yplate = box(x, x + PL, ys - YCH, ys + YCH, ZYP0, ZYP1)
    # Y nut in its bracket, bolted to the plate's inner face; the screw passes through
    xs_ = c1 + YS_X
    ynut = fuse([box(xs_ - YN_D / 2 - 6, x, ys - YN_L / 2 - 8, ys + YN_L / 2 - YN_FT, YS_Z - 40, YS_Z + 40),
                 cyl_y(xs_, YS_Z, YN_D / 2, ys - YN_L / 2, ys + YN_L / 2),
                 cyl_y(xs_, YS_Z, YN_FL / 2, ys + YN_L / 2 - YN_FT, ys + YN_L / 2)]) - cyl_y(xs_, YS_Z, YS_D / 2 + 0.5, ys - 200, ys + 200)
    # counterweight rope anchor, reaching from the plate into the gap
    anchor = box(c1 + ROPE_X - 6, x, ys, ys + 20, SHEAVE_Z - 10, SHEAVE_Z + 10)
    zmot = [MOTOR.moved(z_motor_loc(c1, ys))] if motors else []
    x += PL                                        # Y plate outer face
    zx = x
    zrisers = [box(x, x + Z_RISER, ys + dy - RAIL_W / 2, ys + dy + RAIL_W / 2, ZYP0, ZYP1) for dy in (-Z_RAIL_DY, Z_RAIL_DY)]
    zrails = [box(x + Z_RISER, x + Z_RISER + RAIL_H, ys + dy - RAIL_W / 2, ys + dy + RAIL_W / 2, ZYP0, ZYP1) for dy in (-Z_RAIL_DY, Z_RAIL_DY)]
    zbk = box(x, x + SUP_SPACER + BK15["H"], ys - BK15["B"] / 2, ys + BK15["B"] / 2, ZYP1 - BK15["L"], ZYP1)
    zbf = box(x, x + SUP_SPACER + BF15["H"], ys - BF15["B"] / 2, ys + BF15["B"] / 2, ZYP0, ZYP0 + BF15["L"])
    zscrew = cyl_z(x + ZS_X, ys, ZS_D / 2, ZYP0, ZYP1 + 12 + HTD_W)
    zbelt = box(c1 + Y_RISER + BLK_H - 50 - 38, x + ZS_X + 22, ys - 38, ys + 38, ZYP1 + 12, ZYP1 + 12 + HTD_W)
    zmount = box(c1 - 15, x, ys - 45, ys + 45, ZYP1 + 4, ZYP1 + 10) + box(c1 + Y_RISER + BLK_H - 8.5, c1 + Y_RISER + BLK_H - 0.5, ys - 45, ys + 45, ZYP1 - 40, ZYP1 + 4.5)
    x += Z_RISER
    zblk = [D.c_block_env().moved(D.frame((x, ys + dy, zn + z0 + BLK_L / 2), (0, 0, 1), (1, 0, 0)))
            for dy in (-Z_RAIL_DY, Z_RAIL_DY) for z0 in (ZP0, ZP1 - BLK_L)]
    # Z nut in its bracket on the Z plate's inner face, mid-plate
    zc = zn + (ZP0 + ZP1) / 2
    znut = fuse([box(zx + ZS_X - ZN_D / 2 - 6, x + BLK_H, ys - 36, ys + 36, zc - ZN_L / 2 - 8, zc + ZN_L / 2 - ZN_FT),
                 cyl_z(zx + ZS_X, ys, ZN_D / 2, zc - ZN_L / 2, zc + ZN_L / 2),
                 cyl_z(zx + ZS_X, ys, ZN_FL / 2, zc + ZN_L / 2 - ZN_FT, zc + ZN_L / 2)]) - cyl_z(zx + ZS_X, ys, ZS_D / 2 + 0.5, zc - 200, zc + 200)
    x += BLK_H
    zplate = box(x, x + PL, ys - 110, ys + 110, zn + ZP0, zn + ZP1)
    x += PL
    sp = box(xs - SP_W / 2, xs + SP_W / 2, ys - SP_W / 2, ys + SP_W / 2, zn, zn + SP_L)
    cowl = box(xs - 50, xs + 50, ys - 50, ys + 50, zn + SP_L, zn + SP_L + SP_REAR)
    clamp = fuse([box(x, xs + SP_W / 2 + 12, ys - SP_W / 2 - 20, ys + SP_W / 2 + 20, zn + a, zn + a + 60)
                           for a in CLAMP_Z]) - sp
    holder = cyl_z(xs, ys, HOLDER_R, zn - HOLDER_L, zn)
    tool = cyl_z(xs, ys, TOOL_D / 2, tip, zn - HOLDER_L)
    # Y chain's moving end: a bracket from the Y plate to the chain, beside the Z motor
    ytop = ZC0 + COL_D + 5 + 2 * CHAIN_R + CHAIN["Y"]["h"] + 2 * CH_PAD
    ybr = box(c1 - COL_W / 2 - 20, c1 + Y_RISER + BLK_H, ys + 80, ys + 120, ytop + 2, ytop + 17)
    # Z cable chain: beside the Y plate's upper edge (the Y chain's side), looping outwards (+x) from the plate
    zch = box(zx, zx + 2 * CHAIN_R + CHAIN["Z"]["h"] + 2 * CH_PAD, ys + YCH + 5, ys + YCH + 5 + CHAIN["Z"]["w"], ZYP1 - ZCH_LEN, ZYP1)
    # Z chain: fixed end on a tab off the Y plate's lower edge; moving end on a bracket off the Z plate's lower edge
    zfix = box(zx - 20, zx + 40, ys + YCH + 0.5, ys + YCH + 5, Z_CH_F - 25, Z_CH_F + 25)
    carriage = fuse(yblk + [yplate, ynut, anchor, ybr, zmount] + ([zch, zfix] if zchain else []) + zmot + zrisers + zrails + [zbk, zbf, zscrew, zbelt])
    zm_ = zn + ZYP1 - 450 - ZN_MIN                  # the chain's moving end
    zmov = box(x - PL, zx + 2 * CHAIN_R + CHAIN["Z"]["h"] + 2 * CH_PAD, ys + 110 + 0.5, ys + YCH + 5, zm_ - 15, zm_ + 15)
    zaxis = fuse(zblk + [zplate, clamp, znut] + ([zmov] if zchain else []))
    spindle = fuse([sp, cowl, holder])
    return carriage, zaxis, spindle, tool


# ------------------------------------------------------------------ tilt into the world
LIFT_PROBE = Location.about(Axis.X, 90 - TILT)
_low = bed.moved(LIFT_PROBE).bounding_box().min()[2]
H0 = FOOT_H + BASE_H - _low            # lift so the bed's lowest edge sits on the floor frame (R11 checks the gantry clears it)
W = Location.translation(0, 0, H0) * LIFT_PROBE


def world(p):
    return p.moved(W)


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

# ------------------------------------------------------------------ the model, posed for display
POSE = (1200.0, 600.0, TIP_MIN + 100)
g_frame, g_other = gantry(POSE[0])
h_car, h_z, h_sp, h_tool = head(*POSE)
fixed_local = {"bed": bed, "substrate": substrate, "spoilboard": spoil, "rail_bottom": rail_b, "rail_top": rail_t, "x_chain": xchain,
               "rack_bottom": rack_b, "rack_top": rack_t, "atc_rack": atc}
# (the envelopes above are the clash-check solids; the detailed parts are shown, see "detailed parts" below)

# ================================================================== system models
product("Tilted-bed CNC router, 2400 x 1200", task="new_design")
# which parts of the product tree each requirement is about (drives the viewer's highlighting)
OF = {"R1": ["GAN"], "R2": ["YC"], "R3": ["ZA"], "R4": ["BED"], "R5": ["ZA", "SP"], "R6": ["P"], "R7": ["BASE"],
      "R8": ["BED", "BASE"], "R11": ["GAN", "YC", "ZA", "SP"], "R12": ["GAN", "YC", "ZA", "SP"], "R13": ["YC", "ZA", "SP"],
      "R14": ["GAN", "ATC"], "R15": ["BASE"], "R16": ["BASE"], "R17": ["GAN"], "R18": ["YC"], "R19": ["ZA"], "R20": ["YC"],
      "R21": ["YC"], "R22": ["GAN"], "R23": ["ELEC", "SP"], "R24": ["ELEC", "SP"], "R25": ["ELEC"], "R26": ["SP"],
      "R27": ["ELEC"], "R28": ["BED"], "R29": ["GAN", "YC", "ZA", "SP"], "R30": ["SP"], "R31": ["SP"], "R33": ["ELEC"], "R34": ["YC"], "R35": ["GAN"], "R36": ["GAN"],
      "R37": ["GAN"], "R38": ["GAN", "YC"], "R39": ["ZA", "YC"], "R40": ["YC", "ZA"], "R41": ["ELEC"], "R42": ["ELEC"], "R43": ["ELEC"], "R50": ["P"], "R51": ["YC", "ZA", "SP", "GAN"], "R52": ["ATC", "SP"], "R53": ["GAN"], "R54": ["ATC"], "R55": ["GAN", "YC", "ELEC"], "R56": ["BED", "GAN"],
      "R44": ["BED"], "R45": ["BED"], "R46": ["GAN"], "R47": ["GAN", "BED"],
      "R48": ["BED", "GAN"], "R49": ["BED", "GAN", "BASE"],
      "R57": ["P"], "R58": ["P"], "R59": ["P"], "R60": ["P"], "R61": ["P"], "R62": ["P"], "R63": ["ELEC"], "R64": ["P"], "R65": ["P"], "R66": ["P"], "R67": ["ELEC"], "R68": ["P"]}
_require, _cannot = require, cannot_check


def require(id, *a, **k):
    k.setdefault("of", OF.get(id, "P"))
    return _require(id, *a, **k)


def cannot_check(id, *a, **k):
    k.setdefault("of", OF.get(id, "P"))
    return _cannot(id, *a, **k)

N_BED = part("BED", "Bed: steel ladder frame, MDF spoilboard, X rails and racks", material="Steel", shows=["bed", "substrate", "spoilboard", "rail_bottom", "rail_top", "rack_bottom", "rack_top", "x_chain"])
N_GAN = part("GAN", "Gantry: box column with a 2:1 Y counterweight inside, feet on 2 x HGR25 X rails, 2 x NEMA34 rack drive", material="Steel", shows=["gantry_frame", "gantry_drives", "x_motors", "x_motor_top", "y_motor", "counterweight"])
N_YC = part("YC", "Y carriage on 2 x HGR25 rails, SFU2520 screw, 30T:20T belt step-up, NEMA34, 24 V brake", shows=["y_carriage", "z_motor"])
N_ZA = part("ZA", "Z axis: plate on 2 x HGR25, SFU2010 with 40T:20T belt step-up, NEMA34", shows=["z_axis"])
N_SP = part("SP", "Salvaged 9 kW ISO30 ATC spindle, 380 V 3-ph 800 Hz", shows=["spindle", "tool"], bought=True)
N_ATC = part("ATC", "Linear tool rack beside the sheet", shows=["atc_rack"])
N_BASE = part("BASE", "Floor frame with front outriggers, rear posts, levelling feet", material="Steel", shows=["floor_frame", "feet"])
N_ELEC = part("ELEC", "Cabinet: new Delta MS300 2.2 kW 1-ph VFD (space left for a 11 kW 400 V one), salvaged PSUs, drivers, controller, E-stop")
outside("floor", "levelling feet on a concrete slab")
outside("supply", "one 240 V 15 A single-phase socket circuit", keeps="input current <= 15 A", kind="electrical")
outside("sheet", "2400 x 1200 sheet, up to 25 mm, leaning on the bed on pop-up pins", keeps="position while cut")
outside("operator", "loads sheets from the front with the gantry parked at the left end")
outside("air", "compressed air 6 bar for ATC, pop-up pins and spindle taper blow", kind="fluid")
outside("dust", "dust hood on the Z plate to a collector on its own circuit", kind="fluid")
# ---- interface list: datums and the dimensions each pair of parts must agree on (local machine frame, mm)
meets("BED", "SP", "Datums: A = spoilboard face (z 0), B = sheet's bottom edge on the pop-up pins (y 0), C = sheet's left edge (x 0)",
      keeps="all positions below are from A, B, C")
meets("GAN", "BED", f"X rails HGR25 on the bed's front face (z {-SPOIL_T:g}), centres at y {Y_RB:g} and {Y_RT:g} "
      f"({Y_RT - Y_RB:g} apart), {X_BED[1] - X_BED[0]:.0f} long; 2 x HGH25CA per rail at +-45 from the column centre",
      keeps="rail faces coplanar and rails parallel within 0.05 mm over the length")
meets("GAN", "BED", f"Helical racks m1.5 beside each rail (centre y {Y_RB - 62.5:g} and {Y_RT + 62.5:g}); 20T pinion "
      f"(PCD {X_PINION_PCD:g}) on each foot, 3:1 belt (15T:45T HTD 5M) from the X motor; racks on 3 mm shims, teeth facing away from the rails",
      keeps=f"pinion centre {X_PINION_PCD / 2:.2f} from the rack's pitch line (1.5 below its tooth tips); a sprung, pivoting housing takes up backlash")
meets("GAN", "BED", f"X cable chain {XCH['inner'][0]:g} x {XCH['inner'][1]:g} inside, R{CHAIN_R:g}, lying against the bed's back face just under its top edge; "
      "an arm from the top foot reaches over the bed's top edge to its moving end; the fixed run heads left from the fixed end, so the cables leave it straight into the trunking to the right", keeps="chain clear of the bed and the floor frame")
meets("YC", "GAN", f"Y cable chain 25 x 38, R{CHAIN_R:g}, on the column's front face, looping towards the operator; fixed end above the middle, "
      "running down, so the cables from the X chain go straight in; bracket from the Y plate above the carriage's centre")
meets("ZA", "YC", f"Z cable chain 25 x 38, R{CHAIN_R:g}, beside the Y plate's upper edge (the Y chain's side), looping outwards; carries the spindle, fan and air lines to the Z plate")
meets("YC", "GAN", f"Y rails HGR25 on {Y_RISER:g} mm risers on the column's +x face, at z {ZC0 + 40:g} and {ZC0 + COL_D - 40:g} "
      f"({COL_D - 80:g} apart), y {Y_RAIL[0]:g} to {Y_RAIL[1]:g}; Y plate inner face {Y_RISER + BLK_H:g} off the column face",
      keeps="riser tops machined coplanar, rails parallel within 0.03 mm")
meets("YC", "GAN", f"Y screw 25 x 20 lead: axis {YS_X:g} off the column face at z {YS_Z:g}; BK20 at the top, BF20 at the bottom on "
      f"{SUP_SPACER:g} mm spacers; nut flange 68 bolted to a bracket on the Y plate", keeps="screw axis parallel to the Y rails within 0.05 mm")
meets("YC", "GAN", f"Y belt HTD 5M 15 wide over the column's top cap: 30T on the Y motor, 20T on the screw, centres "
      f"{math.hypot((COL_W + 50) + YS_X, (ZC0 + COL_D - 60) - YS_Z):.0f} apart; 24 V brake on the screw's bottom end")
meets("GAN", "YC", f"Counterweight rope, 5 mm 7x19, in the gap {ROPE_X:g} off the column face at z {SHEAVE_Z:g}: anchor on the Y plate, "
      f"over a {SHEAVE_D:g} sheave through a slot in the column wall, 2:1 to a {M_CW:.0f} kg block", keeps="rope plane clear of the Y blocks and BK20")
meets("ZA", "YC", f"Z rails HGR25 on {Z_RISER:g} mm aluminium risers on the Y plate's outer face, at y +-70 (140 apart); "
      f"Z screw 20 x 10 lead {ZS_X:g} off the plate, BK15 at the far end, BF15 near; nut on the Z plate", keeps="rails parallel within 0.03 mm")
meets("ZA", "YC", f"Z belt past the Y plate's end: 40T on the Z motor (behind the plate), 20T on the screw, centres {Y_RISER + BLK_H + PL + ZS_X - (Y_RISER + BLK_H - 50):.0f} apart")
meets("SP", "ZA", f"Spindle axis {SP_W / 2 + 10:g} off the Z plate's outer face ({SP_OFF:g} off the column face); two clamp blocks on the body",
      keeps="spindle axis normal to datum A within 0.05 mm over 100 mm (tram)")
meets("SP", "ELEC", "3-ph 0-230 V 0-800 Hz from the Delta VFD (full flux to 484 Hz); STO to the E-stop chain", kind="electrical")
meets("GAN", "ELEC", "Four 34E1K-120 motors, each on its own driver and 60 V 350 W supply; cables through drag chains", kind="electrical")
meets("BED", "BASE", f"bed's bottom rail beam welded along the floor frame's front rail; {N_LEGS} rear posts (SHS 60x60x4) to the top rail beam's back face",
      keeps=f"rear posts at {(X_BED[1] - X_BED[0] - 80) / (N_LEGS - 1):.0f} mm pitch")
meets("BED", "BED", f"spoilboard MDF {SPOIL_T:g} screwed to a {SUBSTRATE_T:g} mm MDF substrate glued to {n_cross} RHS 50x50x3 cross members at "
      f"{(X_BED[1] - X_BED[0] - CROSS['b']) / (n_cross - 1):.0f} mm pitch between the rail beams", keeps="spoilboard face is datum A; surfaced in place by the machine")
flow(["mains, A", "air, bar", "G-code"], ["cut parts", "chips to the dust hood"])
meets("ATC", "BED", "tool rack's two stands bolted up through the substrate at the bed's right end (2 x M6 each, from behind)")
meets("ATC", "SP", "ISO30 holder flange groove in a 41 mm fork slot; the spindle slides a holder in along +x at the fork's height",
      keeps="cutter tip above the spoilboard and clear of a 25 mm sheet while sliding (R54)")
meets("ELEC", "BASE", "cabinet stand welded to stubs continuing the floor frame's rails past the bed's right end")
meets("ELEC", "BED", "X chain's fixed end on the tray; trunking on the tray's rear shelf to the stand; X home flags on the substrate; "
      "pop-up pin cylinders and their hose", kind="electrical")
meets("ELEC", "YC", "Z motor, Z home sensor; spindle cables and hoses pass from the Z chain to the Y chain over the carriage's upper edge",
      kind="electrical")
meets("ELEC", "SP", "tool release (8 mm) and taper blow (6 mm) air through the Z, Y and X chains from the valve manifold", kind="fluid")
assume(f"Bed tilt is {TILT:g} deg from vertical", why="answer to a question; the sketch shows 20 deg (110 deg)")
assume(f"The 300 on the sketch is the Z travel", why="it is labelled '(Z-travel) 300'")
assume(f"Stock up to {STOCK_T:g} mm, cutter up to {TOOL_D:g} mm, workholding no taller than {CLAMP_H:g} mm", why="not given")
assume(f"One 60 V 350 W supply per driver", why="user confirmed: four supplies, one per motor").confirmed = True
assume("Motor torque follows the published 48 V DM860T pull-out curve", why="the 60 V supplies and the closed-loop drivers differ from the test")
assume("Spindle is the 380 V version: 17.8 A rated, 29 kg, no-load current 35 % of rated", why="user's correction; figures from the same-body GDZ143x133-9")
assume("On a future 3-phase supply the largest cut is a 25 mm cutter, 25 mm deep, at 10 m/min and 12 000 rpm", why="the steppers' speed, not the spindle, caps it")
assume("Dust collector and compressor run on other circuits", why="the 15 A circuit cannot also carry them")
assume("Rapids X 15, Y 10, Z 5 m/min; 1 m/s^2; 300 N cutting force at 6 m/min", why="hobby router targets, not given")
assume("The X and Z cable chains may stand above 1800 mm; the ceiling is 2400 mm",
       why="user: the 1800 mm limit is for assembly and operating ergonomics; Y can be jogged down to work on the Z chain. Ceiling not given")
assume(f"The head may overhang the floor frame while cutting; parked at the left end it sits in the room's corner",
       why="user accepted the 1342 mm cutting envelope")
assume("Sheet is located on retractable (pop-up) pins along its bottom edge, so the cutter can profile that edge", why="a fixed ledge would be cut")


# ------------------------------------------------------------------ R: the sheet and travels
require("R1", "X travel shall put the tool centre past both 2400 mm sheet edges by tool radius + 3 mm",
        min(X_WORK[0] - X_TRAVEL[0], X_TRAVEL[1] - X_WORK[1]) if X_TRAVEL[0] <= X_WORK[0] else -1, ">=", 0, "mm")
require("R2", "Y travel shall put the tool centre past both 1200 mm sheet edges by tool radius + 3 mm",
        min(Y_WORK[0] - (Y_RAIL[0] + YCH), (Y_RAIL[1] - YCH) - Y_WORK[1]), ">=", 0, "mm")
require("R3", "Z travel shall be at least 300 mm", Z_TRAVEL, ">=", Z_TRAVEL_REQ, "mm")
n_bed = wpt(0, 0, 100)
o_bed = wpt(0, 0, 0)
tilt_meas = math.degrees(math.atan2(n_bed[2] - o_bed[2], o_bed[1] - n_bed[1]))   # normal's angle above horizontal
require("R4", "The bed shall lean back 10 deg from vertical", tilt_meas, "==", TILT, "deg", tolerance=0.01)
require("R5", "The tool shall reach 2 mm into the spoilboard", ZN_MIN - TIP_TO_NOSE, "<=", TIP_MIN, "mm")

# ------------------------------------------------------------------ R: envelope, at the extreme poses
poses = [(xs, ys, tip) for xs in (X_TRAVEL[0], X_WORK[1]) for ys in Y_WORK for tip in (TIP_MIN, ZN_MAX - TIP_TO_NOSE)]
class _BB:
    """The bounding box of several parts, without fusing them."""
    def __init__(self, parts):
        bs = [p.bounding_box() for p in parts]
        self._min = tuple(min(b.min()[i] for b in bs) for i in range(3))
        self._max = tuple(max(b.max()[i] for b in bs) for i in range(3))

    def min(self):
        return self._min

    def max(self):
        return self._max


fixed_parts_w = [bed_w, world(substrate), world(spoil), world(rail_b), world(rail_t), world(rack_b), world(rack_t), world(atc), world(xchain), base, feet]
zmax, ymin, ymax = -1e9, 1e9, -1e9
for xs, ys, tip in poses:
    a = fuse(list(gantry(xs, with_arm=False)) + list(head(xs, ys, tip, zchain=False))).moved(W)   # (the chains are measured below)
    b = a.bounding_box()
    zmax = max(zmax, b.max()[2]); ymin = min(ymin, b.min()[1]); ymax = max(ymax, b.max()[1])
fb = _BB(fixed_parts_w)
fb_h = _BB([p for p in fixed_parts_w if p is not fixed_parts_w[8]])          # without the X chain
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

# ------------------------------------------------------------------ R: fits and clearances
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

# ------------------------------------------------------------------ masses, CG, stability
# ---- detailed parts: built here so the masses below come from them
REF = (0.0, 0.0, TIP_MIN)      # the pose the moving groups are drawn at; the viewer moves them from here
_G = globals()
floor_items = []
_fr = front_lo[1]
_feet = [(_x, _y) for _x in xs_legs for _y in (Y_FRONT + 40, Y_REAR - 40)]
def _foot_holes(p):
    return D.drill(p, "-z", [(fx, fy, ZB0) for fx, fy in _feet], 9.0) if True else p
_rail = D.rhs("x", X_BED[0], X_BED[1], Y_REAR - 80, Y_REAR, ZB0, ZB1, 4.0)
floor_items.append(D.item("floor_frame.front_rail", D.rhs("x", X_BED[0], X_BED[1], _fr + 10, _fr + 110, ZB0, ZB1, 4.0), "steel", "made", "RHS 100x50x4 on edge", "world"))
floor_items.append(D.item("floor_frame.rear_rail", _foot_holes(_rail), "steel", "made", "RHS 100x50x4 on edge, 17 mm holes over the feet", "world"))
D.weld("floor_frame.bed_bottom_beam", "B06", "bed.rail_beam_bottom", "floor_frame.front_rail", "fillet both sides of the contact line")
for _i, _x in enumerate(xs_legs):
    floor_items.append(D.item(f"floor_frame.cross_{_i}", D.rhs("y", _x - 40, _x + 40, _fr + 110.5, Y_REAR - 80.5, ZB0, ZB1, 4.0), "steel", "made",
                              "RHS 100x50x4 between the rails", "world"))
    D.weld(f"floor_frame.cross_{_i}_front", "F02", f"floor_frame.cross_{_i}", "floor_frame.front_rail", "fillet all round")
    D.weld(f"floor_frame.cross_{_i}_rear", "F02", f"floor_frame.cross_{_i}", "floor_frame.rear_rail", "fillet all round")
    _out = D.rhs("y", _x - 39, _x + 39, Y_FRONT, _fr + 9.5, ZB0 + 0.5, ZB0 + OUTRIG_H, 4.0)
    floor_items.append(D.item(f"floor_frame.outrigger_{_i}", _foot_holes(_out), "steel", "made",
                              "RHS 100x50x4 laid flat, welded to the front rail; 17 mm hole over the foot", "world"))
    D.weld(f"floor_frame.outrigger_{_i}", "F02", f"floor_frame.outrigger_{_i}", "floor_frame.front_rail", "fillet all round")
    _a = (_x, Y_REAR - 40, ZB1 - 20)
    _b = (_x, back_hi[1], back_hi[2])
    _L = math.dist(_a, _b)
    _ang = math.degrees(math.atan2(_b[2] - _a[2], _b[1] - _a[1]))
    _post = D.rhs("y", -29, 29, -_L / 2 - 60, _L / 2 + 60, -29, 29, 4.0).moved(Location.about(Axis.X, _ang)).moved(Location.translation(_x, (_a[1] + _b[1]) / 2, (_a[2] + _b[2]) / 2))
    # ends cut to fit: on the rear rail's top face, and on the top beam's back face
    _post = _post - box(_x - 100, _x + 100, Y_REAR - 400, Y_REAR + 400, ZB1 - 400, ZB1)
    _post = _post - world(box(X_BED[0] - 10, X_BED[1] + 10, Y_RT - 400, Y_RT + 400, BED_BACK, BED_BACK + 500))
    floor_items.append(D.item(f"floor_frame.rear_post_{_i}", _post, "steel", "made", "SHS 60x60x4 (58 modelled), ends cut to fit, welded", "world"))
    D.weld(f"floor_frame.rear_post_{_i}_rail", "F04", f"floor_frame.rear_post_{_i}", "floor_frame.rear_rail", "fillet all round")
    D.weld(f"floor_frame.rear_post_{_i}_bed", "B06", f"floor_frame.rear_post_{_i}", "bed.rail_beam_top", "fillet all round")
    for _k, _y in enumerate((Y_FRONT + 40, Y_REAR - 40)):
        _host = f"floor_frame.outrigger_{_i}" if _k == 0 else "floor_frame.rear_rail"
        _top = FOOT_H + (0.5 if _k == 0 else 0.0)
        floor_items.append(D.item(f"feet.foot_{_i}_{_k}", D.levelling_foot(_x, _y, _top, FOOT_H), "steel", "bought", "M16 levelling foot, 80 pad, lock nut", "world"))
        floor_items.append(D.item(f"floor_frame.foot_nut_{_i}_{_k}", D.foot_nut(_x, _y, _top), "steel", "bought", "M16 nut, welded under the rail", "world"))
        D.weld(f"floor_frame.foot_nut_{_i}_{_k}", "F01", f"floor_frame.foot_nut_{_i}_{_k}", _host, "tack 3 sides")
        D.screw(f"feet.foot_{_i}_{_k}", "F01", [f"floor_frame.foot_nut_{_i}_{_k}"], "STUD", 16, [(_x, _y, 16.0)], (0, 0, 1), grip=_top - 13 - 16,
                L=_top + 4.0 - 16.0, into="nut")

D.JOINTS.clear(); D.WELDS.clear()
items = D.bed_assembly(_G) + D.atc_assembly(_G) + D.gantry_assembly(_G, REF[0]) + D.head_assembly(_G, *REF) \
    + D.chains(_G, REF) + D.counterweight_assembly(_G, REF[0], REF[1]) + floor_items
items += EL.cabinet(_G) + EL.front_estop(_G) + EL.popup_pins(_G) + EL.ducts(_G) + EL.world_ducts(_G)
items += EL.machine_side(_G, items)
ROPE_PTS = D.rope_path(_G, REF[0], REF[1])
items.append(D.item("gantry_frame.rope", D.rope_part(ROPE_PTS), "steel", "bought",
                    "5 mm 7x19 galvanised wire rope: swaged stop at the carriage anchor, swaged eye over the dead-end bolt", "x"))
for _it in items:
    if _it["name"].startswith("atc."):
        _it["name"] = "atc_rack." + _it["name"][4:]
print("detailed items", len(items))
COLOURS = {"steel": (0.45, 0.48, 0.53), "6061": (0.75, 0.77, 0.8), "MDF": (0.72, 0.62, 0.45), "UHMW": (0.92, 0.92, 0.88),
           "electrical": (0.22, 0.3, 0.42), "plastic": (0.6, 0.62, 0.6),
           "rubber": (0.12, 0.12, 0.12), "nylon": (0.18, 0.4, 0.3), "carbide": (0.85, 0.85, 0.85)}
for _it in items:
    _c = (0.25, 0.27, 0.3) if _it["kind"] == "bought" and _it["mat"] == "steel" else COLOURS[_it["mat"]]
    if _it["name"].startswith("spindle."):
        _c = (0.55, 0.15, 0.13)
    if _it["name"] == "sheet":
        _c = (0.85, 0.7, 0.45)
    _it["colour"] = _c
    show(_it["part"] if _it["group"] == "world" else world(_it["part"]), _it["name"], colour=_c, group=_it["name"].split(".")[0])

# ---- masses from the detail
DENS_ALL = dict(D.DENS, rubber=1.2, nylon=1.1, carbide=14.5, electrical=0.9, plastic=1.3)
CHAIN_KGM = {"x": 0.9, "y": 0.7, "z": 0.7}


def item_kg(it):
    if it["name"] == "spindle.body":
        return M_SPINDLE_KG
    if it["name"] in CHAIN_SPECS:
        return CHAIN_KGM[it["name"].split(".")[-1][0]] * CHAIN_SPECS[it["name"]]["L"] / 1000
    return it["part"].volume() * DENS_ALL[it["mat"]] * 1e-6


for _it in items:
    _it["kg"] = item_kg(_it)
kg_group = {}
for _it in items:
    kg_group[_it["group"]] = kg_group.get(_it["group"], 0.0) + _it["kg"]
kg_spindle = sum(it["kg"] for it in items if it["name"].startswith(("spindle.", "tool")))
kg_z = kg_group["xyz"] - kg_spindle
kg_y = kg_group["xy"] + M_KG                                  # with the Z motor
kg_gantry = kg_group["x"] + 3 * M_KG                          # with the X and Y motors
print(f"detail masses: Y carriage {kg_y:.1f}, Z axis {kg_z:.1f}, spindle {kg_spindle:.1f}, gantry {kg_gantry:.1f}, cw {kg_group['cw']:.1f}")

# ---- steel and board, member by member: the cut list, and the masses below
def rhs_kgm(b, d, t):
    return (2 * t * (b + d) - 4 * t * t) * 7.85e-3


L_bed = X_BED[1] - X_BED[0]
L_col = Y_RT - Y_RB + 80
L_cross = (Y_RT - 20) - (Y_RB + 20)
post_len = [math.dist((0, Y_REAR - 40, ZB1 - 20), (0, back_hi[1], back_hi[2]))] * N_LEGS
MEMBERS = [  # (assembly, member, section, length mm, qty, kg/m)
    ("bed", "rail beam", "RHS 100x80x5", L_bed, 2, rhs_kgm(100, 80, 5)),
    ("bed", "cross member", "RHS 50x50x3", L_cross, n_cross, rhs_kgm(50, 50, 3)),
    ("bed", "substrate", f"MDF {SUBSTRATE_T:g}", L_bed, 1, (L_cross / 1000) * SUBSTRATE_T / 1000 * 750),
    ("bed", "spoilboard", f"MDF {SPOIL_T:g}", SHEET_L + 40, 1, (SHEET_W + 60) / 1000 * SPOIL_T / 1000 * 750),
    ("column", "web plate (+x and -x faces)", f"plate {COL_D:g}x{COL_T:g}", L_col, 2, COL_D * COL_T * 7.85e-3),
    ("column", "flange plate (front and back)", f"plate {COL_W - 2 * COL_T:g}x{COL_T:g}", L_col, 2, (COL_W - 2 * COL_T) * COL_T * 7.85e-3),
    ("column", "end cap", f"plate {COL_W:g}x{COL_D:g}x10", COL_W, 2, COL_D * 10 * 7.85e-3),
    ("column", "Y rail riser", f"flat {Y_RISER:g}x25", Y_RAIL[1] - Y_RAIL[0], 2, Y_RISER * 25 * 7.85e-3),
    ("column", "foot", f"plate {COL_W:g}x80x{ZC0 - BLK_Z:g} (fabricated)", 80, 2, COL_W * (ZC0 - BLK_Z) * 7.85e-3 * 0.4),
    ("floor frame", "front rail", "RHS 100x50x4", L_bed, 1, rhs_kgm(100, 50, 4)),
    ("floor frame", "rear rail", "RHS 100x50x4", L_bed, 1, rhs_kgm(100, 50, 4)),
    ("floor frame", "cross member", "RHS 100x50x4", Y_REAR - front_lo[1] - 10, N_LEGS, rhs_kgm(100, 50, 4)),
    ("floor frame", "outrigger", "RHS 100x50x4 laid flat", front_lo[1] + 30 - Y_FRONT, N_LEGS, rhs_kgm(100, 50, 4)),
    ("floor frame", "rear post", "SHS 60x60x4", post_len[0], N_LEGS, rhs_kgm(60, 60, 4)),
]
mass_of = lambda asm: sum(L / 1000 * q * kgm for a, _, _, L, q, kgm in MEMBERS if a == asm)
with open("cut_list.csv", "w") as f:
    f.write("assembly,member,section,length_mm,qty,kg_each\n")
    for a, m, sec, L, q, kgm in MEMBERS:
        f.write(f"{a},{m},{sec},{L:.0f},{q},{L / 1000 * kgm:.1f}\n")

def kg_of(prefix, minus=()):
    return sum(it["kg"] for it in items if it["name"].startswith(prefix) and not it["name"].startswith(tuple(minus)))


masses = {   # kg: frames, bed and drives from the detailed parts; the head and counterweight at their allowances (R51, R53)
    "bed": (bed_w, kg_of("bed.", ("bed.spoilboard",))), "spoil": (world(spoil), kg_of("bed.spoilboard")),
    "stock": (world(stock), 2.4 * 1.2 * 0.025 * 750), "atc": (world(atc), kg_of("atc_rack.")),
    "base": (base, kg_of("floor_frame.") + kg_of("feet.")), "gantry_frame": (world(g_frame), kg_of("gantry_frame.")),
    "gantry_drives": (world(g_other), kg_of("gantry_drives.") + 3 * M_KG), "y_carriage": (world(h_car), M_YC), "z_axis": (world(h_z), M_ZA),
    "spindle": (world(h_sp), M_SP), "counterweight": (world(counterweight(*POSE[:2])), M_CW),
}
m_gantry = sum(masses[k][1] for k in ("gantry_frame", "gantry_drives", "y_carriage", "z_axis", "spindle", "counterweight"))
m_y = M_HEAD
m_z = masses["z_axis"][1] + masses["spindle"][1]
m_total = sum(m for _, m in masses.values())
for node, keys in ((N_BED, ("bed", "spoil")), (N_GAN, ("gantry_frame", "gantry_drives", "counterweight")),
                   (N_YC, ("y_carriage",)), (N_ZA, ("z_axis",)), (N_SP, ("spindle",)), (N_BASE, ("base",))):
    node.mass_kg = round(sum(masses[k][1] for k in keys), 1)
N_ATC.mass_kg, N_ELEC.mass_kg = round(kg_of("atc_rack."), 1), 25.0     # cabinet assumed
# worst stability: head plunged at the bottom (most forward), and retracted at the top
feet_y = (Y_FRONT, Y_REAR)
worst = 1e9
for ys, tip in ((Y_WORK[0], ZN_MAX - TIP_TO_NOSE), (Y_WORK[1], TIP_MIN)):
    car, za, sp_, _ = head(POSE[0], ys, tip)
    mm = dict(masses, y_carriage=(world(car), masses["y_carriage"][1]), z_axis=(world(za), masses["z_axis"][1]),
              spindle=(world(sp_), masses["spindle"][1]), counterweight=(world(counterweight(POSE[0], ys)), M_CW))
    cg_y = sum(p.centre()[1] * m for p, m in mm.values()) / m_total
    worst = min(worst, cg_y - feet_y[0], feet_y[1] - cg_y)
require("R15", "The centre of mass shall stay at least 150 mm inside the feet front-to-back in every pose",
        worst, ">=", 150, "mm", evidence={"tool": "sum of part masses x golf part centres", "leaves_out": "masses are estimated from section sizes; dynamic loads"})
# a person pushing 300 N on the top of the head towards the bed, or pulling it towards them
cg_y = sum(p.centre()[1] * m for p, m in masses.values()) / m_total
tip_force = (m_total * 9.81 * (cg_y - feet_y[0])) / (zmax)       # pull at the top that tips it forward
require("R16", "It shall not tip forward with a 300 N pull at its top", tip_force, ">=", 300, "N",
        evidence={"tool": "moments about the front feet", "leaves_out": "floor anchoring, which would add margin"})


# ------------------------------------------------------------------ the motor model
v_in = (MOTOR_STEP & MOTOR).volume()
require("R32", "The motor envelope used for clash checks shall contain the 34E1K-120 STEP model", v_in / MOTOR_STEP.volume(), ">=", 0.999, "",
        of=["GAN", "YC"])

# ------------------------------------------------------------------ drives
# Published pull-out curve of the 34E1K-120 (parts/stepper-speed-torque-curve.png): DM860T driver, 48 V DC,
# 5.7 A peak. Used as-is: the 60 V supplies give more torque at speed, so this is on the safe side.
TORQUE_CURVE = [(0, 8.53), (100, 8.53), (200, 6.73), (300, 4.92), (400, 3.61), (500, 2.78), (600, 2.08), (700, 1.76),
                (800, 1.41), (900, 1.24), (1000, 1.02), (1100, 0.94), (1200, 0.70), (1300, 0.64), (1400, 0.58), (1500, 0.54)]


def stepper_torque(rpm):
    """Pull-out torque at a speed, from the published curve; above 1500 rpm, at its last power (85 W)."""
    for (a, ta), (b, tb) in zip(TORQUE_CURVE, TORQUE_CURVE[1:]):
        if a <= rpm <= b:
            return ta + (tb - ta) * (rpm - a) / (b - a)
    return 0.54 * 1500 / rpm


J_ROTOR = M_J      # kg m^2, from the datasheet
G = 9.81


def axis_margin(name, mass, f_gravity, lead_mm=None, pcd=None, ratio=1.0, motors=1, j_screw=0.0, eff=0.9):
    """Torque margin of one axis: available torque / needed, worst of rapid and cutting feed."""
    worst, p_peak = 1e9, 0.0
    for v, f_extra in ((V_RAPID[name], 0.0), (F_FEED, F_CUT), (F_FEED_3PH, F_CUT_3PH)):
        vs = v / 60.0                                     # m/s
        if lead_mm:
            rev_s = vs / (lead_mm / 1000.0)
            r_eff = lead_mm / 1000.0 / (2 * math.pi)       # m per rad
        else:
            rev_s = vs / (math.pi * pcd / 1000.0)
            r_eff = pcd / 2000.0
        rpm = rev_s * ratio * 60
        force = mass * ACC[name] + f_gravity + f_extra + 0.01 * mass * G
        t_load = force * r_eff / (ratio * eff) / motors
        alpha = ACC[name] / r_eff * ratio                 # motor rad/s^2
        t_inert = (J_ROTOR + j_screw / ratio ** 2) * alpha
        worst = min(worst, stepper_torque(rpm) / (t_load + t_inert))
        p_peak = max(p_peak, (t_load + t_inert) * rpm * 2 * math.pi / 60)   # W at the shaft, per motor
    return worst, rpm, p_peak


def screw_j(d_mm, L_mm):
    return 7850 * math.pi * (d_mm / 1000) ** 4 * (L_mm / 1000) / 32


ev = {"tool": "F = m a + gravity + cut + 1 % friction; T = F r / (ratio eff); 34E1K-120 published pull-out curve at 48 V",
      "leaves_out": "the extra torque of the 60 V supplies, resonance, belt compliance"}
mx, rpm_x, pk_x = axis_margin("X", m_gantry, 0.0, pcd=X_PINION_PCD, ratio=X_RATIO, motors=2)
y_len = Y_RAIL[1] - Y_RAIL[0] + 100
# the counterweight moves at half speed: it adds M_CW / REEVE^2 of inertia and takes M_CW / REEVE of the weight
my, rpm_y, pk_y = axis_margin("Y", m_y + M_CW / REEVE ** 2, (m_y - M_CW / REEVE) * G * math.cos(math.radians(TILT)), lead_mm=Y_LEAD, ratio=Y_RATIO,
                        j_screw=screw_j(25, y_len))
mz, rpm_z, pk_z = axis_margin("Z", m_z, m_z * G * math.sin(math.radians(TILT)), lead_mm=Z_LEAD, ratio=Z_RATIO,
                        j_screw=screw_j(20, ZYP1 - ZYP0))
require("R17", "X drive torque margin at rapid, cutting feed, and the largest 3-phase cut", mx, ">=", 1.5, "", evidence=ev)
require("R18", "Y drive torque margin, lifting the head up the slope", my, ">=", 1.5, "", evidence=ev)
require("R19", "Z drive torque margin", mz, ">=", 1.5, "", evidence=ev)
# Y ballscrew critical speed, fixed-supported, root dia 21.4 mm
n_crit = 15.1 * 21.4 / y_len ** 2 * 1e7
rpm_y_rapid = V_RAPID["Y"] * 1000 / Y_LEAD                      # screw rpm at the Y rapid
require("R20", "Y screw critical speed shall be at least 1.25 x its rapid speed", n_crit / rpm_y_rapid, ">=", 1.25, "",
        evidence={"tool": "n = 15.1 d_r / L^2 x 1e7 (fixed-supported)", "leaves_out": "whip from misalignment"})
f_back = (m_y - M_CW / REEVE) * G * math.cos(math.radians(TILT))
t_back = f_back * (Y_LEAD / 1000) * 0.9 / (2 * math.pi)
require("R21", "With power off the head shall not run down the slope: brake torque >= 2 x back-driving torque",
        BRAKE_T / t_back, ">=", 2.0, "", evidence={"tool": "T = F lead eff / 2 pi", "leaves_out": "brake wear"})
t_back_full = m_y * G * math.cos(math.radians(TILT)) * (Y_LEAD / 1000) * 0.9 / (2 * math.pi)
require("R34", "If the counterweight rope breaks, the brake shall still hold the whole head: brake torque >= 1.25 x its back-driving torque",
        BRAKE_T / t_back_full, ">=", 1.25, "", evidence={"tool": "T = F lead eff / 2 pi", "leaves_out": "the shock of the drop"})
rope_t = M_CW * G * math.cos(math.radians(TILT)) / REEVE * 1.3       # 30 % for the block's acceleration and sheave friction
require("R35", "Counterweight rope: breaking load >= 5 x its working tension", ROPE_MBL / rope_t, ">=", 5.0, "",
        evidence={"tool": "T = m_cw g cos(tilt) / reeving x 1.3", "leaves_out": "fatigue at the sheaves"})
require("R36", "Sheaves shall be at least 20 rope diameters across, for rope life", SHEAVE_D / ROPE_D, ">=", 20.0, "")
for ys in (Y_WORK[0], (Y_WORK[0] + Y_WORK[1]) / 2, Y_WORK[1]):
    require("R37", "The counterweight shall stay inside the column, clear of its walls, caps and the top sheave, over all Y travel",
            _shared(counterweight(0.0, ys), gantry(0.0)[0]), "<=", 0, "mm^3", case=f"head at y {ys:g}")
# rope from its anchor to the sheave, against everything else
for ys in (Y_WORK[0], (Y_WORK[0] + Y_WORK[1]) / 2, Y_WORK[1]):
    # up to where it enters the sheave's flanges (the groove is inside the flange envelope modelled)
    y_in = SHEAVE_Y - math.sqrt((SHEAVE_D / 2 + 5) ** 2 - (SHEAVE_D / 2 - ROPE_D / 2) ** 2)
    rope = cyl_y(-SP_OFF + ROPE_X, SHEAVE_Z, ROPE_D / 2, ys + 20, y_in)
    g_f, g_o = gantry(0.0)
    car, za, spn, _ = head(0.0, ys, TIP_MIN)
    for name, other in (("gantry frame", g_f), ("gantry drives", g_o), ("Y carriage", car), ("Z axis", za)):
        require("R38", "The counterweight rope shall run clear of every part from its anchor to the sheave, over all Y travel",
                _shared(rope, other), "<=", 0, "mm^3", case=f"head at y {ys:g}: {name}")
# Z axis (with its nut) against the Y carriage (screw, BK15, BF15, Z motor, belt) over the whole Z stroke
car, za, spn, _ = head(0.0, POSE[1], TIP_MIN)
clear_travel("R39", za + spn, {"Y carriage": car}, place=lambda t: Location.translation(0, 0, t * Z_TRAVEL), tag="Z stroke",
             text="The Z axis and spindle shall clear the Y carriage, Z screw and its supports over the whole Z stroke", steps=7)
# nut flanges to the faces they pass
yfl = (YS_X - YN_FL / 2, (Y_RISER + BLK_H) - (YS_X + YN_FL / 2))
zfl = (ZS_X - ZN_FL / 2, (Z_RISER + BLK_H) - (ZS_X + ZN_FL / 2))
for name, v in (("Y flange to column face", yfl[0]), ("Y flange to Y plate", yfl[1]), ("Z flange to Y plate", zfl[0]), ("Z flange to Z plate", zfl[1])):
    require("R40", "Each ball-nut flange shall clear the faces either side of it by at least 3 mm", v, ">=", NUT_CLEAR, "mm", case=name)

# cable chains: the loop stays in its zone and both runs stay positive over the whole travel
for _nm, _sp in CHAIN_SPECS.items():
    for _md in (_sp["m_min"], (_sp["m_min"] + _sp["m_max"]) / 2, _sp["m_max"]):      # along the chain's run direction
        _m = _sp["sg"] * _md
        _a, _b = D.chain_state(_sp, _m)
        _run_b = _b - _md
        _hi = _sp["zone"][1] - (_b + _sp["R"] + _sp["h"] / 2)
        _lo = min(_sp["f"], _md) - 0.4 * _sp["pitch"] - _sp["zone"][0]
        require("R55", "Each cable chain shall keep both runs and its loop inside its zone over the whole travel (least margin)",
                min(_a, _run_b, _hi, _lo), ">=", 0, "mm", case=f"{_nm.split('.')[-1]}, moving end at {_m:.0f}")
# cable chains
require("R41", "Cable chains shall bend no tighter than 7.5 x the largest continuous-flex cable", CHAIN_R / CABLE_D_MAX, ">=", 7.5, "",
        evidence={"tool": "chainflex rule: R >= 7.5 d", "leaves_out": "the cable maker's own figure"})
for ax, cables in CABLES.items():
    fill = sum(math.pi / 4 * d * d for d in cables) / (CHAIN[ax]["inner"][0] * CHAIN[ax]["inner"][1])
    require("R42", "Each cable chain shall be no more than 60 % full", fill * 100, "<=", 60, "", case=f"{ax} chain",
            evidence={"tool": "cable areas / inner section", "leaves_out": "separators"})
    require("R43", "Each cable chain's inner height shall take its largest cable", CHAIN[ax]["inner"][0] - max(cables), ">=", 0, "mm",
            case=f"{ax} chain")

# each driver's supply: shaft power / 80 % + copper loss of both phases at rated current
cu = 2 * M_AMPS ** 2 * 0.72
for ax, pk in (("X", pk_x), ("Y", pk_y), ("Z", pk_z)):
    require("R33", "Each motor's peak draw shall be within its 60 V 350 W supply", pk / 0.8 + cu, "<=", PSU_W, "W", case=f"{ax} motor",
            evidence={"tool": "P = T w / 0.8 + 2 I^2 R", "leaves_out": "supply sharing, if drivers share a supply"})

# column deflection under the cutting force, simply supported between the X rails
E = 210000.0
L = Y_RT - Y_RB
I_z = (COL_W * COL_D ** 3 - (COL_W - 2 * COL_T) * (COL_D - 2 * COL_T) ** 3) / 12
I_x = (COL_D * COL_W ** 3 - (COL_D - 2 * COL_T) * (COL_W - 2 * COL_T) ** 3) / 12
d_col = max(F_CUT, F_CUT_3PH) * L ** 3 / (48 * E * min(I_z, I_x))
# plus the column twisting: feed force along x at the spindle axis, SP_OFF+COL_W/2 from the column's centre... carried by both feet
require("R22", "The column shall deflect no more than 0.02 mm under the largest cutting force (now or on 3-phase) at mid-height", d_col, "<=", 0.02, "mm",
        evidence={"tool": "d = F L^3 / 48 E I, column a box beam", "leaves_out": "rail and block compliance, plate bending, torsion"})


# ---- structure: the stiffness budget at the tool
G_STEEL = 81000.0
F_N = (m_gantry * G * math.sin(math.radians(TILT)) + max(F_CUT, F_CUT_3PH)) / 2     # N into each X rail, normal to the bed
# top rail beam between rear posts (the bottom one sits on the floor frame's front rail): simply supported span
span = (X_BED[1] - X_BED[0] - 80) / (N_LEGS - 1)
I_beam = (RAIL_BEAM["b"] * RAIL_BEAM["d"] ** 3 - (RAIL_BEAM["b"] - 2 * RAIL_BEAM["t"]) * (RAIL_BEAM["d"] - 2 * RAIL_BEAM["t"]) ** 3) / 12
d_beam = F_N * span ** 3 / (48 * E * I_beam)
require("R44", "The top rail beam shall deflect no more than 0.02 mm between rear posts under the gantry's normal load and the cut",
        d_beam, "<=", 0.02, "mm", evidence={"tool": "d = F L^3 / 48 E I between posts", "leaves_out": "post and floor-frame compliance"})
# spoilboard on the substrate, between cross members: a 100 mm wide strip, simply supported
pitch = (X_BED[1] - X_BED[0] - CROSS["b"]) / (n_cross - 1) - CROSS["b"]
I_mdf = 100 * (SPOIL_T + SUBSTRATE_T) ** 3 / 12
d_spoil = 100.0 * pitch ** 3 / (48 * 3000 * I_mdf)
require("R45", "The spoilboard shall deflect no more than 0.05 mm under a 100 N plunge force between cross members",
        d_spoil, "<=", 0.05, "mm", evidence={"tool": "100 mm strip of 50 mm MDF (E 3 GPa), d = F L^3 / 48 E I", "leaves_out": "load spreading, which helps"})
# column torsion: a force normal to the bed at the tool, offset in x from the column's centre, fixed at both feet
A_enc = (COL_W - COL_T) * (COL_D - COL_T)
J_col = 4 * A_enc ** 2 * COL_T / (2 * ((COL_W - COL_T) + (COL_D - COL_T)))
arm_t = SP_OFF + COL_W / 2
theta = max(F_CUT, F_CUT_3PH) * arm_t * L / (4 * G_STEEL * J_col)
d_twist = theta * arm_t
require("R46", "Column twist shall move the tool no more than 0.01 mm under the cutting force", d_twist, "<=", 0.01, "mm",
        evidence={"tool": "closed box: J = 4 A^2 t / perimeter; theta = T L / 4 G J", "leaves_out": "warping of the end caps"})
# the budget: column bending + twist + the rail beam (half, shared by two rails) + rail and block compliance
K_BLOCK = 500.0       # N/um per HGH25CA at ZA preload, normal direction (catalogue order of magnitude)
d_blocks = max(F_CUT, F_CUT_3PH) / (4 * K_BLOCK) / 1000 * 4            # X, Y and Z block sets in series, 2 blocks sharing
d_total = d_col + d_twist + d_beam / 2 + d_blocks
require("R47", "Tool deflection from the structure under the cutting force shall be no more than 0.05 mm", d_total, "<=", 0.05, "mm",
        evidence={"tool": "sum of R22, R44/2, R46 and the bearing blocks in series", "leaves_out": "Y and Z plate bending, belts, screws"})
cannot_check("R48", "Rail mounting faces: each pair coplanar and parallel within 0.05 mm over its length, after welding (machined lands, "
             "or epoxy-levelled strips)", why="a fabrication and inspection step: check with a straightedge and dial gauge")
cannot_check("R49", "Weldments stress-relieved or welded in a balanced sequence before the rail lands are finished", why="a fabrication process")

# ------------------------------------------------------------------ power
# Salvaged spindle: 380 V version, 9 kW, 4-pole, 800 Hz. Rated current from the same-body GDZ143x133-9 at 380 V.
SP_RATED_A, SP_V, SP_F = 17.8, 380.0, 800.0
I_MAG_RATED = 0.35 * SP_RATED_A                     # no-load current at full flux (assumed)
# New VFD: Delta MS300 high-speed VFD11AMS21ANSHA, 1-ph 230 V in, 11 A heavy duty out, 0-1500 Hz, STO built in.
# Its output can be no higher than its 230-240 V input, so the 380 V winding is run at full flux up to
# F_BASE = 800 x 230/380 = 484 Hz (14 500 rpm) and at constant 230 V above that (field weakening).
VFD = {"name": "Delta VFD11AMS21ANSHA", "i_out": 11.0, "f_max": 1500.0, "v_max": 230.0}
F_BASE = SP_F * VFD["v_max"] / SP_V
AUX_W = 4 * 75 + 150 + 60 + 20          # steppers average, controller+PC, spindle fan, brake/valves
AUX_PF = 0.9
VFD_PF, VFD_EFF, MOTOR_EFF = 0.70, 0.96, 0.80   # 1-ph rectifier with a line choke; spindle at ~15 % load
I_CONT = 0.8 * SUPPLY_A                  # continuous design limit
i_aux = AUX_W / (SUPPLY_V * AUX_PF)
P_VFD_LIMIT = 1550.0                     # W, VFD input power cap set in its parameters
p_vfd_in = P_VFD_LIMIT
p_shaft = p_vfd_in * VFD_EFF * MOTOR_EFF
require("R23", "The VFD shall run the spindle to 24 000 rpm (800 Hz)", VFD["f_max"], ">=", SP_F, "Hz")
ev_i = {"tool": "V/f: V = min(230, 380 f/800); I_mag scales with flux; I = sqrt(I_mag^2 + (P/eta / sqrt3 V)^2)",
        "leaves_out": "no-load current is assumed (measure it); slip"}
for rpm in (12000, 14500, 18000, 24000):
    f = rpm / 30.0
    v = min(VFD["v_max"], SP_V * f / SP_F)
    flux = v / (SP_V * f / SP_F)
    i_t = (p_shaft / MOTOR_EFF) / (math.sqrt(3) * v)
    i_o = math.hypot(I_MAG_RATED * flux, i_t)
    require("R24", "VFD output current at the power cap shall be within its 11 A rating at every speed", i_o, "<=", VFD["i_out"], "A",
            case=f"{rpm} rpm", evidence=ev_i)
    require("R30", "Spindle current shall stay within its own 17.8 A rating", i_o, "<=", SP_RATED_A, "A", case=f"{rpm} rpm", evidence=ev_i)
i_total = i_aux + p_vfd_in / (SUPPLY_V * VFD_PF)
require("R25", "Continuous draw from the circuit shall be no more than 80 % of 15 A", i_total, "<=", I_CONT, "A",
        evidence={"tool": "I = P / (V PF), VFD power-limited", "leaves_out": "harmonics heating, inrush"})
# cutting need: full-depth 18 mm slot, 12 mm cutter, 6 m/min, plywood 0.04 J/mm^3
p_need = U_WOOD * 12 * 18 * (F_FEED * 1000 / 60)
require("R26", "Spindle shaft power within the circuit shall cover a full-depth 18 mm ply slot at 6 m/min", p_shaft, ">=", p_need, "W",
        evidence={"tool": "P = u x MRR, u = 0.04 J/mm^3 for plywood", "leaves_out": "dull tools, hardwoods"})
print(f"m_gantry {m_gantry:.0f} m_y {m_y:.0f} m_total {m_total:.0f} rpm x {rpm_x:.0f} y {rpm_y:.0f} z {rpm_z:.0f} "
      f"p_shaft {p_shaft:.0f} W need {p_need:.0f} i_total {i_total:.2f} col defl {d_col:.4f} t_back {t_back:.2f} ncrit {n_crit:.0f} "
      f"F_BASE {F_BASE:.0f} P_CUT_3PH {P_CUT_3PH:.0f} F_CUT_3PH {F_CUT_3PH:.0f}")

cannot_check("R27", "Salvaged E-stop, PSUs and controller wired to AS/NZS 3000 and AS/NZS 4024 (STO on the VFD, E-stop drops all drives)", why="wiring, not geometry; for an electrician")
cannot_check("R28", "The sheet shall not move while cut (screws or clamps; vacuum does not fit the circuit)", why="workholding test")
cannot_check("R31", "The spindle's cooling fan shall run from the cabinet (check its nameplate: a 380 V 3-ph fan needs its own supply on 1-ph)", why="not on the listing")
cannot_check("R29", "Guarding: the head sweeps the space in front of the bed at 0.3-1.6 m height", why="a safety review of the installed machine")


# ================================================================== detailed parts
import detail as D

for nm, got, budget in (("Y carriage", kg_y, M_YC), ("Z axis", kg_z, M_ZA), ("spindle with holder and cutter", kg_spindle, M_SP)):
    require("R51", "Each part of the head, detailed part by part, shall weigh no more than the allowance the counterweight and Y drive "
            "were sized for (detail / allowance)", got / budget, "<=", 1.0, "", case=f"{nm}: {got:.1f} of {budget:g} kg")
require("R53", "The detailed counterweight shall weigh the mass the Y drive check used, within 5 %", abs(kg_group["cw"] - M_CW) / M_CW * 100,
        "<=", 5.0, "", evidence={"tool": "part volumes x density", "leaves_out": "tie rods and fasteners"})

# ---- every detailed part inside the envelope the clash checks used (the electrical and pneumatic parts are checked part by part)
E_PREFIXES = ("cabinet", "air.", "ducts.", "popup.", "estop.", "sensors.")
ENV = {"fixed": [bed, substrate, spoil, rail_b, rail_t, rack_b, rack_t, atc, xchain, stock], "x": list(gantry(REF[0])),
       "xy": [head(*REF)[0]], "xyz": list(head(*REF)[1:]), "cw": [counterweight(REF[0], REF[1])], "world": [base, feet]}
env_u = {}
for _g, _ps in ENV.items():
    try:
        env_u[_g] = fuse(_ps)
    except Exception:
        env_u[_g] = None
for _it in items:
    if "pinion" in _it["name"] or ".rack_" in _it["name"] or _it["kind"] == "outside" or _it["name"] == "gantry_frame.rope" \
            or _it["name"].startswith(E_PREFIXES):
        continue          # rack and pinion teeth mesh in each other's tooth band by design; their envelopes stop at the roots
    _e = env_u[_it["group"]]
    try:
        _v = (_it["part"] - _e).volume() if _e is not None else sum((_it["part"] - p).volume() for p in ENV[_it["group"]][:1])
    except Exception:
        _b, _eb = _it["part"].bounding_box(), _BB(ENV[_it["group"]])
        _v = max(0.0, max(_eb.min()[i] - _b.min()[i] for i in range(3)), max(_b.max()[i] - _eb.max()[i] for i in range(3))) * 1000
    require("R50", "Every detailed part shall lie inside the envelope the clash checks used", _v, "<=", 1.0, "mm^3", case=_it["name"])

# ---- tool change: the empty spindle comes down over a holder in its fork, then retracts
z_nose_atc = FORK_Z + 10.5
ATC_SLIDE0 = ATC_X[0] - 10 - 23 - 2           # holder flange just clear of the fork slot's mouth
atc_items = [it for it in items if it["name"].startswith("atc_rack.")]
for _k, _yc in enumerate(ATC_YC):
    _tip = z_nose_atc - TIP_TO_NOSE
    _car, _za, _, _ = head(ATC_XC, _yc, _tip)
    _sp = D.c_spindle(SP_L, SP_W, SP_REAR).moved(Location.translation(ATC_XC, _yc, z_nose_atc))
    for _mn, _mv in (("carriage", _car), ("Z axis", _za), ("spindle", _sp)):
        _vol = sum(_shared(_mv, it["part"]) for it in atc_items if it["name"] != f"atc_rack.holder_{_k}")
        require("R52", "At each tool pocket the empty spindle, Z axis and carriage shall clear the fork plate, its stands and the other holders",
                _vol, "<=", 0, "mm^3", case=f"pocket {_k}: {_mn}")
    # sliding a held tool in along +x through the fork slot, from just clear of the fork; the cutter passes over the
    # spoilboard's edge and beside the thickest sheet
    _h, _t = D.c_holder(TOOL_D, TOOL_STICK)
    _held = (_h + _t).moved(Location.translation(ATC_SLIDE0, _yc, z_nose_atc))
    _obst = atc_items + [it for it in items if it["name"].startswith("bed.spoilboard") or it["name"] == "sheet"]
    for _s in range(6):
        _p = _held.moved(Location.translation((ATC_XC - ATC_SLIDE0) * _s / 5, 0, 0))
        _vol = sum(_shared(_p, it["part"]) for it in _obst if it["name"] != f"atc_rack.holder_{_k}")
        require("R54", "A held tool shall slide into its fork through the slot without touching the fork, the other holders, the spoilboard or a 25 mm sheet",
                _vol, "<=", 0, "mm^3", case=f"pocket {_k}, step {_s} of 5")

# ================================================================== dynamics: the simulation (simulation.py runs page/sim.js under Node)
import simulation as SIM
SIM_P = SIM.params(globals())
for _txt, _why in SIM.ASSUMED:
    assume(_txt, why=_why)
SIM_R = SIM.run(SIM_P)
SIM_JOBS = [k for k in SIM_R if not k.startswith("_")]
SIM_RUN = [k for k in SIM_JOBS if not k.startswith("pfail")]          # normal running; the rest are power failures
SIM_LABEL = {"rapids": "rapids", "profile": "profile cut", "pocket": "raster pocket", "toolchange": "tool change",
             "pfail": "power failure", "pfail_drop": "power failure, drivers drop out at once"}
ev_sim = {"tool": "time-domain simulation (page/sim.js, 0.1 ms steps): planner, closed-loop drivers on the published pull-out curve, "
                  "belt/screw/rack springs, carriages, counterweight rope, column bending modes, 60 V buses, VFD and spindle",
          "leaves_out": "stiffness and damping are catalogue estimates (see the assumptions); no gantry yaw; cutting force from power only"}
CONTOUR_MAX = 100.0                      # um: wood parts hold +-0.1 mm
for _j in ("profile", "pocket"):
    _r = SIM_R[_j]
    require("R69", "While cutting, the tool tip shall stay within 0.1 mm of the programmed path (servo lag, drive springs and column bending)",
            _r["contour"], "<=", CONTOUR_MAX, "um", case=f"{SIM_LABEL[_j]}, worst at {_r['contour_at']:.1f} s", evidence=ev_sim, of=["GAN", "YC", "ZA"])
for _j in SIM_RUN:
    for _a, _n in (("X", "GAN"), ("Y", "YC"), ("Z", "ZA")):
        _u = SIM_R[_j]["util"][_a]
        require("R70", "No axis shall ask for more than 80 % of its motors' pull-out torque at the speed it is running, in any job",
                _u * 100, "<=", 80, "%", case=f"{SIM_LABEL[_j]}: {_a} at {SIM_R[_j]['util_at'][_a]:.1f} s", evidence=ev_sim, of=[_n])
for _k in ("X1", "X2", "Y", "Z"):
    _w = max(SIM_R[_j]["psu"][_k] for _j in SIM_JOBS)
    _jw = max(SIM_JOBS, key=lambda j: SIM_R[j]["psu"][_k])
    require("R71", "Each 60 V supply's load, averaged over 100 ms, shall stay within its 350 W rating in every job",
            _w, "<=", PSU_W, "W", case=f"supply {_k}, worst in {SIM_LABEL[_jw]}", evidence=ev_sim, of=["ELEC"])
for _j in SIM_JOBS:
    require("R72", "Braking energy shall not lift any 60 V bus above 90 V (the drivers trip at 100 V)",
            SIM_R[_j]["vbus"], "<=", 0.9 * SIM.V_DRV_MAX, "V", case=SIM_LABEL[_j], evidence=ev_sim, of=["ELEC", "GAN"])
    require("R73", "Mains current averaged over any 1 s shall stay within the 15 A circuit, in every job",
            SIM_R[_j]["mains_1s"], "<=", SUPPLY_A, "A", case=SIM_LABEL[_j], evidence=ev_sim, of=["ELEC", "SP"])
    if _j in SIM_RUN:
        require("R76", "The counterweight rope shall never go slack: least tension at least half its static tension, in every job",
                SIM_R[_j]["rope_min"] / SIM_P["axes"]["Y"]["cw"]["T0"] * 100, ">=", 50, "%", case=SIM_LABEL[_j], evidence=ev_sim, of=["GAN", "YC"])
for _j in ("profile", "pocket"):
    require("R74", "While cutting, the spindle shall hold within 10 % of its set speed (VFD power cap against the cut)",
            SIM_R[_j]["droop"] * 100, "<=", 10, "%", case=SIM_LABEL[_j], evidence=ev_sim, of=["SP", "ELEC"])
_modes = SIM_R["rapids"]["modes"]
for _m, _f in _modes.items():
    if _m == "counterweight rope":
        continue                         # outside the position loop; R76 checks it
    require("R75", "Each drive and column mode shall be at least 2.5 x the drivers' 20 Hz position-loop bandwidth, so the loop does not excite it",
            _f / SIM.SERVO_BW, ">=", 2.5, "", case=f"{_m}: {_f:.0f} Hz", evidence=ev_sim, of=["GAN", "YC", "ZA"])
# ---- total power failure at rapid, in -y, -z and +x: how far past its normal stop each axis runs, against what it can run
# X: the X blocks have 53 mm of rail beyond the travel; Y: the Y rails end where the travel does; Z: the jobs clear the sheet by 10 mm
_blk_x = (X_TRAVEL[0] - SP_OFF - COL_W / 2 - 45 - BLK_L / 2) - X_BED[0]
OVERRUN_OK = {"X": _blk_x, "Y": min(Y_WORK[0] - (Y_RAIL[0] + YCH), (Y_RAIL[1] - YCH) - Y_WORK[1]), "Z": 10.0}
ev_pf = dict(ev_sim, tool=ev_sim["tool"] + "; on the mains failing: supplies, VFD and controller off, command frozen, drivers on their "
                                            "buses' energy until they trip, Y brake after 50 ms; stick-slip friction, detent and brake")
for _j in ("pfail", "pfail_drop"):
    _f = SIM_R[_j]["fail"]
    for _i, (_a, _n) in enumerate((("X", "GAN"), ("Y", "YC"), ("Z", "ZA"))):
        _v = abs(_f["v0"][_i])
        _over = max(0.0, _f["run"][_i] - _v * _v / (2 * SIM_P["axes"][_a]["acc"])) * 1000
        require("R77", "On a total power failure at rapid, no axis shall run past where the controller would have stopped it by more than it can: "
                "X 53 mm of rail beyond the travel, Y none, Z the 10 mm clearance over the sheet",
                OVERRUN_OK[_a] - _over, ">=", 0, "mm", case=f"{SIM_LABEL[_j]}: {_a} ran {_f['run'][_i] * 1000:.1f} mm, {_over:.1f} past its normal stop",
                evidence=ev_pf, of=[_n])
        _creep = abs(_f["xs"][_i] - _f["x2"][_i]) * 1000 if _f.get("x2") else 0.0
        require("R79", "After a power failure every axis shall hold still: Y on its brake, Z and X on friction and detent (movement 2 s on)",
                _creep, "<=", 0.01, "mm", case=f"{SIM_LABEL[_j]}: {_a}", evidence=ev_pf, of=[_n])
    require("R78", "On a power failure the counterweight rope's peak tension shall stay within its breaking load / 5, as the head stops and the block runs on",
            ROPE_MBL / max(_f["rope_max"], 1.0), ">=", 5.0, "", case=f"{SIM_LABEL[_j]}: peak {_f['rope_max']:.0f} N, least {_f['rope_min']:.0f} N",
            evidence=ev_pf, of=["GAN", "YC"])
print("simulation", {j: {k: SIM_R[j][k] for k in ("contour", "vbus", "mains_1s", "droop", "rope_min")} for j in SIM_JOBS}, f"{SIM_R['_ms']} ms")
print("power failure", {j: SIM_R[j]["fail"] for j in ("pfail", "pfail_drop")}, OVERRUN_OK)
# ---- the model checked against answers known without it (sim.js verify()): it is the model that the results above rest on
SIM_V = SIM_R["_verify"]
ev_v = {"tool": "page/sim.js verify(): lossless free vibration, steady-speed force balance, idle start, half time step",
        "leaves_out": "it checks the model is solved right, not that its parameters are right; see sensitivity.py for those"}
for _a, _q in SIM_V["drive"].items():
    require("R80", "Each drive's simulated natural frequency shall match the two-mass formula sqrt(k (1/m + 1/J G^2)) / 2 pi within 1 %",
            _q["freq_err"], "<=", 1.0, "%", case=f"{_a}: {_q['f']:.1f} Hz against {_q['want']:.1f} Hz", evidence=ev_v, of=["GAN", "YC", "ZA"])
    require("R81", "With losses and the loop off, a ringing drive's energy shall drift no more than 0.1 % over a second (the solver adds or loses none)",
            _q["energy_drift"], "<=", 0.1, "%", case=_a, evidence=ev_v, of=["GAN", "YC", "ZA"])
for _a, _q in SIM_V["steady"].items():
    require("R82", "At a steady rapid, each motor's simulated torque shall equal the force balance (friction, drag, gravity, counterweight, detent) within 1 %",
            _q["err"], "<=", 1.0, "%", case=f"{_a}: {_q['got']:.3f} against {_q['want']:.3f} N m", evidence=ev_v, of=["GAN", "YC", "ZA"])
require("R83", "Left alone where it starts, the simulated tool tip shall move no more than 0.1 um (the model starts in equilibrium)",
        SIM_V["rest"]["worst_um"], "<=", 0.1, "um", case=f"static sag under its own weight {SIM_V['rest']['sag_um']:.2f} um", evidence=ev_v, of=["P"])
for _k, _q in SIM_V["conv"].items():
    require("R84", "Halving the solver's time step shall change no simulated result by more than 2 %",
            _q["change"], "<=", 2.0, "%", case=f"{_k}: {_q['dt']:.4g} to {_q['half']:.4g}", evidence=ev_v, of=["P"])
import json
json.dump(SIM_P, open("sim_params.json", "w"))
print("verification", json.dumps(SIM_V)[:600], f"{SIM_R['_ms_verify']} ms")

# ================================================================== the build, step by step (assembly.py)
import assembly as A
X_ASM = (xs_legs[1] + xs_legs[2]) / 2 + SP_OFF + COL_W / 2     # gantry station while it is built: column between two floor legs
UNIT_PIVOT_H = {"column": wpt(X_ASM - SP_OFF - COL_W / 2, Y_RB - 40, ZC0 + COL_D / 2)[2]}
MOTORS = A.MOTORS
CABLE_ROUTES = EL.routes(globals(), items)
CABLE_M = EL.check(globals(), items, require, CABLE_ROUTES)
CABLE_NAMES = EL.cable_names()
EXTRA_KG = {n: CABLE_M.get(n, 2.0) * (dict((c[0], c[3]) for c in EL.CABLE_LIST).get(n, 0.02)) for n in CABLE_NAMES}
ASM_PARK = (X_TRAVEL[0], Y_WORK[0], ZN_MAX - TIP_TO_NOSE)
ASM_POSE0 = (X_ASM, (Y_WORK[0] + Y_WORK[1]) / 2, ZN_MAX - TIP_TO_NOSE)
ASM_STEPS = A.procedure(globals())
ASM_UNITS = A.check(globals(), items, require, M_KG, None)
import time as _time
_t0 = _time.time()
JOINT_RESULTS = A.check_joints(globals(), items, require, D.JOINTS, D.WELDS)
print(f"joints: {len(D.JOINTS)} joints, {sum(len(j['pts']) for j in D.JOINTS)} fasteners, {len(D.WELDS)} welds, {_time.time() - _t0:.0f} s")
TILT_AXIS = (Axis.X, 90 - TILT)
_t0 = _time.time()
A.check_space(globals(), items, require, D.JOINTS, W)
print(f"space checks {_time.time() - _t0:.0f} s")

# ---- parts lists from the detail
import csv
_bought = {}
for _it in items:
    if _it["kind"] == "bought":
        k = _it["note"]
        _bought.setdefault(k, [0, _it["kg"], []])
        _bought[k][0] += 1
        _bought[k][2].append(_it["name"])
_bought["StepperOnline 34E1K-120 closed-loop stepper (salvaged)"] = [4, M_KG, ["x_motor_bottom", "x_motor_top", "y_motor", "z_motor"]]
with open("bought_parts.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["item", "qty", "kg_each", "where"])
    for k, (q, kg, where) in sorted(_bought.items()):
        w.writerow([k, q, f"{kg:.2f}", " ".join(where)])
with open("made_parts.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["part", "material", "how", "size_x", "size_y", "size_z", "kg", "step_file"])
    for _it in items:
        if _it["kind"] == "made":
            _b = _it["part"].bounding_box()
            w.writerow([_it["name"], _it["mat"], _it["note"], *(f"{_b.max()[i] - _b.min()[i]:.1f}" for i in range(3)), f"{_it['kg']:.2f}",
                        _it["name"] + ".step"])
print("parts lists:", len(_bought), "bought lines,", sum(1 for it in items if it["kind"] == "made"), "made parts")

# ================================================================== data for the 3D viewer page
import json


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
             components=["sim.js", "sim-page.js", "sim-ui.js", "build.js", "flex.js"], whole="whole machine", bought_word="salvaged")
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
for _it in items:
    if _it["name"] in CHAIN_SPECS or _it["name"] == "gantry_frame.rope":
        continue
    V["parts"][_it["name"]] = dict(mesh_of(_it["part"]), group=_it["group"], colour=_hex(_it["colour"]),
                                   info=f"{_it['note']} | {_it['mat']} | {_it['kg']:.2f} kg", kind=_it["kind"])
for name, loc, grp, nd in (("gantry_drives.x_motor_bottom", x_motor_loc(_c1 - COL_W, Y_RB), "x", "GAN"),
                           ("gantry_drives.x_motor_top", x_motor_loc(_c1 - COL_W, Y_RT), "x", "GAN"),
                           ("gantry_drives.y_motor", y_motor_loc(_c1 - COL_W), "x", "GAN"), ("y_carriage.z_motor", z_motor_loc(_c1, REF[1]), "xy", "YC")):
    V["parts"][name] = dict(shared="motor", group=grp, colour="#34383f", loc=loc_matrix(loc),
                            info="StepperOnline 34E1K-120, 12 N*m closed-loop (salvaged) | 5.0 kg", kind="bought")
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
# ---- the build, for the page to play back
_shown = set(V["parts"]) | {c["name"] for c in V["chains"]}
_asm = []
for _st in ASM_STEPS:
    _parts = list(_st["adds"]) + (list(ASM_UNITS[_st["moves"]]["parts"]) if _st["moves"] else [])
    def _legs_json(p):
        L_ = A._legs(p)
        return None if L_ is None else [[list(l[0]), l[1], l[2] if len(l) > 2 else "local"] for l in L_]
    _legs_of = {}
    for _n in _st["adds"]:
        _p = _st["path"]
        for _pat, _q in _st["paths"].items():
            if A.fnmatch.fnmatchcase(_n, _pat):
                _p = _q
        _legs_of[_n] = _legs_json(_p)
    _asm.append(dict(id=_st["id"], phase=_st["phase"], title=_st["title"], text=_st["text"], tools=_st["tools"], fixture=_st["fixture"],
                     why=_st["why"], adds=_st["adds"], unit=_st["unit"], moves=_st["moves"], path=_legs_json(_st["path"]), legs_of=_legs_of,
                     pose=list(_st["pose"]) if _st["pose"] else None, lift=_st.get("lift")))
_missing = [n for _st in _asm for n in _st["adds"] if n not in _shown and n != "gantry_frame.rope" and not n.startswith(("wire.", "cable.", "hose."))]
import fasteners as FA
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
for _st in _asm:
    _js = [J for J in JOINT_RESULTS if J["step"] == _st["id"] and J["f"]["type"] != "STUD"]
    _sum = {}
    for J in _js:
        k = (FA.label(J["f"]), FA.tool(J["f"]), FA.torque(J["f"], J["into"]))
        _sum[k] = _sum.get(k, 0) + len(J["pts"])
    _st["fasteners"] = [dict(n=n, label=k[0], tool=k[1], torque=k[2]) for k, n in _sum.items() if not k[0].startswith("M16 x 34 levelling")]
    _st["welds"] = [dict(a=W["a"], b=W["b"], how=W["how"]) for W in D.WELDS if W["step"] == _st["id"]]
# ---- build documents: the procedure, the cable list, fasteners in the bought list
_fcount = {}
for _J in JOINT_RESULTS:
    if _J["f"]["type"] != "STUD":
        _fcount[FA.label(_J["f"])] = _fcount.get(FA.label(_J["f"]), 0) + len(_J["pts"])
with open("bought_parts.csv", "a", newline="") as f:
    w = csv.writer(f)
    for k, q in sorted(_fcount.items()):
        w.writerow([k, q, "", "fasteners"])
    for c in EL.CABLE_LIST:
        w.writerow([f"{c[1]} ({c[0]})", f"{CABLE_M[c[0]]:.1f} m", f"{c[3]:.2f}/m", f"{c[4]} to {c[6]}"])
with open("cable_list.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["cable", "type", "od_mm", "from", "chains", "to", "length_m"])
    for c in EL.CABLE_LIST:
        w.writerow([c[0], c[1], c[2], c[4], " ".join(c[5]) or "-", c[6], f"{CABLE_M[c[0]]:.1f}"])
    w.writerow([])
    w.writerow(["wire", "from", "to", "what"])
    for i, (a_, b_, t_) in enumerate(EL.WIRES):
        w.writerow([f"wire.{i:02d}", a_, b_, t_])
with open("assembly_procedure.md", "w") as f:
    f.write("# Tilted-bed CNC router: build procedure\n\nGenerated by router.py; every step below is checked (R57-R68).\n")
    _ph = None
    for _st in _asm:
        if _st["phase"] != _ph:
            _ph = _st["phase"]
            f.write(f"\n## {_ph}\n")
        f.write(f"\n### {_st['id']} {_st['title']}\n\n{_st['text']}\n\n")
        if _st.get("lift"):
            f.write(f"- Heaviest handling: {_st['lift']['what']}, {_st['lift']['kg']} kg, {_st['lift']['how']} ({_st['lift']['force']} kg each)\n")
        for _fz in _st.get("fasteners", []):
            f.write(f"- {_fz['n']} x {_fz['label']}: {_fz['tool']}" + (f", {_fz['torque']} N*m" if _fz["torque"] else "") + "\n")
        for _wz in _st.get("welds", []):
            f.write(f"- Weld {_wz['a']} to {_wz['b']}: {_wz['how']}\n")
        if _st["tools"]:
            f.write(f"- Tools: {', '.join(_st['tools'])}\n")
        if _st["fixture"]:
            f.write(f"- Temporary: {_st['fixture']}\n")
        if _st["adds"]:
            f.write(f"- Parts: {', '.join(_st['adds'])}\n")
V["assembly"] = {"steps": _asm, "stage": A.STAGE, "units": {u: d["parts"] for u, d in ASM_UNITS.items()},
                 "pose": [X_ASM, (Y_WORK[0] + Y_WORK[1]) / 2, ZN_MAX - TIP_TO_NOSE]}
require("R64", "Every step of the build shall play back in the 3D viewer with all of its parts (parts a step names that the viewer lacks)",
        len(_missing), "<=", 0, "", case=f"{len(_asm)} steps" + (f"; missing {', '.join(_missing[:4])}" if _missing else ""))
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
open("viewer_data.json", "w").write(json.dumps(V))
# ---- how far each result can be trusted (se.report): who set each requirement, what its check rests on
import se as _se
_M = _se._m()
STATED = {"R1", "R2", "R3", "R4", "R6", "R7", "R8", "R57", "R58", "R64"}       # the user's words, sketch or answers
ASSUMED_LIMITS = {"R15", "R16", "R17", "R18", "R19", "R20", "R21", "R22", "R26", "R34", "R35", "R36", "R40", "R41", "R42", "R44",
                  "R45", "R46", "R47", "R56", "R60", "R67", "R69", "R70", "R72", "R74", "R75", "R76", "R77", "R78", "R79",
                  "R80", "R81", "R82", "R83", "R84"}                            # limits the agent chose
for _id, _r in _M.requirements.items():
    if _id in STATED:
        _r.source = "stated"
    elif _id.split("-")[0] in ASSUMED_LIMITS:
        _r.source = "assumed"
    else:
        _r.source = "implied"


def _affects(start, *ids):
    for _a in _M.assumptions.values():
        if _a.text.startswith(start):
            _a.affects += [i for i in ids if i not in _a.affects]


SIM_REQS = ["R69", "R70", "R71", "R72", "R73", "R74", "R75", "R76", "R77", "R78", "R79"]
_affects("Bed tilt is", "R4")
_affects("The 300 on the sketch", "R3")
_affects("Stock up to", "R1", "R2", "R5", "R12", "R14", "R26", "R69")
_affects("Motor torque follows", "R17", "R18", "R19", "R33", "R70")
_affects("Spindle is the 380 V", "R24", "R25", "R26", "R30", "R73", "R74")
_affects("On a future 3-phase", "R17", "R22", "R46", "R47")
_affects("Dust collector and compressor", "R25", "R73")
_affects("Rapids X 15", "R17", "R18", "R19", "R22", "R33", "R44", "R46", "R47", *SIM_REQS)
_affects("The head may overhang", "R8")
for _txt, _why in SIM.ASSUMED:
    _affects(_txt[:30], *SIM_REQS)
for _a in _M.assumptions.values():                                          # what the user has told us is so
    if _a.text.startswith(("Bed tilt is", "The X and Z cable chains may stand above")):
        _a.confirmed = True
model("sim", "time-domain simulation, page/sim.js", checked_by=["R80", "R81", "R82", "R83", "R84"])
for _id in SIM_REQS:
    _M.requirements[_id].depends.append("sim")
# the sensitivity sweep: a pass that fails when a guess is halved or doubled is fragile
try:
    _sens = json.load(open("sensitivity.json"))
except FileNotFoundError:
    _sens = None
if _sens and _sens.get("digest") == SIM.digest(SIM_P):
    for _row in _sens["rows"]:
        for _k, _c in _row["checks"].items():
            if not _c["ok"]:
                fragile(_k.split()[0], f"{_row['name']} is x{_row['f']:g}")
else:
    for _id in SIM_REQS:
        fragile(_id, "the sensitivity sweep is missing or stale (run sensitivity.py)")
report(baseline="systems_baseline.json")
