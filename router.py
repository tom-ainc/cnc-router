"""Horizontal (tilted-bed) CNC router for a full 2400 x 1200 sheet - concept design.

Local machine frame (before tilting):  x = along the sheet's 2400 length,
y = up the bed slope (sheet bottom edge at y = 0), z = normal to the bed, towards the operator
(spoilboard face at z = 0).  The bed is then tilted back TILT degrees from vertical.
World frame: X = along the machine, Y = front (-) to back (+), Z = up, floor at Z = 0.

The design is the cnc package. Each stage runs its part of the design and its checks as it is imported, in the order
below (cnc.design.STAGES lists the same order); report() ends the run. Run with golf (golf run router.py), or in plain
Python with dev.py.
"""
from se import report

import cnc.params  # noqa: F401
import cnc.geometry.shapes  # noqa: F401
import cnc.geometry.motor  # noqa: F401
import cnc.geometry.bed  # noqa: F401
import cnc.geometry.moving  # noqa: F401
import cnc.geometry.world  # noqa: F401
import cnc.geometry.pose  # noqa: F401
import cnc.system.tree  # noqa: F401
import cnc.system.requirements  # noqa: F401
import cnc.system.interfaces  # noqa: F401
import cnc.system.assumptions  # noqa: F401
import cnc.checks.travel  # noqa: F401
import cnc.checks.envelope  # noqa: F401
import cnc.checks.clearances  # noqa: F401
import cnc.parts.floor  # noqa: F401
import cnc.parts.items  # noqa: F401
from cnc.geometry.world import world
from cnc.parts.items import items

for _it in items:                          # the detailed parts, placed in the world
    show(_it["part"] if _it["group"] == "world" else world(_it["part"]), _it["name"], colour=_it["colour"], group=_it["name"].split(".")[0])

import cnc.checks.stability  # noqa: F401
import cnc.checks.drives  # noqa: F401
import cnc.checks.chains  # noqa: F401
import cnc.checks.structure  # noqa: F401
import cnc.checks.power  # noqa: F401
import cnc.checks.detail_fit  # noqa: F401
import cnc.checks.toolchange  # noqa: F401
import cnc.checks.dynamics  # noqa: F401
import cnc.checks.build  # noqa: F401
import cnc.outputs.build_steps  # noqa: F401
import cnc.outputs.documents  # noqa: F401
import cnc.outputs.page  # noqa: F401
import cnc.outputs.trust  # noqa: F401

report(baseline="systems_baseline.json")
