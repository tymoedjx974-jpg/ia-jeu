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
DOOR_TYPES = ("Porte", "Porte_Simple", "Remise", "Vitrine", "Vitrine_SansStore")
PAINT = [(96, 132, 160), (122, 150, 128), (170, 186, 170), (214, 204, 170), (120, 140, 170), (150, 170, 190), (196, 120, 90)]
FABRIC = [(222, 176, 64), (70, 104, 160), (176, 64, 50), (120, 136, 70), (206, 150, 60), (90, 120, 150)]
REJECT = collections.Counter()   # raisons de refus des maisons candidates (diagnostic)
LINEN = [(236, 226, 204), (212, 196, 170), (190, 170, 140), (160, 170, 150)]


# ------------------------------------------------------------------ sélection
def candidates(blds, center, max_n=340, spacing=9.0):
    """Bâtiments à ouvrir : maisons presque rectangulaires (à étage ou de plain-pied), commerces et mairie."""
    out = []
    for b in blds:
        if b["style"] not in ("core", "faubourg", "mas", "villa"):
            continue
        public = bool(b.get("shop") or b.get("mairie"))
        p = b["poly"]
        if not ((22 if public else 34) <= p.area <= (380 if public else 240)):
            continue
        r = p.minimum_rotated_rectangle
        if p.area / max(r.area, 1e-6) < (0.5 if public else 0.86):
            continue
        _, _, Lm, Wm = b["ombr"]
        if public:
            if Lm < 4.5 or Wm < 3.4:
                continue
        elif Lm < (7.0 if b["nf"] == 1 else 7.4) or Wm < 3.9:
            continue
        out.append(b)
    pri = {"core": 0, "faubourg": 1, "villa": 2, "mas": 2}
    # commerces et mairie d'abord (ils sont peu nombreux), puis les maisons du centre vers l'extérieur
    # (les maisons hautes et larges passent avant : ce sont elles qui peuvent avoir un 2e étage avec colimaçon)
    out.sort(key=lambda b: (0 if (b.get("shop") or b.get("mairie")) else 1,
                            0 if (b["nf"] >= 3 and b["ombr"][3] >= 4.6) else 1, pri[b["style"]], b["poly"].centroid.distance(center)))
    chosen = []
    for b in out:
        c = b["poly"].centroid
        public = b.get("shop") or b.get("mairie")
        if public or all(c.distance(o["poly"].centroid) > spacing for o in chosen if not (o.get("shop") or o.get("mairie"))):
            chosen.append(b)
        if len(chosen) >= max_n:
            break
    for b in chosen:
        b["visit_cand"] = True
    return chosen


# ------------------------------------------------------------------ plan
SPIRAL = 1.8       # emprise de l'escalier en colimaçon (carré, m)


def plan(b, info, openings, gz):
    """Étudie le bâtiment ; renvoie le plan de l'intérieur, ou None s'il ne se prête pas à un intérieur simple.
    Trois sortes : maison à étage(s) (escalier droit, parfois colimaçon vers un 2e étage), maison de plain-pied,
    commerce ou mairie (rez-de-chaussée seulement)."""
    public = bool(b.get("shop") or b.get("mairie"))
    kind = "commerce" if public else ("plainpied" if b["nf"] == 1 else "maison")
    rng = b["rng"]
    p = b["poly"]
    ip = p.buffer(-T_WALL, join_style=2)
    if ip.geom_type != "Polygon" or ip.area < (12 if public else 20):
        REJECT[kind + ":forme"] += 1
        return None
    ip = ip.simplify(0.02)
    c, a, L, W = ombr(ip)
    rect_ratio = ip.area / (L * W)
    if rect_ratio < (0.5 if public else 0.92):
        REJECT[kind + ":pas rectangulaire"] += 1
        return None
    q = np.array([-a[1], a[0]])
    fh = b["fh"]
    l0 = b["zref"]
    lv = [l0 + sum(fh[:k]) for k in range(len(fh) + 1)]      # niveaux des planchers (et du dessus du dernier)
    nlev = 1
    if kind == "maison":
        nlev = 3 if (b["nf"] >= 3 and L >= 8.0 and W >= 3.7 and rng.random() < 0.85) else 2
    top = lv[nlev] - (0.05 if b["nf"] == nlev else SLAB)       # plafond du dernier niveau ouvert
    l1 = lv[1]
    ctop = top if nlev <= 2 else lv[2] - SLAB                   # plafond de l'étage 1
    n = int(math.ceil(fh[0] / RISE_MAX))
    rise = fh[0] / n
    run = n * TREAD
    if kind == "maison" and (L < run + 2.7 or W < STAIR_W + PART + 1.75):
        REJECT[kind + ":trop petite"] += 1
        return None
    if kind == "plainpied" and L < 7.0:
        REJECT[kind + ":trop petite"] += 1
        return None
    # le terrain ne doit pas traverser le plancher
    xs = np.linspace(-L / 2 + 0.2, L / 2 - 0.2, 7)
    ys = np.linspace(-W / 2 + 0.2, W / 2 - 0.2, 4)
    pts = [pt for pt in (c + x * a + y * q for x in xs for y in ys) if ip.contains(Point(*pt))] or [c]
    if max(gz(pt[0], pt[1]) for pt in pts) > l0 - 0.05:
        REJECT[kind + ":terrain"] += 1
        return None

    def to_local(P):
        d = np.asarray(P) - c
        return float(d @ a), float(d @ q)

    # ouvertures dans le repère local ; niveau = nombre de planchers franchis
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
        floor = sum(1 for z in lv[1:-1] if o["z0"] >= z - 0.6)
        is_door = o["type"] in DOOR_TYPES
        locs.append(dict(i=idx, side=side, span=span, z0=o["z0"], z1=o["z1"], floor=floor, door=is_door, type=o["type"]))
    doors = [d for d in locs if d["door"] and d["floor"] == 0 and d["side"] and -0.8 <= d["z0"] - l0 <= 0.45]
    if not doors:
        REJECT[kind + ":porte"] += 1
        return None
    main = min(doors, key=lambda d: abs(d["z0"] - l0))
    ip_local = Polygon([to_local(P_) for P_ in np.array(ip.exterior.coords)])
    base = dict(kind=kind, nlev=nlev, lv=lv, c=c, a=a, q=q, L=L, W=W, ip=ip, ip_local=ip_local, rect=rect_ratio >= 0.9, l0=l0, l1=l1,
                ctop=ctop, top=top, locs=locs, main=main)

    def overlaps(a0, a1, b0, b1, m=0.0):
        return a0 < b1 + m and a1 > b0 - m

    def wall_free(side, lo, hi, floor, m=0.15):
        return not any(o["floor"] == floor and o["side"] == side and overlaps(*o["span"], lo, hi, m) for o in locs)

    if kind == "commerce":
        # arrière-boutique quand on entre par un petit côté et que la boutique est assez profonde
        back = None
        if main["side"] in ("+x", "-x") and L >= 7.0 and rect_ratio >= 0.85:
            sgn = 1 if main["side"] == "+x" else -1
            xp = -sgn * (L / 2 - 2.3)
            if wall_free("+y", xp - 0.1, xp + 0.1, 0) and wall_free("-y", xp - 0.1, xp + 0.1, 0):
                back = dict(x=xp, sgn=sgn, door_y=float(rng.choice([-1, 1])) * (W / 2 - 0.75))
        return dict(base, back=back)
    if kind == "plainpied":
        # pièces en enfilade le long du grand axe : séjour-cuisine (côté entrée), chambre, salle de bain
        ent = (main["span"][0] + main["span"][1]) / 2 if main["side"] in ("+y", "-y") else (L / 2 if main["side"] == "+x" else -L / 2)
        d = -1 if ent > 0 else 1                    # on s'éloigne de l'entrée
        start = d * -L / 2
        la = max(3.3, L * 0.48)
        lb = max(2.6, (L - la) * 0.6)
        if L - la - lb < 1.7:
            lb = L - la - 1.7
        cuts = []
        for x_ in (start + d * la, start + d * (la + lb)):
            best = None
            for dx in (0, 0.2, -0.2, 0.4, -0.4, 0.6, -0.6):
                xp = x_ + dx
                if wall_free("+y", xp - 0.1, xp + 0.1, 0) and wall_free("-y", xp - 0.1, xp + 0.1, 0):
                    best = xp
                    break
            if best is None:
                REJECT[kind + ":cloisons"] += 1
                return None
            cuts.append(best)
        sd = float(rng.choice([-1, 1]))
        return dict(base, d=d, start=start, cuts=cuts, door_y=sd * (W / 2 - 0.7))

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
        REJECT[kind + ":escalier"] += 1
        return None
    spiral = None
    if nlev == 3:
        # colimaçon dans un angle de la chambre (au fond), sinon contre la cloison de la salle de bain, côté mur plein
        far = -best["end"]
        dd, ss = best["d"], best["s"]

        def pl_lv(f):
            return lv[f]
        cands = []
        sx = far - dd * (SPIRAL / 2 + 0.02)
        for sy in (ss * (W / 2 - SPIRAL / 2 - 0.02), -ss * (W / 2 - SPIRAL / 2 - 0.02)):
            cands.append((sx, sy, -dd, -(1.0 if sy > 0 else -1.0), True))
        sx2 = best["xc"] + dd * (PART / 2 + SPIRAL / 2 + 0.03)
        sy2 = -ss * (W / 2 - SPIRAL / 2 - 0.02)
        cands.append((sx2, sy2, dd, -(1.0 if sy2 > 0 else -1.0), False))
        for sx_, sy_, dxr, dyr, corner in cands:
            side_y = "+y" if sy_ > 0 else "-y"
            side_x = "+x" if sx_ > 0 else "-x"
            walls_ = [(side_y, sx_ - SPIRAL / 2, sx_ + SPIRAL / 2)] + ([(side_x, sy_ - SPIRAL / 2, sy_ + SPIRAL / 2)] if corner else [])
            # une fenêtre derrière l'escalier est acceptée (on la voit entre les marches), pas une porte-fenêtre
            if not any(o["floor"] in (1, 2) and o["side"] == sd_ and overlaps(*o["span"], lo_, hi_, 0.05)
                       and ("Porte" in o["type"] or o["z0"] < pl_lv(o["floor"]) + 0.5)
                       for sd_, lo_, hi_ in walls_ for o in locs):
                spiral = (sx_, sy_, dxr, dyr)
                break
        if spiral is None or abs(far - best["xc"]) < SPIRAL + 2.4:
            REJECT["maison:pas de colimaçon"] += 1
            base.update(nlev=2, top=lv[2] - (0.05 if b["nf"] == 2 else SLAB))
            base["ctop"] = base["top"]
            spiral = None
    return dict(base, n=n, rise=rise, run=run, spiral=spiral, **best)


def apply_openings(b, pl, openings, info):
    """Ouvre le bâtiment : porte(s) d'entrée au niveau du sol intérieur, fenêtres sans vitre sur les niveaux aménagés."""
    l0 = pl["l0"]
    steps = []
    for lo in pl["locs"]:
        o = openings[lo["i"]]
        if lo["floor"] < pl["nlev"] and o["type"] in VISIT:
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
    if pl["kind"] != "maison":
        return build_rdc(b, pl, mb, inst, rng)
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
        _flat(mb, dec["wall_mat"], g, l1 - SLAB, up=False, col=COL_PLAFOND)
    if pl["spiral"]:
        # 2e étage (grenier ou chambre) desservi par un escalier en colimaçon : 3/4 de tour de marches,
        # le quart restant (côté pièce) sert de palier en haut et d'accès en bas
        l2 = pl["lv"][2]
        sx, sy, dx_, dy_ = pl["spiral"]                              # centre, direction de la pièce
        lx, ly = sx + dx_ * SPIRAL / 4, sy + dy_ * SPIRAL / 4        # centre du palier (quart de l'emprise)
        sq = rect_world(sx - SPIRAL / 2, sx + SPIRAL / 2, sy - SPIRAL / 2, sy + SPIRAL / 2)
        landing = rect_world(lx - SPIRAL / 4, lx + SPIRAL / 4, ly - SPIRAL / 4, ly + SPIRAL / 4)
        sh = sq.difference(landing).intersection(ip.buffer(0.01))
        up2 = ip.difference(sh)
        for g in _polys(up2):
            _flat(mb, dec["wall_mat"], g, ctop, up=False, col=COL_PLAFOND)
            _flat(mb, dec["floor2"], g, l2 + 0.002, up=True, col=dec["fcol2"])
        _flat(mb, dec["wall_mat"], ip, pl["top"], up=False, col=COL_PLAFOND)
        delta = math.atan2(dy_, dx_)
        spiral_stair(mb, Wp(sx, sy), l1, l2, yaw_a + delta + math.pi / 4)
        # garde-corps du palier au-dessus des premières marches
        ang_first = delta + math.pi / 4                              # direction (locale) des premières marches
        ex, ey = math.cos(ang_first), math.sin(ang_first)
        p0 = Wp(sx, sy)
        p1 = Wp(sx + ex * SPIRAL / 2, sy + ey * SPIRAL / 2)
        tube(mb, "BoisBrut", [(p0[0], p0[1], l2 + 0.95), (p1[0], p1[1], l2 + 0.95)], 0.025, segs=6)
        for t_ in np.linspace(0.1, 1, 5):
            pp = p0 + (p1 - p0) * t_
            tube(mb, "Fer", [(pp[0], pp[1], l2), (pp[0], pp[1], l2 + 0.95)], 0.012, segs=5, col=(60, 55, 50, 255))
    else:
        _flat(mb, dec["wall_mat"], ip, ctop, up=False, col=COL_PLAFOND)
    # chants de la trémie (côté pièce et côté arrivée)
    ye = y_b
    Wbox("Enduit", (xr[0] + xr[1]) / 2, ye - s * 0.005, l1 - SLAB / 2, xr[1] - xr[0], 0.01, SLAB, col=COL_PLAFOND, faces=("-y", "+y"))
    xa = end + d * pl["run"]
    Wbox("Enduit", xa + d * 0.005, (band[0] + band[1]) / 2, l1 - SLAB / 2, 0.01, STAIR_W, SLAB, col=COL_PLAFOND, faces=("-x", "+x"))
    # poutres apparentes (selon le petit axe, tous les 70 cm)
    slabs = [(l1 - SLAB, "volee"), (ctop, "colimacon" if pl["spiral"] else None)] + ([(pl["top"], None)] if pl["spiral"] else [])
    for zc, cut in slabs if dec["beams"] else ():
        nb = int((L - 0.4) / 0.7)
        for k in range(nb + 1):
            x = -L / 2 + 0.2 + k * (L - 0.4) / max(nb, 1)
            y0, y1 = -W / 2 + 0.02, W / 2 - 0.02
            if cut == "volee" and hole_x[0] - 0.1 < x < hole_x[1] + 0.1:
                y0, y1 = (y0, y_b - 0.05) if s > 0 else (y_b + 0.05, y1)
            if cut == "colimacon" and abs(x - pl["spiral"][0]) < SPIRAL / 2 + 0.1:
                sy_ = pl["spiral"][1]
                y0, y1 = (y0, sy_ - SPIRAL / 2 - 0.05) if sy_ > 0 else (sy_ + SPIRAL / 2 + 0.05, y1)
            Wbox("BoisBrut", x, (y0 + y1) / 2, zc - 0.09, 0.14, y1 - y0, 0.18, col=dec["beams"], uv=1.0)

    # ---------- faces intérieures des murs extérieurs (percées des ouvertures)
    bands = [(l0, l1 - SLAB, dec["wall0"]), (l1, ctop, dec["wall1"])]
    if pl["nlev"] == 3:
        bands.append((pl["lv"][2], pl["top"], dec["wall2"]))
    _inner_walls(mb, ip, pl["openings_world"], bands, dec["wall_mat"])

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
    _partition(mb, Wp, yaw_a, (x_lo, y_b - s * PART / 2), (x_hi, y_b - s * PART / 2), l1, ctop, [], dec["wall1"], mat=dec["wall_mat"])
    yo = -s * W / 2
    y_door = y_b - s * 0.6
    ya, yb2 = sorted((yo, y_b))
    _partition(mb, Wp, yaw_a, (xc, ya), (xc, yb2), l1, ctop, [(y_door, 0.85, 2.05)], dec["wall1"], along_y=True, mat=dec["wall_mat"])

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
    b["visit_plan"] = dict(theme=dec["theme"], kind="maison", levels=int(pl["nlev"]), entree=_entree(pl), lv=[float(z) for z in pl["lv"]],
                           spiral=[float(v) for v in pl["spiral"]] if pl["spiral"] else None, top=float(pl["top"]), c=[float(c[0]), float(c[1])], a=[float(a[0]), float(a[1])], L=float(L), W=float(W), s=int(s), d=int(d),
                           end=float(end), xc=float(xc), run=float(pl["run"]), l0=float(l0), l1=float(l1), ctop=float(ctop),
                           band=[float(band[0]), float(band[1])])


# ------------------------------------------------------------------ plain-pied, commerces, mairie (un seul niveau)
SHOP_TYPE = {  # enseigne -> aménagement
    "boulangerie": "boulangerie", "boucherie": "boucherie", "glaces": "glacier",
    "cafe1": "cafe", "cafe2": "cafe", "bar": "cafe", "pizzeria": "restaurant", "cave": "cave",
    "epicerie": "epicerie", "produits": "epicerie", "vins": "cave",
    "pharmacie": "pharmacie", "beaute": "pharmacie", "savons": "boutique_savons", "coiffure": "coiffeur",
    "galerie": "galerie", "atelier": "galerie", "musee": "galerie", "santons": "boutique_santons", "poterie": "boutique_poterie",
    "boutique": "boutique_santons", "poste": "accueil", "tourisme": "accueil", "mediatheque": "accueil", "hotel": "accueil",
    "hotel2": "accueil", "chambres": "accueil",
}
for _k in range(1, 9):
    SHOP_TYPE[f"restaurant{_k}"] = "restaurant"


def build_rdc(b, pl, mb, inst, rng):
    """Maison de plain-pied, commerce ou mairie : un seul niveau aménagé."""
    c, a, q, L, W = pl["c"], pl["a"], pl["q"], pl["L"], pl["W"]
    l0, top = pl["l0"], pl["top"]
    ip = pl["ip"]
    yaw_a = math.atan2(a[1], a[0])
    dec = pl["decor"] = pick_decor(rng, b["style"])
    if pl["kind"] == "commerce":
        dec["floor0"] = str(rng.choice(["CarreauxCiment", "Tomettes", "Dallage"], p=[0.5, 0.35, 0.15]))
        dec["fcol0"] = CIMENT_COLS[rng.integers(len(CIMENT_COLS))] + (255,) if dec["floor0"] == "CarreauxCiment" else WHITE
        dec["theme"] = "mairie" if b.get("mairie") else SHOP_TYPE.get(b.get("shop"), "boutique_santons")

    def Wp(x, y):
        return c + x * a + y * q

    _flat(mb, dec["floor0"], ip, l0 + 0.002, up=True, col=dec["fcol0"])
    _flat(mb, dec["wall_mat"], ip, top, up=False, col=COL_PLAFOND)
    if dec["beams"]:
        from shapely.geometry import LineString
        nb = int((L - 0.4) / 0.7)
        inner = pl["ip_local"].buffer(-0.02)
        for k in range(nb + 1):
            x = -L / 2 + 0.2 + k * (L - 0.4) / max(nb, 1)
            seg = LineString([(x, -W / 2 - 1), (x, W / 2 + 1)]).intersection(inner)
            for piece in getattr(seg, "geoms", [seg]):
                if piece.is_empty or piece.geom_type != "LineString" or piece.length < 0.3:
                    continue
                (x0_, y0_), (x1_, y1_) = piece.coords[0], piece.coords[-1]
                P = Wp(x, (y0_ + y1_) / 2)
                box(mb, "BoisBrut", (P[0], P[1], top - 0.09), (0.14, abs(y1_ - y0_), 0.18), yaw=yaw_a, col=dec["beams"], uv_scale=1.0)
    _inner_walls(mb, ip, pl["openings_world"], [(l0, top, dec["wall0"])], dec["wall_mat"])
    # cloisons
    parts = []
    if pl["kind"] == "plainpied":
        for xp in pl["cuts"]:
            parts.append((xp, pl["door_y"]))
    elif pl.get("back"):
        parts.append((pl["back"]["x"], pl["back"]["door_y"]))
    for xp, dy in parts:
        _partition(mb, Wp, yaw_a, (xp, -W / 2), (xp, W / 2), l0, top, [(dy, 0.85, 2.05)], dec["wall0"], along_y=True, mat=dec["wall_mat"])
    _entry_steps(mb, pl, l0)
    furnish_rdc(b, pl, inst, rng, Wp, yaw_a)
    b["visit_plan"] = dict(theme=dec["theme"], kind=pl["kind"], c=[float(c[0]), float(c[1])], a=[float(a[0]), float(a[1])], L=float(L),
                           W=float(W), l0=float(l0), lv=[float(l0)], top=float(top), entree=_entree(pl))


def _entree(pl):
    """Porte d'entrée vue de l'intérieur : point (repère local) et direction vers l'intérieur."""
    m = pl["main"]
    L, W = pl["L"], pl["W"]
    mid = (m["span"][0] + m["span"][1]) / 2
    return {"+y": [mid, W / 2, 0.0, -1.0], "-y": [mid, -W / 2, 0.0, 1.0], "+x": [L / 2, mid, -1.0, 0.0], "-x": [-L / 2, mid, 1.0, 0.0]}[m["side"]]


def _entry_steps(mb, pl, l0):
    """Marches en pierre devant une porte plus haute que la rue."""
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


def furnish_rdc(b, pl, inst, rng, Wp, yaw_a):
    L, W, l0 = pl["L"], pl["W"], pl["l0"]
    theme = pl["decor"]["theme"]
    ALL = ("+y", "-y", "+x", "-x")
    paint = PAINT[rng.integers(len(PAINT))]
    fabric = FABRIC[rng.integers(len(FABRIC))]
    fabric2 = FABRIC[rng.integers(len(FABRIC))]
    linen = LINEN[rng.integers(len(LINEN))]
    looted = pl["kind"] == "commerce" and theme != "mairie" and rng.random() < 0.5
    wreck = theme == "saccagee" or looted

    def put(name, cx, cy, z, yaw, col=(255, 255, 255)):
        if wreck and SIZE.get(name, (0, 0, 9))[2] < 1.3 and name not in ("Int_Tapis", "Int_Cadre", "Int_Miroir") and rng.random() < 0.5:
            cx, cy, yaw = cx + rng.normal(0, 0.15), cy + rng.normal(0, 0.15), yaw + rng.normal(0, 0.5)
        P = Wp(cx, cy)
        inst[name].append((P[0], P[1], z, yaw_a + yaw, 1.0, 1.0, 1.0, *col))

    blocks, tall = [], []
    for lo in pl["locs"]:
        if lo["floor"] != 0 or lo["side"] is None:
            continue
        a0, a1 = lo["span"]
        if lo["door"] or "Porte" in lo["type"] or "Remise" in lo["type"] or "Vitrine" in lo["type"]:
            blocks.append(_front_rect(lo["side"], a0 - 0.25, a1 + 0.25, 1.2, L, W))
        else:
            tall.append(_front_rect(lo["side"], a0 - 0.1, a1 + 0.1, 0.4, L, W))
    # passages des portes de cloison
    xs = pl.get("cuts") or ([pl["back"]["x"]] if pl.get("back") else [])
    dys = [pl["door_y"]] * len(xs) if pl["kind"] == "plainpied" else ([pl["back"]["door_y"]] if pl.get("back") else [])
    for xp, dy in zip(xs, dys):
        blocks.append((xp - 0.9, xp + 0.9, dy - 0.55, dy + 0.55))
        blocks.append((xp - PART, xp + PART, -W / 2, W / 2))
    P = Placer(blocks, tall, None if pl.get("rect", True) else pl["ip_local"].buffer(-0.02))

    def wall(room, sides, name, col=(255, 255, 255), pref=0.5):
        for sd in sides:
            got = P.wall(room, sd, name, pref=pref)
            if got:
                put(name, got[0], got[1], l0, got[2], col)
                return got
        return None

    def centre(room, name, yaw=0.0, col=(255, 255, 255)):
        cx0, cy0 = (room[0] + room[1]) / 2, (room[2] + room[3]) / 2
        for dx in (0.0, -0.4, 0.4, -0.8, 0.8):
            for dy in (0.0, -0.3, 0.3):
                if P.at(name, cx0 + dx, cy0 + dy, yaw, pad=0.35):
                    put(name, cx0 + dx, cy0 + dy, l0, yaw, col)
                    return cx0 + dx, cy0 + dy
        return None

    def hang(room, n, names=("Int_Cadre",)):
        Pw = Placer(blocks + tall, [], None if pl.get("rect", True) else pl["ip_local"].buffer(-0.02))
        for k in range(n):
            nm = names[k % len(names)]
            sd = ALL[int(rng.integers(4))]
            got = Pw.wall(room, sd, nm, pref=float(rng.uniform(0.2, 0.8)))
            if got:
                put(nm, got[0], got[1], l0, got[2])

    full = (-L / 2, L / 2, -W / 2, W / 2)
    if pl["kind"] == "plainpied":
        d, start, cuts = pl["d"], pl["start"], pl["cuts"]
        edges = [start] + cuts + [-start]
        rooms = []
        for k in range(3):
            x0, x1 = sorted((edges[k], edges[k + 1]))
            rooms.append((x0 + PART, x1 - PART, -W / 2, W / 2))
        living, bedroom, bath = rooms
        if theme == "moderne":
            wall4 = lambda P_, room, sides, name, z, col=(255, 255, 255), pref=0.5: wall(room, sides, name, col, pref)
            modern_ground(P, living, living, living, ("+y", "+x", "-y", "-x"), l0, put, wall4, rng)
            modern_bedroom(P, bedroom, ("+x", "-x", "+y", "-y"), l0, put, wall4, rng, hang=lambda: hang(bedroom, 1, ("Int_CadreModerne",)))
            wall(bath, ALL, "Int_Douche")
            wall(bath, ALL, "Int_WC")
            wall(bath, ALL, "Int_VasqueModerne")
            hang(living, 2, ("Int_CadreModerne",))
            return
        # séjour-cuisine : coin cuisine contre un long mur, table, canapé, cheminée ou poêle selon l'ambiance
        rustic = theme in ("salle_commune", "grand_mere", "atelier")
        if theme == "refuge":
            wall(living, ALL, "Int_Rechaud")
            for k in range(3):
                wall(living, ALL, "Int_Jerrican", pref=float(rng.random()))
            wall(living, ALL, "Int_Conserves", pref=float(rng.random()))
            for k in range(2):
                wall(living, ALL, "Int_Matelas", pref=float(rng.random()))
        else:
            wall(living, ("+y", "-y"), "Int_EvierPierre" if rustic else "Int_PlanTravail", paint, pref=0.8)
            wall(living, ("-y", "+y", "+x", "-x"), "Int_Buffet", paint)
            centre(living, "Int_TableManger" if theme == "bourgeoise" else "Int_TableCuisine", 0.0, fabric)
            wall(living, ("+x", "-x", "-y", "+y"), "Int_Poele" if rustic else "Int_Cheminee")
            wall(living, ("-y", "+y"), "Int_Canape", linen)
            wall(living, ALL, "Int_Fauteuil", linen, pref=float(rng.random()))
            if theme in ("grand_mere", "bourgeoise", "salle_commune"):
                wall(living, ALL, "Int_Horloge", paint)
            if theme == "bourgeoise":
                wall(living, ALL, "Int_Piano")
            wall(living, ALL, "Int_Plante", pref=float(rng.random()))
            for k in range(4):
                c_ = P.at("Int_Chaise", rng.uniform(living[0] + 0.5, living[1] - 0.5), rng.uniform(-W / 4, W / 4), 0.0)
                if c_:
                    put("Int_Chaise", (c_[0] + c_[1]) / 2, (c_[2] + c_[3]) / 2, l0, float(rng.choice([0.0, math.pi])))
            hang(living, 2)
        # chambre
        if theme == "refuge":
            for k in range(2):
                wall(bedroom, ALL, "Int_Matelas", pref=float(rng.random()))
            wall(bedroom, ALL, "Int_EtagereBocaux")
        else:
            bed = "Int_LitsEnfants" if theme == "famille" and W >= 3.0 else ("Int_LitDouble" if W >= 3.2 else "Int_LitSimple")
            wall(bedroom, ("+x", "-x", "+y", "-y"), bed, fabric)
            wall(bedroom, ("+y", "-y"), "Int_Armoire")
            wall(bedroom, ("-y", "+y"), "Int_Commode")
            wall(bedroom, ALL, "Int_Chevet")
            hang(bedroom, 1, ("Int_Cadre", "Int_Miroir"))
        # salle de bain
        wall(bath, ALL, "Int_Baignoire")
        wall(bath, ALL, "Int_WC")
        got = wall(bath, ALL, "Int_Lavabo", paint)
        if got:
            put("Int_Miroir", got[0] - math.sin(got[2]) * 0.21, got[1] + math.cos(got[2]) * 0.21, l0 - 0.35, got[2])
        if wreck or theme == "refuge" or rng.random() < 0.35:
            for k in range(int(rng.integers(1, 4))):
                wall(full, ALL, "Int_Carton", pref=float(rng.random()))
        if theme == "saccagee":
            for k in range(2):
                put(("Z_Sol_sang_1", "Z_Sol_sang_flaque", "Z_Sol_sang_trainee")[int(rng.integers(3))], rng.uniform(-L / 3, L / 3),
                    rng.uniform(-W / 4, W / 4), l0 + 0.005, float(rng.uniform(0, 6.28)))
        return

    # ---------------- commerces et mairie : salle de vente (côté entrée) + arrière-boutique éventuelle
    back = pl.get("back")
    if back:
        xp, sgn = back["x"], back["sgn"]
        front = tuple(sorted((xp + sgn * PART, sgn * L / 2))) + (-W / 2, W / 2)
        rear = tuple(sorted((xp - sgn * PART, -sgn * L / 2))) + (-W / 2, W / 2)
    else:
        front, rear = full, None
    ent = pl["main"]["side"]
    opp = {"+x": "-x", "-x": "+x", "+y": "-y", "-y": "+y"}[ent]
    lat = ("+y", "-y") if ent in ("+x", "-x") else ("+x", "-x")
    far_sides = (opp,) + lat
    across = 0.0 if ent in ("+y", "-y") else math.pi / 2          # meubles d'îlot parallèles à la façade d'entrée
    shape = pl["ip_local"]
    area_f = shape.intersection(sbox(front[0], front[2], front[1], front[3])).area

    def fill_wall(room, sides, name, n, col=(255, 255, 255), gap=0.03):
        got_n = 0
        for pref in (0.5, 0.15, 0.85, 0.3, 0.7, 0.05, 0.95, 0.4, 0.6, 0.22, 0.78):
            for sd in sides:
                if got_n >= n:
                    return got_n
                got = P.wall(room, sd, name, pref=pref, gap=gap)
                if got:
                    put(name, got[0], got[1], l0, got[2], col)
                    got_n += 1
        return got_n

    def fill_floor(room, name, n, yaw=0.0, pad=0.45, col=(255, 255, 255), after=None):
        w_, d_, _ = SIZE[name]
        if abs(math.sin(yaw)) > 0.7:
            w_, d_ = d_, w_
        sx_, sy_ = w_ + 2 * pad, d_ + 2 * pad
        xs_ = np.arange(room[0] + sx_ / 2, room[1] - sx_ / 2 + 1e-6, sx_)
        ys_ = np.arange(room[2] + sy_ / 2, room[3] - sy_ / 2 + 1e-6, sy_)
        spots = [(x_, y_) for x_ in xs_ for y_ in ys_]
        got_n = 0
        for x_, y_ in spots:
            if got_n >= n:
                break
            if P.at(name, x_, y_, yaw, pad=pad * 0.8):
                put(name, x_, y_, l0, yaw, col)
                got_n += 1
                if after:
                    after(x_, y_)
        return got_n

    def counter(name, col=(255, 255, 255)):
        for sd in far_sides:
            got = P.wall(front, sd, name, pref=0.5, gap=0.9)
            if got:
                put(name, got[0], got[1], l0, got[2], col)
                return got
        return None

    n_wall = max(2, int(area_f / 7))
    if theme in ("boulangerie", "boucherie", "glacier"):
        counter({"boulangerie": "Int_ComptoirPain", "boucherie": "Int_ComptoirViande", "glacier": "Int_ComptoirGlaces"}[theme], paint)
        fill_wall(front, far_sides, "Int_EtagerePain" if theme == "boulangerie" else "Int_EtagereBocaux", n_wall)
        if theme == "glacier":
            fill_floor(front, "Table_Cafe", int(area_f / 9), pad=0.6,
                       after=lambda x_, y_: [put("Chaise_Bistrot", x_ + 0.5 * math.cos(g_), y_ + 0.5 * math.sin(g_), l0, g_ + math.pi / 2)
                                             for g_ in (0.0, math.pi)])
        if rear:
            if theme == "boulangerie":
                fill_wall(rear, ALL, "Int_FourPain", 1)
                fill_wall(rear, ALL, "Int_Petrin", 1)
            fill_wall(rear, ALL, "Int_Carton", 3)
    elif theme in ("cafe", "restaurant"):
        if theme == "cafe" or rng.random() < 0.5:
            got = counter("Int_ComptoirBar")
            if got:
                ox, oy = -math.sin(got[2]), math.cos(got[2])
                tx, ty = math.cos(got[2]), math.sin(got[2])
                for k in (-1, 0, 1):
                    sx_, sy_ = got[0] - ox * 0.75 + tx * k * 0.7, got[1] - oy * 0.75 + ty * k * 0.7
                    if P.at("Int_Tabouret", sx_, sy_, 0.0):
                        put("Int_Tabouret", sx_, sy_, l0, 0.0)
            fill_wall(front, far_sides, "Int_CasierBouteilles", 1)

        def seats(x_, y_):
            if theme == "restaurant":
                sl = [(x_, y_ + 0.62, 0.0), (x_, y_ - 0.62, math.pi)]
            else:
                sl = [(x_ + 0.5 * math.cos(g_), y_ + 0.5 * math.sin(g_), g_ + math.pi / 2) for g_ in (0.0, math.pi / 2, math.pi, -math.pi / 2)]
            for cx_, cy_, yw_ in sl:
                chair = "Chaise_Bistrot" if theme == "cafe" else "Int_Chaise"
                if wreck and rng.random() < 0.3:
                    chair = "Int_ChaiseRenversee"
                put(chair, cx_, cy_, l0, yw_)
        fill_floor(front, "Table_Cafe" if theme == "cafe" else "Int_TableCuisine", max(2, int(area_f / 6)),
                   pad=0.55 if theme == "cafe" else 0.7, col=fabric, after=seats)
        fill_wall(front, lat, "Int_Plante", 1)
        hang(front, max(2, int(area_f / 8)))
        if rear:
            fill_wall(rear, ALL, "Int_PlanTravail", 1, paint)
            fill_wall(rear, ALL, "Int_Frigo", 1)
            fill_wall(rear, ALL, "Int_EtagereBocaux", 2)
            fill_wall(rear, ALL, "Int_CasierBouteilles", 1)
    elif theme in ("epicerie", "cave"):
        counter("Int_Caisse", paint)
        if theme == "epicerie":
            fill_wall(front, far_sides, "Int_EtagereBocaux", n_wall)
            fill_floor(front, "Int_Gondole", max(1, int(area_f / 8)), yaw=across, pad=0.6)
            fill_wall(front, ALL, "Int_Cagettes", 2)
        else:
            fill_wall(front, far_sides, "Int_CasierBouteilles", n_wall)
            fill_floor(front, "Int_Tonneau", max(1, int(area_f / 10)), yaw=across, pad=0.5)
        if rear:
            fill_wall(rear, ALL, "Int_Carton", 4)
            fill_wall(rear, ALL, "Int_EtagereOutils", 1)
    elif theme == "pharmacie":
        counter("Int_ComptoirPharmacie")
        fill_wall(front, far_sides, "Int_RayonPharmacie", n_wall)
        fill_floor(front, "Int_PresentoirSavons", max(1, int(area_f / 14)), yaw=across, pad=0.7)
        if rear:
            fill_wall(rear, ALL, "Int_ArmoireArchives", 2)
            fill_wall(rear, ALL, "Int_Carton", 3)
    elif theme == "coiffeur":
        for k in range(max(2, int(area_f / 6))):
            got = P.wall(front, lat[k % 2], "Int_FauteuilCoiffeur", pref=0.2 + 0.2 * (k // 2))
            if got:
                put("Int_FauteuilCoiffeur", got[0], got[1], l0, got[2])
                put("Int_Miroir", got[0] - math.sin(got[2]) * 0.3, got[1] + math.cos(got[2]) * 0.3, l0 - 0.2, got[2])
        counter("Int_Caisse", paint)
        fill_wall(front, ALL, "Int_BancAttente", 1)
        fill_wall(front, ALL, "Int_Plante", 2)
    elif theme == "galerie":
        fill_floor(front, "Int_PresentoirPoterie", max(1, int(area_f / 16)), yaw=across, pad=0.9)
        fill_floor(front, "Int_PresentoirLivres", max(1, int(area_f / 24)), yaw=across, pad=0.9)
        fill_wall(front, ALL, "Int_Statue", max(1, int(area_f / 25)))
        hang(front, max(4, int(area_f / 3)))
        counter("Int_Bureau")
    elif theme.startswith("boutique"):
        fill = {"boutique_savons": "Int_PresentoirSavons", "boutique_poterie": "Int_PresentoirPoterie"}.get(theme, "Int_PresentoirSantons")
        counter("Int_Caisse", paint)
        fill_floor(front, fill, max(1, int(area_f / 9)), yaw=across, pad=0.6)
        fill_wall(front, far_sides, "Int_EtagereBocaux", n_wall)
        hang(front, 2)
    elif theme == "accueil":
        counter("Int_Bureau")
        fill_wall(front, ALL, "Int_BancAttente", max(1, int(area_f / 12)))
        fill_wall(front, ALL, "Int_Bibliotheque", max(1, int(area_f / 10)))
        fill_floor(front, "Int_PresentoirLivres", max(1, int(area_f / 20)), yaw=across, pad=0.8)
        fill_wall(front, ALL, "Int_Plante", 2)
        hang(front, max(3, int(area_f / 6)))
        if rear:
            fill_wall(rear, ALL, "Int_ArmoireArchives", 2)
    elif theme == "mairie":
        # salle du conseil et des mariages : grande table et drapeaux, rangées de chaises tournées vers la table
        spot = []
        fill_floor(front, "Int_TableManger", 1, yaw=across, pad=0.9, after=lambda x_, y_: spot.append((x_, y_)))
        if spot:
            tx_, ty_ = spot[0]
            nx_, ny_ = (0.0, 1.0) if abs(math.sin(across)) < 0.5 else (1.0, 0.0)      # perpendiculaire à la table
            for k in (-1, 0, 1):
                put("Int_Chaise", tx_ + nx_ * 0.62 + ny_ * k * 0.62, ty_ + ny_ * 0.62 + nx_ * k * 0.62, l0,
                    across + (0.0 if abs(math.sin(across)) < 0.5 else 0.0))
            yaw_pub = across + math.pi
            n_ch = 0
            for row in range(2, 16):
                for k in range(-8, 9):
                    if k == 0:
                        continue                                          # allée centrale
                    cx_ = tx_ - nx_ * (0.8 + 0.85 * row) + ny_ * k * 0.55
                    cy_ = ty_ - ny_ * (0.8 + 0.85 * row) + nx_ * k * 0.55
                    if P.at("Int_Chaise", cx_, cy_, yaw_pub, pad=0.03):
                        put("Int_Chaise", cx_, cy_, l0, yaw_pub)
                        n_ch += 1
        fill_wall(front, far_sides, "Int_Drapeaux", 1)
        fill_wall(front, lat, "Int_BancAttente", 2)
        fill_wall(front, ALL, "Int_ArmoireArchives", 2)
        fill_wall(front, ALL, "Int_Bureau", 1)
        fill_wall(front, ALL, "Int_Plante", 2)
        hang(front, max(3, int(area_f / 10)))
        if rear:
            fill_wall(rear, ALL, "Int_ArmoireArchives", 3)
            fill_wall(rear, ALL, "Int_Bureau", 1)
    if looted:
        for k in range(int(rng.integers(2, 5))):
            wall(full, ALL, "Int_Carton", pref=float(rng.random()))
        got = P.at("Int_ChaiseRenversee", rng.uniform(-L / 4, L / 4), rng.uniform(-W / 5, W / 5), 0.3)
        if got:
            put("Int_ChaiseRenversee", (got[0] + got[1]) / 2, (got[2] + got[3]) / 2, l0, float(rng.uniform(0, 6.28)))
        if rng.random() < 0.5:
            put("Z_Sol_sang_trainee", rng.uniform(-L / 4, L / 4), rng.uniform(-W / 5, W / 5), l0 + 0.005, float(rng.uniform(0, 6.28)))


def spiral_stair(mb, C, z0, z1, yaw0):
    """Escalier en colimaçon : noyau central, marches rayonnantes en pierre, main courante en fer.
    La première marche part dans la direction yaw0 ; on arrive en haut après 3/4 de tour."""
    h = z1 - z0
    n = int(math.ceil(h / 0.19))
    rise = h / n
    R = SPIRAL / 2 - 0.08
    turn = math.radians(270)
    tube(mb, "PierreTaille", [(C[0], C[1], z0), (C[0], C[1], z1 + 0.9)], 0.09, segs=10, u_tile=3, v_tile=3)
    rail = []
    for i in range(n):
        ang = yaw0 + turn * (i + 0.5) / n
        rc = (R + 0.09) / 2
        P = (C[0] + math.cos(ang) * rc, C[1] + math.sin(ang) * rc, z0 + (i + 1) * rise - 0.03)
        # marche : pavé tourné, plus large vers l'extérieur (approché par deux pavés)
        box(mb, "PierreTaille", P, (R - 0.05, 0.3, 0.06), yaw=ang, uv_scale=3.0)
        Po = (C[0] + math.cos(ang) * (R * 0.78), C[1] + math.sin(ang) * (R * 0.78), P[2])
        box(mb, "PierreTaille", Po, (R * 0.45, 0.42, 0.06), yaw=ang, uv_scale=3.0)
        # contremarche
        box(mb, "PierreTaille", (P[0], P[1], P[2] - rise / 2), (R - 0.05, 0.05, rise), yaw=ang, uv_scale=3.0)
        a_r = yaw0 + turn * i / n
        rail.append((C[0] + math.cos(a_r) * (R + 0.02), C[1] + math.sin(a_r) * (R + 0.02), z0 + i * rise + 0.95))
        if i % 2 == 0:
            tube(mb, "Fer", [(rail[-1][0], rail[-1][1], z0 + (i + 1) * rise), rail[-1]], 0.012, segs=5, col=(60, 55, 50, 255))
    tube(mb, "Fer", rail, 0.02, segs=6, col=(60, 55, 50, 255))


def _inner_walls(mb, ip, openings_w, bands, mat="Enduit"):
    """Faces intérieures des murs extérieurs, percées des ouvertures ; bands = [(z bas, z haut, couleur)]."""
    cs = np.array(ip.exterior.coords)
    if Polygon(cs).exterior.is_ccw is False:
        cs = cs[::-1]
    for zb, zt, col in bands:
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
                planar_polygon(mb, mat, np.array(g.exterior.coords)[:-1], [np.array(h.coords)[:-1] for h in g.interiors],
                               origin, e1, np.array([0, 0, 1.0]), lambda v2, P: np.stack([v2[:, 0] / 3.0, -v2[:, 1] / 3.0], -1), col)


def _polys(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [x for x in getattr(g, "geoms", []) if x.geom_type == "Polygon"]


def _partition(mb, Wp, yaw_a, p0, p1, zb, zt, doors, col, along_y=False, mat="Enduit"):
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
            box(mb, mat, (P[0], P[1], (z0 + z1) / 2), (PART, a1 - a0, z1 - z0), yaw=yaw_a, col=col, uv_scale=3.0)
        else:
            P = Wp(m, y)
            box(mb, mat, (P[0], P[1], (z0 + z1) / 2), (a1 - a0, PART, z1 - z0), yaw=yaw_a, col=col, uv_scale=3.0)
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

    def __init__(self, blocks, tall_blocks, inside=None):
        self.blocks = list(blocks)          # rectangles interdits (x0, x1, y0, y1)
        self.tall = list(tall_blocks)       # interdits seulement aux meubles hauts (devant les fenêtres)
        self.inside = inside                # contour de la pièce (repère local), pour les plans irréguliers

    @staticmethod
    def hit(r, o, m=0.0):
        return r[0] < o[1] + m and r[1] > o[0] - m and r[2] < o[3] + m and r[3] > o[2] - m

    def free(self, r, h):
        if any(self.hit(r, o) for o in self.blocks):
            return False
        if self.inside is not None and not self.inside.contains(sbox(r[0], r[2], r[1], r[3])):
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
    "moderne": 26,
}
MODERN_WALLS = [(246, 246, 244), (236, 237, 238), (232, 230, 226), (220, 222, 224), (242, 240, 234)]
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
        if m == "BetonCire":
            return [(255, 255, 255), (225, 228, 232), (240, 232, 220), (200, 200, 200)][rng.integers(4)] + (255,)
        if m == "Parquet" and theme == "moderne":
            return (255, 250, 240, 255)
        if m == "CarreauxCiment":
            return CIMENT_COLS[rng.integers(len(CIMENT_COLS))] + (255,)
        if m == "Parquet":
            return PARQUET_COLS[rng.integers(len(PARQUET_COLS))] + (255,)
        return WHITE
    w0 = WALL_COLS[rng.integers(len(WALL_COLS))]
    w1 = WALL_COLS[rng.integers(len(WALL_COLS))] if rng.random() < 0.5 else w0
    beams = None if rng.random() < 0.15 else BEAM_COLS[rng.integers(len(BEAM_COLS))] + (255,)
    frise = [(60, 90, 140), (40, 110, 110), (170, 110, 40), (120, 60, 50), (70, 110, 70)][rng.integers(5)] + (255,)
    f2 = rng.choice(["Parquet", "Tomettes"], p=[0.6, 0.4])
    if theme == "moderne":
        # maison rénovée : béton ciré ou parquet clair, murs blancs ou gris clair, plafond lisse le plus souvent
        f0 = rng.choice(["BetonCire", "Parquet"], p=[0.6, 0.4])
        f1 = f2 = "Parquet"
        w0 = MODERN_WALLS[rng.integers(len(MODERN_WALLS))]
        w1 = MODERN_WALLS[rng.integers(len(MODERN_WALLS))]
        beams = None if rng.random() < 0.75 else (236, 234, 230, 255)
        frise = (70, 72, 76, 255)
    return dict(theme=theme, floor0=str(f0), floor1=str(f1), floor2=str(f2), fcol0=fcol(f0), fcol1=fcol(f1), fcol2=fcol(f2),
                wall0=w0 + (255,), wall1=w1 + (255,), wall2=w1 + (255,), beams=beams, frise=frise,
                kitchen_near_stairs=bool(rng.random() < 0.35), wall_mat="Peinture" if theme == "moderne" else "Enduit")


def modern_ground(P, room_k, room_s, room_all, sides, z, put, wall, rng):
    """Rez-de-chaussée rénové : cuisine laquée (îlot si la place le permet), séjour avec canapé d'angle face à la télévision."""
    s_other, s_far, s_band, s_end = sides
    laque = [(255, 255, 255), (70, 72, 76), (150, 160, 150), (40, 60, 90), (235, 230, 220)][int(rng.integers(5))]
    wall(P, room_k, (s_other, s_far, s_band), "Int_CuisineModerne", z, laque, pref=0.5)
    cx, cy = (room_k[0] + room_k[1]) / 2, (room_k[2] + room_k[3]) / 2
    placed = False
    for dx in (0.0, -0.3, 0.3, -0.6, 0.6):
        for dy in (0.0, -0.3, 0.3):
            if P.at("Int_Ilot", cx + dx, cy + dy, 0.0, pad=0.45):
                put("Int_Ilot", cx + dx, cy + dy, z, 0.0, laque)
                placed = True
                break
        if placed:
            break
    if not placed:
        for dx in (0.0, -0.4, 0.4):
            if P.at("Int_TableModerne", cx + dx, cy, 0.0, pad=0.2):
                put("Int_TableModerne", cx + dx, cy, z, 0.0)
                break
    # séjour : télévision contre un mur, canapé d'angle en face à ~2,8 m, table basse, lampe arc, étagère
    tv = wall(P, room_s, (s_other, s_band, s_end), "Int_MeubleTV", z, pref=0.5)
    if tv:
        tx, ty, tyaw, _ = tv
        nx, ny = -math.sin(tyaw), math.cos(tyaw)
        for dist in (2.9, 2.6, 3.2, 2.3):
            sx_, sy_ = tx - nx * dist, ty - ny * dist
            if P.at("Int_CanapeAngle", sx_, sy_, tyaw + math.pi):
                put("Int_CanapeAngle", sx_, sy_, z, tyaw + math.pi)
                bx, by = tx - nx * (dist - 1.4), ty - ny * (dist - 1.4)
                if P.at("Int_TableBasseModerne", bx, by, tyaw):
                    put("Int_TableBasseModerne", bx, by, z, tyaw)
                break
    wall(P, room_s, (s_band, s_other, s_end), "Int_EtagereCubes", z, pref=float(rng.random()))
    wall(P, room_s, (s_end, s_band, s_other), "Int_LampeArc", z, pref=float(rng.random()))
    for k in range(2):
        wall(P, room_all, (s_other, s_band, s_far, s_end), "Int_PlanteModerne", z, pref=float(rng.random()))


def modern_bedroom(P, room, sides, z, put, wall, rng, hang=None):
    """Chambre moderne : lit plateforme, chevets, dressing, bureau avec ordinateur."""
    got = wall(P, room, sides, "Int_LitModerne", z, pref=0.5)
    if got:
        bx_, by_, byaw, _ = got
        tx, ty = math.cos(byaw), math.sin(byaw)
        nx, ny = -math.sin(byaw), math.cos(byaw)
        for sg in (-1, 1):
            cx = bx_ + tx * sg * (1.8 / 2 + 0.3) + nx * 0.85
            cy = by_ + ty * sg * (1.8 / 2 + 0.3) + ny * 0.85
            if P.at("Int_Chevet", cx, cy, byaw):
                put("Int_Chevet", cx, cy, z, byaw, (245, 245, 245))
    wall(P, room, sides[1:] + sides[:1], "Int_Dressing", z, (245, 245, 245))
    wall(P, room, sides[1:] + sides[:1], "Int_BureauInfo", z)
    wall(P, room, sides, "Int_PlanteModerne", z, pref=float(rng.random()))
    if hang:
        hang()


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
    if pl["decor"].get("kitchen_near_stairs") and theme not in ("atelier", "salle_commune"):
        # variante : cuisine du côté de l'escalier, séjour au fond (vers les fenêtres du pignon)
        kx = sorted((end, end + d * 3.3))
        room_k = (kx[0], kx[1], -W / 2, W / 2)
        sx_ = sorted((end + d * 3.3, far))
        room_s = (sx_[0], sx_[1], -W / 2, W / 2)
        pref_far = 0.0 if d > 0 else 1.0
        side_far, side_end = side_end, side_far

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

    if theme == "moderne":
        modern_ground(P, room_k, room_s, room_all, (side_other, side_far, side_band, side_end), l0, put, wall, rng)
    elif theme in ("classique", "famille", "saccagee"):
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
    side_end = "-x" if d > 0 else "+x"
    side_far = "+x" if d > 0 else "-x"
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
    tub = "Int_Douche" if theme == "moderne" else "Int_Baignoire"
    got = P.wall(room_b, side_end, tub) if bath_w >= 1.75 else None
    got = got or P.wall(room_b, side_other, tub, pref=0.0 if d > 0 else 1.0)
    if got:
        put(tub, got[0], got[1], l1, got[2])
    got = P.wall(room_b, side_other, "Int_WC", pref=1.0 if d > 0 else 0.0) or P.wall(room_b, "+x" if d < 0 else "-x", "Int_WC")
    if got:
        put("Int_WC", got[0], got[1], l1, got[2])
    if theme == "moderne":
        wall(P, room_b, (side_band, side_other), "Int_VasqueModerne", l1)
    else:
        got = wall(P, room_b, (side_band, side_other), "Int_Lavabo", l1, paint)
        if got:
            # miroir au-dessus du lavabo
            put("Int_Miroir", got[0] - math.sin(got[2]) * 0.21, got[1] + math.cos(got[2]) * 0.21, l1 - 0.35, got[2])
    wall(P, room_b, (side_band,), "Int_Commode", l1, pref=0.2 if d > 0 else 0.8)
    rx = sorted((xc, far))
    room_r = (rx[0] + PART / 2 + 0.02, rx[1], -W / 2, W / 2)
    if pl.get("spiral"):
        spx, spy = pl["spiral"][:2]
        P.blocks.append((spx - SPIRAL / 2 - 0.5, spx + SPIRAL / 2 + 0.5, spy - SPIRAL / 2 - 0.5, spy + SPIRAL / 2 + 0.5))
    upper = {"classique": "parents", "saccagee": "parents", "salle_commune": "parents", "bourgeoise": "parents", "grand_mere": "grand_mere",
             "famille": "enfants", "atelier": "bureau", "refuge": "dortoir", "moderne": "moderne"}[theme]
    if upper == "enfants" and W < 3.0:
        upper = "parents"
    if upper == "moderne":
        modern_bedroom(P, room_r, (side_far, side_other, side_band), l1, put, wall, rng, hang=lambda: hang(room_r, 1, l1, 2, ("Int_CadreModerne",)))
    elif upper in ("parents", "grand_mere"):
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

    # ================= 2e étage (colimaçon) : grenier encombré, ou chambre d'amis mansardée
    if pl.get("spiral"):
        l2 = pl["lv"][2]
        blocks, tall = blocks_for(2)
        spx, spy = pl["spiral"][:2]
        blocks.append((spx - SPIRAL / 2 - 0.6, spx + SPIRAL / 2 + 0.6, spy - SPIRAL / 2 - 0.6, spy + SPIRAL / 2 + 0.6))
        P = Placer(blocks, tall)
        if theme in ("refuge",):
            for k in range(3):
                wall(P, room_all, ALL, "Int_Matelas", l2, pref=float(rng.random()))
            wall(P, room_all, ALL, "Int_Jerrican", l2, pref=float(rng.random()))
        elif rng.random() < 0.6:
            # grenier : malles, cartons, vieux meubles, tonneau, chaise renversée
            for nm in ("Int_Malle", "Int_Malle", "Int_Armoire", "Int_Commode", "Int_Fauteuil", "Int_Tonneau", "Int_Bibliotheque"):
                if rng.random() < 0.75:
                    wall(P, room_all, (ALL[int(rng.integers(4))], ALL[int(rng.integers(4))]), nm, l2, pref=float(rng.random()))
            for k in range(int(rng.integers(3, 7))):
                wall(P, room_all, (ALL[int(rng.integers(4))],), "Int_Carton", l2, pref=float(rng.random()))
            got = P.at("Int_ChaiseRenversee", rng.uniform(-L / 4, L / 4), rng.uniform(-W / 5, W / 5), float(rng.uniform(0, 6.28)))
            if got:
                put("Int_ChaiseRenversee", (got[0] + got[1]) / 2, (got[2] + got[3]) / 2, l2, float(rng.uniform(0, 6.28)))
        else:
            wall(P, room_all, (side_far, side_end, side_other), "Int_LitSimple", l2, fabric2)
            wall(P, room_all, (side_other, side_band), "Int_Commode", l2)
            wall(P, room_all, (side_band, side_other), "Int_Bureau", l2)
            wall(P, room_all, ALL, "Int_Malle", l2, paint, pref=float(rng.random()))
            hang(room_all, 2, l2, 2)


def _front_rect(side, a0, a1, depth, L, W):
    if side == "+y":
        return (a0, a1, W / 2 - depth, W / 2)
    if side == "-y":
        return (a0, a1, -W / 2, -W / 2 + depth)
    if side == "+x":
        return (L / 2 - depth, L / 2, a0, a1)
    return (-L / 2, -L / 2 + depth, a0, a1)
