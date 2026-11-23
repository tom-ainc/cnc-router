"""The moving parts as clash-check envelopes: counterweight, gantry and head, at any pose."""
from cnc.parts import detail as D
from cnc.params import (
    BF15, BF20, BK15, BK20, BLK_H, BLK_L, BLK_Z, BRAKE_L, CHAIN, CHAIN_R, CLAMP_Z, COL_D, COL_T, COL_W, CW_GAP,
    CW_SHEAVE, HOLDER_L, HOLDER_R, HTD_W, M_CW, PIN_FACE, PL, RACK_OFF, RACK_W, RAIL_H, RAIL_W, REEVE, SHEAVE_D,
    SPOIL_T, SP_L, SP_OFF, SP_REAR, SP_W, SUP_SPACER, TIP_TO_NOSE, TOOL_D, XD_TOP, X_PINION_PCD, YCH, YN_D, YN_FL,
    YN_FT, YN_L, YS_D, YS_X, YS_Z, Y_RAIL, Y_RB, Y_RISER, Y_RISER_H, Y_RT, Y_WORK, ZC0, ZCH_LEN, ZN_D, ZN_FL, ZN_FT,
    ZN_L, ZN_MIN, ZP0, ZP1, ZS_D, ZS_X, ZYP0, ZYP1, Z_CH_F, Z_RAIL_DY, Z_RISER)
from cnc.geometry.shapes import box, cyl_y, cyl_z, fuse
from cnc.geometry.motor import MOTOR, x_motor_loc, y_motor_loc, z_motor_loc
from cnc.geometry.bed import CH_PAD, M_GEAR, RACK_Z, XCH_Y, XCH_Z, Y_FIX
from cnc.design import namespace

SHEAVE_Y = Y_RT + 40 - 10 - SHEAVE_D / 2 - 10         # top sheave centre, just under the column's top cap
SHEAVE_Z = ZC0 + 85.0                                 # rope plane, between the lower Y rail and the screw supports
ROPE_X = 10.0                                         # rope runs 10 mm off the column face, in the gap


def top_sheave(c1):
    """Fixed sheave (with its flanges) turning the rope from the carriage, in the gap outside the column's +x wall,
    into the column; it passes through a slot in the wall."""
    return cyl_z(c1 + ROPE_X - SHEAVE_D / 2, SHEAVE_Y, SHEAVE_D / 2 + 5, SHEAVE_Z - 15, SHEAVE_Z + 15)
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
    xmot = [MOTOR.fork().moved(x_motor_loc(c0, y)) for y in (Y_RB, Y_RT)] if motors else []
    # X drive: 15T on the motor, 45T on the pinion shaft (3:1), pinion meshing the outward face of the rack;
    # its bearing housing pivots on the foot and a spring pulls it into mesh
    belt_x = []
    for y, sgn in ((Y_RB, -1), (Y_RT, 1)):
        yp = y + sgn * (RACK_OFF + RACK_W / 2 - 1.5 + X_PINION_PCD / 2)          # pinion centre
        zp = (RACK_Z[0] + RACK_Z[1]) / 2
        xp = c0 - 55
        pinion = cyl_z(xp, yp, X_PINION_PCD / 2 - 1.25 * M_GEAR, zp - PIN_FACE / 2, zp + PIN_FACE / 2)
        housing = box(xp - 35, xp + 35, yp - 35, yp + 35, max(zp + PIN_FACE / 2, RACK_Z[1]) + 1, BLK_Z)
        _L = D.x_drive_layout(namespace(), c0, y, sgn)
        belt = box(_L["xlo"], c0 + 30.4, _L["ylo"], _L["yhi"], BLK_Z - 0.3, BLK_Z + XD_TOP + 0.3)
        shaft = cyl_z(xp, yp, 7.5, zp + PIN_FACE / 2 - 0.5, BLK_Z + 1) + cyl_z(xp, yp, 12.5, zp - PIN_FACE / 2 - 10.5, zp - PIN_FACE / 2 + 0.5)
        belt_x += [pinion, housing, belt, shaft]
    # Y motor beside the column top, parallel to the screw, shaft up into a 30T:20T belt step-up
    ymot = [MOTOR.fork().moved(y_motor_loc(c0))] if motors else []
    risers = [box(c1, c1 + Y_RISER, Y_RAIL[0], Y_RAIL[1], z - Y_RISER_H / 2, z + Y_RISER_H / 2) for z in (ZC0 + 40, ZC0 + COL_D - 40)]
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
                box(c0 + 60, c0 + 140, Y_RT + 40.5, Y_RT + 43.5, BLK_Z, BLK_Z + 20),         # the tab bolted to the foot's end
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
    zmot = [MOTOR.fork().moved(z_motor_loc(c1, ys))] if motors else []
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
