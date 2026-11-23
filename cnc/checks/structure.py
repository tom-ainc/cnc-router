"""R22, R44-R49: deflection of the structure under the cut."""
import math
from cnc.params import COL_D, COL_T, COL_W, F_CUT, F_CUT_3PH, SPOIL_T, SP_OFF, TILT, X_BED, Y_RB, Y_RT
from cnc.geometry.bed import CROSS, RAIL_BEAM, SUBSTRATE_T, n_cross
from cnc.geometry.world import N_LEGS
from cnc.system.requirements import cannot_check, require
from cnc.checks.stability import m_gantry
from cnc.checks.drives import G

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
