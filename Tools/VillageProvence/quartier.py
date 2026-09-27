"""Quartier neuf du village, le long de la coulée d'ocre (côté nord-est) : rues en calade, maisons de village mitoyennes,
une rue principale reliée au réseau existant et une placette. Traité ensuite comme le vieux village (style « core »)."""
import math
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union, nearest_points
from common import polys_of, lines_of, ombr

STREET_NAMES = ["Rue des Ocres", "Rue du Colorado", "Rue des Sablières", "Rue de la Garance", "Traverse des Pigments",
                "Rue du Mistral", "Montée des Lavandes", "Rue des Tuiliers", "Traverse du Castrum", "Rue des Ocriers",
                "Rue de la Font", "Traverse des Cigales", "Rue du Four", "Rue des Potiers"]


def new_quarter(V, roads, ochre_keep, village, slope_at, rng, center, reach=480.0):
    """Renvoie (zone, bâtiments, rues, placettes). Les rues ont le format des routes de plan_terrain."""
    oc = unary_union([g for g in V["cliffs"] + V["sand"] + V["rock"] if g.distance(center) < 700])
    c, ax, L, _ = ombr(oc.convex_hull)
    c, ax = np.asarray(c, float), np.asarray(ax, float)
    n = np.array([-ax[1], ax[0]])
    if n[0] + n[1] < 0:                       # côté droit de la coulée vu depuis le village : nord-est
        n = -n
    if ax[0] < 0:
        ax = -ax

    def W(s, t):
        return c + ax * s + n * t

    def loc(P):
        d = np.asarray(P, float) - c
        return float(d @ ax), float(d @ n)

    st = np.array([loc(p) for g in polys_of(oc.buffer(1.0)) for p in g.exterior.coords])
    vil = np.array([loc(p) for g in polys_of(village) for p in g.exterior.coords])
    # le quartier part du bord du vieux village et descend le long de l'ocre
    s0 = max(vil[:, 0].max() - 70.0, st[:, 0].min() - 80.0) if len(vil) else st[:, 0].min() - 60.0
    s0 = min(s0, st[:, 0].min() - 20.0)
    s1 = st[:, 0].max() + 10.0
    # bord nord-est de l'ocre, lissé : les rues le suivent comme des courbes de niveau
    ks = np.linspace(s0, s1, 16)
    edge = []
    for k in ks:
        m = np.abs(st[:, 0] - k) < 25
        edge.append(st[m, 1].max() if m.any() else np.nan)
    edge = np.array(edge)
    if np.isnan(edge).all():
        edge[:] = 0.0
    idx = np.arange(len(edge))
    edge = np.interp(idx, idx[~np.isnan(edge)], edge[~np.isnan(edge)])
    edge = np.convolve(np.pad(edge, 2, mode="edge"), np.ones(5) / 5, mode="valid") + 20.0
    offs = [0.0, 52.0, 104.0, 150.0]

    def curve(off, wob=3.0):
        return [W(k, e + off + rng.uniform(-wob, wob)) for k, e in zip(ks, edge)]
    zone = Polygon(curve(-8.0, 0.0) + curve(offs[-1] + 18.0, 0.0)[::-1]).buffer(0)
    zone = zone.intersection(village.buffer(reach)).difference(ochre_keep.buffer(6.0))
    zone = unary_union([zone, village.buffer(25.0).intersection(zone.buffer(60.0)).difference(village)])
    zone = max(polys_of(zone.difference(ochre_keep.buffer(6.0))), key=lambda g: g.area)

    # ---------------- rues : parallèles au bord de l'ocre, ruelles transversales tous les ~60 m
    streets = []
    for j, off in enumerate(offs):
        main = j == 1
        streets.append(dict(line=LineString(curve(off)), cls="residential" if main else "living_street",
                            surface="asphalt" if main else "stone", width=5.0 if main else 4.0, prio=30 if main else 28))
    kx = ks[0] + 30.0
    while kx < ks[-1] - 20:
        e = float(np.interp(kx, ks, edge))
        pts = [W(kx + rng.uniform(-6, 6), e + off) for off in offs]
        streets.append(dict(line=LineString(pts), cls="living_street", surface="stone", width=3.6, prio=27))
        kx += rng.uniform(50.0, 72.0)
    for sd in streets:
        g = sd["line"].intersection(zone.buffer(8.0))
        ls = lines_of(g) if not g.is_empty else []
        sd["line"] = max(ls, key=lambda l: l.length) if ls else None
    streets = [sd for sd in streets if sd["line"] is not None and sd["line"].length > 20]
    # chaque rue longitudinale rejoint la rue ou la route la plus proche du vieux village / du réseau
    ex = [r["line"] for r in roads if r["surface"] in ("asphalt", "stone") and not zone.buffer(5).contains(r["line"])]
    links = []
    for sd in streets[:len(offs)]:
        for e in (Point(sd["line"].coords[0]), Point(sd["line"].coords[-1])):
            best = min(((rl.distance(e), rl) for rl in ex), key=lambda t: t[0], default=None)
            if best and 1.0 < best[0] < 90:
                a, b_ = nearest_points(e, best[1])
                links.append(dict(line=LineString([a, b_]), cls=sd["cls"], surface=sd["surface"], width=sd["width"], prio=sd["prio"]))
    streets += links
    mainl = next(sd for sd in streets if sd["cls"] == "residential")
    names = list(STREET_NAMES)
    rng.shuffle(names)
    out_roads = []
    for k, sd in enumerate(streets):
        out_roads.append(dict(cls=sd["cls"], surface=sd["surface"], width=sd["width"], prio=sd["prio"],
                              name=names[k % len(names)], line=sd["line"]))

    # ---------------- placette au carrefour central de la rue principale
    mid = mainl["line"].interpolate(0.5, normalized=True)
    tang = np.array(mainl["line"].interpolate(0.52, normalized=True).coords[0]) - np.array(mainl["line"].interpolate(0.48, normalized=True).coords[0])
    tang /= np.linalg.norm(tang) + 1e-9
    nn = np.array([-tang[1], tang[0]])
    m = np.array(mid.coords[0])
    placette = Polygon([m - tang * 13 - nn * 10, m + tang * 13 - nn * 10, m + tang * 13 + nn * 10, m - tang * 13 + nn * 10])
    placette = placette.intersection(zone)

    # ---------------- maisons de village mitoyennes, alignées sur les rues
    all_streets = unary_union([r["line"].buffer(r["width"] / 2 + 0.5) for r in out_roads] +
                              [r["line"].buffer(r["width"] / 2 + 0.5) for r in roads if r["line"].distance(zone) < 30])
    blocked = unary_union([all_streets, placette.buffer(1.0), ochre_keep])
    lots = []
    placed = []
    for sd in sorted(out_roads, key=lambda r: -r["prio"]):
        cs = list(sd["line"].coords)
        off = sd["width"] / 2 + 0.6
        for (x0, y0), (x1, y1) in zip(cs[:-1], cs[1:]):
            A, B = np.array([x0, y0]), np.array([x1, y1])
            seg = np.linalg.norm(B - A)
            if seg < 8:
                continue
            u_ = (B - A) / seg
            v_ = np.array([-u_[1], u_[0]])
            for side in (1, -1):
                pos = rng.uniform(1.0, 4.0)
                while pos < seg - 5:
                    w = rng.uniform(5.5, 10.0)
                    d = rng.uniform(10.0, 16.0)
                    if rng.random() < 0.07:             # passage, jardinet
                        pos += rng.uniform(3.0, 6.0)
                        continue
                    p0 = A + u_ * pos + v_ * side * off
                    p1 = A + u_ * min(pos + w, seg) + v_ * side * off
                    q = Polygon([p0, p1, p1 + v_ * side * d, p0 + v_ * side * d])
                    pos += w
                    if not q.is_valid or q.area < 30:
                        continue
                    if not zone.contains(q) or q.intersects(blocked) or slope_at(q.centroid.x, q.centroid.y) > 26:
                        continue
                    if placed and any(q.buffer(-0.05).intersects(o) for o in placed if o.distance(q) < 1):
                        continue
                    placed.append(q)
                    lots.append(q)
    blds = [dict(poly=q, cls=None, subtype=None, name="", height=None, floors=None, id="quartier-ocres-%04d" % k)
            for k, q in enumerate(lots)]
    return zone, blds, out_roads, ([placette] if placette.area > 100 else [])
