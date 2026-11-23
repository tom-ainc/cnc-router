"""require and cannot_check, defaulting each requirement to the parts it is about; clear_travel."""
from se import _shared, cannot_check, require

# which parts of the product tree each requirement is about (drives the viewer's highlighting)
OF = {"R1": ["GAN"], "R2": ["YC"], "R3": ["ZA"], "R4": ["BED"], "R5": ["ZA", "SP"], "R6": ["P"], "R7": ["BASE"],
      "R8": ["BED", "BASE"], "R11": ["GAN", "YC", "ZA", "SP"], "R12": ["GAN", "YC", "ZA", "SP"], "R13": ["YC", "ZA", "SP"],
      "R14": ["GAN", "ATC"], "R15": ["BASE"], "R16": ["BASE"], "R17": ["GAN"], "R18": ["YC"], "R19": ["ZA"], "R20": ["YC"],
      "R21": ["YC"], "R22": ["GAN"], "R23": ["ELEC", "SP"], "R24": ["ELEC", "SP"], "R25": ["ELEC"], "R26": ["SP"],
      "R27": ["ELEC"], "R28": ["BED"], "R29": ["GAN", "YC", "ZA", "SP"], "R30": ["SP"], "R31": ["SP"], "R33": ["ELEC"], "R34": ["YC"], "R35": ["GAN"], "R36": ["GAN"],
      "R37": ["GAN"], "R38": ["GAN", "YC"], "R39": ["ZA", "YC"], "R40": ["YC", "ZA"], "R41": ["ELEC"], "R42": ["ELEC"], "R43": ["ELEC"], "R50": ["P"], "R51": ["YC", "ZA", "SP", "GAN"], "R52": ["ATC", "SP"], "R53": ["GAN"], "R54": ["ATC"], "R55": ["GAN", "YC", "ELEC"], "R56": ["BED", "GAN"],
      "R44": ["BED"], "R45": ["BED"], "R46": ["GAN"], "R47": ["GAN", "BED"],
      "R48": ["BED", "GAN"], "R49": ["BED", "GAN", "BASE"],
      "R57": ["P"], "R58": ["P"], "R59": ["P"], "R60": ["P"], "R61": ["P"], "R62": ["P"], "R63": ["ELEC"], "R64": ["P"], "R65": ["P"], "R66": ["P"], "R67": ["ELEC"], "R68": ["P"]}
_require, _cannot = require, cannot_check


def require(id, *a, **k):
    k.setdefault("of", OF.get(id, "P"))
    return _require(id, *a, **k)


def cannot_check(id, *a, **k):
    k.setdefault("of", OF.get(id, "P"))
    return _cannot(id, *a, **k)


def clear_travel(id, moving, fixed, place, tag, text, steps=9):
    """require_clear_travel with a tag on each case, for one requirement checked in several poses."""
    for i in range(steps):
        there = moving.fork().moved(place(i / (steps - 1)))
        for name, other in fixed.items():
            require(id, text, _shared(there, other), "<=", 0, "mm^3", case=f"{tag}: {name}, step {i} of {steps - 1}")
