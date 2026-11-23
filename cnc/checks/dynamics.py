"""R69-R84: the time-domain simulation (simulation.py runs page/sim.js under Node) and its verification.
Writes sim_params.json."""
import json
from se import assume
from cnc import simulation as SIM
from cnc.params import BLK_L, COL_W, PSU_W, ROPE_MBL, SP_OFF, SUPPLY_A, X_BED, X_TRAVEL, YCH, Y_RAIL, Y_WORK
from cnc.system.requirements import require
from cnc.design import namespace

SIM_P = SIM.params(namespace())
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
json.dump(SIM_P, open("sim_params.json", "w"))
print("verification", json.dumps(SIM_V)[:600], f"{SIM_R['_ms_verify']} ms")
