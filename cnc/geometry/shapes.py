"""Primitive solids and the helpers the envelopes are built from."""
from golf_py import Axis, Location, Part


def fuse(parts):
    parts = list(parts)
    # fuse_all changes its part in golf: fuse into a copy, so the parts given stay as they are
    return parts[0].fork().fuse_all(parts[1:]) if len(parts) > 1 else parts[0]


def box(x0, x1, y0, y1, z0, z1):
    return Part.cuboid(x1 - x0, y1 - y0, z1 - z0).moved(
        Location.translation((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def cyl_z(cx, cy, r, z0, z1):
    c = Part.cylinder(r, z1 - z0)
    b = c.bounding_box()
    return c.moved(Location.translation(cx, cy, z0 - b.min()[2]))


def cyl_y(cx, cz, r, y0, y1):
    """A cylinder along y."""
    c = Part.cylinder(r, y1 - y0).moved(Location.about(Axis.X, -90))
    b = c.bounding_box()
    return c.moved(Location.translation(cx - (b.min()[0] + b.max()[0]) / 2, y0 - b.min()[1], cz - (b.min()[2] + b.max()[2]) / 2))


class Bounds:
    """The bounding box of several parts, without fusing them."""
    def __init__(self, parts):
        bs = [p.bounding_box() for p in parts]
        self._min = tuple(min(b.min()[i] for b in bs) for i in range(3))
        self._max = tuple(max(b.max()[i] for b in bs) for i in range(3))

    def min(self):
        return self._min

    def max(self):
        return self._max
