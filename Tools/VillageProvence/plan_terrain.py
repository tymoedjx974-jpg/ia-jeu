"""Étape 1 : données vectorielles classées + terrain (relief réel corrigé) + couches de sol."""
import sys, pickle, collections, time
sys.path.insert(0, ".")
from common import *
from geo import load
from dem import sample_xy
from scipy import ndimage
from shapely.ops import linemerge, nearest_points

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

# ---------------------------------------------------------------- ceinture du village : ~500 m de champs de lavande (oliviers et cyprès épars,
# une dizaine de mas avec jardin),
# puis une forêt dense ; les ocres (falaises, sables, carrières) restent à nu. Fait après le calcul du sol : le relief
# (corrigé de la canopée réelle) ne change pas.
LAV_W, FOREST_W = 500.0, 600.0
MAX_MAS = 10          # maisons isolées gardées dans les champs de lavande
_near = [b["poly"] for b in blds if b["poly"].centroid.distance(CENTER) < 500]
_blob = unary_union([p_.buffer(15.0) for p_ in _near])
village = unary_union([p_ for p_ in polys_of(_blob) if p_.intersects(core.buffer(30.0))])
village = village.buffer(10.0).buffer(-10.0).simplify(2.0)
village = unary_union([Polygon(p_.exterior) for p_ in polys_of(village)])     # cours et jardins intérieurs : dans le village
ochre_keep = unary_union([ln.buffer(30.0) for ln in V["cliffs"]] + [p_.buffer(8.0) for p_ in V["sand"] + V["quarry"] + V["rock"]])
water = unary_union(V["ponds"] + V["pools"])
# quartier des Ocres : village perché sur une colline modelée au nord-est de la coulée d'ocre
from quartier import make_hill, shape_ground, new_quarter
hill = make_hill(V, CENTER, rng)
ground, hill_base = shape_ground(ground, Xg, Yg, hill, ochre_keep, village)
# rivière des Ocres : source en haut du ravin d'ocre, canyon dans l'ocre, passage entre les deux villages, plaine au nord
from riviere import trace_ok as trace, carve, river_polygon, river_rim, cut_roads
_keep_b = [b for b in blds if village.buffer(5.0).contains(b["poly"].centroid) or not village.buffer(LAV_W).contains(b["poly"].centroid)]
riv_line, riv_info = trace(V, ground, village, hill, _keep_b, rng)
ground_pre = ground.copy()
ground, riv = carve(ground, Xg, Yg, riv_line, rng)
riv_wet = river_polygon(riv, 0.0)
riv_rim = river_rim(riv, 0.0)                # gorges : jusqu'au bord des falaises
riv_corr = river_rim(riv, 8.0)
_n0 = len(blds)
_rim8 = river_rim(riv, 8.0)


def _au_bord(b):
    """Maison posée sur le bord de la falaise (sol qui plonge sous son emprise)."""
    if not b["poly"].intersects(_rim8):
        return False
    cs = np.array(b["poly"].exterior.coords)
    zz = grid_sample(ground, cs[:, 0], cs[:, 1])
    return float(zz.max() - zz.min()) > 3.0


blds = [b for b in blds if not b["poly"].intersects(river_rim(riv, 3.0)) and not _au_bord(b)]
print("gorges : %d bâtiments retirés au bord des falaises (dont %d du vieux village)" % (_n0 - len(blds),
      sum(1 for b in _keep_b if village.buffer(5.0).contains(b["poly"].centroid) and b["poly"].intersects(river_rim(riv, 3.0)))))
_gy, _gx = np.gradient(ground, RES)
_slope = np.degrees(np.arctan(np.hypot(_gx, _gy))).astype(np.float32)
quarter, q_blds, q_roads, q_plaza, q_drop = new_quarter(V, roads, unary_union([ochre_keep, riv_corr]), village,
                                                        lambda x, y: float(grid_sample(_slope, [x], [y])[0]), rng, hill)
_drop = {id(r) for r in q_drop}
roads = [r for r in roads if id(r) not in _drop]
blds = [b for b in blds if not quarter.contains(b["poly"].centroid)] + q_blds
# les raccords du quartier ne franchissent pas la rivière : c'est le rôle du grand pont
q_roads = [r for r in q_roads if not (len(r["line"].coords) == 2 and r["line"].intersects(riv_rim))]
roads += q_roads
# le grand pont : presque horizontal, du vieux village jusqu'au flanc de la colline, puis la Grand-Rue monte dans le quartier
from riviere import grand_bridge
_old_b = [b for b in blds if not b["id"].startswith("quartier")]
g_br, g_acc = grand_bridge(roads, _old_b, q_roads, ground, riv, riv_info["gap"], hill.C)
if g_br is not None:
    _cor = unary_union([g_br["line"].buffer(g_br["width"] / 2 + 1.5)] + [r["line"].buffer(r["width"] / 2 + 1.0) for r in g_acc])
    blds = [b for b in blds if not b["poly"].intersects(_cor)]
grand_line = g_br["line"] if g_br is not None else None
# le grand pont est le seul passage : les autres routes s'arrêtent au bord des gorges
roads = cut_roads(roads, riv_rim)
V["bridges"] = [g_br] if g_br is not None else []
if g_br is not None:
    roads += g_acc
V["river"] = riv
V["river_poly"] = riv_wet
V["river_rim"] = riv_rim
_rp = river_rim(riv, 3.0)
for key in ("vineyard", "olive", "orchard", "farmland", "meadow", "lavender", "scrub", "lc_shrub", "grass_nat", "forest", "lc_forest", "lawn", "residential"):
    V[key] = [q for p_ in V[key] for q in polys_of(p_.difference(_rp)) if q.area > 20]
print("méandres : amplitude x%.2f" % riv_info["amp"])
print("rivière : %.0f m, %d ponts (grand pont %.0f m)" % (riv_line.length, len(V["bridges"]),
      max([b_["line"].length for b_ in V["bridges"] if b_["grand"]] or [0])))
V["plaza"] += q_plaza
for key in ("vineyard", "olive", "orchard", "farmland", "meadow", "lavender", "scrub", "lc_shrub", "grass_nat", "forest", "lc_forest", "lawn"):
    V[key] = [q for p_ in V[key] for q in polys_of(p_.difference(quarter)) if q.area > 20]
core = unary_union([core, quarter])
V["core"] = core
village = unary_union([village, quarter.buffer(10.0)])
V["quartier"] = quarter
print("quartier des Ocres : colline de %.0f x %.0f m (pied à %.1f m), %d maisons, %d rues, %.1f ha" %
      (2 * hill.Ra, 2 * hill.Rb, hill_base, len(q_blds), len(q_roads), quarter.area / 1e4))
ring_all = village.buffer(LAV_W).difference(village).intersection(ZB)
band_all = village.buffer(LAV_W + FOREST_W).difference(village.buffer(LAV_W)).intersection(ZB)


def _cut(key, g):
    V[key] = [q for p_ in V[key] for q in polys_of(p_.difference(g)) if q.area > 20]


# une mer de lavande : seules une dizaine de maisons bien espacées restent dans la ceinture (avec leur jardin), les autres
# constructions et leurs dessertes disparaissent
_in_ring = [b for b in blds if ring_all.contains(b["poly"].centroid)]
_cands = [b for b in _in_ring if 70 <= b["poly"].area <= 320 and b["poly"].distance(village) > 60 and b["poly"].distance(riv_rim) > 50
          and b["poly"].centroid.distance(village.buffer(LAV_W).exterior if village.buffer(LAV_W).geom_type == "Polygon" else village.buffer(LAV_W).boundary) > 40]
rng.shuffle(_cands)
mas = []
for b in _cands:
    if len(mas) < MAX_MAS and all(b["poly"].distance(m["poly"]) > 120 for m in mas):
        mas.append(b)
_mas_ids = {id(b) for b in mas}
blds = [b for b in blds if not ring_all.contains(b["poly"].centroid) or id(b) in _mas_ids]
mas_zone = unary_union([m["poly"].buffer(16.0) for m in mas]) if mas else Polygon()
V["lawn"] += [m["poly"].buffer(14.0, join_style=2).difference(m["poly"].buffer(1.0)) for m in mas]
V["mas"] = [m["poly"] for m in mas]
V["pools"] = [p_ for p_ in V["pools"] if not ring_all.contains(p_.centroid) or p_.distance(mas_zone) < 5]
_n_roads = len(roads)
roads = [r for r in roads if not (r["cls"] in ("service", "residential", "living_street", "footway", "steps", "pedestrian")
                                   and r["line"].intersection(ring_all).length > 0.6 * r["line"].length
                                   and r["line"].distance(mas_zone) > 25)]
_cut("residential", ring_all)
# haies de cyprès brise-vent : retirées des champs (on veut quelques cyprès, pas des murs), gardées autour des mas
V["hedges"] = [h for h in V["hedges"] if h.intersection(ring_all).length < 0.5 * h.length or h.distance(mas_zone) < 20]
print("ceinture : %d maisons gardées sur %d, %d dessertes retirées" % (len(mas), len(_in_ring), _n_roads - len(roads)))
water = unary_union(V["ponds"] + V["pools"])

# on vide la ceinture de ses anciennes cultures, et la bande de forêt de ses champs et garrigues
for key in ("vineyard", "olive", "orchard", "farmland", "meadow", "lavender", "scrub", "lc_shrub", "grass_nat", "forest", "lc_forest"):
    _cut(key, ring_all)
for key in ("vineyard", "olive", "orchard", "farmland", "meadow", "lavender", "scrub", "lc_shrub", "grass_nat", "lawn"):
    _cut(key, band_all)
gardens = unary_union(V["lawn"] + [p_ for ps, _ in V["pitch"] for p_ in ps] + V["cemetery"] + V["farmyard"])
ring = ring_all.difference(ochre_keep).difference(water.buffer(3.0)).difference(gardens.buffer(2.0)).difference(riv_corr)
# parcelles de lavande irrégulières (Voronoï, ~45 m) : chacune a ses rangs dans sa propre direction
_seeds = []
_bx0, _by0, _bx1, _by1 = ring.bounds
for _x in np.arange(_bx0, _bx1, 45.0):
    for _y in np.arange(_by0, _by1, 45.0):
        _seeds.append((_x + rng.uniform(-18, 18), _y + rng.uniform(-18, 18)))
_cells = shapely.voronoi_polygons(shapely.MultiPoint(_seeds), extend_to=ring.envelope.buffer(50))
lav = [q for c_ in polys_of(_cells) for q in polys_of(c_.intersection(ring)) if q.area > 60]
V["lavender"] += lav
V["lavender_ring"] = polys_of(ring)
dense = band_all.difference(ochre_keep).difference(water.buffer(3.0)).difference(river_rim(riv, 4.0))
V["forest_dense"] = polys_of(dense)
V["forest"] += V["forest_dense"]
forest_all = V["forest"] + V["lc_forest"]
print("ceinture : %d parcelles de lavande (%.0f ha), forêt dense %.0f ha" % (len(lav), ring.area / 1e4, dense.area / 1e4))

Bm = rasterize([b["poly"] for b in blds]).astype(np.float32) / 255.0     # bâti à jour (maisons retirées, quartier neuf)
# relief naturel renforcé hors du village : ondulations de colline, buttes, bosses, ravines d'écoulement
def _norm(a):
    return (a - a.mean()) / (a.std() + 1e-6)
b_dist = ndimage.distance_transform_edt(Bm < 0.5) * RES
core_m = ndimage.gaussian_filter(rasterize([core.buffer(40.0)]).astype(np.float32) / 255.0, 8.0)
riv_m = ndimage.gaussian_filter(rasterize([river_rim(riv, 20.0)]).astype(np.float32) / 255.0, 5.0)
NAT = (smoothstep(12.0, 70.0, b_dist) * (1.0 - core_m) * (1.0 - riv_m)).astype(np.float32)
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
# la forêt dense est tramée à part : les trous (clairières, champs) des autres polygones de forêt ne doivent pas l'effacer
forest = blur(np.maximum(rasterize(forest_all), rasterize(V["forest_dense"])), 1.5)
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
# lit et berges de la rivière : galets et terre nue
rivb = blur(rasterize([river_rim(riv, 1.0)]), 1.0)
W *= (1.0 - 0.85 * rivb)[None]
# dans le ravin d'ocre, les parois des gorges restent ocre (canyon), ailleurs roche calcaire
och_near = blur(rasterize([g_.buffer(45.0) for g_ in ochre_geoms]), 4.0)
W[L["ochre"]] += 3.0 * rivb * och_near
W[L["rock"]] += 1.4 * rivb * (1 - och_near)
W[L["dirt"]] += 0.3 * rivb
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
