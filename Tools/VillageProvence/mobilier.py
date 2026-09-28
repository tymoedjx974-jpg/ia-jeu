"""Étape 5 : piscines, fontaines, monument aux morts, bancs, réverbères, panneaux, table d'orientation."""
import sys, pickle, math, json, time, collections
sys.path.insert(0, ".")
from common import *
from geomlib import MB, box, tube, revolve, disk, rect_sign, planar_polygon, triangulate, nrm, WHITE
from signs_tex import DIRECTIONS

T0 = time.time()
GROUND = np.load("terrain.npz")["ground"]
V = pickle.load(open("vec.pkl", "rb"))
SIGNS = json.load(open("tex/Enseignes.json", encoding="utf-8"))
rng = np.random.default_rng(99)
CHUNK = 128.0
CENTER = Point(-10.0, 0.0)
chunks = collections.defaultdict(MB)
inst = collections.defaultdict(list)


def zat(x, y):
    return float(grid_sample(GROUND, [x], [y], order=1)[0])


def mb_at(x, y):
    return chunks[(int(math.floor(x / CHUNK)), int(math.floor(y / CHUNK)))]


# ------------------------------------------------------------------ piscines
def pool(p):
    p = shapely.simplify(p, 0.1)
    if p.geom_type != "Polygon" or p.area < 8:
        return
    cs = np.array(p.exterior.coords)
    z = min(zat(x, y) for x, y in cs[:-1]) + 0.05
    c = p.centroid
    mb = mb_at(c.x, c.y)
    # margelle en pierre
    ring = p.buffer(0.4, join_style=2).difference(p)
    for pg in polys_of(ring):
        v2, idx = triangulate(np.array(pg.exterior.coords), [np.array(h.coords) for h in pg.interiors])
        P = np.column_stack([v2, np.full(len(v2), z + 0.06)])
        mb.add("PierreTaille", P, [(0, 0, 1)], v2 / 3.0, [WHITE], idx)
    outer = p.buffer(0.4, join_style=2)
    oc = np.array(outer.exterior.coords)
    for k in range(len(oc) - 1):
        a, b = oc[k], oc[k + 1]
        mb.quad("PierreTaille", (a[0], a[1], z - 0.4), (b[0], b[1], z - 0.4), (b[0], b[1], z + 0.06), (a[0], a[1], z + 0.06), [(0, 0.1), (1, 0.1), (1, 0), (0, 0)])
    # parois et fond du bassin
    for k in range(len(cs) - 1):
        a, b = cs[k], cs[k + 1]
        mb.quad("Piscine", (b[0], b[1], z - 1.4), (a[0], a[1], z - 1.4), (a[0], a[1], z + 0.06), (b[0], b[1], z + 0.06), [(0, 1), (1, 1), (1, 0), (0, 0)])
    v2, idx = triangulate(cs, [])
    mb.add("Piscine", np.column_stack([v2, np.full(len(v2), z - 1.4)]), [(0, 0, 1)], v2 / 2.0, [WHITE], idx)
    mb.add("EauPiscine", np.column_stack([v2, np.full(len(v2), z - 0.12)]), [(0, 0, 1)], v2 / 2.0, [WHITE], idx)


for p in V["pools"]:
    pool(p)
print("piscines:", len(V["pools"]), "%.0fs" % (time.time() - T0))


# ------------------------------------------------------------------ fontaine de place
def fountain(x, y, r=1.4):
    z = zat(x, y)
    mb = mb_at(x, y)
    n = 8
    ang = [2 * math.pi * (k + 0.5) / n for k in range(n)]
    outer = [(x + r * math.cos(a) / math.cos(math.pi / n), y + r * math.sin(a) / math.cos(math.pi / n)) for a in ang]
    inner = [(x + (r - 0.25) * math.cos(a) / math.cos(math.pi / n), y + (r - 0.25) * math.sin(a) / math.cos(math.pi / n)) for a in ang]
    h = 0.65
    for k in range(n):
        a, b = outer[k], outer[(k + 1) % n]
        mb.quad("PierreTaille", (a[0], a[1], z - 0.3), (b[0], b[1], z - 0.3), (b[0], b[1], z + h), (a[0], a[1], z + h), [(0, 0.3), (0.6, 0.3), (0.6, 0), (0, 0)])
        ai, bi = inner[k], inner[(k + 1) % n]
        mb.quad("PierreTaille", (b[0], b[1], z + h), (bi[0], bi[1], z + h), (ai[0], ai[1], z + h), (a[0], a[1], z + h), [(0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1)])
        mb.quad("PierreTaille", (bi[0], bi[1], z + h), (bi[0], bi[1], z + 0.1), (ai[0], ai[1], z + 0.1), (ai[0], ai[1], z + h), [(0, 0), (0.2, 0), (0.2, 0.2), (0, 0.2)])
    v2, idx = triangulate(np.array(inner), [])
    mb.add("Eau", np.column_stack([v2, np.full(len(v2), z + h - 0.12)]), [(0, 0, 1)], v2 / 2.0, [WHITE], idx)
    # colonne centrale, vasque, becs
    revolve(mb, "PierreTaille", [(0.28, 0.0), (0.22, 0.1), (0.18, 1.3), (0.24, 1.4), (0.55, 1.5), (0.6, 1.62), (0.2, 1.66), (0.12, 1.9), (0.16, 2.1), (0.0, 2.3)], (x, y, z + 0.1), segs=16, u_tile=3, v_tile=3)
    revolve(mb, "Eau", [(0.5, 0.0), (0.0, 0.0)], (x, y, z + 0.1 + 1.6), segs=16)
    for k in range(4):
        a = k * math.pi / 2
        p0 = (x + 0.18 * math.cos(a), y + 0.18 * math.sin(a), z + 1.1)
        p1 = (x + 0.45 * math.cos(a), y + 0.45 * math.sin(a), z + 1.05)
        tube(mb, "Bronze", [p0, p1], 0.025, segs=6)
        # filet d'eau
        pts = [(x + (0.45 + 0.35 * t) * math.cos(a), y + (0.45 + 0.35 * t) * math.sin(a), z + 1.05 - 0.4 * t * t - 0.05 * t) for t in np.linspace(0, 1, 6)]
        tube(mb, "Eau", pts, 0.012, segs=5)


# ------------------------------------------------------------------ monument aux morts
def war_memorial(x, y, yaw):
    z = zat(x, y)
    mb = mb_at(x, y)
    box(mb, "PierreTaille", (x, y, z - 0.6), (2.4, 2.4, 1.8), yaw=yaw, uv_scale=3)
    box(mb, "PierreTaille", (x, y, z + 0.45), (1.9, 1.9, 0.3), yaw=yaw, uv_scale=3)
    box(mb, "PierreTaille", (x, y, z + 1.6), (1.1, 1.1, 2.0), yaw=yaw, uv_scale=3)
    revolve(mb, "PierreTaille", [(0.55, 0.0), (0.4, 0.2), (0.28, 2.6), (0.0, 3.0)], (x, y, z + 2.6), segs=4, u_tile=3, v_tile=3)
    ca, sa = math.cos(yaw), math.sin(yaw)
    nrm_ = np.array([-sa, ca, 0.0])
    c = np.array([x, y, z + 1.7]) + nrm_ * 0.56
    rect_sign(mb, "Enseignes", c, 0.95, 0.31, nrm_, SIGNS["monument"])
    # chaînes et bornes
    for k in range(4):
        a = yaw + math.pi / 4 + k * math.pi / 2
        px, py = x + 2.2 * math.cos(a), y + 2.2 * math.sin(a)
        inst["Borne"].append((px, py, zat(px, py), 0, 1, 1, 1, 255, 255, 255))


# ------------------------------------------------------------------ table d'orientation (belvédère)
def viewpoint_table(x, y):
    z = zat(x, y)
    mb = mb_at(x, y)
    revolve(mb, "PierreTaille", [(0.35, -0.2), (0.3, 0.2), (0.22, 0.9), (0.6, 1.0), (0.6, 1.1), (0.0, 1.12)], (x, y, z), segs=16, u_tile=3, v_tile=3)


# places : fontaine sur la place de la mairie, monument sur la place de l'église
bu = unary_union([b["poly"] for b in V["buildings"]])
from shapely.ops import polylabel
spots = []
for p in V["plaza"]:
    freep = p.difference(bu.buffer(3.0))
    if freep.is_empty:
        continue
    big = max(polys_of(freep), key=lambda g: g.area)
    spots.append((big.area, polylabel(big, 0.3), p))
spots.sort(key=lambda s: -s[0])
# la fontaine principale va sur la place la plus proche de la mairie (terrasses de café)
spots.sort(key=lambda s: (0 if s[0] > 60 and s[1].distance(Point(8.7, 9.4)) < 25 else 1, -s[0]))
placed = []
for area, c, p in spots:
    if area < 25:
        continue
    d = c.distance(CENTER)
    if not placed:
        fountain(c.x, c.y)
        placed.append(("fontaine", c))
    elif len(placed) == 1:
        war_memorial(c.x, c.y, rng.uniform(0, math.pi))
        placed.append(("monument", c))
    elif len(placed) == 2:
        fountain(c.x, c.y, 1.1)
        placed.append(("fontaine", c))
print("places:", [(n, round(c.x), round(c.y)) for n, c in placed])
for (x, y) in V.get("viewpoints", []):
    if CENTER.distance(Point(x, y)) < 600:
        viewpoint_table(x, y)

# bancs (OSM + autour des places)
for (x, y) in V.get("benches", []):
    inst[rng.choice(["Banc", "Banc_Pierre"])].append((x, y, zat(x, y), rng.uniform(0, 6.28), 1, 1, 1, 255, 255, 255))
for area, c, p in spots:
    edge = p.exterior
    n = int(edge.length / 14)
    for k in range(n):
        q = edge.interpolate((k + 0.5) * edge.length / max(n, 1))
        v = np.array([c.x - q.x, c.y - q.y])
        v /= np.linalg.norm(v) + 1e-9
        pt = np.array([q.x, q.y]) + v * 1.2
        if bu.distance(Point(*pt)) < 1.2:
            continue
        yaw = math.atan2(v[1], v[0]) - math.pi / 2
        inst["Banc"].append((pt[0], pt[1], zat(*pt), yaw + math.pi, 1, 1, 1, 255, 255, 255))

# réverbères le long des rues du village et des routes d'accès
lamp_pts = []
for r in V["roads"]:
    if r["surface"] not in ("asphalt", "stone"):
        continue
    ln = r["line"]
    n = int(ln.length / 26)
    for k in range(n):
        s = (k + 0.5) * 26
        p = ln.interpolate(s)
        if CENTER.distance(p) > 520:
            continue
        a = ln.interpolate(max(0, s - 1))
        b = ln.interpolate(min(ln.length, s + 1))
        dv = np.array([b.x - a.x, b.y - a.y])
        dv /= np.linalg.norm(dv) + 1e-9
        nn = np.array([-dv[1], dv[0]])
        q = np.array([p.x, p.y]) + nn * (r["width"] / 2 + 0.5)
        if bu.distance(Point(*q)) < 0.8 or any(np.hypot(*(q - np.array(o))) < 18 for o in lamp_pts[-6:]):
            continue
        if V["core"].contains(Point(*q)):
            continue
        lamp_pts.append(tuple(q))
        yaw = math.atan2(-nn[1], -nn[0])
        inst["Lampadaire"].append((q[0], q[1], zat(*q), yaw, 1, 1, 1, 255, 255, 255))

# panneaux d'entrée d'agglomération et directions
signs_done = 0
for r in V["roads"]:
    if r["surface"] != "asphalt" or r["cls"] not in ("primary", "secondary", "tertiary"):
        continue
    ln = r["line"]
    s_all = np.linspace(0, ln.length, max(2, int(ln.length / 3)))
    d = np.array([CENTER.distance(ln.interpolate(s)) for s in s_all])
    cross = np.where(np.diff(np.sign(d - 420)) != 0)[0]
    for ci in cross:
        s = s_all[ci]
        p = ln.interpolate(s)
        a = ln.interpolate(max(0, s - 2))
        b = ln.interpolate(min(ln.length, s + 2))
        dv = np.array([b.x - a.x, b.y - a.y])
        dv /= np.linalg.norm(dv) + 1e-9
        towards_center = (d[ci + 1] < d[ci])
        facing = -dv if towards_center else dv
        nn = np.array([-dv[1], dv[0]])
        q = np.array([p.x, p.y]) + nn * (r["width"] / 2 + 1.0) * (1 if towards_center else -1)
        z = zat(*q)
        mb = mb_at(*q)
        tube(mb, "Fer", [(q[0], q[1], z - 0.3), (q[0], q[1], z + 2.3)], 0.04, segs=6, col=(200, 200, 200, 255))
        n3 = np.array([facing[0], facing[1], 0.0]) * -1
        rect_sign(mb, "Enseignes", np.array([q[0], q[1], z + 1.9]) + n3 * 0.05, 1.4, 0.5, n3, SIGNS["entree"], thickness=0.02, back_mat="Fer")
        rect_sign(mb, "Enseignes", np.array([q[0], q[1], z + 1.9]) - n3 * 0.05, 1.4, 0.5, -n3, SIGNS["sortie"], thickness=0.02, back_mat="Fer")
        # panneaux directionnels juste avant l'entrée
        q2 = q + (dv if towards_center else -dv) * 25
        z2 = zat(*q2)
        tube(mb, "Fer", [(q2[0], q2[1], z2 - 0.3), (q2[0], q2[1], z2 + 2.6)], 0.045, segs=6, col=(200, 200, 200, 255))
        for k in range(2):
            key = f"dir_{rng.integers(len(DIRECTIONS))}"
            side = np.array([nn[0], nn[1], 0.0]) * (1 if k == 0 else -1)
            c3 = np.array([q2[0], q2[1], z2 + 2.25 - 0.32 * k]) + side * 0.62
            rect_sign(mb, "Enseignes", c3, 1.25, 0.21, n3 if k == 0 else n3, SIGNS[key], thickness=0.015, back_mat="Fer")
        signs_done += 1
print("panneaux d'entrée:", signs_done, " réverbères:", len(lamp_pts), " %.0fs" % (time.time() - T0))

# ------------------------------------------------------------------ rivière des Ocres et ponts de pierre
if V.get("river"):
    from ponts import water, bridge
    water(mb_at, V["river"])
    rv = V["river"]
    for br in V.get("bridges", []):
        m = br["line"].interpolate(0.5, normalized=True)
        k = int(np.argmin(np.hypot(rv["xy"][:, 0] - m.x, rv["xy"][:, 1] - m.y)))
        # culées au niveau du sol définitif (après l'aplanissement des routes) : pas de marche à l'entrée du pont
        z0, z1 = zat(*br["line"].coords[0]), zat(*br["line"].coords[-1])
        br = dict(br, z0=z0, z1=z1)
        A = np.array(br["line"].coords[0]); L_ = br["line"].length
        zfun = (lambda x, y, A=A, L_=L_, z0=z0, z1=z1, br=br: zat(x, y)) if z0 is None else None
        if z0 is not None:
            # culées au niveau prévu pour le tablier ; sous le pont, le vrai sol
            def zfun(x, y, A=A, L_=L_, z0=z0, z1=z1):
                t = float(np.hypot(x - A[0], y - A[1]))
                if t < 0.05:
                    return z0
                if t > L_ - 0.05:
                    return z1
                return zat(x, y)
        lamps = bridge(mb_at(m.x, m.y), br, zfun, water_level=float(rv["level"][k]))
        for (x, y, z, yaw) in lamps or []:
            inst["Lampadaire"].append((x, y, z, yaw, 1, 1, 1, 255, 255, 255))
    print("rivière et %d ponts  %.0fs" % (len(V.get("bridges", [])), time.time() - T0))

# rien au fond des gorges (bancs, bornes...) ; les réverbères du pont, eux, sont sur le tablier
if V.get("river_rim") is not None:
    _rim = V["river_rim"].buffer(1.0)
    for k in list(inst):
        a = np.array(inst[k], np.float64)
        if not len(a):
            continue
        gz_ = grid_sample(GROUND, a[:, 0], a[:, 1])
        bad = shapely.contains_xy(_rim, a[:, 0], a[:, 1]) & (a[:, 2] < gz_ + 2.0)
        if bad.any():
            print("gorges : %d %s retirés" % (int(bad.sum()), k))
            inst[k] = [tuple(x) for x in a[~bad]]

with open("mobilier_out.pkl", "wb") as f:
    pickle.dump(dict(chunks={k: v.arrays() for k, v in chunks.items()}, inst={k: np.array(v, np.float32) for k, v in inst.items()},
                     places=[(n, c.x, c.y, zat(c.x, c.y)) for n, c in placed]), f)
print("instances:", {k: len(v) for k, v in inst.items()})
