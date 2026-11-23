"""The floor frame in detail: rails, cross members, outriggers, rear posts and levelling feet (world frame)."""
import math
from golf_py import Axis, Location
from cnc.parts import detail as D
from cnc.params import FOOT_H, X_BED, Y_RT
from cnc.geometry.shapes import box
from cnc.geometry.bed import BED_BACK
from cnc.geometry.world import OUTRIG_H, Y_FRONT, Y_REAR, ZB0, ZB1, back_hi, front_lo, world, xs_legs

floor_items = []
_fr = front_lo[1]
_feet = [(_x, _y) for _x in xs_legs for _y in (Y_FRONT + 40, Y_REAR - 40)]
def _foot_holes(p):
    return D.drill(p, "-z", [(fx, fy, ZB0) for fx, fy in _feet], 9.0) if True else p
_rail = D.rhs("x", X_BED[0], X_BED[1], Y_REAR - 80, Y_REAR, ZB0, ZB1, 4.0)
floor_items.append(D.item("floor_frame.front_rail", D.rhs("x", X_BED[0], X_BED[1], _fr + 10, _fr + 110, ZB0, ZB1, 4.0), "steel", "made", "RHS 100x50x4 on edge", "world"))
floor_items.append(D.item("floor_frame.rear_rail", _foot_holes(_rail), "steel", "made", "RHS 100x50x4 on edge, 17 mm holes over the feet", "world"))
D.weld("floor_frame.bed_bottom_beam", "B06", "bed.rail_beam_bottom", "floor_frame.front_rail", "fillet both sides of the contact line")
for _i, _x in enumerate(xs_legs):
    floor_items.append(D.item(f"floor_frame.cross_{_i}", D.rhs("y", _x - 40, _x + 40, _fr + 110.5, Y_REAR - 80.5, ZB0, ZB1, 4.0), "steel", "made",
                              "RHS 100x50x4 between the rails", "world"))
    D.weld(f"floor_frame.cross_{_i}_front", "F02", f"floor_frame.cross_{_i}", "floor_frame.front_rail", "fillet all round")
    D.weld(f"floor_frame.cross_{_i}_rear", "F02", f"floor_frame.cross_{_i}", "floor_frame.rear_rail", "fillet all round")
    _out = D.rhs("y", _x - 39, _x + 39, Y_FRONT, _fr + 9.5, ZB0 + 0.5, ZB0 + OUTRIG_H, 4.0)
    floor_items.append(D.item(f"floor_frame.outrigger_{_i}", _foot_holes(_out), "steel", "made",
                              "RHS 100x50x4 laid flat, welded to the front rail; 17 mm hole over the foot", "world"))
    D.weld(f"floor_frame.outrigger_{_i}", "F02", f"floor_frame.outrigger_{_i}", "floor_frame.front_rail", "fillet all round")
    _a = (_x, Y_REAR - 40, ZB1 - 20)
    _b = (_x, back_hi[1], back_hi[2])
    _L = math.dist(_a, _b)
    _ang = math.degrees(math.atan2(_b[2] - _a[2], _b[1] - _a[1]))
    _post = D.rhs("y", -29, 29, -_L / 2 - 60, _L / 2 + 60, -29, 29, 4.0).moved(Location.about(Axis.X, _ang)).moved(Location.translation(_x, (_a[1] + _b[1]) / 2, (_a[2] + _b[2]) / 2))
    # ends cut to fit: on the rear rail's top face, and on the top beam's back face
    _post = _post - box(_x - 100, _x + 100, Y_REAR - 400, Y_REAR + 400, ZB1 - 400, ZB1)
    _post = _post - world(box(X_BED[0] - 10, X_BED[1] + 10, Y_RT - 400, Y_RT + 400, BED_BACK, BED_BACK + 500))
    floor_items.append(D.item(f"floor_frame.rear_post_{_i}", _post, "steel", "made", "SHS 60x60x4 (58 modelled), ends cut to fit, welded", "world"))
    D.weld(f"floor_frame.rear_post_{_i}_rail", "F04", f"floor_frame.rear_post_{_i}", "floor_frame.rear_rail", "fillet all round")
    D.weld(f"floor_frame.rear_post_{_i}_bed", "B06", f"floor_frame.rear_post_{_i}", "bed.rail_beam_top", "fillet all round")
    for _k, _y in enumerate((Y_FRONT + 40, Y_REAR - 40)):
        _host = f"floor_frame.outrigger_{_i}" if _k == 0 else "floor_frame.rear_rail"
        _top = FOOT_H + (0.5 if _k == 0 else 0.0)
        floor_items.append(D.item(f"feet.foot_{_i}_{_k}", D.levelling_foot(_x, _y, _top, FOOT_H), "steel", "bought", "M16 levelling foot, 80 pad, lock nut", "world"))
        floor_items.append(D.item(f"floor_frame.foot_nut_{_i}_{_k}", D.foot_nut(_x, _y, _top), "steel", "bought", "M16 nut, welded under the rail", "world"))
        D.weld(f"floor_frame.foot_nut_{_i}_{_k}", "F01", f"floor_frame.foot_nut_{_i}_{_k}", _host, "tack 3 sides")
        D.screw(f"feet.foot_{_i}_{_k}", "F01", [f"floor_frame.foot_nut_{_i}_{_k}"], "STUD", 16, [(_x, _y, 16.0)], (0, 0, 1), grip=_top - 13 - 16,
                L=_top + 4.0 - 16.0, into="nut")
