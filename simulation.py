"""The machine's dynamic model: its parameters, drawn from the design (router.py's globals), and a run of every job.

The model itself is page/sim.js: one implementation, run live in the page and here under Node, so the requirements are
checked on exactly the model the page shows. Parameters not set by the design are assumptions, each named below."""
import hashlib, json, math, os, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_JS = os.path.join(HERE, "page", "sim.js")

# ---- assumptions: values the design does not fix (catalogue orders of magnitude)
BELT_EA = 1.2e5          # N, HTD 5M 15 mm glass-cord belt, per unit strain
X_BELT_SPAN, Y_BELT_SPAN, Z_BELT_SPAN = 0.10, 0.12, 0.10    # m, belt free spans (both spans tensioned)
K_MESH = 1.0e8           # N/m, m1.5 helical rack and pinion, 15 mm face
K_NUT, K_BK = 2.0e8, 4.0e8   # N/m, SFU ball nut (not preloaded) and the fixed-end bearing pair
SEAL_N = 15.0            # N, drag of one HGH25CA block's seals
MU_BLOCK = 0.005         # rolling friction of the blocks
ROPE_EA = 1.0e6          # N, 5 mm 7x19 steel rope
ROPE_L = 2.2             # m, rope from its anchor over the sheave, round the block's sheave and back up
C_BUS = 2.2e-3           # F, supply output plus driver input capacitors on one 60 V bus
V_DRV_MAX = 100.0        # V DC, the closed-loop drivers' maximum input
SP_J = 3.0e-3            # kg m^2, spindle rotor with an ISO30 holder
SP_P_LOSS = 400.0        # W, bearings and windage at 24 000 rpm, scaling with speed squared
SP_T_MAX = 2.0           # N m, what 11 A from the VFD gives on the 17.8 A winding
SERVO_BW = 20.0          # Hz, the closed-loop drivers' position loop
STRUCT_ZETA = 0.03       # damping of the welded column
DRIVE_ZETA = 0.05        # damping of the belt and screw drives
K_BLOCKS_Z = 1.0e9       # N/m, X and Y bearing blocks in series, normal to the bed
DT = 1e-4                # s, the solver step
V_DRV_UV = 20.0          # V DC, the drivers' undervoltage trip
E_TRIP = 2 * math.pi     # rad, the drivers' position-error alarm (one motor turn)
T_DETENT = 0.15          # N m, a NEMA34's unpowered detent torque
BRAKE_DELAY = 0.05       # s, from the mains going to the Y brake holding (24 V hold-up and armature release)

ASSUMED = [
    ("Drive stiffness from catalogue orders of magnitude: HTD 5M belt EA 120 kN, rack mesh 100 N/um, ball nut 200 N/um",
     "no stiffness data for the salvaged parts; the simulation's vibration results scale with them"),
    ("Each 60 V bus has 2200 uF and the supplies cannot sink current; the drivers trip above 100 V DC",
     "typical for open-frame supplies and closed-loop stepper drivers; measure the salvaged ones"),
    ("Spindle rotor 0.003 kg m^2, 400 W of bearing and windage loss at 24 000 rpm", "same-body spindles' catalogues"),
    ("The drivers' position loop closes at 20 Hz on the motor encoder", "a closed-loop stepper driver's usual tuning"),
    ("On a power failure the controller stops at once; the drivers trip below 20 V or at one turn of position error; the Y brake holds 50 ms "
     "after the mains goes; unpowered motors give 0.15 N m of detent torque", "closed-loop stepper drivers' and spring brakes' usual behaviour; measure them"),
]


def params(g):
    """The model's parameters, from the design's globals."""
    G_ = 9.81
    th = math.radians(g["TILT"])
    m_frame = g["masses"]["gantry_frame"][1]
    m_head = g["M_HEAD"]
    mx = m_head + 0.4 * m_frame                         # head plus the column's share at mid-height
    # ---- X: two rack-and-pinion drives, 3:1 belt
    r_pin = g["X_PINION_PCD"] / 2000
    r_big = 60 * 5 / (2 * math.pi) / 1000               # 60T HTD 5M pulley on the pinion shaft
    kb = 2 * BELT_EA / X_BELT_SPAN
    k_side = 1 / (1 / (kb * (r_big / r_pin) ** 2) + 1 / K_MESH)
    Gx = g["X_RATIO"] / r_pin
    J_big = 0.5 * (math.pi * r_big ** 2 * 0.03 * 2700) * r_big ** 2
    Jx = 2 * (g["J_ROTOR"] + 2e-5 + (J_big + 1e-5) / g["X_RATIO"] ** 2)
    mX = g["m_gantry"] - mx
    # ---- Y: SFU2520 through a 2:3 belt, the counterweight on a 2:1 rope
    lead_y = g["Y_LEAD"] / 1000
    y_len = g["y_len"] / 1000
    Js_y = g["screw_j"](25, g["y_len"]) + 3e-5
    kb = 2 * BELT_EA / Y_BELT_SPAN
    r_sp = 20 * 5 / (2 * math.pi) / 1000
    k_belt_y = kb * (r_sp / (lead_y / (2 * math.pi))) ** 2
    k_screw_y = 210e9 * math.pi / 4 * 0.0214 ** 2 / (y_len - 0.1)   # nut at the far end from the fixed BK20
    ky = 1 / (1 / k_belt_y + 1 / k_screw_y + 1 / K_NUT + 1 / K_BK)
    Gy = g["Y_RATIO"] * 2 * math.pi / lead_y
    mY = m_head + Js_y * (2 * math.pi / lead_y) ** 2
    cw_m = g["M_CW"]
    k_rope = ROPE_EA / ROPE_L
    # ---- Z: SFU2010 through a 1:2 belt
    lead_z = g["Z_LEAD"] / 1000
    z_len = (g["ZYP1"] - g["ZYP0"]) / 1000
    Js_z = g["screw_j"](20, g["ZYP1"] - g["ZYP0"]) + 2e-5
    kb = 2 * BELT_EA / Z_BELT_SPAN
    k_belt_z = kb * (r_sp / (lead_z / (2 * math.pi))) ** 2
    k_screw_z = 210e9 * math.pi / 4 * 0.0172 ** 2 / z_len
    kz = 1 / (1 / k_belt_z + 1 / k_screw_z + 1 / K_NUT + 1 / K_BK)
    Gz = g["Z_RATIO"] * 2 * math.pi / lead_z
    mZ = g["m_z"] + Js_z * (2 * math.pi / lead_z) ** 2

    def axis(m, G, Jm, k, trans, n_mot, Fc, grav, A):
        return dict(m=m, G=G, J_m=Jm, J_servo=Jm + m / G ** 2, k=k, c=2 * DRIVE_ZETA * math.sqrt(k * m), eta=0.9, n_mot=n_mot,
                    Fc=Fc, bv=40.0, b_m=1e-3 * n_mot, grav=grav, trans=trans, v_rapid=g["V_RAPID"][A] / 60, acc=g["ACC"][A], x0=0.0)

    axes = {
        "X": axis(mX, Gx, Jx, 2 * k_side, "2 × belt + rack", 2, 4 * SEAL_N + MU_BLOCK * g["m_gantry"] * G_, 0.0, "X"),
        "Y": axis(mY, Gy, g["J_ROTOR"] + 5e-5, ky, "belt + ballscrew", 1, 4 * SEAL_N + 10 + MU_BLOCK * m_head * G_, -m_head * G_ * math.cos(th), "Y"),
        "Z": axis(mZ, Gz, g["J_ROTOR"] + 6e-5, kz, "belt + ballscrew", 1, 4 * SEAL_N + 5, -g["m_z"] * G_ * math.sin(th), "Z"),
    }
    axes["Y"]["brake_F"] = g["BRAKE_T"] * 2 * math.pi / lead_y * 0.9      # the screw brake's hold, at the nut
    axes["Y"]["cw"] = dict(m=cw_m, k=k_rope, c=2 * 0.03 * math.sqrt(4 * k_rope * cw_m) / 4, T0=cw_m * G_ * math.cos(th) / 2, Fc=5.0)
    col_t, cw_, cd = g["COL_T"], g["COL_W"], g["COL_D"]
    Ix = (cd * cw_ ** 3 - (cd - 2 * col_t) * (cw_ - 2 * col_t) ** 3) / 12 * 1e-12
    Iz = (cw_ * cd ** 3 - (cw_ - 2 * col_t) * (cd - 2 * col_t) ** 3) / 12 * 1e-12
    tip_up = g["ZN_MAX"] - g["TIP_TO_NOSE"]
    P = {
        "dt": DT, "g": G_, "tilt": g["TILT"], "axes": axes,
        "motor": {"curve": [list(c) for c in g["TORQUE_CURVE"]], "Kt": g["M_HOLD"] / g["M_AMPS"], "R": 0.72, "I_idle": 0.3 * g["M_AMPS"],
                  "I_peak": 8.0, "e_trip": E_TRIP, "T_det": T_DETENT},
        "fail": {"brake_delay": BRAKE_DELAY},
        "servo": {"f_bw": SERVO_BW, "zeta": 0.8, "ki": 0.15},
        "struct": {"E": 210e9, "Ix": Ix, "Iz": Iz, "L": (g["Y_RT"] - g["Y_RB"]) / 1000, "y0": g["Y_RB"] / 1000, "mx": mx, "mz": mx,
                   "zeta": STRUCT_ZETA, "k_blocks_z": K_BLOCKS_Z},
        "spindle": {"J": SP_J, "P_loss": SP_P_LOSS, "w_rated": 24000 * math.pi / 30, "T_max": SP_T_MAX,
                    "P_cap": g["P_VFD_LIMIT"] * g["VFD_EFF"] * g["MOTOR_EFF"], "kp": 0.05, "eta_m": g["MOTOR_EFF"], "eta_vfd": g["VFD_EFF"],
                    "P_standby": 15.0},
        "power": {"V_set": g["V_BUS"], "C": C_BUS, "psu_w": g["PSU_W"], "psu_peak": 1.15 * g["PSU_W"], "G": 2000.0, "eta_drv": 0.9,
                  "regen": 0.85, "drv_idle": 6.0, "eta_psu": 0.86, "psu_idle": 4.0, "V_max": V_DRV_MAX, "V_uv": V_DRV_UV,
                  "aux_w": 150 + 60 + 20, "pf_aux": g["AUX_PF"], "pf_vfd": g["VFD_PF"], "mains_v": g["SUPPLY_V"]},
        "cut": {"u": g["U_WOOD"], "r": g["TOOL_D"] / 2000, "k_feed": 0.6},
        "plan": {"jd": 2e-5},
        "limits": {"contour": 100.0, "mains": g["SUPPLY_A"], "rope_mbl": g["ROPE_MBL"],
                   "overrun": {"X": (g["X_TRAVEL"][0] - g["SP_OFF"] - g["COL_W"] / 2 - 45 - g["BLK_L"] / 2) - g["X_BED"][0],
                               "Y": min(g["Y_WORK"][0] - (g["Y_RAIL"][0] + g["YCH"]), (g["Y_RAIL"][1] - g["YCH"]) - g["Y_WORK"][1]), "Z": 10.0}},
        "job": {"park": [g["X_TRAVEL"][0], g["Y_WORK"][0], tip_up], "x": list(g["X_TRAVEL"]), "y": list(g["Y_WORK"]),
                "lim": [list(g["X_TRAVEL"]), list(g["Y_WORK"]), [g["TIP_MIN"], tip_up]], "stock_t": g["STOCK_T"], "tool_d": g["TOOL_D"],
                "feed": g["F_FEED"], "plunge": 1.0, "rpm": 18000, "spinup": 6.0,
                "atc": {"x0": g["ATC_SLIDE0"], "x1": g["ATC_XC"], "y": g["ATC_YC"][0], "z_nose": g["z_nose_atc"] - g["TIP_TO_NOSE"]}},
    }
    return P


def run(P):
    """Every job to its end under Node; the measures the requirements read."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(P, f)
        path = f.name
    try:
        out = subprocess.run(["node", SIM_JS, path], capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(path)
    if out.returncode:
        raise RuntimeError(out.stderr[-2000:])
    return json.loads(out.stdout)


def digest(P):
    """A short fingerprint of the parameters, so a sensitivity sweep can tell whether it is stale."""
    return hashlib.sha1(json.dumps(P, sort_keys=True).encode()).hexdigest()[:12]
