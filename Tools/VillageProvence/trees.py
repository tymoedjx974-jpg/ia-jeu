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


def make_tree(species, seed, lod=0):
    sp = SPECIES[species]
    rng = np.random.default_rng(seed)
    H = rng.uniform(*sp["h"])
    mb = MB()
    branches = []  # (pts, radii, level)
    tips = []  # (point, direction, level)
    lean = rng.normal(0, 0.06 if species not in ("Pin",) else 0.14, 2)
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
    rng = np.random.default_rng(seed)
    H = rng.uniform(9, 14)
    R = H * rng.uniform(0.09, 0.12)
    mb = MB()
    tube(mb, "EcorcePin", [(0, 0, 0), (0, 0, H * 0.3)], [0.22, 0.12], segs=6)
    n = {0: 700, 1: 300, 2: 80}[lod]
    size = {0: 1.0, 1: 1.5, 2: 2.8}[lod] * H / 12
    for i in range(n):
        z = H * (0.04 + 0.96 * rng.random() ** 0.85)
        t = z / H
        rad = R * (math.sin(math.pi * min(1.0, t * 1.05)) ** 0.75) * (1.1 - 0.35 * t)
        a = rng.uniform(0, 2 * math.pi)
        rr = rad * math.sqrt(rng.uniform(0.3, 1.0))
        c = np.array([rr * math.cos(a), rr * math.sin(a), z])
        leaf_card(mb, "FeuillesCypres", c, np.array([0, 0, z]), rng, size * rng.uniform(0.8, 1.2), R * 2, sway=int(80 + 175 * t), spherical=0.7)
    return mb, H, R


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




def make_vine_row(seed, lod=0):
    """Segment de rang de vigne (4 ceps sur 4,8 m, le long de l'axe X) + piquet."""
    mb = MB()
    rng = np.random.default_rng(seed)
    for k, x in enumerate((-1.8, -0.6, 0.6, 1.8)):
        v, _, _ = make_vine(seed * 10 + k, lod)
        mb.extend(v, offset=(x + rng.normal(0, 0.05), rng.normal(0, 0.04), 0.0))
    tube(mb, "BoisBrut", [(2.4, 0, -0.2), (2.4, 0, 1.35)], 0.035, segs=5)
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
    for v in range(3):
        C[f"Arbre_Cypres_{v}"] = (lambda lod, v=v: make_cypress(50 + v, lod))
    for v in range(4):
        C[f"Buisson_Garrigue_{v}"] = (lambda lod, v=v: make_bush(300 + v, "FeuillesGarrigue", (0.5, 1.2), 24, lod))
    for v in range(2):
        C[f"Buisson_LaurierRose_{v}"] = (lambda lod, v=v: make_bush(400 + v, "FeuillesOlivier", (1.6, 2.4), 40, lod, flowers=("Fleurs", 3, 26)))
        C[f"Buisson_Romarin_{v}"] = (lambda lod, v=v: make_bush(420 + v, "FeuillesGarrigue", (0.5, 0.8), 18, lod, quad=v))
    for v in range(3):
        C[f"Lavande_{v}"] = (lambda lod, v=v: make_lavender(500 + v, lod))
        C[f"Vigne_{v}"] = (lambda lod, v=v: make_vine(600 + v, lod))
        C[f"Herbe_Seche_{v}"] = (lambda lod, v=v: make_grass(700 + v, "HerbeSeche", lod))
        C[f"Herbe_Verte_{v}"] = (lambda lod, v=v: make_grass(800 + v, "HerbeVerte", lod, (0.2, 0.4)))
    for v in range(3):
        C[f"Vigne_Rang_{v}"] = (lambda lod, v=v: make_vine_row(650 + v, lod))
        C[f"Lavande_Rang_{v}"] = (lambda lod, v=v: make_lavender_row(550 + v, lod))
    C["Balle_Foin"] = (lambda lod: make_bale(900))
    return C
