"""Étape 4 : répartition de la végétation d'après les vraies parcelles (forêts, garrigue, vignes, lavande, vergers, haies...)."""
import sys, pickle, math, time, collections
sys.path.insert(0, ".")
from common import *
from geomlib import MB, box, tube, WHITE
from trees import make_vine, make_lavender, catalog

T0 = time.time()
G = np.load("terrain.npz")
GROUND, SPLAT = G["ground"], G["splat"]
V = pickle.load(open("vec.pkl", "rb"))
rng = np.random.default_rng(2024)
CENTER = Point(-10.0, 0.0)

# ------------------------------------------------------------------ masque d'exclusion à 1 m (bâtiments, routes, piscines, places)
R1 = 1.0
NX1 = int((ZONE["xmax"] - ZONE["xmin"]) / R1) + 1
NY1 = int((ZONE["ymax"] - ZONE["ymin"]) / R1) + 1


def raster1(geoms):
    img = Image.new("L", (NX1, NY1), 0)
    d = ImageDraw.Draw(img)
    for g in geoms:
        for p in polys_of(g):
            d.polygon([((x - ZONE["xmin"]) / R1, (y - ZONE["ymin"]) / R1) for x, y in p.exterior.coords], fill=255)
    return np.asarray(img) > 0


blocked_geoms = [b["poly"].buffer(1.6) for b in V["buildings"]]
for r in V["roads"]:
    extra = 0.9 if r["surface"] in ("asphalt", "stone", "gravel") else 0.4
    blocked_geoms.append(r["line"].buffer(r["width"] / 2 + extra))
blocked_geoms += [p.buffer(1.0) for p in V["pools"]] + V["plaza"] + [p.buffer(0.5) for p in V["parking"]]
if V.get("river_poly") is not None:
    blocked_geoms.append(V["river_poly"].buffer(2.5))
    blocked_geoms += [b["line"].buffer(b["width"] / 2 + 2.0) for b in V.get("bridges", [])]
BLOCK = raster1(blocked_geoms)
if V.get("river_rim") is not None:
    # parois raides des gorges : pas de culture ni d'herbe (seulement les rochers et buissons accrochés, plus bas)
    _sl = np.repeat(np.repeat(G["slope"].astype(np.float32), 2, axis=0), 2, axis=1)[:NY1, :NX1]
    _rz = raster1([V["river_rim"].buffer(2.0)])
    BLOCK |= _rz & (_sl > 36.0)
print("masque %.0fs" % (time.time() - T0), flush=True)


def free(x, y):
    i = np.clip(((x - ZONE["xmin"]) / R1).astype(int), 0, NX1 - 1)
    j = np.clip(((y - ZONE["ymin"]) / R1).astype(int), 0, NY1 - 1)
    return ~BLOCK[j, i]


def zat(x, y):
    return grid_sample(GROUND, x, y, order=1)


def jitter_grid(geom, spacing, keep=1.0, jitter=0.45):
    if geom is None or geom.is_empty:
        return np.zeros((0, 2))
    x0, y0, x1, y1 = geom.bounds
    xs = np.arange(x0, x1, spacing)
    ys = np.arange(y0, y1, spacing)
    X, Y = np.meshgrid(xs, ys)
    X = X.ravel() + rng.uniform(-jitter, jitter, X.size) * spacing
    Y = Y.ravel() + rng.uniform(-jitter, jitter, Y.size) * spacing
    m = shapely.contains_xy(geom, X, Y)
    X, Y = X[m], Y[m]
    if keep < 1.0:
        k = rng.random(X.size) < keep
        X, Y = X[k], Y[k]
    f = free(X, Y)
    return np.column_stack([X[f], Y[f]])


INST = collections.defaultdict(list)


def put(name, xy, scale=(0.8, 1.2), yaw=None, sink=0.05, tint=None, zscale=None):
    if len(xy) == 0:
        return
    n = len(xy)
    z = zat(xy[:, 0], xy[:, 1]) - sink
    s = rng.uniform(*scale, n)
    sz = s if zscale is None else s * rng.uniform(*zscale, n)
    yw = rng.uniform(0, 2 * math.pi, n) if yaw is None else np.broadcast_to(yaw, (n,))
    t = np.full((n, 3), 255.0) if tint is None else np.broadcast_to(np.asarray(tint, float), (n, 3))
    arr = np.column_stack([xy, z, yw, s, s, sz, t])
    INST[name].append(arr)


def put_variants(prefix, nvar, xy, **kw):
    if len(xy) == 0:
        return
    v = rng.integers(0, nvar, len(xy))
    for k in range(nvar):
        put(f"{prefix}_{k}", xy[v == k], **kw)


def U(key):
    return unary_union(V[key]).intersection(ZBOX) if V.get(key) else None


# ------------------------------------------------------------------ forêts : pins + chênes, sous-bois de garrigue
forest = unary_union((V.get("forest") or []) + (V.get("lc_forest") or [])).intersection(ZBOX)
pts = jitter_grid(forest, 7.5)


def ochre_at(p):
    return grid_sample(SPLAT[..., 2].astype(np.float32), p[:, 0], p[:, 1]) / 255.0 if len(p) else np.zeros(0)


def bare_ochre(p, keep_min=0.12):
    """Falaises et ravins d'ocre : sol presque nu, quelques pins clairsemés."""
    return p[rng.random(len(p)) < np.clip(1 - 1.6 * ochre_at(p), keep_min, 1)]


pts = bare_ochre(pts)
ochre_w = ochre_at(pts)
patch = grid_sample(fbm((NY, NX), 60, 3, seed=77), pts[:, 0], pts[:, 1])
p_pine = np.clip(0.35 + 0.35 * patch + 1.5 * ochre_w, 0.05, 0.95)
u = rng.random(len(pts))
pine = u < p_pine
pp = pts[pine]
sub = rng.random(len(pp))
put_variants("Arbre_Pin", 4, pp[sub < 0.9], scale=(0.75, 1.2))
put_variants("Arbre_PinParasol", 2, pp[sub >= 0.9], scale=(0.8, 1.1))
put_variants("Arbre_Chene", 4, pts[~pine], scale=(0.7, 1.25))
under = bare_ochre(jitter_grid(forest, 4.0, keep=0.45), 0.2)
put_variants("Buisson_Garrigue", 4, under, scale=(0.7, 1.4))
# forêt dense autour de la ceinture de lavande : un second semis d'arbres, sous-bois fourni
dense = unary_union(V.get("forest_dense") or []).intersection(ZBOX)
if not dense.is_empty:
    dp = bare_ochre(jitter_grid(dense, 8.0, keep=0.9))
    dv = rng.random(len(dp))
    put_variants("Arbre_Chene", 4, dp[dv < 0.5], scale=(0.8, 1.3))
    put_variants("Arbre_Pin", 4, dp[(dv >= 0.5) & (dv < 0.92)], scale=(0.85, 1.25))
    put_variants("Arbre_PinParasol", 2, dp[dv >= 0.92], scale=(0.8, 1.1))
    du = bare_ochre(jitter_grid(dense, 3.6, keep=0.5), 0.2)
    put_variants("Buisson_Garrigue", 4, du, scale=(0.8, 1.5))
    print("forêt dense : %d arbres, %d buissons en plus" % (len(dp), len(du)), flush=True)
print("forêt:", len(pts), "arbres, %d buissons  %.0fs" % (len(under), time.time() - T0), flush=True)

# ------------------------------------------------------------------ garrigue : buissons, romarins, herbes sèches, arbres isolés
scrub = unary_union((V.get("scrub") or []) + (V.get("lc_shrub") or []) + (V.get("grass_nat") or [])).intersection(ZBOX).difference(forest)
b = bare_ochre(jitter_grid(scrub, 4.2, keep=0.8), 0.2)
put_variants("Buisson_Garrigue", 4, b, scale=(0.6, 1.5))
b2 = jitter_grid(scrub, 7.0, keep=0.35)
put_variants("Buisson_Romarin", 2, b2, scale=(0.8, 1.3))
t = bare_ochre(jitter_grid(scrub, 16.0, keep=0.5))
tv = rng.random(len(t))
put_variants("Arbre_Chene", 4, t[tv < 0.55], scale=(0.5, 0.9))
put_variants("Arbre_Pin", 4, t[(tv >= 0.55) & (tv < 0.9)], scale=(0.5, 0.9))
put_variants("Arbre_Cypres", 4, t[tv >= 0.9], scale=(0.7, 1.0))
gr = jitter_grid(scrub, 2.6, keep=0.5)
put_variants("Herbe_Seche", 3, gr, scale=(0.8, 1.5))
print("garrigue %.0fs" % (time.time() - T0), flush=True)

# ------------------------------------------------------------------ prés : herbes sèches
meadow = U("meadow")
gr = jitter_grid(meadow, 2.2, keep=0.55)
put_variants("Herbe_Seche", 3, gr, scale=(0.9, 1.6))

# ------------------------------------------------------------------ rangs (vigne, lavande) orientés selon la parcelle
def rows(parcel, spacing, seg_len, name_prefix, nvar, margin=1.5, jitter=0.03):
    placed = []
    for pg in polys_of(parcel):
        inner = pg.buffer(-margin)
        if inner.is_empty or inner.area < 30:
            continue
        c, ax, Lm, Wm = ombr(inner)
        perp = np.array([-ax[1], ax[0]])
        half = max(Lm, Wm) * 0.75 + 5
        k0 = -half
        offs = np.arange(-half, half, spacing) + rng.uniform(0, spacing)
        yaw = math.atan2(ax[1], ax[0])
        for o in offs:
            a = c + perp * o - ax * half
            bb = c + perp * o + ax * half
            ln = LineString([a, bb]).intersection(inner)
            for seg in lines_of(ln):
                n = int(seg.length / seg_len)
                if n < 1:
                    continue
                s0 = (seg.length - n * seg_len) / 2 + seg_len / 2
                for k in range(n):
                    p = seg.interpolate(s0 + k * seg_len)
                    placed.append((p.x, p.y, yaw))
    if not placed:
        return 0
    P = np.array(placed)
    f = free(P[:, 0], P[:, 1])
    P = P[f]
    v = rng.integers(0, nvar, len(P))
    for kk in range(nvar):
        m = v == kk
        put(f"{name_prefix}_{kk}", P[m, :2], scale=(0.95, 1.05), yaw=P[m, 2] + rng.normal(0, 0.01, m.sum()), sink=0.02)
    return len(P)


nv = rows(U("vineyard"), 2.5, 4.8, "Vigne_Rang", 3)
nl = rows(U("lavender"), 1.7, 4.0, "Lavande_Rang", 3, margin=1.2)
print("vignes: %d segments, lavande: %d segments  %.0fs" % (nv, nl, time.time() - T0), flush=True)

# ------------------------------------------------------------------ cyprès dans les champs de lavande autour du village :
# fuseaux isolés, courts alignements en bordure de parcelle, et vieux oliviers épars (seuls ou par deux ou trois)
lring = unary_union(V.get("lavender_ring") or []).intersection(ZBOX)
n_lc = n_lo = 0
if not lring.is_empty:
    solo = jitter_grid(lring, 42.0, keep=0.3)
    put_variants("Arbre_Cypres", 4, solo, scale=(0.8, 1.15), sink=0.1)
    n_lc += len(solo)
    oli = jitter_grid(lring, 38.0, keep=0.35)
    grp = []
    for o in oli:
        for _ in range(int(rng.choice([0, 0, 1, 2]))):
            a_, d_ = rng.uniform(0, 2 * math.pi), rng.uniform(5, 8)
            grp.append((o[0] + math.cos(a_) * d_, o[1] + math.sin(a_) * d_))
    if grp:
        grp = np.array(grp)
        oli = np.concatenate([oli, grp[free(grp[:, 0], grp[:, 1])]])
    put_variants("Arbre_Olivier", 4, oli, scale=(0.85, 1.35))
    n_lo = len(oli)
    for pg in polys_of(unary_union(V["lavender"]).intersection(lring)):
        if rng.random() > 0.2 or pg.area < 600:
            continue
        ring_ = pg.exterior
        s0 = rng.uniform(0, ring_.length)
        m = int(rng.integers(4, 8))
        P = np.array([ring_.interpolate((s0 + k * 4.5) % ring_.length).coords[0] for k in range(m)])
        P = P[free(P[:, 0], P[:, 1])]
        put_variants("Arbre_Cypres", 4, P, scale=(0.85, 1.1), sink=0.1)
        n_lc += len(P)
print("dans la lavande : %d cyprès, %d oliviers" % (n_lc, n_lo), flush=True)

# ------------------------------------------------------------------ vergers : oliviers (et cerisiers), alignés sur la parcelle
def orchard(parcel, spacing, species_fn):
    out = []
    for pg in polys_of(parcel):
        inner = pg.buffer(-2.0)
        if inner.is_empty:
            continue
        c, ax, Lm, Wm = ombr(inner)
        perp = np.array([-ax[1], ax[0]])
        n1, n2 = int(Lm / spacing) + 2, int(Wm / spacing) + 2
        I, J = np.meshgrid(np.arange(-n1, n1 + 1), np.arange(-n2, n2 + 1))
        P = c + np.outer(I.ravel() * spacing, ax) + np.outer(J.ravel() * spacing, perp)
        P += rng.normal(0, 0.25, P.shape)
        m = shapely.contains_xy(inner, P[:, 0], P[:, 1])
        out.append(P[m])
    if not out:
        return np.zeros((0, 2))
    P = np.concatenate(out)
    return P[free(P[:, 0], P[:, 1])]


olive_parcels = U("olive")
orch = polys_of(U("orchard"))
conv = [p for p in orch if rng.random() < 0.45]
rest = [p for p in orch if p not in conv]
op = orchard(unary_union([olive_parcels] + conv) if conv else olive_parcels, 7.0, None)
put_variants("Arbre_Olivier", 4, op, scale=(0.75, 1.15))
fp = orchard(unary_union(rest), 5.5, None)
put_variants("Arbre_Fruitier", 3, fp, scale=(0.85, 1.15))
gr = jitter_grid(unary_union([olive_parcels] + orch), 3.0, keep=0.35)
put_variants("Herbe_Seche", 3, gr, scale=(0.8, 1.3))
print("vergers: %d oliviers, %d fruitiers  %.0fs" % (len(op), len(fp), time.time() - T0), flush=True)

# ------------------------------------------------------------------ champs moissonnés : balles de foin
bales = []
for pg in polys_of(U("farmland")):
    if pg.area > 2500 and rng.random() < 0.4:
        n = int(pg.area / 1800)
        P = jitter_grid(pg.buffer(-6), 30.0, keep=1.0)
        if len(P):
            bales.append(P[: max(1, n)])
if bales:
    put("Balle_Foin", np.concatenate(bales), scale=(0.95, 1.05))

# ------------------------------------------------------------------ haies de cyprès (brise-mistral), alignements de platanes
hedge_pts = []
for ln in V["hedges"]:
    if not isinstance(ln, LineString):
        ln = LineString(ln.coords)
    n = int(ln.length / 1.9)
    for k in range(n):
        p = ln.interpolate((k + 0.5) * ln.length / max(n, 1))
        hedge_pts.append((p.x, p.y))
if hedge_pts:
    H = np.array(hedge_pts)
    H = H[free(H[:, 0], H[:, 1]) | True]
    put_variants("Arbre_Cypres", 4, H, scale=(0.55, 0.8), sink=0.1)
for ln in V.get("tree_rows", []):
    n = int(ln.length / 8)
    P = np.array([(ln.interpolate(k * 8 + 4).x, ln.interpolate(k * 8 + 4).y) for k in range(n)])
    if len(P):
        put_variants("Arbre_Platane", 3, P, scale=(0.8, 1.0))
print("haies: %d cyprès  %.0fs" % (len(hedge_pts), time.time() - T0), flush=True)

# ------------------------------------------------------------------ allée de platanes le long des routes à l'entrée du village
allee = []
for r in V["roads"]:
    if r["surface"] != "asphalt" or r["cls"] not in ("secondary", "tertiary", "unclassified", "residential"):
        continue
    ln = r["line"]
    n = int(ln.length / 11)
    for k in range(n):
        s = (k + 0.5) * 11
        p = ln.interpolate(s)
        d = CENTER.distance(p)
        if not (160 < d < 650):
            continue
        a = ln.interpolate(max(0, s - 1))
        b_ = ln.interpolate(min(ln.length, s + 1))
        dv = np.array([b_.x - a.x, b_.y - a.y])
        dv /= np.linalg.norm(dv) + 1e-9
        nn = np.array([-dv[1], dv[0]])
        for sd in (-1, 1):
            q = np.array([p.x, p.y]) + nn * sd * (r["width"] / 2 + 2.2)
            allee.append(q)
if allee:
    A = np.array(allee)
    keep = rng.random(len(A)) < 0.55
    A = A[keep]
    fA = free(A[:, 0], A[:, 1]) | True
    # pas de platane dans une maison
    from shapely.strtree import STRtree
    btree = STRtree([b["poly"] for b in V["buildings"]])
    ok = np.array([len(btree.query(Point(*q).buffer(3.5))) == 0 for q in A])
    put_variants("Arbre_Platane", 3, A[ok], scale=(0.75, 0.95))
    print("allée de platanes:", int(ok.sum()), flush=True)

# ------------------------------------------------------------------ places du village : platanes et bancs
bu = unary_union([b["poly"] for b in V["buildings"]])
plaza_trees = []
for p in V["plaza"]:
    freep = p.difference(bu.buffer(4.5))
    if freep.is_empty or freep.area < 20:
        continue
    n = max(1, int(freep.area / 140))
    P = jitter_grid(freep, 9.0, keep=1.0, jitter=0.2) if False else None
    xs = []
    for k in range(60):
        q = freep.representative_point() if k == 0 else Point(rng.uniform(*freep.bounds[0::2]), rng.uniform(*freep.bounds[1::2]))
        if freep.contains(q) and all(q.distance(Point(*o)) > 7 for o in xs):
            xs.append((q.x, q.y))
        if len(xs) >= n:
            break
    plaza_trees += xs
if plaza_trees:
    put_variants("Arbre_Platane", 3, np.array(plaza_trees), scale=(0.7, 0.9))

# ------------------------------------------------------------------ jardins des villas et mas : oliviers, cyprès, lauriers-roses, lavande, pelouses
gard_trees, gard_cyp, gard_bush, gard_lav, lawn = [], [], [], [], []
for bld in V["buildings"]:
    p = bld["poly"]
    c = p.centroid
    if V["core"].contains(c) or p.area < 40:
        continue
    ring = p.buffer(14).difference(p.buffer(2.5))
    k = rng.random()
    P = jitter_grid(ring, 6.0, keep=0.35)
    if len(P) == 0:
        continue
    gard_trees.append(P[: rng.integers(1, 4)])
    if k < 0.45:
        # paire de cyprès près de l'entrée
        d = rng.uniform(0, 2 * math.pi)
        base = np.array([c.x, c.y]) + np.array([math.cos(d), math.sin(d)]) * (math.sqrt(p.area) / 2 + 6)
        side = np.array([-math.sin(d), math.cos(d)]) * 2.2
        gard_cyp += [base + side, base - side]
    B = jitter_grid(ring, 4.0, keep=0.25)
    gard_bush.append(B)
    if rng.random() < 0.3:
        L = jitter_grid(p.buffer(7).difference(p.buffer(3)), 1.4, keep=0.7)
        gard_lav.append(L[:30])
    lawn.append(jitter_grid(p.buffer(10).difference(p.buffer(2)), 1.8, keep=0.4))
GT = np.concatenate(gard_trees) if gard_trees else np.zeros((0, 2))
tv = rng.random(len(GT))
put_variants("Arbre_Olivier", 4, GT[tv < 0.6], scale=(0.7, 1.1))
put_variants("Arbre_Pin", 4, GT[(tv >= 0.6) & (tv < 0.7)], scale=(0.7, 1.0))
put_variants("Arbre_PinParasol", 2, GT[(tv >= 0.7) & (tv < 0.75)], scale=(0.7, 1.0))
put_variants("Arbre_Platane", 3, GT[(tv >= 0.75) & (tv < 0.85)], scale=(0.6, 0.8))
put_variants("Arbre_Fruitier", 3, GT[tv >= 0.85], scale=(0.8, 1.1))
if gard_cyp:
    C_ = np.array(gard_cyp)
    put_variants("Arbre_Cypres", 4, C_[free(C_[:, 0], C_[:, 1])], scale=(0.6, 0.85))
GB = np.concatenate(gard_bush) if gard_bush else np.zeros((0, 2))
bv = rng.random(len(GB))
put_variants("Buisson_LaurierRose", 2, GB[bv < 0.4], scale=(0.7, 1.1))
put_variants("Buisson_Romarin", 2, GB[(bv >= 0.4) & (bv < 0.7)], scale=(0.8, 1.2))
put_variants("Buisson_Garrigue", 4, GB[bv >= 0.7], scale=(0.8, 1.2))
if gard_lav:
    put_variants("Lavande", 3, np.concatenate(gard_lav), scale=(0.8, 1.1))
if lawn:
    put_variants("Herbe_Verte", 3, np.concatenate(lawn), scale=(0.8, 1.2))
print("jardins: %d arbres, %d buissons  %.0fs" % (len(GT), len(GB), time.time() - T0), flush=True)

# ------------------------------------------------------------------ oliviers en plus : oliveraies en terrasses, vieux village, places, bords de route
CEN = Point(-10.0, 20.0)
extra = []
# oliveraies (restanques) sur une partie des prés et des champs autour du village
groves = [pg for pg in polys_of(U("meadow")) if pg.centroid.distance(CEN) < 1300 and pg.area > 400 and rng.random() < 0.45]
groves += [pg for pg in polys_of(U("farmland")) if pg.centroid.distance(CEN) < 1000 and pg.area > 800 and rng.random() < 0.18]
if groves:
    G_ = orchard(unary_union(groves), 7.5, None)
    put_variants("Arbre_Olivier", 4, G_, scale=(0.8, 1.3))
    extra.append(len(G_))
# vieux village : oliviers isolés dans les cours et les recoins
yard = V["core"].buffer(25).difference(bu.buffer(2.2))
Y_ = jitter_grid(yard, 16.0, keep=0.35)
put_variants("Arbre_Olivier", 4, Y_, scale=(0.6, 0.95))
extra.append(len(Y_))
# un vieil olivier sur chaque place, à l'écart des platanes
PL_ = []
for p in V["plaza"]:
    freep = p.difference(bu.buffer(3.5))
    if freep.is_empty or freep.area < 25:
        continue
    for _ in range(40):
        q = Point(rng.uniform(*freep.bounds[0::2]), rng.uniform(*freep.bounds[1::2]))
        if freep.contains(q) and all(q.distance(Point(*o)) > 6 for o in plaza_trees):
            PL_.append((q.x, q.y))
            break
if PL_:
    PL_ = np.array(PL_)
    put_variants("Arbre_Olivier", 4, PL_[free(PL_[:, 0], PL_[:, 1])], scale=(1.1, 1.35))
    extra.append(len(PL_))
# le long des routes et chemins du faubourg
RD_ = []
for r in V["roads"]:
    ln = r["line"]
    if ln.distance(CEN) > 900 or r["cls"] in ("steps",):
        continue
    for k in range(int(ln.length / 22)):
        if rng.random() > 0.4:
            continue
        t = (k + rng.uniform(0.2, 0.8)) * 22
        a, b = ln.interpolate(max(0, t - 1)), ln.interpolate(min(ln.length, t + 1))
        d = np.array([b.x - a.x, b.y - a.y])
        d /= np.linalg.norm(d) + 1e-9
        side = rng.choice([-1, 1])
        off = (r.get("width") or 4.0) / 2 + rng.uniform(2.5, 4.5)
        pt = ln.interpolate(t)
        RD_.append((pt.x - d[1] * off * side, pt.y + d[0] * off * side))
if RD_:
    RD_ = np.array(RD_)
    RD_ = RD_[free(RD_[:, 0], RD_[:, 1])]
    put_variants("Arbre_Olivier", 4, RD_, scale=(0.7, 1.1))
    extra.append(len(RD_))
print("oliviers ajoutés : %d (oliveraies, vieux village, places, routes)  %.0fs" % (sum(extra), time.time() - T0), flush=True)

# ------------------------------------------------------------------ rochers calcaires : affleurements, blocs, éboulis
OUT_M = G["outcrop"].astype(np.float32) if "outcrop" in G.files else np.zeros_like(GROUND)
SLOPE = G["slope"].astype(np.float32)
wild = unary_union([forest, scrub] + ([meadow] if meadow is not None else [])).intersection(ZBOX).difference(V["core"].buffer(40))
def _pick(p, base, k_out, k_slope=0.0):
    if len(p) == 0:
        return p
    o = grid_sample(OUT_M, p[:, 0], p[:, 1])
    sl = grid_sample(SLOPE, p[:, 0], p[:, 1])
    pr = base + k_out * o + k_slope * smoothstep(14.0, 32.0, sl)
    return p[rng.random(len(p)) < pr]
rb = _pick(jitter_grid(wild, 11.0), 0.05, 0.75, 0.25)
put_variants("Rocher_Bloc", 4, rb, scale=(0.6, 1.5), zscale=(0.8, 1.2))
rd = _pick(jitter_grid(wild, 22.0), 0.0, 0.9)
put_variants("Rocher_Dalle", 3, rd, scale=(0.7, 1.3), zscale=(0.7, 1.1), sink=0.12)
re_ = _pick(jitter_grid(wild, 4.5), 0.015, 0.25, 0.35)
put_variants("Rocher_Eboulis", 3, re_, scale=(0.6, 1.6))
print("rochers : %d blocs, %d dalles, %d éboulis  %.0fs" % (len(rb), len(rd), len(re_), time.time() - T0), flush=True)

# ------------------------------------------------------------------ bas-côtés : herbes sèches le long des routes
side = []
for r in V["roads"]:
    if r["surface"] not in ("asphalt", "gravel", "dirt"):
        continue
    buf = r["line"].buffer(r["width"] / 2 + 2.5).difference(r["line"].buffer(r["width"] / 2 + 0.9))
    side.append(buf)
sideg = unary_union(side).intersection(ZBOX).difference(V["core"].buffer(20))
S = jitter_grid(sideg, 1.6, keep=0.45)
put_variants("Herbe_Seche", 3, S, scale=(0.8, 1.6))
print("bas-côtés: %d touffes  %.0fs" % (len(S), time.time() - T0), flush=True)

# ------------------------------------------------------------------ arbres isolés OSM
for (x, y, genus) in V["trees"]:
    if not free(np.array([x]), np.array([y]))[0]:
        continue
    g = (genus or "").lower()
    name = "Arbre_Platane" if "platan" in g else ("Arbre_Pin" if "pinus" in g else ("Arbre_Cypres" if "cupress" in g else ("Arbre_Olivier" if "olea" in g else "Arbre_Chene")))
    nvar = {"Arbre_Platane": 3, "Arbre_Pin": 4, "Arbre_Cypres": 4, "Arbre_Olivier": 4, "Arbre_Chene": 4}[name]
    put_variants(name, nvar, np.array([[x, y]]), scale=(0.8, 1.1))

# ------------------------------------------------------------------ cyprès dans le village : une partie des arbres de la ville devient des cyprès,
# souvent en bouquets de 2 à 4 fuseaux comme dans les jardins provençaux
town = unary_union([V["core"].buffer(60)] + [p.buffer(10) for p in (V.get("residential") or [])]).intersection(ZBOX)
town = town.difference(dense)          # la forêt dense autour du village reste une forêt de pins et de chênes
n_cyp = 0
for sp in ("Arbre_Chene", "Arbre_Pin", "Arbre_PinParasol", "Arbre_Fruitier"):
    for k in [k for k in INST if k.startswith(sp + "_")]:
        arr = np.concatenate(INST[k])
        inside = shapely.contains_xy(town, arr[:, 0], arr[:, 1])
        conv = inside & (rng.random(len(arr)) < 0.45)
        INST[k] = [arr[~conv]]
        xy = arr[conv, :2]
        n_cyp += len(xy)
        put_variants("Arbre_Cypres", 4, xy, scale=(0.75, 1.1), sink=0.1)
        grp = xy[rng.random(len(xy)) < 0.35]
        for g in grp:
            m = int(rng.integers(1, 4))
            a = rng.uniform(0, 2 * math.pi) + np.arange(m) * 2.1
            d = rng.uniform(1.4, 2.4, m)
            ex = np.column_stack([g[0] + np.cos(a) * d, g[1] + np.sin(a) * d])
            ex = ex[free(ex[:, 0], ex[:, 1])]
            n_cyp += len(ex)
            put_variants("Arbre_Cypres", 4, ex, scale=(0.6, 0.95), sink=0.1)
print("cyprès dans le village : %d" % n_cyp, flush=True)

# ------------------------------------------------------------------ au bord des gorges de la rivière des Ocres : platanes, cyprès, chênes,
# lauriers-roses et garrigue (les falaises restent nues)
if V.get("river_poly") is not None:
    rp = V.get("river_rim") or V["river_poly"]          # en haut des falaises des gorges
    bank = rp.buffer(16.0).difference(rp.buffer(2.0)).difference(unary_union([V["core"].buffer(5)]))
    T_ = jitter_grid(bank, 11.0, keep=0.55)
    tv = rng.random(len(T_))
    put_variants("Arbre_Platane", 3, T_[tv < 0.55], scale=(0.8, 1.15))
    put_variants("Arbre_Cypres", 4, T_[(tv >= 0.55) & (tv < 0.7)], scale=(0.9, 1.2), sink=0.1)
    put_variants("Arbre_Chene", 4, T_[tv >= 0.7], scale=(0.7, 1.0))
    edge = rp.buffer(6.0).difference(rp.buffer(1.5))
    Lr = jitter_grid(edge, 5.0, keep=0.5)
    put_variants("Buisson_LaurierRose", 2, Lr, scale=(0.8, 1.2))
    Rs = jitter_grid(edge, 3.0, keep=0.5)
    put_variants("Buisson_Garrigue", 4, Rs, scale=(0.8, 1.4))
    print("berges : %d arbres, %d lauriers-roses  %.0fs" % (len(T_), len(Lr), time.time() - T0), flush=True)

# ------------------------------------------------------------------ parois des gorges : blocs de calcaire en saillie, éboulis, buissons et
# chênes verts accrochés aux vires (la paroi n'est plus une surface lisse)
if V.get("river_rim") is not None:
    wall = V["river_rim"].buffer(-1.5).difference(V["river_poly"].buffer(3.0))
    SLOPE_W = G["slope"].astype(np.float32)
    def wall_pts(spacing, keep, steep=True):
        x0, y0, x1, y1 = wall.bounds
        X_, Y_ = np.meshgrid(np.arange(x0, x1, spacing), np.arange(y0, y1, spacing))
        X_ = X_.ravel() + rng.uniform(-0.45, 0.45, X_.size) * spacing
        Y_ = Y_.ravel() + rng.uniform(-0.45, 0.45, Y_.size) * spacing
        m = shapely.contains_xy(wall, X_, Y_) & (rng.random(X_.size) < keep)
        sl_ = grid_sample(SLOPE_W, X_, Y_)
        if steep is not None:
            m &= (sl_ > 45.0) if steep else ((sl_ > 12.0) & (sl_ < 45.0))   # ressauts ou vires
        return np.column_stack([X_[m], Y_[m]])
    # végétation en taches, comme sur les vraies parois : fissures et vires colonisées, dalles nues entre elles
    from scipy import ndimage
    WPATCH = ndimage.gaussian_filter(np.random.default_rng(63).normal(0, 1, G["slope"].shape).astype(np.float32), 5.0)
    WPATCH /= WPATCH.std() + 1e-6

    def patchy(p_, bias):
        if not len(p_):
            return p_
        v_ = grid_sample(WPATCH, p_[:, 0], p_[:, 1])
        return p_[rng.random(len(p_)) < np.clip(0.5 + 0.45 * v_ + bias, 0.05, 1.0)]
    wb = wall_pts(6.0, 0.5, steep=True)
    put_variants("Rocher_Bloc", 4, wb, scale=(1.5, 3.5), zscale=(0.6, 1.1), sink=0.5)
    we = wall_pts(4.0, 0.45, steep=None)
    put_variants("Rocher_Eboulis", 3, we, scale=(1.2, 2.5), sink=0.1)
    wg = patchy(wall_pts(2.4, 0.8, steep=None), 0.1)              # garrigue accrochée sur toute la paroi
    put_variants("Buisson_Garrigue", 4, wg, scale=(1.0, 1.8), sink=0.2)
    wr = patchy(wall_pts(3.2, 0.6, steep=None), 0.0)
    put_variants("Buisson_Romarin", 2, wr, scale=(1.0, 1.5), sink=0.1)
    wt = patchy(wall_pts(6.0, 0.6, steep=None), -0.1)             # chênes verts accrochés
    tv_ = rng.random(len(wt))
    put_variants("Arbre_Chene", 4, wt[tv_ < 0.7], scale=(0.45, 0.85), sink=0.3)
    put_variants("Arbre_Pin", 4, wt[tv_ >= 0.7], scale=(0.45, 0.8), sink=0.3)
    wh = patchy(wall_pts(1.8, 0.7, steep=None), 0.2)
    put_variants("Herbe_Haute", 3, wh, scale=(0.8, 1.2))
    wv = patchy(wall_pts(1.6, 0.7, steep=None), 0.3)             # touffes d'herbe verte sur toute la paroi
    put_variants("Herbe_Touffe", 3, wv, scale=(1.0, 1.5))
    wg2 = patchy(wall_pts(2.2, 0.5, steep=None), 0.0)
    put_variants("Buisson_Garrigue", 4, wg2, scale=(1.0, 1.8), sink=0.2)
    wg = np.vstack([wg, wg2])
    print("parois des gorges : %d blocs, %d éboulis, %d buissons, %d arbres accrochés" % (len(wb), len(we), len(wg) + len(wr), len(wt)), flush=True)

# ------------------------------------------------------------------ sol en couches (hors routes, rues, places, bâtis, eau) : touffes d'herbe,
# hautes herbes, petits graviers et mottes de terre, selon la mosaïque du sol ; denses autour des villages, clairsemés au loin
if "cover" in G.files:
    COV = G["cover"]
    RESG = ZONE["res"]
    hubs = [np.array([-10.0, 0.0])] + ([np.array(V["quartier"].centroid.coords[0])] if V.get("quartier") is not None else [])

    def cover_pts(cls, spacing, keep):
        xs_ = np.arange(ZONE["xmin"] + 1, ZONE["xmax"] - 1, spacing)
        ys_ = np.arange(ZONE["ymin"] + 1, ZONE["ymax"] - 1, spacing)
        out = []
        for y0 in ys_:                                   # par bandes : mémoire modeste
            X_ = xs_ + rng.uniform(-0.45, 0.45, len(xs_)) * spacing
            Y_ = y0 + rng.uniform(-0.45, 0.45, len(xs_)) * spacing
            i_ = np.clip(((X_ - ZONE["xmin"]) / RESG).astype(int), 0, COV.shape[1] - 1)
            j_ = np.clip(((Y_ - ZONE["ymin"]) / RESG).astype(int), 0, COV.shape[0] - 1)
            m = COV[j_, i_] == cls
            if not m.any():
                continue
            X_, Y_ = X_[m], Y_[m]
            d = np.min([np.hypot(X_ - h[0], Y_ - h[1]) for h in hubs], axis=0)
            dens = np.clip(1.0 - (d - 700.0) / 600.0, 0.12, 1.0)     # plein jusqu'à 700 m des villages, 12 % au-delà de 1,3 km
            m = rng.random(len(X_)) < keep * dens
            X_, Y_ = X_[m], Y_[m]
            f = free(X_, Y_)
            out.append(np.column_stack([X_[f], Y_[f]]))
        return np.concatenate(out) if out else np.zeros((0, 2))

    g_ = cover_pts(3, 1.05, 0.85)
    put_variants("Herbe_Touffe", 3, g_, scale=(0.8, 1.4))
    t_ = cover_pts(4, 1.25, 0.85)
    put_variants("Herbe_Haute", 3, t_, scale=(0.8, 1.3))
    t2 = cover_pts(4, 2.0, 0.6)
    put_variants("Herbe_Touffe", 3, t2, scale=(0.9, 1.4))
    e3 = cover_pts(1, 3.0, 0.35)
    put_variants("Herbe_Touffe", 3, e3, scale=(0.6, 1.0))
    t2 = np.vstack([t2, e3])
    gr = cover_pts(2, 1.5, 0.6)
    put_variants("Gravillons", 3, gr, scale=(0.8, 1.4), sink=0.0)
    e_ = cover_pts(1, 3.2, 0.35)
    put_variants("Motte_Terre", 3, e_, scale=(0.8, 1.3), sink=0.0)
    e2 = cover_pts(1, 4.0, 0.25)
    put_variants("Gravillons", 3, e2, scale=(0.6, 1.0), sink=0.0)
    print("sol en couches : %d touffes d'herbe, %d hautes herbes, %d tas de graviers, %d mottes de terre  %.0fs"
          % (len(g_) + len(t2), len(t_), len(gr) + len(e2), len(e_), time.time() - T0), flush=True)

INST = {k: np.concatenate(v).astype(np.float32) for k, v in INST.items()}
# rien dans l'eau des gorges (les parois gardent leurs rochers et leurs buissons accrochés)
if V.get("river_rim") is not None:
    _rim = V["river_poly"].buffer(2.5)
    for k in list(INST):
        a = INST[k]
        m = shapely.contains_xy(_rim, a[:, 0], a[:, 1])
        if m.any():
            INST[k] = a[~m]
with open("nature_out.pkl", "wb") as f:
    pickle.dump(INST, f)
tot = sum(len(v) for v in INST.values())
print("instances de végétation:", tot, {k: len(v) for k, v in sorted(INST.items())})
print("%.0fs" % (time.time() - T0))
