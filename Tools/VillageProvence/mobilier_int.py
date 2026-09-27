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
}


# seules les parties peintes et les tissus prennent la teinte de l'instance (alpha de sommet = 0 ailleurs, comme pour les modules)
TINTABLE = ("BoisPeint", "Toile", "TissuProvence")


def _untint(fn):
    def build():
        mb = fn()
        for mat, p in mb.parts.items():
            if mat not in TINTABLE:
                p["C"] = [np.concatenate([np.asarray(c)[:, :3], np.zeros((len(c), 1), np.uint8)], 1) for c in p["C"]]
        return mb
    return build


FURNITURE = {k: _untint(v) for k, v in FURNITURE.items()}
