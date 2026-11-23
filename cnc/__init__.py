"""The tilted-bed CNC router's design, as router.py runs it.

    params.py        stated and assumed values, catalogue sizes, design variables, derived positions
    geometry/        coarse solids for the clash checks: shapes, motor, bed, moving (gantry, head,
                     counterweight), world (tilt, floor frame), pose
    system/          product tree, require() defaulting to the parts each requirement is about,
                     interfaces, assumptions
    parts/           the detailed parts: detail (bed, gantry, head, ...), fasteners, electrical,
                     floor, items (every part with its colour and mass)
    checks/          one module per topic of requirements, run in router.py's order
    simulation.py    the dynamic model (page/sim.js under Node) and its parameters
    assembly.py      the build procedure and its checks
    outputs/         build steps, documents (cut list, parts lists, cable list, procedure), the
                     page's data, how far each result can be trusted
    design.py        namespace(): the design's names for the modules that read them as g["NAME"]

Each stage runs as it is imported. Import it from router.py, not on its own: a stage expects the
ones before it to have run.
"""
