"""Étape 2 : bâtiments provençaux (maisons de village, mas, villas, remises, église, beffroi, mairie, commerces)."""
import sys, pickle, json, math, time, hashlib, collections
sys.path.insert(0, ".")
from common import *
from geomlib import MB, planar_polygon, triangulate, tube, box, revolve, disk, rect_sign, nrm, WHITE
from materials import TILE
from modules import OPENINGS, DOOR_LEAF, LEAVES
import interiors
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree
import shapely.prepared

T0 = time.time()
GROUND = np.load("terrain.npz")["ground"]
V = pickle.load(open("vec.pkl", "rb"))
SIGNS = json.load(open("tex/Enseignes.json", encoding="utf-8"))
from signs_tex import STREETS

CHUNK = 128.0


def gz(x, y):
    return float(grid_sample(GROUND, [x], [y], order=1)[0])


def gzv(xs, ys):
    return grid_sample(GROUND, np.asarray(xs), np.asarray(ys), order=1)


def rng_for(key):
    return np.random.default_rng(int(hashlib.md5(str(key).encode()).hexdigest()[:8], 16))


def pick(rng, items, weights=None):
    if weights is None:
        return items[rng.integers(len(items))]
    w = np.asarray(weights, float)
    return items[rng.choice(len(items), p=w / w.sum())]


# ------------------------------------------------------------------ palettes (sRGB)
OCHRES = [(226, 176, 100), (218, 158, 82), (210, 132, 70), (190, 104, 66), (218, 146, 116), (230, 166, 128), (200, 120, 74),
          (232, 196, 128), (176, 90, 60), (222, 186, 118), (206, 140, 92)]
CREAMS = [(238, 224, 192), (230, 212, 176), (242, 232, 210), (226, 208, 178), (234, 218, 196), (220, 200, 166), (236, 214, 172)]
PINKS = [(228, 184, 164), (220, 166, 146), (232, 196, 176)]
STONE_TINT = [(255, 255, 255), (250, 244, 232), (244, 236, 222)]
SHUTTERS = [(128, 150, 190), (78, 120, 168), (118, 142, 158), (104, 166, 166), (140, 160, 118), (98, 114, 72), (160, 188, 150),
            (170, 170, 165), (118, 48, 46), (156, 72, 52), (108, 78, 56), (222, 212, 186), (214, 196, 128), (88, 110, 128)]
SHUTTER_W = [2, 3, 2, 1.5, 2.5, 1.5, 1.5, 1.5, 1, 1, 1.5, 1, 0.7, 1.2]
DOORS = [(96, 66, 44), (118, 48, 46), (70, 90, 70), (88, 60, 40), (60, 80, 110)]
AWNINGS = [(120, 36, 40), (40, 80, 60), (226, 214, 180), (200, 150, 60), (50, 80, 130), (150, 60, 40), (90, 100, 60)]


# ------------------------------------------------------------------ préparation des emprises
def clean_poly(p):
    p = p.buffer(0)
    if p.geom_type == "MultiPolygon":
        p = max(p.geoms, key=lambda g: g.area)
    p = Polygon(p.exterior.coords)
    p = orient(shapely.simplify(p, 0.18), 1.0)
    cs = [np.array(c) for c in list(p.exterior.coords)[:-1]]
    changed = True
    while changed and len(cs) > 3:
        changed = False
        for i in range(len(cs)):
            a, b = cs[i], cs[(i + 1) % len(cs)]
            if np.linalg.norm(b - a) < 0.4:
                cs.pop((i + 1) % len(cs))
                changed = True
                break
            c = cs[(i + 2) % len(cs)]
            u, v = b - a, c - b
            cr = abs(u[0] * v[1] - u[1] * v[0]) / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-9)
            if cr < 0.08 and np.dot(u, v) > 0:
                cs.pop((i + 1) % len(cs))
                changed = True
                break
    if len(cs) < 3:
        return None
    q = orient(Polygon(cs), 1.0)
    if not q.is_valid or q.area < 5:
        return None
    return q


blds = []
for b in V["buildings"]:
    q = clean_poly(b["poly"])
    if q is None:
        continue
    b = dict(b)
    b["poly"] = q
    blds.append(b)
tree = STRtree([b["poly"] for b in blds])
core = V["core"]
CENTER = Point(-10.0, 0.0)

# rues, places, parkings : pour savoir quelles façades donnent sur l'espace public
street_geoms = [r["line"].buffer(r["width"] / 2 + 0.6) for r in V["roads"] if r["surface"] in ("asphalt", "stone", "gravel", "steps", "path", "dirt")]
street_geoms += V["plaza"] + V["parking"]
street_union = unary_union(street_geoms)
road_names = [(r["line"], r["name"]) for r in V["roads"] if r["name"]]
name_tree = STRtree([l for l, _ in road_names])

# ------------------------------------------------------------------ classification
for i, b in enumerate(blds):
    p = b["poly"]
    c = p.centroid
    rng = rng_for(b["id"])
    b["rng"] = rng
    dist = c.distance(CENTER)
    area = p.area
    cls, name = b["cls"], b["name"]
    in_core = core.contains(c)
    if name == "Église Saint-Michel" or cls in ("church", "chapel"):
        style = "church"
    elif name == "Beffroi":
        style = "belfry"
    elif cls == "roof":
        style = "shelter"
    elif cls == "greenhouse":
        style = "shed"
    elif in_core:
        style = "core"
    elif dist < 650 and area < 450:
        style = "faubourg"
    elif area < 24:
        style = "shed"
    elif area > 170 and (cls in (None, "farm_auxiliary", "house") and rng.random() < 0.8):
        style = "mas"
    else:
        style = "villa"
    b["style"] = style
    c_, axis, Lm, Wm = ombr(p)
    b["ombr"] = (c_, axis, Lm, Wm)

# commerces : chaque lieu est affecté au bâtiment le plus proche du vieux village / faubourg
SHOP_OF = {
    "restaurant": ["restaurant1", "restaurant2", "restaurant3", "restaurant4", "restaurant5", "restaurant6", "restaurant7", "restaurant8"],
    "french_restaurant": ["restaurant1", "restaurant2", "restaurant3", "restaurant4", "restaurant5", "restaurant6", "restaurant7", "restaurant8"],
    "mediterranean_restaurant": ["restaurant3", "restaurant4"], "pizza_restaurant": ["pizzeria"],
    "cafe": ["cafe1", "cafe2"], "bar": ["bar"], "brewery": ["bar"], "wine_bar": ["cave"],
    "bakery": ["boulangerie"], "hair_salon": ["coiffure"], "beauty_salon": ["beaute"], "spa": ["beaute"],
    "pharmacy": ["pharmacie"], "post_office": ["poste"], "grocery_store": ["epicerie"], "liquor_store": ["epicerie"],
    "art_gallery": ["galerie", "atelier"], "hotel": ["hotel", "hotel2"], "bed_and_breakfast": ["chambres"],
    "library": ["mediatheque"], "museum": ["musee"], "ice_cream_shop": ["glaces"],
    "fashion_boutique": ["boutique", "savons"], "home_goods_store": ["produits", "poterie"],
    "arts_crafts_and_hobby_store": ["santons", "poterie"], "gift_shop": ["santons"], "souvenir_shop": ["savons"],
    "winery": ["vins"], "butcher_shop": ["boucherie"], "tobacco_shop": ["bar"], "newsstand": ["bar"],
    "cultural_center": ["tourisme"],
}
used_signs = collections.Counter()
for pl in V["places"]:
    keys = SHOP_OF.get(pl["kind"])
    if not keys:
        continue
    pt = Point(pl["x"], pl["y"])
    cands = tree.query(pt.buffer(14))
    best, bd = None, 1e9
    for k in cands:
        b = blds[k]
        if b["style"] in ("church", "belfry", "shelter", "shed") or "shop" in b:
            continue
        d = b["poly"].distance(pt)
        if d < bd:
            best, bd = b, d
    if best is None or bd > 14:
        continue
    key = min(keys, key=lambda k: used_signs[k])
    used_signs[key] += 1
    best["shop"] = key
    best["shop_kind"] = pl["kind"]
# on s'assure qu'il y a bien un coiffeur, une boulangerie, une pharmacie et une épicerie au village
for must in ("coiffure", "boulangerie", "pharmacie", "epicerie", "bar", "tabac"):
    if must == "tabac" or used_signs[must]:
        continue
    cands = sorted([b for b in blds if b["style"] in ("core", "faubourg") and "shop" not in b and b["poly"].area > 40],
                   key=lambda b: b["poly"].centroid.distance(CENTER))
    for b in cands[3:]:
        if b["poly"].exterior.distance(street_union.boundary) < 6:
            b["shop"] = must
            used_signs[must] += 1
            break

# mairie : grand bâtiment du vieux village le plus proche du beffroi, donnant sur une place
belfry = next((b for b in blds if b["style"] == "belfry"), None)
ref = belfry["poly"].centroid if belfry else CENTER
cands = [b for b in blds if b["style"] == "core" and b["poly"].area > 70 and b["poly"].centroid.distance(ref) < 45]
if cands:
    mairie = max(cands, key=lambda b: b["poly"].area - 2.0 * b["poly"].centroid.distance(ref))
    mairie["mairie"] = True
    mairie.pop("shop", None)
print("classement : %s  (%.0fs)" % (dict(collections.Counter(b["style"] for b in blds)), time.time() - T0))


# ------------------------------------------------------------------ attributs architecturaux
def attributes(b):
    rng = b["rng"]
    st = b["style"]
    p = b["poly"]
    area = p.area
    c_, axis, Lm, Wm = b["ombr"]
    ov = b.get("height")
    if st == "core":
        nf = 2 if area < 28 else (3 if area < 160 else pick(rng, [3, 4], [0.7, 0.3]))
        if area > 45 and rng.random() < 0.25:
            nf += 1
        nf = min(nf, 4)
        if b.get("mairie"):
            nf = 3
    elif st == "faubourg":
        nf = pick(rng, [1, 2, 3], [0.15, 0.7, 0.15])
    elif st == "mas":
        nf = pick(rng, [2, 2, 3], [0.6, 0.3, 0.1])
    elif st == "villa":
        nf = pick(rng, [1, 2], [0.45, 0.55])
    else:
        nf = 1
    if ov and st in ("faubourg", "villa", "mas") and 3.0 < ov < 13:
        nf = int(np.clip(round((ov - 1.0) / 2.9), 1, 3))
    fh = [3.15 if st == "core" else 3.0] + [2.85] * (nf - 1)
    if st == "shed":
        fh = [pick(rng, [2.6, 3.0, 3.6])]
    b["nf"], b["fh"] = nf, fh
    # matériau et couleurs
    if st == "core":
        wall = pick(rng, ["Enduit", "PierreMoellons"], [0.88, 0.12])
        facade = pick(rng, OCHRES + CREAMS + PINKS, [3] * len(OCHRES) + [1.5] * len(CREAMS) + [1] * len(PINKS))
    elif st == "faubourg":
        wall = pick(rng, ["Enduit", "PierreMoellons"], [0.8, 0.2])
        facade = pick(rng, OCHRES + CREAMS + PINKS, [2] * len(OCHRES) + [2] * len(CREAMS) + [1] * len(PINKS))
    elif st == "mas":
        wall = pick(rng, ["PierreMoellons", "Enduit"], [0.55, 0.45])
        facade = pick(rng, CREAMS + OCHRES[:4], [2] * len(CREAMS) + [1] * 4)
    elif st == "villa":
        wall = "Enduit"
        facade = pick(rng, CREAMS + OCHRES + PINKS, [2.5] * len(CREAMS) + [1.2] * len(OCHRES) + [1] * len(PINKS))
    elif st in ("church", "belfry"):
        wall = "PierreTaille"
        facade = (255, 255, 255)
    else:
        wall = pick(rng, ["PierreMoellons", "Enduit", "BoisBrut"], [0.55, 0.3, 0.15])
        facade = pick(rng, CREAMS)
    if wall != "Enduit":
        facade = pick(rng, STONE_TINT)
    if b.get("mairie"):
        wall, facade = "Enduit", (234, 206, 150)
    b["wall"], b["facade"] = wall, tuple(int(v) for v in facade)
    b["shutter"] = tuple(int(v) for v in pick(rng, SHUTTERS, SHUTTER_W))
    b["door"] = b["shutter"] if rng.random() < 0.5 else tuple(int(v) for v in pick(rng, DOORS))
    if b.get("mairie"):
        b["shutter"] = (70, 96, 72)
        b["door"] = (70, 96, 72)
    # toiture
    if st == "core":
        rt = "mono" if (Wm < 4.2 and rng.random() < 0.6) or area < 22 else "gable"
    elif st == "faubourg":
        rt = pick(rng, ["gable", "hip", "mono"], [0.8, 0.1, 0.1])
    elif st == "mas":
        rt = pick(rng, ["gable", "hip", "mono"], [0.72, 0.2, 0.08])
    elif st == "villa":
        rt = pick(rng, ["hip", "gable", "flat"], [0.5, 0.46, 0.04])
    elif st in ("shed", "shelter"):
        rt = "mono"
    elif st == "belfry":
        rt = "flat"
    else:
        rt = "gable"
    if area < 12:
        rt = "mono"
    b["roof"] = rt
    b["pitch"] = math.radians(rng.uniform(15.5, 18.5) if rt != "mono" else rng.uniform(13, 16))
    b["genoise"] = {"core": pick(rng, [2, 2, 3]), "faubourg": 2, "mas": pick(rng, [2, 3]), "villa": pick(rng, [1, 2]),
                    "church": 3, "belfry": 0, "shed": 0, "shelter": 0}[st]
    if b.get("mairie"):
        b["genoise"] = 3
    b["overhang"] = 0.3 if b["genoise"] else (0.45 if st in ("villa", "shelter") else 0.25)


for b in blds:
    attributes(b)

# maisons visitables (intérieurs) : candidates réparties dans le village, validées à la génération
VISIT_CANDS = interiors.candidates(blds, CENTER)
VISITED = []
MOVING_DOORS = []   # portes mobiles des maisons visitables
MAX_VISIT = 220


# ------------------------------------------------------------------ analyse des façades
def edge_analysis(b):
    cs = np.array(b["poly"].exterior.coords)[:-1]
    n = len(cs)
    info = []
    others = [k for k in tree.query(b["poly"].buffer(1.2)) if blds[k] is not b]
    other_union = unary_union([blds[k]["poly"].buffer(0.2) for k in others]) if others else None
    prep_o = shapely.prepared.prep(other_union) if other_union is not None else None
    perim = 0.0
    for i in range(n):
        p0, p1 = cs[i], cs[(i + 1) % n]
        d = p1 - p0
        L = float(np.linalg.norm(d))
        u = d / max(L, 1e-9)
        out = np.array([u[1], -u[0]])
        ss = np.arange(0.25, L, 0.5) if L > 0.5 else np.array([L / 2])
        pts = p0 + np.outer(ss, u) + out * 0.45
        if prep_o is not None:
            occ = np.array([prep_o.contains(Point(x, y)) for x, y in pts])
        else:
            occ = np.zeros(len(ss), bool)
        far = p0 + np.outer(ss, u) + out * 3.0
        near = p0 + np.outer(ss, u) + out * 1.2
        street = shapely.contains_xy(street_union, far[:, 0], far[:, 1]) | shapely.contains_xy(street_union, near[:, 0], near[:, 1])
        g_out = gzv(p0[0] + ss * u[0] + out[0] * 0.7, p0[1] + ss * u[1] + out[1] * 0.7)
        info.append(dict(p0=p0, p1=p1, L=L, u=u, out=out, ss=ss, occ=occ, party=occ.mean() > 0.85, street=street.mean() > 0.3 and occ.mean() < 0.7,
                         g_out=g_out, perim=perim))
        perim += L
    return info


# ------------------------------------------------------------------ toit : plans z = A.p + B
def roof_planes(b, eave_z, info):
    rng = b["rng"]
    c_, axis, Lm, Wm = b["ombr"]
    rt = b["roof"]
    t = math.tan(b["pitch"])
    # direction du faîtage
    ridge = axis
    street_edges = [e for e in info if e["street"] and e["L"] > 2.5]
    if b["style"] in ("core", "faubourg") and street_edges:
        e = max(street_edges, key=lambda e: e["L"])
        ridge = e["u"]
    ridge = ridge / np.linalg.norm(ridge)
    q = np.array([-ridge[1], ridge[0]])
    cs = np.array(b["poly"].exterior.coords)[:-1]
    s = (cs - c_) @ q
    r_ = (cs - c_) @ ridge
    s0, s1 = s.min(), s.max()
    r0, r1 = r_.min(), r_.max()
    sm, rm = (s0 + s1) / 2, (r0 + r1) / 2
    W, L = s1 - s0, r1 - r0
    planes = []
    # plan : z = eave + t*(W/2 - (s - sm)) = A.p + B  avec s = q.(p - c)
    def plane_s(sign, halfw, center):
        A = -sign * t * q
        B = eave_z + t * halfw - (-sign * t) * (-(q @ c_)) - (-sign * t) * (-center) * 1.0
        # z = eave + t*halfw - sign*t*((q.p - q.c) - center)
        A = -sign * t * q
        B = eave_z + t * halfw + sign * t * (q @ c_ + center)
        return (A, B)
    def plane_r(sign, halfl, center):
        A = -sign * t * ridge
        B = eave_z + t * halfl + sign * t * (ridge @ c_ + center)
        return (A, B)
    if rt == "gable":
        planes = [plane_s(1, W / 2, sm), plane_s(-1, W / 2, sm)]
    elif rt == "hip":
        planes = [plane_s(1, W / 2, sm), plane_s(-1, W / 2, sm), plane_r(1, L / 2, rm), plane_r(-1, L / 2, rm)]
    elif rt == "mono":
        # côté haut à l'opposé de la rue (ou aléatoire)
        sign = 1
        if street_edges:
            e = max(street_edges, key=lambda e: e["L"])
            if np.dot(e["out"], q) > 0:
                sign = -1
        elif rng.random() < 0.5:
            sign = -1
        # z = eave + t*(s - s_low)  (monte vers le côté haut)
        if sign == 1:
            A = t * q
            B = eave_z - t * (q @ c_ + s0)
        else:
            A = -t * q
            B = eave_z + t * (q @ c_ + s1)
        planes = [(A, B)]
    else:  # flat
        planes = [(np.zeros(2), eave_z + 0.15)]
    return planes, dict(ridge=ridge, q=q, W=W, L=L)


def zroof(planes, x, y):
    return min(float(A @ np.array([x, y]) + B) for A, B in planes)


def clip_halfplane(poly, a, c):
    """Garde a.p + c <= 0."""
    ln = np.linalg.norm(a)
    if ln < 1e-9:
        return poly if c <= 1e-9 else None
    n = a / ln
    c = c / ln
    p0 = -c * n
    d = np.array([-n[1], n[0]])
    M = 5000.0
    hp = Polygon([p0 + d * M, p0 - d * M, p0 - d * M - n * M, p0 + d * M - n * M])
    r = poly.intersection(hp)
    return None if r.is_empty else r


def roof_facets(outline, planes):
    regs = []
    for i, (Ai, Bi) in enumerate(planes):
        R = outline
        for j, (Aj, Bj) in enumerate(planes):
            if i == j or R is None:
                continue
            R = clip_halfplane(R, Ai - Aj, Bi - Bj)
        regs.append(R)
    return regs


# ------------------------------------------------------------------ génération d'un bâtiment
def tri_poly_z(mb, mat, poly, zf, uvf, col, flip=False, zoff=0.0):
    for pg in polys_of(poly):
        if pg.area < 0.01:
            continue
        v2, idx = triangulate(np.array(pg.exterior.coords), [np.array(h.coords) for h in pg.interiors])
        if len(idx) == 0:
            continue
        z = np.array([zf(x, y) for x, y in v2]) + zoff
        P = np.column_stack([v2, z])
        if flip:
            idx = idx[:, [0, 2, 1]]
        n0 = np.cross(P[idx[0, 1]] - P[idx[0, 0]], P[idx[0, 2]] - P[idx[0, 0]])
        mb.add(mat, P, [nrm(n0)], uvf(P), [col], idx)


def gen_building(b, mb, inst):
    rng = b["rng"]
    st = b["style"]
    p = b["poly"]
    cs = np.array(p.exterior.coords)[:-1]
    info = edge_analysis(b)
    b["info"] = info
    # niveaux
    inner = [p.representative_point()] + [Point(x, y) for x, y in cs]
    gs = gzv(cs[:, 0], cs[:, 1])
    gmin, gmax = float(gs.min()), float(gs.max())
    street_edges = [e for e in info if e["street"]]
    if st == "core" and street_edges:
        zref = float(max(e["g_out"].max() for e in street_edges))
        zref = min(zref, gmax)
    else:
        zref = gmax
    zref += 0.05
    base = gmin - 0.8
    eave = zref + sum(b["fh"]) + (0.35 if b["genoise"] else 0.15)
    if st == "church":
        eave = zref + 8.5
    if st == "belfry":
        eave = zref + 14.0
    b["zref"], b["base"], b["eave"] = zref, base, eave
    planes, rinfo = roof_planes(b, eave, info)
    b["planes"] = planes
    wall = b["wall"]
    col = b["facade"] + (255,)
    tw = TILE[wall]
    # ---------------- ouvertures
    openings = layout(b, info) if st not in ("shelter",) else []
    # maison visitable : plan de l'intérieur, porte et fenêtres ouvertes
    pl = None
    if b.get("visit_cand") and len(VISITED) < MAX_VISIT:
        pl = interiors.plan(b, info, openings, gz)
        if pl:
            interiors.apply_openings(b, pl, openings, info)
            b["visit"] = True
            VISITED.append(b)
    by_edge = collections.defaultdict(list)
    for o in openings:
        by_edge[o["edge"]].append(o)
    # ---------------- murs
    if st != "shelter":
        for ei, e in enumerate(info):
            p0, p1, L, u = e["p0"], e["p1"], e["L"], e["u"]
            ts = [0.0, 1.0]
            for i in range(len(planes)):
                for j in range(i + 1, len(planes)):
                    dA = planes[i][0] - planes[j][0]
                    dB = planes[i][1] - planes[j][1]
                    den = dA @ (p1 - p0)
                    if abs(den) > 1e-9:
                        tt = -(dA @ p0 + dB) / den
                        if 0.001 < tt < 0.999:
                            ts.append(tt)
            ts = sorted(set(ts))
            top = [(tt * L, zroof(planes, *(p0 + tt * (p1 - p0))) - 0.03) for tt in ts]
            outer = [(0.0, base), (L, base)] + [top[k] for k in range(len(top) - 1, -1, -1)]
            holes = []
            for o in by_edge.get(ei, []):
                holes.append([(o["s0"], o["z0"]), (o["s1"], o["z0"]), (o["s1"], o["z1"]), (o["s0"], o["z1"])])
            origin = np.array([p0[0], p0[1], 0.0])
            e1 = np.array([u[0], u[1], 0.0])
            e2 = np.array([0.0, 0.0, 1.0])
            per = e["perim"]
            planar_polygon(mb, wall, outer, holes, origin, e1, e2,
                           lambda v2, P, per=per: np.stack([(per + v2[:, 0]) / tw, -v2[:, 1] / tw], -1), col)
            # tableaux des ouvertures (profondeur vers l'intérieur)
            inward = np.array([-e["out"][0], -e["out"][1], 0.0])
            D = interiors.T_WALL if pl else 0.22
            for o in by_edge.get(ei, []):
                a0 = origin + e1 * o["s0"]
                a1 = origin + e1 * o["s1"]
                z0, z1 = o["z0"], o["z1"]
                for (pa, pb, za, zb) in ((a0, a0, z0, z1), (a1, a1, z1, z0)):
                    A = pa + e2 * za
                    B = pb + e2 * zb
                    mb.quad(wall, A, B, B + inward * D, A + inward * D, [(0, 0), (0, (zb - za) / tw), (D / tw, (zb - za) / tw), (D / tw, 0)], col)
                mb.quad(wall, a0 + e2 * z1, a1 + e2 * z1, a1 + e2 * z1 + inward * D, a0 + e2 * z1 + inward * D, [(0, 0), (o["s1"] / tw - o["s0"] / tw, 0), (o["s1"] / tw - o["s0"] / tw, D / tw), (0, D / tw)], col)
                mb.quad(wall, a1 + e2 * z0, a0 + e2 * z0, a0 + e2 * z0 + inward * D, a1 + e2 * z0 + inward * D, [(0, 0), (o["s1"] / tw - o["s0"] / tw, 0), (o["s1"] / tw - o["s0"] / tw, D / tw), (0, D / tw)], col)
                # fond sombre derrière les vitres (pas d'intérieur modélisé)
                back = inward * 0.6
                if not pl or not o.get("visit"):
                    mb.quad("Verre", a1 + e2 * z0 + back, a0 + e2 * z0 + back, a0 + e2 * z1 + back, a1 + e2 * z1 + back, [(0, 0), (1, 0), (1, 1), (0, 1)], WHITE, n=-inward)
                # instance du module
                yaw = math.atan2(u[1], u[0])
                sc = (o["s1"] - o["s0"]) / OPENINGS[o["type"]][0]
                pos = origin + e1 * ((o["s0"] + o["s1"]) / 2) + e2 * z0
                colr = o.get("color", b["shutter"])
                inst[o["type"]].append((pos[0], pos[1], pos[2], yaw, sc, 1.0, 1.0, *colr))
                if o["type"] in DOOR_LEAF:
                    # vantail mobile (acteur porte dans Unreal) : charnière dans le repère du module, mise à l'échelle de l'ouverture
                    _, hx0, hy = LEAVES[DOOR_LEAF[o["type"]]]
                    hx = sc * hx0
                    cy_, sy_ = math.cos(yaw), math.sin(yaw)
                    MOVING_DOORS.append(dict(x=float(pos[0] + hx * cy_ - hy * sy_), y=float(pos[1] + hx * sy_ + hy * cy_), z=float(pos[2]), yaw=float(yaw),
                                      sx=float(sc), leaf=DOOR_LEAF[o["type"]], house=b["id"], color=[int(c_) for c_ in colr]))
                for extra in o.get("extras", []):
                    kind, dz, dx, ecol = extra
                    pe = pos + e1 * dx + e2 * dz
                    inst[kind].append((pe[0], pe[1], pe[2], yaw, 1.0, 1.0, 1.0, *ecol))
    else:
        # auvent : poteaux
        for x, y in cs:
            tube(mb, "BoisBrut", [(x, y, gz(x, y) - 0.2), (x, y, zroof(planes, x, y) - 0.05)], 0.09, segs=6)
    # ---------------- toit
    ov = b["overhang"]
    outline = p.buffer(ov, join_style=2, mitre_limit=2.5)
    regs = roof_facets(outline, planes)
    roofmat = "TuilesCanal" if b["roof"] != "flat" else "Dallage"
    tr = TILE[roofmat]
    for (A, B), R in zip(planes, regs):
        if R is None:
            continue
        gA = np.linalg.norm(A)
        if gA > 1e-6:
            g = -A / gA
            perp = np.array([-g[1], g[0]])
            cp = math.cos(math.atan(gA))
            uvf = lambda P, g=g, perp=perp, cp=cp: np.stack([(P[:, :2] @ perp) / tr, (P[:, :2] @ g) / cp / tr], -1)
        else:
            uvf = lambda P: np.stack([P[:, 0] / tr, -P[:, 1] / tr], -1)
        zf = lambda x, y, A=A, B=B: float(A @ np.array([x, y]) + B)
        tri_poly_z(mb, roofmat, R, zf, uvf, WHITE)
        # sous-face du débord
        S = R.difference(p)
        if not S.is_empty:
            tri_poly_z(mb, wall if wall != "PierreTaille" else "Enduit", S, zf,
                       lambda P: np.stack([P[:, 0] / 3, P[:, 1] / 3], -1), (246, 238, 222, 255), flip=True, zoff=-0.07)
    # bord de toit : lèvre de tuiles (égout) et rive maçonnée (pignon)
    oc = np.array(outline.exterior.coords)
    for k in range(len(oc) - 1):
        a, c2 = oc[k], oc[k + 1]
        za, zb = zroof(planes, *a), zroof(planes, *c2)
        d = c2 - a
        Ld = np.linalg.norm(d)
        if Ld < 0.05:
            continue
        rake = abs(za - zb) > 0.05
        h = 0.14 if rake else 0.06
        mat = (wall if wall == "Enduit" else "Enduit") if rake else "TerreCuite"
        cc = (246, 238, 222, 255) if rake else WHITE
        if b["roof"] == "flat":
            h, mat = 0.9, wall
            cc = col
        A3 = (a[0], a[1], za - h)
        B3 = (c2[0], c2[1], zb - h)
        C3 = (c2[0], c2[1], zb + (0.02 if not rake else 0.0) + (0.0 if b["roof"] != "flat" else h * 0.9))
        D3 = (a[0], a[1], za + (0.02 if not rake else 0.0) + (0.0 if b["roof"] != "flat" else h * 0.9))
        mb.quad(mat, A3, B3, C3, D3, [(0, h), (Ld, h), (Ld, 0), (0, 0)], cc)
    # faîtage et arêtiers (tuiles demi-rondes)
    if len(planes) > 1:
        for i in range(len(planes)):
            for j in range(i + 1, len(planes)):
                if regs[i] is None or regs[j] is None:
                    continue
                sh = regs[i].boundary.intersection(regs[j].boundary)
                for ln in lines_of(sh) if not sh.is_empty else []:
                    if ln.length < 0.3:
                        continue
                    n_s = max(2, int(ln.length / 0.5) + 1)
                    pts2 = [ln.interpolate(k / (n_s - 1), normalized=True) for k in range(n_s)]
                    pts3 = [(q.x, q.y, zroof(planes, q.x, q.y) + 0.02) for q in pts2]
                    tube(mb, "TuilesCanal", pts3, 0.11, segs=6, arc=math.pi, arc0=-math.pi / 2, u_tile=2.0, v_tile=2.0)
    # génoise
    if b["genoise"] and st != "shelter":
        genoise(b, mb, info, planes)
    # cheminées
    if b["roof"] in ("gable", "hip") and st in ("core", "faubourg", "mas", "villa") and rng.random() < {"core": 0.65, "faubourg": 0.6, "mas": 0.8, "villa": 0.45}[st]:
        for k in range(1 if st != "mas" else pick(rng, [1, 2])):
            chimney(b, mb, rinfo, planes)
    # plaques, enseignes, mairie
    decorations(b, mb, info, openings, inst)
    # intérieur de la maison visitable
    if pl:
        interiors.build(b, pl, mb, inst, rng)
    # données pour l'habillage (barricades, inscriptions) et le parkour (échelles, planches entre toits)
    b["meta"] = dict(id=b["id"], style=st, poly=np.array(p.exterior.coords)[:-1].tolist(), zref=float(b["zref"]), eave=float(eave),
                     nf=int(b["nf"]), roof=b["roof"], visit=bool(pl), shop=b.get("shop"), mairie=bool(b.get("mairie")),
                     planes=[(A.tolist(), float(B_)) for A, B_ in planes],
                     edges=[dict(p0=e["p0"].tolist(), p1=e["p1"].tolist(), out=e["out"].tolist(), L=float(e["L"]), street=bool(e["street"]),
                                 party=bool(e["party"]), g=float(e["g_out"].min()) if len(e["g_out"]) else float(b["zref"])) for e in info],
                     openings=[dict(edge=o["edge"], type=o["type"], s0=float(o["s0"]), s1=float(o["s1"]), z0=float(o["z0"]), z1=float(o["z1"]))
                               for o in openings])


def genoise(b, mb, info, planes):
    rows = b["genoise"]
    ov = b["overhang"]
    hr = 0.112
    t = math.tan(b["pitch"])
    col = b["facade"] + (255,)
    for e in info:
        if e["party"] or e["L"] < 0.8:
            continue
        p0, p1 = e["p0"], e["p1"]
        z0, z1 = zroof(planes, *p0), zroof(planes, *p1)
        if abs(z0 - z1) > 0.05:
            continue
        # vérifie que c'est bien un égout (le toit descend vers l'extérieur)
        mid = (p0 + p1) / 2
        if zroof(planes, *(mid + e["out"] * 0.2)) > zroof(planes, *mid) - 0.01:
            continue
        ze = min(z0, z1)
        u, out = e["u"], e["out"]
        L = e["L"]
        for k in range(rows):
            pk = ov * (rows - k) / rows - 0.02
            ztop = ze - t * pk - 0.015 - k * hr
            zbot = ztop - hr
            ext = pk
            a = p0 - u * ext + out * pk
            c2 = p1 + u * ext + out * pk
            uv0 = -(e["perim"] - ext) / 1.12
            uv1 = uv0 + (L + 2 * ext) / 1.12
            vr0, vr1 = k / 10.0, (k + 1) / 10.0
            mb.quad("Genoise", (a[0], a[1], zbot), (c2[0], c2[1], zbot), (c2[0], c2[1], ztop), (a[0], a[1], ztop),
                    [(uv0, vr1), (uv1, vr1), (uv1, vr0), (uv0, vr0)], WHITE)
            # dessous de la rangée
            inner = ov * (rows - k - 1) / rows - 0.02 if k < rows - 1 else 0.0
            a2 = p0 - u * ext + out * inner
            c3 = p1 + u * ext + out * inner
            mb.quad("Enduit", (a2[0], a2[1], zbot), (c3[0], c3[1], zbot), (c2[0], c2[1], zbot), (a[0], a[1], zbot),
                    [(0, 0), (L / 3, 0), (L / 3, 0.05), (0, 0.05)], col)


def chimney(b, mb, rinfo, planes):
    rng = b["rng"]
    p = b["poly"]
    c_, axis, Lm, Wm = b["ombr"]
    ridge, q = rinfo["ridge"], rinfo["q"]
    for _ in range(12):
        pt = np.array([p.centroid.x, p.centroid.y]) + ridge * rng.uniform(-0.35, 0.35) * rinfo["L"] + q * rng.uniform(-0.25, 0.25) * rinfo["W"]
        if p.buffer(-0.6).contains(Point(*pt)):
            break
    else:
        return
    sx, sy = rng.uniform(0.5, 0.7), rng.uniform(0.4, 0.55)
    zr = zroof(planes, *pt)
    ztop_roof = max(zroof(planes, *(pt + d)) for d in (ridge * sx, -ridge * sx, q * sy, -q * sy))
    zc = max(ztop_roof, zr) + rng.uniform(0.7, 1.2)
    yaw = math.atan2(ridge[1], ridge[0])
    zb = zr - 0.6
    col = tuple(min(255, int(v * 1.02 + 8)) for v in b["facade"]) + (255,)
    if rng.random() < 0.3:
        # souche en briques apparentes au-dessus du toit, enduit en dessous
        zr_top = max(ztop_roof, zr) + 0.05
        box(mb, "Enduit", (pt[0], pt[1], (zb + zr_top) / 2), (sx, sy, zr_top - zb), yaw=yaw, col=col, uv_scale=3.0)
        box(mb, "Brique", (pt[0], pt[1], (zr_top + zc) / 2), (sx + 0.01, sy + 0.01, zc - zr_top), yaw=yaw, uv_scale=1.0)
    else:
        box(mb, "Enduit", (pt[0], pt[1], (zb + zc) / 2), (sx, sy, zc - zb), yaw=yaw, col=col, uv_scale=3.0)
    # chapeau : deux tuiles en bâtière
    for sgn in (-1, 1):
        cxy = pt + q * sgn * sy * 0.28
        box(mb, "TuilesCanal", (cxy[0], cxy[1], zc + 0.12), (sx + 0.12, sy * 0.62, 0.035), yaw=yaw, uv_scale=2.0, pitch=-sgn * math.radians(32))


# ------------------------------------------------------------------ disposition des ouvertures
WIN_CORE = (["Fenetre_Ouverte", "Fenetre_Persiennes", "Fenetre_Fermee", "Fenetre_MiClose", "Fenetre_Nue"], [45, 20, 20, 10, 5])
WIN_VILLA = (["Fenetre_Persiennes", "Fenetre_Ouverte", "Fenetre_Fermee", "Fenetre_Nue"], [40, 40, 10, 10])
WIN_MAS = (["Fenetre_Ouverte", "Fenetre_Fermee", "Fenetre_MiClose", "Fenetre_Persiennes"], [50, 30, 10, 10])


def layout(b, info):
    rng = b["rng"]
    st = b["style"]
    if st in ("church", "belfry"):
        return landmark_openings(b, info)
    zref, eave = b["zref"], b["eave"]
    planes = b["planes"]
    fh = b["fh"]
    levels = [zref + sum(fh[:k]) for k in range(len(fh))]
    wins = WIN_CORE if st in ("core", "faubourg") else (WIN_MAS if st == "mas" else WIN_VILLA)
    bay = {"core": 2.35, "faubourg": 2.6, "mas": 3.0, "villa": 3.1, "shed": 3.0}.get(st, 2.8)
    margin = {"core": 0.45, "faubourg": 0.6}.get(st, 0.8)
    out = []
    door_done = False
    shop_done = False
    # façade principale : la plus longue sur rue, sinon la plus longue libre
    free_edges = [i for i, e in enumerate(info) if not e["party"] and e["L"] > 1.2]
    if not free_edges:
        return out
    street_ids = [i for i in free_edges if info[i]["street"]]
    # façade principale : longue, sur rue, et à peu près de plain-pied
    flat_w = 6.0 if b.get("mairie") else 2.5
    main = max(street_ids or free_edges, key=lambda i: info[i]["L"] - flat_w * float(info[i]["g_out"].max() - info[i]["g_out"].min()))
    old = st in ("core", "faubourg", "mas")
    for ei in free_edges:
        e = info[ei]
        L = e["L"]
        usable = L - 2 * margin
        if usable < 0.8:
            continue
        bay_e = bay if (e["street"] or ei == main) else bay * 1.2
        nb = max(1, int(round(usable / bay_e)))
        if L < 2.0:
            nb = 1
        centers = [margin + usable * (j + 0.5) / nb for j in range(nb)]
        if old:
            centers = [c + rng.uniform(-0.15, 0.15) for c in centers]
        is_main = ei == main
        is_street = e["street"]
        placed = []
        skip_p = 0.12 if (is_main or is_street) else 0.45

        def ok(s0, s1, z0, z1):
            if s0 < 0.25 or s1 > L - 0.25:
                return False
            k0, k1 = int(max(0, (s0 - 0.25) / 0.5)), int(min(len(e["occ"]) - 1, (s1 - 0.25) / 0.5))
            if e["occ"][k0:k1 + 1].any():
                return False
            ztop = min(zroof(planes, *(e["p0"] + e["u"] * s)) for s in (s0, s1))
            if z1 > ztop - (0.5 if b["genoise"] else 0.3):
                return False
            for (a0, a1, c0, c1) in placed:
                if s0 < a1 + 0.3 and s1 > a0 - 0.3 and z0 < c1 + 0.3 and z1 > c0 - 0.3:
                    return False
            return True

        def ground_at(s0, s1):
            ks = [int(np.clip(s / 0.5, 0, len(e["g_out"]) - 1)) for s in np.linspace(s0, s1, 4)]
            g = e["g_out"][ks]
            return float(g.min()), float(g.max())

        def add(tp, s, z0, **kw):
            w, h = OPENINGS[tp]
            scale = kw.pop("scale", 1.0)
            w *= scale
            s0, s1 = s - w / 2, s + w / 2
            z1 = z0 + h
            if not ok(s0, s1, z0, z1):
                return False
            placed.append((s0, s1, z0, z1))
            out.append(dict(edge=ei, type=tp, s0=s0, s1=s1, z0=z0, z1=z1, **kw))
            return True

        # rez-de-chaussée : porte / vitrine / remise
        shop_bay = None
        if is_main and b.get("shop") and not shop_done:
            j = int(np.argmin([abs(c - L / 2) for c in centers]))
            s = centers[j] if nb > 1 else L / 2
            g0, g1 = ground_at(s - 1.3, s + 1.3)
            z0 = g1 + 0.04
            if g1 - g0 < 0.8 and z0 < levels[0] + 0.8:
                tp = pick(rng, ["Vitrine", "Vitrine_SansStore"], [0.6, 0.4])
                sc = float(np.clip((min(L - 1.0, 3.2)) / 2.6, 0.85, 1.25))
                aw = tuple(int(v) for v in pick(rng, AWNINGS))
                if add(tp, s, z0, scale=sc, color=aw if tp == "Vitrine" else b["door"], shop=b["shop"]):
                    shop_done = True
                    door_done = True
                    shop_bay = j
        for j, s in enumerate(centers):
            if j == shop_bay:
                continue
            g0, g1 = ground_at(s - 0.6, s + 0.6)
            if (is_main or (st in ("mas", "villa") and not door_done)) and not door_done and g1 - g0 < 0.5 and abs(g1 - levels[0]) < 1.2:
                tp = "Remise" if (old and L > 5.5 and rng.random() < 0.2 and st != "villa") else pick(rng, ["Porte", "Porte_Simple"], [0.7, 0.3])
                if add(tp, s, g1 + 0.03, color=b["door"]):
                    door_done = True
                    if b.get("mairie"):
                        b["mairie_door"] = (ei, s, g1 + 0.03)
                    continue
            if is_street and old and st == "core" and rng.random() < 0.18 and L > 5 and g1 - g0 < 0.4 and abs(g1 - levels[0]) < 1.2:
                if add("Remise", s, g1 + 0.03, color=pick(rng, DOORS)):
                    continue
            # fenêtre de rez-de-chaussée
            z0 = max(levels[0] + 0.95, g1 + 0.9)
            if z0 < levels[0] + 1.6:
                tp = "Fenetre_Barreaux" if (is_street and st == "core" and rng.random() < 0.6) else pick(rng, *wins)
                add(tp, s, z0)
        # étages
        for k in range(1, len(levels)):
            top_floor = k == len(levels) - 1
            for j, s in enumerate(centers):
                if rng.random() < (skip_p if old else skip_p * 0.6):
                    continue
                z0 = levels[k] + 0.9
                if top_floor and st == "core" and rng.random() < 0.28:
                    add("Fenestron", s, levels[k] + 1.1)
                    continue
                if k == 1 and is_main and not b.get("shop") and rng.random() < (0.35 if b.get("mairie") else 0.15) and st in ("core", "faubourg", "villa"):
                    if add("PorteFenetre_Balcon", s, levels[k] + 0.05):
                        continue
                tp = pick(rng, *wins)
                extras = []
                if st in ("core", "faubourg") and rng.random() < 0.12:
                    extras.append(("Jardiniere", 0.0, 0.0, (255, 255, 255)))
                add(tp, s, z0, extras=extras)
        # niveau inférieur côté aval (villages perchés)
        gmin = float(e["g_out"].min())
        if gmin < levels[0] - 2.6 and old:
            zl = levels[0] - 2.9
            for j, s in enumerate(centers):
                g0, g1 = ground_at(s - 0.6, s + 0.6)
                if abs(g1 - zl) < 0.6 and rng.random() < 0.5:
                    add(pick(rng, ["Porte_Simple", "Remise"], [0.7, 0.3]), s, g1 + 0.03, color=pick(rng, DOORS))
                elif g1 < zl + 0.2:
                    add("Fenetre_Barreaux", s, zl + 1.0)
        # petite fenêtre isolée sur les murs courts
        if nb == 1 and not placed and L > 1.3 and len(levels) > 1:
            add("Fenestron", L / 2, levels[-1] + 1.0)
    return out


def landmark_openings(b, info):
    """Église et beffroi : grande porte + oculus / baies simples ; le reste est traité dans landmarks()."""
    out = []
    return out


# ------------------------------------------------------------------ enseignes, plaques, lanternes, pots
def decorations(b, mb, info, openings, inst):
    rng = b["rng"]
    st = b["style"]
    for o in openings:
        e = info[o["edge"]]
        origin = np.array([e["p0"][0], e["p0"][1], 0.0])
        e1 = np.array([e["u"][0], e["u"][1], 0.0])
        out3 = np.array([e["out"][0], e["out"][1], 0.0])
        sc = (o["s0"] + o["s1"]) / 2
        if o.get("shop") and o["shop"] and ("shop_" + o["shop"]) in SIGNS:
            key = "shop_" + o["shop"]
            ztop = o["z1"] + (0.75 if o["type"] == "Vitrine" else 0.28)
            c = origin + e1 * sc + out3 * 0.05 + np.array([0, 0, ztop + 0.2])
            rect_sign(mb, "Enseignes", c, min(2.4, o["s1"] - o["s0"] + 0.2), 0.45, out3, SIGNS[key], WHITE, thickness=0.04, back_mat="BoisPeint")
            if o["shop"] == "pharmacie":
                # croix verte en drapeau
                cc = origin + e1 * (o["s1"] + 0.5) + out3 * 0.45 + np.array([0, 0, o["z1"] + 0.5])
                n2 = np.array([e["u"][0], e["u"][1], 0.0])
                rect_sign(mb, "Enseignes", cc, 0.6, 0.6, n2, SIGNS["croix"])
                rect_sign(mb, "Enseignes", cc, 0.6, 0.6, -n2, SIGNS["croix"])
            if o["shop"] in ("restaurant1", "restaurant2", "restaurant3", "restaurant4", "restaurant5", "restaurant6", "restaurant7", "restaurant8", "cafe1", "cafe2", "bar", "pizzeria", "glaces"):
                terrace(b, e, o, inst)
            if o["shop"] == "bar":
                cc = origin + e1 * (o["s0"] - 0.45) + out3 * 0.3 + np.array([0, 0, o["z1"] + 0.3])
                n2 = np.array([e["u"][0], e["u"][1], 0.0])
                rect_sign(mb, "Enseignes", cc, 0.35, 0.7, n2, SIGNS["tabac"])
                rect_sign(mb, "Enseignes", cc, 0.35, 0.7, -n2, SIGNS["tabac"])
        if o["type"] in ("Porte", "Porte_Simple") and st in ("core", "faubourg", "mas", "villa") and rng.random() < 0.45:
            for sd in (-1, 1):
                if rng.random() < 0.7:
                    pp = origin + e1 * (sc + sd * 0.85) + out3 * 0.4
                    g = gz(pp[0], pp[1])
                    inst[pick(rng, ["Pot_Geranium", "Pot_Rose", "Pot_Bougainvillier"], [0.5, 0.3, 0.2])].append((pp[0], pp[1], g - 0.03, rng.uniform(0, 6.28), 1.0, 1.0, 1.0, 255, 255, 255))
    # lanternes sur les façades de rue du vieux village
    if st in ("core", "faubourg"):
        for ei, e in enumerate(info):
            if not e["street"] or e["party"] or e["L"] < 4.0:
                continue
            if rng.random() < (0.45 if st == "core" else 0.2):
                s = e["L"] * rng.uniform(0.3, 0.7)
                clash = any(True for o in openings if o["edge"] == ei and o["s0"] - 0.5 < s < o["s1"] + 0.5 and o["z1"] > b["zref"] + 2.0 and o["z0"] < b["zref"] + 3.9)
                if clash:
                    continue
                p = e["p0"] + e["u"] * s
                z = b["zref"] + 3.0
                if b["eave"] - z < 1.0:
                    continue
                inst["Lanterne_Murale"].append((p[0], p[1], z, math.atan2(e["u"][1], e["u"][0]), 1.0, 1.0, 1.0, 255, 255, 255))
    # mairie
    if b.get("mairie") and b.get("mairie_door"):
        ei, s, z0 = b["mairie_door"]
        e = info[ei]
        origin = np.array([e["p0"][0], e["p0"][1], 0.0])
        e1 = np.array([e["u"][0], e["u"][1], 0.0])
        out3 = np.array([e["out"][0], e["out"][1], 0.0])
        c = origin + e1 * s + out3 * 0.03 + np.array([0, 0, z0 + 2.75])
        rect_sign(mb, "Enseignes", c, 1.7, 0.32, out3, SIGNS["mairie"], WHITE, thickness=0.05, back_mat="PierreTaille")
        c2 = c + np.array([0, 0, 3.0])
        rect_sign(mb, "Enseignes", c2, 3.2, 0.22, out3, SIGNS["devise"], WHITE, thickness=0.04, back_mat="PierreTaille")
        yaw = math.atan2(e["u"][1], e["u"][0])
        for dx, fl in ((-0.9, "drapeau_fr"), (0.9, "drapeau_eu")):
            pp = origin + e1 * (s + dx) + np.array([0, 0, z0 + 5.2])
            inst["Drapeau_" + ("FR" if fl == "drapeau_fr" else "EU")].append((pp[0], pp[1], pp[2], yaw, 1.0, 1.0, 1.0, 255, 255, 255))


def terrace(b, e, o, inst):
    """Terrasse de café : tables, chaises, parasols devant la vitrine si l'espace public le permet."""
    rng = b["rng"]
    sc = (o["s0"] + o["s1"]) / 2
    base = e["p0"] + e["u"] * sc
    yaw = math.atan2(e["u"][1], e["u"][0])
    par_col = pick(rng, [(226, 214, 180), (120, 36, 40), (40, 80, 60), (200, 150, 60)])
    chair_col = pick(rng, [(40, 80, 60), (120, 36, 40), (60, 60, 60), (200, 170, 90), (60, 90, 130)])
    n = 0
    for row in (2.2, 4.0):
        for off in (-2.2, 0.0, 2.2):
            p = base + e["out"] * row + e["u"] * off
            if not street_union.contains(Point(*p)) or tree.query(Point(*p).buffer(1.2)).size:
                continue
            if row > 3 and rng.random() < 0.5:
                continue
            g = gz(*p)
            inst["Table_Cafe"].append((p[0], p[1], g, rng.uniform(0, 6.28), 1, 1, 1, 255, 255, 255))
            for k in range(rng.integers(2, 4)):
                a = rng.uniform(0, 2 * math.pi)
                cp = p + np.array([math.cos(a), math.sin(a)]) * 0.62
                inst["Chaise_Bistrot"].append((cp[0], cp[1], gz(*cp), a + math.pi / 2 + rng.normal(0, 0.3), 1, 1, 1, *chair_col))
            if rng.random() < 0.6:
                inst["Parasol"].append((p[0], p[1], g, 0.0, 1, 1, 1, *par_col))
            n += 1
    return n


# ------------------------------------------------------------------ monuments
def landmark(b, mb, inst):
    st = b["style"]
    p = b["poly"]
    info = edge_analysis(b)
    cs = np.array(p.exterior.coords)[:-1]
    gs = gzv(cs[:, 0], cs[:, 1])
    zref = float(gs.max()) + 0.05
    base = float(gs.min()) - 0.8
    c_, axis, Lm, Wm = b["ombr"]
    if st == "belfry":
        eave = zref + 15.5
        planes = [(np.zeros(2), eave)]
        b["roof"] = "flat"
    else:
        eave = zref + 8.8
        b["pitch"] = math.radians(20)
        b["roof"] = "gable"
        b["style"] = "church"
        planes, _ = roof_planes(b, eave, info)
    b["zref"], b["base"], b["eave"], b["planes"] = zref, base, eave, planes
    wall = "PierreTaille"
    tw = TILE[wall]
    # église visitable : portail et hautes fenêtres réellement percés
    holes_of = collections.defaultdict(list)
    church_open = []
    if st != "belfry":
        short = sorted(info, key=lambda e: e["L"])[:2]
        fac = max(short, key=lambda e: (1 if e["street"] else 0, -np.linalg.norm((e["p0"] + e["p1"]) / 2 - np.array([-19.0, 21.0]))))
        fi = next(i for i, e in enumerate(info) if e is fac)
        gdoor = float(fac["g_out"].max())
        Lf = fac["L"]
        arch = [(Lf / 2 + 0.9 * math.cos(t_), gdoor + 3.2 + 0.9 * math.sin(t_)) for t_ in np.linspace(0, math.pi, 9)]
        holes_of[fi].append([(Lf / 2 - 0.9, gdoor), (Lf / 2 + 0.9, gdoor)] + arch[1:-1] + [])
        holes_of[fi][-1] = [(Lf / 2 - 0.9, gdoor), (Lf / 2 + 0.9, gdoor), (Lf / 2 + 0.9, gdoor + 3.2)] + arch[1:-1] + [(Lf / 2 - 0.9, gdoor + 3.2)]
        church_open.append((fi, Lf / 2, 1.8, gdoor, gdoor + 3.2))
        for e in sorted(info, key=lambda e: -e["L"])[:2]:
            if e["party"]:
                continue
            ei = next(i for i, e2 in enumerate(info) if e2 is e)
            nb = int(e["L"] / 5.0)
            for k in range(nb):
                sc_ = e["L"] * (k + 0.5) / nb
                holes_of[ei].append([(sc_ - 0.275, zref + 4.1), (sc_ + 0.275, zref + 4.1), (sc_ + 0.275, zref + 5.9), (sc_ - 0.275, zref + 5.9)])
                church_open.append((ei, sc_, 0.55, zref + 4.1, zref + 5.9))
    # murs pleins
    for ei_, e in enumerate(info):
        p0, p1, L, u = e["p0"], e["p1"], e["L"], e["u"]
        ts = [0.0, 1.0]
        for i in range(len(planes)):
            for j in range(i + 1, len(planes)):
                dA = planes[i][0] - planes[j][0]
                dB = planes[i][1] - planes[j][1]
                den = dA @ (p1 - p0)
                if abs(den) > 1e-9:
                    tt = -(dA @ p0 + dB) / den
                    if 0.001 < tt < 0.999:
                        ts.append(tt)
        ts = sorted(set(ts))
        top = [(tt * L, zroof(planes, *(p0 + tt * (p1 - p0))) - 0.03) for tt in ts]
        outer = [(0.0, base), (L, base)] + top[::-1]
        planar_polygon(mb, wall, outer, holes_of.get(ei_, []), np.array([p0[0], p0[1], 0.0]), np.array([u[0], u[1], 0.0]), np.array([0, 0, 1.0]),
                       lambda v2, P, per=e["perim"]: np.stack([(per + v2[:, 0]) / tw, -v2[:, 1] / tw], -1), WHITE)
    if st == "belfry":
        # corniche + campanile en fer forgé + cloche + horloge
        ctr = np.array([p.centroid.x, p.centroid.y])
        out = p.buffer(0.25, join_style=2)
        tri_poly_z(mb, "PierreTaille", out, lambda x, y: eave + 0.3, lambda P: np.stack([P[:, 0] / 3, P[:, 1] / 3], -1), WHITE)
        oc = np.array(out.exterior.coords)
        for k in range(len(oc) - 1):
            a, c2 = oc[k], oc[k + 1]
            mb.quad("PierreTaille", (a[0], a[1], eave - 0.1), (c2[0], c2[1], eave - 0.1), (c2[0], c2[1], eave + 0.3), (a[0], a[1], eave + 0.3), [(0, 0.13), (1, 0.13), (1, 0), (0, 0)], WHITE)
        campanile(mb, ctr, eave + 0.3, 1.6, 3.2)
        # horloge sur la face la plus longue donnant sur la rue
        e = max(info, key=lambda e: e["L"] + (5 if e["street"] else 0))
        mid = (e["p0"] + e["p1"]) / 2
        cpt = np.array([mid[0], mid[1], eave - 1.8]) + np.array([e["out"][0], e["out"][1], 0]) * 0.04
        disk(mb, "Enseignes", cpt, 0.85, (e["out"][0], e["out"][1], 0), (0, 0, 1), 28, WHITE, SIGNS["horloge"])
        return
    # église : toit, génoise, clocher carré à l'extrémité proche de la place, portail, oculus, contreforts
    b["genoise"], b["overhang"], b["facade"] = 3, 0.35, (240, 232, 214)
    ov = b["overhang"]
    outline = p.buffer(ov, join_style=2, mitre_limit=2.5)
    regs = roof_facets(outline, planes)
    for (A, B), R in zip(planes, regs):
        if R is None:
            continue
        g = -A / max(np.linalg.norm(A), 1e-9)
        perp = np.array([-g[1], g[0]])
        cp = math.cos(math.atan(np.linalg.norm(A)))
        tri_poly_z(mb, "TuilesCanal", R, lambda x, y, A=A, B=B: float(A @ np.array([x, y]) + B),
                   lambda P, g=g, perp=perp, cp=cp: np.stack([(P[:, :2] @ perp) / 2, (P[:, :2] @ g) / cp / 2], -1), WHITE)
    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            sh = regs[i].boundary.intersection(regs[j].boundary) if regs[i] is not None and regs[j] is not None else None
            for ln in lines_of(sh) if sh is not None and not sh.is_empty else []:
                if ln.length > 0.3:
                    pts3 = [(q.x, q.y, zroof(planes, q.x, q.y) + 0.02) for q in (ln.interpolate(k / 8, normalized=True) for k in range(9))]
                    tube(mb, "TuilesCanal", pts3, 0.13, segs=6, arc=math.pi, arc0=-math.pi / 2, u_tile=2, v_tile=2)
    genoise(b, mb, info, planes)
    # façade = petit côté le plus proche d'une rue / place
    short = sorted(info, key=lambda e: e["L"])[:2]
    fac = max(short, key=lambda e: (1 if e["street"] else 0, -np.linalg.norm((e["p0"] + e["p1"]) / 2 - np.array([-19.0, 21.0]))))
    mid = (fac["p0"] + fac["p1"]) / 2
    out3 = np.array([fac["out"][0], fac["out"][1], 0.0])
    u3 = np.array([fac["u"][0], fac["u"][1], 0.0])
    gdoor = float(fac["g_out"].max())
    # portail : vantaux + arc en pierre + marches
    yaw = math.atan2(fac["u"][1], fac["u"][0])
    dc = np.array([mid[0], mid[1], gdoor])
    # portail à deux vantaux mobiles (acteurs porte dans Unreal), charnières de part et d'autre de l'ouverture
    for sgn_, leaf_ in ((-1, "Vantail_EgliseG"), (1, "Vantail_EgliseD")):
        hp = mid + fac["u"] * sgn_ * 0.9
        MOVING_DOORS.append(dict(x=float(hp[0]), y=float(hp[1]), z=float(gdoor), yaw=float(yaw), sx=1.0, leaf=leaf_, house=b["id"],
                                 color=[96, 66, 44], open_sign=1 if sgn_ < 0 else -1))
    church_interior(b, mb, inst, info, fac, gdoor, church_open, eave)
    arc_pts = [dc + out3 * 0.12 + u3 * (1.15 * math.cos(a)) + np.array([0, 0, 3.2 + 1.15 * math.sin(a)]) for a in np.linspace(0, math.pi, 13)]
    tube(mb, "PierreTaille", arc_pts, 0.16, segs=6, u_tile=3, v_tile=3)
    for sd in (-1, 1):
        box(mb, "PierreTaille", dc + out3 * 0.12 + u3 * sd * 1.15 + np.array([0, 0, 1.6]), (0.32, 0.25, 3.2), yaw=yaw, uv_scale=3)
    for k in range(3):
        box(mb, "PierreTaille", dc + out3 * (0.5 + 0.35 * (2 - k)) + np.array([0, 0, -0.08 - 0.16 * k]), (3.4 + 0.5 * k, 0.4 + 0.35 * k * 0.0, 0.16), yaw=yaw, uv_scale=3)
    # oculus
    oc_c = dc + out3 * 0.05 + np.array([0, 0, 6.0])
    disk(mb, "Verre", oc_c, 0.55, out3, (0, 0, 1), 20, WHITE)
    ring = [oc_c + out3 * 0.02 + u3 * 0.6 * math.cos(a) + np.array([0, 0, 0.6 * math.sin(a)]) for a in np.linspace(0, 2 * math.pi, 25)]
    tube(mb, "PierreTaille", ring, 0.07, segs=6, u_tile=3, v_tile=3)
    # contreforts le long des grands côtés
    for e in sorted(info, key=lambda e: -e["L"])[:2]:
        if e["party"]:
            continue
        nb = int(e["L"] / 5.0)
        for k in range(1, nb):
            pp = e["p0"] + e["u"] * (e["L"] * k / nb) + e["out"] * 0.35
            g = gz(*pp)
            box(mb, "PierreTaille", (pp[0], pp[1], (base + zref + 5.5) / 2), (0.7, 0.7, zref + 5.5 - base), yaw=math.atan2(e["u"][1], e["u"][0]), uv_scale=3)
            box(mb, "PierreTaille", (pp[0] - e["out"][0] * 0.1, pp[1] - e["out"][1] * 0.1, zref + 5.9), (0.7, 0.5, 0.8), yaw=math.atan2(e["u"][1], e["u"][0]), uv_scale=3, pitch=math.radians(25))
        # hautes fenêtres étroites
        for k in range(nb):
            pp = e["p0"] + e["u"] * (e["L"] * (k + 0.5) / nb) + e["out"] * 0.03
            rect_sign(mb, "Verre", np.array([pp[0], pp[1], zref + 5.0]), 0.55, 1.8, np.array([e["out"][0], e["out"][1], 0]), (0, 0, 1, 1))
    # clocher
    corner = fac["p0"] if np.linalg.norm(fac["p0"] - np.array([-19.0, 21.0])) < np.linalg.norm(fac["p1"] - np.array([-19.0, 21.0])) else fac["p1"]
    inward_u = (fac["u"] if corner is fac["p0"] else -fac["u"])
    inward_n = -fac["out"]
    tw_ = 4.2
    tc = corner + inward_u * (tw_ / 2 + 0.1) + inward_n * (tw_ / 2 + 0.1)
    tower(mb, tc, math.atan2(fac["u"][1], fac["u"][0]), tw_, base, eave + 10.0)


def church_interior(b, mb, inst, info, fac, gdoor, openings, eave):
    """Intérieur de l'église : murs épais (tableaux des ouvertures), sol dallé, voûte en berceau, nef avec bancs, autel."""
    from shapely.geometry import box as sbox_
    from shapely import affinity
    T = 0.9
    p = b["poly"]
    l0 = gdoor + 0.02
    # emprise du clocher (carré de 4,2 m dans l'angle de la façade) : murs pleins de l'intérieur
    corner = fac["p0"] if np.linalg.norm(fac["p0"] - np.array([-19.0, 21.0])) < np.linalg.norm(fac["p1"] - np.array([-19.0, 21.0])) else fac["p1"]
    inward_u = (fac["u"] if corner is fac["p0"] else -fac["u"])
    tc = corner + inward_u * 2.2 + (-fac["out"]) * 2.2
    tw_poly = affinity.rotate(sbox_(tc[0] - 2.1 - T, tc[1] - 2.1 - T, tc[0] + 2.1 + T, tc[1] + 2.1 + T), math.degrees(math.atan2(fac["u"][1], fac["u"][0])),
                              origin=(tc[0], tc[1]))
    ip = p.buffer(-T, join_style=2).difference(tw_poly)
    if ip.geom_type != "Polygon":
        ip = max(getattr(ip, "geoms", [ip]), key=lambda g: g.area)
    ip = ip.simplify(0.05)
    c, a, L, W = ombr(ip)
    q = np.array([-a[1], a[0]])
    zs = min(eave - 1.6, l0 + 6.6)                     # naissance de la voûte
    hv = min(W / 2, eave - 0.5 - zs)
    # tableaux (épaisseur des murs) du portail et des fenêtres, vitres des fenêtres
    ow = []
    for ei, sc_, w, z0, z1 in openings:
        e = info[ei]
        P0 = e["p0"] + e["u"] * sc_
        inward = -e["out"]
        a0, a1 = P0 - e["u"] * w / 2, P0 + e["u"] * w / 2
        for (pa, za, zb_) in ((a0, z0, z1), (a1, z1, z0)):
            A = np.array([pa[0], pa[1], za])
            B_ = np.array([pa[0], pa[1], zb_])
            In = np.array([inward[0], inward[1], 0.0]) * T
            mb.quad("PierreTaille", A, B_, B_ + In, A + In, [(0, 0), (0, (zb_ - za) / 3), (T / 3, (zb_ - za) / 3), (T / 3, 0)], WHITE)
        In = np.array([inward[0], inward[1], 0.0]) * T
        top_a, top_b = np.array([a0[0], a0[1], z1]), np.array([a1[0], a1[1], z1])
        mb.quad("PierreTaille", top_a, top_b, top_b + In, top_a + In, [(0, 0), (w / 3, 0), (w / 3, T / 3), (0, T / 3)], WHITE)
        bot_a, bot_b = np.array([a1[0], a1[1], z0]), np.array([a0[0], a0[1], z0])
        mb.quad("PierreTaille", bot_a, bot_b, bot_b + In, bot_a + In, [(0, 0), (w / 3, 0), (w / 3, T / 3), (0, T / 3)], WHITE)
        if w < 1.0:
            g = P0 + inward * (T * 0.4)
            box(mb, "Verre", (g[0], g[1], (z0 + z1) / 2), (w, 0.02, z1 - z0), yaw=math.atan2(e["u"][1], e["u"][0]))
        ow.append((P0 + inward * T, e["u"], w, z0 - (0.05 if w > 1 else 0), z1))
    interiors._flat(mb, "Dallage", ip, l0, up=True)
    interiors._inner_walls(mb, ip, ow, [(l0, zs, (238, 230, 214, 255))])
    # voûte en berceau (surbaissée si le toit est bas), lunettes aux deux extrémités
    nseg = 14

    def V(x, t):
        P_ = c + a * x + q * (math.cos(t) * W / 2)
        return np.array([P_[0], P_[1], zs + math.sin(t) * hv])
    for i in range(nseg):
        t0, t1 = math.pi * i / nseg, math.pi * (i + 1) / nseg
        quad = [V(-L / 2, t0), V(-L / 2, t1), V(L / 2, t1), V(L / 2, t0)]
        want = -np.append(q * math.cos((t0 + t1) / 2), math.sin((t0 + t1) / 2))        # vers l'axe de la nef
        got = np.cross(quad[1] - quad[0], quad[2] - quad[0])
        if got @ want < 0:
            quad = quad[::-1]
        mb.quad("Enduit", *quad, [(0, 0), (0, 1), (L / 3, 1), (L / 3, 0)], (240, 234, 222, 255))
    for sx in (-1, 1):
        # lunette : demi-ellipse fermant la voûte au-dessus des murs d'extrémité, tournée vers l'intérieur
        origin = c + a * sx * L / 2
        e1 = -sx * q
        prof = [(-sx * math.cos(t) * W / 2, zs + math.sin(t) * hv) for t in np.linspace(0, math.pi, nseg + 1)]
        planar_polygon(mb, "Enduit", prof, [], np.array([origin[0], origin[1], 0.0]), np.array([e1[0], e1[1], 0.0]), np.array([0, 0, 1.0]),
                       lambda v2, P: np.stack([v2[:, 0] / 3, -v2[:, 1] / 3], -1), (240, 234, 222, 255))
    # doubleaux (arcs de pierre) tous les 4 m
    for k in range(1, int(L / 4.0)):
        x = -L / 2 + k * L / int(L / 4.0)
        pts = [tuple(c + a * x + q * (math.cos(t) * (W / 2 - 0.05))) + (zs + math.sin(t) * (hv - 0.05),) for t in np.linspace(0, math.pi, 15)]
        tube(mb, "PierreTaille", pts, 0.16, segs=6, u_tile=3, v_tile=3)
    # mobilier : l'autel à l'opposé de la façade, bancs de part et d'autre de l'allée centrale
    mid = (fac["p0"] + fac["p1"]) / 2
    sf = 1.0 if (mid - c) @ a > 0 else -1.0
    to_altar = -sf * a
    yaw_face = math.atan2(to_altar[0], -to_altar[1])         # la façade des meubles (-Y local) regarde l'autel
    inside = ip.buffer(-0.1)

    def put(name, P_, yaw_, sx_=1.0, col=(255, 255, 255)):
        inst[name].append((float(P_[0]), float(P_[1]), l0, float(yaw_), sx_, 1.0, 1.0, *col))

    def fits(P_, w_, d_, yaw_):
        r = affinity.rotate(sbox_(P_[0] - w_ / 2, P_[1] - d_ / 2, P_[0] + w_ / 2, P_[1] + d_ / 2), math.degrees(yaw_), origin=(P_[0], P_[1]))
        return inside.contains(r)

    xa = -sf * (L / 2 - 1.3)
    alt = c + a * xa
    if fits(alt, 3.4, 2.2, yaw_face):
        put("Int_Autel", alt, yaw_face + math.pi)
    for sy in (-1, 1):
        put("Int_Chandelier", c + a * (xa + sf * 1.6) + q * sy * 1.3, 0.0)
        st_ = c + a * (xa + sf * 0.4) + q * sy * (W / 2 - 0.5)
        if fits(st_, 0.55, 0.55, 0.0):
            put("Int_Statue", st_, yaw_face)
    pu = c + a * (xa + sf * 2.2) + q * (W / 2 - 1.2)
    if fits(pu, 0.55, 0.45, yaw_face):
        put("Int_Pupitre", pu, yaw_face + math.pi)
    aisle = 0.8
    pew_w = min(3.0, W / 2 - aisle - 0.25)
    x = xa + sf * 3.4
    rows = 0
    while abs(x) < L / 2 - 2.6 and pew_w > 1.2:
        for sy in (-1, 1):
            P_ = c + a * x + q * sy * (aisle + pew_w / 2)
            if fits(P_, pew_w, 0.8, yaw_face):
                put("Int_BancEglise", P_, yaw_face, pew_w / 3.0)
        rows += 1
        x += sf * 1.05
    # confessionnal et bénitier
    cf = c + a * (xa + sf * (L * 0.55)) + q * -(W / 2 - 0.45)
    if fits(cf, 1.8, 0.9, 0.0):
        put("Int_Confessionnal", cf, math.atan2(a[1], a[0]))
    bn = c + a * (sf * (L / 2 - 1.2)) + q * 1.2
    if fits(bn, 0.6, 0.6, 0.0):
        put("Int_Benitier", bn, 0.0)
    ein = mid - fac["out"] * 0.9 - c
    b["visit_plan"] = dict(theme="eglise", kind="eglise", c=[float(c[0]), float(c[1])], a=[float(a[0]), float(a[1])], L=float(L), W=float(W),
                           l0=float(l0), lv=[float(l0)], rows=rows,
                           entree=[float(ein @ a), float(ein @ q), float(-fac["out"] @ a), float(-fac["out"] @ q)])
    b["zref"] = l0
    VISITED.append(b)


def tower(mb, c, yaw, w, base, top):
    box(mb, "PierreTaille", (c[0], c[1], (base + top) / 2), (w, w, top - base), yaw=yaw, uv_scale=3.0, faces=("-x", "+x", "-y", "+y"))
    # étage des cloches : piliers d'angle + baies
    zb = top
    h = 3.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            ca, sa = math.cos(yaw), math.sin(yaw)
            dx, dy = sx * (w / 2 - 0.35), sy * (w / 2 - 0.35)
            px_, py_ = c[0] + dx * ca - dy * sa, c[1] + dx * sa + dy * ca
            box(mb, "PierreTaille", (px_, py_, zb + h / 2), (0.7, 0.7, h), yaw=yaw, uv_scale=3.0)
    # plancher sombre et linteaux en arc
    box(mb, "PierreTaille", (c[0], c[1], zb + 0.05), (w - 0.2, w - 0.2, 0.1), yaw=yaw, uv_scale=3.0, faces=("+z",))
    box(mb, "PierreTaille", (c[0], c[1], zb + h + 0.2), (w + 0.2, w + 0.2, 0.4), yaw=yaw, uv_scale=3.0)
    # toit en pavillon (quatre pans) en tuiles
    apex = (c[0], c[1], zb + h + 0.4 + 1.6)
    ca, sa = math.cos(yaw), math.sin(yaw)
    corners = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        dx, dy = sx * (w / 2 + 0.3), sy * (w / 2 + 0.3)
        corners.append((c[0] + dx * ca - dy * sa, c[1] + dx * sa + dy * ca, zb + h + 0.35))
    for k in range(4):
        a, b2 = corners[k], corners[(k + 1) % 4]
        nn = nrm(np.cross(np.subtract(b2, a), np.subtract(apex, a)))
        mb.add("TuilesCanal", [a, b2, apex], [nn], [(0, 2.4), (w / 2 + 0.3, 2.4), (w / 4, 0)], [WHITE], [[0, 1, 2]])
    # cloche
    revolve(mb, "Bronze", [(0.0, 0.0), (0.55, 0.02), (0.5, 0.12), (0.38, 0.5), (0.3, 0.95), (0.18, 1.08), (0.0, 1.12)], (c[0], c[1], zb + 0.9), segs=16)
    tube(mb, "BoisBrut", [(c[0] - w / 2 + 0.4, c[1], zb + 2.1), (c[0] + w / 2 - 0.4, c[1], zb + 2.1)], 0.1, segs=6)
    # croix au sommet
    tube(mb, "Fer", [apex, (apex[0], apex[1], apex[2] + 1.3)], 0.03, segs=6)
    tube(mb, "Fer", [(apex[0] - 0.35 * ca, apex[1] - 0.35 * sa, apex[2] + 0.95), (apex[0] + 0.35 * ca, apex[1] + 0.35 * sa, apex[2] + 0.95)], 0.025, segs=6)


def campanile(mb, c, z0, r, h):
    """Campanile provençal : cage en fer forgé en forme de bulbe, cloche, girouette."""
    n = 8
    for k in range(n):
        a = 2 * math.pi * k / n
        pts = []
        for t in np.linspace(0, 1, 14):
            rad = r * (math.sin(math.pi * min(t * 1.25, 1.0)) ** 0.8) * (1 - 0.15 * t) + 0.02
            if t > 0.8:
                rad = r * 0.22 * (1 - (t - 0.8) / 0.2)
            pts.append((c[0] + rad * math.cos(a), c[1] + rad * math.sin(a), z0 + t * h))
        tube(mb, "Fer", pts, 0.028, segs=5)
    for t in (0.0, 0.35, 0.62):
        rad = r * (math.sin(math.pi * min(t * 1.25, 1.0)) ** 0.8) * (1 - 0.15 * t) + 0.02
        ring = [(c[0] + rad * math.cos(a), c[1] + rad * math.sin(a), z0 + t * h) for a in np.linspace(0, 2 * math.pi, 25)]
        tube(mb, "Fer", ring, 0.03, segs=5)
    revolve(mb, "Bronze", [(0.0, 0.0), (0.42, 0.02), (0.38, 0.1), (0.28, 0.4), (0.22, 0.75), (0.12, 0.85), (0.0, 0.88)], (c[0], c[1], z0 + 0.5), segs=14)
    tube(mb, "Fer", [(c[0], c[1], z0 + h), (c[0], c[1], z0 + h + 1.0)], 0.03, segs=6)
    # girouette (coq stylisé)
    box(mb, "Fer", (c[0] + 0.15, c[1], z0 + h + 0.85), (0.5, 0.02, 0.25), uv_scale=1)


# ------------------------------------------------------------------ plaques de rue
def street_plaques(mb):
    done = set()
    for b in blds:
        if b["style"] not in ("core", "faubourg") or "info" not in b:
            continue
        for e in b["info"]:
            if not e["street"] or e["party"] or e["L"] < 3:
                continue
            mid = (e["p0"] + e["p1"]) / 2 + e["out"] * 3
            near = name_tree.query(Point(*mid).buffer(8))
            if not len(near):
                continue
            k = min(near, key=lambda k: road_names[k][0].distance(Point(*mid)))
            nm = road_names[k][1]
            if nm not in STREETS or (nm, round(mid[0] / 60), round(mid[1] / 60)) in done:
                continue
            key = f"rue_{STREETS.index(nm)}"
            s = min(0.9, e["L"] * 0.15)
            p = e["p0"] + e["u"] * s + e["out"] * 0.02
            z = gz(*(e["p0"] + e["out"] * 0.7)) + 2.6
            if z + 0.2 > b["eave"] - 0.6:
                continue
            rect_sign(mb, "Enseignes", np.array([p[0], p[1], z]), 0.48, 0.14, np.array([e["out"][0], e["out"][1], 0]), SIGNS[key], WHITE)
            done.add((nm, round(mid[0] / 60), round(mid[1] / 60)))
    return len(done)


# ------------------------------------------------------------------ exécution
def chunk_key(x, y):
    return (int(math.floor(x / CHUNK)), int(math.floor(y / CHUNK)))


if __name__ == "__main__":
    only_core = "--core" in sys.argv
    chunks = collections.defaultdict(MB)
    specials = {}
    inst = collections.defaultdict(list)
    n = 0
    for b in blds:
        c = b["poly"].centroid
        if only_core and c.distance(CENTER) > 260:
            continue
        try:
            if b["style"] in ("church", "belfry"):
                mbl = MB()
                landmark(b, mbl, inst)
                specials[("Eglise" if b["style"] == "church" else "Beffroi") + "_" + b["id"][:6]] = (mbl, (c.x, c.y))
            else:
                gen_building(b, chunks[chunk_key(c.x, c.y)], inst)
            n += 1
        except Exception as ex:
            import traceback
            traceback.print_exc()
            print("échec bâtiment", b["id"], b["style"], ex)
        if n % 200 == 0:
            print(n, "bâtiments  %.0fs" % (time.time() - T0), flush=True)
    npl = street_plaques(chunks[(0, 0)])
    print("plaques de rue:", npl)
    print("maisons visitables : %d (sur %d candidates) ; refus : %s" % (len(VISITED), len(VISIT_CANDS), dict(interiors.REJECT)))
    themes = {b["id"]: (b.get("visit_plan") or {}).get("theme", "") for b in VISITED}
    for dr in MOVING_DOORS:
        dr["theme"] = themes.get(dr["house"], "")
    out = dict(doors=MOVING_DOORS, visit=[dict(id=b["id"], x=b["poly"].centroid.x, y=b["poly"].centroid.y, z=b["zref"], style=b["style"], plan=b.get("visit_plan"))
                      for b in VISITED],
               meta=[b["meta"] for b in blds if "meta" in b],
               chunks={k: v.arrays() for k, v in chunks.items()}, specials={k: (v[0].arrays(), v[1]) for k, v in specials.items()},
               inst={k: np.array(v, np.float32) for k, v in inst.items()})
    with open("buildings_out.pkl" if not only_core else "buildings_core.pkl", "wb") as f:
        pickle.dump(out, f)
    tris = sum(len(d["I"]) for ch in out["chunks"].values() for d in ch.values())
    print("bâtiments: %d, triangles: %d, instances: %s, %.0fs" % (n, tris, {k: len(v) for k, v in out["inst"].items()}, time.time() - T0))
