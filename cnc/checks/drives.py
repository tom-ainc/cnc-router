"""R32, R17-R21, R34-R40: the motor model, axis drives, brake, counterweight and its rope, nut clearances."""
import math
from golf_py import Location
from se import _shared
from cnc.params import (
    ACC, BLK_H, BRAKE_T, F_CUT, F_CUT_3PH, F_FEED, F_FEED_3PH, M_CW, M_J, NUT_CLEAR, REEVE, ROPE_D, ROPE_MBL, SHEAVE_D,
    SP_OFF, TILT, TIP_MIN, V_RAPID, X_PINION_PCD, X_RATIO, YN_FL, YS_X, Y_LEAD, Y_RAIL, Y_RATIO, Y_RISER, Y_WORK,
    ZN_FL, ZS_X, ZYP0, ZYP1, Z_LEAD, Z_RATIO, Z_RISER, Z_TRAVEL)
from cnc.geometry.shapes import cyl_y
from cnc.geometry.motor import MOTOR, MOTOR_STEP
from cnc.geometry.moving import ROPE_X, SHEAVE_Y, SHEAVE_Z, counterweight, gantry, head
from cnc.geometry.pose import POSE
from cnc.system.requirements import clear_travel, require
from cnc.checks.stability import m_gantry, m_y, m_z

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
