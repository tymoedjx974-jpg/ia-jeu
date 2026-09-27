"""Maisons visitables : intérieurs de maisons de village provençales.

Pour chaque maison retenue : murs épais (45 cm) enduits à la chaux, sol en tomettes, plafonds à poutres apparentes,
escalier droit le long d'un mur, rez-de-chaussée en pièce à vivre (séjour avec cheminée + cuisine),
étage avec salle de bain et chambre. Les fenêtres des deux premiers niveaux sont ouvertes (sans vitre),
la porte d'entrée est ouverte. Le mobilier est instancié (voir mobilier_int.py).

Repère local d'une maison : x le long du grand axe, y le long du petit axe, centré sur l'intérieur.
"""
import math, collections
import numpy as np
from shapely.geometry import Polygon, Point, box as sbox
from shapely.ops import unary_union
from common import ombr
from geomlib import box, tube, planar_polygon, triangulate, nrm, WHITE
from materials import TILE
from mobilier_int import SIZE
from modules import VISIT

T_WALL = 0.45       # épaisseur des murs extérieurs
SLAB = 0.24         # épaisseur des planchers
STAIR_W = 0.95
TREAD = 0.235
RISE_MAX = 0.2
PART = 0.1          # épaisseur des cloisons
COL_PLAFOND = (247, 244, 238, 255)
DOOR_TYPES = ("Porte", "Porte_Simple", "Remise")
PAINT = [(96, 132, 160), (122, 150, 128), (170, 186, 170), (214, 204, 170), (120, 140, 170), (150, 170, 190), (196, 120, 90)]
FABRIC = [(222, 176, 64), (70, 104, 160), (176, 64, 50), (120, 136, 70), (206, 150, 60), (90, 120, 150)]
REJECT = collections.Counter()   # raisons de refus des maisons candidates (diagnostic)
LINEN = [(236, 226, 204), (212, 196, 170), (190, 170, 140), (160, 170, 150)]


# ------------------------------------------------------------------ sélection
def candidates(blds, center, max_n=260, spacing=11.0):
    """Maisons simples (presque rectangulaires, 2 niveaux ou plus) réparties dans le village."""
    out = []
    for b in blds:
        if b["style"] not in ("core", "faubourg", "mas", "villa") or b.get("shop") or b.get("mairie") or b["nf"] < 2:
            continue
        p = b["poly"]
        if not (40 <= p.area <= 210):
            continue
        r = p.minimum_rotated_rectangle
        if p.area / max(r.area, 1e-6) < 0.9:
            continue
        _, _, Lm, Wm = b["ombr"]
        if Lm < 7.4 or Wm < 3.9:
            continue
        out.append(b)
    pri = {"core": 0, "faubourg": 1, "villa": 2, "mas": 2}
    out.sort(key=lambda b: (pri[b["style"]], b["poly"].centroid.distance(center)))
    chosen = []
    for b in out:
        c = b["poly"].centroid
        if all(c.distance(o["poly"].centroid) > spacing for o in chosen):
            chosen.append(b)
        if len(chosen) >= max_n:
            break
    for b in chosen:
        b["visit_cand"] = True
    return chosen


# ------------------------------------------------------------------ plan
def plan(b, info, openings, gz):
    """Étudie la maison ; renvoie le plan de l'intérieur, ou None si elle ne se prête pas à un intérieur simple."""
    if b["nf"] < 2:
        REJECT["niveaux"] += 1
        return None
    p = b["poly"]
    ip = p.buffer(-T_WALL, join_style=2)
    if ip.geom_type != "Polygon" or ip.area < 20:
        REJECT["forme"] += 1
        return None
    ip = ip.simplify(0.02)
    c, a, L, W = ombr(ip)
    if ip.area / (L * W) < 0.92:
        REJECT["pas rectangulaire"] += 1
        return None
    q = np.array([-a[1], a[0]])
    fh = b["fh"]
    l0 = b["zref"]
    l1 = l0 + fh[0]
    ctop = l1 + fh[1] - 0.05 if b["nf"] == 2 else l1 + fh[1] - SLAB
    n = int(math.ceil(fh[0] / RISE_MAX))
    rise = fh[0] / n
    run = n * TREAD
    if L < run + 2.7 or W < STAIR_W + PART + 1.75:
        REJECT["trop petite"] += 1
        return None
    # le terrain ne doit pas traverser le plancher
    xs = np.linspace(-L / 2 + 0.2, L / 2 - 0.2, 7)
    ys = np.linspace(-W / 2 + 0.2, W / 2 - 0.2, 4)
    pts = [c + x * a + y * q for x in xs for y in ys]
    if max(gz(pt[0], pt[1]) for pt in pts) > l0 - 0.05:
        REJECT["terrain"] += 1
        return None

    def to_local(P):
        d = np.asarray(P) - c
        return float(d @ a), float(d @ q)

    # ouvertures dans le repère local
    locs = []
    for idx, o in enumerate(openings):
        e = info[o["edge"]]
        sc = (o["s0"] + o["s1"]) / 2
        P = e["p0"] + e["u"] * sc - e["out"] * T_WALL
        lx, ly = to_local(P)
        ox, oy = float(e["out"] @ a), float(e["out"] @ q)
        side = "+x" if ox > 0.8 else "-x" if ox < -0.8 else "+y" if oy > 0.8 else "-y" if oy < -0.8 else None
        w = o["s1"] - o["s0"]
        span = (lx - w / 2, lx + w / 2) if side in ("+y", "-y") else (ly - w / 2, ly + w / 2)
        floor = 0 if o["z0"] < l1 - 0.6 else (1 if o["z0"] < ctop - 0.3 else 2)
        is_door = o["type"] in DOOR_TYPES
        locs.append(dict(i=idx, side=side, span=span, z0=o["z0"], z1=o["z1"], floor=floor, door=is_door, type=o["type"]))
    doors = [d for d in locs if d["door"] and d["floor"] == 0 and d["side"] and -0.8 <= d["z0"] - l0 <= 0.45]
    if not doors:
        REJECT["porte"] += 1
        return None
    main = min(doors, key=lambda d: abs(d["z0"] - l0))

    def overlaps(a0, a1, b0, b1, m=0.0):
        return a0 < b1 + m and a1 > b0 - m

    best = None
    order = [(s, d) for s in (1, -1) for d in (1, -1)]
    # escalier de préférence sur le long mur opposé à la porte d'entrée
    order.sort(key=lambda sd: (main["side"] == ("+y" if sd[0] > 0 else "-y")))
    for s, d in order:
        end = -d * L / 2
        xr = sorted((end, end + d * run))
        band = (W / 2 - STAIR_W, W / 2) if s > 0 else (-W / 2, -W / 2 + STAIR_W)
        y_b = band[0] if s > 0 else band[1]
        side_band = "+y" if s > 0 else "-y"
        side_other = "-y" if s > 0 else "+y"
        side_end = "-x" if d > 0 else "+x"
        ok = True
        for o in locs:
            if o["floor"] == 0 and o["door"] and o["side"] == side_band and overlaps(*o["span"], *xr, 0.3):
                ok = False
            if o["floor"] == 0 and o["door"] and o["side"] == side_end and overlaps(*o["span"], *band, 0.2):
                ok = False
            if o["floor"] == 1 and o["type"].startswith("PorteFenetre") and o["side"] == side_band and overlaps(*o["span"], *xr, 0.2):
                ok = False
        if not ok:
            continue
        for delta in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            xc = end + d * (run + delta)
            if L - (run + delta) < 2.6:
                break
            bad = False
            for o in locs:
                if o["floor"] != 1:
                    continue
                if o["side"] == side_other and overlaps(*o["span"], xc, xc, 0.12):
                    bad = True
                if o["side"] == side_end and overlaps(*o["span"], y_b, y_b, 0.12):
                    bad = True
            if not bad:
                best = dict(s=s, d=d, end=end, xc=xc, band=band, y_b=y_b)
                break
        if best:
            break
    if not best:
        REJECT["escalier"] += 1
        return None
    return dict(c=c, a=a, q=q, L=L, W=W, ip=ip, l0=l0, l1=l1, ctop=ctop, n=n, rise=rise, run=run, locs=locs, main=main, **best)


def apply_openings(b, pl, openings, info):
    """Ouvre la maison : porte(s) d'entrée ouvertes au niveau du sol intérieur, fenêtres sans vitre sur deux niveaux."""
    l0 = pl["l0"]
    steps = []
    for lo in pl["locs"]:
        o = openings[lo["i"]]
        if lo["floor"] <= 1 and o["type"] in VISIT:
            if lo["door"] and not (-0.8 <= lo["z0"] - l0 <= 0.45):
                continue
            o["type"] = VISIT[o["type"]]
            o["visit"] = True
            if lo["door"] and o["z0"] < l0 - 0.02:
                e = info[o["edge"]]
                sc = (o["s0"] + o["s1"]) / 2
                steps.append((e["p0"] + e["u"] * sc, e["out"], e["u"], o["s1"] - o["s0"], o["z0"] - 0.03))
                h = o["z1"] - o["z0"]
                o["z0"], o["z1"] = l0, l0 + h
    pl["steps"] = steps
    # ouvertures vues de l'intérieur (après ajustement des portes) : point sur la face intérieure, direction du mur
    ow = []
    for o in openings:
        e = info[o["edge"]]
        sc = (o["s0"] + o["s1"]) / 2
        ow.append((e["p0"] + e["u"] * sc - e["out"] * T_WALL, e["u"], o["s1"] - o["s0"], o["z0"], o["z1"]))
    pl["openings_world"] = ow


# ------------------------------------------------------------------ géométrie
def _flat(mb, mat, poly, z, up=True, col=WHITE, tile=None, holes=()):
    outer = np.array(poly.exterior.coords)[:-1]
    hs = [np.array(h.coords)[:-1] for h in poly.interiors] + [np.asarray(h) for h in holes]
    v2, idx = triangulate(outer, hs)
    if len(idx) == 0:
        return
    P = np.column_stack([v2, np.full(len(v2), z)])
    e1 = P[idx[:, 1]] - P[idx[:, 0]]
    e2 = P[idx[:, 2]] - P[idx[:, 0]]
    nz = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    flip = (nz < 0) if up else (nz > 0)
    idx = idx.copy()
    idx[flip] = idx[flip][:, [0, 2, 1]]
    t = tile or TILE.get(mat, 3.0)
    UV = np.column_stack([v2[:, 0] / t, -v2[:, 1] / t])
    mb.add(mat, P, [(0, 0, 1 if up else -1)], UV, [col], idx)


def build(b, pl, mb, inst, rng):
    c, a, q, L, W = pl["c"], pl["a"], pl["q"], pl["L"], pl["W"]
    s, d, end, xc, band, y_b = pl["s"], pl["d"], pl["end"], pl["xc"], pl["band"], pl["y_b"]
    l0, l1, ctop = pl["l0"], pl["l1"], pl["ctop"]
    ip = pl["ip"]
    yaw_a = math.atan2(a[1], a[0])
    dec = pl["decor"] = pick_decor(rng, b["style"])

    def Wp(x, y):
        return c + x * a + y * q

    def Wbox(mat, x, y, z, sx, sy, sz, col=WHITE, uv=1.0, faces="all", yaw=0.0):
        P = Wp(x, y)
        box(mb, mat, (P[0], P[1], z), (sx, sy, sz), yaw=yaw_a + yaw, col=col, uv_scale=uv, faces=faces)

    def rect_world(x0, x1, y0, y1):
        return Polygon([tuple(Wp(x0, y0)), tuple(Wp(x1, y0)), tuple(Wp(x1, y1)), tuple(Wp(x0, y1))])

    xr = sorted((end, end + d * pl["run"]))
    hole_x = sorted((end - d * 0.2, end + d * pl["run"]))  # la trémie va jusqu'au mur de départ
    hole = rect_world(hole_x[0], hole_x[1], band[0] - (0.0 if s > 0 else 0.2), band[1] + (0.2 if s > 0 else 0.0))
    hole = hole.intersection(ip.buffer(0.01))

    # ---------- sols et plafonds
    _flat(mb, dec["floor0"], ip, l0 + 0.002, up=True, col=dec["fcol0"])
    upper = ip.difference(hole)
    for g in ([upper] if upper.geom_type == "Polygon" else list(upper.geoms)):
        _flat(mb, dec["floor1"], g, l1 + 0.002, up=True, col=dec["fcol1"])
        _flat(mb, "Enduit", g, l1 - SLAB, up=False, col=COL_PLAFOND)
    _flat(mb, "Enduit", ip, ctop, up=False, col=COL_PLAFOND)
    # chants de la trémie (côté pièce et côté arrivée)
    ye = y_b
    Wbox("Enduit", (xr[0] + xr[1]) / 2, ye - s * 0.005, l1 - SLAB / 2, xr[1] - xr[0], 0.01, SLAB, col=COL_PLAFOND, faces=("-y", "+y"))
    xa = end + d * pl["run"]
    Wbox("Enduit", xa + d * 0.005, (band[0] + band[1]) / 2, l1 - SLAB / 2, 0.01, STAIR_W, SLAB, col=COL_PLAFOND, faces=("-x", "+x"))
    # poutres apparentes (selon le petit axe, tous les 70 cm)
    for zc, is_upper_slab in ((l1 - SLAB, True), (ctop, False)) if dec["beams"] else ():
        nb = int((L - 0.4) / 0.7)
        for k in range(nb + 1):
            x = -L / 2 + 0.2 + k * (L - 0.4) / max(nb, 1)
            y0, y1 = -W / 2 + 0.02, W / 2 - 0.02
            if is_upper_slab and hole_x[0] - 0.1 < x < hole_x[1] + 0.1:
                y0, y1 = (y0, y_b - 0.05) if s > 0 else (y_b + 0.05, y1)
            Wbox("BoisBrut", x, (y0 + y1) / 2, zc - 0.09, 0.14, y1 - y0, 0.18, col=dec["beams"], uv=1.0)

    # ---------- faces intérieures des murs extérieurs (percées des ouvertures)
    cs = np.array(ip.exterior.coords)
    if Polygon(cs).exterior.is_ccw is False:
        cs = cs[::-1]
    openings_w = pl["openings_world"]
    for fl, zb, zt, col in ((0, l0, l1 - SLAB, dec["wall0"]), (1, l1, ctop, dec["wall1"])):
        for i in range(len(cs) - 1):
            p0, p1 = cs[i], cs[i + 1]
            dv = p1 - p0
            Le = float(np.linalg.norm(dv))
            if Le < 0.05:
                continue
            u = dv / Le
            cuts = []
            for (Pin, ou, w, z0, z1) in openings_w:
                if abs(float(ou @ u)) < 0.95:
                    continue
                t = float((Pin - p0) @ u)
                dist = abs(float((Pin - p0) @ np.array([-u[1], u[0]])))
                if dist > 0.2 or t < -0.1 or t > Le + 0.1:
                    continue
                zz0, zz1 = max(z0, zb + 0.001), min(z1, zt - 0.001)
                if zz1 <= zz0:
                    continue
                t0, t1 = max(0.02, t - w / 2), min(Le - 0.02, t + w / 2)
                if t1 - t0 < 0.1:
                    continue
                cuts.append(sbox(Le - t1, zz0 if zz0 > zb + 0.02 else zb - 0.01, Le - t0, zz1))
            face = sbox(0.0, zb, Le, zt)
            if cuts:
                face = face.difference(unary_union(cuts))
            origin = np.array([p1[0], p1[1], 0.0])
            e1 = np.array([-u[0], -u[1], 0.0])
            for g in _polys(face):
                if g.area < 0.005:
                    continue
                planar_polygon(mb, "Enduit", np.array(g.exterior.coords)[:-1], [np.array(h.coords)[:-1] for h in g.interiors],
                               origin, e1, np.array([0, 0, 1.0]), lambda v2, P: np.stack([v2[:, 0] / 3.0, -v2[:, 1] / 3.0], -1), col)

    # ---------- escalier (marches pleines, girons en terre cuite, main courante)
    n, rise, tr = pl["n"], pl["rise"], TREAD
    ym = (band[0] + band[1]) / 2
    for i in range(n):
        x0 = end + d * i * tr
        xm = x0 + d * tr / 2
        top = l0 + (i + 1) * rise
        Wbox("Enduit", xm, ym, (l0 + top) / 2, tr, STAIR_W, top - l0 - 0.03, col=(236, 232, 224, 255))
        Wbox("TerreCuite", xm - d * 0.015, ym, top - 0.015, tr + 0.03, STAIR_W, 0.03, uv=0.3)
    yr = y_b - s * 0.04
    rail = []
    for i in range(0, n + 1, 3):
        x = end + d * min(i, n - 0.5) * tr
        zt = l0 + min(i + 1, n) * rise
        P = Wp(x, yr)
        tube(mb, "Fer", [(P[0], P[1], zt), (P[0], P[1], zt + 0.9)], 0.014, segs=6, col=(60, 55, 50, 255))
        rail.append((P[0], P[1], zt + 0.9))
    tube(mb, "BoisBrut", rail, 0.025, segs=6)

    # ---------- cloisons de l'étage (salle de bain) avec encadrement de porte
    x_lo, x_hi = sorted((end, xc))
    _partition(mb, Wp, yaw_a, (x_lo, y_b - s * PART / 2), (x_hi, y_b - s * PART / 2), l1, ctop, [], dec["wall1"])
    yo = -s * W / 2
    y_door = y_b - s * 0.6
    ya, yb2 = sorted((yo, y_b))
    _partition(mb, Wp, yaw_a, (xc, ya), (xc, yb2), l1, ctop, [(y_door, 0.85, 2.05)], dec["wall1"], along_y=True)

    # ---------- faïence murale de la salle de bain (1,25 m), interrompue aux portes et aux fenêtres
    bx0, bx1 = sorted((end, xc))
    by0, by1 = sorted((-s * W / 2, y_b - s * PART))
    side_band = "+y" if s > 0 else "-y"
    side_other = "-y" if s > 0 else "+y"
    side_end = "-x" if d > 0 else "+x"
    walls = [  # (côté, point de départ, point d'arrivée) dans le repère local, face tournée vers la pièce
        (side_other, (bx0, -s * W / 2 + s * 0.005), (bx1, -s * W / 2 + s * 0.005)),
        (side_band, (bx0, y_b - s * PART - s * 0.005), (bx1, y_b - s * PART - s * 0.005)),
        (side_end, (end + d * 0.005, by0), (end + d * 0.005, by1)),
        ("C", (xc - d * (PART / 2 + 0.005), by0), (xc - d * (PART / 2 + 0.005), by1)),
    ]
    y_door = y_b - s * 0.6
    for side, (ax, ay), (bxx, byy) in walls:
        along_x = abs(bxx - ax) > abs(byy - ay)
        lo, hi = (ax, bxx) if along_x else (ay, byy)
        cuts = []
        for lo_ in pl["locs"]:
            if lo_["floor"] == 1 and lo_["side"] == side and lo_["z0"] < l1 + 1.3:
                cuts.append((lo_["span"][0] - 0.05, lo_["span"][1] + 0.05))
        if side == "C":
            cuts.append((y_door - 0.5, y_door + 0.5))
        segs, cur = [], lo
        for c0, c1 in sorted(cuts):
            if c0 > cur:
                segs.append((cur, min(c0, hi)))
            cur = max(cur, c1)
        if cur < hi:
            segs.append((cur, hi))
        room_c = np.array(((bx0 + bx1) / 2, (by0 + by1) / 2))
        for a0, a1 in segs:
            if a1 - a0 < 0.1:
                continue
            if along_x:
                P0, P1 = Wp(a0, ay), Wp(a1, ay)
                inward = np.array([0.0, room_c[1] - ay])
            else:
                P0, P1 = Wp(ax, a0), Wp(ax, a1)
                inward = np.array([room_c[0] - ax, 0.0])
            nw = inward[0] * a + inward[1] * q
            nw = nw / (np.linalg.norm(nw) + 1e-9)
            L_ = a1 - a0
            yaw_w = math.atan2(P1[1] - P0[1], P1[0] - P0[0])
            Pc = (np.array(P0) + np.array(P1)) / 2 + nw * 0.008
            box(mb, "Faience", (Pc[0], Pc[1], l1 + 0.625), (L_, 0.012, 1.25), yaw=yaw_w, uv_scale=1.0, faces=("-y", "+y", "+z"))
            # frise de couronnement
            Pm = (np.array(P0) + np.array(P1)) / 2 + nw * 0.01
            box(mb, "Faience", (Pm[0], Pm[1], l1 + 1.265), (L_, 0.02, 0.03), yaw=math.atan2(P1[1] - P0[1], P1[0] - P0[0]),
                col=dec["frise"], uv_scale=1.0)

    # ---------- marches en pierre devant une porte plus haute que la rue
    for Pout, out, u, w, zg in pl.get("steps", []):
        hgt = l0 - zg
        ns = max(1, int(math.ceil(hgt / 0.17)))
        rs = hgt / ns
        yaw_e = math.atan2(u[1], u[0])
        for k in range(ns):
            top = l0 - k * rs
            dep = 0.32 * (k + 1)
            C = Pout + out * (dep / 2)
            box(mb, "PierreTaille", (C[0], C[1], (top + zg - 0.25) / 2), (w + 0.3, dep, top - zg + 0.25), yaw=yaw_e, uv_scale=3.0,
                faces=("+z", "-y", "+y", "-x", "+x"))

    # ---------- mobilier
    furnish(pl, inst, rng, Wp, yaw_a)
    b["visit_plan"] = dict(theme=dec["theme"], c=[float(c[0]), float(c[1])], a=[float(a[0]), float(a[1])], L=float(L), W=float(W), s=int(s), d=int(d),
                           end=float(end), xc=float(xc), run=float(pl["run"]), l0=float(l0), l1=float(l1), ctop=float(ctop),
                           band=[float(band[0]), float(band[1])])


def _polys(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon"]


def _partition(mb, Wp, yaw_a, p0, p1, zb, zt, doors, col, along_y=False):
    """Cloison de 10 cm entre p0 et p1 (repère local), percée de portes (centre, largeur, hauteur) avec encadrement."""
    if along_y:
        x = p0[0]
        s0, s1 = p0[1], p1[1]
    else:
        y = p0[1]
        s0, s1 = p0[0], p1[0]
    cuts = sorted((sc - w / 2, sc + w / 2, h) for sc, w, h in doors)
    segs = []
    cur = s0
    for a0, a1, h in cuts:
        segs.append((cur, a0, zb, zt))
        segs.append((a0, a1, zb + h, zt))
        cur = a1
    segs.append((cur, s1, zb, zt))
    for a0, a1, z0, z1 in segs:
        if a1 - a0 < 0.02 or z1 - z0 < 0.02:
            continue
        m = (a0 + a1) / 2
        if along_y:
            P = Wp(x, m)
            box(mb, "Enduit", (P[0], P[1], (z0 + z1) / 2), (PART, a1 - a0, z1 - z0), yaw=yaw_a, col=col, uv_scale=3.0)
        else:
            P = Wp(m, y)
            box(mb, "Enduit", (P[0], P[1], (z0 + z1) / 2), (a1 - a0, PART, z1 - z0), yaw=yaw_a, col=col, uv_scale=3.0)
    for a0, a1, h in cuts:
        for sgn in (-1, 1):
            for (m, lo, hi) in ((a0 - 0.035, zb, zb + h), (a1 + 0.035, zb, zb + h)):
                P = Wp(x + sgn * (PART / 2 + 0.01), m) if along_y else Wp(m, y + sgn * (PART / 2 + 0.01))
                sz = (0.02, 0.07, hi - lo) if along_y else (0.07, 0.02, hi - lo)
                box(mb, "BoisPeint", (P[0], P[1], (lo + hi) / 2), sz, yaw=yaw_a, col=(236, 230, 214, 255))
            P = Wp(x + sgn * (PART / 2 + 0.01), (a0 + a1) / 2) if along_y else Wp((a0 + a1) / 2, y + sgn * (PART / 2 + 0.01))
            sz = (0.02, a1 - a0 + 0.14, 0.07) if along_y else (a1 - a0 + 0.14, 0.02, 0.07)
            box(mb, "BoisPeint", (P[0], P[1], zb + h + 0.035), sz, yaw=yaw_a, col=(236, 230, 214, 255))


# ------------------------------------------------------------------ mobilier
class Placer:
    """Placement de meubles dos au mur dans des pièces rectangulaires (repère local), sans chevauchement."""

    def __init__(self, blocks, tall_blocks):
        self.blocks = list(blocks)          # rectangles interdits (x0, x1, y0, y1)
        self.tall = list(tall_blocks)       # interdits seulement aux meubles hauts (devant les fenêtres)

    @staticmethod
    def hit(r, o, m=0.0):
        return r[0] < o[1] + m and r[1] > o[0] - m and r[2] < o[3] + m and r[3] > o[2] - m

    def free(self, r, h):
        if any(self.hit(r, o) for o in self.blocks):
            return False
        if h > 1.0 and any(self.hit(r, o) for o in self.tall):
            return False
        return True

    def wall(self, room, side, name, pref=0.5, gap=0.03, extra=None):
        w, dd, h = SIZE[name]
        x0, x1, y0, y1 = room
        if side in ("+y", "-y"):
            lo, hi = x0 + w / 2 + 0.05, x1 - w / 2 - 0.05
        else:
            lo, hi = y0 + w / 2 + 0.05, y1 - w / 2 - 0.05
        if hi < lo:
            return None
        target = lo + (hi - lo) * pref
        cands = sorted(np.arange(lo, hi + 1e-6, 0.1), key=lambda v: abs(v - target))
        for p in cands:
            if side == "+y":
                r, cx, cy, yaw = (p - w / 2, p + w / 2, y1 - gap - dd, y1 - gap), p, y1 - gap - dd / 2, 0.0
            elif side == "-y":
                r, cx, cy, yaw = (p - w / 2, p + w / 2, y0 + gap, y0 + gap + dd), p, y0 + gap + dd / 2, math.pi
            elif side == "+x":
                r, cx, cy, yaw = (x1 - gap - dd, x1 - gap, p - w / 2, p + w / 2), x1 - gap - dd / 2, p, -math.pi / 2
            else:
                r, cx, cy, yaw = (x0 + gap, x0 + gap + dd, p - w / 2, p + w / 2), x0 + gap + dd / 2, p, math.pi / 2
            if self.free(r, h):
                self.blocks.append(r)
                return cx, cy, yaw, r
        return None

    def at(self, name, cx, cy, yaw, pad=0.0):
        w, dd, h = SIZE[name]
        if abs(math.sin(yaw)) > 0.7:
            w, dd = dd, w
        r = (cx - w / 2 - pad, cx + w / 2 + pad, cy - dd / 2 - pad, cy + dd / 2 + pad)
        if self.free(r, h):
            self.blocks.append(r)
            return r
        return None


# ------------------------------------------------------------------ variété : thème et décor de chaque maison
THEMES = {  # thème : poids
    "classique": 16, "salle_commune": 13, "bourgeoise": 12, "atelier": 11, "grand_mere": 12, "famille": 10, "refuge": 14, "saccagee": 12,
}
WALL_COLS = [(244, 238, 226), (238, 222, 186), (236, 214, 200), (214, 222, 232), (218, 228, 206), (228, 226, 220), (246, 232, 206)]
CIMENT_COLS = [(176, 70, 52), (60, 96, 150), (84, 120, 84), (196, 150, 60), (70, 70, 72), (150, 80, 110)]
PARQUET_COLS = [(255, 245, 230), (220, 196, 170), (170, 140, 115)]
BEAM_COLS = [(150, 120, 95), (110, 82, 62), (200, 186, 160), (236, 232, 222)]


def pick_decor(rng, style):
    """Décor d'une maison : sols, couleur des murs, poutres, faïence ; les maisons bourgeoises ont plus souvent parquet et ciment."""
    th_names = list(THEMES)
    w = np.array([THEMES[t] for t in th_names], float)
    if style in ("villa",):
        w[th_names.index("bourgeoise")] *= 2.0
    if style == "mas":
        w[th_names.index("salle_commune")] *= 1.8
        w[th_names.index("atelier")] *= 1.5
    theme = th_names[int(rng.choice(len(th_names), p=w / w.sum()))]
    f0 = rng.choice(["Tomettes", "CarreauxCiment", "Dallage", "Parquet"], p=[0.45, 0.25, 0.15, 0.15])
    if theme == "bourgeoise":
        f0 = rng.choice(["CarreauxCiment", "Parquet"])
    if theme == "atelier":
        f0 = "Dallage"
    f1 = rng.choice(["Tomettes", "Parquet", "CarreauxCiment"], p=[0.45, 0.4, 0.15])

    def fcol(m):
        if m == "CarreauxCiment":
            return CIMENT_COLS[rng.integers(len(CIMENT_COLS))] + (255,)
        if m == "Parquet":
            return PARQUET_COLS[rng.integers(len(PARQUET_COLS))] + (255,)
        return WHITE
    w0 = WALL_COLS[rng.integers(len(WALL_COLS))]
    w1 = WALL_COLS[rng.integers(len(WALL_COLS))] if rng.random() < 0.5 else w0
    beams = None if rng.random() < 0.15 else BEAM_COLS[rng.integers(len(BEAM_COLS))] + (255,)
    frise = [(60, 90, 140), (40, 110, 110), (170, 110, 40), (120, 60, 50), (70, 110, 70)][rng.integers(5)] + (255,)
    return dict(theme=theme, floor0=str(f0), floor1=str(f1), fcol0=fcol(f0), fcol1=fcol(f1), wall0=w0 + (255,), wall1=w1 + (255,),
                beams=beams, frise=frise)


def furnish(pl, inst, rng, Wp, yaw_a):
    L, W = pl["L"], pl["W"]
    s, d, end, xc, band, y_b = pl["s"], pl["d"], pl["end"], pl["xc"], pl["band"], pl["y_b"]
    l0, l1, ctop = pl["l0"], pl["l1"], pl["ctop"]
    theme = pl["decor"]["theme"]
    far = -end
    side_band = "+y" if s > 0 else "-y"
    side_other = "-y" if s > 0 else "+y"
    side_end = "-x" if d > 0 else "+x"
    side_far = "+x" if d > 0 else "-x"
    ALL = (side_other, side_far, side_band, side_end)
    run = pl["run"]
    xr = sorted((end, end + d * run))
    paint = PAINT[rng.integers(len(PAINT))]
    fabric = FABRIC[rng.integers(len(FABRIC))]
    fabric2 = FABRIC[rng.integers(len(FABRIC))]
    linen = LINEN[rng.integers(len(LINEN))]
    wreck = theme == "saccagee"
    abandoned = wreck or theme == "refuge" or (theme != "bourgeoise" and rng.random() < 0.4)

    def put(name, cx, cy, z, yaw, col=(255, 255, 255)):
        if wreck and SIZE.get(name, (0, 0, 9))[2] < 1.3 and name not in ("Int_Tapis", "Int_Cadre", "Int_Miroir", "Int_Suspension") and rng.random() < 0.6:
            # maison saccagée : les petits meubles sont déplacés et tournés
            cx, cy, yaw = cx + rng.normal(0, 0.15), cy + rng.normal(0, 0.15), yaw + rng.normal(0, 0.5)
        P = Wp(cx, cy)
        inst[name].append((P[0], P[1], z, yaw_a + yaw, 1.0, 1.0, 1.0, *col))

    def wall(P, room, sides, name, z, col=(255, 255, 255), pref=0.5):
        for sd in sides:
            got = P.wall(room, sd, name, pref=pref)
            if got:
                put(name, got[0], got[1], z, got[2], col)
                return got
        return None

    def blocks_for(floor):
        blocks, tall = [], []
        for lo in pl["locs"]:
            if lo["floor"] != floor or lo["side"] is None:
                continue
            a0, a1 = lo["span"]
            if lo["door"] or lo["type"].startswith("PorteFenetre") or "Porte" in lo["type"] or "Remise" in lo["type"]:
                blocks.append(_front_rect(lo["side"], a0 - 0.25, a1 + 0.25, 1.1, L, W))
            else:
                tall.append(_front_rect(lo["side"], a0 - 0.1, a1 + 0.1, 0.4, L, W))
        return blocks, tall

    def table_with_chairs(P, room, table, n_chairs, z, col, lamp=True):
        """Table au centre de la pièce, chaises autour (si elles tiennent)."""
        w_, d_, _ = SIZE[table]
        cx0, cy0 = (room[0] + room[1]) / 2, (room[2] + room[3]) / 2
        for dx in (0.0, -0.3, 0.3, -0.6, 0.6):
            for dy in (0.0, -0.3, 0.3):
                tx, ty = cx0 + dx, cy0 + dy
                if P.free((tx - w_ / 2 - 0.1, tx + w_ / 2 + 0.1, ty - d_ / 2 - 0.45, ty + d_ / 2 + 0.45), 0.8):
                    P.blocks.append((tx - w_ / 2, tx + w_ / 2, ty - d_ / 2, ty + d_ / 2))
                    put(table, tx, ty, z, 0.0, col)
                    if lamp:
                        put("Int_Suspension", tx, ty, (l1 - SLAB if z < l1 - 0.5 else ctop) - 0.18, 0.0)
                    per_side = max(1, n_chairs // 2)
                    for k in range(n_chairs):
                        side = -1 if k < per_side else 1
                        j = k % per_side
                        cx = tx - w_ / 2 + (j + 0.5) * w_ / per_side
                        cy = ty + side * (d_ / 2 + 0.23)
                        yaw = math.pi if side < 0 else 0.0
                        if (abandoned and rng.random() < 0.18) or (wreck and rng.random() < 0.4):
                            if P.at("Int_ChaiseRenversee", cx, cy + side * 0.4, yaw + 0.4):
                                put("Int_ChaiseRenversee", cx, cy + side * 0.4, z, yaw + rng.normal(0.4, 0.6))
                            continue
                        if P.at("Int_Chaise", cx, cy, yaw):
                            put("Int_Chaise", cx, cy, z, yaw)
                    return tx, ty
        return None

    def hang(room, floor, z, n, names=("Int_Cadre",)):
        """Tableaux et miroirs aux murs, à l'écart des portes et fenêtres (au-dessus des meubles bas)."""
        blocks, tall = blocks_for(floor)
        Pw = Placer(blocks + tall, [])
        for k in range(n):
            nm = names[k % len(names)]
            wall(Pw, room, [ALL[(k + int(rng.integers(4))) % 4]], nm, z, pref=float(rng.uniform(0.2, 0.8)))

    # ================= rez-de-chaussée
    blocks, tall = blocks_for(0)
    blocks.append((xr[0] - 0.05, xr[1] + 0.05, band[0] - 0.05, band[1] + 0.05))                # escalier
    appr = (min(end, end + d * 1.1), max(end, end + d * 1.1), *sorted((y_b, y_b - s * 0.9)))   # départ de l'escalier
    blocks.append(appr)
    P = Placer(blocks, tall)
    kx = sorted((far, far - d * 3.1))
    room_k = (kx[0], kx[1], -W / 2, W / 2)
    sx_ = sorted((end, far - d * 3.1))
    room_s = (sx_[0], sx_[1], -W / 2, W / 2)
    room_all = (-L / 2, L / 2, -W / 2, W / 2)
    pref_far = 1.0 if d > 0 else 0.0

    def kitchen(room, rustic=False):
        if rustic:
            wall(P, room, (side_other, side_far, side_band), "Int_EvierPierre", l0, pref=pref_far)
            wall(P, room, (side_far, side_band, side_other), "Int_Petrin", l0)
        else:
            got = wall(P, room, (side_other, side_far, side_band), "Int_PlanTravail", l0, paint, pref=pref_far)
            if got:
                cx, cy, yaw, _ = got
                for off in (1.55, -1.55):
                    fx, fy = (cx + off, cy) if yaw in (0.0, math.pi) else (cx, cy + off)
                    if P.at("Int_Frigo", fx, fy, yaw):
                        put("Int_Frigo", fx, fy, l0, yaw)
                        break
        wall(P, room, (side_far, side_other, side_band), "Int_Buffet", l0, paint)

    def fireplace_corner(room, stove=False, sofa=True):
        name = "Int_Poele" if stove else "Int_Cheminee"
        got = (wall(P, room, (side_other,), name, l0) if room[1] - room[0] > 3.0 else None) or wall(P, room, (side_end, side_band), name, l0)
        if got and sofa:
            fx, fy, fyaw, _ = got
            nx, ny = -math.sin(fyaw), math.cos(fyaw)
            cx, cy = fx - nx * 2.5, fy - ny * 2.5
            if P.at("Int_Canape", cx, cy, fyaw + math.pi):
                put("Int_Canape", cx, cy, l0, fyaw + math.pi, linen)
                tx, ty = fx - nx * 1.45, fy - ny * 1.45
                if P.at("Int_TableBasse", tx, ty, fyaw):
                    put("Int_TableBasse", tx, ty, l0, fyaw)
                    put("Int_Tapis", tx, ty, l0, fyaw, fabric2)
                ax, ay = tx + ny * 1.3, ty - nx * 1.3
                if P.at("Int_Fauteuil", ax, ay, fyaw - math.pi / 2):
                    put("Int_Fauteuil", ax, ay, l0, fyaw - math.pi / 2, linen)
        return got

    if theme in ("classique", "famille", "saccagee"):
        kitchen(room_k)
        table_with_chairs(P, room_k, "Int_TableCuisine", 4, l0, fabric)
        fireplace_corner(room_s)
        wall(P, room_s, (side_band, side_other), "Int_Bibliotheque", l0)
        if theme == "famille":
            wall(P, room_s, (side_end, side_band), "Int_Plante", l0)
        hang(room_s, 0, l0, 2)
    elif theme == "salle_commune":
        # une seule grande pièce : cheminée, grande table rustique, évier en pierre, pétrin, horloge
        kitchen(room_k, rustic=True)
        table_with_chairs(P, room_all, "Int_TableManger", 6, l0, (255, 255, 255))
        fireplace_corner(room_s, sofa=False)
        wall(P, room_s, (side_band, side_other, side_end), "Int_Horloge", l0, paint)
        wall(P, room_all, (side_band, side_other), "Int_EtagereBocaux", l0)
        hang(room_all, 0, l0, 1)
    elif theme == "bourgeoise":
        # salle à manger + salon (piano, horloge, lampadaire)
        table_with_chairs(P, room_k, "Int_TableManger", 6, l0, (255, 255, 255))
        wall(P, room_k, (side_far, side_other, side_band), "Int_Buffet", l0, paint)
        fireplace_corner(room_s)
        wall(P, room_s, (side_band, side_other, side_end), "Int_Piano", l0)
        wall(P, room_s, (side_band, side_other, side_end), "Int_Horloge", l0, paint)
        wall(P, room_s, (side_other, side_band), "Int_Bibliotheque", l0)
        wall(P, room_s, (side_end, side_other, side_band), "Int_Lampadaire", l0)
        wall(P, room_s, (side_end, side_band), "Int_Plante", l0)
        hang(room_all, 0, l0, 3, ("Int_Cadre", "Int_Cadre", "Int_Miroir"))
    elif theme == "atelier":
        # rez-de-chaussée en atelier et cave : établi, outils, tonneaux, bouteilles
        wall(P, room_k, (side_far, side_other, side_band), "Int_Etabli", l0)
        wall(P, room_k, (side_other, side_band, side_far), "Int_EtagereOutils", l0)
        wall(P, room_s, (side_other, side_band), "Int_CasierBouteilles", l0)
        wall(P, room_s, (side_other, side_band), "Int_EtagereBocaux", l0)
        for k in range(3):
            wall(P, room_s, (side_other, side_end, side_band), "Int_Tonneau", l0, pref=float(rng.random()))
        for k in range(int(rng.integers(2, 5))):
            wall(P, room_all, ALL, "Int_Carton", l0, pref=float(rng.random()))
        wall(P, room_all, ALL, "Int_Malle", l0, pref=float(rng.random()))
    elif theme == "grand_mere":
        kitchen(room_k)
        table_with_chairs(P, room_k, "Int_TableCuisine", 2, l0, fabric)
        fireplace_corner(room_s, stove=True, sofa=False)
        for k in range(2):
            wall(P, room_s, (side_other, side_band, side_end), "Int_Fauteuil", l0, linen, pref=0.3 + 0.4 * k)
        wall(P, room_s, (side_band, side_other), "Int_MachineCoudre", l0)
        wall(P, room_s, (side_band, side_other, side_end), "Int_Horloge", l0, paint)
        for k in range(2):
            wall(P, room_all, ALL, "Int_Plante", l0, pref=float(rng.random()))
        put("Int_Tapis", (room_s[0] + room_s[1]) / 2, 0.0, l0, 0.0, fabric2)
        hang(room_all, 0, l0, 4, ("Int_Cadre", "Int_Cadre", "Int_Miroir"))
    elif theme == "refuge":
        # refuge de survivants : cuisine de fortune, réserves, couchages au sol
        wall(P, room_k, (side_other, side_far, side_band), "Int_Rechaud", l0)
        table_with_chairs(P, room_k, "Int_TableCuisine", 2, l0, fabric, lamp=False)
        for k in range(2):
            wall(P, room_k, (side_far, side_band, side_other), "Int_Conserves", l0, pref=float(rng.random()))
        for k in range(int(rng.integers(2, 5))):
            wall(P, room_all, ALL, "Int_Jerrican", l0, pref=float(rng.random()))
        for k in range(2):
            wall(P, room_s, (side_other, side_band, side_end), "Int_Matelas", l0, pref=float(rng.random()))
        for k in range(int(rng.integers(1, 3))):
            got = P.at("Int_SacCouchage", (room_s[0] + room_s[1]) / 2 + rng.normal(0, 0.4), rng.normal(0, 0.3), rng.uniform(0, 3.14))
            if got:
                put("Int_SacCouchage", (got[0] + got[1]) / 2, (got[2] + got[3]) / 2, l0, float(rng.uniform(0, 3.14)))
        wall(P, room_s, (side_band, side_other), "Int_EtagereBocaux", l0)
        wall(P, room_all, ALL, "Int_Malle", l0, pref=float(rng.random()))
    if abandoned:
        for k in range(int(rng.integers(1, 4))):
            wall(P, room_s if k % 2 else room_k, (ALL[int(rng.integers(4))],), "Int_Carton", l0, pref=float(rng.random()))
    if wreck:
        # traces de lutte : sang au sol, gravats
        for k in range(int(rng.integers(1, 3))):
            x = rng.uniform(-L / 2 + 0.8, L / 2 - 0.8)
            y = rng.uniform(-W / 2 + 0.6, W / 2 - 0.6)
            if not (xr[0] - 0.2 < x < xr[1] + 0.2 and band[0] - 0.2 < y < band[1] + 0.2):
                put(("Z_Sol_sang_1", "Z_Sol_sang_2", "Z_Sol_sang_flaque", "Z_Sol_sang_trainee")[int(rng.integers(4))], x, y, l0 + 0.005,
                    float(rng.uniform(0, 6.28)))

    # ================= étage : salle de bain + chambre (ou bureau, chambre d'enfants, dortoir...)
    blocks, tall = blocks_for(1)
    hole = (min(end, end + d * run) - 0.2, max(end, end + d * run) + 0.2, band[0] - 0.05, band[1] + 0.05)
    blocks.append(hole)
    arr = sorted((end + d * run, end + d * (run + 1.0)))
    blocks.append((arr[0], arr[1], band[0] - 0.1, band[1]))
    y_door = y_b - s * 0.6
    blocks.append((xc - 0.9, xc + 0.9, y_door - 0.5, y_door + 0.5))
    P = Placer(blocks, tall)
    bx = sorted((end, xc))
    by = sorted((-s * W / 2, y_b - s * PART))
    room_b = (bx[0] + 0.02, bx[1] - PART / 2, by[0], by[1])
    bath_w = by[1] - by[0]
    got = P.wall(room_b, side_end, "Int_Baignoire") if bath_w >= 1.75 else None
    got = got or P.wall(room_b, side_other, "Int_Baignoire", pref=0.0 if d > 0 else 1.0)
    if got:
        put("Int_Baignoire", got[0], got[1], l1, got[2])
    got = P.wall(room_b, side_other, "Int_WC", pref=1.0 if d > 0 else 0.0) or P.wall(room_b, "+x" if d < 0 else "-x", "Int_WC")
    if got:
        put("Int_WC", got[0], got[1], l1, got[2])
    got = wall(P, room_b, (side_band, side_other), "Int_Lavabo", l1, paint)
    if got:
        # miroir au-dessus du lavabo
        put("Int_Miroir", got[0] - math.sin(got[2]) * 0.21, got[1] + math.cos(got[2]) * 0.21, l1 - 0.35, got[2])
    wall(P, room_b, (side_band,), "Int_Commode", l1, pref=0.2 if d > 0 else 0.8)
    rx = sorted((xc, far))
    room_r = (rx[0] + PART / 2 + 0.02, rx[1], -W / 2, W / 2)
    upper = {"classique": "parents", "saccagee": "parents", "salle_commune": "parents", "bourgeoise": "parents", "grand_mere": "grand_mere",
             "famille": "enfants", "atelier": "bureau", "refuge": "dortoir"}[theme]
    if upper == "enfants" and W < 3.0:
        upper = "parents"
    if upper in ("parents", "grand_mere"):
        double = W >= 3.2
        bed = "Int_LitDouble" if double else "Int_LitSimple"
        got = wall(P, room_r, (side_far, side_other, side_band), bed, l1, fabric, pref=0.5)
        if got:
            bx_, by_, byaw, br = got
            wbed = SIZE[bed][0]
            tx, ty = math.cos(byaw), math.sin(byaw)
            nx, ny = -math.sin(byaw), math.cos(byaw)
            hb = SIZE[bed][1] / 2 - 0.2
            for sg in (-1, 1):
                cx = bx_ + tx * sg * (wbed / 2 + 0.3) + nx * hb
                cy = by_ + ty * sg * (wbed / 2 + 0.3) + ny * hb
                if P.at("Int_Chevet", cx, cy, byaw):
                    put("Int_Chevet", cx, cy, l1, byaw)
            put("Int_Tapis", bx_ - nx * 0.2, by_ - ny * 0.2, l1, byaw, fabric2)
        wall(P, room_r, (side_other, side_band, side_far), "Int_Armoire", l1)
        wall(P, room_r, (side_band, side_other), "Int_Commode", l1)
        if upper == "grand_mere":
            wall(P, room_r, (side_other, side_band, side_far), "Int_Malle", l1)
            wall(P, room_r, (side_band, side_other), "Int_Fauteuil", l1, linen)
        else:
            wall(P, room_r, (side_other, side_band), "Int_Chaise", l1, pref=0.2)
        hang(room_r, 1, l1, 2 if upper == "parents" else 3, ("Int_Cadre", "Int_Miroir", "Int_Cadre"))
    elif upper == "enfants":
        wall(P, room_r, (side_far, side_other, side_band), "Int_LitsEnfants", l1, fabric)
        wall(P, room_r, (side_other, side_band), "Int_Bureau", l1)
        wall(P, room_r, (side_band, side_other), "Int_Commode", l1, paint)
        wall(P, room_r, ALL, "Int_Malle", l1, paint, pref=float(rng.random()))
        hang(room_r, 1, l1, 2)
    elif upper == "bureau":
        wall(P, room_r, (side_far, side_other, side_band), "Int_LitSimple", l1, fabric)
        wall(P, room_r, (side_other, side_band), "Int_Bureau", l1)
        wall(P, room_r, (side_band, side_other), "Int_Bibliotheque", l1)
        wall(P, room_r, (side_other, side_band), "Int_Armoire", l1)
        hang(room_r, 1, l1, 1)
    else:  # dortoir de survivants
        for k in range(3):
            wall(P, room_r, (side_far, side_other, side_band), "Int_Matelas", l1, pref=float(rng.random()))
        wall(P, room_r, (side_band, side_other), "Int_EtagereBocaux", l1)
        for k in range(int(rng.integers(1, 4))):
            wall(P, room_r, ALL, "Int_Jerrican", l1, pref=float(rng.random()))
        wall(P, room_r, ALL, "Int_Conserves", l1, pref=float(rng.random()))
    if abandoned:
        wall(P, room_r, ((side_other, side_band)[int(rng.integers(2))],), "Int_Carton", l1, pref=float(rng.random()))


def _front_rect(side, a0, a1, depth, L, W):
    if side == "+y":
        return (a0, a1, W / 2 - depth, W / 2)
    if side == "-y":
        return (a0, a1, -W / 2, -W / 2 + depth)
    if side == "+x":
        return (L / 2 - depth, L / 2, a0, a1)
    return (-L / 2, -L / 2 + depth, a0, a1)
