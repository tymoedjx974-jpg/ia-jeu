"""Étape 5 bis : le village envahi par les zombies, jouable en parkour.

- voitures abandonnées sur les routes, barrage à l'entrée du village, épaves brûlées ;
- déchets, poubelles, palettes, gravats le long des ruelles, terrasses de café renversées ;
- fenêtres et portes condamnées par des planches, inscriptions à la bombe, suie, impacts, traces de sang ;
- camp de survivants sur la place de la mairie (sacs de sable, bâches, brasero) ;
- parcours de toit en toit : planches entre les toits, échelles, échafaudages, caisses et bennes pour grimper ;
- points d'apparition des zombies.
Sortie : envahi_out.pkl (instances au même format que les autres étapes + points d'apparition + parcours).
"""
import sys, pickle, math, time, json, collections
sys.path.insert(0, ".")
import numpy as np
import shapely
from shapely.geometry import Point, LineString, Polygon
from shapely.strtree import STRtree
from shapely import affinity
from common import grid_sample, ZONE

T0 = time.time()
rng = np.random.default_rng(1947)
V = pickle.load(open("vec.pkl", "rb"))
B = pickle.load(open("buildings_out.pkl", "rb"))
M = pickle.load(open("mobilier_out.pkl", "rb"))
G = np.load("terrain.npz")["ground"]
ATLAS = json.load(open("tex/Graffitis.json"))
CENTER = Point(-10.0, 20.0)

inst = collections.defaultdict(list)
spawns = []
route = []          # éléments du parcours (pour la carte et le README)
occupied = []       # emprises au sol déjà prises


def gz(x, y):
    return float(grid_sample(G, [x], [y], order=1)[0])


def put(name, x, y, z, yaw, s=(1.0, 1.0, 1.0), col=(255, 255, 255)):
    inst[name].append((x, y, z, yaw, s[0], s[1], s[2], *col))


def footprint(x, y, yaw, L, W):
    r = Polygon([(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)])
    return affinity.translate(affinity.rotate(r, yaw, use_radians=True, origin=(0, 0)), x, y)


# ------------------------------------------------------------------ bâtiments
metas = [m for m in B["meta"]]
polys = [Polygon(m["poly"]) for m in metas]
tree = STRtree(polys)
for m in metas:
    m["planes_np"] = [(np.array(A), b) for A, b in m["planes"]]


def zroof(m, x, y):
    return min(float(A @ np.array([x, y]) + b) for A, b in m["planes_np"])


def near_building(geom, buf=0.3, skip=()):
    for k in tree.query(geom.buffer(buf)):
        if k in skip:
            continue
        if polys[k].distance(geom) < buf:
            return True
    return False


def free(fp, buf=0.4):
    for o in occupied:
        if o.distance(fp) < buf:
            return False
    return True


def door_centers(m):
    out = []
    for o in m["openings"]:
        if "Porte" in o["type"] or "Remise" in o["type"] or "Vitrine" in o["type"]:
            e = m["edges"][o["edge"]]
            p0, p1 = np.array(e["p0"]), np.array(e["p1"])
            u = (p1 - p0) / max(e["L"], 1e-9)
            out.append(p0 + u * (o["s0"] + o["s1"]) / 2)
    return out


DOORS = [np.array(d) for m in metas for d in door_centers(m)]
DOOR_TREE = STRtree([Point(*d) for d in DOORS]) if DOORS else None


def near_door(x, y, dist=1.6):
    if DOOR_TREE is None:
        return False
    for k in DOOR_TREE.query(Point(x, y).buffer(dist)):
        if np.hypot(DOORS[k][0] - x, DOORS[k][1] - y) < dist:
            return True
    return False


core = V["core"]
roads = V["roads"]

# ------------------------------------------------------------------ 1. voitures abandonnées
CAR = {"Z_Citadine": (3.7, 1.65), "Z_Berline": (4.5, 1.8), "Z_Fourgon": (4.3, 1.8), "Z_Epave": (3.7, 1.65)}
PAINTS = [(236, 234, 228), (196, 40, 36), (48, 78, 140), (214, 196, 150), (74, 110, 80), (140, 140, 138), (222, 180, 40), (120, 30, 40), (30, 30, 34)]
cars = 0
car_roads = [r for r in roads if r["surface"] == "asphalt" and r["cls"] in ("secondary", "tertiary", "residential", "unclassified", "service")]
for r in sorted(car_roads, key=lambda r: r["line"].distance(CENTER)):
    ln = r["line"]
    if ln.distance(CENTER) > 1400 or core.buffer(8).contains(ln) or (r["cls"] == "service" and ln.distance(CENTER) > 450):
        continue
    if cars >= 230:
        break
    L = ln.length
    near = ln.distance(CENTER) < 500
    pos = rng.uniform(5, 30)
    while pos < L - 3:
        p = ln.interpolate(pos)
        a = ln.interpolate(max(0, pos - 1.0))
        b = ln.interpolate(min(L, pos + 1.0))
        t = np.array([b.x - a.x, b.y - a.y])
        t /= np.linalg.norm(t) + 1e-9
        nrm_ = np.array([-t[1], t[0]])
        w = r.get("width") or 4.0
        name = rng.choice(list(CAR), p=[0.38, 0.3, 0.16, 0.16])
        Lc, Wc = CAR[name]
        crash = rng.random() < 0.22
        side = rng.choice([-1, 1])
        off = max(0.0, w / 2 - Wc / 2 - 0.1) * side if not crash else rng.uniform(-w / 3, w / 3)
        yaw = math.atan2(t[1], t[0]) + (math.pi if (side < 0 and rng.random() < 0.8) else 0.0)
        if crash:
            yaw += rng.normal(0, 0.55)
        x, y = p.x + nrm_[0] * off, p.y + nrm_[1] * off
        fp = footprint(x, y, yaw, Lc, Wc)
        if not near_building(fp, 0.4) and free(fp, 1.0) and not near_door(x, y, 3.0):
            col = PAINTS[rng.integers(len(PAINTS))] if name != "Z_Epave" else (255, 255, 255)
            put(name, x, y, gz(x, y) + 0.02, yaw, col=col)
            occupied.append(fp)
            cars += 1
            spawns.append((x + nrm_[0] * 2.5, y + nrm_[1] * 2.5, gz(x, y)))
        pos += rng.uniform(25, 70) * (0.8 if near else 3.0)
print("voitures abandonnées :", cars, flush=True)

# barrage à l'entrée du village : sur la route principale, à ~280 m du centre
main = [r for r in roads if r["cls"] in ("secondary", "tertiary") and r["surface"] == "asphalt"]
best = None
for r in main:
    ln = r["line"]
    for k in range(int(ln.length / 5)):
        p = ln.interpolate(k * 5.0)
        d = abs(p.distance(CENTER) - 280)
        if best is None or d < best[0]:
            best = (d, r, k * 5.0)
blocks = 0
if best:
    _, r, s0 = best
    ln = r["line"]
    p = ln.interpolate(s0)
    a, b = ln.interpolate(max(0, s0 - 1)), ln.interpolate(min(ln.length, s0 + 1))
    t = np.array([b.x - a.x, b.y - a.y])
    t /= np.linalg.norm(t)
    n_ = np.array([-t[1], t[0]])
    yaw_across = math.atan2(n_[1], n_[0])
    w = r.get("width") or 5.0
    for k in range(-1, 2):
        x, y = p.x + n_[0] * k * 2.0, p.y + n_[1] * k * 2.0
        put("Z_Barriere", x, y, gz(x, y), yaw_across)
        blocks += 1
    for sgn in (-1, 1):
        x, y = p.x + n_[0] * sgn * (w / 2 + 1.2) + t[0] * 1.0, p.y + n_[1] * sgn * (w / 2 + 1.2) + t[1] * 1.0
        put("Z_SacsSable", x, y, gz(x, y), yaw_across)
    for k, name in enumerate(("Z_Berline", "Z_Epave", "Z_Citadine")):
        x, y = p.x - t[0] * (6 + 5 * k) + n_[0] * rng.uniform(-1.5, 1.5), p.y - t[1] * (6 + 5 * k) + n_[1] * rng.uniform(-1.5, 1.5)
        put(name, x, y, gz(x, y) + 0.02, math.atan2(t[1], t[0]) + rng.normal(0, 0.5), col=PAINTS[rng.integers(len(PAINTS))])
        occupied.append(footprint(x, y, 0, 4.5, 1.8))
    # inscription peinte sur la chaussée, lisible en arrivant de l'extérieur
    to_village = t if np.dot(t, np.array([CENTER.x - p.x, CENTER.y - p.y])) > 0 else -t
    q = np.array([p.x, p.y]) - to_village * 5.0
    # le haut du texte pointe vers le village : on le lit en arrivant de l'extérieur
    put("Z_Sol_zone_infectee", q[0], q[1], gz(*q) + 0.09, math.atan2(to_village[1], to_village[0]) - math.pi / 2)
    route.append(dict(kind="barrage", x=p.x, y=p.y))
print("barrage :", blocks, "barrières", flush=True)

# ------------------------------------------------------------------ 2. déchets et débris le long des ruelles
PROPS = [("Z_SacsPoubelle", 3.0, 1.0, 0.9), ("Z_Poubelle", 2.0, 0.8, 0.9), ("Z_Palette", 1.2, 1.2, 0.8), ("Z_CaissePetite", 1.4, 0.6, 0.6),
         ("Z_Pneus", 0.9, 0.7, 0.7), ("Z_Gravats", 0.5, 2.0, 1.6), ("Z_Matelas", 0.4, 1.9, 1.35), ("Z_PilePalettes", 0.8, 1.2, 0.8),
         ("Z_Caisse", 0.8, 1.0, 1.0), ("Z_Conteneur", 0.5, 2.0, 1.05)]
pw = np.array([p[1] for p in PROPS])
pw /= pw.sum()
props = 0
street_roads = [r for r in roads if r["cls"] not in ("track", "steps") and r["line"].distance(CENTER) < 700]
for r in street_roads:
    ln = r["line"]
    pos = rng.uniform(2, 10)
    in_core = core.buffer(15).intersects(ln)
    while pos < ln.length:
        p = ln.interpolate(pos)
        pos += rng.uniform(6, 13) if in_core else rng.uniform(10, 24)
        ks = tree.query(p.buffer(6.0))
        if len(ks) == 0:
            continue
        k = min(ks, key=lambda k: polys[k].exterior.distance(p))
        poly = polys[k]
        from shapely.ops import nearest_points
        qpt = nearest_points(poly.exterior, p)[0]
        out = np.array([p.x - qpt.x, p.y - qpt.y])
        dd = np.linalg.norm(out)
        if dd < 0.5 or dd > 6.0:
            continue
        out /= dd
        name, _, L, W = PROPS[rng.choice(len(PROPS), p=pw)]
        if name == "Z_Conteneur" and dd < 3.5:
            continue
        tan = np.array([-out[1], out[0]])
        x, y = qpt.x + out[0] * (W / 2 + 0.12), qpt.y + out[1] * (W / 2 + 0.12)
        yaw = math.atan2(tan[1], tan[0]) + rng.normal(0, 0.12)
        fp = footprint(x, y, yaw, L, W)
        if near_building(fp, 0.05) or not free(fp, 0.3) or near_door(x, y, 1.5):
            continue
        put(name, x, y, gz(x, y) + 0.03, yaw)
        occupied.append(fp)
        props += 1
print("débris et déchets :", props, flush=True)

# terrasses de café renversées
tabs = np.asarray(B["inst"].get("Table_Cafe", []), np.float32)
for t_ in tabs:
    if rng.random() < 0.45:
        x, y = t_[0] + rng.normal(0, 0.5), t_[1] + rng.normal(0, 0.5)
        put("Z_TableRenversee", x, y, gz(x, y) + 0.02, rng.uniform(0, 6.28))

# ------------------------------------------------------------------ 3. ouvertures condamnées, inscriptions, suie
boarded = tags = 0
TAG_W = {"zone_infectee": 1.0, "ne_pas_entrer": 1.2, "ils_sont_dedans": 1.0, "survivants_mairie": 1.2, "aidez_nous": 0.8, "morts_ici": 1.0,
         "pas_de_bruit": 0.8, "croix": 0.8, "fleche": 1.0, "vide_3": 0.6, "sang_main": 0.8, "impacts": 1.0}
tag_keys = list(TAG_W)
tag_p = np.array([TAG_W[k] for k in tag_keys])
tag_p /= tag_p.sum()
for m in metas:
    if m["style"] not in ("core", "faubourg", "villa", "mas") or m["visit"]:
        continue
    dist_c = Polygon(m["poly"]).centroid.distance(CENTER)
    if dist_c > 900:
        continue
    fac = 1.0 if m["style"] in ("core", "faubourg") else 0.45
    for o in m["openings"]:
        e = m["edges"][o["edge"]]
        p0, p1 = np.array(e["p0"]), np.array(e["p1"])
        u = (p1 - p0) / max(e["L"], 1e-9)
        yaw = math.atan2(u[1], u[0])
        c = p0 + u * (o["s0"] + o["s1"]) / 2
        w = o["s1"] - o["s0"]
        h = o["z1"] - o["z0"]
        low = o["z0"] - m["zref"] < 1.9
        if o["type"].startswith("Fenetre") and low and rng.random() < 0.1 * fac:
            put("Z_PlanchesFenetre", c[0], c[1], o["z0"], yaw, s=(w / 0.9, 1.0, h / 1.45))
            boarded += 1
        elif o["type"] in ("Porte", "Porte_Simple") and rng.random() < 0.1 * fac:
            put("Z_PlanchesPorte", c[0], c[1], o["z0"], yaw, s=(w / 1.0, 1.0, h / 2.3))
            boarded += 1
        elif o["type"].startswith("Vitrine") and rng.random() < 0.3:
            put("Z_PlanchesPorte", c[0], c[1], o["z0"], yaw, s=(w / 1.0, 1.0, min(h, 2.4) / 2.3))
            boarded += 1
        elif o["type"].startswith("Fenetre") and not low and rng.random() < 0.035:
            put("Z_Tag_suie", c[0], c[1], o["z1"] - 0.25, yaw, s=(1.0, 1.0, 1.0))
        if o["type"] in ("Porte", "Porte_Simple") and rng.random() < 0.12 * fac:
            cx = c + u * (w / 2 + 0.55)
            put("Z_Tag_croix", cx[0], cx[1], o["z0"] + 1.0, yaw, s=(0.8, 0.8, 0.8))
    # inscriptions sur les façades côté rue, entre les ouvertures
    for ei, e in enumerate(m["edges"]):
        if e["party"] or e["L"] < 2.4 or rng.random() > (0.6 if e["street"] else 0.15) * fac:
            continue
        spans = sorted((o["s0"], o["s1"]) for o in m["openings"] if o["edge"] == ei and o["z0"] - m["zref"] < 2.6)
        key = tag_keys[rng.choice(len(tag_keys), p=tag_p)]
        hgt = rng.uniform(0.75, 1.2)
        wd = ATLAS[key][4] * hgt
        free_s = []
        cur = 0.4
        for a0, a1 in spans + [(e["L"] - 0.4, e["L"])]:
            if a0 - cur > wd + 0.2:
                free_s.append((cur, a0))
            cur = max(cur, a1 + 0.2)
        if not free_s:
            continue
        a0, a1 = free_s[rng.integers(len(free_s))]
        s = rng.uniform(a0 + wd / 2 + 0.1, a1 - wd / 2 - 0.1) if a1 - a0 > wd + 0.2 else (a0 + a1) / 2
        p0, p1 = np.array(e["p0"]), np.array(e["p1"])
        u = (p1 - p0) / e["L"]
        P = p0 + u * s
        z = gz(*(P + np.array(e["out"]) * 0.6)) + rng.uniform(0.9, 1.5)
        put(f"Z_Tag_{key}", P[0], P[1], z, math.atan2(u[1], u[0]), s=(hgt, 1.0, hgt))
        tags += 1
print("ouvertures condamnées :", boarded, " inscriptions :", tags, flush=True)

# ------------------------------------------------------------------ 4. sang au sol, dans les rues et dans les maisons visitables
blood = 0
for r in street_roads:
    ln = r["line"]
    for _ in range(int(ln.length / 40) + (1 if rng.random() < 0.5 else 0)):
        p = ln.interpolate(rng.uniform(0, ln.length))
        key = rng.choice(["sang_1", "sang_2", "sang_flaque", "sang_trainee"], p=[0.3, 0.3, 0.2, 0.2])
        sc = rng.uniform(0.8, 1.4)
        put(f"Z_Sol_{key}", p.x + rng.normal(0, 1.0), p.y + rng.normal(0, 1.0), gz(p.x, p.y) + 0.09, rng.uniform(0, 6.28), s=(sc, sc, 1.0))
        blood += 1
for v in B.get("visit", []):
    pl = v.get("plan")
    if not pl or rng.random() > 0.5:
        continue
    c, a = np.array(pl["c"]), np.array(pl["a"])
    q = np.array([-a[1], a[0]])
    P = c + a * rng.uniform(-pl["L"] / 4, pl["L"] / 4) + q * rng.uniform(-pl["W"] / 5, pl["W"] / 5)
    put("Z_Sol_" + rng.choice(["sang_trainee", "sang_1", "sang_flaque"]), P[0], P[1], pl["l0"] + 0.004, rng.uniform(0, 6.28), s=(0.8, 0.8, 1.0))
    blood += 1
print("traces de sang :", blood, flush=True)

# ------------------------------------------------------------------ 5. camp de survivants devant la mairie
camp = None
mairie = next((m for m in metas if m["mairie"]), None)
fountains = [(x, y) for n, x, y, z in M.get("places", []) if n == "fontaine"]
if mairie:
    mp = Polygon(mairie["poly"])
    plaza = max(V["plaza"], key=lambda g: -g.distance(mp)) if V["plaza"] else None
    cands = []
    if plaza is not None:
        x0, y0, x1, y1 = plaza.bounds
        for x in np.arange(x0, x1, 1.0):
            for y in np.arange(y0, y1, 1.0):
                pt = Point(x, y)
                if not plaza.buffer(-1.0).contains(pt):
                    continue
                if near_building(pt, 4.5) or any(np.hypot(x - fx, y - fy) < 4.5 for fx, fy in fountains):
                    continue
                cands.append((pt.distance(mp), x, y))
    if cands:
        _, cx, cy = min(cands)
        camp = (cx, cy)
        z0 = gz(cx, cy)
        put("Z_Brasero", cx, cy, z0, 0.0)
        for k in range(8):
            ang = 2 * math.pi * k / 8 + 0.2
            if k in (2,):
                continue
            x, y = cx + 4.2 * math.cos(ang), cy + 4.2 * math.sin(ang)
            if near_building(Point(x, y), 0.8) or any(np.hypot(x - fx, y - fy) < 2.2 for fx, fy in fountains):
                continue
            put("Z_SacsSable", x, y, gz(x, y), ang + math.pi / 2)
        for k, (dx, dy, yaw) in enumerate(((-2.0, 1.5, 0.3), (1.8, -1.8, 1.9))):
            put("Z_Bache", cx + dx, cy + dy, gz(cx + dx, cy + dy), yaw, col=((70, 100, 150), (160, 130, 80))[k])
        for dx, dy in ((2.2, 1.6), (2.9, 1.1), (2.4, 2.4)):
            put("Z_Caisse" if dx < 2.5 else "Z_CaissePetite", cx + dx, cy + dy, gz(cx + dx, cy + dy), rng.uniform(0, 1))
        put("Z_PilePalettes", cx - 2.6, cy - 1.8, gz(cx - 2.6, cy - 1.8), 0.4)
        put("Z_Matelas", cx - 1.8, cy + 1.6, gz(cx - 1.8, cy + 1.6) + 0.01, 0.3)
        put("Z_Sol_sos", cx + 0.5, cy - 2.6, gz(cx, cy) + 0.1, 0.0)
        route.append(dict(kind="camp", x=cx, y=cy))
print("camp de survivants :", camp, flush=True)

# ------------------------------------------------------------------ 6. parkour : planches entre les toits
from shapely.ops import nearest_points
PK_STYLES = ("core", "faubourg", "villa", "mas", "shed")
planks = ramps = 0
done_pts = []
for i, m in enumerate(metas):
    if m["style"] not in PK_STYLES or polys[i].centroid.distance(CENTER) > 650:
        continue
    pa = polys[i]
    for j in tree.query(pa.buffer(5.2)):
        if j <= i or metas[j]["style"] not in PK_STYLES:
            continue
        pb = polys[j]
        d = pa.distance(pb)
        if not (1.0 <= d <= 5.0):
            continue
        # plusieurs appuis possibles le long de la façade : on garde le meilleur (toits à même hauteur, portée courte)
        ring = pa.exterior
        best = None
        for t in np.linspace(0, 1, 60, endpoint=False):
            A = ring.interpolate(t, normalized=True)
            if A.distance(pb) > 5.0:
                continue
            Bp = nearest_points(A, pb)[1]
            A_, B_ = np.array([A.x, A.y]), np.array([Bp.x, Bp.y])
            gap = float(np.linalg.norm(B_ - A_))
            if not (1.0 <= gap <= 5.0):
                continue
            dv = (B_ - A_) / gap
            A2, B2 = A_ - dv * 0.45, B_ + dv * 0.45
            if not (pa.buffer(-0.05).contains(Point(*A2)) and pb.buffer(-0.05).contains(Point(*B2))):
                continue
            za, zb = zroof(m, *A2), zroof(metas[j], *B2)
            gmid = gz(*((A_ + B_) / 2))
            if min(za, zb) - gmid < 2.6:
                continue
            L = float(np.linalg.norm(B2 - A2))
            dz = abs(za - zb)
            if dz > min(0.55 * L, 2.0):
                continue
            score = dz * 3 + gap
            if best is None or score < best[0]:
                best = (score, A2, B2, za, zb, L, dv)
        if best is None:
            continue
        _, A2, B2, za, zb, L, dv = best
        mid = (A2 + B2) / 2
        if any(np.hypot(*(mid - q_)) < 14.0 for q_ in done_pts) or planks + ramps >= 30:
            continue
        seg = LineString([tuple(A2), tuple(B2)])
        if near_building(seg.interpolate(0.5, normalized=True).buffer(0.2), 0.05, skip=(i, j)):
            continue
        if abs(za - zb) <= 0.4:
            z = max(za, zb) + 0.03
            put("Z_Planche", mid[0], mid[1], z, math.atan2(dv[1], dv[0]), s=(L, 1.0, 1.0))
            planks += 1
        else:
            lo, hi = (A2, B2) if za < zb else (B2, A2)
            dvr = (hi - lo) / L
            put("Z_PlancheRampe", mid[0], mid[1], min(za, zb) + 0.05, math.atan2(dvr[1], dvr[0]), s=(L, 1.0, abs(za - zb)))
            ramps += 1
            z = max(za, zb)
        done_pts.append(mid)
        route.append(dict(kind="planche", x=float(mid[0]), y=float(mid[1]), z=float(z), L=L))
print("planches entre les toits :", planks, " rampes :", ramps, flush=True)

# ------------------------------------------------------------------ 7. parkour : échelles, échafaudages, caisses et bennes pour monter
ladders = scaff = starts = 0
lad_pts = []
for mi, m in sorted(enumerate(metas), key=lambda im: Polygon(im[1]["poly"]).centroid.distance(CENTER)):
    if m["style"] not in PK_STYLES or m["visit"]:
        continue
    c = Polygon(m["poly"]).centroid
    if c.distance(CENTER) > 700:
        break
    for ei, e in sorted(enumerate(m["edges"]), key=lambda ie: (not ie[1]["street"], -ie[1]["L"])):
        if e["party"] or e["L"] < 2.2:
            continue
        p0, p1 = np.array(e["p0"]), np.array(e["p1"])
        u = (p1 - p0) / e["L"]
        out = np.array(e["out"])
        spans = sorted((o["s0"], o["s1"]) for o in m["openings"] if o["edge"] == ei)
        # colonne libre de toute ouverture (sur toute la hauteur)
        free_s = []
        cur = 0.5
        for a0, a1 in spans + [(e["L"] - 0.5, e["L"])]:
            if a0 - cur > 1.0:
                free_s.append((cur, a0))
            cur = max(cur, a1 + 0.3)
        # échafaudage de façade (vieux village) : devant les fenêtres, mais jamais devant une porte
        if m["style"] == "core" and e["street"] and e["L"] >= 3.2 and scaff < 6:
            sc = e["L"] / 2
            Pc = p0 + u * sc
            gc = gz(*(Pc + out * 0.8))
            hc = m["eave"] - gc
            doors_e = [o for o in m["openings"] if o["edge"] == ei and ("Porte" in o["type"] or "Remise" in o["type"] or "Vitrine" in o["type"])
                       and o["s1"] > sc - 1.6 and o["s0"] < sc + 1.6]
            fp = footprint(*(Pc + out * 0.8), math.atan2(u[1], u[0]), 2.7, 1.0)
            if 5.0 <= hc <= 11.5 and not doors_e and free(fp, 0.2) and not near_building(fp, 0.02, skip=(mi,)) \
                    and not any(np.hypot(*(Pc + out - q_)) < 32.0 for q_ in lad_pts):
                # le dernier plancher arrive 1,2 m sous la gouttière : on se hisse sur le toit
                put("Z_Echafaudage", Pc[0], Pc[1], gc, math.atan2(u[1], u[0]), s=(1.0, 1.0, (hc - 1.2) / 6.0))
                occupied.append(fp)
                scaff += 1
                lad_pts.append(Pc + out)
                route.append(dict(kind="echafaudage", x=float(Pc[0]), y=float(Pc[1])))
                break
        if not free_s:
            continue
        a0, a1 = max(free_s, key=lambda s: s[1] - s[0])
        s_ = (a0 + a1) / 2
        P = p0 + u * s_
        g = gz(*(P + out * 0.8))
        hgt = m["eave"] - g
        yaw = math.atan2(u[1], u[0])
        spot = P + out * 1.0
        if any(np.hypot(*(spot - q_)) < 32.0 for q_ in lad_pts) or near_door(P[0], P[1], 1.2):
            continue
        placed = False
        if 2.3 <= hgt <= 4.4 and a1 - a0 > 1.6 and starts < 25:
            # départ : caisse + pile de palettes, ou benne, contre le mur d'une construction basse
            fp = footprint(*(P + out * 0.7), yaw, 2.4, 1.1)
            if near_building(fp, 0.02, skip=(mi,)) or not free(fp, 0.3):
                continue
            if a1 - a0 > 2.6 and rng.random() < 0.6:
                q1 = P + out * 0.62 - u * 0.6
                q2 = P + out * 0.52 + u * 0.75
                put("Z_Caisse", q1[0], q1[1], gz(*q1), yaw)
                put("Z_PilePalettes", q2[0], q2[1], gz(*q2), yaw)
            elif a1 - a0 > 2.2:
                q1 = P + out * 0.62
                put("Z_Conteneur", q1[0], q1[1], gz(*q1), yaw)
            else:
                q1 = P + out * 0.62
                put("Z_Caisse", q1[0], q1[1], gz(*q1), yaw)
            occupied.append(fp)
            starts += 1
            placed = True
            route.append(dict(kind="depart", x=float(P[0]), y=float(P[1])))
        elif 6.4 <= hgt <= 8.8 and scaff < 6 and e["street"] and a1 - a0 > 2.8 and m["style"] == "core":
            fp = footprint(*(P + out * 0.8), yaw, 2.7, 1.0)
            if not free(fp, 0.2) or near_building(fp, 0.02, skip=(mi,)):
                continue
            put("Z_Echafaudage", P[0], P[1], g, yaw)
            occupied.append(fp)
            scaff += 1
            placed = True
            route.append(dict(kind="echafaudage", x=float(P[0]), y=float(P[1])))
        elif 4.4 < hgt <= 9.8 and ladders < 30:
            top = m["eave"] - 0.32
            put("Z_Echelle6", P[0], P[1], g, yaw, s=(1.0, 1.0, (top - g) / 6.0))
            ladders += 1
            placed = True
            route.append(dict(kind="echelle", x=float(P[0]), y=float(P[1]), h=float(top - g)))
        if placed:
            lad_pts.append(spot)
            break
print("échelles :", ladders, " échafaudages :", scaff, " départs (caisses, bennes) :", starts, flush=True)

# ------------------------------------------------------------------ 8. points d'apparition des zombies
for g in V["plaza"]:
    if g.distance(CENTER) > 900:
        continue
    for _ in range(max(2, int(g.area / 150))):
        x0, y0, x1, y1 = g.bounds
        for _t in range(20):
            p = Point(rng.uniform(x0, x1), rng.uniform(y0, y1))
            if g.contains(p) and not near_building(p, 1.0):
                spawns.append((p.x, p.y, gz(p.x, p.y)))
                break
for r in street_roads:
    ln = r["line"]
    for k in range(int(ln.length / 28)):
        p = ln.interpolate((k + 0.5) * 28)
        spawns.append((p.x, p.y, gz(p.x, p.y)))
for v in B.get("visit", []):
    pl = v.get("plan")
    if pl:
        spawns.append((pl["c"][0], pl["c"][1], pl["l0"]))
# champs et vignes autour du village
for _ in range(80):
    ang, rr = rng.uniform(0, 2 * math.pi), rng.uniform(250, 1300)
    x, y = CENTER.x + rr * math.cos(ang), CENTER.y + rr * math.sin(ang)
    if not near_building(Point(x, y), 3.0):
        spawns.append((x, y, gz(x, y)))
spawns = [(float(x), float(y), float(z) + 0.1) for x, y, z in spawns]
# pas de zombies ni d'objets au fond des gorges de la rivière
if V.get("river_rim") is not None:
    _rim = V["river_rim"].buffer(2.0)
    spawns = [s_ for s_ in spawns if not _rim.contains(Point(s_[0], s_[1]))]
    for k in list(inst):
        a = np.array(inst[k], np.float64)
        if len(a):
            keep = ~shapely.contains_xy(_rim, a[:, 0], a[:, 1])
            inst[k] = [tuple(x) for x in a[keep]]
print("points d'apparition des zombies :", len(spawns), flush=True)

out = dict(inst={k: np.array(v, np.float32) for k, v in inst.items()}, spawns=spawns, route=route)
with open("envahi_out.pkl", "wb") as f:
    pickle.dump(out, f)
print("envahi : %s  %.0fs" % ({k: len(v) for k, v in inst.items()}, time.time() - T0))
