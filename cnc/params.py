"""What the user stated, what is assumed, catalogue sizes of bought parts, design variables, and the positions
derived from them. Numbers only: every other module reads its sizes from here."""
import math

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
Y_RISER, Y_RISER_H = 40.0, 25.0          # steel flat 40 x 25 welded to the column face, rails on top
Z_RISER = 32.0                           # aluminium bar on the Y plate: lifts the Z blocks clear of BK15 at the top of the stroke
BRAKE_D, BRAKE_L = 70.0, 45.0            # 24 V spring-applied brake on the Y screw's bottom end
Z_RAIL_DY = 50.0                         # Z rails at +-50: the Y blocks' bolt holes (at +-88 +-17.5) stay clear of the Z risers
CLAMP_Z = (130.0, 260.0)                 # spindle clamps, from the nose: between the Z blocks' bolt rows
ZCH_LEN = 470.0                          # Z chain zone, from the Y plate's far end: high enough to clear the ATC rack
HTD_W = 30.0                             # belt and pulley plane thickness (HTD 5M, 15 mm belt, flanged pulleys)
# The salvaged axis motors: StepperOnline 34E1K-120 (datasheet in parts/): 12 N*m holding, 6 A, 0.72 ohm, 7.3 mH,
# rotor 5400 g*cm^2, 5.0 kg, 1000 PPR encoder. Its STEP: mounting face at z = 0, shaft +z, cable outlet -y.
M_HOLD, M_AMPS, M_L, M_J, M_KG = 12.0, 6.0, 7.3e-3, 5.4e-4, 5.0
V_BUS = 58.0                             # V DC: the salvaged 60 V 350 W supplies, ~58 V loaded
PSU_W = 350.0                            # W, one supply per driver (assumed)
XD_TOP = 44.0     # X drive: motor plate's top face above the X blocks' top (8 lower plate, 30 standoffs, 6 motor plate)
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
