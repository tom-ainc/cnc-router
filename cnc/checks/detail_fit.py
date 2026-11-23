"""R51, R53, R50: the detailed parts against the masses and envelopes the checks above used."""
from cnc.params import M_CW, M_SP, M_YC, M_ZA
from cnc.geometry.shapes import Bounds, fuse
from cnc.geometry.bed import atc, bed, rack_b, rack_t, rail_b, rail_t, spoil, stock, substrate, xchain
from cnc.geometry.moving import counterweight, gantry, head
from cnc.geometry.world import base, feet
from cnc.geometry.pose import REF
from cnc.system.requirements import require
from cnc.parts.items import items, kg_group, kg_spindle, kg_y, kg_z

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
        _b, _eb = _it["part"].bounding_box(), Bounds(ENV[_it["group"]])
        _v = max(0.0, max(_eb.min()[i] - _b.min()[i] for i in range(3)), max(_b.max()[i] - _eb.max()[i] for i in range(3))) * 1000
    require("R50", "Every detailed part shall lie inside the envelope the clash checks used", _v, "<=", 1.0, "mm^3", case=_it["name"])
