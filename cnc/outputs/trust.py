"""How far each result can be trusted (se.report): who set each requirement, what its check rests on."""
import json
from se import fragile, model
from cnc import simulation as SIM
import se as _se
from cnc.checks.dynamics import SIM_P

# ---- how far each result can be trusted (se.report): who set each requirement, what its check rests on
_M = _se._m()
STATED = {"R1", "R2", "R3", "R4", "R6", "R7", "R8", "R57", "R58", "R64"}       # the user's words, sketch or answers
ASSUMED_LIMITS = {"R15", "R16", "R17", "R18", "R19", "R20", "R21", "R22", "R26", "R34", "R35", "R36", "R40", "R41", "R42", "R44",
                  "R45", "R46", "R47", "R56", "R60", "R67", "R69", "R70", "R72", "R74", "R75", "R76", "R77", "R78", "R79",
                  "R80", "R81", "R82", "R83", "R84"}                            # limits the agent chose
for _id, _r in _M.requirements.items():
    if _id in STATED:
        _r.source = "stated"
    elif _id.split("-")[0] in ASSUMED_LIMITS:
        _r.source = "assumed"
    else:
        _r.source = "implied"


def _affects(start, *ids):
    for _a in _M.assumptions.values():
        if _a.text.startswith(start):
            _a.affects += [i for i in ids if i not in _a.affects]


SIM_REQS = ["R69", "R70", "R71", "R72", "R73", "R74", "R75", "R76", "R77", "R78", "R79"]
_affects("Bed tilt is", "R4")
_affects("The 300 on the sketch", "R3")
_affects("Stock up to", "R1", "R2", "R5", "R12", "R14", "R26", "R69")
_affects("Motor torque follows", "R17", "R18", "R19", "R33", "R70")
_affects("Spindle is the 380 V", "R24", "R25", "R26", "R30", "R73", "R74")
_affects("On a future 3-phase", "R17", "R22", "R46", "R47")
_affects("Dust collector and compressor", "R25", "R73")
_affects("Rapids X 15", "R17", "R18", "R19", "R22", "R33", "R44", "R46", "R47", *SIM_REQS)
_affects("The head may overhang", "R8")
for _txt, _why in SIM.ASSUMED:
    _affects(_txt[:30], *SIM_REQS)
for _a in _M.assumptions.values():                                          # what the user has told us is so
    if _a.text.startswith(("Bed tilt is", "The X and Z cable chains may stand above")):
        _a.confirmed = True
model("sim", "time-domain simulation, page/sim.js", checked_by=["R80", "R81", "R82", "R83", "R84"])
for _id in SIM_REQS:
    _M.requirements[_id].depends.append("sim")
# the sensitivity sweep: a pass that fails when a guess is halved or doubled is fragile
try:
    _sens = json.load(open("sensitivity.json"))
except FileNotFoundError:
    _sens = None
if _sens and _sens.get("digest") == SIM.digest(SIM_P):
    for _row in _sens["rows"]:
        for _k, _c in _row["checks"].items():
            if not _c["ok"]:
                fragile(_k.split()[0], f"{_row['name']} is x{_row['f']:g}")
else:
    for _id in SIM_REQS:
        fragile(_id, "the sensitivity sweep is missing or stale (run sensitivity.py)")
