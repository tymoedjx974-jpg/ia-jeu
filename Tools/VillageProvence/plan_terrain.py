"""Étape 1 : données vectorielles classées + terrain (relief réel corrigé) + couches de sol."""
import sys, pickle, collections, time
sys.path.insert(0, ".")
from common import *
from geo import load
from dem import sample_xy
from scipy import ndimage
from shapely.ops import linemerge

t0 = time.time()
rng = np.random.default_rng(42)
ZB = ZBOX.buffer(80.0)
CENTER = Point(-10.0, 0.0)


def clip(g):
    if g is None or g.is_empty or not g.intersects(ZB):
        return None
    g = g.intersection(ZB)
    return None if g.is_empty else g


V = collections.defaultdict(list)

# ---------------------------------------------------------------- nature (OSM via Overture "land")
for r in load("land"):
    g = clip(r["geom"])
    if g is None:
        continue
    st, cl = r["subtype"], r["class"]
    if st == "forest":
        V["forest"] += polys_of(g)
    elif st == "shrub":
        V["scrub"] += polys_of(g)
    elif st == "grass":
        V["grass_nat"] += polys_of(g)
    elif st == "rock":
        V["rock"] += polys_of(g)
    elif st == "sand":
        V["sand"] += polys_of(g)
    elif cl == "cliff":
        V["cliffs"] += lines_of(g)
    elif cl == "tree" and g.geom_type == "Point":
        V["trees"].append((g.x, g.y, (r["source_tags"] or {}).get("genus") or (r["source_tags"] or {}).get("species") or ""))
    elif cl == "tree_row":
        V["tree_rows"] += lines_of(g)

# ---------------------------------------------------------------- occupation du sol
for r in load("land_use"):
    g = clip(r["geom"])
    if g is None:
        continue
    st, cl, tags = r["subtype"], r["class"], (r["source_tags"] or {})
    ps = polys_of(g)
    if not ps:
        continue
    if cl == "vineyard":
        V["vineyard"] += ps
    elif cl == "orchard":
        if tags.get("trees") == "olive_trees" or "olive" in (tags.get("produce") or ""):
            V["olive"] += ps
        else:
            V["orchard"] += ps
    elif cl == "farmland":
        if tags.get("crop") == "lavender":
            V["lavender"] += ps
        else:
            V["farmland"] += ps
    elif cl == "meadow":
        V["meadow"] += ps
    elif cl in ("grass", "garden", "village_green", "park", "recreation_ground", "playground"):
        V["lawn"] += ps
    elif cl == "residential":
        V["residential"] += ps
    elif cl in ("plaza", "pedestrian"):
        V["plaza"] += ps
    elif cl in ("cemetery", "grave_yard"):
        V["cemetery"] += ps
    elif cl == "pitch":
        V["pitch"].append((ps, tags.get("sport")))
    elif cl in ("quarry", "landfill", "brownfield"):
        V["quarry"] += ps
    elif cl in ("farmyard",):
        V["farmyard"] += ps
    elif cl in ("camp_site", "resort"):
        V["lawn"] += ps

# couverture satellite (ESA WorldCover) : complète forêt / garrigue hors parcelles
parcels_union = unary_union(V["vineyard"] + V["olive"] + V["orchard"] + V["lavender"] + V["farmland"] + V["meadow"] + V["lawn"] + V["residential"])
for r in load("land_cover"):
    g = clip(r["geom"])
    if g is None:
        continue
    if r["subtype"] in ("forest", "shrub"):
        g = g.difference(parcels_union)
        V["lc_" + r["subtype"]] += [p for p in polys_of(g) if p.area > 400]

# ---------------------------------------------------------------- eau
for r in load("water"):
    g = clip(r["geom"])
    if g is None:
        continue
    st, cl = r["subtype"], r["class"]
    if cl == "swimming_pool":
        V["pools"] += [p for p in polys_of(g) if 8 < p.area < 400]
    elif st in ("stream", "canal", "river"):
        V["streams"] += lines_of(g)
    elif st in ("pond", "water", "reservoir"):
        V["ponds"] += [p for p in polys_of(g) if p.area > 15]

# ---------------------------------------------------------------- infrastructures
for r in load("infrastructure"):
    g = clip(r["geom"])
    if g is None:
        continue
    st, cl = r["subtype"], r["class"]
    if cl == "hedge":
        V["hedges"] += lines_of(g) + [p.exterior for p in polys_of(g)]
    elif cl == "wall":
        V["walls"] += lines_of(g) + [p.exterior for p in polys_of(g)]
    elif cl == "retaining_wall":
        V["retaining"] += lines_of(g)
    elif cl == "fence":
        V["fences"] += lines_of(g)
    elif g.geom_type == "Point":
        key = {"bench": "benches", "fountain": "fountains", "drinking_water": "drinking", "viewpoint": "viewpoints",
               "bus_stop": "bus_stops", "power_pole": "power_poles", "waste_basket": "bins", "information": "info",
               "post_box": "post_boxes", "artwork": "artworks", "milestone": "milestones", "fire_hydrant": "hydrants"}.get(cl)
        if key:
            V[key].append((g.x, g.y))
    elif cl == "parking":
        V["parking"] += polys_of(g)
    elif cl == "minor_line":
        V["power_lines"] += lines_of(g)

# ---------------------------------------------------------------- lieux (commerces, services)
KEEP = {"restaurant", "cafe", "bar", "bakery", "hair_salon", "beauty_salon", "pharmacy", "post_office", "grocery_store",
        "art_gallery", "hotel", "library", "museum", "ice_cream_shop", "town_hall", "fashion_boutique", "home_goods_store",
        "brewery", "winery", "liquor_store", "arts_crafts_and_hobby_store", "bed_and_breakfast", "church", "school",
        "butcher_shop", "tobacco_shop", "newsstand", "gift_shop", "souvenir_shop", "wine_bar", "pizza_restaurant",
        "french_restaurant", "mediterranean_restaurant", "spa", "florist", "real_estate_agent", "cultural_center"}
BAD_NAMES = ("Lacoste", "Théziers", "saussan", "Uzès", "Chanas", "Dèze", "Cataluna", "Rosellon", "Point.P", "Montgolfière", "Beaumettes")
for r in load("places_region", ["geometry", "names", "basic_category", "taxonomy", "confidence", "operating_status"]):
    g = r["geom"]
    if not ZBOX.contains(g) or (r["confidence"] or 0) < 0.5:
        continue
    name = (r["names"] or {}).get("primary") or ""
    if any(b in name for b in BAD_NAMES):
        continue
    tax = (r["taxonomy"] or {}).get("primary")
    cat = r["basic_category"]
    kind = tax if tax in KEEP else (cat if cat in KEEP else None)
    if kind is None and cat in ("restaurant", "casual_eatery", "bar"):
        kind = "restaurant"
    if kind:
        V["places"].append(dict(x=g.x, y=g.y, kind=kind, name=name, conf=r["confidence"]))

# ---------------------------------------------------------------- routes
ROADCLS = {
    "primary": ("asphalt", 7.0, 50), "secondary": ("asphalt", 6.5, 45), "tertiary": ("asphalt", 5.6, 40),
    "residential": ("asphalt", 4.6, 30), "unclassified": ("asphalt", 4.2, 30), "living_street": ("stone", 4.0, 28),
    "pedestrian": ("stone", 4.0, 27), "service": ("asphalt", 3.6, 20), "track": ("dirt", 3.0, 10),
    "path": ("path", 1.4, 5), "footway": ("path", 1.8, 6), "steps": ("steps", 2.0, 26), "cycleway": ("asphalt", 2.5, 15),
    "bridleway": ("path", 1.8, 5),
}
raw_roads = collections.defaultdict(list)
for r in load("segments"):
    if r["subtype"] != "road" or r["class"] not in ROADCLS:
        continue
    g = clip(r["geom"])
    if g is None:
        continue
    cl, sub = r["class"], r["subclass"]
    surf_tag = None
    if r["road_surface"]:
        surf_tag = r["road_surface"][0].get("value")
    surface, width, prio = ROADCLS[cl]
    if cl == "service":
        if sub == "driveway":
            surface, width, prio = ("gravel" if surf_tag != "paved" else "asphalt"), 3.0, 18
        elif sub == "parking_aisle":
            width = 5.0
        elif sub == "alley":
            surface, width = "stone", 2.6
        if surf_tag in ("gravel", "unpaved", "dirt", "compacted", "fine_gravel"):
            surface = "gravel"
    if cl in ("track",) and surf_tag == "paved":
        surface, width = "asphalt", 3.0
    if cl in ("residential", "unclassified") and surf_tag in ("unpaved", "gravel", "dirt"):
        surface = "gravel"
    if cl in ("path", "footway") and surf_tag in ("paving_stones", "paved"):
        surface = "stone"
    name = (r["names"] or {}).get("primary") or ""
    for ln in lines_of(g):
        raw_roads[(cl, surface, width, prio, name)].append(ln)

roads = []
for (cl, surface, width, prio, name), lns in raw_roads.items():
    merged = linemerge(lns) if len(lns) > 1 else lns[0]
    for ln in lines_of(merged):
        if ln.length < 2.0:
            continue
        roads.append(dict(cls=cl, surface=surface, width=width, prio=prio, name=name, line=ln))

# ---------------------------------------------------------------- bâtiments
blds = []
for r in load("buildings"):
    g = r["geom"]
    if not ZBOX.buffer(-5).contains(g.centroid):
        continue
    for p in polys_of(g):
        p = p.buffer(0)
        if p.is_empty or p.area < 6:
            continue
        p = shapely.simplify(p, 0.15)
        if p.geom_type != "Polygon" or p.area < 6:
            continue
        blds.append(dict(poly=p, cls=r["class"], subtype=r["subtype"], name=(r["names"] or {}).get("primary") or "",
                         height=r["height"], floors=r["num_floors"], id=r["id"]))
print("bâtiments:", len(blds))

# village ancien : grappe dense autour de la place
near = [b["poly"] for b in blds if b["poly"].centroid.distance(CENTER) < 420]
blob = unary_union([p.buffer(7.0) for p in near])
core = None
for p in polys_of(blob):
    if p.contains(CENTER) or p.distance(CENTER) < 20:
        core = p if core is None or p.area > core.area else core
core = core.buffer(-4.0)
# les maisons les plus éloignées du centre (lotissements) ne font pas partie du vieux village
core = core.intersection(CENTER.buffer(330))
V["core"] = core
print("vieux village: %.0f m², %.0f s" % (core.area, time.time() - t0))

# ---------------------------------------------------------------- TERRAIN
Xg, Yg = np.meshgrid(XS, YS)
Zd = sample_xy(Xg, Yg, order=3).astype(np.float32) - ZONE["z0"]
print("MNS échantillonné %.0f s" % (time.time() - t0))

forest_all = V["forest"] + V["lc_forest"]
Fm = rasterize(forest_all).astype(np.float32) / 255.0
Bm = rasterize([b["poly"] for b in blds]).astype(np.float32) / 255.0
Fb = ndimage.gaussian_filter(Fm, 6.0)
Bb = ndimage.gaussian_filter(Bm, 8.0)
ground = Zd - 5.0 * Fb - 6.0 * Bb
ground = ndimage.gaussian_filter(ground, 3.0)

fields = rasterize(V["vineyard"] + V["olive"] + V["orchard"] + V["lavender"] + V["farmland"] + V["meadow"]).astype(np.float32) / 255.0
fields_b = ndimage.gaussian_filter(fields, 3.0)
n1 = fbm((NY, NX), 40, octaves=3, seed=11)
n2 = fbm((NY, NX), 7, octaves=2, seed=12)
micro = 1.4 * n1 * (1.0 - 0.65 * fields_b) + 0.35 * n2 * (1.0 - 0.8 * fields_b)
ground = ground + micro.astype(np.float32)

# relief naturel renforcé hors du village : ondulations de colline, buttes, bosses, ravines d'écoulement
def _norm(a):
    return (a - a.mean()) / (a.std() + 1e-6)
b_dist = ndimage.distance_transform_edt(Bm < 0.5) * RES
core_m = ndimage.gaussian_filter(rasterize([core.buffer(40.0)]).astype(np.float32) / 255.0, 8.0)
NAT = (smoothstep(12.0, 70.0, b_dist) * (1.0 - core_m)).astype(np.float32)
h_hill = _norm(fbm((NY, NX), 70, 3, seed=21))       # ~140 m
h_mound = _norm(fbm((NY, NX), 12, 2, seed=22))      # ~25 m
h_bump = _norm(fbm((NY, NX), 3, 2, seed=23))        # ~6 m
rv = _norm(fbm((NY, NX), 40, 2, seed=24))
ravine = np.exp(-(rv / 0.14) ** 2) * smoothstep(-0.3, 0.8, _norm(fbm((NY, NX), 90, 2, seed=25)))
relief = 2.6 * h_hill + 0.9 * h_mound + 0.28 * h_bump - 2.4 * ravine
# les parcelles cultivées restent plus douces (terrasses), les bois et la garrigue plus accidentés
ground = ground + (relief * NAT * (1.0 - 0.6 * fields_b)).astype(np.float32)
# affleurements calcaires : sommets des bosses en garrigue et en forêt
OUTCROP = (smoothstep(1.1, 2.2, h_mound + 0.5 * h_bump) * NAT * (1.0 - fields_b)).astype(np.float32)

# falaises d'ocre : marche nette (haut à gauche du sens de tracé, bas à droite)
for ln in V["cliffs"]:
    if ln.length < 8:
        continue
    D = 26.0
    x0, y0, x1, y1 = ln.bounds
    i0 = max(0, int((x0 - D - ZONE["xmin"]) / RES)); i1 = min(NX, int((x1 + D - ZONE["xmin"]) / RES) + 2)
    j0 = max(0, int((y0 - D - ZONE["ymin"]) / RES)); j1 = min(NY, int((y1 + D - ZONE["ymin"]) / RES) + 2)
    if i1 <= i0 or j1 <= j0:
        continue
    sx, sy = np.meshgrid(XS[i0:i1], YS[j0:j1])
    pts = shapely.points(sx.ravel(), sy.ravel())
    s = shapely.line_locate_point(ln, pts)
    q = shapely.line_interpolate_point(ln, s)
    qx, qy = shapely.get_x(q), shapely.get_y(q)
    s2 = np.minimum(s + 0.5, ln.length)
    s1 = np.maximum(s - 0.5, 0)
    a = shapely.line_interpolate_point(ln, s1); b = shapely.line_interpolate_point(ln, s2)
    dx = shapely.get_x(b) - shapely.get_x(a); dy = shapely.get_y(b) - shapely.get_y(a)
    px, py = sx.ravel() - qx, sy.ravel() - qy
    cross = dx * py - dy * px
    d = np.hypot(px, py)
    side = np.where(cross >= 0, 1.0, -1.0)
    drop = 9.0
    along = smoothstep(0, 18, s) * smoothstep(0, 18, ln.length - s)
    off = 0.5 * drop * side * smoothstep(0.0, 1.6, d) * (1 - smoothstep(4.0, D, d)) * along
    ground[j0:j1, i0:i1] += off.reshape(sx.shape).astype(np.float32)

# routes : profil en long lissé + aplanissement transversal
roads.sort(key=lambda r: r["prio"])
SHOULDER = {"asphalt": 3.5, "stone": 1.2, "gravel": 2.5, "dirt": 2.5, "path": 1.5, "steps": 1.0}
SIG = {"asphalt": 9.0, "stone": 3.0, "gravel": 6.0, "dirt": 5.0, "path": 3.0, "steps": 1.5}
for rd in roads:
    ln = rd["line"]
    n = max(2, int(ln.length / 2.0) + 1)
    ss = np.linspace(0, ln.length, n)
    pp = shapely.line_interpolate_point(ln, ss)
    zz = grid_sample(ground, shapely.get_x(pp), shapely.get_y(pp), order=1)
    sig = SIG[rd["surface"]] / 2.0
    if n > 3:
        zz = ndimage.gaussian_filter1d(zz, sig, mode="nearest")
    rd["prof_s"], rd["prof_z"] = ss.astype(np.float32), zz.astype(np.float32)
    half = rd["width"] / 2.0
    D = half + SHOULDER[rd["surface"]]
    x0, y0, x1, y1 = ln.bounds
    i0 = max(0, int((x0 - D - ZONE["xmin"]) / RES)); i1 = min(NX, int((x1 + D - ZONE["xmin"]) / RES) + 2)
    j0 = max(0, int((y0 - D - ZONE["ymin"]) / RES)); j1 = min(NY, int((y1 + D - ZONE["ymin"]) / RES) + 2)
    if i1 <= i0 or j1 <= j0:
        continue
    sx, sy = np.meshgrid(XS[i0:i1], YS[j0:j1])
    pts = shapely.points(sx.ravel(), sy.ravel())
    d = shapely.distance(ln, pts)
    m = d < D
    if not m.any():
        continue
    sl = shapely.line_locate_point(ln, pts[m])
    rz = np.interp(sl, ss, zz)
    w = smoothstep(half - 0.2, D, d[m])
    sub = ground[j0:j1, i0:i1].ravel()
    sub[m] = rz * (1 - w) + sub[m] * w
    ground[j0:j1, i0:i1] = sub.reshape(sx.shape)
# places : terrasses planes (pente maximale 3 %), raccord sur 4 m
plaza_planes = []
for p in V["plaza"]:
    D = 4.0
    x0, y0, x1, y1 = p.bounds
    i0 = max(0, int((x0 - D - ZONE["xmin"]) / RES)); i1 = min(NX, int((x1 + D - ZONE["xmin"]) / RES) + 2)
    j0 = max(0, int((y0 - D - ZONE["ymin"]) / RES)); j1 = min(NY, int((y1 + D - ZONE["ymin"]) / RES) + 2)
    sx, sy = np.meshgrid(XS[i0:i1], YS[j0:j1])
    sub = ground[j0:j1, i0:i1]
    inside = shapely.contains_xy(p, sx, sy)
    if inside.sum() < 4:
        continue
    A = np.column_stack([sx[inside], sy[inside], np.ones(inside.sum())])
    coef, *_ = np.linalg.lstsq(A, sub[inside], rcond=None)
    gxp, gyp = coef[0], coef[1]
    gmag = math.hypot(gxp, gyp)
    if gmag > 0.03:
        gxp, gyp = gxp * 0.03 / gmag, gyp * 0.03 / gmag
    c0 = float(np.mean(sub[inside]) - gxp * np.mean(sx[inside]) - gyp * np.mean(sy[inside]))
    plane = gxp * sx + gyp * sy + c0
    d = shapely.distance(p, shapely.points(sx.ravel(), sy.ravel())).reshape(sx.shape)
    w = smoothstep(0.0, D, d)
    ground[j0:j1, i0:i1] = (plane * (1 - w) + sub * w).astype(np.float32)
    plaza_planes.append((p, float(gxp), float(gyp), c0))
V["plaza_planes"] = plaza_planes
# églises et chapelles (visitables) : terrain creusé sous l'emprise, au niveau le plus bas de ses abords (bâties en terrasse)
for bd in blds:
    if not (bd["name"] == "Église Saint-Michel" or bd["cls"] in ("church", "chapel")):
        continue
    pg = bd["poly"]
    ring = pg.buffer(1.5).exterior
    rp = [ring.interpolate(t, normalized=True) for t in np.linspace(0, 1, 60)]
    level = float(min(grid_sample(ground, [q_.x], [q_.y], order=1)[0] for q_ in rp)) - 0.2
    x0, y0, x1, y1 = pg.buffer(1.0).bounds
    i0 = max(0, int((x0 - ZONE["xmin"]) / RES)); i1 = min(NX, int((x1 - ZONE["xmin"]) / RES) + 2)
    j0 = max(0, int((y0 - ZONE["ymin"]) / RES)); j1 = min(NY, int((y1 - ZONE["ymin"]) / RES) + 2)
    sx, sy = np.meshgrid(XS[i0:i1], YS[j0:j1])
    inside = shapely.contains_xy(pg.buffer(0.6), sx, sy)
    sub = ground[j0:j1, i0:i1]
    sub[inside] = np.minimum(sub[inside], level)
    ground[j0:j1, i0:i1] = sub
    print("église : terrain creusé à %.1f m sous l'emprise" % level)
print("terrain + routes + places %.0f s" % (time.time() - t0))

# ---------------------------------------------------------------- couches du sol
def blur(m, s):
    return ndimage.gaussian_filter(m.astype(np.float32) / 255.0, s)

W = np.zeros((len(LAYERS), NY, NX), np.float32)
W[L["dry"]] = 0.35
gy, gx = np.gradient(ground, RES)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
scrub = blur(rasterize(V["scrub"] + V["lc_shrub"] + V["grass_nat"]), 1.5)
W[L["dry"]] += scrub
forest = blur(rasterize(forest_all), 1.5)
W[L["forest"]] += 1.3 * forest
cult = blur(rasterize(V["vineyard"] + V["lavender"] + V["orchard"] + V["olive"]), 0.8)
W[L["earth"]] += 1.6 * cult
W[L["dry"]] += 0.25 * cult
farm = blur(rasterize(V["farmland"]), 0.8)
W[L["straw"]] += 1.5 * farm
W[L["earth"]] += 0.25 * farm
mead = blur(rasterize(V["meadow"]), 1.0)
W[L["dry"]] += 0.9 * mead
W[L["grass"]] += 0.6 * mead
lawn = blur(rasterize(V["lawn"] + [p for ps, _ in V["pitch"] for p in ps]), 1.0)
W[L["grass"]] += 1.8 * lawn
resid = blur(rasterize(V["residential"]), 2.0)
W[L["grass"]] += 0.35 * resid
W[L["dry"]] += 0.2 * resid
# ocres : falaises + terrains nus autour + carrières proches du village
ochre_geoms = [ln.buffer(22.0) for ln in V["cliffs"]] + V["sand"] + V["quarry"] + V["rock"]
ochre = blur(rasterize(ochre_geoms), 3.0)
ochre_macro = np.clip(0.5 + 0.9 * fbm((NY, NX), 25, 3, seed=5), 0, 1)
W[L["ochre"]] += 2.2 * ochre * (0.6 + 0.4 * ochre_macro)
rockm = smoothstep(28.0, 42.0, slope)
W[L["rock"]] += 2.5 * rockm * (1 - np.clip(ochre * 2, 0, 1))
W[L["rock"]] += 1.8 * OUTCROP * (1 - np.clip(ochre * 2, 0, 1))
W[L["ochre"]] += 2.5 * rockm * np.clip(ochre * 2, 0, 1)
# chemins de terre et pistes
track_lines = [r["line"].buffer(r["width"] / 2.0) for r in roads if r["surface"] in ("dirt", "path")]
dirt = blur(rasterize(track_lines), 0.7)
W[L["dirt"]] += 3.0 * dirt
# bas-côtés des routes : graviers / terre battue
shoulders = [r["line"].buffer(r["width"] / 2.0 + 1.2) for r in roads if r["surface"] in ("asphalt", "gravel")]
sh = blur(rasterize(shoulders), 0.8)
W[L["dirt"]] += 0.9 * sh
W[L["rock"]] += 0.3 * sh
# cours de ferme, abords des bâtiments hors village
farmyard = blur(rasterize(V["farmyard"] + [b["poly"].buffer(4.0) for b in blds if not core.contains(b["poly"].centroid)]), 1.5)
W[L["dirt"]] += 0.7 * farmyard
# variation naturelle
var = fbm((NY, NX), 18, 3, seed=9)
W[L["dry"]] *= 1.0 + 0.5 * var
W[L["grass"]] *= 1.0 - 0.4 * var
W = np.clip(W, 0, None)
W /= W.sum(axis=0, keepdims=True) + 1e-6
splat = np.round(W.transpose(1, 2, 0) * 255).astype(np.uint8)
print("couches %.0f s" % (time.time() - t0))

np.savez_compressed("terrain.npz", ground=ground.astype(np.float32), splat=splat, slope=slope.astype(np.float16),
                    outcrop=OUTCROP.astype(np.float16), nat=NAT.astype(np.float16))
V = dict(V)
V["roads"] = roads
V["buildings"] = blds
with open("vec.pkl", "wb") as f:
    pickle.dump(V, f)
print({k: len(v) if hasattr(v, "__len__") else 1 for k, v in V.items() if k != "core"})
print("sol min/max %.1f %.1f  —  %.0f s" % (ground.min(), ground.max(), time.time() - t0))
