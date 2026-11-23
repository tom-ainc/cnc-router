"""The salvaged 34E1K-120 axis motor: its STEP, the envelope the clash checks use, and where each motor sits."""
from golf_py import Axis, Location, Part, import_step_file
from cnc.params import BLK_H, BLK_Z, COL_D, XD_TOP, Y_RISER, Y_RT, ZC0, ZYP1

MOTOR_STEP = import_step_file("parts/34E1K-120.STEP").parts()[0]
# Its envelope, built from the datasheet and the STEP's cable outlet, so it can be fused and clash-checked
# (R32 checks that the STEP lies inside it).


def _motor_envelope(pad=0.5):
    """Datasheet sizes plus `pad` all round, so it clears the STEP's own faces."""
    body = Part.cuboid(85.86 + 2 * pad, 85.86 + 2 * pad, 172.4 + 2 * pad).moved(Location.translation(0, 0, -86.2))
    pilot = Part.cylinder(36.5 + pad, 1.6 + pad)
    pilot = pilot.moved(Location.translation(0, 0, -pilot.bounding_box().min()[2] - 0.1))
    shaft = Part.cylinder(7.0 + pad, 35.4 + pad)
    shaft = shaft.moved(Location.translation(0, 0, 1.5 - shaft.bounding_box().min()[2]))
    outlet = Part.cuboid(36.0 + 2 * pad, 101.5 + 2 * pad, 173.5 + 2 * pad).moved(Location.translation(-2.35, -93.2, -74.2))  # cables, from the STEP
    return body.fuse_all([pilot, shaft, outlet])


MOTOR = _motor_envelope()


def x_motor_loc(c0, y):      # shaft towards the bed into a 3:1 belt to the pinion, cable outlet away from the column
    return Location.translation(c0 - 55, y, BLK_Z + XD_TOP) * Location.about(Axis.Z, 90) * Location.about(Axis.X, 180)


def y_motor_loc(c0):         # beside the column top, parallel to the screw, shaft up into a 30T:20T belt step-up over the top cap
    return Location.translation(c0 - 50, Y_RT + 40, ZC0 + COL_D - 60) * Location.about(Axis.Y, -90) * Location.about(Axis.X, -90)


def z_motor_loc(c1, ys):     # behind the Y plate, parallel to the Z screw, shaft out past the plate's end into a 40T:20T belt
    return Location.translation(c1 + Y_RISER + BLK_H - 50, ys, ZYP1 + 3.5) * Location.about(Axis.Z, -90)
