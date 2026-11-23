"""The design as one namespace, for the modules that read it by name (g["NAME"]): parts.detail, parts.electrical,
simulation and assembly.

router.py runs the stages below in this order; namespace() merges what each has defined so far, later stages over
earlier ones, which is what those modules saw when the design was one script.
"""
import sys

STAGES = (
    "cnc.params",
    "cnc.geometry.shapes",
    "cnc.geometry.motor",
    "cnc.geometry.bed",
    "cnc.geometry.moving",
    "cnc.geometry.world",
    "cnc.geometry.pose",
    "cnc.system.tree",
    "cnc.system.requirements",
    "cnc.system.interfaces",
    "cnc.system.assumptions",
    "cnc.checks.travel",
    "cnc.checks.envelope",
    "cnc.checks.clearances",
    "cnc.parts.floor",
    "cnc.parts.items",
    "cnc.checks.stability",
    "cnc.checks.drives",
    "cnc.checks.chains",
    "cnc.checks.structure",
    "cnc.checks.power",
    "cnc.checks.detail_fit",
    "cnc.checks.toolchange",
    "cnc.checks.dynamics",
    "cnc.checks.build",
    "cnc.outputs.build_steps",
    "cnc.outputs.documents",
    "cnc.outputs.page",
    "cnc.outputs.trust",
)


def namespace():
    """Every name the stages run so far define (a stage still running gives what it has defined so far)."""
    g = {}
    for name in STAGES:
        module = sys.modules.get(name)
        if module is not None:
            g.update((k, v) for k, v in vars(module).items() if not k.startswith("__"))
    return g
