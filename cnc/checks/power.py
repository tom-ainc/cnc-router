"""R33, R23-R31: motor supplies, the VFD, the spindle and the circuit."""
import math
from cnc.params import F_CUT_3PH, F_FEED, M_AMPS, PSU_W, P_CUT_3PH, SUPPLY_A, SUPPLY_V, U_WOOD
from cnc.system.requirements import cannot_check, require
from cnc.checks.stability import m_gantry, m_total, m_y
from cnc.checks.drives import n_crit, pk_x, pk_y, pk_z, rpm_x, rpm_y, rpm_z, t_back
from cnc.checks.structure import d_col

# each driver's supply: shaft power / 80 % + copper loss of both phases at rated current
cu = 2 * M_AMPS ** 2 * 0.72
for ax, pk in (("X", pk_x), ("Y", pk_y), ("Z", pk_z)):
    require("R33", "Each motor's peak draw shall be within its 60 V 350 W supply", pk / 0.8 + cu, "<=", PSU_W, "W", case=f"{ax} motor",
            evidence={"tool": "P = T w / 0.8 + 2 I^2 R", "leaves_out": "supply sharing, if drivers share a supply"})
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
