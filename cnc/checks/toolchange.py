"""R52, R54: tool change at each pocket of the tool rack."""
from golf_py import Location
from se import _shared
from cnc.parts import detail as D
from cnc.params import ATC_X, ATC_XC, ATC_YC, FORK_Z, SP_L, SP_REAR, SP_W, TIP_TO_NOSE, TOOL_D, TOOL_STICK
from cnc.geometry.moving import head
from cnc.system.requirements import require
from cnc.parts.items import items

# ---- tool change: the empty spindle comes down over a holder in its fork, then retracts
z_nose_atc = FORK_Z + 10.5
ATC_SLIDE0 = ATC_X[0] - 10 - 23 - 2           # holder flange just clear of the fork slot's mouth
atc_items = [it for it in items if it["name"].startswith("atc_rack.")]
for _k, _yc in enumerate(ATC_YC):
    _tip = z_nose_atc - TIP_TO_NOSE
    _car, _za, _, _ = head(ATC_XC, _yc, _tip)
    _sp = D.c_spindle(SP_L, SP_W, SP_REAR).moved(Location.translation(ATC_XC, _yc, z_nose_atc))
    for _mn, _mv in (("carriage", _car), ("Z axis", _za), ("spindle", _sp)):
        _vol = sum(_shared(_mv, it["part"]) for it in atc_items if it["name"] != f"atc_rack.holder_{_k}")
        require("R52", "At each tool pocket the empty spindle, Z axis and carriage shall clear the fork plate, its stands and the other holders",
                _vol, "<=", 0, "mm^3", case=f"pocket {_k}: {_mn}")
    # sliding a held tool in along +x through the fork slot, from just clear of the fork; the cutter passes over the
    # spoilboard's edge and beside the thickest sheet
    _h, _t = D.c_holder(TOOL_D, TOOL_STICK)
    _held = (_h + _t).moved(Location.translation(ATC_SLIDE0, _yc, z_nose_atc))
    _obst = atc_items + [it for it in items if it["name"].startswith("bed.spoilboard") or it["name"] == "sheet"]
    for _s in range(6):
        _p = _held.fork().moved(Location.translation((ATC_XC - ATC_SLIDE0) * _s / 5, 0, 0))
        _vol = sum(_shared(_p, it["part"]) for it in _obst if it["name"] != f"atc_rack.holder_{_k}")
        require("R54", "A held tool shall slide into its fork through the slot without touching the fork, the other holders, the spoilboard or a 25 mm sheet",
                _vol, "<=", 0, "mm^3", case=f"pocket {_k}, step {_s} of 5")
