"""Végétation procédurale : arbres (branches en tubes + cartes de feuillage), buissons, lavande, vigne, herbes.

Chaque plante est construite à l'origine (pied en (0,0,0)). Trois niveaux de détail : LOD0, LOD1, LOD2.
Couleur de sommet des feuilles : RGB = légère variation, A = amplitude du vent (0 au tronc -> 255 aux extrémités).
"""
import math
import numpy as np
from geomlib import MB, tube, nrm, revolve, WHITE

UP = np.array([0.0, 0.0, 1.0])


def rot_axis(v, axis, ang):
    axis = nrm(axis)
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * np.dot(axis, v) * (1 - math.cos(ang))


def perp_of(d):
    a = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
    return nrm(np.cross(d, a))


SPECIES = {
    # h: hauteur, crown: (centre z relatif, rayon horizontal, rayon vertical), trunk: fraction du tronc nu
    "Platane": dict(h=(14, 19), trunk_r=0.32, trunk_h=0.38, limbs=(4, 6), limb_ang=(28, 45), levels=3, kids=(3, 5), ratio=0.62,
                    crown=(0.62, 0.42, 0.36), bark="EcorcePlatane", leaf="FeuillesPlatane", card=(1.1, 1.6), cards=1500, droop=0.08, wobble=0.18),
    "Olivier": dict(h=(4.2, 6.5), trunk_r=0.2, trunk_h=0.22, limbs=(3, 5), limb_ang=(35, 55), levels=3, kids=(3, 5), ratio=0.6,
                    crown=(0.6, 0.62, 0.42), bark="EcorceOlivier", leaf="FeuillesOlivier", card=(0.55, 0.8), cards=900, droop=0.15, wobble=0.35, twist=True),
    "Chene": dict(h=(7, 11), trunk_r=0.22, trunk_h=0.25, limbs=(4, 6), limb_ang=(30, 55), levels=3, kids=(3, 5), ratio=0.6,
                  crown=(0.58, 0.5, 0.42), bark="EcorceChene", leaf="FeuillesChene", card=(0.6, 0.95), cards=1300, droop=0.1, wobble=0.3),
    "Fruitier": dict(h=(4, 5.5), trunk_r=0.13, trunk_h=0.28, limbs=(3, 5), limb_ang=(35, 50), levels=3, kids=(3, 4), ratio=0.6,
                     crown=(0.62, 0.5, 0.4), bark="EcorceChene", leaf="FeuillesFruitier", card=(0.5, 0.75), cards=650, droop=0.12, wobble=0.25),
    "Pin": dict(h=(9, 15), trunk_r=0.24, trunk_h=0.45, limbs=(5, 8), limb_ang=(30, 60), levels=2, kids=(3, 5), ratio=0.6,
                crown=(0.72, 0.42, 0.3), bark="EcorcePin", leaf="AiguillesPin", card=(0.9, 1.4), cards=1100, droop=0.05, wobble=0.25, clumps=True),
    "PinParasol": dict(h=(11, 16), trunk_r=0.3, trunk_h=0.6, limbs=(4, 6), limb_ang=(35, 55), levels=3, kids=(3, 4), ratio=0.6,
                       crown=(0.86, 0.55, 0.14), bark="EcorcePin", leaf="AiguillesPin", card=(1.0, 1.5), cards=1400, droop=0.0, wobble=0.2, clumps=True, flat=True),
}


def gnarled_trunk(mb, mat, pts, radii, segs, cols, rng, seed):
    """Tronc d'olivier (d'après photo) : cannelures légèrement torsadées, bourrelets autour des anciennes branches,
    pied légèrement renflé avec quelques racines noueuses qui s'enfoncent dans la terre (le tronc descend sous le sol,
    aucun bord visible). Anneaux orientés de façon constante (pas de vrille de l'écorce), UV mesurés sur la surface."""
    pts = np.asarray(pts, np.float64)
    radii = np.asarray(radii, np.float64)
    z0 = pts[0, 2]
    pts = np.vstack([pts[:1] - np.array([0, 0, 0.35]), pts])
    radii = np.concatenate([radii[:1], radii])
    cols = [cols[0]] + list(cols)
    # plus d'anneaux pour que les bourrelets soient ronds
    m = (len(pts) - 1) * 3 + 1
    t_old = np.linspace(0, 1, len(pts))
    t = np.linspace(0, 1, m)
    P = np.column_stack([np.interp(t, t_old, pts[:, k]) for k in range(3)])
    R = np.interp(t, t_old, radii)
    # pas d'évasement conique : le pied garde à peu près le diamètre du tronc
    R = np.minimum(R, np.interp(0.35, t, R) * 1.12)
    C = [cols[min(len(cols) - 1, int(round(ti * (len(cols) - 1))))] for ti in t]
    ring = segs + 1
    ang = 2 * np.pi * np.arange(ring) / segs
    ph = rng.uniform(0, 2 * np.pi, 4)
    burls = [(rng.uniform(0.35, 0.95), rng.uniform(0, 2 * np.pi), rng.uniform(0.15, 0.35), rng.uniform(0.05, 0.1)) for _ in range(rng.integers(3, 6))]
    roots = [(rng.uniform(0, 2 * np.pi), rng.uniform(0.08, 0.16)) for _ in range(rng.integers(3, 5))]
    Q = np.zeros((m, ring, 3))
    X = np.array([1.0, 0.0, 0.0])
    for i in range(m):
        T = nrm(P[min(i + 1, m - 1)] - P[max(i - 1, 0)])
        ref = X - np.dot(X, T) * T
        if np.linalg.norm(ref) < 1e-3:
            ref = np.array([0.0, 1.0, 0.0]) - T[1] * T
        ref = nrm(ref)
        B = np.cross(T, ref)
        ti = t[i]
        z = P[i, 2] - z0
        f = 0.1 * np.sin(3 * ang + 3.0 * ti + ph[0]) + 0.05 * np.sin(5 * ang - 2.5 * ti + ph[1])
        for tb, ab, amp, wdt in burls:
            da = np.angle(np.exp(1j * (ang - ab)))
            f = f + amp * np.exp(-((ti - tb) / wdt) ** 2 - (da / 0.6) ** 2)
        zc = max(z, 0.0)
        f = f + 0.12 * np.exp(-zc / 0.4)                   # renflement doux du pied
        for ar, amp in roots:                               # racines : bosses étroites qui plongent dans le sol
            da = np.angle(np.exp(1j * (ang - ar)))
            f = f + amp * np.exp(-(da / 0.32) ** 2) * np.exp(-zc / 0.18)
        d = np.outer(np.cos(ang), ref) + np.outer(np.sin(ang), B)
        Q[i] = P[i] + d * (max(R[i], 0.012) * (1 + f))[:, None]
    Pv = Q.reshape(-1, 3)
    # UV : u = longueur d'arc autour de l'anneau, v = distance le long du tronc
    arc = np.concatenate([np.zeros((m, 1)), np.cumsum(np.linalg.norm(np.diff(Q, axis=1), axis=2), axis=1)], axis=1)
    vlen = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    UV = np.column_stack([arc.ravel(), -np.repeat(vlen, ring)])
    I = []
    for i in range(m - 1):
        for k in range(segs):
            a_ = i * ring + k
            I += [(a_, a_ + ring + 1, a_ + ring), (a_, a_ + 1, a_ + ring + 1)]
    I = np.array(I, np.int64)
    fn = np.cross(Pv[I[:, 1]] - Pv[I[:, 0]], Pv[I[:, 2]] - Pv[I[:, 0]])
    Nn = np.zeros_like(Pv)
    for k in range(3):
        np.add.at(Nn, I[:, k], fn)
    Nn = nrm(Nn)
    radial = Pv - np.repeat(P, ring, axis=0)
    if np.mean(np.sum(Nn * radial, axis=1)) < 0:
        Nn = -Nn
    Cv = np.repeat(np.array(C, np.uint8), ring, axis=0)
    mb.add(mat, Pv, Nn, UV, Cv, I)


def make_tree(species, seed, lod=0):
    sp = SPECIES[species]
    rng = np.random.default_rng(seed)
    H = rng.uniform(*sp["h"])
    mb = MB()
    branches = []  # (pts, radii, level)
    tips = []  # (point, direction, level)
    lean = rng.normal(0, {"Pin": 0.14, "Olivier": 0.22}.get(species, 0.06), 2)
    # tronc
    th = H * sp["trunk_h"] * rng.uniform(0.85, 1.15)
    n = 8
    pts = [np.zeros(3)]
    d = nrm(np.array([lean[0], lean[1], 1.0]))
    for i in range(n):
        d = nrm(d + rng.normal(0, sp["wobble"] * 0.25, 3) * np.array([1, 1, 0.3]))
        if species == "Pin":
            d = nrm(d + np.array([lean[0], lean[1], 0]) * 0.3)
        pts.append(pts[-1] + d * th / n)
    r0 = sp["trunk_r"] * (H / np.mean(sp["h"])) ** 0.8
    radii = [r0 * (1.25 if i == 0 else 1.0) * (1 - 0.25 * i / n) for i in range(n + 1)]
    if sp.get("twist"):
        # olivier : tronc noueux, souvent double
        radii = [r * (1 + 0.25 * math.sin(i * 1.7 + seed)) for i, r in enumerate(radii)]
    branches.append((np.array(pts), np.array(radii), 0))
    top = pts[-1]
    crown_c = np.array([0, 0, H * sp["crown"][0]]) + np.array([lean[0], lean[1], 0]) * H * 0.5
    rx, rz = H * sp["crown"][1], H * sp["crown"][2]

    def inside(p):
        q = (p - crown_c) / np.array([rx, rx, rz])
        return np.dot(q, q) <= 1.15

    def grow(p0, d, length, rad, level):
        nseg = max(3, int(length / 0.45))
        pts = [p0]
        rr = [rad]
        dd = d
        for i in range(nseg):
            toward = nrm(crown_c - pts[-1]) if not inside(pts[-1]) else np.zeros(3)
            dd = nrm(dd + rng.normal(0, sp["wobble"] * 0.3, 3) + UP * 0.05 - UP * sp["droop"] * level * 0.5 + toward * 0.25)
            if sp.get("flat") and level >= 1:
                dd = nrm(dd * np.array([1, 1, 0.35]))
            pts.append(pts[-1] + dd * length / nseg)
            rr.append(rad * (1 - 0.7 * (i + 1) / nseg))
        pts = np.array(pts)
        branches.append((pts, np.array(rr), level))
        if level < sp["levels"]:
            nk = rng.integers(sp["kids"][0], sp["kids"][1] + 1)
            for k in range(nk):
                t = rng.uniform(0.35, 1.0)
                idx = min(len(pts) - 2, int(t * (len(pts) - 1)))
                base_d = nrm(pts[idx + 1] - pts[idx])
                ax = rot_axis(perp_of(base_d), base_d, rng.uniform(0, 2 * math.pi))
                cd = rot_axis(base_d, ax, math.radians(rng.uniform(25, 55)))
                grow(pts[idx], cd, length * sp["ratio"] * rng.uniform(0.7, 1.15), rr[idx] * 0.62, level + 1)
        else:
            for t in (0.45, 0.75, 1.0):
                idx = int(t * (len(pts) - 1))
                tips.append((pts[idx], nrm(pts[min(idx + 1, len(pts) - 1)] - pts[max(idx - 1, 0)]), level))

    nl = rng.integers(sp["limbs"][0], sp["limbs"][1] + 1)
    for k in range(nl):
        az = 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / nl
        el = math.radians(90 - rng.uniform(*sp["limb_ang"]))
        d = nrm(np.array([math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)]))
        t = rng.uniform(0.75, 1.0)
        start = branches[0][0][int(t * n)]
        L = max(rx, rz) * rng.uniform(0.8, 1.1)
        grow(start, d, L, r0 * 0.6, 1)
    # géométrie des branches selon le niveau de détail
    maxlev = {0: 3, 1: 2, 2: 1}[lod]
    segs = {0: (10, 7, 5, 4), 1: (8, 5, 4, 3), 2: (6, 4, 3, 3)}[lod]
    for pts, rr, level in branches:
        if level > maxlev:
            continue
        sway = np.clip(np.linalg.norm(pts[:, :2], axis=1) / max(rx, 1) * 90, 0, 90).astype(int)
        cols = [(255, 255, 255, int(s * (0.3 if level == 0 else 1))) for s in sway]
        if level == 0 and sp.get("twist"):
            gnarled_trunk(mb, sp["bark"], pts, rr, {0: 20, 1: 12, 2: 7}[lod], cols, rng, seed)
        else:
            tube(mb, sp["bark"], pts, np.maximum(rr, 0.012), segs=segs[min(level, 3)], cols=cols, u_tile=1.0, v_tile=1.0)
    # feuillage : l'enveloppe réelle est celle des extrémités de branches
    if tips:
        tp = np.array([t_[0] for t_ in tips])
        crown_c = tp.mean(axis=0)
        rx = max(0.8, float(np.percentile(np.linalg.norm(tp[:, :2] - crown_c[:2], axis=1), 90)) + 0.4)
        rz = max(0.6, float(np.percentile(np.abs(tp[:, 2] - crown_c[2]), 90)) + 0.4)
    ncards = {0: sp["cards"], 1: int(sp["cards"] * 0.45), 2: int(sp["cards"] * 0.12)}[lod]
    size_mult = {0: 1.0, 1: 1.45, 2: 2.6}[lod]
    if tips:
        sel = rng.choice(len(tips), size=ncards, replace=len(tips) < ncards)
        for s in sel:
            p, d, lev = tips[s]
            off = rng.normal(0, 0.3 if sp.get("clumps") else 0.28, 3)
            c = p + off
            # reste dans l'enveloppe du houppier
            q = (c - crown_c) / np.array([rx, rx, rz])
            lq = np.linalg.norm(q)
            if lq > 1.05:
                c = crown_c + (c - crown_c) * (1.05 / lq)
            leaf_card(mb, sp["leaf"], c, crown_c, rng, rng.uniform(*sp["card"]) * size_mult, rx)
    return mb, H, rx


def leaf_card(mb, mat, c, crown_c, rng, size, rx, quad=None, sway=None, spherical=0.6, tint=None, upright=False):
    q = rng.integers(4) if quad is None else quad
    u0, v0 = (q % 2) * 0.5, (q // 2) * 0.5
    outward = nrm(c - crown_c + np.array([0, 0, 0.3]))
    if upright:
        a = rng.uniform(0, math.pi)
        right = np.array([math.cos(a), math.sin(a), 0.0])
        up = UP
    else:
        # carte orientée aléatoirement, plutôt face à l'extérieur
        right = perp_of(outward)
        right = rot_axis(right, outward, rng.uniform(0, 2 * math.pi))
        up = nrm(np.cross(outward, right))
        tilt = rng.uniform(-0.5, 0.5)
        right, up = rot_axis(right, outward, tilt), rot_axis(up, outward, tilt)
    h = size / 2
    p0 = c - right * h - up * h
    p1 = c + right * h - up * h
    p2 = c + right * h + up * h
    p3 = c - right * h + up * h
    n_card = nrm(np.cross(right, up))
    n = nrm(n_card * (1 - spherical) + outward * spherical)
    t = tint or (int(rng.uniform(210, 255)), int(rng.uniform(215, 255)), int(rng.uniform(205, 250)))
    sw = int(np.clip(np.linalg.norm(c[:2]) / max(rx, 0.5) * 200 + 55, 0, 255)) if sway is None else sway
    mb.add(mat, [p0, p1, p2, p3], [n], [(u0, v0 + 0.5), (u0 + 0.5, v0 + 0.5), (u0 + 0.5, v0), (u0, v0)], [t + (sw,)], [[0, 1, 2], [0, 2, 3]])


def make_cypress(seed, lod=0):
    """Cyprès de Provence (Cupressus sempervirens 'Stricta') : fuseau très élancé, plus large au tiers inférieur,
    pointe effilée qui s'incline un peu (d'après photo)."""
    rng = np.random.default_rng(seed)
    H = rng.uniform(10, 16)
    R = H * rng.uniform(0.065, 0.085)
    a_lean = rng.uniform(0, 2 * math.pi)
    lean = np.array([math.cos(a_lean), math.sin(a_lean)]) * H * rng.uniform(0.02, 0.06)
    mb = MB()
    tube(mb, "EcorcePin", [(0, 0, 0), (0, 0, H * 0.3)], [0.2, 0.1], segs=6)
    n = {0: 950, 1: 380, 2: 100}[lod]
    size = {0: 0.85, 1: 1.35, 2: 2.6}[lod] * H / 12
    for i in range(n):
        z = H * (0.03 + 0.97 * rng.random() ** 0.8)
        t = z / H
        # profil en flamme : maximum vers 30 % de la hauteur, bosses irrégulières le long du tronc
        prof = (min(1.0, t / 0.3) ** 0.5) * (1.0 - smooth_t(t, 0.3, 1.0) ** 1.3)
        bump = 1.0 + 0.12 * math.sin(t * 23.0 + seed) + 0.08 * math.sin(t * 41.0 + 2 * seed)
        rad = R * max(prof, 0.04) * bump
        off = lean * t ** 2.5
        a = rng.uniform(0, 2 * math.pi)
        rr = rad * math.sqrt(rng.uniform(0.35, 1.0))
        c = np.array([off[0] + rr * math.cos(a), off[1] + rr * math.sin(a), z])
        leaf_card(mb, "FeuillesCypres", c, np.array([off[0], off[1], z]), rng, size * rng.uniform(0.75, 1.15) * (0.6 + 0.4 * max(prof, 0.3)), R * 2,
                  sway=int(80 + 175 * t), spherical=0.7)
    return mb, H, R


def smooth_t(t, a, b):
    x = min(1.0, max(0.0, (t - a) / (b - a)))
    return x * x * (3 - 2 * x)


def make_bush(seed, mat="FeuillesGarrigue", size=(0.6, 1.3), cards=24, lod=0, quad=None, flowers=None):
    rng = np.random.default_rng(seed)
    h = rng.uniform(*size)
    w = h * rng.uniform(1.0, 1.5)
    mb = MB()
    n = {0: cards, 1: max(6, cards // 2), 2: max(4, cards // 4)}[lod]
    for i in range(n):
        a = rng.uniform(0, 2 * math.pi)
        r = w / 2 * math.sqrt(rng.random())
        z = h * (0.25 + 0.6 * rng.random())
        c = np.array([r * math.cos(a), r * math.sin(a), z])
        leaf_card(mb, mat, c, np.array([0, 0, h * 0.3]), rng, h * rng.uniform(0.7, 1.0) * (1.3 if lod else 1.0), w, quad=quad, sway=int(60 + 120 * z / h))
    if flowers:
        fmat, fq, fn = flowers
        for i in range({0: fn, 1: fn // 2, 2: fn // 3}[lod]):
            a = rng.uniform(0, 2 * math.pi)
            r = w / 2 * math.sqrt(rng.random()) * 0.9
            z = h * (0.5 + 0.5 * rng.random())
            c = np.array([r * math.cos(a), r * math.sin(a), z])
            leaf_card(mb, fmat, c, np.array([0, 0, h * 0.3]), rng, h * 0.6, w, quad=fq, sway=150)
    return mb, h, w / 2


def make_lavender(seed, lod=0):
    """Touffe de lavande en boule (épis violets)."""
    rng = np.random.default_rng(seed)
    h = rng.uniform(0.55, 0.75)
    w = rng.uniform(0.7, 0.95)
    mb = MB()
    n = {0: 16, 1: 9, 2: 5}[lod]
    for i in range(n):
        a = math.pi * i / n + rng.uniform(-0.2, 0.2)
        right = np.array([math.cos(a), math.sin(a), 0.0])
        tilt_ax = np.array([-math.sin(a), math.cos(a), 0.0])
        up = rot_axis(UP, tilt_ax, rng.uniform(-0.35, 0.35))
        c = np.array([rng.normal(0, 0.08), rng.normal(0, 0.08), 0.0])
        s = w / 2
        p0, p1 = c - right * s, c + right * s
        p2, p3 = p1 + up * h, p0 + up * h
        n_ = nrm(np.cross(right, up) * 0.3 + UP * 0.7)
        q = rng.integers(4)
        u0, v0 = (q % 2) * 0.5, (q // 2) * 0.5
        t = (int(rng.uniform(225, 255)), int(rng.uniform(225, 255)), int(rng.uniform(230, 255)))
        mb.add("Lavande", [p0, p1, p2, p3], [n_], [(u0, v0 + 0.5), (u0 + 0.5, v0 + 0.5), (u0 + 0.5, v0), (u0, v0)],
               [t + (0,), t + (0,), t + (200,), t + (200,)], [[0, 1, 2], [0, 2, 3]])
    return mb, h, w / 2


def make_grass(seed, mat="HerbeSeche", lod=0, size=(0.35, 0.7)):
    rng = np.random.default_rng(seed)
    h = rng.uniform(*size)
    mb = MB()
    n = {0: 4, 1: 3, 2: 2}[lod]
    for i in range(n):
        a = math.pi * i / n + rng.uniform(-0.3, 0.3)
        right = np.array([math.cos(a), math.sin(a), 0.0])
        s = h * 0.7
        c = np.array([rng.normal(0, 0.05), rng.normal(0, 0.05), 0])
        p0, p1 = c - right * s, c + right * s
        p2, p3 = p1 + UP * h, p0 + UP * h
        q = rng.integers(4)
        u0, v0 = (q % 2) * 0.5, (q // 2) * 0.5
        t = (int(rng.uniform(220, 255)), int(rng.uniform(220, 255)), int(rng.uniform(215, 250)))
        mb.add(mat, [p0, p1, p2, p3], [UP * 0.8 + nrm(np.cross(right, UP)) * 0.2], [(u0, v0 + 0.5), (u0 + 0.5, v0 + 0.5), (u0 + 0.5, v0), (u0, v0)],
               [t + (0,), t + (0,), t + (255,), t + (255,)], [[0, 1, 2], [0, 2, 3]])
    return mb, h, h * 0.7


def make_vine(seed, lod=0):
    """Cep de vigne palissé : tronc tortueux + rideau de feuilles le long du rang (axe X)."""
    rng = np.random.default_rng(seed)
    mb = MB()
    th = rng.uniform(0.45, 0.65)
    pts = [(0, 0, 0)]
    for i in range(4):
        pts.append((rng.normal(0, 0.04), rng.normal(0, 0.04), th * (i + 1) / 4))
    tube(mb, "EcorceOlivier", pts, np.linspace(0.05, 0.035, 5), segs=5)
    for sgn in (-1, 1):
        tube(mb, "EcorceOlivier", [pts[-1], (sgn * 0.45, rng.normal(0, 0.03), th + 0.05)], 0.02, segs=4)
    n = {0: 22, 1: 12, 2: 6}[lod]
    for i in range(n):
        c = np.array([rng.uniform(-0.55, 0.55), rng.normal(0, 0.12), th + rng.uniform(0.1, 0.8)])
        leaf_card(mb, "FeuillesVigne", c, np.array([0, 0, th + 0.4]), rng, rng.uniform(0.35, 0.55) * (1.4 if lod else 1.0), 0.6, sway=int(80 + 150 * (c[2] - th)))
    return mb, th + 0.9, 0.6


def make_bale(seed):
    """Balle de foin ronde (champs moissonnés)."""
    mb = MB()
    rng = np.random.default_rng(seed)
    r, w = 0.75, 1.2
    ang = rng.uniform(0, math.pi)
    d = np.array([math.cos(ang), math.sin(ang), 0])
    c = np.array([0, 0, r * 0.97])
    tube(mb, "Paille", [c - d * w / 2, c + d * w / 2], r, segs=16, u_tile=1.0, v_tile=1.0)
    for sgn in (-1, 1):
        cc = c + d * sgn * w / 2
        P = [cc]
        side = perp_of(d)
        up = np.cross(d, side)
        for k in range(16):
            a = 2 * math.pi * k / 16
            P.append(cc + (side * math.cos(a) + up * math.sin(a)) * r)
        I = [(0, k + 1, (k + 1) % 16 + 1) if sgn > 0 else (0, (k + 1) % 16 + 1, k + 1) for k in range(16)]
        UVs = [(0.5, 0.5)] + [(0.5 + 0.5 * math.cos(2 * math.pi * k / 16), 0.5 + 0.5 * math.sin(2 * math.pi * k / 16)) for k in range(16)]
        mb.add("Paille", P, [d * sgn], UVs, [WHITE], I)
    return mb, 1.5, 0.8




def _icosphere(sub):
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    for _ in range(sub):
        cache, F2 = {}, []
        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = V[a] + V[b]
                V.append(m / np.linalg.norm(m))
                cache[k] = len(V) - 1
            return cache[k]
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            F2 += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = F2
    return np.array(V), np.array(F, np.int64)


def make_rock(seed, lod=0, kind="bloc"):
    """Rocher calcaire : sphère déformée (bruit de faces planes = cassures), base enterrée.
    kind : bloc (rond, 0,6-1,4 m), dalle (affleurement plat et large), eboulis (petit, anguleux)."""
    rng = np.random.default_rng(seed)
    P, F = _icosphere((3, 2, 1)[lod])
    # cassures : on rabote la sphère par quelques plans aléatoires, puis bruit doux
    for _ in range(9 if kind != "eboulis" else 6):
        n = nrm(rng.normal(size=3))
        d = rng.uniform(0.55, 0.85)
        proj = P @ n
        over = proj > d
        P[over] -= np.outer(proj[over] - d, n) * 0.85
    freqs = [(rng.normal(size=3) * f, rng.uniform(0, 6.28), a) for f, a in ((2.0, 0.08), (4.5, 0.04), (9.0, 0.02))]
    r = 1.0 + sum(a * np.sin(P @ k + ph) for k, ph, a in freqs)
    P = P * r[:, None]
    size = {"bloc": (rng.uniform(1.0, 1.5), rng.uniform(0.8, 1.2), rng.uniform(0.95, 1.35)),
            "dalle": (rng.uniform(2.2, 3.4), rng.uniform(1.6, 2.4), rng.uniform(0.45, 0.7)),
            "eboulis": (rng.uniform(0.35, 0.55), rng.uniform(0.3, 0.45), rng.uniform(0.25, 0.4))}[kind]
    P = P * np.array(size) * 0.5
    zmin = P[:, 2].min()
    P[:, 2] -= zmin + size[2] * 0.22          # un quart enfoui dans le sol
    # normales lissées par sommet
    fn = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    N = np.zeros_like(P)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    N = nrm(N)
    # UV : projection cylindrique (en mètres), la texture Roche est à grain fin et sans orientation marquée
    ang = np.arctan2(P[:, 1], P[:, 0])
    circ = math.pi * (size[0] + size[1]) / 2
    UV = np.column_stack([(ang / (2 * math.pi) + 0.5) * circ, -P[:, 2] + 0.35 * (P[:, 0] + P[:, 1])])
    # base plus sombre (terre, humidité)
    h = np.clip((P[:, 2] + 0.05) / max(size[2] * 0.4, 0.1), 0, 1)
    C = np.column_stack([np.repeat((170 + 85 * h)[:, None], 3, 1), np.zeros(len(P))]).astype(np.uint8)
    mb = MB()
    mb.add("Rocher", P, N, UV, C, F)
    return mb, float(P[:, 2].max()), float(max(size[:2]) * 0.5)


def make_tall_grass(seed, lod=0):
    """Haute herbe sèche (graminées de 0,6 à 1 m, épis) : touffe de cartes croisées, plus fournie que l'herbe rase."""
    rng = np.random.default_rng(seed)
    mb = MB()
    n = {0: 14, 1: 8, 2: 4}[lod]
    h0 = rng.uniform(0.6, 1.0)
    for i in range(n):
        a = math.pi * i / n + rng.uniform(-0.25, 0.25)
        h = h0 * rng.uniform(0.75, 1.1)
        right = np.array([math.cos(a), math.sin(a), 0.0])
        lean = np.array([rng.normal(0, 0.12), rng.normal(0, 0.12), 0.0])
        s = h * 0.35
        c = np.array([rng.normal(0, 0.22), rng.normal(0, 0.22), 0])       # bouquet d'environ 1 m
        p0, p1 = c - right * s, c + right * s
        p2, p3 = p1 + UP * h + lean, p0 + UP * h + lean
        q = rng.integers(4)
        u0, v0 = (q % 2) * 0.5, (q // 2) * 0.5
        t = (int(rng.uniform(215, 255)), int(rng.uniform(205, 245)), int(rng.uniform(170, 220)))
        mb.add("HerbeSeche", [p0, p1, p2, p3], [UP * 0.8 + nrm(np.cross(right, UP)) * 0.2], [(u0, v0 + 0.5), (u0 + 0.5, v0 + 0.5), (u0 + 0.5, v0), (u0, v0)],
               [t + (0,), t + (0,), t + (255,), t + (255,)], [[0, 1, 2], [0, 2, 3]])
    return mb, h0, h0 * 0.4


def make_grass_clump(seed, lod=0):
    """Touffe d'herbe rase et verte, large (~0,8 m) : une dizaine de cartes réparties, hauteurs variées."""
    rng = np.random.default_rng(seed)
    mb = MB()
    n = {0: 12, 1: 7, 2: 4}[lod]
    for i in range(n):
        a = rng.uniform(0, math.pi)
        h = rng.uniform(0.18, 0.42)
        right = np.array([math.cos(a), math.sin(a), 0.0])
        s = h * 0.8
        c = np.array([rng.normal(0, 0.2), rng.normal(0, 0.2), 0])
        p0, p1 = c - right * s, c + right * s
        p2, p3 = p1 + UP * h, p0 + UP * h
        q = rng.integers(4)
        u0, v0 = (q % 2) * 0.5, (q // 2) * 0.5
        t = (int(rng.uniform(210, 255)), int(rng.uniform(220, 255)), int(rng.uniform(200, 245)))
        mb.add("HerbeVerte", [p0, p1, p2, p3], [UP * 0.8 + nrm(np.cross(right, UP)) * 0.2], [(u0, v0 + 0.5), (u0 + 0.5, v0 + 0.5), (u0 + 0.5, v0), (u0, v0)],
               [t + (0,), t + (0,), t + (255,), t + (255,)], [[0, 1, 2], [0, 2, 3]])
    return mb, 0.42, 0.45


def make_pebbles(seed, lod=0):
    """Petits graviers : une poignée de cailloux calcaires (2 à 8 cm) à demi enfoncés, sur ~0,7 m."""
    rng = np.random.default_rng(seed)
    P0, F0 = _icosphere(0)
    mb = MB()
    k = {0: 26, 1: 14, 2: 6}[lod]
    for _ in range(k):
        r = rng.uniform(0.015, 0.06)
        P = P0 * np.array([r * rng.uniform(1.0, 1.6), r * rng.uniform(0.8, 1.3), r * rng.uniform(0.5, 0.9)])
        a = rng.uniform(0, 2 * math.pi)
        R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        P = P @ R.T + np.array([rng.normal(0, 0.32), rng.normal(0, 0.32), -r * 0.35])
        N = nrm(P - P.mean(axis=0))
        g = int(rng.uniform(225, 255))
        C = np.tile(np.array([g, int(g * rng.uniform(0.95, 1.0)), int(g * rng.uniform(0.88, 0.97)), 0], np.uint8), (len(P), 1))
        # calcaire clair : on échantillonne une zone unie de la texture de roche (pas les fissures sombres)
        uv = P[:, :2] * 0.6 + rng.uniform(0, 1, 2)
        mb.add("PierreTaille", P, N, uv, C, F0)
    return mb, 0.05, 0.4


def make_clod(seed, lod=0):
    """Motte de terre : petite bosse irrégulière (0,3 à 0,7 m de large, 6 à 15 cm de haut)."""
    rng = np.random.default_rng(seed)
    P, F = _icosphere((2, 1, 0)[lod])
    freqs = [(rng.normal(size=3) * f, rng.uniform(0, 6.28), a) for f, a in ((2.5, 0.12), (6.0, 0.05))]
    P = P * (1.0 + sum(a * np.sin(P @ k_ + ph) for k_, ph, a in freqs))[:, None]
    w = rng.uniform(0.3, 0.7)
    h = rng.uniform(0.06, 0.15)
    P = P * np.array([w / 2, w / 2 * rng.uniform(0.7, 1.0), h])
    P[:, 2] -= h * 0.35
    N = nrm(P * np.array([1.0 / w, 1.0 / w, 1.0 / h]))
    C = np.tile(np.array([255, 255, 255, 0], np.uint8), (len(P), 1))
    mb = MB()
    mb.add("Motte", P, N, P[:, :2] * 2.0, C, F)
    return mb, h, w / 2


def make_vine_row(seed, lod=0):
    """Segment de rang de vigne (4 ceps sur 4,8 m, le long de l'axe X) + piquet."""
    mb = MB()
    rng = np.random.default_rng(seed)
    for k, x in enumerate((-1.8, -0.6, 0.6, 1.8)):
        v, _, _ = make_vine(seed * 10 + k, lod)
        mb.extend(v, offset=(x + rng.normal(0, 0.05), rng.normal(0, 0.04), 0.0))
    tube(mb, "BoisBrut", [(2.4, 0, -0.2), (2.4, 0, 1.35)], 0.035, segs=5)
    # fils de palissage tendus d'un piquet à l'autre (les segments se suivent le long du rang)
    for z in (0.62, 0.95, 1.25):
        tube(mb, "Fer", [(-2.4, 0, z), (2.4, 0, z - 0.01)], 0.0035, segs=3, col=(150, 150, 150, 0))
    return mb, 1.5, 2.4


def make_lavender_row(seed, lod=0):
    """Segment de rang de lavande (5 touffes sur 4 m, le long de l'axe X)."""
    mb = MB()
    rng = np.random.default_rng(seed)
    for k in range(5):
        v, _, _ = make_lavender(seed * 10 + k, lod)
        mb.extend(v, offset=(-1.6 + 0.8 * k + rng.normal(0, 0.06), rng.normal(0, 0.05), 0.0))
    return mb, 0.75, 2.0


# catalogue : nom -> fonction(lod) ; plusieurs variantes par espèce
def catalog():
    C = {}
    for sp, nvar in (("Platane", 3), ("Olivier", 4), ("Chene", 4), ("Fruitier", 3), ("Pin", 4), ("PinParasol", 2)):
        for v in range(nvar):
            C[f"Arbre_{sp}_{v}"] = (lambda lod, sp=sp, v=v: make_tree(sp, 1000 * v + sum(map(ord, sp)) * 7, lod))
    for v in range(4):
        C[f"Arbre_Cypres_{v}"] = (lambda lod, v=v: make_cypress(50 + v, lod))
    for v in range(4):
        C[f"Buisson_Garrigue_{v}"] = (lambda lod, v=v: make_bush(300 + v, "FeuillesGarrigue", (0.5, 1.2), 24, lod))
    for v in range(2):
        C[f"Buisson_LaurierRose_{v}"] = (lambda lod, v=v: make_bush(400 + v, "FeuillesLaurier", (1.6, 2.4), 40, lod, flowers=("Fleurs", 3, 26)))
        C[f"Buisson_Romarin_{v}"] = (lambda lod, v=v: make_bush(420 + v, "FeuillesGarrigue", (0.5, 0.8), 18, lod, quad=v))
    for v in range(3):
        C[f"Lavande_{v}"] = (lambda lod, v=v: make_lavender(500 + v, lod))
        C[f"Vigne_{v}"] = (lambda lod, v=v: make_vine(600 + v, lod))
        C[f"Herbe_Seche_{v}"] = (lambda lod, v=v: make_grass(700 + v, "HerbeSeche", lod))
        C[f"Herbe_Verte_{v}"] = (lambda lod, v=v: make_grass(800 + v, "HerbeVerte", lod, (0.2, 0.4)))
        C[f"Herbe_Haute_{v}"] = (lambda lod, v=v: make_tall_grass(850 + v, lod))
        C[f"Herbe_Touffe_{v}"] = (lambda lod, v=v: make_grass_clump(870 + v, lod))
        C[f"Gravillons_{v}"] = (lambda lod, v=v: make_pebbles(1400 + v, lod))
        C[f"Motte_Terre_{v}"] = (lambda lod, v=v: make_clod(1450 + v, lod))
    for v in range(3):
        C[f"Vigne_Rang_{v}"] = (lambda lod, v=v: make_vine_row(650 + v, lod))
        C[f"Lavande_Rang_{v}"] = (lambda lod, v=v: make_lavender_row(550 + v, lod))
    C["Balle_Foin"] = (lambda lod: make_bale(900))
    for v in range(4):
        C[f"Rocher_Bloc_{v}"] = (lambda lod, v=v: make_rock(1100 + v, lod, "bloc"))
    for v in range(3):
        C[f"Rocher_Dalle_{v}"] = (lambda lod, v=v: make_rock(1200 + v, lod, "dalle"))
        C[f"Rocher_Eboulis_{v}"] = (lambda lod, v=v: make_rock(1300 + v, lod, "eboulis"))
    return C
