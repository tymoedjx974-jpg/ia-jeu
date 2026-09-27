"""Éléments architecturaux instanciés : fenêtres, volets, portes, vitrines, balcons, mobilier urbain.

Repère local : X le long du mur, Y vers l'intérieur du bâtiment, Z vers le haut.
Ouverture : x dans [-w/2, w/2], z dans [0, h] ; plan du mur en y = 0 ; l'extérieur est du côté y < 0.
Les parties peintes (BoisPeint, Toile) sont teintées par instance (couleur des volets, des stores...).
"""
import math
import numpy as np
from geomlib import MB, box, tube, revolve, nrm, planar_polygon, WHITE
from materials import TILE

T = lambda m: TILE.get(m, 1.0)
DEPTH = 0.20  # profondeur de l'ouverture (tableau) jusqu'à la menuiserie


def frame_rect(mb, x0, x1, z0, z1, y, t=0.055, d=0.05, mat="BoisPeint"):
    box(mb, mat, ((x0 + x1) / 2, y, z0 + t / 2), (x1 - x0, d, t), uv_scale=T(mat))
    box(mb, mat, ((x0 + x1) / 2, y, z1 - t / 2), (x1 - x0, d, t), uv_scale=T(mat))
    box(mb, mat, (x0 + t / 2, y, (z0 + z1) / 2), (t, d, z1 - z0 - 2 * t), uv_scale=T(mat))
    box(mb, mat, (x1 - t / 2, y, (z0 + z1) / 2), (t, d, z1 - z0 - 2 * t), uv_scale=T(mat))


def glass(mb, x0, x1, z0, z1, y):
    mb.quad("Verre", (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), [(0, 1), (1, 1), (1, 0), (0, 0)], n=(0, -1, 0))


def casement(mb, w, h, y=DEPTH, panes=3, leaves=2):
    """Fenêtre à la française : dormant, vantaux, petits-bois, vitrage."""
    frame_rect(mb, -w / 2, w / 2, 0, h, y + 0.02, t=0.06, d=0.06)
    lw = w / leaves
    for k in range(leaves):
        x0 = -w / 2 + k * lw + 0.05
        x1 = -w / 2 + (k + 1) * lw - 0.05
        frame_rect(mb, x0, x1, 0.06, h - 0.06, y, t=0.045, d=0.045)
        for p in range(1, panes):
            z = 0.06 + (h - 0.12) * p / panes
            box(mb, "BoisPeint", ((x0 + x1) / 2, y, z), (x1 - x0 - 0.06, 0.03, 0.022), uv_scale=1)
        glass(mb, x0 + 0.03, x1 - 0.03, 0.09, h - 0.09, y + 0.01)


def rotated_into(dst, src, ang, pivot):
    """Ajoute à dst le contenu de src tourné de ang (rad) autour de l'axe vertical passant par pivot (x, y)."""
    ca, sa = math.cos(ang), math.sin(ang)
    for mat, a in src.arrays().items():
        P = a["P"].astype(np.float64).copy()
        N = a["N"].astype(np.float64).copy()
        x, y = P[:, 0] - pivot[0], P[:, 1] - pivot[1]
        P[:, 0], P[:, 1] = x * ca - y * sa + pivot[0], x * sa + y * ca + pivot[1]
        nx, ny = N[:, 0].copy(), N[:, 1].copy()
        N[:, 0], N[:, 1] = nx * ca - ny * sa, nx * sa + ny * ca
        dst.add(mat, P, N, a["UV"], a["C"], a["I"])


def casement_open(mb, w, h, y=DEPTH, panes=3, leaves=2, ang=math.radians(96)):
    """Fenêtre ouverte vers l'intérieur (maisons visitables) : dormant fixe, vantaux rabattus contre le tableau."""
    frame_rect(mb, -w / 2, w / 2, 0, h, y + 0.02, t=0.06, d=0.06)
    lw = w / leaves
    for k in range(leaves):
        leaf = MB()
        x0 = -w / 2 + k * lw + 0.05
        x1 = -w / 2 + (k + 1) * lw - 0.05
        frame_rect(leaf, x0, x1, 0.06, h - 0.06, y + 0.03, t=0.045, d=0.045)
        for p in range(1, panes):
            z = 0.06 + (h - 0.12) * p / panes
            box(leaf, "BoisPeint", ((x0 + x1) / 2, y + 0.03, z), (x1 - x0 - 0.06, 0.03, 0.022), uv_scale=1)
        left = (k == 0) if leaves > 1 else True
        pivot = (x0, y + 0.05) if left else (x1, y + 0.05)
        rotated_into(mb, leaf, ang if left else -ang, pivot)


def sill(mb, w, depth_out=0.06, thick=0.06, mat="PierreTaille"):
    box(mb, mat, (0, (DEPTH + 0.04 - depth_out) / 2, -thick / 2 + 0.005), (w + 0.12, DEPTH + 0.04 + depth_out, thick), uv_scale=T(mat))


def shutter_leaf(mb, x0, x1, z0, z1, y_back, inner_face_out=True, thick=0.035, louvers=False):
    """Un vantail de volet : lames + barres + écharpe (volet provençal) ou persienne."""
    w = x1 - x0
    h = z1 - z0
    if louvers:
        frame_rect(mb, x0, x1, z0, z1, y_back - thick / 2, t=0.05, d=thick)
        n = int(h / 0.075)
        for i in range(n):
            z = z0 + 0.06 + (h - 0.12) * (i + 0.5) / n
            box(mb, "BoisPeint", ((x0 + x1) / 2, y_back - thick / 2, z), (w - 0.09, 0.012, 0.06), uv_scale=1, pitch=math.radians(35))
        return
    box(mb, "BoisPeint", ((x0 + x1) / 2, y_back - thick / 2, (z0 + z1) / 2), (w, thick, h), uv_scale=1)
    if inner_face_out:
        yb = y_back - thick - 0.012
        for zc in (z0 + 0.18, (z0 + z1) / 2, z1 - 0.18):
            box(mb, "BoisPeint", ((x0 + x1) / 2, yb, zc), (w - 0.04, 0.025, 0.1), uv_scale=1)
        # écharpes (le Z) entre les barres
        for za, zb in ((z0 + 0.18, (z0 + z1) / 2), ((z0 + z1) / 2, z1 - 0.18)):
            L = math.hypot(w - 0.12, zb - za)
            ang = math.atan2(zb - za, w - 0.12)
            c = ((x0 + x1) / 2, yb, (za + zb) / 2)
            # rotation dans le plan XZ : on construit une boîte tournée autour de Y
            bx = MB()
            box(bx, "BoisPeint", (0, 0, 0), (L, 0.022, 0.08), uv_scale=1)
            for mat, p in bx.parts.items():
                for P, N in zip(p["P"], p["N"]):
                    ca, sa = math.cos(ang), math.sin(ang)
                    x, z = P[:, 0].copy(), P[:, 2].copy()
                    P[:, 0], P[:, 2] = x * ca - z * sa + c[0], x * sa + z * ca + c[2]
                    P[:, 1] += c[1]
                    nx, nz = N[:, 0].copy(), N[:, 2].copy()
                    N[:, 0], N[:, 2] = nx * ca - nz * sa, nx * sa + nz * ca
            mb.extend(bx)


def shutters(mb, w, h, state="open", louvers=False):
    if state == "open":
        shutter_leaf(mb, -w / 2 - w / 2 - 0.02, -w / 2 - 0.02, 0.0, h, -0.005, inner_face_out=True, louvers=louvers)
        shutter_leaf(mb, w / 2 + 0.02, w / 2 + w / 2 + 0.02, 0.0, h, -0.005, inner_face_out=True, louvers=louvers)
    elif state == "closed":
        shutter_leaf(mb, -w / 2 + 0.005, 0, 0.005, h - 0.005, 0.05, inner_face_out=False, louvers=louvers)
        shutter_leaf(mb, 0, w / 2 - 0.005, 0.005, h - 0.005, 0.05, inner_face_out=False, louvers=louvers)
    elif state == "half":
        shutter_leaf(mb, -w / 2 - w / 2 - 0.02, -w / 2 - 0.02, 0.0, h, -0.005, inner_face_out=True, louvers=louvers)
        shutter_leaf(mb, 0, w / 2 - 0.005, 0.005, h - 0.005, 0.05, inner_face_out=False, louvers=louvers)


def surround(mb, w, h, band=0.14, proud=0.012, mat="Enduit"):
    """Encadrement peint en saillie autour de l'ouverture (teinte claire via la couleur de sommet)."""
    col = (246, 240, 228, 0)
    y = -proud / 2
    for (cx, cz, sx, sz) in (((-w / 2 - band / 2), h / 2, band, h + 2 * band), ((w / 2 + band / 2), h / 2, band, h + 2 * band), (0, h + band / 2, w, band)):
        box(mb, mat, (cx, y, cz), (sx, proud, sz), col=col, uv_scale=T(mat), faces=("-y", "-x", "+x", "+z", "-z"))


def window(w=0.9, h=1.35, state="open", louvers=False, grille=False, surround_band=True, panes=3, open_in=False):
    mb = MB()
    if open_in:
        casement_open(mb, w, h, panes=panes)
    else:
        casement(mb, w, h, panes=panes)
    sill(mb, w)
    if surround_band:
        surround(mb, w, h)
    if state:
        shutters(mb, w, h, state, louvers)
    if grille:
        for i in range(5):
            x = -w / 2 + w * (i + 1) / 6
            tube(mb, "Fer", [(x, 0.06, 0.0), (x, 0.06, h)], 0.009, segs=6)
        for z in (0.15, h - 0.15):
            box(mb, "Fer", (0, 0.06, z), (w, 0.012, 0.03), uv_scale=1)
    return mb


def small_window(w=0.55, h=0.55, open_in=False):
    mb = MB()
    frame_rect(mb, -w / 2, w / 2, 0, h, DEPTH, t=0.05, d=0.05)
    if not open_in:
        glass(mb, -w / 2 + 0.04, w / 2 - 0.04, 0.04, h - 0.04, DEPTH + 0.01)
    box(mb, "BoisPeint", (0, DEPTH, h / 2), (0.03, 0.03, h - 0.08), uv_scale=1)
    sill(mb, w, depth_out=0.04, thick=0.05)
    return mb


def door(w=1.0, h=2.2, transom=True, stone=True, open_in=False, leaf=True):
    """Porte d'entrée. leaf=False : encadrement seul, le vantail est un acteur mobile dans Unreal (maisons visitables)."""
    mb = MB()
    y = DEPTH - 0.04
    frame_rect(mb, -w / 2, w / 2, 0, h, y + 0.03, t=0.07, d=0.07)
    ht = h - 0.45 if transom else h - 0.07
    # vantail : lames verticales + cadre (ouvert vers l'intérieur dans les maisons visitables)
    if leaf:
        lf = MB() if open_in else mb
        door_leaf(lf, w, ht, y)
        if open_in:
            rotated_into(mb, lf, math.radians(100), (-w / 2 + 0.07, y + 0.03))
    if transom:
        box(mb, "BoisPeint", (0, y, ht + 0.02), (w - 0.1, 0.07, 0.05), uv_scale=1)
        glass(mb, -w / 2 + 0.07, w / 2 - 0.07, ht + 0.05, h - 0.07, y + 0.02)
        for k in range(1, 4):
            x = -w / 2 + w * k / 4
            box(mb, "BoisPeint", (x, y - 0.01, (ht + h) / 2), (0.025, 0.03, h - ht - 0.1), uv_scale=1)
    # seuil en pierre + marche
    box(mb, "PierreTaille", (0, 0.02, -0.08), (w + 0.2, DEPTH + 0.3, 0.2), uv_scale=3)
    box(mb, "PierreTaille", (0, -0.25, -0.35), (w + 0.4, 0.3, 0.5), uv_scale=3)
    if stone:
        band = 0.2
        for (cx, cz, sx, sz) in (((-w / 2 - band / 2), h / 2, band, h), ((w / 2 + band / 2), h / 2, band, h), (0, h + band / 2, w + 2 * band, band)):
            box(mb, "PierreTaille", (cx, -0.01, cz), (sx, 0.03, sz), uv_scale=3, faces=("-y", "-x", "+x", "+z"))
    return mb


def door_leaf(mb, w, ht, y):
    """Vantail en lames verticales avec traverses et poignée (repère de la porte)."""
    box(mb, "BoisPeint", (0, y, (0.02 + ht) / 2), (w - 0.14, 0.05, ht - 0.02), uv_scale=1)
    for zc in (0.25, ht * 0.5, ht - 0.25):
        box(mb, "BoisPeint", (0, y - 0.03, zc), (w - 0.2, 0.02, 0.1), uv_scale=1)
    tube(mb, "Fer", [(w / 2 - 0.16, y - 0.08, 1.0), (w / 2 - 0.16, y - 0.03, 1.0)], 0.018, segs=6)
    # poignée côté intérieur
    tube(mb, "Fer", [(w / 2 - 0.16, y + 0.025, 1.0), (w / 2 - 0.16, y + 0.07, 1.0)], 0.018, segs=6)


# vantaux mobiles des maisons visitables : charnière à l'origine, porte fermée le long de +X, extérieur vers -Y
LEAF_HINGE_Y = DEPTH - 0.04 + 0.03
LEAVES = {  # nom du vantail : (largeur de la porte, hauteur du vantail)
    "Vantail_Porte": (1.0, 2.25 - 0.45),
    "Vantail_PorteSimple": (0.95, 2.15 - 0.07),
}
DOOR_LEAF = {"PorteI": "Vantail_Porte", "PorteI_Simple": "Vantail_PorteSimple"}


def moving_leaf(name):
    w, ht = LEAVES[name]
    src = MB()
    door_leaf(src, w, ht, DEPTH - 0.04)
    out = MB()
    for mat, a in src.arrays().items():
        P = a["P"].astype(np.float64).copy()
        P[:, 0] -= -w / 2 + 0.07
        P[:, 1] -= LEAF_HINGE_Y
        out.add(mat, P, a["N"], a["UV"], a["C"], a["I"])
    return out


def leaf_collision(name):
    """Boîte de collision du vantail (centre, taille) dans son repère."""
    w, ht = LEAVES[name]
    lw = w - 0.14
    return ("boxes", [lw / 2, -0.03, (0.02 + ht) / 2, lw, 0.07, ht - 0.02])


def arched_infill(mb, w, h, rise, mat="Enduit", y=0.0, col=WHITE):
    """Remplit le haut d'une ouverture rectangulaire pour former un arc surbaissé."""
    n = 14
    pts = []
    zs = h - rise
    for i in range(n + 1):
        t = i / n
        x = -w / 2 + w * t
        z = zs + rise * math.sin(math.pi * t)
        pts.append((x, z))
    outer = [(-w / 2, h), ] + pts[::-1][:0]
    poly = [(w / 2, zs), (w / 2, h), (-w / 2, h), (-w / 2, zs)] + pts[1:-1]
    poly = [(w / 2, zs), (w / 2, h), (-w / 2, h), (-w / 2, zs)]
    arc = [(x, z) for x, z in pts]
    poly = [(-w / 2, zs), ] + arc[1:-1] + [(w / 2, zs), (w / 2, h), (-w / 2, h)]
    # plan du mur : X horizontal, Z vertical ; normale vers l'extérieur (-Y)
    planar_polygon(mb, mat, poly, [], origin=(0, y, 0), e1=(1, 0, 0), e2=(0, 0, 1),
                   uv_fn=lambda v2, P: np.stack([P[:, 0] / T(mat), -P[:, 2] / T(mat)], -1), col=col)
    # intrados de l'arc
    for i in range(n):
        (xa, za), (xb, zb) = arc[i], arc[i + 1]
        mb.quad(mat, (xb, y, zb), (xa, y, za), (xa, DEPTH, za), (xb, DEPTH, zb), [(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)], col)


def carriage_door(w=2.4, h=2.6, rise=0.45, open_in=False):
    mb = MB()
    y = DEPTH - 0.02
    for k, (x0, x1) in enumerate(((-w / 2 + 0.05, -0.01), (0.01, w / 2 - 0.05))):
        leaf = MB() if open_in else mb
        box(leaf, "BoisPeint", ((x0 + x1) / 2, y, (h - rise * 0.2) / 2), (x1 - x0, 0.06, h - rise * 0.2), uv_scale=1)
        for zc in (0.3, 1.3, 2.1):
            box(leaf, "BoisPeint", ((x0 + x1) / 2, y - 0.035, zc), (x1 - x0 - 0.1, 0.02, 0.12), uv_scale=1)
        if open_in:
            rotated_into(mb, leaf, math.radians(100) * (1 if k == 0 else -1), (x0, y + 0.03) if k == 0 else (x1, y + 0.03))
    arched_infill(mb, w, h, rise, y=-0.001, col=(240, 236, 226, 0))
    box(mb, "PierreTaille", (0, 0.02, -0.08), (w + 0.1, DEPTH + 0.3, 0.2), uv_scale=3)
    return mb


def shopfront(w=2.6, h=2.7, awning=True):
    mb = MB()
    y = DEPTH - 0.05
    # soubassement bois, vitrine, porte vitrée, imposte
    frame_rect(mb, -w / 2, w / 2, 0, h, y + 0.02, t=0.09, d=0.08)
    dw = 0.95
    xd = w / 2 - 0.09 - dw
    box(mb, "BoisPeint", (-w / 2 + 0.09 + (xd - (-w / 2 + 0.09)) / 2, y, 0.3), (xd - (-w / 2 + 0.09), 0.08, 0.5), uv_scale=1)
    glass(mb, -w / 2 + 0.1, xd - 0.04, 0.58, h - 0.5, y + 0.03)
    box(mb, "BoisPeint", (xd - 0.02, y, h / 2), (0.06, 0.08, h - 0.1), uv_scale=1)
    box(mb, "BoisPeint", (0, y, h - 0.46), (w - 0.1, 0.08, 0.07), uv_scale=1)
    glass(mb, -w / 2 + 0.1, w / 2 - 0.1, h - 0.42, h - 0.1, y + 0.03)
    # porte vitrée
    frame_rect(mb, xd + 0.02, w / 2 - 0.09, 0.0, h - 0.5, y - 0.01, t=0.08, d=0.05)
    glass(mb, xd + 0.1, w / 2 - 0.17, 0.35, h - 0.58, y + 0.0)
    box(mb, "BoisPeint", ((xd + w / 2 - 0.09) / 2, y - 0.01, 0.18), (dw - 0.1, 0.05, 0.3), uv_scale=1)
    box(mb, "PierreTaille", (0, 0.02, -0.08), (w + 0.1, DEPTH + 0.3, 0.2), uv_scale=3)
    if awning:
        # store banne en toile (teinté par instance) : pente + lambrequin
        d = 1.3
        z1, z0 = h + 0.55, h + 0.05
        mb.quad("Toile", (-w / 2 - 0.1, -0.02, z1), (w / 2 + 0.1, -0.02, z1), (w / 2 + 0.1, -d, z0), (-w / 2 - 0.1, -d, z0), [(0, 0), (1, 0), (1, 1), (0, 1)])
        mb.quad("Toile", (-w / 2 - 0.1, -d, z0), (w / 2 + 0.1, -d, z0), (w / 2 + 0.1, -d, z0 - 0.22), (-w / 2 - 0.1, -d, z0 - 0.22), [(0, 0), (1, 0), (1, 0.2), (0, 0.2)])
        # dessous (visible depuis la rue)
        mb.quad("Toile", (-w / 2 - 0.1, -d, z0 + 0.002), (w / 2 + 0.1, -d, z0 + 0.002), (w / 2 + 0.1, -0.02, z1 + 0.002), (-w / 2 - 0.1, -0.02, z1 + 0.002), [(0, 1), (1, 1), (1, 0), (0, 0)])
        for sx in (-1, 1):
            tube(mb, "Fer", [(sx * (w / 2 + 0.05), -0.02, h + 0.1), (sx * (w / 2 + 0.05), -d + 0.05, z0 + 0.02)], 0.015, segs=6)
    return mb


def balcony_door(w=0.9, h=2.15, open_in=False):
    mb = MB()
    if open_in:
        casement_open(mb, w, h, panes=4)
    else:
        casement(mb, w, h, panes=4)
    shutters(mb, w, h, "open")
    surround(mb, w, h)
    # dalle en pierre + garde-corps en fer forgé
    d = 0.42
    box(mb, "PierreTaille", (0, -d / 2 + 0.05, -0.05), (w + 0.5, d + 0.1, 0.1), uv_scale=3)
    rail_h = 0.95
    xs = np.linspace(-w / 2 - 0.2, w / 2 + 0.2, 11)
    for x in xs:
        tube(mb, "Fer", [(x, -d + 0.03, 0.0), (x, -d + 0.03, rail_h)], 0.008, segs=5)
    tube(mb, "Fer", [(-w / 2 - 0.22, -d + 0.03, rail_h), (w / 2 + 0.22, -d + 0.03, rail_h)], 0.018, segs=6)
    tube(mb, "Fer", [(-w / 2 - 0.22, -d + 0.03, 0.12), (w / 2 + 0.22, -d + 0.03, 0.12)], 0.012, segs=5)
    for sx in (-1, 1):
        tube(mb, "Fer", [(sx * (w / 2 + 0.22), 0.0, rail_h), (sx * (w / 2 + 0.22), -d + 0.03, rail_h)], 0.015, segs=6)
        tube(mb, "Fer", [(sx * (w / 2 + 0.22), 0.0, 0.1), (sx * (w / 2 + 0.22), -d + 0.03, 0.1)], 0.012, segs=5)
    # volutes décoratives (petits cercles)
    for x in xs[1:-1:2]:
        pts = [(x + 0.05 * math.cos(a), -d + 0.03, 0.55 + 0.08 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 12)]
        tube(mb, "Fer", pts, 0.005, segs=4)
    return mb


def wall_lantern():
    """Lanterne provençale sur potence (fixée au mur, le mur est en y = 0, extérieur y < 0)."""
    mb = MB()
    pts = [(0, 0, 0), (0, -0.25, 0.05), (0, -0.45, 0.18), (0, -0.55, 0.3)]
    tube(mb, "Fer", pts, 0.012, segs=6)
    tube(mb, "Fer", [(0, 0, -0.25), (0, -0.3, -0.05), (0, -0.45, 0.18)], 0.009, segs=5)
    box(mb, "Fer", (0, 0.0, 0.0), (0.12, 0.02, 0.35), uv_scale=1)
    c = (0, -0.55, 0.0)
    revolve(mb, "Fer", [(0.02, 0.28), (0.14, 0.2), (0.16, 0.17), (0.02, 0.13)], (c[0], c[1], 0.0), segs=8)
    revolve(mb, "Lanterne", [(0.09, -0.18), (0.13, 0.13)], (c[0], c[1], 0.0), segs=8)
    revolve(mb, "Fer", [(0.02, -0.26), (0.1, -0.2), (0.08, -0.18)], (c[0], c[1], 0.0), segs=8)
    for a in np.linspace(0, 2 * math.pi, 5)[:-1]:
        x, y = c[0] + 0.13 * math.cos(a), c[1] + 0.13 * math.sin(a)
        tube(mb, "Fer", [(x * 0.7, y + (1 - 0.7) * (c[1] - y) * 0, -0.19), (x, y, 0.14)], 0.006, segs=4)
    return mb


def street_lamp(h=3.6):
    mb = MB()
    revolve(mb, "Fer", [(0.12, 0), (0.1, 0.3), (0.06, 0.35), (0.05, h - 0.4), (0.07, h - 0.3)], (0, 0, 0), segs=10)
    tube(mb, "Fer", [(0, 0, h - 0.3), (0.25, 0, h - 0.15), (0.45, 0, h - 0.2)], 0.02, segs=6)
    revolve(mb, "Fer", [(0.02, 0.18), (0.16, 0.08), (0.02, 0.02)], (0.45, 0, h - 0.4), segs=8)
    revolve(mb, "Lanterne", [(0.08, -0.3), (0.13, 0.02)], (0.45, 0, h - 0.4), segs=8)
    return mb


def bench():
    mb = MB()
    for x in (-0.7, 0.7):
        box(mb, "Fer", (x, 0, 0.22), (0.05, 0.45, 0.44), uv_scale=1)
        box(mb, "Fer", (x, 0.2, 0.62), (0.05, 0.05, 0.45), uv_scale=1)
    for k in range(4):
        box(mb, "BoisBrut", (0, -0.18 + k * 0.11, 0.45), (1.7, 0.09, 0.035), uv_scale=1)
    for k in range(2):
        box(mb, "BoisBrut", (0, 0.23, 0.62 + k * 0.14), (1.7, 0.035, 0.1), uv_scale=1)
    return mb


def stone_bench():
    mb = MB()
    box(mb, "PierreTaille", (0, 0, 0.42), (1.8, 0.45, 0.1), uv_scale=3)
    for x in (-0.65, 0.65):
        box(mb, "PierreTaille", (x, 0, 0.19), (0.3, 0.38, 0.38), uv_scale=3)
    return mb


def bollard():
    mb = MB()
    revolve(mb, "PierreTaille", [(0.14, -0.2), (0.14, 0.45), (0.12, 0.55), (0.06, 0.62), (0.0, 0.63)], (0, 0, 0), segs=10, u_tile=3, v_tile=3)
    return mb


def pot(r=0.22, h=0.4, flowers=True, flower_q=0):
    mb = MB()
    revolve(mb, "TerreCuite", [(r * 0.7, 0), (r * 0.95, h * 0.8), (r * 1.08, h * 0.85), (r * 1.08, h), (r * 0.98, h), (r * 0.92, h * 0.9)], (0, 0, 0), segs=12)
    revolve(mb, "TerreCuite", [(r * 0.92, h * 0.9), (0.0, h * 0.88)], (0, 0, 0), segs=12)
    if flowers:
        foliage_ball(mb, (0, 0, h + r * 0.4), r * 1.4, "Fleurs", flower_q, cards=7)
    return mb


def foliage_ball(mb, c, rad, mat, quad, cards=8, seed=0, sway=128):
    """Petite touffe de cartes de feuillage (quadrant `quad` de l'atlas 2x2)."""
    rng = np.random.default_rng(seed + quad * 7)
    u0, v0 = (quad % 2) * 0.5, (quad // 2) * 0.5
    for i in range(cards):
        a = rng.uniform(0, math.pi)
        tilt = rng.uniform(-0.6, 0.6)
        d = np.array([math.cos(a), math.sin(a), 0.0])
        up = np.array([0.0, 0.0, 1.0]) * math.cos(tilt) + np.cross(d, [0, 0, 1]) * math.sin(tilt)
        cc = np.asarray(c) + rng.normal(0, rad * 0.25, 3)
        s = rad * rng.uniform(0.8, 1.2)
        p0 = cc - d * s - up * s
        p1 = cc + d * s - up * s
        p2 = cc + d * s + up * s
        p3 = cc - d * s + up * s
        n = nrm(cc - np.asarray(c) + np.array([0, 0, rad * 0.5]))
        col = (int(rng.uniform(220, 255)), int(rng.uniform(220, 255)), int(rng.uniform(215, 250)), sway)
        mb.add(mat, [p0, p1, p2, p3], [n], [(u0, v0 + 0.5), (u0 + 0.5, v0 + 0.5), (u0 + 0.5, v0), (u0, v0)], [col], [[0, 1, 2], [0, 2, 3]])


def window_box(w=0.8):
    mb = MB()
    box(mb, "TerreCuite", (0, -0.12, 0.09), (w, 0.2, 0.18), uv_scale=1)
    for k in range(3):
        foliage_ball(mb, (-w / 3 + k * w / 3, -0.12, 0.3), 0.2, "Fleurs", k % 2, cards=5, seed=k)
    return mb


def cafe_table():
    mb = MB()
    revolve(mb, "Fer", [(0.2, 0), (0.02, 0.05), (0.02, 0.72)], (0, 0, 0), segs=8)
    revolve(mb, "Fer", [(0.0, 0.72), (0.32, 0.72), (0.32, 0.745), (0.0, 0.745)], (0, 0, 0), segs=16)
    return mb


def bistro_chair():
    mb = MB()
    for x, y in ((-0.2, -0.2), (0.2, -0.2), (-0.2, 0.2), (0.2, 0.2)):
        tube(mb, "Fer", [(x, y, 0), (x * 0.9, y * 0.9, 0.45)], 0.012, segs=5)
    box(mb, "Toile", (0, 0, 0.46), (0.42, 0.42, 0.025), uv_scale=1)
    for x in (-0.2, 0.2):
        tube(mb, "Fer", [(x * 0.9, 0.18, 0.45), (x, 0.22, 0.85)], 0.012, segs=5)
    box(mb, "Toile", (0, 0.21, 0.72), (0.42, 0.02, 0.22), uv_scale=1)
    return mb


def parasol(r=1.3, h=2.4):
    mb = MB()
    tube(mb, "BoisBrut", [(0, 0, 0), (0, 0, h + 0.1)], 0.025, segs=6)
    box(mb, "PierreTaille", (0, 0, 0.05), (0.45, 0.45, 0.1), uv_scale=3)
    n = 8
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        p0 = (0, 0, h + 0.1)
        p1 = (r * math.cos(a0), r * math.sin(a0), h - 0.35)
        p2 = (r * math.cos(a1), r * math.sin(a1), h - 0.35)
        nn = nrm(np.cross(np.subtract(p1, p0), np.subtract(p2, p0)))
        mb.add("Toile", [p0, p1, p2], [nn], [(0.5, 0), (0, 1), (1, 1)], [WHITE], [[0, 1, 2]])
        mb.add("Toile", [p0, p2, p1], [-nn], [(0.5, 0), (1, 1), (0, 1)], [(200, 200, 200, 255)], [[0, 1, 2]])
        # lambrequin
        mb.quad("Toile", p1, p2, (p2[0], p2[1], p2[2] - 0.18), (p1[0], p1[1], p1[2] - 0.18), [(0, 0), (1, 0), (1, 0.2), (0, 0.2)])
    return mb


def flag_pole(length=1.6, flag="drapeau_fr", signs=None):
    """Hampe inclinée fixée au mur + drapeau (atlas des enseignes)."""
    mb = MB()
    ang = math.radians(35)
    p0 = np.array([0, 0.0, 0.0])
    p1 = np.array([0, -length * math.sin(ang), length * math.cos(ang)])
    tube(mb, "BoisPeint", [p0, p1], 0.018, segs=6, col=(250, 250, 250, 255))
    if signs:
        u0, v0, u1, v1 = signs[flag]
        # drapeau accroché le long de la hampe, pendant légèrement
        top = p1 - (p1 - p0) * 0.05
        mid = p1 - (p1 - p0) * 0.45
        side = np.array([0.9, 0, 0])
        pts = [mid, top, top + side + np.array([0, -0.05, -0.25]), mid + side + np.array([0, -0.05, -0.28])]
        nn = nrm(np.cross(pts[1] - pts[0], pts[2] - pts[0]))
        mb.add("Enseignes", pts, [nn], [(u0, v1), (u0, v0), (u1, v0), (u1, v1)], [WHITE], [[0, 1, 2], [0, 2, 3]])
        mb.add("Enseignes", pts, [-nn], [(u0, v1), (u0, v0), (u1, v0), (u1, v1)], [WHITE], [[0, 2, 1], [0, 3, 2]])
    return mb


import json as _json, os as _os
_SIGNS = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "tex", "Enseignes.json"), encoding="utf-8"))

MODULE_BUILDERS = {
    "Drapeau_FR": lambda: flag_pole(1.6, "drapeau_fr", _SIGNS),
    "Drapeau_EU": lambda: flag_pole(1.6, "drapeau_eu", _SIGNS),
    "Fenetre_Ouverte": lambda: window(0.9, 1.35, "open"),
    "Fenetre_Fermee": lambda: window(0.9, 1.35, "closed"),
    "Fenetre_MiClose": lambda: window(0.9, 1.35, "half"),
    "Fenetre_Persiennes": lambda: window(0.9, 1.35, "open", louvers=True),
    "Fenetre_Nue": lambda: window(0.9, 1.35, None, surround_band=False),
    "Fenetre_Barreaux": lambda: window(0.8, 1.1, None, grille=True, surround_band=False, panes=2),
    "Fenestron": lambda: small_window(0.55, 0.55),
    "Porte": lambda: door(1.0, 2.25, transom=True),
    "Porte_Simple": lambda: door(0.95, 2.15, transom=False, stone=False),
    "Remise": lambda: carriage_door(2.4, 2.6),
    "Vitrine": lambda: shopfront(2.6, 2.75, awning=True),
    "Vitrine_SansStore": lambda: shopfront(2.6, 2.75, awning=False),
    "PorteFenetre_Balcon": lambda: balcony_door(0.9, 2.15),
    # maisons visitables : ouvertures sans vitre, vantaux ouverts vers l'intérieur
    "FenetreV_Ouverte": lambda: window(0.9, 1.35, "open", open_in=True),
    "FenetreV_Fermee": lambda: window(0.9, 1.35, "closed", open_in=True),
    "FenetreV_MiClose": lambda: window(0.9, 1.35, "half", open_in=True),
    "FenetreV_Persiennes": lambda: window(0.9, 1.35, "open", louvers=True, open_in=True),
    "FenetreV_Nue": lambda: window(0.9, 1.35, None, surround_band=False, open_in=True),
    "FenetreV_Barreaux": lambda: window(0.8, 1.1, None, grille=True, surround_band=False, panes=2, open_in=True),
    "FenestronV": lambda: small_window(0.55, 0.55, open_in=True),
    "PorteV": lambda: door(1.0, 2.25, transom=True, open_in=True),
    "PorteV_Simple": lambda: door(0.95, 2.15, transom=False, stone=False, open_in=True),
    "RemiseV": lambda: carriage_door(2.4, 2.6, open_in=True),
    "PorteI": lambda: door(1.0, 2.25, transom=True, open_in=True, leaf=False),
    "PorteI_Simple": lambda: door(0.95, 2.15, transom=False, stone=False, open_in=True, leaf=False),
    "Vantail_Porte": lambda: moving_leaf("Vantail_Porte"),
    "Vantail_PorteSimple": lambda: moving_leaf("Vantail_PorteSimple"),
    "PorteFenetreV_Balcon": lambda: balcony_door(0.9, 2.15, open_in=True),
    "Lanterne_Murale": wall_lantern,
    "Lampadaire": street_lamp,
    "Banc": bench,
    "Banc_Pierre": stone_bench,
    "Borne": bollard,
    "Pot_Geranium": lambda: pot(0.22, 0.4, True, 0),
    "Pot_Rose": lambda: pot(0.25, 0.45, True, 1),
    "Pot_Bougainvillier": lambda: pot(0.32, 0.55, True, 2),
    "Jardiniere": window_box,
    "Table_Cafe": cafe_table,
    "Chaise_Bistrot": bistro_chair,
    "Parasol": parasol,
}

# dimensions nominales des ouvertures (largeur, hauteur) : sert à découper les murs
OPENINGS = {
    "Fenetre_Ouverte": (0.9, 1.35), "Fenetre_Fermee": (0.9, 1.35), "Fenetre_MiClose": (0.9, 1.35),
    "Fenetre_Persiennes": (0.9, 1.35), "Fenetre_Nue": (0.9, 1.35), "Fenetre_Barreaux": (0.8, 1.1),
    "Fenestron": (0.55, 0.55), "Porte": (1.0, 2.25), "Porte_Simple": (0.95, 2.15), "Remise": (2.4, 2.6),
    "Vitrine": (2.6, 2.75), "Vitrine_SansStore": (2.6, 2.75), "PorteFenetre_Balcon": (0.9, 2.15),
}
# variantes ouvertes des maisons visitables (mêmes dimensions)
VISIT = {"Fenetre_Ouverte": "FenetreV_Ouverte", "Fenetre_Fermee": "FenetreV_Fermee", "Fenetre_MiClose": "FenetreV_MiClose",
         "Fenetre_Persiennes": "FenetreV_Persiennes", "Fenetre_Nue": "FenetreV_Nue", "Fenetre_Barreaux": "FenetreV_Barreaux",
         "Fenestron": "FenestronV", "Porte": "PorteI", "Porte_Simple": "PorteI_Simple", "Remise": "RemiseV",
         "PorteFenetre_Balcon": "PorteFenetreV_Balcon"}
for _k, _v in VISIT.items():
    OPENINGS[_v] = OPENINGS[_k]
OPENINGS["PorteV"], OPENINGS["PorteV_Simple"] = OPENINGS["Porte"], OPENINGS["Porte_Simple"]

# mobilier d'intérieur
from mobilier_int import FURNITURE as _FURN
MODULE_BUILDERS.update(_FURN)
