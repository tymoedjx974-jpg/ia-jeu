"""Village envahi : voitures abandonnées, barricades, débris, camp de survivants, éléments de parkour, inscriptions.

Repère des objets posés au sol : centrés en (0, 0), z = 0, longueur selon X.
Repère des objets muraux (planches, inscriptions, échelles) : comme les ouvertures, X le long du mur,
Y vers l'intérieur du bâtiment (l'extérieur est du côté Y < 0), Z vers le haut.
"""
import math, json, os
import numpy as np
from geomlib import MB, box, tube, revolve, nrm, triangulate, WHITE

DARK = (60, 60, 60, 255)
_HERE = os.path.dirname(os.path.abspath(__file__))


def _untinted(col):
    return tuple(col[:3]) + (0,)


# ------------------------------------------------------------------ outils
def extrude(mb, mat, pts, y0, y1, col=WHITE, uv=1.0, caps=True):
    """Extrusion selon Y d'un profil (x, z) donné dans le sens trigonométrique vu depuis -Y."""
    pts = np.asarray(pts, float)
    v2, idx = triangulate(pts)
    if caps and len(idx):
        P0 = np.column_stack([v2[:, 0], np.full(len(v2), y0), v2[:, 1]])
        P1 = np.column_stack([v2[:, 0], np.full(len(v2), y1), v2[:, 1]])
        # face -Y : on la voit depuis -Y, le profil est trigonométrique en (x, z)
        i0 = idx.copy()
        n0 = np.cross(P0[i0[0, 1]] - P0[i0[0, 0]], P0[i0[0, 2]] - P0[i0[0, 0]])
        if n0[1] > 0:
            i0 = i0[:, [0, 2, 1]]
        mb.add(mat, P0, [(0, -1, 0)], v2 / uv, [col], i0)
        i1 = i0[:, [0, 2, 1]]
        mb.add(mat, P1, [(0, 1, 0)], v2 / uv, [col], i1)
    n = len(pts)
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        e = b - a
        L = float(np.linalg.norm(e))
        if L < 1e-4:
            continue
        nn = np.array([e[1], 0.0, -e[0]]) / L
        A0, B0 = (a[0], y0, a[1]), (b[0], y0, b[1])
        A1, B1 = (a[0], y1, a[1]), (b[0], y1, b[1])
        q = [(0, 0), (L / uv, 0), (L / uv, (y1 - y0) / uv), (0, (y1 - y0) / uv)]
        # orientation : normale sortante du profil
        mid = (np.array(A0) + np.array(B1)) / 2
        cen = np.array([pts[:, 0].mean(), (y0 + y1) / 2, pts[:, 1].mean()])
        if np.dot(nn, mid - cen) < 0:
            nn = -nn
            mb.quad(mat, A0, A1, B1, B0, q, col, n=nn)
        else:
            mb.quad(mat, A0, B0, B1, A1, q, col, n=nn)


def wheel(mb, x, y, r=0.3, w=0.18, rim=True, burnt=False):
    """Roue sur l'axe Y, centrée en (x, y, r)."""
    segs = 16
    prof = [(r * 0.6, -w / 2), (r * 0.95, -w / 2), (r, -w / 2 + 0.03), (r, w / 2 - 0.03), (r * 0.95, w / 2), (r * 0.6, w / 2)]
    if not burnt:
        for k in range(segs):
            a0 = 2 * math.pi * k / segs
            a1 = 2 * math.pi * (k + 1) / segs
            for j in range(len(prof) - 1):
                (ra, ya), (rb, yb) = prof[j], prof[j + 1]
                P = [(x + ra * math.cos(a0), y + ya, r + ra * math.sin(a0)), (x + ra * math.cos(a1), y + ya, r + ra * math.sin(a1)),
                     (x + rb * math.cos(a1), y + yb, r + rb * math.sin(a1)), (x + rb * math.cos(a0), y + yb, r + rb * math.sin(a0))]
                mb.quad("Pneu", P[0], P[3], P[2], P[1], [(0, 0), (0, 1), (1, 1), (1, 0)])
    if rim:
        rr = r * (0.62 if not burnt else 0.7)
        for sy in (-1, 1):
            c = (x, y + sy * (w / 2 - 0.01), r)
            pts = [(x + rr * math.cos(2 * math.pi * k / segs), y + sy * (w / 2 - 0.01), r + rr * math.sin(2 * math.pi * k / segs)) for k in range(segs)]
            for k in range(segs):
                p0, p1 = pts[k], pts[(k + 1) % segs]
                tri = [c, p0, p1] if sy < 0 else [c, p1, p0]
                mb.add("Fer", tri, [(0, sy, 0)], [(0.5, 0.5), (0, 0), (1, 0)], [(150, 150, 150, 0) if not burnt else (70, 50, 40, 0)], [[0, 1, 2]])


def roll_box(mb, mat, center, size, roll, col=WHITE, uv=1.0, yaw=0.0):
    """Pavé tourné autour de l'axe Y (roulis) puis de Z : planche en diagonale sur un mur."""
    tmp = MB()
    box(tmp, mat, (0, 0, 0), size, col=col, uv_scale=uv)
    cr, sr = math.cos(roll), math.sin(roll)
    cy, sy = math.cos(yaw), math.sin(yaw)
    for m, a in tmp.arrays().items():
        P = a["P"].astype(float).copy()
        N = a["N"].astype(float).copy()
        for M in (P, N):
            x, z = M[:, 0].copy(), M[:, 2].copy()
            M[:, 0], M[:, 2] = x * cr - z * sr, x * sr + z * cr
            x, y = M[:, 0].copy(), M[:, 1].copy()
            M[:, 0], M[:, 1] = x * cy - y * sy, x * sy + y * cy
        P += np.asarray(center, float)
        mb.add(m, P, N, a["UV"], a["C"], a["I"])


# ------------------------------------------------------------------ voitures abandonnées
def car(kind="citadine", burnt=False, rng_seed=0):
    rng = np.random.default_rng(rng_seed)
    mb = MB()
    if kind == "citadine":          # petite citadine des années 80 (esprit R5)
        L, Wd, H = 3.6, 1.56, 1.38
        body = [(-L / 2, 0.28), (L / 2, 0.28), (L / 2 + 0.02, 0.62), (L / 2 - 0.25, 0.78), (-L / 2 + 0.05, 0.84), (-L / 2, 0.62)]
        cab = [(-L / 2 + 0.08, 0.84), (0.95, 0.8), (0.35, H), (-L / 2 + 0.22, H), (-L / 2 + 0.06, 0.95)]
        wheels = (1.2, -1.2)
    elif kind == "berline":         # berline familiale
        L, Wd, H = 4.4, 1.7, 1.42
        body = [(-L / 2, 0.3), (L / 2, 0.3), (L / 2 + 0.03, 0.62), (L / 2 - 0.15, 0.8), (-L / 2 + 0.1, 0.84), (-L / 2, 0.62)]
        cab = [(-L / 2 + 0.55, 0.84), (1.15, 0.82), (0.45, H), (-0.95, H), (-L / 2 + 0.4, 0.9)]
        wheels = (1.4, -1.35)
    else:                           # fourgonnette de livraison
        L, Wd, H = 4.2, 1.72, 1.85
        body = [(-L / 2, 0.32), (L / 2, 0.32), (L / 2 + 0.02, 0.66), (L / 2 - 0.3, 0.9), (-L / 2, 0.9)]
        cab = [(-L / 2, 0.9), (1.55, 0.9), (0.95, 1.55), (0.7, H), (-L / 2, H)]
        wheels = (1.35, -1.3)
    paint = WHITE if not burnt else (90, 70, 60, 255)
    extrude(mb, "Carrosserie", body, -Wd / 2, Wd / 2, col=paint)
    extrude(mb, "Carrosserie", cab, -Wd / 2 + 0.07, Wd / 2 - 0.07, col=paint)
    # vitrage (ou vitres brisées)
    broken = burnt or rng.random() < 0.4
    for sy in (-1, 1):
        y = sy * (Wd / 2 - 0.065)
        pts = np.array(cab, float)
        cen = pts.mean(axis=0)
        inner = cen + (pts - cen) * 0.82
        if not (broken and sy > 0) and not burnt:
            v2, idx = triangulate(inner)
            P = np.column_stack([v2[:, 0], np.full(len(v2), y + sy * 0.004), v2[:, 1]])
            if sy < 0:
                idx = idx[:, [0, 2, 1]] if np.cross(P[idx[0, 1]] - P[idx[0, 0]], P[idx[0, 2]] - P[idx[0, 0]])[1] > 0 else idx
            else:
                idx = idx[:, [0, 2, 1]] if np.cross(P[idx[0, 1]] - P[idx[0, 0]], P[idx[0, 2]] - P[idx[0, 0]])[1] < 0 else idx
            mb.add("Verre", P, [(0, sy, 0)], v2, [WHITE], idx)
    # pare-brise
    fa, fb = np.array(cab[1]), np.array(cab[2])
    if not burnt:
        d = fb - fa
        t0, t1 = fa + d * 0.08, fa + d * 0.92
        y0, y1 = -Wd / 2 + 0.13, Wd / 2 - 0.13
        mb.quad("Verre", (t0[0] + 0.01, y0, t0[1]), (t0[0] + 0.01, y1, t0[1]), (t1[0] + 0.01, y1, t1[1]), (t1[0] + 0.01, y0, t1[1]),
                [(0, 0), (1, 0), (1, 1), (0, 1)])
    # pare-chocs, phares, plaques
    for sx in (-1, 1):
        box(mb, "Pneu", (sx * (L / 2 + 0.03), 0, 0.4), (0.08, Wd + 0.04, 0.14), col=(50, 50, 50, 0))
        for sy in (-1, 1):
            box(mb, "Porcelaine" if sx > 0 else "Carrosserie", (sx * (L / 2 + 0.015), sy * (Wd / 2 - 0.25), 0.58), (0.04, 0.26, 0.13),
                col=(250, 250, 240, 0) if sx > 0 else (170, 30, 25, 0))
        box(mb, "Porcelaine", (sx * (L / 2 + 0.075), 0, 0.4), (0.01, 0.5, 0.11), col=(240, 240, 235, 0))
    # soubassement sombre et roues
    box(mb, "Pneu", (0, 0, 0.3), (L - 0.2, Wd - 0.1, 0.06), col=(30, 30, 30, 0), faces=("-z",))
    for x in wheels:
        for sy in (-1, 1):
            wheel(mb, x, sy * (Wd / 2 - 0.12), r=0.3 if kind != "fourgon" else 0.32, burnt=burnt)
    if burnt:
        # intérieur calciné visible
        box(mb, "Fer", (0, 0, 0.9), (L * 0.6, Wd - 0.2, 0.05), col=(25, 20, 18, 0))
    return mb


# ------------------------------------------------------------------ barricades et débris
def planches(w=1.2, h=1.4, seed=0):
    """Planches clouées sur une ouverture, côté rue (Y < 0)."""
    rng = np.random.default_rng(seed)
    mb = MB()
    n = max(3, int(h / 0.32))
    for k in range(n):
        z = h * (k + 0.5) / n + rng.normal(0, 0.03)
        roll = rng.normal(0, 0.09)
        roll_box(mb, "BoisBrut", (rng.normal(0, 0.04), -0.05 - 0.012 * (k % 2), z), (w + 0.35, 0.03, 0.17), roll, col=(215, 190, 160, 255))
    roll_box(mb, "BoisBrut", (0, -0.085, h / 2), (math.hypot(w, h) * 0.95, 0.03, 0.16), math.atan2(h, w) * (1 if seed % 2 else -1), col=(200, 175, 145, 255))
    return mb


def sacs_sable(L=2.0, rows=3):
    mb = MB()
    rng = np.random.default_rng(3)
    sw, sh, sd = 0.55, 0.16, 0.34
    for r in range(rows):
        n = int(L / sw)
        off = (sw / 2) * (r % 2)
        for k in range(n - (r % 2)):
            x = -L / 2 + sw / 2 + k * sw + off
            c = tuple(int(v) for v in (np.array([176, 160, 118]) * rng.uniform(0.85, 1.05))) + (255,)
            box(mb, "Toile", (x, rng.normal(0, 0.02), sh / 2 + r * (sh - 0.01)), (sw - 0.03, sd * 1.6, sh), col=c, yaw=rng.normal(0, 0.05))
            box(mb, "Toile", (x, rng.normal(0, 0.02), sh / 2 + r * (sh - 0.01)), (sw - 0.1, sd * 1.7, sh * 0.7), col=c)
    return mb


def barriere():
    """Barrière de police (grille métallique amovible)."""
    mb = MB()
    L, H = 2.0, 1.1
    col = (205, 205, 200, 0)
    tube(mb, "Fer", [(-L / 2, 0, 0.08), (-L / 2, 0, H), (L / 2, 0, H), (L / 2, 0, 0.08)], 0.02, segs=6, col=col)
    tube(mb, "Fer", [(-L / 2, 0, 0.25), (L / 2, 0, 0.25)], 0.015, segs=5, col=col)
    for k in range(1, 14):
        x = -L / 2 + L * k / 14
        tube(mb, "Fer", [(x, 0, 0.25), (x, 0, H)], 0.006, segs=4, col=col)
    for sx in (-1, 1):
        tube(mb, "Fer", [(sx * L / 2, -0.3, 0.02), (sx * L / 2, 0.3, 0.02)], 0.02, segs=5, col=col)
    return mb


def palette(n=1):
    mb = MB()
    for k in range(n):
        z0 = k * 0.145
        for x in (-0.55, 0, 0.55):
            box(mb, "BoisBrut", (x, 0, z0 + 0.06), (0.1, 0.8, 0.1), col=(210, 190, 160, 255))
        for y in np.linspace(-0.35, 0.35, 5):
            box(mb, "BoisBrut", (0, y, z0 + 0.125), (1.2, 0.1, 0.025), col=(220, 200, 170, 255))
        for y in (-0.35, 0, 0.35):
            box(mb, "BoisBrut", (0, y, z0 + 0.0125), (1.2, 0.1, 0.025), col=(200, 180, 150, 255))
    return mb


def caisse(s=1.0):
    mb = MB()
    box(mb, "BoisBrut", (0, 0, s / 2), (s, s, s), col=(215, 190, 150, 255), uv_scale=1.0)
    for sy in (-1, 1):
        for z in (0.08 * s, 0.92 * s):
            box(mb, "BoisBrut", (0, sy * (s / 2 + 0.012), z), (s, 0.025, 0.1 * s), col=(180, 155, 120, 255))
        roll_box(mb, "BoisBrut", (0, sy * (s / 2 + 0.012), s / 2), (s * 1.25, 0.025, 0.1 * s), math.atan2(s, s) * sy, col=(180, 155, 120, 255))
    return mb


def pneus(n=3):
    mb = MB()
    for k in range(n):
        revolve(mb, "Pneu", [(0.2, 0), (0.3, 0.0), (0.32, 0.1), (0.3, 0.2), (0.2, 0.2), (0.2, 0.0)], (0.03 * k, 0.02 * k, k * 0.2), segs=18, col=(35, 35, 35, 0))
    return mb


def sacs_poubelle():
    mb = MB()
    rng = np.random.default_rng(8)
    for k in range(4):
        r = rng.uniform(0.25, 0.35)
        c = (rng.normal(0, 0.3), rng.normal(0, 0.25), 0)
        revolve(mb, "Pneu", [(0.0, 0), (r * 0.8, 0.02), (r, r * 0.6), (r * 0.8, r * 1.3), (0.06, r * 1.55), (0.03, r * 1.75), (0, r * 1.75)], c, segs=10, col=(20, 20, 22, 0))
    return mb


def poubelle():
    mb = MB()
    box(mb, "Plastique", (0, 0, 0.52), (0.58, 0.72, 0.98))
    box(mb, "Plastique", (0, -0.02, 1.03), (0.62, 0.78, 0.05))
    for sy in (-1, 1):
        wheel(mb, -0.2 if sy < 0 else -0.2, sy * 0.3, r=0.1, w=0.05)
    return mb


def conteneur():
    """Benne à ordures métallique (sert aussi de marchepied)."""
    mb = MB()
    L, Wd, H = 1.9, 1.05, 1.25
    extrude(mb, "Carrosserie", [(-L / 2, 0.12), (L / 2, 0.12), (L / 2 + 0.1, H), (-L / 2 - 0.1, H)], -Wd / 2, Wd / 2, col=(70, 110, 80, 255))
    box(mb, "Plastique", (0, 0.1, H + 0.04), (L + 0.2, Wd, 0.06), yaw=0.0)
    for sx in (-1, 1):
        for sy in (-1, 1):
            revolve(mb, "Pneu", [(0, 0), (0.06, 0), (0.06, 0.12), (0, 0.12)], (sx * (L / 2 - 0.15), sy * (Wd / 2 - 0.1), 0), segs=8, col=(30, 30, 30, 0))
    return mb


def gravats():
    mb = MB()
    rng = np.random.default_rng(12)
    for k in range(26):
        s = rng.uniform(0.1, 0.4)
        r = rng.uniform(0, 1.0) ** 0.7 * 1.1
        a = rng.uniform(0, 2 * math.pi)
        z = max(0.0, 0.45 * (1 - r / 1.1)) + s * 0.3
        box(mb, "PierreMoellons" if k % 3 else "Enduit", (r * math.cos(a), r * math.sin(a) * 0.8, z), (s, s * 0.8, s * 0.6),
            yaw=rng.uniform(0, 3), col=(220, 210, 190, 255), uv_scale=3.0)
    for k in range(3):
        roll_box(mb, "BoisBrut", (rng.normal(0, 0.4), rng.normal(0, 0.3), 0.3), (1.6, 0.1, 0.12), rng.normal(0, 0.3), yaw=rng.uniform(0, 3), col=(160, 130, 100, 255))
    return mb


def brasero():
    mb = MB()
    revolve(mb, "Fer", [(0.0, 0), (0.29, 0), (0.29, 0.88), (0.27, 0.9), (0.27, 0.12), (0.0, 0.12)], (0, 0, 0), segs=16, col=(120, 70, 40, 0))
    for k in range(4):
        roll_box(mb, "BoisBrut", (0, 0, 0.85), (0.5, 0.06, 0.06), 0.6 * (k - 1.5), yaw=k * 0.8, col=(40, 30, 25, 255))
    return mb


def bache(L=3.0, Wd=2.4, H=1.6):
    """Abri en bâche (toile teintée) sur une perche."""
    mb = MB()
    for sy in (-1, 1):
        mb.quad("Toile", (-L / 2, sy * Wd / 2, 0.05), (L / 2, sy * Wd / 2, 0.05), (L / 2, 0, H), (-L / 2, 0, H), [(0, 0), (L, 0), (L, 1), (0, 1)])
        mb.quad("Toile", (-L / 2, 0, H), (L / 2, 0, H), (L / 2, sy * Wd / 2, 0.05), (-L / 2, sy * Wd / 2, 0.05), [(0, 0), (L, 0), (L, 1), (0, 1)])
    for sx in (-1, 1):
        tube(mb, "BoisBrut", [(sx * L / 2, 0, 0), (sx * L / 2, 0, H + 0.1)], 0.03, segs=6)
    tube(mb, "BoisBrut", [(-L / 2 - 0.1, 0, H + 0.02), (L / 2 + 0.1, 0, H + 0.02)], 0.025, segs=6)
    return mb


def matelas():
    mb = MB()
    box(mb, "Toile", (0, 0, 0.09), (1.9, 1.35, 0.18), col=(200, 190, 165, 255))
    return mb


def meuble_renverse():
    """Table de café renversée et deux chaises au sol."""
    from modules import cafe_table, bistro_chair
    mb = MB()
    t = cafe_table().arrays()
    for m, a in t.items():
        P = a["P"].astype(float).copy()
        N = a["N"].astype(float).copy()
        # couchée sur le côté
        y, z = P[:, 1].copy(), P[:, 2].copy()
        P[:, 1], P[:, 2] = z, -y + 0.33
        ny, nz = N[:, 1].copy(), N[:, 2].copy()
        N[:, 1], N[:, 2] = nz, -ny
        mb.add(m, P, N, a["UV"], a["C"], a["I"])
    return mb


# ------------------------------------------------------------------ parkour
def echelle(h=6.0):
    """Échelle de meunier fixée au mur (repère mural : mur en y = 0, l'échelle est côté rue, Y < 0)."""
    mb = MB()
    y = -0.16
    for sx in (-1, 1):
        box(mb, "BoisBrut", (sx * 0.24, y, h / 2), (0.06, 0.08, h), col=(200, 175, 140, 255))
        for z in (0.4, h - 0.4):
            box(mb, "Fer", (sx * 0.24, y / 2, z), (0.03, 0.16, 0.03), col=(80, 80, 80, 0))
    n = int(h / 0.28)
    for k in range(1, n):
        tube(mb, "BoisBrut", [(-0.22, y, k * 0.28), (0.22, y, k * 0.28)], 0.02, segs=6, col=(210, 185, 150, 255))
    return mb


def echafaudage(w=2.5, d=0.8, levels=3, lh=2.0):
    """Échafaudage de façade (repère mural) : montants, garde-corps, planchers tous les 2 m, échelle intérieure."""
    mb = MB()
    y0, y1 = -0.25 - d, -0.25
    col = (175, 180, 185, 0)
    top = levels * lh
    for sx in (-1, 1):
        for yy in (y0, y1):
            tube(mb, "Fer", [(sx * w / 2, yy, 0), (sx * w / 2, yy, top + 1.0)], 0.024, segs=6, col=col)
    for k in range(1, levels + 1):
        z = k * lh
        box(mb, "BoisBrut", (0, (y0 + y1) / 2, z - 0.03), (w + 0.1, d, 0.05), col=(200, 180, 140, 255))
        for zz in (z + 0.5, z + 1.0):
            tube(mb, "Fer", [(-w / 2, y0, zz), (w / 2, y0, zz)], 0.02, segs=5, col=col)
        for sx in (-1, 1):
            tube(mb, "Fer", [(sx * w / 2, y0, zz), (sx * w / 2, y1, zz)], 0.02, segs=5, col=col)
        # diagonale
        tube(mb, "Fer", [(-w / 2, y0, z - lh), (w / 2, y0, z)], 0.018, segs=5, col=col)
    # échelle d'accès sur le côté gauche
    xl = -w / 2 + 0.35
    for sx in (-0.22, 0.22):
        tube(mb, "Fer", [(xl + sx, y1 - 0.12, 0), (xl + sx, y1 - 0.12, top + 0.9)], 0.018, segs=5, col=col)
    for k in range(1, int(top / 0.3) + 3):
        tube(mb, "Fer", [(xl - 0.22, y1 - 0.12, k * 0.3), (xl + 0.22, y1 - 0.12, k * 0.3)], 0.013, segs=4, col=col)
    return mb


def planche(L=1.0):
    """Planche de passage entre deux toits (longueur 1 m, étirée par l'instance)."""
    mb = MB()
    box(mb, "BoisBrut", (0, 0, 0.025), (L, 0.4, 0.05), col=(205, 180, 140, 255))
    for x in (-0.35, 0.0, 0.35):
        box(mb, "BoisBrut", (x, 0, -0.005), (0.05, 0.38, 0.02), col=(180, 155, 120, 255))
    return mb


def planche_rampe():
    """Planche inclinée : monte de z = 0 (x = -0,5) à z = 1 (x = +0,5) ; l'instance l'étire (longueur, dénivelé)."""
    mb = MB()
    w, t = 0.2, 0.04
    top = [(-0.5, -w, 0.0), (0.5, -w, 1.0), (0.5, w, 1.0), (-0.5, w, 0.0)]
    bot = [(x, y, z - t) for x, y, z in top]
    col = (205, 180, 140, 255)
    mb.quad("BoisBrut", top[0], top[1], top[2], top[3], [(0, 0), (1, 0), (1, 0.4), (0, 0.4)], col)
    mb.quad("BoisBrut", bot[3], bot[2], bot[1], bot[0], [(0, 0), (1, 0), (1, 0.4), (0, 0.4)], col)
    mb.quad("BoisBrut", bot[0], bot[1], top[1], top[0], [(0, 0), (1, 0), (1, 0.05), (0, 0.05)], col)
    mb.quad("BoisBrut", bot[2], bot[3], top[3], top[2], [(0, 0), (1, 0), (1, 0.05), (0, 0.05)], col)
    for k in range(5):
        x = -0.4 + 0.2 * k
        z = x + 0.5
        box(mb, "BoisBrut", (x, 0, z + 0.012), (0.03, 2 * w - 0.02, 0.024), col=(180, 155, 120, 255))
    return mb


# ------------------------------------------------------------------ inscriptions (atlas Graffitis)
_ATLAS = None


def graffiti(key, height=1.0, ground=False):
    global _ATLAS
    if _ATLAS is None:
        _ATLAS = json.load(open(os.path.join(_HERE, "tex", "Graffitis.json")))
    u0, v0, u1, v1, asp = _ATLAS[key]
    w = height * asp
    mb = MB()
    if ground:
        mb.add("Graffitis", [(-w / 2, -height / 2, 0.01), (w / 2, -height / 2, 0.01), (w / 2, height / 2, 0.01), (-w / 2, height / 2, 0.01)],
               [(0, 0, 1)], [(u0, v1), (u1, v1), (u1, v0), (u0, v0)], [WHITE], [[0, 1, 2], [0, 2, 3]])
    else:
        y = -0.012
        mb.add("Graffitis", [(-w / 2, y, 0), (w / 2, y, 0), (w / 2, y, height), (-w / 2, y, height)],
               [(0, -1, 0)], [(u0, v1), (u1, v1), (u1, v0), (u0, v0)], [WHITE], [[0, 1, 2], [0, 2, 3]])
    return mb


WALL_TAGS = ["zone_infectee", "ne_pas_entrer", "ils_sont_dedans", "survivants_mairie", "aidez_nous", "morts_ici", "pas_de_bruit",
             "croix", "fleche", "vide_3", "sang_main", "suie", "impacts"]
GROUND_TAGS = ["sang_1", "sang_2", "sang_flaque", "sang_trainee", "sos", "zone_infectee"]

ZOMBIE_BUILDERS = {
    "Z_Citadine": lambda: car("citadine", rng_seed=1),
    "Z_Berline": lambda: car("berline", rng_seed=2),
    "Z_Fourgon": lambda: car("fourgon", rng_seed=3),
    "Z_Epave": lambda: car("citadine", burnt=True, rng_seed=4),
    "Z_PlanchesFenetre": lambda: planches(1.2, 1.45, 1),
    "Z_PlanchesPorte": lambda: planches(1.3, 2.3, 2),
    "Z_SacsSable": sacs_sable,
    "Z_Barriere": barriere,
    "Z_Palette": lambda: palette(1),
    "Z_PilePalettes": lambda: palette(5),
    "Z_Caisse": lambda: caisse(1.0),
    "Z_CaissePetite": lambda: caisse(0.6),
    "Z_Pneus": pneus,
    "Z_SacsPoubelle": sacs_poubelle,
    "Z_Poubelle": poubelle,
    "Z_Conteneur": conteneur,
    "Z_Gravats": gravats,
    "Z_Brasero": brasero,
    "Z_Bache": bache,
    "Z_Matelas": matelas,
    "Z_TableRenversee": meuble_renverse,
    "Z_Echelle4": lambda: echelle(4.0),
    "Z_Echelle6": lambda: echelle(6.0),
    "Z_Echelle8": lambda: echelle(8.0),
    "Z_Echafaudage": echafaudage,
    "Z_Planche": planche,
    "Z_PlancheRampe": planche_rampe,
}
for _k in WALL_TAGS:
    ZOMBIE_BUILDERS[f"Z_Tag_{_k}"] = (lambda k: (lambda: graffiti(k, 1.0 if k not in ("suie",) else 1.6)))(_k)
for _k in GROUND_TAGS:
    ZOMBIE_BUILDERS[f"Z_Sol_{_k}"] = (lambda k: (lambda: graffiti(k, {"sos": 3.0, "zone_infectee": 1.6}.get(k, 1.2), ground=True)))(_k)

# collisions : ("box", sx, sy, sz) centrée, ("boxes", [cx, cy, cz, sx, sy, sz] * n) ou ("complex",)
ZOMBIE_COLLIDE = {
    "Z_Citadine": ("boxes", [0, 0, 0.55, 3.6, 1.56, 0.6, -0.4, 0, 1.1, 2.6, 1.42, 0.55]),
    "Z_Berline": ("boxes", [0, 0, 0.57, 4.4, 1.7, 0.58, -0.1, 0, 1.13, 2.6, 1.56, 0.58]),
    "Z_Fourgon": ("boxes", [0, 0, 0.6, 4.2, 1.72, 0.6, -0.3, 0, 1.35, 3.6, 1.58, 1.0]),
    "Z_Epave": ("boxes", [0, 0, 0.55, 3.6, 1.56, 0.6, -0.4, 0, 1.1, 2.6, 1.42, 0.55]),
    "Z_SacsSable": ("box", 2.0, 0.6, 0.48),
    "Z_Barriere": ("box", 2.0, 0.15, 1.1),
    "Z_PilePalettes": ("box", 1.2, 0.8, 0.72),
    "Z_Caisse": ("box", 1.0, 1.0, 1.0),
    "Z_CaissePetite": ("box", 0.6, 0.6, 0.6),
    "Z_Pneus": ("capsule", 0.32, 0.6),
    "Z_Poubelle": ("box", 0.62, 0.78, 1.06),
    "Z_Conteneur": ("box", 2.0, 1.05, 1.28),
    "Z_Brasero": ("capsule", 0.3, 0.9),
    "Z_Echelle4": ("boxes", [0, -0.16, 2.0, 0.55, 0.1, 4.0]),
    "Z_Echelle6": ("boxes", [0, -0.16, 3.0, 0.55, 0.1, 6.0]),
    "Z_Echelle8": ("boxes", [0, -0.16, 4.0, 0.55, 0.1, 8.0]),
    "Z_Echafaudage": ("complex",),
    "Z_Planche": ("box", 1.0, 0.4, 0.05),
    "Z_PlancheRampe": ("complex",),
    "Z_Gravats": ("box", 1.8, 1.4, 0.5),
}
