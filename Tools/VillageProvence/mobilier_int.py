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


# ------------------------------------------------------------------ commerces, mairie, église
def _pains(mb, x0, x1, y, z, rng, n=None):
    """Baguettes, boules et pains sur une surface."""
    n = n or int((x1 - x0) / 0.12)
    for k in range(n):
        x = x0 + (k + 0.5) * (x1 - x0) / n
        if rng.random() < 0.6:
            tube(mb, "Toile", [(x, y - 0.25, z + 0.03), (x + 0.02, y + 0.25, z + 0.03)], 0.028, segs=6, col=(196, 140, 70, 255))
        else:
            revolve(mb, "Toile", [(0, 0), (0.07, 0.0), (0.075, 0.03), (0.05, 0.07), (0, 0.08)], (x, y, z), segs=10, col=(180, 120, 60, 255))


def comptoir_vitrine(w=2.2, d=0.7, h=1.0, fill="pain"):
    """Comptoir-vitrine (boulangerie, pâtisserie, boucherie, glacier) : caisson peint, vitre inclinée, marchandises."""
    mb = MB()
    rng = np.random.default_rng(len(fill))
    box(mb, "BoisPeint", (0, 0.05, 0.45), (w, d - 0.1, 0.9))
    box(mb, "Porcelaine", (0, 0.05, 0.91), (w, d - 0.1, 0.02))
    box(mb, "Verre", (0, -d / 2 + 0.12, 1.08), (w - 0.04, 0.01, 0.32), pitch=math.radians(-25))
    box(mb, "Verre", (0, 0.05, h + 0.2), (w - 0.04, d - 0.2, 0.01))
    if fill == "pain":
        _pains(mb, -w / 2 + 0.1, w / 2 - 0.1, 0.05, 0.92, rng)
    elif fill == "viande":
        for k in range(int(w / 0.25)):
            box(mb, "Toile", (-w / 2 + 0.15 + k * 0.25, 0.05, 0.95), (0.2, 0.3, 0.06), col=(150 + 10 * (k % 3), 50, 50, 255))
    else:  # glaces : bacs colorés
        for k in range(int(w / 0.3)):
            box(mb, "Toile", (-w / 2 + 0.18 + k * 0.3, 0.05, 0.95), (0.26, 0.4, 0.07),
                col=((240, 200, 210), (250, 240, 200), (160, 110, 80), (200, 230, 170), (250, 180, 120))[k % 5] + (255,))
    # caisse enregistreuse
    box(mb, "Carrosserie", (w / 2 - 0.25, 0.2, 1.08), (0.35, 0.3, 0.18), col=(40, 40, 42, 255))
    return mb


def etagere_pain(w=1.4, d=0.4, h=1.9):
    """Étagère murale à pains : paniers en osier, baguettes debout."""
    mb = MB()
    rng = np.random.default_rng(9)
    box(mb, "BoisBrut", (0, d / 2 - 0.01, h / 2), (w, 0.02, h))
    for sx in (-1, 1):
        box(mb, "BoisBrut", (sx * (w / 2 - 0.02), 0, h / 2), (0.04, d, h))
    for z in (0.5, 0.95, 1.4):
        box(mb, "BoisBrut", (0, 0, z), (w - 0.04, d, 0.025), pitch=math.radians(-8))
        _pains(mb, -w / 2 + 0.08, w / 2 - 0.08, 0.0, z + 0.02, rng)
    for k in range(8):
        tube(mb, "Toile", [(-w / 2 + 0.15 + k * 0.15, -0.05, 0.05), (-w / 2 + 0.17 + k * 0.15, 0.05, 0.45)], 0.025, segs=6, col=(200, 145, 75, 255))
    return mb


def four_pain():
    """Four à pain en briques et pierre, gueule en arc, pelle en bois."""
    mb = MB()
    box(mb, "PierreTaille", (0, 0.1, 0.45), (1.6, 1.1, 0.9), uv_scale=3.0)
    revolve(mb, "Brique", [(0.75, 0), (0.72, 0.25), (0.6, 0.5), (0.35, 0.7), (0.0, 0.78)], (0, 0.15, 0.9), segs=14)
    box(mb, "Fer", (0, -0.46, 1.12), (0.5, 0.02, 0.32), col=(25, 25, 25, 255))
    box(mb, "Brique", (0, -0.45, 1.33), (0.7, 0.06, 0.12), uv_scale=1.0)
    tube(mb, "BoisBrut", [(0.55, -0.5, 0.02), (0.62, -0.52, 1.7)], 0.02, segs=6)
    box(mb, "BoisBrut", (0.55, -0.5, 0.12), (0.28, 0.02, 0.35))
    return mb


def comptoir_bar(w=2.6, d=0.7, h=1.1):
    """Comptoir de café en zinc : façade en bois, tireuse à bière, percolateur, verres."""
    mb = MB()
    box(mb, "BoisBrut", (0, 0.05, (h - 0.05) / 2), (w, d - 0.1, h - 0.05), col=(130, 90, 60, 255))
    for k in range(int(w / 0.5)):
        box(mb, "BoisBrut", (-w / 2 + 0.25 + k * 0.5, -d / 2 + 0.04, 0.55), (0.42, 0.02, 0.7), col=(110, 75, 50, 255))
    box(mb, "Fer", (0, 0.0, h - 0.02), (w + 0.06, d + 0.06, 0.04), col=(175, 178, 182, 255))
    tube(mb, "Fer", [(-w / 2, -d / 2 - 0.06, 0.2), (w / 2, -d / 2 - 0.06, 0.2)], 0.018, segs=8, col=(200, 170, 90, 255))
    for x in (-0.6, -0.45):
        tube(mb, "Fer", [(x, 0.1, h), (x, 0.1, h + 0.35), (x, 0.0, h + 0.35)], 0.02, segs=6, col=(210, 210, 215, 255))
    box(mb, "Carrosserie", (0.6, 0.12, h + 0.2), (0.6, 0.45, 0.4), col=(150, 30, 28, 255))
    for k in range(6):
        revolve(mb, "Verre", [(0, 0), (0.03, 0), (0.035, 0.12), (0, 0.12)], (-0.1 + k * 0.08, -0.15, h), segs=8)
    return mb


def tabouret():
    mb = MB()
    for a in range(3):
        ang = a * 2 * math.pi / 3
        tube(mb, "Fer", [(0.15 * math.cos(ang), 0.15 * math.sin(ang), 0), (0.05 * math.cos(ang), 0.05 * math.sin(ang), 0.72)], 0.012, segs=5,
             col=(40, 40, 40, 255))
    revolve(mb, "Toile", [(0, 0), (0.18, 0), (0.18, 0.05), (0, 0.06)], (0, 0, 0.72), segs=14, col=(140, 40, 35, 255))
    return mb


def gondole(w=1.8, d=0.8, h=1.6):
    """Rayonnage d'épicerie à double face : conserves, paquets, bouteilles."""
    mb = MB()
    rng = np.random.default_rng(21)
    box(mb, "BoisPeint", (0, 0, h / 2), (w, 0.06, h), col=(210, 210, 205, 255))
    for sy in (-1, 1):
        for z in (0.12, 0.5, 0.88, 1.26):
            box(mb, "BoisPeint", (0, sy * d / 4, z), (w, d / 2 - 0.04, 0.02), col=(200, 200, 195, 255))
            x = -w / 2 + 0.08
            while x < w / 2 - 0.1:
                kind = rng.integers(3)
                if kind == 0:
                    revolve(mb, "Fer", [(0, 0), (0.04, 0), (0.04, 0.11), (0, 0.11)], (x, sy * d / 4, z + 0.01), segs=8, col=(190, 190, 195, 255))
                    revolve(mb, "Toile", [(0.041, 0.02), (0.041, 0.09)], (x, sy * d / 4, z + 0.01), segs=8,
                            col=((200, 50, 40), (230, 190, 60), (60, 120, 60), (60, 90, 160))[int(rng.integers(4))] + (255,))
                    x += 0.09
                elif kind == 1:
                    hh = rng.uniform(0.18, 0.3)
                    box(mb, "Toile", (x + 0.05, sy * d / 4, z + 0.01 + hh / 2), (0.1, 0.22, hh),
                        col=((220, 190, 60), (200, 70, 50), (240, 240, 230), (90, 140, 200))[int(rng.integers(4))] + (255,))
                    x += 0.12
                else:
                    revolve(mb, "Verre", [(0, 0), (0.035, 0), (0.035, 0.2), (0.012, 0.28), (0, 0.28)], (x, sy * d / 4, z + 0.01), segs=8)
                    x += 0.08
    return mb


def cagettes():
    """Étal de fruits et légumes : cagettes inclinées sur tréteaux."""
    mb = MB()
    rng = np.random.default_rng(5)
    legs(mb, 1.2, 0.6, 0.6, r=0.02)
    for k in range(3):
        x = -0.4 + k * 0.4
        box(mb, "BoisBrut", (x, 0, 0.7), (0.38, 0.55, 0.14), pitch=math.radians(-15), col=(200, 170, 120, 255))
        col = ((220, 60, 40), (240, 170, 40), (120, 170, 60))[k]
        for j in range(12):
            revolve(mb, "Toile", [(0, 0), (0.04, 0.0), (0.045, 0.04), (0, 0.08)],
                    (x + rng.uniform(-0.14, 0.14), rng.uniform(-0.2, 0.2), 0.76 - 0.0), segs=8, col=col + (255,))
    return mb


def caisse_comptoir(w=1.4, d=0.6, h=1.0):
    mb = MB()
    box(mb, "BoisPeint", (0, 0.03, h / 2), (w, d - 0.06, h))
    box(mb, "BoisBrut", (0, 0, h + 0.02), (w + 0.04, d, 0.04))
    box(mb, "BoisPeint", (0.35, 0.1, h + 0.13), (0.35, 0.3, 0.18), col=(40, 40, 42, 255))
    box(mb, "Toile", (-0.3, 0.0, h + 0.1), (0.3, 0.2, 0.14), col=(230, 220, 190, 255))
    return mb


def rayon_pharmacie(w=1.6, d=0.4, h=2.1):
    """Rayonnage mural blanc à tiroirs et boîtes de médicaments."""
    mb = MB()
    rng = np.random.default_rng(33)
    box(mb, "BoisPeint", (0, 0.02, h / 2), (w, d - 0.04, h), col=(238, 238, 234, 255), faces=("+y", "-x", "+x", "+z"))
    box(mb, "BoisPeint", (0, -d / 2 + 0.2, 0.4), (w, 0.4, 0.8), col=(236, 236, 232, 255))
    for k in range(int(w / 0.2)):
        for z in (0.2, 0.45, 0.7):
            box(mb, "BoisPeint", (-w / 2 + 0.1 + k * 0.2, -d / 2 - 0.005, z), (0.17, 0.01, 0.2), col=(225, 228, 225, 255))
    for z in (1.0, 1.35, 1.7):
        box(mb, "BoisPeint", (0, 0, z), (w - 0.02, d - 0.04, 0.02), col=(245, 245, 242, 255))
        x = -w / 2 + 0.07
        while x < w / 2 - 0.07:
            ww = rng.uniform(0.05, 0.1)
            box(mb, "Toile", (x + ww / 2, -0.02, z + 0.08), (ww, 0.14, 0.15),
                col=((250, 250, 250), (90, 160, 90), (70, 120, 190), (230, 90, 70), (240, 200, 80))[int(rng.integers(5))] + (255,))
            x += ww + 0.01
    return mb


def comptoir_pharmacie(w=2.0, d=0.6, h=1.0):
    mb = MB()
    box(mb, "BoisPeint", (0, 0.03, h / 2), (w, d - 0.06, h), col=(240, 240, 236, 255))
    box(mb, "Porcelaine", (0, 0, h + 0.015), (w + 0.04, d, 0.03))
    box(mb, "BoisPeint", (0, -d / 2 + 0.01, 0.55), (w - 0.3, 0.01, 0.12), col=(40, 150, 80, 255))
    box(mb, "BoisPeint", (0.5, 0.1, h + 0.2), (0.4, 0.05, 0.3), col=(30, 30, 32, 255), pitch=math.radians(-10))
    return mb


def fauteuil_coiffeur():
    mb = MB()
    revolve(mb, "Fer", [(0, 0), (0.28, 0), (0.28, 0.03), (0.05, 0.08), (0.05, 0.4), (0, 0.4)], (0, 0, 0), segs=14, col=(190, 190, 195, 255))
    box(mb, "Toile", (0, 0, 0.47), (0.55, 0.55, 0.14), col=(40, 30, 30, 255))
    box(mb, "Toile", (0, 0.24, 0.85), (0.55, 0.1, 0.7), col=(40, 30, 30, 255), pitch=math.radians(-8))
    for sx in (-1, 1):
        box(mb, "Toile", (sx * 0.3, 0.02, 0.66), (0.08, 0.5, 0.08), col=(40, 30, 30, 255))
    return mb


def presentoir(fill="santons"):
    """Table de présentation : santons, poteries, savons ou livres."""
    mb = MB()
    rng = np.random.default_rng(len(fill) * 7)
    legs(mb, 1.4, 0.8, 0.78, r=0.025)
    box(mb, "BoisBrut", (0, 0, 0.8), (1.4, 0.8, 0.04))
    box(mb, "TissuProvence", (0, 0, 0.823), (1.3, 0.7, 0.006), uv_scale=0.5)
    for k in range(18):
        x, y = rng.uniform(-0.6, 0.6), rng.uniform(-0.3, 0.3)
        if fill == "santons":
            revolve(mb, "Toile", [(0, 0), (0.035, 0), (0.03, 0.08), (0.02, 0.1), (0.025, 0.13), (0, 0.14)], (x, y, 0.826), segs=8,
                    col=((180, 60, 50), (60, 90, 150), (220, 190, 120), (90, 120, 70))[k % 4] + (255,))
        elif fill == "poterie":
            revolve(mb, "TerreCuite", [(0, 0), (0.06, 0), (0.09, 0.08), (0.05, 0.16), (0.06, 0.2), (0, 0.2)], (x, y, 0.826), segs=10)
        elif fill == "savons":
            box(mb, "Toile", (x, y, 0.85), (0.09, 0.06, 0.05), col=((150, 110, 190), (240, 220, 160), (200, 230, 170), (240, 190, 170))[k % 4] + (255,))
        else:
            box(mb, "Toile", (x, y, 0.84), (0.16, 0.22, 0.03), col=((150, 40, 40), (40, 60, 110), (170, 140, 60))[k % 3] + (255,))
    return mb


def banc_attente(w=1.6):
    mb = MB()
    legs(mb, w, 0.42, 0.44, r=0.025, mat="Fer")
    box(mb, "BoisBrut", (0, 0, 0.46), (w, 0.42, 0.04))
    box(mb, "BoisBrut", (0, 0.2, 0.75), (w, 0.03, 0.35))
    return mb


def drapeaux():
    """Drapeaux français et européen sur hampes (salle de la mairie)."""
    mb = MB()
    for x, cols in ((-0.2, ((0, 35, 149), (255, 255, 255), (237, 41, 57))), (0.2, ((0, 51, 153), (0, 51, 153), (0, 51, 153)))):
        tube(mb, "Bronze", [(x, 0, 0), (x, 0, 2.2)], 0.015, segs=6)
        revolve(mb, "Bronze", [(0, 0), (0.15, 0), (0.15, 0.04), (0, 0.04)], (x, 0, 0), segs=10)
        for k, c in enumerate(cols):
            box(mb, "Toile", (x + 0.06, 0.02 + 0.03 * k, 1.6 - 0.28 * k), (0.04, 0.03, 0.28), col=c + (255,))
    return mb


def armoire_archives():
    mb = MB()
    box(mb, "BoisPeint", (0, 0, 1.0), (1.0, 0.5, 2.0), col=(120, 128, 120, 255))
    for z in (0.35, 0.8, 1.25, 1.7):
        box(mb, "BoisPeint", (0, -0.255, z), (0.9, 0.01, 0.38), col=(110, 118, 110, 255))
        box(mb, "Fer", (0, -0.27, z + 0.1), (0.12, 0.02, 0.03), col=(200, 200, 200, 255))
    return mb


def banc_eglise(w=3.0):
    """Banc d'église en chêne : assise, dossier, agenouilloir, joues sculptées."""
    mb = MB()
    for sx in (-1, 1):
        box(mb, "BoisVernis", (sx * (w / 2 - 0.03), 0.0, 0.5), (0.06, 0.6, 1.0))
    box(mb, "BoisVernis", (0, -0.05, 0.45), (w - 0.06, 0.4, 0.04))
    box(mb, "BoisVernis", (0, 0.2, 0.75), (w - 0.06, 0.04, 0.5), pitch=math.radians(-8))
    box(mb, "BoisVernis", (0, 0.36, 0.85), (w - 0.06, 0.18, 0.03))                 # tablette du banc suivant
    box(mb, "BoisVernis", (0, 0.4, 0.12), (w - 0.06, 0.16, 0.05))                  # agenouilloir
    return mb


def autel():
    """Autel en pierre sur deux marches, nappe, croix, chandeliers, retable peint."""
    mb = MB()
    box(mb, "PierreTaille", (0, 0.2, 0.08), (3.4, 2.2, 0.16), uv_scale=3.0)
    box(mb, "PierreTaille", (0, 0.4, 0.24), (3.0, 1.8, 0.16), uv_scale=3.0)
    box(mb, "PierreTaille", (0, 0.5, 0.8), (2.0, 0.9, 0.96), uv_scale=3.0)
    box(mb, "Toile", (0, 0.5, 1.29), (2.1, 0.95, 0.02), col=(245, 242, 234, 255))
    box(mb, "Toile", (0, 0.03, 1.1), (2.1, 0.01, 0.4), col=(245, 242, 234, 255))
    box(mb, "Bronze", (0, 0.75, 1.75), (0.05, 0.05, 0.9))
    box(mb, "Bronze", (0, 0.75, 1.95), (0.45, 0.05, 0.05))
    for x in (-0.7, -0.4, 0.4, 0.7):
        revolve(mb, "Bronze", [(0, 0), (0.07, 0), (0.02, 0.05), (0.015, 0.35), (0.04, 0.37), (0, 0.37)], (x, 0.7, 1.3), segs=8)
        revolve(mb, "Porcelaine", [(0, 0), (0.018, 0), (0.018, 0.2), (0, 0.2)], (x, 0.7, 1.67), segs=6)
    # retable : panneaux dorés et toile peinte
    box(mb, "Bronze", (0, 1.05, 2.4), (2.4, 0.08, 2.4))
    for zc, hh, col in ((2.9, 0.9, (90, 120, 180)), (2.3, 0.4, (200, 160, 110)), (1.95, 0.35, (140, 50, 45))):
        box(mb, "Toile", (0, 1.0, zc), (1.4, 0.01, hh), col=col + (255,))
    return mb


def chandelier_sol():
    mb = MB()
    revolve(mb, "Bronze", [(0, 0), (0.16, 0), (0.04, 0.1), (0.03, 1.2), (0.09, 1.25), (0.02, 1.28), (0, 1.28)], (0, 0, 0), segs=10)
    revolve(mb, "Porcelaine", [(0, 0), (0.025, 0), (0.025, 0.3), (0, 0.3)], (0, 0, 1.28), segs=8)
    return mb


def benitier():
    mb = MB()
    revolve(mb, "PierreTaille", [(0, 0), (0.18, 0), (0.12, 0.1), (0.08, 0.75), (0.28, 0.85), (0.3, 0.98), (0.0, 0.93)], (0, 0, 0), segs=16,
            u_tile=3, v_tile=3)
    return mb


def pupitre():
    mb = MB()
    revolve(mb, "BoisVernis", [(0, 0), (0.22, 0), (0.05, 0.08), (0.05, 1.05), (0, 1.05)], (0, 0, 0), segs=10)
    box(mb, "BoisVernis", (0, 0, 1.12), (0.55, 0.4, 0.03), pitch=math.radians(-25))
    box(mb, "Toile", (0, -0.02, 1.15), (0.4, 0.3, 0.03), col=(120, 30, 30, 255), pitch=math.radians(-25))
    return mb


def statue():
    """Statue de saint sur piédestal (plâtre peint)."""
    mb = MB()
    box(mb, "PierreTaille", (0, 0, 0.5), (0.55, 0.55, 1.0), uv_scale=3.0)
    revolve(mb, "Toile", [(0, 0), (0.2, 0), (0.18, 0.5), (0.14, 0.9), (0.1, 1.0), (0.0, 1.02)], (0, 0, 1.0), segs=12, col=(90, 120, 190, 255))
    revolve(mb, "Toile", [(0, 0), (0.08, 0.02), (0.09, 0.1), (0.07, 0.18), (0, 0.2)], (0, 0, 2.0), segs=10, col=(230, 200, 170, 255))
    tube(mb, "Bronze", [(0, 0, 2.28), (0.0, 0.0, 2.3)], 0.12, segs=14)
    return mb


def confessionnal():
    mb = MB()
    box(mb, "BoisVernis", (0, 0.05, 1.2), (1.8, 0.8, 2.4), faces=("+y", "-x", "+x", "+z"))
    box(mb, "BoisVernis", (0, -0.35, 2.3), (1.8, 0.1, 0.2))
    for x in (-0.6, 0.0, 0.6):
        box(mb, "BoisVernis", (x, -0.33, 1.15), (0.08, 0.14, 2.3))
    for x in (-0.3, 0.3):
        box(mb, "TissuProvence", (x, -0.3, 1.2), (0.5, 0.02, 1.9), col=(120, 30, 40, 255), uv_scale=0.5)
    return mb


# ------------------------------------------------------------------ intérieurs modernes
GRIS = (70, 72, 76, 255)
ANTHRACITE = (48, 50, 54, 255)


def _centre(mb):
    """Recentre un meuble sur son emprise au sol (placement et boîte de collision centrés)."""
    arr = mb.arrays()
    P = np.concatenate([a["P"] for a in arr.values()])
    off = -(P.min(0) + P.max(0)) / 2
    out = MB()
    for mat, a in arr.items():
        out.add(mat, a["P"] + np.array([off[0], off[1], 0.0], np.float32), a["N"], a["UV"], a["C"], a["I"])
    return out


def cuisine_moderne(w=3.0, d=0.65, h=0.9):
    """Cuisine contemporaine : façades laquées sans poignées, plan en béton ciré, plaque à induction, four encastré, hotte,
    évier inox, meubles hauts ; la couleur des façades se règle par instance."""
    mb = MB()
    box(mb, "Laque", (0, 0.02, 0.05), (w - 0.04, d - 0.1, 0.1), col=ANTHRACITE)
    box(mb, "Laque", (0, 0.0, (h - 0.04) / 2 + 0.05), (w, d - 0.04, h - 0.14))
    nd = int(w / 0.6)
    for k in range(nd):
        x = -w / 2 + (k + 0.5) * w / nd
        box(mb, "Laque", (x, -d / 2 + 0.01, 0.47), (w / nd - 0.006, 0.02, 0.72))
        box(mb, "MetalBrosse", (x, -d / 2 - 0.003, h - 0.12), (w / nd - 0.2, 0.008, 0.012))
    box(mb, "BetonCire", (0, 0, h - 0.02), (w + 0.02, d, 0.04), uv_scale=2.0, col=(200, 196, 190, 255))
    # four encastré, plaque à induction, évier et mitigeur
    box(mb, "Verre", (-w / 2 + 0.9, -d / 2 - 0.004, 0.5), (0.56, 0.01, 0.5))
    box(mb, "MetalBrosse", (-w / 2 + 0.9, -d / 2 - 0.006, 0.78), (0.56, 0.012, 0.06))
    box(mb, "Verre", (-w / 2 + 0.9, -0.02, h + 0.003), (0.6, 0.52, 0.006))
    box(mb, "MetalBrosse", (w / 2 - 0.8, -0.02, h + 0.002), (0.55, 0.42, 0.006))
    box(mb, "Fer", (w / 2 - 0.8, -0.02, h + 0.004), (0.45, 0.34, 0.004), col=(35, 35, 38, 255))
    tube(mb, "MetalBrosse", [(w / 2 - 0.8, 0.22, h), (w / 2 - 0.8, 0.22, h + 0.38), (w / 2 - 0.8, 0.05, h + 0.4)], 0.014, segs=8)
    # crédence et meubles hauts, hotte inox
    box(mb, "Laque", (0, d / 2 - 0.005, h + 0.3), (w, 0.01, 0.6), col=(210, 210, 208, 255), faces=("-y",))
    for k in range(nd):
        x = -w / 2 + (k + 0.5) * w / nd
        if abs(x - (-w / 2 + 0.9)) < 0.35:
            continue
        box(mb, "Laque", (x, d / 2 - 0.18, 1.85), (w / nd - 0.006, 0.34, 0.7))
    box(mb, "MetalBrosse", (-w / 2 + 0.9, d / 2 - 0.25, 1.55), (0.6, 0.5, 0.08))
    box(mb, "MetalBrosse", (-w / 2 + 0.9, d / 2 - 0.12, 1.95), (0.3, 0.24, 0.8))
    return mb


def ilot(w=1.8, d=0.9, h=0.92):
    """Îlot central : caisson laqué, plan en béton ciré qui déborde, trois tabourets hauts."""
    mb = MB()
    box(mb, "Laque", (0, -0.1, (h - 0.04) / 2), (w - 0.1, d - 0.3, h - 0.04))
    box(mb, "BetonCire", (0, 0, h - 0.02), (w, d, 0.04), uv_scale=2.0, col=(200, 196, 190, 255))
    for k in (-1, 0, 1):
        x = k * 0.55
        tube(mb, "MetalBrosse", [(x, 0.55, 0), (x, 0.55, 0.62)], 0.02, segs=8)
        revolve(mb, "MetalBrosse", [(0, 0), (0.18, 0), (0.18, 0.01), (0, 0.01)], (x, 0.55, 0), segs=12)
        revolve(mb, "Toile", [(0, 0), (0.19, 0), (0.19, 0.06), (0, 0.07)], (x, 0.55, 0.62), segs=14, col=(60, 62, 66, 255))
    return mb


def table_moderne(w=1.8, d=0.9, h=0.75):
    """Table à manger moderne (plateau blanc, piètement en métal noir) et six chaises coques."""
    mb = MB()
    box(mb, "Laque", (0, 0, h - 0.015), (w, d, 0.03))
    for sx in (-1, 1):
        box(mb, "Fer", (sx * (w / 2 - 0.12), 0, (h - 0.03) / 2), (0.05, d - 0.1, 0.03), col=(25, 25, 25, 255))
        box(mb, "Fer", (sx * (w / 2 - 0.12), 0, 0.015), (0.05, d - 0.1, 0.03), col=(25, 25, 25, 255))
        for sy in (-1, 1):
            box(mb, "Fer", (sx * (w / 2 - 0.12), sy * (d / 2 - 0.08), (h - 0.03) / 2), (0.04, 0.04, h - 0.03), col=(25, 25, 25, 255))
    for k in range(3):
        for sy in (-1, 1):
            x, y = -w / 2 + 0.3 + k * (w - 0.6) / 2, sy * (d / 2 + 0.25)
            for lx in (-0.18, 0.18):
                for ly in (-0.18, 0.18):
                    tube(mb, "BoisBrut", [(x + lx, y + ly, 0), (x + lx * 0.8, y + ly * 0.8, 0.44)], 0.014, segs=6)
            revolve(mb, "Laque", [(0, 0), (0.22, 0.0), (0.24, 0.06), (0, 0.05)], (x, y, 0.44), segs=16)
            box(mb, "Laque", (x, y + sy * 0.2, 0.68), (0.42, 0.04, 0.34), pitch=math.radians(-sy * 10))
    revolve(mb, "Verre", [(0, 0), (0.08, 0), (0.1, 0.25), (0.06, 0.3), (0, 0.3)], (0, 0, h), segs=12)
    return mb


def canape_angle():
    """Canapé d'angle bas en tissu gris, coussins, plaid."""
    mb = MB()
    col = (120, 122, 126, 255)
    box(mb, "Toile", (0, 0.05, 0.2), (2.8, 0.95, 0.32), col=col)
    box(mb, "Toile", (-1.05, -0.55, 0.2), (0.7, 1.2, 0.32), col=col)
    box(mb, "Toile", (0, 0.44, 0.52), (2.8, 0.2, 0.46), col=col)
    box(mb, "Toile", (1.3, 0.05, 0.42), (0.2, 0.95, 0.26), col=col)
    for k in range(4):
        box(mb, "Toile", (-0.95 + k * 0.62, 0.05, 0.42), (0.58, 0.72, 0.12), col=(130, 132, 136, 255))
    box(mb, "Toile", (-1.05, -0.65, 0.42), (0.62, 1.0, 0.12), col=(130, 132, 136, 255))
    for x, c in ((-0.9, (230, 200, 90)), (0.6, (80, 120, 150)), (0.95, (235, 232, 225))):
        box(mb, "Toile", (x, 0.3, 0.6), (0.42, 0.14, 0.4), col=c + (255,), pitch=math.radians(-12))
    box(mb, "TissuProvence", (-1.05, -0.8, 0.49), (0.6, 0.5, 0.02), col=(90, 90, 110, 255), uv_scale=0.5)
    for x in (-1.3, 1.3):
        box(mb, "Fer", (x, 0.4, 0.02), (0.05, 0.05, 0.05), col=(25, 25, 25, 255))
    return mb


def table_basse_moderne():
    mb = MB()
    box(mb, "BoisVernis", (0, 0, 0.36), (1.1, 0.6, 0.05))
    box(mb, "BoisVernis", (0, 0, 0.12), (1.0, 0.5, 0.03))
    for sx in (-1, 1):
        box(mb, "Fer", (sx * 0.5, 0, 0.18), (0.03, 0.56, 0.36), col=(25, 25, 25, 255))
    for k in range(3):
        box(mb, "Toile", (-0.25 + k * 0.02, 0.05, 0.4 + k * 0.025), (0.3, 0.22, 0.025), col=((200, 60, 50), (240, 240, 235), (40, 60, 110))[k] + (255,))
    return mb


def meuble_tv():
    """Meuble TV bas suspendu et téléviseur à écran plat, enceinte, console de jeu."""
    mb = MB()
    box(mb, "Laque", (0, 0.05, 0.35), (1.9, 0.4, 0.4))
    box(mb, "BoisVernis", (0, 0.05, 0.56), (1.9, 0.4, 0.03))
    box(mb, "Fer", (0, 0.15, 1.2), (1.45, 0.05, 0.84), col=(15, 15, 16, 255))
    box(mb, "Verre", (0, 0.12, 1.2), (1.4, 0.01, 0.79))
    box(mb, "Fer", (-0.6, 0.05, 0.62), (0.2, 0.2, 0.08), col=(20, 20, 20, 255))
    box(mb, "Laque", (0.55, 0.05, 0.61), (0.3, 0.22, 0.06), col=(235, 235, 235, 255))
    return mb


def lampe_arc():
    mb = MB()
    box(mb, "PierreTaille", (0, 0.1, 0.05), (0.35, 0.25, 0.1), col=(240, 240, 238, 255), uv_scale=3.0)
    pts = [(0, 0.1, 0.1)] + [(0.0, 0.1 - 1.3 * math.sin(t), 0.1 + 1.9 * math.sin(t * 1.2 + 0.2) / math.sin(1.4)) for t in np.linspace(0.05, 1.2, 12)]
    tube(mb, "MetalBrosse", pts, 0.015, segs=6)
    end = pts[-1]
    revolve(mb, "MetalBrosse", [(0.0, 0.0), (0.2, -0.18), (0.21, -0.2), (0.0, -0.02)], end, segs=16)
    return mb


def etagere_cubes():
    """Étagère à cases (4 x 4), livres, boîtes, plantes."""
    mb = MB()
    rng = np.random.default_rng(71)
    w, h, d, n = 1.5, 1.5, 0.39, 4
    for k in range(n + 1):
        box(mb, "Laque", (-w / 2 + k * w / n, 0, h / 2), (0.03, d, h))
        box(mb, "Laque", (0, 0, k * h / n), (w, d, 0.03))
    for i in range(n):
        for j in range(n):
            x, z = -w / 2 + (i + 0.5) * w / n, j * h / n + 0.02
            r = rng.random()
            if r < 0.4:
                for b in range(rng.integers(3, 7)):
                    box(mb, "Toile", (x - 0.13 + b * 0.045, -0.02, z + 0.13), (0.035, 0.25, 0.24 + 0.05 * rng.random()),
                        col=((200, 60, 50), (40, 60, 110), (230, 200, 90), (60, 110, 80), (240, 240, 235))[int(rng.integers(5))] + (255,))
            elif r < 0.65:
                box(mb, "Toile", (x, -0.01, z + 0.15), (0.32, 0.33, 0.3), col=((210, 205, 195), (90, 90, 95), (180, 150, 110))[int(rng.integers(3))] + (255,))
            elif r < 0.8:
                revolve(mb, "Laque", [(0, 0), (0.07, 0), (0.08, 0.14), (0, 0.14)], (x, 0, z), segs=10)
                tube(mb, "Toile", [(x, 0, z + 0.14), (x + 0.05, 0.03, z + 0.3)], 0.03, segs=5, col=(70, 120, 60, 255))
    return mb


def lit_moderne():
    """Lit plateforme bas, tête de lit capitonnée grise, linge blanc, plaid."""
    mb = MB()
    box(mb, "BoisVernis", (0, 0, 0.12), (1.7, 2.05, 0.24))
    box(mb, "Toile", (0, -0.05, 0.36), (1.6, 1.95, 0.24), col=(240, 240, 236, 255))
    box(mb, "Toile", (0, 1.02, 0.6), (1.8, 0.1, 1.0), col=(110, 112, 118, 255))
    for x in (-0.4, 0.4):
        box(mb, "Toile", (x, 0.75, 0.55), (0.6, 0.35, 0.14), col=(245, 245, 242, 255), pitch=math.radians(-15))
    box(mb, "Toile", (0, -0.55, 0.49), (1.62, 0.6, 0.03), col=(70, 90, 110, 255))
    return mb


def dressing():
    """Dressing à portes coulissantes (laque et miroir)."""
    mb = MB()
    box(mb, "Laque", (0, 0, 1.15), (2.0, 0.62, 2.3))
    box(mb, "Miroir", (-0.5, -0.315, 1.15), (0.96, 0.01, 2.2))
    box(mb, "Laque", (0.5, -0.33, 1.15), (0.96, 0.02, 2.2))
    return mb


def bureau_info():
    """Bureau moderne : plateau blanc, écran, ordinateur portable, lampe, chaise de bureau à roulettes."""
    mb = MB()
    box(mb, "Laque", (0, 0, 0.74), (1.4, 0.7, 0.03))
    for sx in (-1, 1):
        box(mb, "Fer", (sx * 0.66, 0, 0.36), (0.04, 0.64, 0.72), col=(25, 25, 25, 255))
    box(mb, "Fer", (0.0, 0.18, 1.02), (0.62, 0.03, 0.38), col=(15, 15, 16, 255))
    box(mb, "Verre", (0.0, 0.165, 1.03), (0.58, 0.004, 0.33))
    box(mb, "Fer", (0.0, 0.22, 0.8), (0.08, 0.06, 0.12), col=(25, 25, 25, 255))
    box(mb, "MetalBrosse", (-0.4, -0.08, 0.765), (0.34, 0.24, 0.015))
    box(mb, "MetalBrosse", (-0.4, 0.04, 0.88), (0.34, 0.01, 0.23), pitch=math.radians(-15))
    box(mb, "Fer", (0.1, -0.12, 0.76), (0.44, 0.14, 0.015), col=(30, 30, 30, 255))
    # chaise de bureau
    cy = -0.65
    for k in range(5):
        a = k * 2 * math.pi / 5
        tube(mb, "Fer", [(0, cy, 0.06), (0.3 * math.cos(a), cy + 0.3 * math.sin(a), 0.04)], 0.015, segs=5, col=(25, 25, 25, 255))
    tube(mb, "MetalBrosse", [(0, cy, 0.06), (0, cy, 0.46)], 0.025, segs=8)
    box(mb, "Toile", (0, cy, 0.5), (0.5, 0.48, 0.08), col=(40, 40, 44, 255))
    box(mb, "Toile", (0, cy - 0.24, 0.85), (0.46, 0.06, 0.6), col=(40, 40, 44, 255), pitch=math.radians(8))
    return mb


def douche():
    """Douche à l'italienne : receveur extra-plat, paroi vitrée, colonne de douche, faïence grand format."""
    mb = MB()
    box(mb, "Porcelaine", (0, 0, 0.02), (1.2, 0.9, 0.04))
    box(mb, "Verre", (0.6, -0.1, 1.0), (0.012, 0.7, 2.0))
    box(mb, "MetalBrosse", (0.6, -0.1, 2.0), (0.02, 0.72, 0.02))
    tube(mb, "MetalBrosse", [(-0.3, 0.43, 0.9), (-0.3, 0.43, 2.05), (-0.3, 0.2, 2.1)], 0.015, segs=8)
    revolve(mb, "MetalBrosse", [(0, 0), (0.12, 0), (0.12, 0.01), (0, 0.015)], (-0.3, 0.2, 2.08), segs=16)
    box(mb, "Laque", (0, 0.44, 1.1), (1.2, 0.01, 2.2), col=(90, 92, 96, 255), faces=("-y",))
    return mb


def vasque_moderne():
    """Meuble-vasque suspendu, vasque à poser, mitigeur, miroir rétroéclairé."""
    mb = MB()
    box(mb, "BoisVernis", (0, 0.02, 0.62), (0.9, 0.46, 0.36))
    box(mb, "Porcelaine", (0, 0.0, 0.83), (0.9, 0.48, 0.03))
    revolve(mb, "Porcelaine", [(0, 0), (0.2, 0.0), (0.22, 0.13), (0.2, 0.14), (0, 0.02)], (0, -0.02, 0.845), segs=18)
    tube(mb, "MetalBrosse", [(0, 0.18, 0.845), (0, 0.18, 1.1), (0, 0.06, 1.1)], 0.012, segs=8)
    box(mb, "Miroir", (0, 0.23, 1.55), (0.8, 0.01, 0.7))
    return mb


def plante_moderne():
    mb = MB()
    revolve(mb, "Laque", [(0, 0), (0.18, 0), (0.2, 0.45), (0, 0.45)], (0, 0, 0), segs=16)
    rng = np.random.default_rng(12)
    for k in range(9):
        a = k * 0.7
        h = 0.9 + 0.5 * rng.random()
        tube(mb, "Toile", [(0, 0, 0.45), (0.12 * math.cos(a), 0.12 * math.sin(a), 0.45 + h * 0.6), (0.3 * math.cos(a), 0.3 * math.sin(a), 0.45 + h)],
             [0.05, 0.035, 0.005], segs=4, col=(60, 100, 50, 255))
    return mb


def cadre_moderne():
    """Grande toile abstraite (1,2 x 0,8 m) accrochée au mur."""
    mb = MB()
    z = 1.5
    box(mb, "Laque", (0, 0.015, z), (1.2, 0.03, 0.8), col=(245, 245, 243, 255))
    for (x, zz, w, hh, c) in ((-0.3, 0.1, 0.5, 0.45, (220, 90, 60)), (0.25, -0.12, 0.45, 0.35, (40, 70, 120)), (0.15, 0.2, 0.2, 0.2, (240, 200, 70)),
                              (-0.35, -0.25, 0.3, 0.15, (30, 30, 32))):
        box(mb, "Toile", (x, -0.002, z + zz), (w, 0.004, hh), col=c + (255,))
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
    "Int_ComptoirPain": lambda: comptoir_vitrine(fill="pain"),
    "Int_ComptoirViande": lambda: comptoir_vitrine(fill="viande"),
    "Int_ComptoirGlaces": lambda: comptoir_vitrine(fill="glaces"),
    "Int_EtagerePain": etagere_pain,
    "Int_FourPain": four_pain,
    "Int_ComptoirBar": comptoir_bar,
    "Int_Tabouret": tabouret,
    "Int_Gondole": gondole,
    "Int_Cagettes": cagettes,
    "Int_Caisse": caisse_comptoir,
    "Int_RayonPharmacie": rayon_pharmacie,
    "Int_ComptoirPharmacie": comptoir_pharmacie,
    "Int_FauteuilCoiffeur": fauteuil_coiffeur,
    "Int_PresentoirSantons": lambda: presentoir("santons"),
    "Int_PresentoirPoterie": lambda: presentoir("poterie"),
    "Int_PresentoirSavons": lambda: presentoir("savons"),
    "Int_PresentoirLivres": lambda: presentoir("livres"),
    "Int_BancAttente": banc_attente,
    "Int_Drapeaux": drapeaux,
    "Int_ArmoireArchives": armoire_archives,
    "Int_BancEglise": banc_eglise,
    "Int_Autel": autel,
    "Int_Chandelier": chandelier_sol,
    "Int_Benitier": benitier,
    "Int_Pupitre": pupitre,
    "Int_Statue": statue,
    "Int_Confessionnal": confessionnal,
    "Int_CuisineModerne": cuisine_moderne,
    "Int_Ilot": lambda: _centre(ilot()),
    "Int_TableModerne": table_moderne,
    "Int_CanapeAngle": lambda: _centre(canape_angle()),
    "Int_TableBasseModerne": table_basse_moderne,
    "Int_MeubleTV": meuble_tv,
    "Int_LampeArc": lambda: _centre(lampe_arc()),
    "Int_EtagereCubes": etagere_cubes,
    "Int_LitModerne": lit_moderne,
    "Int_Dressing": dressing,
    "Int_BureauInfo": lambda: _centre(bureau_info()),
    "Int_Douche": douche,
    "Int_VasqueModerne": vasque_moderne,
    "Int_PlanteModerne": plante_moderne,
    "Int_CadreModerne": cadre_moderne,
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
    "Int_ComptoirPain": (2.2, 0.72, 1.2), "Int_ComptoirViande": (2.2, 0.72, 1.2), "Int_ComptoirGlaces": (2.2, 0.72, 1.2),
    "Int_EtagerePain": (1.4, 0.5, 1.9), "Int_FourPain": (1.6, 1.46, 1.7), "Int_ComptoirBar": (2.7, 0.8, 1.15),
    "Int_Tabouret": (0.4, 0.4, 0.78), "Int_Gondole": (1.8, 0.82, 1.6), "Int_Cagettes": (1.25, 0.65, 0.85),
    "Int_Caisse": (1.45, 0.62, 1.05), "Int_RayonPharmacie": (1.6, 0.42, 2.1), "Int_ComptoirPharmacie": (2.05, 0.62, 1.05),
    "Int_FauteuilCoiffeur": (0.62, 0.6, 1.2), "Int_PresentoirSantons": (1.4, 0.8, 0.9), "Int_PresentoirPoterie": (1.4, 0.8, 1.0),
    "Int_PresentoirSavons": (1.4, 0.8, 0.9), "Int_PresentoirLivres": (1.4, 0.8, 0.9), "Int_BancAttente": (1.6, 0.45, 0.92),
    "Int_Drapeaux": (0.7, 0.3, 2.2), "Int_ArmoireArchives": (1.0, 0.52, 2.0), "Int_BancEglise": (3.0, 0.8, 1.0),
    "Int_Autel": (3.4, 2.2, 1.3), "Int_Chandelier": (0.34, 0.34, 1.6), "Int_Benitier": (0.6, 0.6, 1.0),
    "Int_Pupitre": (0.55, 0.45, 1.25), "Int_Statue": (0.55, 0.55, 2.4), "Int_Confessionnal": (1.8, 0.9, 2.4),
    # modules de terrasse réutilisés à l'intérieur des cafés
    "Table_Cafe": (0.7, 0.7, 0.75), "Chaise_Bistrot": (0.45, 0.45, 0.9),
    "Int_CuisineModerne": (3.0, 0.66, 2.3), "Int_Ilot": (1.8, 1.2, 0.95), "Int_TableModerne": (1.8, 1.9, 0.8),
    "Int_CanapeAngle": (2.8, 1.7, 0.8), "Int_TableBasseModerne": (1.1, 0.6, 0.45), "Int_MeubleTV": (1.9, 0.45, 1.65),
    "Int_LampeArc": (0.42, 1.56, 2.1), "Int_EtagereCubes": (1.55, 0.4, 1.52), "Int_LitModerne": (1.8, 2.1, 1.1),
    "Int_Dressing": (2.0, 0.64, 2.3), "Int_BureauInfo": (1.4, 1.35, 1.2), "Int_Douche": (1.2, 0.9, 2.2),
    "Int_VasqueModerne": (0.9, 0.5, 1.0), "Int_PlanteModerne": (0.6, 0.6, 1.8), "Int_CadreModerne": (1.2, 0.04, 0.0),
}


# seules les parties peintes et les tissus prennent la teinte de l'instance (alpha de sommet = 0 ailleurs, comme pour les modules)
TINTABLE = ("BoisPeint", "Toile", "TissuProvence", "Carrosserie", "Laque", "BetonCire")


def _untint(fn):
    def build():
        mb = fn()
        for mat, p in mb.parts.items():
            if mat not in TINTABLE:
                p["C"] = [np.concatenate([np.asarray(c)[:, :3], np.zeros((len(c), 1), np.uint8)], 1) for c in p["C"]]
        return mb
    return build


FURNITURE = {k: _untint(v) for k, v in FURNITURE.items()}
