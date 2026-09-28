"""Étape 1 : données vectorielles classées + terrain (relief réel corrigé) + couches de sol."""
import sys, pickle, collections, time
sys.path.insert(0, ".")
from common import *
from geo import load
from dem import sample_xy
from scipy import ndimage
from shapely.ops import linemerge, nearest_points, substring
from shapely.strtree import STRtree

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
# à l'ouest et au nord-ouest du vieux village, pas de lavande : la campagne d'origine (vignes, champs, prés, oliveraies,
# garrigue) va du village jusqu'à la forêt
NOLAV = Polygon([(-1090, 950), (-1090, 1020), (-1061, 1039), (-1040, 1150), (-950, 1210), (-830, 1210), (-689, 1130), (-550, 1130),
                 (-491, 1096), (-450, 1110), (-390, 1060), (-260, 890), (-227, 815), (0, 530), (-19, 479), (30, 460), (90, 330),
                 (100, 260), (50, 180), (-20, 230), (-35, 297), (-69, 291), (-49, 169), (0, 100), (0, 40), (-20, 20), (-90, 30),
                 (-201, 80), (-230, 70), (-296, 91), (-310, 76), (-263, -17), (-82, -109), (-30, -110), (90, -190), (110, -280),
                 (80, -410), (-168, -420), (-180, -470), (-220, -490), (-340, -500), (-520, -420), (-590, -370), (-735, -213),
                 (-798, -171), (-860, -160), (-910, -110), (-960, -50), (-1020, 130), (-1020, 180), (-990, 247), (-1020, 320),
                 (-1021, 391), (-1080, 500), (-1050, 836), (-1090, 950)])
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
ring_lav = ring_all.difference(NOLAV)          # la ceinture de lavande proprement dite
ring_nat = ring_all.intersection(NOLAV)        # la campagne sans lavande
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
    _cut(key, ring_lav)
_cut("lavender", ring_nat)
# campagne sans lavande : on garde les cultures d'origine et on comble les vides (anciennes maisons, dessertes) de prés,
# champs, garrigue et oliveraies en parcelles irrégulières
_cult = unary_union([p_ for key in ("vineyard", "olive", "orchard", "farmland", "meadow", "scrub", "lc_shrub", "grass_nat", "forest",
                                    "lc_forest", "lawn", "residential") for p_ in V[key] if p_.intersects(ring_nat)])
_gap = ring_nat.difference(_cult).difference(ochre_keep).difference(river_polygon(riv, 8.0)).buffer(-0.5).buffer(0.5)
_sd = []
_bx0, _by0, _bx1, _by1 = _gap.bounds if not _gap.is_empty else (0, 0, 0, 0)
for _x in np.arange(_bx0, _bx1, 60.0):
    for _y in np.arange(_by0, _by1, 60.0):
        _sd.append((_x + rng.uniform(-24, 24), _y + rng.uniform(-24, 24)))
_nfill = collections.Counter()
if len(_sd) > 3:
    for c_ in polys_of(shapely.voronoi_polygons(shapely.MultiPoint(_sd), extend_to=_gap.envelope.buffer(60))):
        for q in polys_of(c_.intersection(_gap)):
            if q.area < 80:
                continue
            key = str(rng.choice(["meadow", "farmland", "scrub", "olive", "grass_nat"], p=[0.3, 0.22, 0.22, 0.14, 0.12]))
            V[key].append(q)
            _nfill[key] += 1
print("campagne sans lavande : %.0f ha, parcelles ajoutées %s" % (ring_nat.area / 1e4, dict(_nfill)))
for key in ("vineyard", "olive", "orchard", "farmland", "meadow", "lavender", "scrub", "lc_shrub", "grass_nat", "lawn"):
    _cut(key, band_all)
gardens = unary_union(V["lawn"] + [p_ for ps, _ in V["pitch"] for p_ in ps] + V["cemetery"] + V["farmyard"])
ring = ring_lav.difference(ochre_keep).difference(water.buffer(3.0)).difference(gardens.buffer(2.0)).difference(river_polygon(riv, 8.0))
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
dense = band_all.difference(ochre_keep).difference(water.buffer(3.0)).difference(river_polygon(riv, 8.0))
# château des Ocres : très grande forteresse sur une butte de la forêt dense, du côté du quartier perché
from chateau import pick_site, layout as castle_layout, shape_ground as castle_ground, MOAT_IN, MOAT_OUT
_gat = lambda xs, ys: grid_sample(ground, np.asarray(xs, float), np.asarray(ys, float))
_site = pick_site(dense, riv_rim, _gat, CENTER, Point(*hill.C), rng)
CH = None
if _site is not None:
    CH = castle_layout(_site, Point(*hill.C), _gat)
    _clear = CH["enc"].buffer(55.0)
    dense = dense.difference(_clear)
    for key in ("forest", "lc_forest", "scrub", "lc_shrub", "farmland", "meadow", "vineyard", "orchard", "olive", "lavender"):
        _cut(key, _clear)
    V["grass_nat"] += polys_of(_clear.difference(CH["enc"].buffer(MOAT_OUT)))
    blds = [b for b in blds if not b["poly"].intersects(_clear)]
    roads = [r for r in roads if not r["line"].intersects(CH["enc"].buffer(MOAT_OUT))]
    print("château des Ocres : centre (%.0f, %.0f), plate-forme à %.1f m, enceinte %.1f ha, %d tours" %
          (_site.x, _site.y, CH["Z0"], CH["enc"].area / 1e4, len(CH["towers"])))
V["chateau"] = CH
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
# micro-relief partout hors des bâtiments et des gorges (les routes, rues et places sont aplanies ensuite) :
# petites bosses et creux de 10 à 30 cm, pour que le sol ne soit jamais lisse
m1 = _norm(fbm((NY, NX), 2, 2, seed=41))            # ~4 m
m2 = _norm(fbm((NY, NX), 5, 2, seed=42))            # ~10 m
micro = 0.09 * m1 + 0.12 * m2
ground = ground + (micro * smoothstep(2.0, 6.0, b_dist) * (1.0 - riv_m)).astype(np.float32)
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

# château : plate-forme, fossé sec, butte et levée de terre
if CH is not None:
    ground = castle_ground(ground, Xg, Yg, CH)
    # allée du château : de la levée de terre au grand anneau du quartier, en lacets sur le flanc de la butte
    from chateau import route as castle_route
    _end = CH["frame"].P(90 + MOAT_OUT + 12, 0)
    _ring = [r["line"] for r in roads if r["surface"] == "asphalt" and quarter.buffer(20).contains(r["line"].interpolate(0.5, normalized=True))]
    _forbid = unary_union([riv_rim.buffer(15.0), CH["enc"].buffer(MOAT_OUT + 6).difference(CH["causeway"].buffer(5.0)),
                           CH["enc"]])
    _costly = unary_union([b["poly"].buffer(3.0) for b in blds if b["poly"].distance(Point(*_end)) < 1500] or [Point(0, 0).buffer(0.1)])
    _al = castle_route(ground, XS, YS, _end, _ring, _forbid, _costly) if _ring else None
    if _al is not None:
        _al = LineString([CH["frame"].P(90 + MOAT_OUT - 2, 0)] + list(_al.coords))
        roads.append(dict(cls="unclassified", surface="gravel", width=5.0, prio=26, name="Allée du Château", line=_al))
        print("château : allée de %.0f m" % _al.length)
    else:
        print("château : pas d'allée trouvée")

# ---------------------------------------------------------------- nettoyage des incohérences avant l'aplanissement
_bl_u = unary_union([b["poly"] for b in blds])
_n_r0 = len(roads)
# ruelles du vieux village et du quartier : largeur ajustée à l'espace entre les façades (elles ne passent plus dans les murs)
_narrowed = 0
for r in roads:
    ln = r["line"]
    if r["surface"] not in ("asphalt", "stone") or not core.buffer(15).contains(ln.interpolate(0.5, normalized=True)):
        continue
    ts = np.linspace(0, ln.length, max(3, int(ln.length / 3)))
    clr = np.array([_bl_u.distance(ln.interpolate(t)) for t in ts])
    fit = float(np.percentile(clr, 20)) * 2.0 - 0.3
    if fit < r["width"]:
        r["width"] = max(2.2, fit)
        _narrowed += 1
# bouts de route isolés (reliés à rien) et tronçons minuscules
_lt = STRtree([r["line"] for r in roads])
_keep = []
for k, r in enumerate(roads):
    ln = r["line"]
    touch = [j for j in _lt.query(ln.buffer(1.5)) if j != k]
    if (not touch and ln.length < 150 and r.get("name") not in ("Pont des Ocres", "Grand-Rue")) or (ln.length < 4 and not touch):
        continue
    _keep.append(r)
roads = _keep
# piscines, parkings et terrains de sport sans maison autour (restes des constructions retirées)
_near60 = _bl_u.buffer(60.0)
_np0 = len(V["pools"]) + len(V["parking"]) + len(V["pitch"])
V["pools"] = [p for p in V["pools"] if p.intersects(_bl_u.buffer(40.0))]
V["parking"] = [p for p in V["parking"] if p.intersects(_bl_u.buffer(120.0))]
V["pitch"] = [(ps, sp_) for ps, sp_ in V["pitch"] if any(p.intersects(_near60) for p in ps)]
print("nettoyage : %d ruelles ajustées aux façades, %d bouts de route isolés retirés, %d piscines/parkings/terrains orphelins retirés"
      % (_narrowed, _n_r0 - len(roads), _np0 - len(V["pools"]) - len(V["parking"]) - len(V["pitch"])))

# ---------------------------------------------------------------- petit patrimoine rural : murets de pierre sèche le long des chemins et
# entre certaines parcelles, bories (cabanes de berger en pierre sèche) dans les champs, puits près des mas
_rngp = np.random.default_rng(77)
_fields_u = unary_union(V["lavender"] + V["vineyard"] + V["orchard"] + V["olive"])
_roads_u = unary_union([r["line"].buffer(r["width"] / 2 + 1.0) for r in roads])
_avoid = unary_union([_roads_u, _bl_u.buffer(2.5), river_rim(riv, 4.0), core.buffer(30.0), ochre_keep])
murets = []
for r in roads:
    if r["surface"] not in ("asphalt", "gravel", "dirt") or r["cls"] in ("primary", "secondary") or r["line"].length < 30:
        continue
    for side in (1.0, -1.0):
        try:
            off = r["line"].offset_curve(side * (r["width"] / 2 + 1.7), join_style=2)
        except Exception:
            continue
        for ol in lines_of(off):
            t = _rngp.uniform(0, 20)
            while t < ol.length - 6:
                seg_len = _rngp.uniform(25, 70)
                seg = substring(ol, t, min(ol.length, t + seg_len))
                t += seg_len + _rngp.uniform(6, 25)
                if seg is None or seg.length < 6:
                    continue
                if _rngp.random() > 0.5 or not _fields_u.contains(seg.interpolate(0.5, normalized=True)):
                    continue
                for piece in lines_of(seg.difference(_avoid)):
                    if piece.length > 6:
                        murets.append(piece)
# quelques murets entre parcelles de lavande (limites de propriété)
for pg in polys_of(unary_union(V["lavender"])):
    if _rngp.random() > 0.06 or pg.area < 1500:
        continue
    ring_ = pg.exterior
    t0 = _rngp.uniform(0, ring_.length)
    seg = substring(ring_, t0, min(ring_.length, t0 + _rngp.uniform(30, 80)))
    for piece in lines_of(seg.difference(_avoid)):
        if piece.length > 8:
            murets.append(piece)
V["murets"] = murets
# bories : cabanes rondes en pierre sèche, isolées dans les champs et la garrigue
_cand = unary_union([unary_union(V.get("lavender_ring") or [Polygon()]), unary_union(V["scrub"] + V["lc_shrub"])]).difference(
    unary_union([_avoid.buffer(20.0), unary_union(murets).buffer(6.0) if murets else Polygon()]))
bories = []
x0_, y0_, x1_, y1_ = _cand.bounds if not _cand.is_empty else (0, 0, 0, 0)
for _ in range(4000):
    if len(bories) >= 12 or _cand.is_empty:
        break
    p_ = Point(_rngp.uniform(x0_, x1_), _rngp.uniform(y0_, y1_))
    if p_.distance(CENTER) > 1400 or not _cand.contains(p_) or any(p_.distance(Point(b_[0], b_[1])) < 180 for b_ in bories):
        continue
    bories.append((p_.x, p_.y, float(_rngp.uniform(0, 2 * math.pi))))
V["bories"] = bories
# puits : un sur deux près des mas, dans le jardin
puits = []
for m_ in V.get("mas", []):
    if _rngp.random() > 0.6:
        continue
    for _ in range(30):
        a_ = _rngp.uniform(0, 2 * math.pi)
        q_ = m_.centroid
        dd_ = math.sqrt(m_.area) / 2 + _rngp.uniform(6, 10)
        p_ = Point(q_.x + math.cos(a_) * dd_, q_.y + math.sin(a_) * dd_)
        if p_.distance(m_) > 4 and not _roads_u.contains(p_):
            puits.append((p_.x, p_.y))
            break
V["puits"] = puits
print("petit patrimoine : %d murets de pierre sèche (%.1f km), %d bories, %d puits"
      % (len(murets), sum(m_.length for m_ in murets) / 1000, len(bories), len(puits)))

# routes : profil en long lissé + pente maximale (déblais / remblais) + aplanissement transversal
GRADE = {"asphalt": 0.14, "stone": 0.20, "gravel": 0.16, "dirt": 0.20, "path": 0.30, "steps": 1.0}
# les routes principales d'abord ; les suivantes se raccordent à leur niveau aux carrefours sans retoucher la chaussée déjà posée
roads.sort(key=lambda r: -r["prio"])
SHOULDER = {"asphalt": 3.5, "stone": 1.2, "gravel": 2.5, "dirt": 2.5, "path": 1.5, "steps": 1.0}
SIG = {"asphalt": 9.0, "stone": 3.0, "gravel": 6.0, "dirt": 5.0, "path": 3.0, "steps": 1.5}
claimed = np.zeros(ground.shape, bool)
for rd in roads:
    ln = rd["line"]
    n = max(2, int(ln.length / 2.0) + 1)
    ss = np.linspace(0, ln.length, n)
    pp = shapely.line_interpolate_point(ln, ss)
    px_, py_ = shapely.get_x(pp), shapely.get_y(pp)
    zz = grid_sample(ground, px_, py_, order=1)
    ci = np.clip(np.round((px_ - ZONE["xmin"]) / RES).astype(int), 0, NX - 1)
    cj = np.clip(np.round((py_ - ZONE["ymin"]) / RES).astype(int), 0, NY - 1)
    pinned = claimed[cj, ci]                      # points déjà sur une chaussée (carrefours) : niveau imposé
    zpin = zz.copy()
    sig = SIG[rd["surface"]] / 2.0
    if n > 3:
        zz = ndimage.gaussian_filter1d(zz, sig, mode="nearest")
        zz[pinned] = zpin[pinned]
        # pente maximale : on répartit l'excès entre les deux points (déblai en haut, remblai en bas)
        gmax = GRADE[rd["surface"]] * (ss[1] - ss[0])
        for _ in range(3000):
            dz = np.diff(zz)
            ex = np.clip(np.abs(dz) - gmax, 0, None) * np.sign(dz)
            if not np.any(ex):
                break
            zz[:-1] += 0.5 * ex
            zz[1:] -= 0.5 * ex
            zz[pinned] = zpin[pinned]
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
    cl = claimed[j0:j1, i0:i1].ravel()
    w = np.where(cl[m], 1.0, w)                 # chaussées déjà posées : intactes
    sub[m] = rz * (1 - w) + sub[m] * w
    ground[j0:j1, i0:i1] = sub.reshape(sx.shape)
    cl_m = cl.copy()
    cl_m[np.nonzero(m)[0][d[m] < half]] = True
    claimed[j0:j1, i0:i1] = cl_m.reshape(sx.shape)
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
# sol en mosaïque hors des surfaces aménagées (routes, rues, places, bâtis, eau) : plaques de terre, de petits graviers,
# d'herbe et de hautes herbes, dosées selon le milieu (champs, bois, prés, garrigue, cours du village)
paved = rasterize([r["line"].buffer(r["width"] / 2 + 0.8) for r in roads if r["surface"] not in ("path", "dirt")]
                  + V["plaza"] + V["parking"] + [b["poly"].buffer(0.5) for b in blds] + V["pools"] + V["ponds"]
                  + [river_polygon(riv, 3.0)]) > 0
open_ = (~paved) & (ochre < 0.3) & (rockm < 0.5) & (dirt < 0.5)
coreb = blur(rasterize([core]), 2.0)
_nz = [np.clip(_norm(fbm((NY, NX), 3, 2, seed=s_)) * 0.9, -2.5, 2.5) for s_ in (51, 52, 53, 54)]
w_cov = np.stack([
    (0.3 + 1.1 * cult + 0.6 * forest + 0.7 * coreb + 0.4 * farm) * np.exp(_nz[0]),                          # terre
    (0.35 + 0.7 * cult + 0.9 * coreb + 0.5 * sh + 0.6 * smoothstep(12.0, 25.0, slope)) * np.exp(_nz[1]),    # petits graviers
    (0.8 + 1.2 * lawn + 0.8 * mead + 0.5 * resid + 0.3 * forest) * np.exp(_nz[2]),                          # herbe
    (0.6 + 1.1 * mead + 1.0 * scrub + 0.3 * farm) * np.exp(_nz[3]) * (1.0 - 0.7 * coreb),                  # hautes herbes
])
cover = (np.argmax(w_cov, axis=0) + 1).astype(np.uint8)
cover[~open_] = 0
_a = 1.6 * (1.0 - 0.6 * forest)
for _cls, _lay in ((1, "earth"), (2, "dirt"), (3, "grass"), (4, "dry")):
    W[L[_lay]] += _a * ndimage.gaussian_filter((cover == _cls).astype(np.float32), 0.8)
print("sol en mosaïque : terre %.0f %%, graviers %.0f %%, herbe %.0f %%, hautes herbes %.0f %%" %
      tuple(100.0 * (cover == c_).sum() / max(1, (cover > 0).sum()) for c_ in (1, 2, 3, 4)))
# variation naturelle
var = fbm((NY, NX), 18, 3, seed=9)
W[L["dry"]] *= 1.0 + 0.5 * var
W[L["grass"]] *= 1.0 - 0.4 * var
# lit et berges de la rivière : galets et terre nue
# seules les vraies parois (pente forte) sont traitées en falaise ; les rives en pente douce gardent leur sol et leurs cultures
rivb = blur(rasterize([river_rim(riv, 1.0)]), 1.0) * smoothstep(24.0, 38.0, slope)
rivb = np.maximum(rivb, blur(rasterize([river_polygon(riv, 2.0)]), 1.0))
W *= (1.0 - 0.85 * rivb)[None]
# dans le ravin d'ocre, les parois des gorges restent ocre (canyon), ailleurs roche calcaire
och_near = blur(rasterize([g_.buffer(45.0) for g_ in ochre_geoms]), 4.0)
W[L["ochre"]] += 3.0 * rivb * och_near
# parois calcaires en strates (bancs clairs et bancs plus sombres, comme dans les gorges du Verdon), un peu de terre
# et de végétation sur les vires
# ressauts (pente forte) en roche nue, vires (pente faible) en terre et litière : les gradins se lisent de loin
rivw = blur(rasterize([river_rim(riv, 1.0)]), 1.0) * (1 - blur(rasterize([river_polygon(riv, 1.0)]), 1.0))
_ledge = 1.0 - smoothstep(30.0, 50.0, slope)
W *= (1.0 - 0.85 * rivw * _ledge)[None]
_mott = np.clip(0.5 + 0.5 * _norm(fbm((NY, NX), 5, 2, seed=64)), 0, 1)        # taches de végétation et de roche sombre
W[L["rock"]] += 0.7 * rivb * (1 - och_near) * (1 - _ledge) * (1.1 - 0.8 * _mott)
W[L["forest"]] += 2.2 * rivw * (1 - och_near) * np.maximum(_ledge, 0.9 * _mott)
W[L["grass"]] += 2.0 * rivw * (1 - och_near) * (0.4 + 0.6 * _mott)
W[L["dry"]] += 0.6 * rivw * (1 - och_near) * (1 - _mott)
W[L["dirt"]] += 0.6 * rivw * (1 - och_near) * _ledge
W[L["dirt"]] += 0.3 * rivb
# château : cour en terre battue et gravier, fossé herbeux semé de pierres
if CH is not None:
    _cm = blur(rasterize([CH["enc"].buffer(1.0)]), 1.0)
    W *= (1.0 - 0.9 * _cm)[None]
    W[L["dirt"]] += 0.55 * _cm
    W[L["dry"]] += 0.35 * _cm
    _mo = blur(rasterize([CH["enc"].buffer(MOAT_OUT).difference(CH["enc"].buffer(MOAT_IN))]), 1.5)
    W *= (1.0 - 0.7 * _mo)[None]
    W[L["grass"]] += 0.7 * _mo
    W[L["rock"]] += 0.25 * _mo
W = np.clip(W, 0, None)
W /= W.sum(axis=0, keepdims=True) + 1e-6
splat = np.round(W.transpose(1, 2, 0) * 255).astype(np.uint8)
# ombre des gorges : la roche s'assombrit en descendant vers l'eau (moins de lumière, suintements, patine noire
# et mousses), par taches ; appliquée à l'export en baissant l'intensité des couches (le splat reste normalisé)
_top = ndimage.gaussian_filter(ndimage.maximum_filter(ground, size=61), 10.0)
_deep = smoothstep(4.0, 85.0, np.clip(_top - ground, 0, None))
_gz = blur(rasterize([river_rim(riv, 1.0).buffer(6.0)]), 3.0)
_var = np.clip(0.5 + 0.5 * _norm(fbm((NY, NX), 3, 2, seed=77)), 0, 1)       # coulées sombres de quelques mètres
shade = 1.0 - _gz * (0.36 + 0.4 * _deep + 0.12 * och_near) * (0.75 + 0.4 * _var) * (0.85 + 0.25 * _mott)
shade = np.clip(shade, 0.28, 1.0)
print("ombre des gorges : %.0f %% de la carte, facteur mini %.2f" % (100.0 * (shade < 0.97).mean(), shade.min()))
print("couches %.0f s" % (time.time() - t0))

np.savez_compressed("terrain.npz", ground=ground.astype(np.float32), splat=splat, slope=slope.astype(np.float16),
                    outcrop=OUTCROP.astype(np.float16), nat=NAT.astype(np.float16), cover=cover,
                    shade=shade.astype(np.float16))
V = dict(V)
V["roads"] = roads
V["buildings"] = blds
with open("vec.pkl", "wb") as f:
    pickle.dump(V, f)
print({k: len(v) if hasattr(v, "__len__") else 1 for k, v in V.items() if k != "core"})
print("sol min/max %.1f %.1f  —  %.0f s" % (ground.min(), ground.max(), time.time() - t0))
