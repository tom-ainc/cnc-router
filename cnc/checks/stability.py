"""R15, R16: masses, centre of mass and tipping."""
from cnc.params import M_CW, M_HEAD, M_KG, M_SP, M_YC, M_ZA, TIP_MIN, TIP_TO_NOSE, Y_WORK, ZN_MAX
from cnc.geometry.bed import atc, spoil, stock
from cnc.geometry.moving import counterweight, head
from cnc.geometry.world import Y_FRONT, Y_REAR, base, bed_w, world
from cnc.geometry.pose import POSE, g_frame, g_other, h_car, h_sp, h_z
from cnc.system.tree import N_ATC, N_BASE, N_BED, N_ELEC, N_GAN, N_SP, N_YC, N_ZA
from cnc.system.requirements import require
from cnc.checks.envelope import zmax
from cnc.parts.items import items


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
