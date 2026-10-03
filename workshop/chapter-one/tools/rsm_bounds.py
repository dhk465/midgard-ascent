"""Conservative static RSM 1.4 bounds matching pinned roBrowserLegacy.

Reference: local/test-20261002/.../dist/Web/ThreadEventHandler.js,
Node.calcBoundingBox/compile and RSM.createInstance (lines 17100–17595).
No asset writes. Unsupported/corrupt inputs raise UnsupportedModel: callers must
skip/report them rather than substituting origin-only bounds. Units are source
RSM/RSW units, before the renderer's /5 conversion and map offset.
"""
from dataclasses import dataclass
import itertools
import math
import struct


class UnsupportedModel(ValueError):
    """No trustworthy static bound can be returned for this input."""


@dataclass(frozen=True)
class Bounds:
    """Renderer-recentered 3D AABB; all vertices included conservatively."""
    minimum: tuple
    maximum: tuple
    textures: tuple
    numeric_error: float = 0.0


class _Reader:
    def __init__(self, raw):
        self.raw, self.p = raw, 0

    def take(self, size):
        if size < 0 or self.p + size > len(self.raw):
            raise UnsupportedModel('Truncated RSM')
        out = self.raw[self.p:self.p + size]
        self.p += size
        return out

    def unpack(self, fmt):
        values = struct.unpack('<' + fmt, self.take(struct.calcsize('<' + fmt)))
        if any(isinstance(v, float) and (not math.isfinite(v) or abs(v) > 1e12) for v in values):
            raise UnsupportedModel('Nonfinite or excessive model value')
        return values

    def count(self, stride=1):
        n, = self.unpack('i')
        if n < 0 or n > 1000000 or n * stride > len(self.raw) - self.p:
            raise UnsupportedModel('Invalid RSM count')
        return n

    def name(self):
        return self.take(40).split(b'\0')[0]


def _identity():
    return [[float(i == j) for j in range(4)] for i in range(4)]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def _translate(v):
    m = _identity()
    for i in range(3):
        m[i][3] = v[i]
    return m


def _scale(v):
    m = _identity()
    for i in range(3):
        m[i][i] = v[i]
    return m


def _rotate(angle, axis):
    length = math.sqrt(sum(x*x for x in axis))
    # gl-matrix rotate returns null without changing its destination for zero axis.
    if length < 1e-6:
        return _identity()
    x, y, z = (v / length for v in axis)
    c, s, t = math.cos(angle), math.sin(angle), 1 - math.cos(angle)
    m = _identity()
    m[:3] = [[t*x*x+c, t*x*y-s*z, t*x*z+s*y, 0],
             [t*x*y+s*z, t*y*y+c, t*y*z-s*x, 0],
             [t*x*z-s*y, t*y*z+s*x, t*z*z+c, 0]]
    return m


def _point(matrix, v):
    out = tuple(sum(matrix[i][j] * v[j] for j in range(3)) + matrix[i][3] for i in range(3))
    if any(not math.isfinite(x) or abs(x) > 1e12 for x in out):
        raise UnsupportedModel('Nonfinite or excessive transformed geometry')
    return out


def model_bounds(raw):
    """Return Bounds, or raise UnsupportedModel for unsupported/corrupt RSM.

    Rotation keyframes and model position keyframes are deliberately unsupported,
    including single keys. Header animLen alone does not imply animated geometry.
    Volume boxes do not render and are ignored after validating their records.
    """
    r = _Reader(raw)
    if r.take(6) != b'GRSM\x01\x04':
        raise UnsupportedModel('Requires RSM 1.4')
    r.unpack('iiB')
    r.take(16)
    textures = tuple(r.name() for _ in range(r.count(40)))
    main = r.name()
    count = r.count(80)
    if not count:
        raise UnsupportedModel('Empty RSM')
    nodes = []
    for _ in range(count):
        name, parent = r.name(), r.name()
        ids = [r.unpack('i')[0] for _ in range(r.count(4))]
        if any(i < 0 or i >= len(textures) for i in ids):
            raise UnsupportedModel('Invalid texture index')
        basis = r.unpack('9f')
        offset, pos = r.unpack('3f'), r.unpack('3f')
        angle, = r.unpack('f')
        axis, scale = r.unpack('3f'), r.unpack('3f')
        vertices = [r.unpack('3f') for _ in range(r.count(12))]
        uv_count = r.count(12)
        for _ in range(uv_count):
            r.unpack('I2f')
        for _ in range(r.count(24)):
            face = r.unpack('8H2i')
            if any(i >= len(vertices) for i in face[:3]) or any(i >= uv_count for i in face[3:6]) or face[6] >= len(ids):
                raise UnsupportedModel('Invalid face index')
        if r.count(20):
            raise UnsupportedModel('Animated rotation keys unsupported')
        nodes.append((name, parent, basis, offset, pos, angle, axis, scale, vertices))
    if r.count(20):
        raise UnsupportedModel('Animated position keys unsupported')
    if r.p < len(raw):
        for _ in range(r.count(40)):
            r.unpack('9fi')
    if r.p != len(raw):
        raise UnsupportedModel('Trailing RSM data')
    by_name = {n[0]: n for n in nodes}
    if len(by_name) != len(nodes):
        raise UnsupportedModel('Duplicate node names')
    root = by_name.get(main, nodes[0])
    points, seen = [], set()
    numeric_error = 0.0
    stack = [(root, _identity(), 0)]
    while stack:
        node, inherited, depth = stack.pop()
        if node[0] in seen or depth > 128:
            raise UnsupportedModel('Cyclic or excessive node hierarchy')
        seen.add(node[0])
        name, parent, basis, offset, pos, angle, axis, scale, vertices = node
        matrix = _mul(_mul(_mul(inherited, _translate(pos)), _rotate(angle, axis)), _scale(scale))
        geometry = _mul(matrix, _translate(offset)) if count > 1 else matrix
        b = _identity()
        for i in range(3):
            for j in range(3):
                b[i][j] = basis[j*3+i]  # file/gl-matrix column-major
        final = _mul(geometry, b)
        # Include cancelling intermediate terms, not only final coordinates.
        magnitude = max(1, *(abs(x) for row in matrix for x in row))
        for v in vertices:
            magnitude = max(magnitude, *(sum(abs(final[i][j]*v[j]) for j in range(3)) + abs(final[i][3]) for i in range(3)))
            points.append(_point(final, v))
        numeric_error = max(numeric_error, .001 + 1e-5*magnitude*(depth+1))
        if name != parent:
            stack.extend((child, matrix, depth + 1) for child in nodes if child[1] == name)
    if len(seen) != count or not points:
        raise UnsupportedModel('Disconnected hierarchy or empty geometry')
    lo = tuple(min(p[i] for p in points) for i in range(3))
    hi = tuple(max(p[i] for p in points) for i in range(3))
    center = ((lo[0]+hi[0])/2, hi[1], (lo[2]+hi[2])/2)
    return Bounds(tuple(lo[i]-center[i] for i in range(3)),
                  tuple(hi[i]-center[i] for i in range(3)), textures, numeric_error*2)


def instance_bounds(raw, obj):
    """(minx,maxx,minz,maxz), conservative AABB of source 252-byte RSW object.

    Transforms all eight recentered 3D AABB corners, so X/Z rotation includes
    vertical extent. Padding covers ordinary Float32 renderer rounding (0.001
    source units plus 1e-5 relative). Extreme arithmetic is rejected explicitly.
    """
    if len(obj) != 252 or struct.unpack_from('<i', obj)[0] != 1:
        raise UnsupportedModel('Requires 252-byte RSW model object')
    b = model_bounds(raw)
    pos = struct.unpack_from('<3f', obj, 216)
    rot = struct.unpack_from('<3f', obj, 228)
    scale = struct.unpack_from('<3f', obj, 240)
    if any(not math.isfinite(v) or abs(v) > 1e12 for v in pos + rot + scale):
        raise UnsupportedModel('Invalid instance transform')
    matrix = _translate(pos)
    for angle, axis in ((rot[2], (0,0,1)), (rot[0], (1,0,0)), (rot[1], (0,1,0))):
        matrix = _mul(matrix, _rotate(math.radians(angle), axis))
    matrix = _mul(matrix, _scale(scale))
    points = [_point(matrix, p) for p in itertools.product(*zip(b.minimum, b.maximum))]
    magnitude = max(1, *map(abs, pos), *(sum(abs(matrix[i][j]*p[j]) for j in range(3)) for p in itertools.product(*zip(b.minimum, b.maximum)) for i in range(3)))
    pad = .001 + 1e-5*magnitude + b.numeric_error*max(sum(abs(matrix[i][j]) for j in range(3)) for i in range(3))
    return (min(p[0] for p in points)-pad, max(p[0] for p in points)+pad,
            min(p[2] for p in points)-pad, max(p[2] for p in points)+pad)
