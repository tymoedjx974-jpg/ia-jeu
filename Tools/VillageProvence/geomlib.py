"""Construction de maillages (repère droit, z vers le haut, mètres ; UV à la convention Unreal : v vers le bas)."""
import math
import numpy as np
import mapbox_earcut as earcut

WHITE = (255, 255, 255, 255)


def nrm(v):
    v = np.asarray(v, np.float64)
    l = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(l, 1e-12)


class MB:
    """Accumulateur de triangles par matériau (indices locaux à chaque bloc, fusionnés à la fin)."""

    def __init__(self):
        self.parts = {}

    def _p(self, mat):
        if mat not in self.parts:
            self.parts[mat] = dict(P=[], N=[], UV=[], C=[], I=[])
        return self.parts[mat]

    def add(self, mat, P, N, UV, C, I):
        P = np.asarray(P, np.float32).reshape(-1, 3)
        if len(P) == 0:
            return
        p = self._p(mat)
        N = np.asarray(N, np.float32).reshape(-1, 3)
        if len(N) == 1 and len(P) > 1:
            N = np.repeat(N, len(P), 0)
        UV = np.asarray(UV, np.float32).reshape(-1, 2)
        C = np.asarray(C, np.uint8).reshape(-1, 4)
        if len(C) == 1 and len(P) > 1:
            C = np.repeat(C, len(P), 0)
        p["P"].append(P)
        p["N"].append(N)
        p["UV"].append(UV)
        p["C"].append(C)
        p["I"].append(np.asarray(I, np.int64).reshape(-1, 3))

    def quad(self, mat, a, b, c, d, uvs, col=WHITE, n=None):
        a, b, c, d = (np.asarray(x, np.float64) for x in (a, b, c, d))
        if n is None:
            n = nrm(np.cross(b - a, c - a) + np.cross(c - a, d - a))
        self.add(mat, [a, b, c, d], [n], uvs, [col], [[0, 1, 2], [0, 2, 3]])

    def extend(self, other, offset=None):
        for mat, p in other.parts.items():
            q = self._p(mat)
            for k in ("N", "UV", "C", "I"):
                q[k] += p[k]
            q["P"] += p["P"] if offset is None else [P + np.asarray(offset, np.float32) for P in p["P"]]

    def arrays(self):
        out = {}
        for mat, p in self.parts.items():
            if not p["P"]:
                continue
            offs = np.cumsum([0] + [len(P) for P in p["P"][:-1]])
            out[mat] = dict(P=np.concatenate(p["P"]), N=np.concatenate(p["N"]), UV=np.concatenate(p["UV"]),
                            C=np.concatenate(p["C"]), I=np.concatenate([I + o for I, o in zip(p["I"], offs)]).astype(np.int32))
        return out

    def tri_count(self):
        return sum(sum(len(i) for i in p["I"]) for p in self.parts.values())


def triangulate(outer, holes=()):
    """Triangule un polygone 2D (avec trous). Renvoie (sommets (K,2), indices (M,3)) orientés dans le sens direct."""
    rings = [np.asarray(outer, np.float64)[:, :2]]
    for h in holes:
        rings.append(np.asarray(h, np.float64)[:, :2])
    rings = [r[:-1] if len(r) > 3 and np.allclose(r[0], r[-1]) else r for r in rings]
    verts = np.concatenate(rings)
    ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
    idx = np.asarray(earcut.triangulate_float64(verts, ends), np.int64).reshape(-1, 3)
    if len(idx) == 0:
        return verts, idx
    a, b, c = verts[idx[:, 0]], verts[idx[:, 1]], verts[idx[:, 2]]
    area = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    flip = area < 0
    idx[flip] = idx[flip][:, [0, 2, 1]]
    idx = idx[np.abs(area) > 1e-10]
    return verts, idx


def planar_polygon(mb, mat, outer2d, holes2d, origin, e1, e2, uv_fn, col=WHITE):
    """Polygone plan défini dans le repère (origin, e1, e2) ; la normale est e1 x e2."""
    v2, idx = triangulate(outer2d, holes2d)
    if len(idx) == 0:
        return
    origin, e1, e2 = (np.asarray(x, np.float64) for x in (origin, e1, e2))
    P = origin + v2[:, :1] * e1 + v2[:, 1:2] * e2
    n = nrm(np.cross(e1, e2))
    mb.add(mat, P, [n], uv_fn(v2, P), [col], idx)


def box(mb, mat, center, size, yaw=0.0, col=WHITE, uv_scale=1.0, faces="all", pitch=0.0):
    """Pavé orienté (yaw autour de z). size = (sx, sy, sz). UV en mètres / uv_scale."""
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    if pitch:
        cp, sp = math.cos(pitch), math.sin(pitch)
        R = R @ np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    corners = np.array([[x, y, z] for z in (-sz, sz) for y in (-sy, sy) for x in (-sx, sx)])
    W = corners @ R.T + np.array([cx, cy, cz])
    F = {  # indices des coins (x,y,z) -> 0..7 ; ordre direct vu de l'extérieur
        "-z": (0, 2, 3, 1), "+z": (4, 5, 7, 6), "-y": (0, 1, 5, 4), "+y": (2, 6, 7, 3), "-x": (0, 4, 6, 2), "+x": (1, 3, 7, 5)}
    dims = {"-z": (2 * sx, 2 * sy), "+z": (2 * sx, 2 * sy), "-y": (2 * sx, 2 * sz), "+y": (2 * sx, 2 * sz), "-x": (2 * sy, 2 * sz), "+x": (2 * sy, 2 * sz)}
    for f, ids in F.items():
        if faces != "all" and f not in faces:
            continue
        w, h = dims[f]
        u, v = w / uv_scale, h / uv_scale
        mb.quad(mat, W[ids[0]], W[ids[1]], W[ids[2]], W[ids[3]], [(0, v), (u, v), (u, 0), (0, 0)], col)


def frames_along(pts):
    """Repères de transport parallèle le long d'une polyligne 3D."""
    pts = np.asarray(pts, np.float64)
    T = np.gradient(pts, axis=0)
    T = nrm(T)
    up = np.array([0, 0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0, 0])
    N0 = nrm(np.cross(np.cross(T[0], up), T[0]))
    Ns = [N0]
    for i in range(1, len(pts)):
        v = np.cross(T[i - 1], T[i])
        s = np.linalg.norm(v)
        n = Ns[-1]
        if s > 1e-8:
            ax = v / s
            ang = math.atan2(s, np.dot(T[i - 1], T[i]))
            n = n * math.cos(ang) + np.cross(ax, n) * math.sin(ang) + ax * np.dot(ax, n) * (1 - math.cos(ang))
        Ns.append(nrm(n))
    Ns = np.array(Ns)
    Bs = np.cross(T, Ns)
    return T, Ns, Bs


def tube(mb, mat, pts, radii, segs=8, col=WHITE, u_tile=1.0, v_tile=1.0, arc=2 * math.pi, arc0=0.0, cap_end=False, cols=None):
    """Tube (ou demi-tube si arc < 2pi) le long d'une polyligne 3D."""
    pts = np.asarray(pts, np.float64)
    if len(pts) < 2:
        return
    radii = np.broadcast_to(np.asarray(radii, np.float64), (len(pts),))
    T, Nn, Bn = frames_along(pts)
    full = arc >= 2 * math.pi - 1e-6
    ring = segs + 1
    angs = arc0 + np.linspace(0, arc, ring)
    seglen = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    P, N, UV, C = [], [], [], []
    for i in range(len(pts)):
        for k, a in enumerate(angs):
            d = Nn[i] * math.cos(a) + Bn[i] * math.sin(a)
            P.append(pts[i] + d * radii[i])
            N.append(d)
            circ = arc * max(radii[i], 1e-3)
            UV.append((k / segs * circ / u_tile, -seglen[i] / v_tile))
            C.append(col if cols is None else cols[i])
    I = []
    for i in range(len(pts) - 1):
        for k in range(segs):
            a = i * ring + k
            b = a + 1
            c = a + ring + 1
            d = a + ring
            I += [(a, c, d), (a, b, c)]
    mb.add(mat, P, N, UV, C, I)
    if cap_end:
        center = pts[-1]
        base = len(P)
        idx = [((len(pts) - 1) * ring + k) for k in range(segs)]
        Pc = [center] + [P[j] for j in idx]
        Nc = [T[-1]] * (segs + 1)
        UVc = [(0.5, 0.5)] + [(0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)) for a in angs[:-1]]
        Ic = [(0, k + 1, (k + 1) % segs + 1) for k in range(segs)]
        mb.add(mat, Pc, Nc, UVc, [col], Ic)


def revolve(mb, mat, profile, center, segs=16, col=WHITE, u_tile=1.0, v_tile=1.0, flip=False):
    """Surface de révolution autour de z. profile : liste (rayon, z) de bas en haut."""
    cx, cy, cz = center
    prof = np.asarray(profile, np.float64)
    ring = segs + 1
    P, N, UV = [], [], []
    L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(prof, axis=0), axis=1))])
    for i, (r, z) in enumerate(prof):
        if i == 0:
            dr, dz = prof[1] - prof[0]
        elif i == len(prof) - 1:
            dr, dz = prof[-1] - prof[-2]
        else:
            dr, dz = prof[i + 1] - prof[i - 1]
        nr, nz = dz, -dr
        ln = math.hypot(nr, nz) or 1
        nr, nz = nr / ln, nz / ln
        if flip:
            nr, nz = -nr, -nz
        for k in range(ring):
            a = 2 * math.pi * k / segs
            ca, sa = math.cos(a), math.sin(a)
            P.append((cx + r * ca, cy + r * sa, cz + z))
            N.append((nr * ca, nr * sa, nz))
            UV.append((k / segs * 2 * math.pi * max(r, 0.05) / u_tile, -L[i] / v_tile))
    I = []
    for i in range(len(prof) - 1):
        for k in range(segs):
            a = i * ring + k
            b = a + 1
            c = a + ring + 1
            d = a + ring
            I += [(a, b, c), (a, c, d)] if not flip else [(a, c, b), (a, d, c)]
    mb.add(mat, P, N, UV, [col], I)


def disk(mb, mat, center, radius, normal_axis, up_axis, segs=24, col=WHITE, uv_rect=(0, 0, 1, 1)):
    """Disque plan (horloge…) : normal_axis = normale, up_axis = haut de l'image."""
    c = np.asarray(center, np.float64)
    n = nrm(normal_axis)
    up = nrm(up_axis)
    right = np.cross(up, n)
    u0, v0, u1, v1 = uv_rect
    P = [c]
    UV = [((u0 + u1) / 2, (v0 + v1) / 2)]
    for k in range(segs):
        a = 2 * math.pi * k / segs
        x, y = math.cos(a), math.sin(a)
        P.append(c + right * x * radius + up * y * radius)
        UV.append(((u0 + u1) / 2 + x * (u1 - u0) / 2, (v0 + v1) / 2 - y * (v1 - v0) / 2))
    I = [(0, k + 1, (k + 1) % segs + 1) for k in range(segs)]
    mb.add(mat, P, [n], UV, [col], I)


def rect_sign(mb, mat, center, width, height, normal, uv_rect, col=WHITE, thickness=0.0, back_mat=None):
    """Panneau rectangulaire face à `normal` (horizontale), texte lisible de l'extérieur."""
    c = np.asarray(center, np.float64)
    n = nrm(normal)
    up = np.array([0, 0, 1.0])
    right = np.cross(up, n)
    u0, v0, u1, v1 = uv_rect
    hw, hh = width / 2, height / 2
    a = c - right * hw - up * hh
    b = c + right * hw - up * hh
    cc = c + right * hw + up * hh
    d = c - right * hw + up * hh
    mb.quad(mat, a, b, cc, d, [(u0, v1), (u1, v1), (u1, v0), (u0, v0)], col, n)
    if thickness > 0 and back_mat:
        t = -n * thickness
        mb.quad(back_mat, b + t, a + t, d + t, cc + t, [(0, 0), (1, 0), (1, 1), (0, 1)], col, -n)
        for p0, p1 in ((a, b), (b, cc), (cc, d), (d, a)):
            en = nrm(np.cross(p1 - p0, t))
            mb.quad(back_mat, p0, p0 + t, p1 + t, p1, [(0, 0), (0, 0.05), (1, 0.05), (1, 0)], col, -en if np.dot(-en, (p0 + p1) / 2 - c) > 0 else en)


def transform_arrays(arr, yaw=0.0, pos=(0, 0, 0), scale=(1, 1, 1)):
    """Applique échelle, rotation autour de z puis translation à un dictionnaire de maillage."""
    c, s = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
    S = np.asarray(scale, np.float32)
    out = {}
    for m, d in arr.items():
        P = (d["P"] * S) @ R.T + np.asarray(pos, np.float32)
        Nn = (d["N"] / S) @ R.T
        Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-9)
        out[m] = dict(P=P.astype(np.float32), N=Nn.astype(np.float32), UV=d["UV"], C=d["C"], I=d["I"])
    return out
