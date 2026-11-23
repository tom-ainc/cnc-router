"""The build, step by step (assembly.py): cable routes, the procedure, its units, joints and space checks."""
import time as _time
from golf_py import Axis
from cnc import assembly as A
from cnc.parts import detail as D
from cnc.parts import electrical as EL
from cnc.params import COL_D, COL_W, M_KG, SP_OFF, TILT, TIP_TO_NOSE, X_TRAVEL, Y_RB, Y_WORK, ZC0, ZN_MAX
from cnc.geometry.world import W, wpt, xs_legs
from cnc.system.requirements import require
from cnc.parts.items import items
from cnc.design import namespace

X_ASM = (xs_legs[1] + xs_legs[2]) / 2 + SP_OFF + COL_W / 2     # gantry station while it is built: column between two floor legs
UNIT_PIVOT_H = {"column": wpt(X_ASM - SP_OFF - COL_W / 2, Y_RB - 40, ZC0 + COL_D / 2)[2]}
MOTORS = A.MOTORS
CABLE_ROUTES = EL.routes(namespace(), items)
CABLE_M = EL.check(namespace(), items, require, CABLE_ROUTES)
CABLE_NAMES = EL.cable_names()
EXTRA_KG = {n: CABLE_M.get(n, 2.0) * (dict((c[0], c[3]) for c in EL.CABLE_LIST).get(n, 0.02)) for n in CABLE_NAMES}
ASM_PARK = (X_TRAVEL[0], Y_WORK[0], ZN_MAX - TIP_TO_NOSE)
ASM_POSE0 = (X_ASM, (Y_WORK[0] + Y_WORK[1]) / 2, ZN_MAX - TIP_TO_NOSE)
ASM_STEPS = A.procedure(namespace())
ASM_UNITS = A.check(namespace(), items, require, M_KG, None)
_t0 = _time.time()
JOINT_RESULTS = A.check_joints(namespace(), items, require, D.JOINTS, D.WELDS)
print(f"joints: {len(D.JOINTS)} joints, {sum(len(j['pts']) for j in D.JOINTS)} fasteners, {len(D.WELDS)} welds, {_time.time() - _t0:.0f} s")
TILT_AXIS = (Axis.X, 90 - TILT)
_t0 = _time.time()
A.check_space(namespace(), items, require, D.JOINTS, W)
print(f"space checks {_time.time() - _t0:.0f} s")
