"""Surface de la rivière et ponts de pierre (voûtes, piles à avant-becs, parapets, tablier dallé)."""
import math
import numpy as np
from shapely.geometry import Polygon, box as sbox
from shapely.ops import unary_union
from common import polys_of
from geomlib import planar_polygon, box, nrm, WHITE

STONE = "PierreTaille"


def water(mb_at, prof, step=2):
    """Plan d'eau en ruban le long du lit (niveau décroissant vers l'aval)."""
    xy, lv, w = prof["xy"].astype(np.float64), prof["level"].astype(np.float64), prof["width"].astype(np.float64)
    d = np.gradient(xy, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    n = np.column_stack([-d[:, 1], d[:, 0]])
    hw = w / 2 + 0.6
    Lp = xy + n * hw[:, None]
    Rp = xy - n * hw[:, None]
    z = lv + 0.12
    for i in range(0, len(xy) - step, step):
        j = i + step
        a = (Rp[i][0], Rp[i][1], z[i]); b = (Rp[j][0], Rp[j][1], z[j])
        c = (Lp[j][0], Lp[j][1], z[j]); dd = (Lp[i][0], Lp[i][1], z[i])
        mid = xy[i]
        mb_at(mid[0], mid[1]).quad("Eau", a, b, c, dd, [(a[0] / 6, a[1] / 6), (b[0] / 6, b[1] / 6), (c[0] / 6, c[1] / 6), (dd[0] / 6, dd[1] / 6)],
                                   n=(0, 0, 1.0))


def _both(mb, mat, a, b, c, d, uvs):
    mb.quad(mat, a, b, c, d, uvs)
    mb.quad(mat, d, c, b, a, uvs[::-1])


def bridge(mb, br, zat, water_level=None):
    """Pont maçonné sur le tronçon br['line'] ; le tablier relie les deux culées au niveau de la route."""
    ln = br["line"]
    A = np.array(ln.coords[0], float)
    B = np.array(ln.coords[-1], float)
    L = float(np.linalg.norm(B - A))
    if L < 4:
        return 0
    u = (B - A) / L
    v = np.array([-u[1], u[0]])
    grand = br["grand"]
    road_w = br["width"] + (2.4 if grand else 0.6)             # trottoirs sur le grand pont
    par_t, par_h = (0.5, 1.05) if grand else (0.4, 0.9)
    Wd = road_w + 2 * par_t
    zA, zB = zat(*A), zat(*B)
    camber = (0.018 if grand else 0.01) * L

    def deck(t):
        return zA + (zB - zA) * t / L + camber * 4 * (t / L) * (1 - t / L)

    ts = np.linspace(0, L, max(8, int(L / 1.5)) + 1)
    g = np.array([zat(*(A + u * t)) for t in ts])
    bottom = float(g.min()) - 4.0
    # voûtes : piles régulières entre deux culées
    abut = 2.5 if grand else 1.5
    inner = L - 2 * abut
    nspan = max(1, int(round(inner / (15.0 if grand else 18.0))))
    if grand:
        nspan = max(nspan, 3)
    pier = max(1.6, 0.14 * inner / nspan) if nspan > 1 else 0.0
    sl = (inner - pier * (nspan - 1)) / nspan
    openings = []
    arcs = []
    for k in range(nspan):
        t0 = abut + k * (sl + pier)
        t1 = t0 + sl
        m = 0.5 * (t0 + t1)
        seg = (ts >= t0) & (ts <= t1)
        gmin = float(g[seg].min()) if seg.any() else float(min(zat(*(A + u * t0)), zat(*(A + u * t1))))
        spring = gmin + (1.2 if grand else 0.6)
        if water_level is not None:
            spring = max(spring, water_level + 0.6)
        crown_max = min(deck(t0), deck(t1)) - (1.1 if grand else 0.7)
        ry = min(sl / 2, crown_max - spring)
        if ry < 0.8:                       # tablier trop bas pour une voûte : arche en anse de panier sous l'eau
            spring = crown_max - max(1.2, sl / 3)
            ry = crown_max - spring
        rx = sl / 2
        th = np.linspace(0, math.pi, 25)
        arc = [(m + rx * math.cos(a), spring + ry * math.sin(a)) for a in th]
        poly = Polygon([(t1, bottom - 1)] + arc + [(t0, bottom - 1)])
        openings.append(poly)
        arcs.append((t0, t1, spring, [(t1, bottom - 1)] + arc + [(t0, bottom - 1)]))
    top = [(t, deck(t) + par_h) for t in ts]
    wall = Polygon(top + [(L, bottom), (0, bottom)]).buffer(0)
    wall = wall.difference(unary_union(openings)) if openings else wall
    uvf = lambda v2, P: np.stack([v2[:, 0] / 3.0, -v2[:, 1] / 3.0], -1)
    for side in (1, -1):
        org = np.array([A[0], A[1], 0.0]) + np.array([v[0], v[1], 0.0]) * side * Wd / 2
        e1 = np.array([u[0], u[1], 0.0]) * (1 if side < 0 else -1)
        for pg in polys_of(wall):
            outer = np.array(pg.exterior.coords)[:-1]
            holes = [np.array(h.coords)[:-1] for h in pg.interiors]
            if side > 0:
                outer = outer * np.array([-1, 1])
                holes = [h * np.array([-1, 1]) for h in holes]
            planar_polygon(mb, STONE, outer, holes, org, e1, np.array([0, 0, 1.0]), uvf)
    # intrados des voûtes et flancs des piles
    for t0, t1, spring, ring in arcs:
        for p, q in zip(ring[:-1], ring[1:]):
            P0 = A + u * p[0]
            Q0 = A + u * q[0]
            a = (*(P0 + v * Wd / 2), p[1]); b = (*(Q0 + v * Wd / 2), q[1])
            c = (*(Q0 - v * Wd / 2), q[1]); d = (*(P0 - v * Wd / 2), p[1])
            ln_ = math.hypot(q[0] - p[0], q[1] - p[1])
            _both(mb, STONE, a, b, c, d, [(0, 0), (ln_ / 3, 0), (ln_ / 3, Wd / 3), (0, Wd / 3)])
    # avant-becs triangulaires contre le courant (grand pont)
    if grand and nspan > 1:
        yaw = math.atan2(u[1], u[0])
        for k in range(1, nspan):
            tp = abut + k * sl + (k - 0.5) * pier
            Pp = A + u * tp
            zb = bottom
            zt = arcs[k][2] + 0.4
            for side in (1, -1):
                C = Pp + v * side * Wd / 2
                box(mb, STONE, (C[0], C[1], (zb + zt) / 2), (pier * 0.71, pier * 0.71, zt - zb), yaw=yaw + math.pi / 4, uv_scale=3.0)
    # tablier (chaussée dallée ou goudronnée) et faces intérieures / dessus des parapets
    road_mat = "Dallage" if grand else ("Asphalte" if br["cls"] in ("primary", "secondary", "tertiary", "residential", "unclassified") else "Calade")
    hw = road_w / 2
    for t0, t1 in zip(ts[:-1], ts[1:]):
        P0, P1 = A + u * t0, A + u * t1
        z0, z1 = deck(t0), deck(t1)
        mb.quad(road_mat, (*(P0 - v * hw), z0), (*(P1 - v * hw), z1), (*(P1 + v * hw), z1), (*(P0 + v * hw), z0),
                [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, road_w / 3), (t0 / 3, road_w / 3)], n=(0, 0, 1.0))
        for side in (1, -1):
            ins = v * side * hw
            out = v * side * Wd / 2
            a = (*(P0 + ins), z0); b = (*(P1 + ins), z1); c = (*(P1 + ins), z1 + par_h); d = (*(P0 + ins), z0 + par_h)
            if side > 0:
                mb.quad(STONE, a, b, c, d, [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, par_h / 3), (t0 / 3, par_h / 3)])
            else:
                mb.quad(STONE, b, a, d, c, [(t1 / 3, 0), (t0 / 3, 0), (t0 / 3, par_h / 3), (t1 / 3, par_h / 3)])
            mb.quad(STONE, (*(P0 + ins), z0 + par_h), (*(P1 + ins), z1 + par_h), (*(P1 + out), z1 + par_h), (*(P0 + out), z0 + par_h),
                    [(t0 / 3, 0), (t1 / 3, 0), (t1 / 3, par_t / 3), (t0 / 3, par_t / 3)], n=(0, 0, 1.0))
    # bouts des parapets
    for t, s_ in ((0.0, -1), (L, 1)):
        P = A + u * t
        for side in (1, -1):
            c_ = P + v * side * (hw + par_t / 2)
            box(mb, STONE, (c_[0], c_[1], deck(t) + par_h / 2 + 0.05), (0.6, par_t + 0.1, par_h + 0.1), yaw=math.atan2(u[1], u[0]), uv_scale=3.0)
    # réverbères sur le grand pont
    lamps = []
    if grand:
        for t in np.arange(6.0, L - 3.0, 12.0):
            P = A + u * t
            for side in (1, -1):
                q = P + v * side * (hw + par_t / 2)
                lamps.append((float(q[0]), float(q[1]), float(deck(t) + par_h), float(math.atan2(u[1], u[0]) + (math.pi / 2) * side)))
    return lamps
