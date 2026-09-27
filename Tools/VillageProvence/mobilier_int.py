"""Mobilier d'intérieur provençal (instancié) : cuisine, séjour, chambre, salle de bain.

Repère local : centré en (0, 0), posé en z = 0, dos du meuble vers +Y (contre le mur), façade vers -Y.
Les parties BoisPeint, Toile et TissuProvence sont teintées par instance.
"""
import math
import numpy as np
from geomlib import MB, box, tube, revolve, nrm, disk, WHITE

WOOD = (255, 255, 255, 255)
DARK = (150, 120, 100, 255)


def legs(mb, w, d, h, r=0.025, inset=0.04, mat="BoisBrut"):
    for sx in (-1, 1):
        for sy in (-1, 1):
            box(mb, mat, (sx * (w / 2 - inset), sy * (d / 2 - inset), h / 2), (2 * r, 2 * r, h))


def table_cuisine(w=1.4, d=0.8, h=0.76):
    mb = MB()
    legs(mb, w, d, h - 0.04, r=0.03)
    box(mb, "BoisBrut", (0, 0, h - 0.02), (w, d, 0.04))
    box(mb, "BoisBrut", (0, 0, h - 0.1), (w - 0.1, d - 0.1, 0.1), faces=("-y", "+y", "-x", "+x"))
    # nappe provençale posée sur le plateau, qui retombe sur les côtés
    box(mb, "TissuProvence", (0, 0, h + 0.004), (w - 0.1, d + 0.04, 0.008), uv_scale=0.5)
    for sy in (-1, 1):
        box(mb, "TissuProvence", (0, sy * (d / 2 + 0.024), h - 0.1), (w - 0.1, 0.006, 0.2), uv_scale=0.5)
    # cruche et corbeille de fruits
    revolve(mb, "TerreCuite", [(0.0, 0), (0.06, 0.0), (0.075, 0.1), (0.05, 0.19), (0.035, 0.22), (0.0, 0.22)], (0.3, 0.1, h), segs=12)
    revolve(mb, "BoisBrut", [(0.0, 0), (0.1, 0.0), (0.14, 0.07), (0.0, 0.07)], (-0.25, -0.05, h), segs=12)
    for k in range(5):
        a = k * 1.3
        revolve(mb, "TerreCuite", [(0, 0), (0.035, 0.02), (0.04, 0.045), (0.03, 0.07), (0, 0.075)],
                (-0.25 + 0.06 * math.cos(a), -0.05 + 0.06 * math.sin(a), h + 0.05), segs=8, col=(230, 150 + 20 * k, 60, 255))
    return mb


def chaise_paillee():
    mb = MB()
    s = 0.45
    for x, y in ((-0.19, -0.19), (0.19, -0.19)):
        tube(mb, "BoisBrut", [(x, y, 0), (x, y, s)], 0.018, segs=6)
    for x in (-0.19, 0.19):
        tube(mb, "BoisBrut", [(x, 0.19, 0), (x, 0.21, 0.95)], 0.02, segs=6)
    for z in (0.62, 0.78, 0.92):
        box(mb, "BoisBrut", (0, 0.2 + (z - 0.45) * 0.04, z), (0.38, 0.02, 0.05))
    for y in (-0.19, 0.19):
        tube(mb, "BoisBrut", [(-0.19, y, 0.15), (0.19, y, 0.15)], 0.01, segs=5)
    box(mb, "Paille", (0, 0, s), (0.42, 0.42, 0.035), uv_scale=0.5)
    return mb


def chaise_renversee():
    """Chaise tombée sur le dossier (ambiance de maison abandonnée)."""
    mb = MB()
    c = chaise_paillee()
    arr = c.arrays()
    ang = math.radians(-82)
    ca, sa = math.cos(ang), math.sin(ang)
    for mat, a in arr.items():
        P = a["P"].copy()
        N = a["N"].copy()
        y, z = P[:, 1].copy(), P[:, 2].copy()
        P[:, 1], P[:, 2] = y * ca - z * sa, y * sa + z * ca
        ny, nz = N[:, 1].copy(), N[:, 2].copy()
        N[:, 1], N[:, 2] = ny * ca - nz * sa, ny * sa + nz * ca
        P[:, 2] -= P[:, 2].min()
        P[:, 1] -= (P[:, 1].max() + P[:, 1].min()) / 2
        mb.add(mat, P, N, a["UV"], a["C"], a["I"])
    return mb


def plan_travail(w=2.4, d=0.62, h=0.9):
    """Cuisine : placards peints, plan en carreaux de terre cuite, évier en grès, cuisinière, crédence en faïence."""
    mb = MB()
    box(mb, "BoisPeint", (0, 0.02, 0.05), (w - 0.04, d - 0.08, 0.1), col=(120, 110, 100, 255))
    box(mb, "BoisPeint", (0, 0.0, (h - 0.04) / 2 + 0.05), (w, d - 0.04, h - 0.14))
    nd = int(w / 0.6)
    for k in range(nd):
        x = -w / 2 + (k + 0.5) * w / nd
        box(mb, "BoisPeint", (x, -d / 2 + 0.005, 0.47), (w / nd - 0.04, 0.02, 0.62))
        box(mb, "BoisPeint", (x, -d / 2 - 0.01, 0.47), (w / nd - 0.16, 0.012, 0.48))
        tube(mb, "Fer", [(x + w / nd / 2 - 0.08, -d / 2 - 0.03, 0.62), (x + w / nd / 2 - 0.08, -d / 2 - 0.03, 0.7)], 0.008, segs=5)
    # plan de travail en tomettes carrées
    box(mb, "TerreCuite", (0, 0, h - 0.02), (w + 0.02, d, 0.04), uv_scale=0.15)
    # évier en grès (cuvette creuse)
    sx = -w / 2 + 0.55
    box(mb, "Porcelaine", (sx, -0.02, h + 0.005), (0.62, 0.46, 0.012))
    box(mb, "Fer", (sx, -0.02, h + 0.012), (0.48, 0.34, 0.004), col=(40, 40, 40, 255))
    tube(mb, "Fer", [(sx, 0.22, h), (sx, 0.22, h + 0.3), (sx, 0.08, h + 0.3), (sx, 0.08, h + 0.24)], 0.012, segs=6, col=(210, 210, 210, 255))
    # cuisinière (dessus en fonte, quatre feux)
    cx = w / 2 - 0.45
    box(mb, "Fer", (cx, -0.02, h + 0.01), (0.6, 0.55, 0.02), col=(35, 35, 38, 255))
    for dx in (-0.14, 0.14):
        for dy in (-0.12, 0.12):
            revolve(mb, "Fer", [(0, 0), (0.08, 0), (0.08, 0.02), (0, 0.02)], (cx + dx, -0.02 + dy, h + 0.02), segs=12, col=(20, 20, 20, 255))
    # crédence en faïence
    box(mb, "Faience", (0, d / 2 - 0.005, h + 0.3), (w, 0.01, 0.6), uv_scale=1.0, faces=("-y",))
    # casseroles et bocaux
    revolve(mb, "Fer", [(0, 0), (0.11, 0), (0.11, 0.12), (0, 0.12)], (cx - 0.14, -0.14, h + 0.04), segs=14, col=(170, 170, 175, 255))
    for k in range(3):
        revolve(mb, "Verre", [(0, 0), (0.05, 0), (0.05, 0.16), (0.04, 0.18), (0, 0.18)], (-0.2 + k * 0.13, 0.2, h), segs=10)
    return mb


def frigo(w=0.6, d=0.62, h=1.55):
    mb = MB()
    box(mb, "Porcelaine", (0, 0, h / 2), (w, d, h))
    box(mb, "Fer", (0, -d / 2 - 0.005, h * 0.62), (w - 0.02, 0.006, 0.01), col=(120, 120, 120, 255))
    tube(mb, "Fer", [(w / 2 - 0.07, -d / 2 - 0.035, h * 0.7), (w / 2 - 0.07, -d / 2 - 0.035, h * 0.85)], 0.012, segs=6, col=(200, 200, 200, 255))
    return mb


def buffet(w=1.3, d=0.5, h=2.0):
    """Vaisselier provençal : bas à portes, haut ouvert avec étagères et assiettes."""
    mb = MB()
    box(mb, "BoisPeint", (0, 0, 0.45), (w, d, 0.9))
    box(mb, "BoisBrut", (0, -0.02, 0.92), (w + 0.06, d + 0.04, 0.04))
    for sx in (-1, 1):
        box(mb, "BoisPeint", (sx * w / 4, -d / 2 - 0.01, 0.5), (w / 2 - 0.08, 0.02, 0.62))
        box(mb, "BoisBrut", (sx * w / 4, -d / 2 - 0.022, 0.5), (w / 2 - 0.22, 0.01, 0.42), col=DARK)
    top_d = 0.3
    yb = d / 2 - top_d / 2
    box(mb, "BoisPeint", (0, d / 2 - 0.01, 1.45), (w - 0.04, 0.02, 1.06))
    for sx in (-1, 1):
        box(mb, "BoisPeint", (sx * (w / 2 - 0.02), yb, 1.45), (0.04, top_d, 1.06))
    box(mb, "BoisBrut", (0, yb - 0.02, h - 0.03), (w + 0.1, top_d + 0.08, 0.06))
    for z in (1.25, 1.6):
        box(mb, "BoisPeint", (0, yb, z), (w - 0.06, top_d, 0.025))
        for k in range(5):
            x = -w / 2 + 0.2 + k * (w - 0.4) / 4
            disk(mb, "Porcelaine", (x, d / 2 - 0.06, z + 0.13), 0.11, (0, -1, 0.25), (0, 0, 1), segs=16)
    return mb


def canape(w=2.0, d=0.9, h=0.85):
    mb = MB()
    box(mb, "BoisBrut", (0, 0, 0.06), (w - 0.1, d - 0.1, 0.12), col=DARK)
    box(mb, "Toile", (0, -0.05, 0.3), (w - 0.3, d - 0.2, 0.26), uv_scale=1)
    box(mb, "Toile", (0, d / 2 - 0.1, 0.55), (w - 0.1, 0.2, 0.6), uv_scale=1)
    for sx in (-1, 1):
        box(mb, "Toile", (sx * (w / 2 - 0.1), 0, 0.37), (0.2, d, 0.5), uv_scale=1)
    for k in (-1, 0, 1):
        box(mb, "TissuProvence", (k * 0.5, 0.16, 0.6), (0.42, 0.14, 0.4), uv_scale=0.5, pitch=math.radians(-12))
    return mb


def fauteuil():
    mb = MB()
    w, d = 0.85, 0.85
    box(mb, "BoisBrut", (0, 0, 0.06), (w - 0.1, d - 0.1, 0.12), col=DARK)
    box(mb, "Toile", (0, -0.05, 0.3), (w - 0.3, d - 0.2, 0.26), uv_scale=1)
    box(mb, "Toile", (0, d / 2 - 0.1, 0.58), (w - 0.1, 0.2, 0.66), uv_scale=1)
    for sx in (-1, 1):
        box(mb, "Toile", (sx * (w / 2 - 0.1), 0, 0.37), (0.2, d, 0.5), uv_scale=1)
    box(mb, "TissuProvence", (0, 0.15, 0.6), (0.4, 0.14, 0.4), uv_scale=0.5, pitch=math.radians(-12))
    return mb


def table_basse(w=1.0, d=0.6, h=0.42):
    mb = MB()
    legs(mb, w, d, h - 0.04, r=0.025)
    box(mb, "BoisBrut", (0, 0, h - 0.02), (w, d, 0.04))
    box(mb, "BoisBrut", (0, 0, 0.1), (w - 0.1, d - 0.1, 0.02))
    for k in range(3):
        box(mb, "Toile", (-0.25 + k * 0.03, 0.05, h + 0.01 + k * 0.025), (0.22, 0.3, 0.024), yaw=0.2 * k, col=((180, 60, 50, 255), (60, 90, 140, 255), (220, 200, 150, 255))[k])
    return mb


def cheminee(w=1.5, d=0.55, h=1.25, hood=2.6):
    """Cheminée de mas : jambages et linteau en pierre, hotte enduite jusqu'au plafond, foyer et bûches."""
    mb = MB()
    for sx in (-1, 1):
        box(mb, "PierreTaille", (sx * (w / 2 - 0.12), 0, h / 2), (0.24, d, h), uv_scale=1.5)
    box(mb, "PierreTaille", (0, 0, h + 0.1), (w + 0.1, d + 0.08, 0.2), uv_scale=1.5)
    box(mb, "BoisBrut", (0, -0.03, h + 0.24), (w + 0.2, d + 0.12, 0.08))
    # hotte trapézoïdale (enduit)
    hb = h + 0.28
    top_w, top_d = w * 0.6, d * 0.6
    pts = [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    tops = [(-top_w / 2, d / 2 - top_d), (top_w / 2, d / 2 - top_d), (top_w / 2, d / 2), (-top_w / 2, d / 2)]
    col = (242, 236, 224, 255)
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        c, e = tops[(i + 1) % 4], tops[i]
        mb.quad("Enduit", (a[0], a[1], hb), (b[0], b[1], hb), (c[0], c[1], hood), (e[0], e[1], hood), [(0, 0), (1, 0), (1, 1), (0, 1)], col)
    # foyer : fond noirci, sole, chenets, bûches
    box(mb, "Fer", (0, d / 2 - 0.04, h / 2), (w - 0.48, 0.04, h), col=(25, 22, 20, 255))
    box(mb, "PierreTaille", (0, 0, 0.04), (w - 0.48, d, 0.08), col=(90, 85, 80, 255))
    for k in range(3):
        tube(mb, "BoisBrut", [(-0.3, -0.05 + k * 0.1, 0.14 + (k % 2) * 0.08), (0.3, 0.02 + k * 0.08, 0.14 + (k % 2) * 0.08)], 0.06, segs=7, col=DARK)
    return mb


def bibliotheque(w=1.0, d=0.35, h=1.9):
    mb = MB()
    rng = np.random.default_rng(4)
    box(mb, "BoisBrut", (0, d / 2 - 0.01, h / 2), (w, 0.02, h))
    for sx in (-1, 1):
        box(mb, "BoisBrut", (sx * (w / 2 - 0.015), 0, h / 2), (0.03, d, h))
    for z in (0.05, 0.45, 0.85, 1.25, 1.65, h - 0.015):
        box(mb, "BoisBrut", (0, 0, z), (w - 0.06, d, 0.03))
    books = [(200, 60, 45), (60, 90, 140), (220, 190, 120), (70, 110, 70), (150, 110, 60), (230, 220, 200), (110, 50, 70)]
    for z in (0.065, 0.465, 0.865, 1.265):
        x = -w / 2 + 0.05
        while x < w / 2 - 0.08:
            bw = rng.uniform(0.025, 0.06)
            bh = rng.uniform(0.2, 0.32)
            c = books[rng.integers(len(books))]
            if rng.random() < 0.12:
                x += 0.08
                continue
            box(mb, "Toile", (x + bw / 2, 0.02, z + bh / 2), (bw * 0.95, d - 0.1, bh), col=c + (255,))
            x += bw
    return mb


def tapis(w=2.0, d=1.4):
    mb = MB()
    box(mb, "TissuProvence", (0, 0, 0.005), (w, d, 0.01), uv_scale=0.5, faces=("+z", "-x", "+x", "-y", "+y"))
    return mb


def lit(w=1.6, L=2.05, double=True):
    """Lit en bois avec tête de lit, matelas, boutis provençal, oreillers. Tête contre le mur (+Y)."""
    mb = MB()
    hb = 1.05 if double else 0.9
    box(mb, "BoisBrut", (0, L / 2 - 0.03, hb / 2), (w + 0.08, 0.06, hb))
    box(mb, "BoisBrut", (0, -L / 2 + 0.03, 0.3), (w + 0.08, 0.06, 0.6))
    for sx in (-1, 1):
        box(mb, "BoisBrut", (sx * (w / 2 + 0.01), 0, 0.3), (0.04, L - 0.1, 0.2))
    box(mb, "Toile", (0, 0, 0.42), (w - 0.02, L - 0.12, 0.2), col=(245, 244, 238, 255))
    # boutis (couvre-lit matelassé) qui retombe sur les côtés
    box(mb, "TissuProvence", (0, -0.12, 0.535), (w + 0.1, L - 0.4, 0.04), uv_scale=0.5)
    for sx in (-1, 1):
        box(mb, "TissuProvence", (sx * (w / 2 + 0.05), -0.12, 0.4), (0.02, L - 0.4, 0.28), uv_scale=0.5)
    n = 2 if double else 1
    for k in range(n):
        x = 0 if n == 1 else (k - 0.5) * (w / 2)
        box(mb, "Toile", (x, L / 2 - 0.3, 0.6), (w / n - 0.12, 0.35, 0.14), col=(250, 250, 246, 255), pitch=math.radians(-15))
    return mb


def chevet():
    mb = MB()
    w, d, h = 0.45, 0.4, 0.55
    legs(mb, w, d, 0.12, r=0.02)
    box(mb, "BoisBrut", (0, 0, 0.12 + (h - 0.12) / 2), (w, d, h - 0.12))
    box(mb, "BoisBrut", (0, -d / 2 - 0.01, 0.42), (w - 0.06, 0.02, 0.14), col=DARK)
    revolve(mb, "TerreCuite", [(0, 0), (0.07, 0), (0.08, 0.12), (0.03, 0.2), (0.01, 0.32), (0, 0.32)], (0.08, 0.05, h), segs=10)
    revolve(mb, "Toile", [(0.13, 0.26), (0.09, 0.44), (0.0, 0.44)], (0.08, 0.05, h), segs=14, col=(240, 225, 190, 255))
    return mb


def armoire(w=1.4, d=0.6, h=2.2):
    """Armoire provençale : corniche chantournée, deux portes à panneaux, pieds tournés."""
    mb = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            revolve(mb, "BoisBrut", [(0, 0), (0.04, 0), (0.05, 0.06), (0.03, 0.12), (0, 0.12)], (sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), 0), segs=8)
    box(mb, "BoisBrut", (0, 0, 0.12 + (h - 0.3) / 2), (w, d, h - 0.3))
    box(mb, "BoisBrut", (0, -0.02, h - 0.12), (w + 0.12, d + 0.08, 0.1))
    box(mb, "BoisBrut", (0, -0.03, h - 0.04), (w + 0.18, d + 0.1, 0.07))
    for sx in (-1, 1):
        x = sx * w / 4
        for z0, z1 in ((0.3, 1.0), (1.1, 1.8)):
            box(mb, "BoisBrut", (x, -d / 2 - 0.012, (z0 + z1) / 2), (w / 2 - 0.22, 0.025, z1 - z0), col=(215, 180, 150, 255))
        box(mb, "Fer", (x - sx * (w / 4 - 0.1), -d / 2 - 0.03, 1.05), (0.02, 0.02, 0.35), col=(160, 150, 120, 255))
    return mb


def commode(w=1.1, d=0.5, h=0.85):
    mb = MB()
    legs(mb, w, d, 0.1)
    box(mb, "BoisBrut", (0, 0, 0.1 + (h - 0.12) / 2), (w, d, h - 0.12))
    box(mb, "BoisBrut", (0, -0.01, h - 0.01), (w + 0.04, d + 0.03, 0.03))
    for k in range(3):
        z = 0.22 + k * 0.22
        box(mb, "BoisBrut", (0, -d / 2 - 0.01, z), (w - 0.08, 0.02, 0.18), col=(215, 180, 150, 255))
        for sx in (-1, 1):
            box(mb, "Fer", (sx * 0.25, -d / 2 - 0.03, z), (0.08, 0.02, 0.02), col=(160, 150, 120, 255))
    revolve(mb, "TerreCuite", [(0, 0), (0.08, 0), (0.1, 0.1), (0.06, 0.22), (0.07, 0.26), (0, 0.26)], (0.3, 0.05, h), segs=12, col=(90, 120, 170, 255))
    return mb


def baignoire(w=1.7, d=0.75, h=0.58):
    """Baignoire en fonte émaillée sur pieds de lion, à poser le long d'un mur."""
    mb = MB()
    t = 0.05
    box(mb, "Porcelaine", (0, 0, 0.14 + (h - 0.14) / 2), (w, d, h - 0.14), faces=("-y", "+y", "-x", "+x", "-z"))
    # bord et intérieur
    box(mb, "Porcelaine", (0, -d / 2 + t / 2, h), (w, t, 0.03))
    box(mb, "Porcelaine", (0, d / 2 - t / 2, h), (w, t, 0.03))
    for sx in (-1, 1):
        box(mb, "Porcelaine", (sx * (w / 2 - t / 2), 0, h), (t, d, 0.03))
    box(mb, "Porcelaine", (0, 0, 0.2), (w - 2 * t, d - 2 * t, 0.02), faces=("+z",))
    for sy in (-1, 1):
        mb.quad("Porcelaine", (-w / 2 + t, sy * (d / 2 - t), 0.2), (w / 2 - t, sy * (d / 2 - t), 0.2), (w / 2 - t, sy * (d / 2 - t), h), (-w / 2 + t, sy * (d / 2 - t), h),
                [(0, 0), (1, 0), (1, 1), (0, 1)], n=(0, -sy, 0))
    for sx in (-1, 1):
        mb.quad("Porcelaine", (sx * (w / 2 - t), d / 2 - t, 0.2), (sx * (w / 2 - t), -d / 2 + t, 0.2), (sx * (w / 2 - t), -d / 2 + t, h), (sx * (w / 2 - t), d / 2 - t, h),
                [(0, 0), (1, 0), (1, 1), (0, 1)], n=(-sx, 0, 0))
    for sx in (-1, 1):
        for sy in (-1, 1):
            revolve(mb, "Fer", [(0, 0), (0.05, 0), (0.03, 0.08), (0.04, 0.15), (0, 0.15)], (sx * (w / 2 - 0.15), sy * (d / 2 - 0.12), 0), segs=8, col=(180, 160, 110, 255))
    tube(mb, "Fer", [(w / 2 - 0.12, d / 2 - 0.02, h), (w / 2 - 0.12, d / 2 - 0.02, h + 0.25), (w / 2 - 0.12, d / 2 - 0.18, h + 0.25)], 0.012, segs=6, col=(210, 210, 210, 255))
    return mb


def wc():
    mb = MB()
    revolve(mb, "Porcelaine", [(0, 0), (0.13, 0), (0.12, 0.2), (0.18, 0.36), (0.19, 0.4), (0.0, 0.4)], (0, -0.05, 0), segs=16)
    box(mb, "BoisBrut", (0, -0.05, 0.41), (0.38, 0.44, 0.025))
    box(mb, "Porcelaine", (0, 0.24, 0.62), (0.42, 0.18, 0.4))
    box(mb, "Porcelaine", (0, 0.24, 0.83), (0.44, 0.2, 0.03))
    return mb


def lavabo():
    """Lavabo sur colonne, robinet, miroir au-dessus (dos au mur)."""
    mb = MB()
    revolve(mb, "Porcelaine", [(0, 0), (0.12, 0), (0.08, 0.1), (0.08, 0.7), (0, 0.7)], (0, 0.08, 0), segs=12)
    box(mb, "Porcelaine", (0, 0.02, 0.8), (0.62, 0.46, 0.14))
    box(mb, "Fer", (0, 0.0, 0.875), (0.44, 0.3, 0.004), col=(200, 200, 200, 255))
    tube(mb, "Fer", [(0, 0.2, 0.87), (0, 0.2, 0.98), (0, 0.1, 0.98)], 0.012, segs=6, col=(210, 210, 210, 255))
    box(mb, "BoisPeint", (0, 0.225, 1.4), (0.62, 0.03, 0.72))
    box(mb, "Miroir", (0, 0.205, 1.4), (0.52, 0.01, 0.62), faces=("-y",))
    box(mb, "BoisPeint", (0, 0.13, 1.02), (0.5, 0.16, 0.02))
    return mb


def suspension(drop=0.8):
    """Suspension de cuisine : cordon depuis le plafond (z = 0) et abat-jour émaillé."""
    mb = MB()
    tube(mb, "Fer", [(0, 0, 0), (0, 0, -drop)], 0.006, segs=5, col=(40, 40, 40, 255))
    revolve(mb, "Porcelaine", [(0.0, -drop - 0.02), (0.06, -drop - 0.02), (0.22, -drop - 0.16), (0.2, -drop - 0.17), (0.0, -drop - 0.05)], (0, 0, 0), segs=16)
    return mb


def carton(w=0.5, d=0.4, h=0.35):
    mb = MB()
    box(mb, "Toile", (0, 0, h / 2), (w, d, h), col=(170, 130, 85, 255))
    box(mb, "Toile", (0, -d / 4, h + 0.005), (w, d / 2 + 0.02, 0.01), col=(155, 118, 76, 255), pitch=math.radians(20))
    return mb


# ------------------------------------------------------------------ meubles ajoutés : intérieurs variés
def table_manger(w=2.0, d=0.9, h=0.76):
    """Grande table de salle à manger en noyer, pieds tournés, chemin de table et chandelier."""
    mb = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            revolve(mb, "BoisVernis", [(0.0, 0), (0.035, 0), (0.035, 0.1), (0.05, 0.16), (0.03, 0.3), (0.045, 0.45), (0.035, 0.55),
                                      (0.04, h - 0.04), (0.0, h - 0.04)], (sx * (w / 2 - 0.1), sy * (d / 2 - 0.08), 0), segs=10)
    box(mb, "BoisVernis", (0, 0, h - 0.02), (w, d, 0.045))
    box(mb, "BoisVernis", (0, 0, h - 0.1), (w - 0.2, d - 0.16, 0.1), faces=("-y", "+y", "-x", "+x"))
    box(mb, "TissuProvence", (0, 0, h + 0.004), (w * 0.8, 0.34, 0.006), uv_scale=0.5)
    revolve(mb, "Bronze", [(0, 0), (0.07, 0), (0.07, 0.015), (0.015, 0.03), (0.012, 0.25), (0.03, 0.27), (0.0, 0.27)], (0, 0, h), segs=10)
    tube(mb, "Bronze", [(-0.14, 0, h + 0.2), (0.14, 0, h + 0.2)], 0.008, segs=5)
    for x in (-0.14, 0.0, 0.14):
        revolve(mb, "Porcelaine", [(0, 0), (0.012, 0), (0.012, 0.12), (0, 0.12)], (x, 0, h + 0.27 if x == 0 else h + 0.2), segs=6)
    for k in range(6):
        x = -w / 2 + 0.3 + (k % 3) * (w - 0.6) / 2
        y = (-1 if k < 3 else 1) * (d / 2 - 0.2)
        disk(mb, "Porcelaine", (x, y, h + 0.006), 0.13, (0, 0, 1), (0, 1, 0), segs=16)
    return mb


def piano(w=1.48, d=0.6, h=1.28):
    """Piano droit en bois sombre : clavier, pupitre, pédales, bougeoirs."""
    mb = MB()
    box(mb, "BoisVernis", (0, 0.1, h / 2), (w, d - 0.2, h))
    box(mb, "BoisVernis", (0, -0.1, 0.36), (w, 0.32, 0.72), faces=("-y", "-x", "+x", "+z"))
    box(mb, "Porcelaine", (0, -0.17, 0.735), (w - 0.14, 0.15, 0.03))
    for k in range(36):
        x = -w / 2 + 0.1 + k * (w - 0.2) / 36
        if k % 7 not in (2, 6):
            box(mb, "Fer", (x + (w - 0.2) / 72, -0.14, 0.757), (0.012, 0.09, 0.014), col=(20, 20, 20, 255))
    box(mb, "BoisVernis", (0, -0.03, 0.95), (w - 0.3, 0.02, 0.25), pitch=math.radians(-12))
    box(mb, "Toile", (0.1, -0.05, 0.98), (0.35, 0.01, 0.25), col=(236, 230, 214, 255), pitch=math.radians(-12))
    for sx in (-1, 1):
        box(mb, "BoisVernis", (sx * (w / 2 - 0.04), -0.26, 0.4), (0.06, 0.06, 0.8))
        revolve(mb, "Bronze", [(0, 0), (0.04, 0), (0.02, 0.02), (0.012, 0.1), (0.03, 0.12), (0, 0.12)], (sx * 0.55, -0.08, 0.9), segs=8)
    for x in (-0.08, 0.0, 0.08):
        box(mb, "Bronze", (x, -0.24, 0.05), (0.035, 0.1, 0.012))
    return mb


def horloge():
    """Horloge comtoise : caisse galbée peinte, cadran émaillé, balancier en laiton."""
    mb = MB()
    box(mb, "BoisPeint", (0, 0, 0.15), (0.52, 0.32, 0.3))
    revolve(mb, "BoisPeint", [(0.2, 0), (0.17, 0.3), (0.14, 0.9), (0.18, 1.4), (0.2, 1.55), (0.0, 1.55)], (0, 0.02, 0.3), segs=4)
    box(mb, "BoisPeint", (0, 0, 2.02), (0.46, 0.3, 0.44))
    box(mb, "BoisBrut", (0, 0, 2.27), (0.5, 0.34, 0.06), col=DARK)
    disk(mb, "Porcelaine", (0, -0.155, 2.02), 0.15, (0, -1, 0), (0, 0, 1), segs=24)
    for k in range(12):
        a = k * math.pi / 6
        box(mb, "Fer", (0.12 * math.sin(a), -0.16, 2.02 + 0.12 * math.cos(a)), (0.012, 0.004, 0.02), col=(20, 20, 20, 255))
    box(mb, "Fer", (0.03, -0.162, 2.05), (0.012, 0.004, 0.09), col=(20, 20, 20, 255), pitch=0.0)
    disk(mb, "Bronze", (0, -0.13, 1.0), 0.11, (0, -1, 0), (0, 0, 1), segs=18)
    box(mb, "Bronze", (0, -0.12, 1.4), (0.02, 0.01, 0.75))
    return mb


def machine_coudre():
    """Machine à coudre à pédale sur son meuble en fonte."""
    mb = MB()
    for sx in (-1, 1):
        box(mb, "Fer", (sx * 0.36, 0, 0.36), (0.04, 0.4, 0.7), col=(30, 30, 30, 255))
    tube(mb, "Fer", [(-0.36, 0, 0.12), (0.36, 0, 0.12)], 0.015, segs=6, col=(30, 30, 30, 255))
    box(mb, "Fer", (0, -0.05, 0.1), (0.4, 0.28, 0.02), col=(30, 30, 30, 255))
    revolve(mb, "Fer", [(0, 0), (0.2, 0), (0.2, 0.02), (0, 0.02)], (0.28, 0.1, 0.35), segs=16, col=(30, 30, 30, 255))
    box(mb, "BoisBrut", (0, 0, 0.74), (0.88, 0.46, 0.035))
    box(mb, "Carrosserie", (0.05, 0.02, 0.8), (0.4, 0.14, 0.08), col=(25, 25, 25, 255))
    box(mb, "Carrosserie", (0.21, 0.02, 0.9), (0.08, 0.12, 0.2), col=(25, 25, 25, 255))
    box(mb, "Carrosserie", (0.05, 0.02, 1.0), (0.38, 0.1, 0.08), col=(25, 25, 25, 255))
    box(mb, "Carrosserie", (-0.13, 0.02, 0.9), (0.06, 0.08, 0.16), col=(25, 25, 25, 255))
    revolve(mb, "Bronze", [(0, 0), (0.06, 0), (0.06, 0.02), (0, 0.02)], (0.28, 0.02, 0.9), segs=10)
    box(mb, "TissuProvence", (-0.25, -0.05, 0.765), (0.3, 0.25, 0.01), uv_scale=0.5)
    return mb


def bureau(w=1.2, d=0.6, h=0.76):
    """Bureau à caissons, lampe, livres et papiers."""
    mb = MB()
    for sx in (-1, 1):
        box(mb, "BoisVernis", (sx * (w / 2 - 0.2), 0, (h - 0.03) / 2), (0.38, d - 0.04, h - 0.03))
        for k in range(3):
            box(mb, "BoisVernis", (sx * (w / 2 - 0.2), -d / 2 + 0.01, 0.13 + k * 0.23), (0.34, 0.02, 0.2))
    box(mb, "BoisVernis", (0, 0, h - 0.015), (w, d, 0.03))
    box(mb, "Toile", (0.05, -0.05, h + 0.002), (0.5, 0.35, 0.004), col=(60, 90, 60, 255))
    for k in range(4):
        box(mb, "Toile", (-0.4 + k * 0.035, 0.18, h + 0.12), (0.03, 0.18, 0.24), col=((150, 40, 40), (40, 60, 110), (170, 140, 60), (60, 90, 50))[k] + (255,))
    box(mb, "Toile", (0.1, -0.02, h + 0.006), (0.21, 0.297, 0.004), col=(236, 232, 220, 255))
    revolve(mb, "Bronze", [(0, 0), (0.08, 0), (0.02, 0.03), (0.015, 0.32), (0, 0.32)], (0.42, 0.15, h), segs=10)
    revolve(mb, "Toile", [(0.16, 0), (0.09, 0.16), (0.0, 0.16)], (0.42, 0.15, h + 0.26), segs=12, col=(222, 190, 120, 255))
    return mb


def etabli(w=2.0, d=0.7, h=0.9):
    """Établi de menuisier : plateau épais, étau, outils, panneau d'outils au mur."""
    mb = MB()
    legs(mb, w, d, h - 0.08, r=0.045)
    box(mb, "BoisBrut", (0, 0, h - 0.04), (w, d, 0.08))
    box(mb, "BoisBrut", (0, 0, 0.2), (w - 0.2, d - 0.1, 0.03))
    box(mb, "Fer", (w / 2 - 0.2, -d / 2 - 0.05, h - 0.05), (0.18, 0.12, 0.1), col=(60, 70, 80, 255))
    tube(mb, "Fer", [(w / 2 - 0.2, -d / 2 - 0.1, h - 0.05), (w / 2 - 0.2, -d / 2 - 0.16, h - 0.05)], 0.01, segs=5)
    box(mb, "BoisPeint", (0, d / 2 - 0.01, h + 0.55), (w, 0.02, 0.9), col=(170, 150, 110, 255))
    for k in range(9):
        x = -w / 2 + 0.2 + k * (w - 0.4) / 8
        L = 0.2 + 0.15 * ((k * 7) % 3)
        tube(mb, "Fer" if k % 2 else "BoisBrut", [(x, d / 2 - 0.04, h + 0.85), (x, d / 2 - 0.04, h + 0.85 - L)], 0.012 + 0.006 * (k % 2), segs=5,
             col=(90, 90, 95, 255) if k % 2 else WHITE)
    box(mb, "Fer", (-0.4, -0.05, h + 0.03), (0.5, 0.06, 0.05), col=(80, 50, 30, 255))
    box(mb, "BoisBrut", (0.2, 0.05, h + 0.05), (0.6, 0.12, 0.1))
    return mb


def tonneau():
    """Tonneau de vin couché sur son chantier."""
    mb = MB()
    prof = [(0.26, 0.0), (0.31, 0.2), (0.33, 0.45), (0.31, 0.7), (0.26, 0.9)]
    arr = MB()
    revolve(arr, "BoisBrut", [(0.0, 0.0)] + prof + [(0.0, 0.9)], (0, 0, 0), segs=16, col=(150, 110, 80, 255))
    for z in (0.08, 0.26, 0.64, 0.82):
        r = np.interp(z, [p[1] for p in prof], [p[0] for p in prof]) + 0.006
        revolve(arr, "Fer", [(r, z - 0.02), (r, z + 0.02)], (0, 0, 0), segs=16, col=(40, 40, 40, 255))
    for mat, a in arr.arrays().items():
        P = a["P"].copy()
        N = a["N"].copy()
        P = np.column_stack([P[:, 2] - 0.45, P[:, 1], P[:, 0] + 0.45])
        N = np.column_stack([N[:, 2], N[:, 1], N[:, 0]])
        mb.add(mat, P, N, a["UV"], a["C"], a["I"][:, [0, 2, 1]])   # échange de deux axes = symétrie : on retourne les faces
    for sx in (-1, 1):
        box(mb, "BoisBrut", (sx * 0.3, 0, 0.06), (0.1, 0.7, 0.12), col=DARK)
    box(mb, "BoisBrut", (0.46, 0, 0.45), (0.02, 0.08, 0.06), col=DARK)
    return mb


def etagere(w=1.0, d=0.35, h=1.8, fill="bocaux"):
    """Étagère ouverte : bocaux (conserves maison), outils ou bouteilles."""
    mb = MB()
    for sx in (-1, 1):
        box(mb, "BoisBrut", (sx * (w / 2 - 0.02), 0, h / 2), (0.04, d, h))
    rng = np.random.default_rng(len(fill) * 13)
    for k, z in enumerate((0.05, 0.5, 0.95, 1.4, h - 0.02)):
        box(mb, "BoisBrut", (0, 0, z), (w - 0.04, d, 0.025))
        if z > h - 0.1:
            continue
        x = -w / 2 + 0.1
        while x < w / 2 - 0.1:
            if fill == "bouteilles":
                P = [(0, 0), (0.037, 0), (0.037, 0.2), (0.015, 0.26), (0.013, 0.31), (0, 0.31)]
                revolve(mb, "Verre", P, (x, 0.02, z + 0.012), segs=8)
                x += 0.09
            elif fill == "outils":
                if rng.random() < 0.5:
                    box(mb, "Carrosserie", (x + 0.1, 0, z + 0.08), (0.24, 0.16, 0.14), col=((150, 40, 30), (40, 70, 120), (60, 90, 50))[k % 3] + (255,))
                    x += 0.3
                else:
                    box(mb, "Toile", (x + 0.08, 0, z + 0.11), (0.18, 0.26, 0.2), col=(170, 130, 85, 255))
                    x += 0.24
            else:
                hh = rng.uniform(0.12, 0.22)
                revolve(mb, "Verre", [(0, 0), (0.045, 0), (0.045, hh), (0.035, hh + 0.02), (0, hh + 0.02)], (x, 0.0, z + 0.012), segs=8)
                revolve(mb, "Toile", [(0.036, hh + 0.02), (0.036, hh + 0.04), (0.0, hh + 0.04)], (x, 0.0, z + 0.012), segs=8,
                        col=((200, 60, 50), (230, 200, 90), (120, 150, 90))[int(rng.integers(3))] + (255,))
                x += 0.11
    return mb


def evier_pierre(w=1.2, d=0.6, h=0.88):
    """Évier en pierre sur maçonnerie, rideau en tissu provençal, pompe à eau."""
    mb = MB()
    box(mb, "PierreTaille", (0, 0, h - 0.1), (w, d, 0.2), uv_scale=3.0)
    box(mb, "Fer", (0.1, -0.02, h + 0.002), (0.6, 0.4, 0.004), col=(90, 85, 75, 255))
    for sx in (-1, 1):
        box(mb, "Enduit", (sx * (w / 2 - 0.06), 0.02, (h - 0.2) / 2), (0.12, d - 0.04, h - 0.2), col=(236, 230, 218, 255), uv_scale=3.0)
    box(mb, "TissuProvence", (0, -d / 2 + 0.06, (h - 0.2) / 2 + 0.02), (w - 0.24, 0.01, h - 0.24), uv_scale=0.5)
    tube(mb, "Fer", [(-0.1, d / 2 - 0.08, h), (-0.1, d / 2 - 0.08, h + 0.4), (-0.1, d / 2 - 0.3, h + 0.4), (-0.1, d / 2 - 0.3, h + 0.33)], 0.02,
         segs=6, col=(60, 60, 60, 255))
    revolve(mb, "TerreCuite", [(0, 0), (0.1, 0), (0.13, 0.12), (0.1, 0.24), (0.06, 0.28), (0, 0.28)], (-w / 2 + 0.22, -0.05, h), segs=12)
    return mb


def petrin(w=1.25, d=0.55, h=0.9):
    """Pétrin provençal : coffre à pieds galbés, façade sculptée, dessus en abattant ; panetière posée dessus."""
    mb = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            tube(mb, "BoisBrut", [(sx * (w / 2 - 0.06), sy * (d / 2 - 0.05), 0), (sx * (w / 2 - 0.03), sy * (d / 2 - 0.03), 0.18),
                                  (sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), 0.35)], 0.035, segs=6)
    box(mb, "BoisBrut", (0, 0, 0.6), (w, d, 0.5))
    box(mb, "BoisBrut", (0, 0, 0.87), (w + 0.05, d + 0.05, 0.04))
    for sx in (-1, 1):
        box(mb, "BoisBrut", (sx * w / 4, -d / 2 - 0.006, 0.6), (w / 2 - 0.12, 0.012, 0.34), col=DARK)
    box(mb, "BoisBrut", (0, 0.05, 1.2), (0.9, 0.35, 0.02))
    for x in (-0.45, 0.45):
        for y in (-0.12, 0.22):
            tube(mb, "BoisBrut", [(x, y, 0.89), (x, y, 1.5)], 0.018, segs=6)
    box(mb, "BoisBrut", (0, 0.05, 1.5), (0.96, 0.4, 0.03))
    for x in (-0.3, 0.0, 0.3):
        tube(mb, "BoisBrut", [(x, -0.12, 0.95), (x, -0.12, 1.45)], 0.01, segs=5)
    return mb


def poele():
    """Poêle à bois en fonte émaillée, tuyau jusqu'au plafond, seau à bois."""
    mb = MB()
    legs(mb, 0.55, 0.45, 0.14, r=0.02, mat="Fer")
    box(mb, "Carrosserie", (0, 0, 0.5), (0.55, 0.45, 0.72), col=(40, 40, 42, 255))
    box(mb, "Fer", (0, -0.23, 0.5), (0.3, 0.02, 0.3), col=(20, 20, 20, 255))
    box(mb, "Fer", (0, 0, 0.87), (0.6, 0.5, 0.03), col=(25, 25, 25, 255))
    tube(mb, "Fer", [(0, 0.05, 0.88), (0, 0.05, 1.8), (0, 0.3, 2.3), (0, 0.3, 2.9)], 0.07, segs=10, col=(30, 30, 30, 255))
    revolve(mb, "Fer", [(0, 0), (0.13, 0), (0.15, 0.3), (0.0, 0.3)], (0.45, -0.05, 0), segs=12, col=(80, 70, 60, 255))
    for k in range(3):
        tube(mb, "EcorceChene", [(0.4 + 0.03 * k, -0.1, 0.25), (0.47 - 0.02 * k, 0.0, 0.42)], 0.03, segs=6)
    return mb


def matelas(w=1.4, L=1.95):
    """Matelas posé au sol avec couverture froissée et oreiller (refuge de survivants)."""
    mb = MB()
    box(mb, "Toile", (0, 0, 0.09), (w, L, 0.18), col=(200, 196, 180, 255))
    box(mb, "TissuProvence", (0.05, -0.2, 0.19), (w - 0.1, L * 0.62, 0.03), uv_scale=0.5, pitch=0.02)
    box(mb, "Toile", (0, L / 2 - 0.25, 0.22), (0.6, 0.35, 0.1), col=(230, 226, 214, 255))
    return mb


def sac_couchage():
    mb = MB()
    box(mb, "Toile", (0, 0, 0.06), (0.75, 1.95, 0.12), col=(60, 80, 110, 255))
    box(mb, "Toile", (0, 0.7, 0.14), (0.72, 0.5, 0.06), col=(170, 60, 50, 255))
    return mb


def jerrican():
    mb = MB()
    box(mb, "Carrosserie", (0, 0, 0.235), (0.34, 0.17, 0.47), col=(60, 90, 50, 255))
    box(mb, "Carrosserie", (0.1, 0, 0.5), (0.04, 0.04, 0.06), col=(60, 90, 50, 255))
    box(mb, "Carrosserie", (-0.05, 0, 0.49), (0.16, 0.03, 0.04), col=(60, 90, 50, 255))
    for x in (-0.08, 0.08):
        box(mb, "Carrosserie", (x, -0.086, 0.24), (0.1, 0.004, 0.36), col=(50, 78, 42, 255))
    return mb


def conserves():
    """Pile de boîtes de conserve et bouteilles d'eau sur un carton."""
    mb = MB()
    box(mb, "Toile", (0, 0, 0.1), (0.5, 0.35, 0.2), col=(170, 130, 85, 255))
    for i in range(3):
        for j in range(2):
            for k in range(2 if i != 1 else 1):
                revolve(mb, "Fer", [(0, 0), (0.042, 0), (0.042, 0.11), (0, 0.11)], (-0.13 + i * 0.13, -0.07 + j * 0.14, 0.2 + k * 0.11), segs=10,
                        col=(190, 190, 195, 255))
                revolve(mb, "Toile", [(0.043, 0.02), (0.043, 0.09)], (-0.13 + i * 0.13, -0.07 + j * 0.14, 0.2 + k * 0.11), segs=10,
                        col=((200, 50, 40), (230, 190, 60), (60, 120, 60))[(i + j + k) % 3] + (255,))
    for k in range(3):
        revolve(mb, "Verre", [(0, 0), (0.045, 0), (0.045, 0.26), (0.02, 0.3), (0, 0.3)], (0.33 + 0.1 * k, 0.05, 0), segs=8)
    return mb


def rechaud():
    """Réchaud de camping sur une caisse, casserole, bouteille de gaz."""
    mb = MB()
    box(mb, "BoisBrut", (0, 0, 0.25), (0.6, 0.4, 0.5))
    box(mb, "Fer", (0, 0, 0.53), (0.4, 0.3, 0.06), col=(50, 50, 55, 255))
    revolve(mb, "Fer", [(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)], (-0.08, 0, 0.56), segs=12, col=(170, 170, 175, 255))
    revolve(mb, "Carrosserie", [(0, 0), (0.12, 0), (0.12, 0.3), (0.05, 0.36), (0, 0.36)], (0.45, 0.05, 0), segs=12, col=(40, 80, 160, 255))
    return mb


def cadre(w=0.6, h=0.45):
    """Tableau accroché au mur (1,5 m) : cadre doré, toile peinte (couleur par instance)."""
    mb = MB()
    z = 1.55
    # paysage provençal naïf : ciel, colline, champ de lavande
    for zc, hh, col in ((z + h * 0.25, h * 0.5, (150, 185, 215)), (z - h * 0.05, h * 0.1, (120, 140, 80)), (z - h * 0.3, h * 0.4, (120, 90, 170))):
        box(mb, "Toile", (0, 0.01, zc), (w, 0.01, hh), col=col + (255,), uv_scale=1.0)
    box(mb, "Toile", (w * 0.25, 0.004, z + h * 0.3), (0.06, 0.004, 0.06), col=(240, 200, 90, 255))
    for sx in (-1, 1):
        box(mb, "Bronze", (sx * (w / 2 + 0.02), 0.012, z), (0.04, 0.03, h + 0.08))
    for sz in (-1, 1):
        box(mb, "Bronze", (0, 0.012, z + sz * (h / 2 + 0.02)), (w + 0.08, 0.03, 0.04))
    return mb


def miroir_mural():
    mb = MB()
    box(mb, "Miroir", (0, 0.005, 1.5), (0.5, 0.01, 0.7))
    box(mb, "BoisPeint", (0, 0.012, 1.5), (0.58, 0.01, 0.78))
    return mb


def plante_pot():
    mb = MB()
    revolve(mb, "TerreCuite", [(0, 0), (0.13, 0), (0.18, 0.32), (0.19, 0.34), (0, 0.34)], (0, 0, 0), segs=14)
    rng = np.random.default_rng(4)
    for k in range(9):
        a = k * 0.7
        tip = (0.25 * math.cos(a), 0.25 * math.sin(a), 0.9 + 0.2 * rng.random())
        tube(mb, "Toile", [(0, 0, 0.32), (tip[0] * 0.5, tip[1] * 0.5, 0.7), tip], [0.03, 0.02, 0.005], segs=4, col=(70, 110, 50, 255))
    return mb


def malle():
    mb = MB()
    box(mb, "BoisBrut", (0, 0, 0.23), (0.9, 0.5, 0.46), col=(140, 100, 70, 255))
    box(mb, "BoisBrut", (0, 0, 0.49), (0.86, 0.46, 0.06), col=(120, 85, 60, 255))
    for x in (-0.3, 0.3):
        box(mb, "Fer", (x, 0, 0.23), (0.04, 0.52, 0.48), col=(50, 45, 40, 255))
    box(mb, "Bronze", (0, -0.26, 0.38), (0.08, 0.02, 0.08))
    return mb


def lampadaire():
    mb = MB()
    revolve(mb, "Bronze", [(0, 0), (0.15, 0), (0.15, 0.02), (0.02, 0.05), (0.015, 1.5), (0, 1.5)], (0, 0, 0), segs=10)
    revolve(mb, "Toile", [(0.22, 0), (0.13, 0.28), (0.0, 0.28)], (0, 0, 1.35), segs=14, col=(230, 200, 150, 255))
    return mb


def lits_enfants():
    """Deux lits simples côte à côte (chambre d'enfants) avec un coffre à jouets."""
    mb = MB()
    for sx in (-1, 1):
        l = lit(0.9, 1.95, False)
        mb.extend(l, offset=(sx * 0.62, 0, 0))
    box(mb, "BoisPeint", (0, 0.6, 0.25), (0.28, 0.4, 0.5), col=(200, 90, 70, 255))
    return mb


FURNITURE = {
    "Int_TableCuisine": table_cuisine,
    "Int_Chaise": chaise_paillee,
    "Int_ChaiseRenversee": chaise_renversee,
    "Int_PlanTravail": plan_travail,
    "Int_Frigo": frigo,
    "Int_Buffet": buffet,
    "Int_Canape": canape,
    "Int_Fauteuil": fauteuil,
    "Int_TableBasse": table_basse,
    "Int_Cheminee": cheminee,
    "Int_Bibliotheque": bibliotheque,
    "Int_Tapis": tapis,
    "Int_LitDouble": lambda: lit(1.6, 2.05, True),
    "Int_LitSimple": lambda: lit(0.95, 2.0, False),
    "Int_Chevet": chevet,
    "Int_Armoire": armoire,
    "Int_Commode": commode,
    "Int_Baignoire": baignoire,
    "Int_WC": wc,
    "Int_Lavabo": lavabo,
    "Int_Suspension": suspension,
    "Int_Carton": carton,
    "Int_TableManger": table_manger,
    "Int_Piano": piano,
    "Int_Horloge": horloge,
    "Int_MachineCoudre": machine_coudre,
    "Int_Bureau": bureau,
    "Int_Etabli": etabli,
    "Int_Tonneau": tonneau,
    "Int_EtagereBocaux": lambda: etagere(fill="bocaux"),
    "Int_EtagereOutils": lambda: etagere(fill="outils"),
    "Int_CasierBouteilles": lambda: etagere(fill="bouteilles"),
    "Int_EvierPierre": evier_pierre,
    "Int_Petrin": petrin,
    "Int_Poele": poele,
    "Int_Matelas": matelas,
    "Int_SacCouchage": sac_couchage,
    "Int_Jerrican": jerrican,
    "Int_Conserves": conserves,
    "Int_Rechaud": rechaud,
    "Int_Cadre": cadre,
    "Int_Miroir": miroir_mural,
    "Int_Plante": plante_pot,
    "Int_Malle": malle,
    "Int_Lampadaire": lampadaire,
    "Int_LitsEnfants": lits_enfants,
}

# encombrement au sol (largeur X, profondeur Y, hauteur) : sert au placement et à la collision (boîte)
SIZE = {
    "Int_TableCuisine": (1.4, 0.8, 0.8), "Int_Chaise": (0.44, 0.44, 0.95), "Int_ChaiseRenversee": (0.44, 0.95, 0.45),
    "Int_PlanTravail": (2.4, 0.62, 0.92), "Int_Frigo": (0.6, 0.62, 1.55), "Int_Buffet": (1.3, 0.5, 2.0),
    "Int_Canape": (2.0, 0.9, 0.85), "Int_Fauteuil": (0.85, 0.85, 0.9), "Int_TableBasse": (1.0, 0.6, 0.45),
    "Int_Cheminee": (1.6, 0.6, 1.4), "Int_Bibliotheque": (1.0, 0.35, 1.9), "Int_Tapis": (2.0, 1.4, 0.0),
    "Int_LitDouble": (1.7, 2.1, 1.05), "Int_LitSimple": (1.05, 2.05, 0.9), "Int_Chevet": (0.45, 0.4, 0.6),
    "Int_Armoire": (1.55, 0.7, 2.25), "Int_Commode": (1.15, 0.53, 0.9), "Int_Baignoire": (1.7, 0.75, 0.6),
    "Int_WC": (0.44, 0.7, 0.85), "Int_Lavabo": (0.62, 0.48, 0.9), "Int_Suspension": (0.45, 0.45, 0.0),
    "Int_Carton": (0.5, 0.4, 0.4),
    "Int_TableManger": (2.0, 0.9, 0.8), "Int_Piano": (1.5, 0.62, 1.3), "Int_Horloge": (0.52, 0.42, 2.3),
    "Int_MachineCoudre": (0.9, 0.48, 1.05), "Int_Bureau": (1.2, 0.6, 0.8), "Int_Etabli": (2.0, 0.88, 0.95),
    "Int_Tonneau": (0.95, 0.7, 0.8), "Int_EtagereBocaux": (1.0, 0.36, 1.8), "Int_EtagereOutils": (1.0, 0.36, 1.8),
    "Int_CasierBouteilles": (1.0, 0.36, 1.8), "Int_EvierPierre": (1.2, 0.62, 0.95), "Int_Petrin": (1.3, 0.6, 1.52),
    "Int_Poele": (0.9, 0.6, 0.95), "Int_Matelas": (1.4, 1.95, 0.25), "Int_SacCouchage": (0.75, 1.95, 0.0),
    "Int_Jerrican": (0.35, 0.18, 0.52), "Int_Conserves": (0.8, 0.36, 0.42), "Int_Rechaud": (0.8, 0.42, 0.62),
    "Int_Cadre": (0.68, 0.06, 0.0), "Int_Miroir": (0.58, 0.04, 0.0), "Int_Plante": (0.5, 0.5, 1.0),
    "Int_Malle": (0.9, 0.52, 0.5), "Int_Lampadaire": (0.44, 0.44, 1.65), "Int_LitsEnfants": (2.3, 2.0, 0.9),
}


# seules les parties peintes et les tissus prennent la teinte de l'instance (alpha de sommet = 0 ailleurs, comme pour les modules)
TINTABLE = ("BoisPeint", "Toile", "TissuProvence", "Carrosserie")


def _untint(fn):
    def build():
        mb = fn()
        for mat, p in mb.parts.items():
            if mat not in TINTABLE:
                p["C"] = [np.concatenate([np.asarray(c)[:, :3], np.zeros((len(c), 1), np.uint8)], 1) for c in p["C"]]
        return mb
    return build


FURNITURE = {k: _untint(v) for k, v in FURNITURE.items()}
